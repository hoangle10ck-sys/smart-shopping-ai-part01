import type { ParsedRequirement } from "@/types/shopping";
import { finiteNumber, formatMoney } from "@/lib/results-utils";

export function RequirementSummary({ requirement }: { requirement?: ParsedRequirement | null }) {
  const confidence = finiteNumber(requirement?.confidence);
  const mode = requirement?.budget_mode;
  return <section aria-label="Nhu cầu đã phân tích" className="surface mb-6 p-5 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="section-title">Nhu cầu đã phân tích</h2>{mode && <span className="tag tag-green">{mode === 'FLEXIBLE_TARGET' ? 'Ngân sách linh hoạt' : mode === 'HARD_MAX' ? 'Giới hạn ngân sách' : 'Khoảng ngân sách'}</span>}</div>
    {!requirement ? <p className="muted mt-3 text-sm">Phiên này chưa có dữ liệu nhu cầu đã phân tích.</p> : <>
      <dl className="mt-5 grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Danh mục", requirement.category || "Chưa xác định"],
          ...(mode === "FLEXIBLE_TARGET" ? [
            ["Ngân sách mục tiêu", formatMoney(requirement.budget_target, requirement.currency)],
            ["Khoảng giá tham khảo", `${formatMoney(requirement.preferred_min, requirement.currency)} – ${formatMoney(requirement.preferred_max, requirement.currency)}`],
          ] : mode === "RANGE" ? [["Khoảng ngân sách", `${formatMoney(requirement.budget_min, requirement.currency)} – ${formatMoney(requirement.budget_max, requirement.currency)}`]] : [
            ...(requirement.budget_min != null ? [["Ngân sách tối thiểu", formatMoney(requirement.budget_min, requirement.currency)]] : []),
            ["Ngân sách tối đa", formatMoney(requirement.budget_max, requirement.currency)],
          ]),
          ["Mục đích", requirement.purpose?.join(", ") || "Chưa cung cấp"],
        ].map(([label,value]) => <div key={label}><dt className="muted text-xs">{label}</dt><dd className="mt-1.5 font-semibold">{value}</dd></div>)}
      </dl>
      {requirement.requirements?.length ? <ul aria-label="Tiêu chí và mức ưu tiên" className="mt-5 flex flex-wrap gap-2">{requirement.requirements.map((item,index) => <li key={index} className="tag"><strong>{item.name}</strong>: {item.value || "Chưa có giá trị"}{item.priority != null && <span className="muted">· Ưu tiên {item.priority}/5</span>}</li>)}</ul> : <p className="muted mt-4 text-xs">Chưa có tiêu chí cụ thể.</p>}
      <details className="mt-4 text-xs"><summary className="muted">Thông tin nhu cầu bổ sung</summary><div className="muted mt-2 space-y-2"><p>Thương hiệu: {requirement.brands?.join(", ") || "Không chỉ định"}</p><p>Loại trừ: {requirement.excluded_requirements?.join(", ") || "Không có tiêu chí loại trừ được cung cấp"}</p><p>Tiền tệ: {requirement.currency || "Chưa xác định"} · Confidence phân tích: {confidence === null ? "Chưa có dữ liệu" : `${(confidence*100).toFixed(1)}%`}</p></div></details>
    </>}
  </section>;
}
