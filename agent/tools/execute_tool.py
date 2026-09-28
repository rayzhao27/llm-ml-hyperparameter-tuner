# mirrors BashTool from Claude Code repo
# src/tools/bash.ts — run a command, stream output line by line, return result

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
from typing import Callable, Optional

from pydantic import BaseModel, Field


class ExecuteToolInput(BaseModel):
    command: str
    cwd: str
    timeout_seconds: int = Field(default=600, ge=1)  # 10 min max per smoke test


class ExecuteToolOutput(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    timed_out: bool = False


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def execute_command(
        input: ExecuteToolInput,
        on_output: Optional[Callable[[str], None]] = None,
) -> ExecuteToolOutput:
    try:
        process = subprocess.Popen(
            input.command,
            shell=True,
            cwd=input.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout so logs stream in order
            text=True,
            bufsize=1,  # line buffered
            start_new_session=True,
        )
    except OSError as exc:
        msg = f"failed to start command: {exc}\n"
        if on_output:
            on_output(msg)
        return ExecuteToolOutput(
            stdout=msg.strip(),
            stderr=str(exc),
            exit_code=-1,
            success=False,
        )

    line_q: queue.Queue[Optional[str]] = queue.Queue()
    timed_out = False

    def _reader() -> None:
        try:
            if process.stdout is None:
                return
            for line in process.stdout:
                line_q.put(line)
        finally:
            line_q.put(None)

    def _watchdog() -> None:
        nonlocal timed_out
        finished.wait(input.timeout_seconds)
        if finished.is_set():
            return
        timed_out = True
        _kill_process_group(process)

    finished = threading.Event()
    reader = threading.Thread(target=_reader, daemon=True)
    watchdog = threading.Thread(target=_watchdog, daemon=True)
    reader.start()
    watchdog.start()

    stdout_lines: list[str] = []

    while True:
        line = line_q.get()
        if line is None:
            break
        stdout_lines.append(line)
        if on_output:
            on_output(line)

    finished.set()
    reader.join(timeout=2)
    watchdog.join(timeout=1)

    if process.poll() is None:
        _kill_process_group(process)

    if timed_out:
        timeout_msg = f"\n[timeout] command exceeded {input.timeout_seconds}s and was killed\n"
        stdout_lines.append(timeout_msg)
        if on_output:
            on_output(timeout_msg)
        return ExecuteToolOutput(
            stdout="".join(stdout_lines).strip(),
            stderr=f"timed out after {input.timeout_seconds}s",
            exit_code=-1,
            success=False,
            timed_out=True,
        )

    return ExecuteToolOutput(
        stdout="".join(stdout_lines).strip(),
        stderr="",
        exit_code=process.returncode if process.returncode is not None else -1,
        success=process.returncode == 0,
    )
