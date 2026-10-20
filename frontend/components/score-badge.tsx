import { displayScore, finiteNumber } from "@/lib/results-utils";

export function ScoreBadge({
  value,
  label = "AI Match",
}: {
  value?: number | null;
  label?: string;
}) {
  const score = finiteNumber(value);

  return (
    <div className="rounded-xl border border-[#d6e3da] bg-[#f0f6f2] p-3 transition-colors">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-[#2f5540]">{label}</span>
        <span className="font-mono text-sm font-bold text-[#0f5b44]">
          {displayScore(value)}
        </span>
      </div>
      {score !== null && (
        <div
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#d7e4db]"
          aria-hidden="true"
        >
          <div
            className="h-full rounded-full bg-[#0f5b44] transition-all duration-300"
            style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
          />
        </div>
      )}
    </div>
  );
}
