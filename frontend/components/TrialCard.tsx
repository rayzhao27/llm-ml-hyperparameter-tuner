"use client";

import { useEffect, useRef } from "react";

import type { TrialView } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  running: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function TrialCard({ trial }: { trial: TrialView }) {
  const logRef = useRef<HTMLPreElement>(null);
  const title = trial.trial_number === 0 ? "Setup" : `Trial ${trial.trial_number}`;

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [trial.logs]);

  return (
    <article className="flex flex-col rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[trial.status]}`}
        >
          {trial.timed_out ? "timed out" : trial.status}
        </span>
      </header>

      {trial.rationale ? (
        <p className="mb-2 text-sm text-zinc-700">
          <span className="font-medium text-zinc-900">Rationale. </span>
          {trial.rationale}
        </p>
      ) : null}
      {trial.hypothesis ? (
        <p className="mb-2 text-sm text-zinc-700">
          <span className="font-medium text-zinc-900">Hypothesis. </span>
          {trial.hypothesis}
        </p>
      ) : null}
      {trial.command_flags ? (
        <p className="mb-2 font-mono text-xs text-zinc-600">
          {trial.command_flags}
        </p>
      ) : null}
      {trial.metrics ? (
        <p className="mb-2 text-xs text-zinc-500">{trial.metrics.summary}</p>
      ) : null}
      {trial.error ? (
        <p className="mb-2 text-sm text-red-700">{trial.error}</p>
      ) : null}

      <pre
        ref={logRef}
        className="mt-auto max-h-48 overflow-auto rounded-md bg-zinc-950 px-3 py-2 font-mono text-[11px] leading-5 text-zinc-100"
      >
        {trial.logs.join("") || "waiting for logs…"}
      </pre>
    </article>
  );
}
