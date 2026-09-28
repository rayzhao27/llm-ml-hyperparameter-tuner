"use client";

import { FormEvent, type ReactNode, useState } from "react";

import type { AgentConfig } from "@/lib/types";

const DEFAULT_FORM: AgentConfig = {
  trainer_path: "/content/bert4rec/training/trainer.py",
  project_dir: "/content/bert4rec",
  smoke_epochs: 5,
  max_trials: 3,
  extra_flags: "",
  python_bin: "python3",
  agent_persona: "You are an expert ML engineer.",
  baseline: {
    metric_name: "val_loss",
    metric_value: 5.8259,
    higher_is_better: false,
    epochs: 300,
    note: "",
  },
};

interface RunFormProps {
  disabled?: boolean;
  error?: string | null;
  onSubmit: (config: AgentConfig) => void;
}

export function RunForm({ disabled, error, onSubmit }: RunFormProps) {
  const [form, setForm] = useState<AgentConfig>(DEFAULT_FORM);

  const update = (field: string, value: string | number | boolean) => {
    setForm((prev) => {
      if (field.startsWith("baseline.")) {
        const key = field.slice("baseline.".length) as keyof AgentConfig["baseline"];
        return { ...prev, baseline: { ...prev.baseline, [key]: value } };
      }
      return { ...prev, [field]: value };
    });
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(form);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Trainer path" htmlFor="trainer_path">
          <input
            id="trainer_path"
            required
            value={form.trainer_path}
            onChange={(e) => update("trainer_path", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Project dir" htmlFor="project_dir">
          <input
            id="project_dir"
            required
            value={form.project_dir}
            onChange={(e) => update("project_dir", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Smoke epochs" htmlFor="smoke_epochs">
          <input
            id="smoke_epochs"
            type="number"
            min={1}
            required
            value={form.smoke_epochs}
            onChange={(e) => update("smoke_epochs", Number(e.target.value))}
            className="input"
          />
        </Field>
        <Field label="Max trials" htmlFor="max_trials">
          <input
            id="max_trials"
            type="number"
            min={1}
            required
            value={form.max_trials}
            onChange={(e) => update("max_trials", Number(e.target.value))}
            className="input"
          />
        </Field>
        <Field label="Python bin" htmlFor="python_bin">
          <input
            id="python_bin"
            value={form.python_bin}
            onChange={(e) => update("python_bin", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Extra flags" htmlFor="extra_flags">
          <input
            id="extra_flags"
            value={form.extra_flags}
            onChange={(e) => update("extra_flags", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Baseline metric" htmlFor="metric_name">
          <input
            id="metric_name"
            required
            value={form.baseline.metric_name}
            onChange={(e) => update("baseline.metric_name", e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Baseline value" htmlFor="metric_value">
          <input
            id="metric_value"
            type="number"
            step="any"
            required
            value={form.baseline.metric_value}
            onChange={(e) => update("baseline.metric_value", Number(e.target.value))}
            className="input"
          />
        </Field>
        <Field label="Full-run epochs" htmlFor="epochs">
          <input
            id="epochs"
            type="number"
            min={1}
            required
            value={form.baseline.epochs}
            onChange={(e) => update("baseline.epochs", Number(e.target.value))}
            className="input"
          />
        </Field>
        <label className="flex items-end gap-2 pb-2 text-sm text-zinc-700">
          <input
            type="checkbox"
            checked={form.baseline.higher_is_better}
            onChange={(e) => update("baseline.higher_is_better", e.target.checked)}
          />
          Higher is better
        </label>
      </div>
      <Field label="Baseline note" htmlFor="note">
        <input
          id="note"
          value={form.baseline.note}
          onChange={(e) => update("baseline.note", e.target.value)}
          className="input"
        />
      </Field>
      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={disabled}
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? "Run in progress…" : "Start run"}
      </button>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <label htmlFor={htmlFor} className="block text-sm">
      <span className="mb-1 block text-zinc-600">{label}</span>
      {children}
    </label>
  );
}
