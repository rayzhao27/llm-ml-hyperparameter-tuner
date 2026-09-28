import type { AgentConfig, CreateRunResponse, RunResponse } from "./types";

export function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

export function streamUrl(runId: string): string {
  const http = apiBase();
  const ws = http.startsWith("https://")
    ? http.replace(/^https:/, "wss:")
    : http.replace(/^http:/, "ws:");
  return `${ws}/runs/${runId}/stream`;
}

function formatApiError(status: number, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const loc = Array.isArray((item as { loc?: unknown }).loc)
              ? (item as { loc: unknown[] }).loc.slice(1).join(".")
              : "";
            return loc
              ? `${loc}: ${(item as { msg: string }).msg}`
              : String((item as { msg: string }).msg);
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
  }
  return `Request failed (${status})`;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function startRun(config: AgentConfig): Promise<CreateRunResponse> {
  const response = await fetch(`${apiBase()}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  const body = await readJson(response);
  if (!response.ok) {
    throw new Error(formatApiError(response.status, body));
  }
  return body as CreateRunResponse;
}

export async function getRun(runId: string): Promise<RunResponse> {
  const response = await fetch(`${apiBase()}/runs/${runId}`);
  const body = await readJson(response);
  if (!response.ok) {
    throw new Error(formatApiError(response.status, body));
  }
  return body as RunResponse;
}
