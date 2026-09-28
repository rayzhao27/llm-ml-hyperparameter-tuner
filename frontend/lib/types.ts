// Mirrors backend/models.py StreamEvent + run/trial shapes.

export type RunStatus = "queued" | "running" | "completed" | "failed";
export type TrialStatus = "running" | "completed" | "failed";

export type StreamEventType =
  | "log"
  | "status"
  | "trial_started"
  | "proposal"
  | "metrics"
  | "recommendation"
  | "error";

export interface EpochMetrics {
  epoch: number;
  train_loss: number;
  val_loss: number;
  ppl?: number | null;
}

export interface ParseToolOutput {
  epochs: EpochMetrics[];
  best_val_loss?: number | null;
  final_val_loss?: number | null;
  converging: boolean;
  summary: string;
}

export interface StreamEvent {
  type: StreamEventType;
  run_id: string;
  ts: string;
  trial?: number | null;
  message?: string | null;
  data?: Record<string, unknown> | null;
}

export interface BaselineConfig {
  metric_name: string;
  metric_value: number;
  higher_is_better: boolean;
  epochs: number;
  note?: string;
}

export interface AgentConfig {
  trainer_path: string;
  project_dir: string;
  smoke_epochs: number;
  max_trials: number;
  baseline: BaselineConfig;
  extra_flags?: string;
  agent_persona?: string;
  python_bin?: string;
}

export interface TrialRecord {
  trial_number: number;
  status: TrialStatus;
  rationale?: string | null;
  hypothesis?: string | null;
  command_flags?: string | null;
  metrics?: ParseToolOutput | null;
  exit_code?: number | null;
  timed_out: boolean;
  error?: string | null;
}

export interface CreateRunResponse {
  run_id: string;
  status: RunStatus;
  stream_url: string;
}

export interface RunResponse {
  run_id: string;
  status: RunStatus;
  config: AgentConfig;
  trials: TrialRecord[];
  recommendation?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrialView {
  trial_number: number;
  status: TrialStatus;
  rationale?: string;
  hypothesis?: string;
  command_flags?: string;
  metrics?: ParseToolOutput;
  exit_code?: number;
  timed_out: boolean;
  error?: string;
  logs: string[];
}
