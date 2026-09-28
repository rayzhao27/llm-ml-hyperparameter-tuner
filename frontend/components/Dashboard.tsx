"use client";

import { useState } from "react";

import { RecommendationPanel } from "@/components/RecommendationPanel";
import { RunForm } from "@/components/RunForm";
import { TrialCard } from "@/components/TrialCard";
import { ValLossChart } from "@/components/ValLossChart";
import { useRunStream } from "@/hooks/useRunStream";
import { apiBase, startRun } from "@/lib/api";
import type { AgentConfig } from "@/lib/types";

const SOCKET_LABEL = {
  idle: "idle",
  connecting: "connecting",
  open: "live",
  reconnecting: "reconnecting",
} as const;

export function Dashboard() {
  const [runId, setRunId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { state, socketStatus } = useRunStream(runId);

  const running = state.status === "queued" || state.status === "running" || submitting;

  const handleStart = async (config: AgentConfig) => {
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await startRun(config);
      setRunId(created.run_id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">ML Agent</h1>
          <p className="text-sm text-zinc-500">
            Start a run, stream trials live, and read the recommended config.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span>API {apiBase()}</span>
          {runId ? <span className="font-mono">run {runId.slice(0, 8)}</span> : null}
          <span
            className={
              socketStatus === "open"
                ? "text-emerald-700"
                : socketStatus === "reconnecting"
                  ? "text-amber-700"
                  : ""
            }
          >
            {SOCKET_LABEL[socketStatus]}
          </span>
          {state.status !== "idle" ? <span>status {state.status}</span> : null}
        </div>
      </header>

      <section className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-zinc-900">New run</h2>
        <RunForm disabled={running} error={formError} onSubmit={handleStart} />
      </section>

      <ValLossChart trials={state.trials} />

      {state.trials.length > 0 ? (
        <section className="grid gap-4 md:grid-cols-2">
          {state.trials.map((trial) => (
            <TrialCard key={trial.trial_number} trial={trial} />
          ))}
        </section>
      ) : (
        <p className="text-sm text-zinc-500">
          No trials yet. Start a run to stream rationale, logs, and metrics.
        </p>
      )}

      <RecommendationPanel
        recommendation={state.recommendation}
        error={state.error}
      />
    </main>
  );
}
