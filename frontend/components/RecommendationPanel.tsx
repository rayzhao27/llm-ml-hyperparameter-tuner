"use client";

export function RecommendationPanel({
  recommendation,
  error,
}: {
  recommendation: string | null;
  error: string | null;
}) {
  if (!recommendation && !error) return null;

  if (error && !recommendation) {
    return (
      <section className="rounded-xl border border-red-200 bg-red-50 p-4">
        <h2 className="mb-2 text-sm font-semibold text-red-900">Run failed</h2>
        <p className="whitespace-pre-wrap text-sm text-red-800">{error}</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-900 bg-zinc-900 p-4 text-zinc-50">
      <h2 className="mb-2 text-sm font-semibold">Final recommendation</h2>
      <p className="whitespace-pre-wrap text-sm leading-6 text-zinc-100">{recommendation}</p>
    </section>
  );
}
