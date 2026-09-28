from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agent.config import AgentConfig
from agent.observability import configure_logging, observe_error
from backend.models import CreateRunResponse, HealthResponse, RunResponse, StreamEvent
from backend.runner import AgentRunner
from backend.store import RunStore


def _validate_runtime_config(cfg: AgentConfig) -> None:
    trainer = Path(cfg.trainer_path)
    if not trainer.is_file():
        observe_error("config", error=f"trainer_path not found: {cfg.trainer_path}")
        raise HTTPException(status_code=400, detail=f"trainer_path not found: {cfg.trainer_path}")
    project = Path(cfg.project_dir)
    if not project.is_dir():
        observe_error("config", error=f"project_dir not found: {cfg.project_dir}")
        raise HTTPException(status_code=400, detail=f"project_dir not found: {cfg.project_dir}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    configure_logging()
    store = RunStore()
    store.loop = asyncio.get_running_loop()
    app.state.store = store
    app.state.runner = AgentRunner(store)
    yield


app = FastAPI(
    title="ML Agent API",
    version="0.1.0",
    description="Start agent runs and stream trial logs, proposals, and metrics.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="ml-agent")


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/runs", response_model=CreateRunResponse, status_code=201)
def create_run(cfg: AgentConfig, request: Request) -> CreateRunResponse:
    _validate_runtime_config(cfg)
    store: RunStore = request.app.state.store
    runner: AgentRunner = request.app.state.runner
    run = store.create(cfg)
    runner.start(run.run_id, cfg)
    return CreateRunResponse(
        run_id=run.run_id,
        status=run.status,
        stream_url=f"/runs/{run.run_id}/stream",
    )


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, request: Request) -> RunResponse:
    store: RunStore = request.app.state.store
    run = store.get(run_id)
    if run is None:
        observe_error("http", error=f"run not found: {run_id}")
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run.snapshot()


@app.websocket("/runs/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    store: RunStore = websocket.app.state.store
    run = store.get(run_id)
    if run is None:
        await websocket.close(code=4004, reason="run not found")
        return

    await websocket.accept()
    replay, queue = store.subscribe(run_id)
    try:
        for event in replay:
            await websocket.send_json(event.model_dump(mode="json"))
            if _is_terminal(event):
                return

        while True:
            event = await queue.get()
            if event is None:
                return
            await websocket.send_json(event.model_dump(mode="json"))
            if _is_terminal(event):
                return
    except WebSocketDisconnect:
        return
    finally:
        store.unsubscribe(run_id, queue)


def _is_terminal(event: StreamEvent) -> bool:
    if event.type != "status" or not event.data:
        return False
    return event.data.get("status") in {"completed", "failed"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
