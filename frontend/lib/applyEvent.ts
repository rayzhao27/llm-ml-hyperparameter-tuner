import type {
  ParseToolOutput,
  RunStatus,
  StreamEvent,
  TrialView,
} from "./types";

export interface RunViewState {
  runId: string | null;
  status: RunStatus | "idle";
  currentTrial: number | null;
  trials: TrialView[];
  recommendation: string | null;
  error: string | null;
}

export function emptyRunState(): RunViewState {
  return {
    runId: null,
    status: "idle",
    currentTrial: null,
    trials: [],
    recommendation: null,
    error: null,
  };
}

function upsertTrial(trials: TrialView[], trialNumber: number): TrialView[] {
  if (trials.some((trial) => trial.trial_number === trialNumber)) {
    return trials;
  }
  return [
    ...trials,
    {
      trial_number: trialNumber,
      status: "running" as const,
      timed_out: false,
      logs: [],
    },
  ].sort((a, b) => a.trial_number - b.trial_number);
}

function patchTrial(
  trials: TrialView[],
  trialNumber: number,
  patch: Partial<TrialView>,
): TrialView[] {
  return upsertTrial(trials, trialNumber).map((trial) =>
    trial.trial_number === trialNumber ? { ...trial, ...patch } : trial,
  );
}

function asMetrics(value: unknown): ParseToolOutput | undefined {
  if (!value || typeof value !== "object") return undefined;
  const raw = value as Partial<ParseToolOutput>;
  if (!Array.isArray(raw.epochs)) return undefined;
  return raw as ParseToolOutput;
}

export function applyEvent(state: RunViewState, event: StreamEvent): RunViewState {
  const trialNo = event.trial ?? state.currentTrial;
  const next: RunViewState = {
    ...state,
    runId: event.run_id,
    trials: state.trials.map((trial) => ({ ...trial, logs: [...trial.logs] })),
  };

  switch (event.type) {
    case "status": {
      const status = event.data?.status;
      if (status === "queued" || status === "running" || status === "completed" || status === "failed") {
        next.status = status;
      }
      if (typeof event.data?.error === "string") {
        next.error = event.data.error;
      }
      if (event.message && status === "failed") {
        next.error = event.message;
      }
      return next;
    }
    case "trial_started": {
      if (event.trial == null) return next;
      next.currentTrial = event.trial;
      next.status = "running";
      next.trials = upsertTrial(next.trials, event.trial);
      return next;
    }
    case "proposal": {
      if (trialNo == null) return next;
      next.currentTrial = trialNo;
      next.trials = patchTrial(next.trials, trialNo, {
        rationale: typeof event.data?.rationale === "string" ? event.data.rationale : undefined,
        hypothesis: typeof event.data?.hypothesis === "string" ? event.data.hypothesis : undefined,
        command_flags:
          typeof event.data?.command_flags === "string" ? event.data.command_flags : undefined,
      });
      return next;
    }
    case "metrics": {
      if (trialNo == null) return next;
      const metrics = asMetrics(event.data?.metrics);
      const timedOut = event.data?.timed_out === true;
      next.trials = patchTrial(next.trials, trialNo, {
        metrics,
        exit_code: typeof event.data?.exit_code === "number" ? event.data.exit_code : undefined,
        timed_out: timedOut,
        status: timedOut ? "failed" : "completed",
      });
      return next;
    }
    case "recommendation": {
      const text =
        (typeof event.data?.recommendation === "string" && event.data.recommendation) ||
        event.message ||
        null;
      next.recommendation = text;
      return next;
    }
    case "error": {
      const message =
        (typeof event.data?.error === "string" && event.data.error) || event.message || "error";
      if (trialNo != null) {
        next.trials = patchTrial(next.trials, trialNo, {
          error: message,
          status: "failed",
          timed_out: event.data?.timed_out === true,
        });
      } else {
        next.error = message;
      }
      return next;
    }
    case "log": {
      const line = event.message ?? "";
      if (!line) return next;
      if (trialNo == null) {
        next.trials = upsertTrial(next.trials, 0);
        next.trials = patchTrial(next.trials, 0, {
          logs: [
            ...(next.trials.find((trial) => trial.trial_number === 0)?.logs ?? []),
            line,
          ],
        });
        return next;
      }
      next.currentTrial = trialNo;
      const existing = next.trials.find((trial) => trial.trial_number === trialNo);
      next.trials = patchTrial(next.trials, trialNo, {
        logs: [...(existing?.logs ?? []), line],
      });
      return next;
    }
    default:
      return next;
  }
}
