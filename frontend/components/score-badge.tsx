import { displayScore, finiteNumber } from "@/lib/results-utils";

export function ScoreBadge({ value, label = "AI Match" }: { value?: number | null; label?: string }) {
  const score = finiteNumber(value);
  return <div className="rounded-xl bg-[#eef4eb] p-3"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-semibold text-[#42634c]">{label}</span><span className="text-sm font-bold text-[#245c3d]">{displayScore(value)}</span></div>{score !== null && <div className="mt-2 h-1 overflow-hidden rounded-full bg-[#dbe8d6]" aria-hidden="true"><div className="h-full bg-[#397c53]" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} /></div>}</div>;
}
