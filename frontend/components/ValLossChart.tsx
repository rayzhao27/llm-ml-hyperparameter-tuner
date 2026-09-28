"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TrialView } from "@/lib/types";

const COLORS = ["#18181b", "#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

interface ChartRow {
  epoch: number;
  [key: string]: number;
}

function toRows(trials: TrialView[]): { rows: ChartRow[]; keys: string[] } {
  const keys: string[] = [];
  const byEpoch = new Map<number, ChartRow>();

  for (const trial of trials) {
    if (trial.trial_number === 0 || !trial.metrics?.epochs.length) continue;
    const key = `trial_${trial.trial_number}`;
    keys.push(key);
    for (const epoch of trial.metrics.epochs) {
      const row = byEpoch.get(epoch.epoch) ?? { epoch: epoch.epoch };
      row[key] = epoch.val_loss;
      byEpoch.set(epoch.epoch, row);
    }
  }

  return {
    rows: [...byEpoch.values()].sort((a, b) => a.epoch - b.epoch),
    keys,
  };
}

export function ValLossChart({ trials }: { trials: TrialView[] }) {
  const { rows, keys } = toRows(trials);

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-zinc-900">val_loss by trial</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-zinc-500">No epoch metrics yet.</p>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
              <XAxis dataKey="epoch" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={48} />
              <Tooltip />
              <Legend />
              {keys.map((key, index) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  name={key.replace("_", " ")}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-600">
            <thead>
              <tr className="border-b border-zinc-200">
                <th className="py-1 pr-3 font-medium">epoch</th>
                {keys.map((key) => (
                  <th key={key} className="py-1 pr-3 font-medium">
                    {key.replace("_", " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.epoch} className="border-b border-zinc-100">
                  <td className="py-1 pr-3">{row.epoch}</td>
                  {keys.map((key) => (
                    <td key={key} className="py-1 pr-3 font-mono">
                      {row[key] == null ? "—" : row[key].toFixed(4)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
