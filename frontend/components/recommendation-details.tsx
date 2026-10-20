import type { RecommendationItem } from "@/types/shopping";
import { RequirementMatches } from "@/components/requirement-matches";
import { displayScore, record, safeHttpUrl, scoreRows, textList } from "@/lib/results-utils";

function Notes({ title, items }: { title: string; items: string[] }) {
  return items.length ? (
    <div className="mt-3 rounded-lg border border-[var(--line)] bg-[var(--surface-subtle)] p-3">
      <h4 className="font-semibold text-xs text-[var(--foreground)]">{title}</h4>
      <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs text-[var(--muted)]">
        {items.map((item, index) => (
          <li key={index} className="leading-relaxed">{item}</li>
        ))}
      </ul>
    </div>
  ) : null;
}

export function RecommendationDetails({
  product,
  compact = false,
}: {
  product: RecommendationItem;
  compact?: boolean;
}) {
  const explanation = record(product.explanation);
  const evidence = record(product.evidence);
  const url = safeHttpUrl(product.product_url);
  const timestamp = product.last_checked_at ? new Date(product.last_checked_at) : null;
  const modeNames: Record<string, string> = {
    demo: "Giải thích Demo",
    openai: "Giải thích OpenAI",
    gemini: "Giải thích Gemini",
    fallback: "Giải thích dự phòng",
  };
  const summary =
    typeof explanation.summary === "string"
      ? explanation.summary
      : typeof product.explanation === "string"
      ? product.explanation
      : null;
  const whyFit = textList(explanation.why_fit);
  const research = product.source_mode === "HISTORICAL_RESEARCH";
  const researchParts = record(product.product_suitability?.breakdown);
  const researchWeights = record(product.product_suitability?.weights);
  const rows = research
    ? Object.keys(researchParts).map((key) => ({
        key,
        label: key,
        value: researchParts[key],
        weight: Number(researchWeights[key] ?? 0) * 100,
      }))
    : scoreRows(product.score);

  return (
    <div className="mt-3 text-xs sm:text-sm text-[var(--foreground)]">
      {compact && !!product.requirement_matches?.length && (
        <div className="mb-3 flex flex-wrap gap-1.5" aria-label="Tóm tắt mức đáp ứng">
          {(["matched", "unknown", "unmet"] as const).map((status) => {
            const count = product.requirement_matches!.filter((item) => item.status === status).length;
            return count ? (
              <span
                key={status}
                className={`tag !py-0.5 !text-[10px] ${
                  status === "matched"
                    ? "tag-green"
                    : status === "unmet"
                    ? "tag-red"
                    : ""
                }`}
              >
                {status === "matched"
                  ? "✓ Đáp ứng"
                  : status === "unmet"
                  ? "✕ Không đáp ứng"
                  : "? Chưa đủ dữ liệu"}
                : {count}
              </span>
            ) : null;
          })}
        </div>
      )}

      {/* 1. Mức đáp ứng yêu cầu */}
      <details open={!compact} className="detail-disclosure">
        <summary>Mức đáp ứng yêu cầu</summary>
        <RequirementMatches items={product.requirement_matches} />
      </details>

      {/* 2. Điểm thành phần */}
      <details className="detail-disclosure">
        <summary className="cursor-pointer font-bold text-slate-950">Điểm thành phần</summary>
        <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-3.5">
          <p className="text-xs font-medium text-[var(--foreground)]">
            Final AI Match: <strong className="font-mono text-sm text-[var(--brand)]">{displayScore(product.score?.final_score)}</strong>
          </p>
          <p className="mt-1 text-[11px] text-[var(--muted)]">
            Điểm gốc theo thang 100 và trọng số của từng tiêu chí trong kết quả này.
          </p>
          <table className="mt-3 w-full text-left text-xs">
            <caption className="sr-only">Điểm gốc và trọng số</caption>
            <thead>
              <tr className="border-b border-[var(--line)] text-[11px] font-semibold text-[var(--muted)]">
                <th scope="col" className="pb-1.5 font-semibold">Thành phần</th>
                <th scope="col" className="pb-1.5 font-semibold">Điểm gốc</th>
                <th scope="col" className="pb-1.5 font-semibold">Trọng số</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {rows.map((row) => (
                <tr key={row.key} className="hover:bg-white/60">
                  <th scope="row" className="py-2 font-medium text-[var(--foreground)]">{row.label}</th>
                  <td className="py-2 font-mono">{displayScore(row.value)}</td>
                  <td className="py-2 font-mono text-[var(--muted)]">{Number(row.weight.toFixed(2))}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {/* 3. Vì sao được đề xuất? */}
      <details className="detail-disclosure">
        <summary className="cursor-pointer font-bold text-slate-950">Vì sao được đề xuất?</summary>
        <div className="mt-3 space-y-2.5">
          <p className="text-xs leading-relaxed text-[var(--foreground)]">
            {summary || "Backend chưa cung cấp phần tóm tắt giải thích."}
          </p>
          {typeof explanation.generation_mode === "string" && (
            <p className="text-[11px] font-medium text-[var(--brand)]">
              {modeNames[explanation.generation_mode] || "Chưa rõ cách tạo giải thích"}
            </p>
          )}
          <Notes title="Lý do phù hợp" items={whyFit} />
          <Notes title="Ưu điểm" items={[...textList(product.pros), ...textList(explanation.pros)]} />
          <Notes
            title="Hạn chế / đánh đổi"
            items={[...textList(product.cons), ...textList(explanation.cons), ...textList(explanation.tradeoffs)]}
          />
          <Notes
            title="Lưu ý từ backend"
            items={[...textList(explanation.cautions), ...textList(explanation.evidence_notes)]}
          />
        </div>
      </details>

      {/* 4. Nguồn và bằng chứng */}
      <details className="detail-disclosure">
        <summary className="cursor-pointer font-bold text-slate-950">Nguồn và bằng chứng</summary>
        <div className="mt-3 space-y-3">
          {product.evidence?.fields?.length ? (
            <ul aria-label="Bằng chứng theo trường" className="space-y-2.5 break-words">
              {product.evidence.fields.map((field, index) => {
                const fieldUrl = safeHttpUrl(field.url);
                return (
                  <li key={index} className="rounded-xl border border-[#dfe8e2] bg-[#f4f8f5] p-3 text-xs leading-relaxed">
                    <p className="font-bold text-[var(--foreground)]">
                      {field.field}: <span className="font-mono">{field.value}</span>
                    </p>
                    <p className="text-[var(--muted)] mt-1">Nguồn: {field.source || "Chưa cung cấp"}</p>
                    <p className="text-[var(--muted)]">
                      Domain: {field.domain || "Chưa cung cấp"} · Merchant: {field.merchant || "Chưa cung cấp"}
                    </p>
                    <p className="text-[var(--muted)]">Thời điểm thu thập: {field.retrieved_at || "Chưa cung cấp"}</p>
                    {field.reliability != null && (
                      <p className="font-medium text-[var(--brand)]">Độ tin cậy nguồn: {field.reliability}/100</p>
                    )}
                    {fieldUrl && (
                      <a
                        href={fieldUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--brand)] underline hover:opacity-80 mt-1 block truncate"
                      >
                        {fieldUrl}
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-xs text-[var(--muted)]">Chưa có evidence có cấu trúc cho kết quả này.</p>
          )}

          {!research && (
            <dl className="space-y-1.5 rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-3 text-xs break-words">
              <div>
                <dt className="text-[var(--muted)] font-medium">Merchant / cửa hàng</dt>
                <dd className="font-semibold text-[var(--foreground)]">{product.merchant || "Chưa được cung cấp"}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)] font-medium">Domain của URL sản phẩm</dt>
                <dd className="font-mono">{url ? new URL(url).hostname : "Chưa có URL hợp lệ"}</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)] font-medium">Lần kiểm tra offer ghi trong snapshot</dt>
                <dd>
                  {timestamp && !Number.isNaN(timestamp.getTime())
                    ? timestamp.toLocaleString("vi-VN")
                    : "Backend chưa lưu thời điểm kiểm tra cho kết quả này"}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--muted)] font-medium">URL sản phẩm</dt>
                <dd>
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer" className="text-[var(--brand)] underline truncate block">
                      {url}
                    </a>
                  ) : (
                    "Chưa được cung cấp"
                  )}
                </dd>
              </div>
            </dl>
          )}

          <Notes
            title="Bằng chứng giá / rating / thông số từ backend"
            items={textList(evidence.supporting_evidence)}
          />
          {!textList(evidence.supporting_evidence).length && (
            <p className="text-xs text-[var(--muted)]">Chưa có bằng chứng chi tiết được backend cung cấp.</p>
          )}
          <Notes title="Cảnh báo dữ liệu" items={textList(evidence.warnings)} />
          <p className="text-[11px] text-[var(--muted)] italic">
            Thông tin thuộc kết quả đã lưu; không khẳng định giá hiện tại của cửa hàng.
          </p>
        </div>
      </details>
    </div>
  );
}
