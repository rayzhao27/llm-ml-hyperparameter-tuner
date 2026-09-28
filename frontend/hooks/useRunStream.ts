"use client";

import { useEffect, useRef, useState } from "react";

import { streamUrl } from "@/lib/api";
import { applyEvent, emptyRunState, type RunViewState } from "@/lib/applyEvent";
import type { StreamEvent } from "@/lib/types";

export type SocketStatus = "idle" | "connecting" | "open" | "reconnecting";

const MAX_DELAY_MS = 8000;

export function useRunStream(runId: string | null): {
  state: RunViewState;
  socketStatus: SocketStatus;
} {
  const [state, setState] = useState<RunViewState>(emptyRunState);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("idle");
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (!runId) {
      setState(emptyRunState());
      setSocketStatus("idle");
      return;
    }

    let cancelled = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let terminal = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const clearTimer = () => {
      if (timer != null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const connect = () => {
      if (cancelled) return;
      setSocketStatus(attempt === 0 ? "connecting" : "reconnecting");
      const next = new WebSocket(streamUrl(runId));
      socket = next;

      next.onopen = () => {
        if (cancelled) return;
        attempt = 0;
        terminal = false;
        // Backend replays full history on every connect — reset so reconnects do not duplicate.
        setState({ ...emptyRunState(), runId, status: "running" });
        setSocketStatus("open");
      };

      next.onmessage = (message) => {
        if (cancelled) return;
        let event: StreamEvent;
        try {
          event = JSON.parse(message.data) as StreamEvent;
        } catch {
          return;
        }
        const status = event.data?.status;
        if (
          event.type === "status" &&
          (status === "completed" || status === "failed")
        ) {
          terminal = true;
        }
        setState((prev) => applyEvent(prev, event));
      };

      next.onerror = () => {
        next.close();
      };

      next.onclose = () => {
        if (cancelled) return;
        const status = stateRef.current.status;
        if (terminal || status === "completed" || status === "failed") {
          setSocketStatus("idle");
          return;
        }
        attempt += 1;
        const delay = Math.min(500 * 2 ** (attempt - 1), MAX_DELAY_MS);
        setSocketStatus("reconnecting");
        timer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimer();
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close();
      }
    };
  }, [runId]);

  return { state, socketStatus };
}
