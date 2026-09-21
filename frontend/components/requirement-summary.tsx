import type { ParsedRequirement } from "@/types/shopping";
import { finiteNumber, formatMoney } from "@/lib/results-utils";

export function RequirementSummary({ requirement }: { requirement?: ParsedRequirement | null }) {
  const confidence = finiteNumber(requirement?.confidence);
  return (
    <section aria-label="Nhu cầu đã phân tích" className="mb-6 rounded-3xl border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-extrabold">Nhu cầu đã phân tích</h2>
      {!requirement ? <p className="mt-3 text-sm text-slate-500">Phiên này chưa có dữ liệu nhu cầu đã phân tích.</p> : <>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Danh mục", requirement.category || "Chưa xác định"],
            ...(requirement.budget_mode === "FLEXIBLE_TARGET" ? [
              ["Ngân sách mục tiêu", formatMoney(requirement.budget_target, requirement.currency)],
              ["Khoảng giá tham khảo", `${formatMoney(requirement.preferred_min, requirement.currency)} – ${formatMoney(requirement.preferred_max, requirement.currency)}`],
            ] : requirement.budget_mode === "RANGE" ? [
              ["Khoảng ngân sách", `${formatMoney(requirement.budget_min, requirement.currency)} – ${formatMoney(requirement.budget_max, requirement.currency)}`],
            ] : [
              ["Ngân sách tối thiểu", formatMoney(requirement.budget_min, requirement.currency)],
              ["Ngân sách tối đa", formatMoney(requirement.budget_max, requirement.currency)],
            ]),
            ["Tiền tệ", requirement.currency || "Chưa xác định"],
            ["Mục đích", requirement.purpose?.join(", ") || "Chưa cung cấp"],
            ["Thương hiệu", requirement.brands?.join(", ") || "Không có thương hiệu được chỉ định"],
            ["Confidence phân tích nhu cầu", confidence === null ? "Chưa có dữ liệu" : `${(confidence * 100).toFixed(1)}%`],
          ].map(([label, value]) => <div key={label}><dt className="text-slate-500">{label}</dt><dd className="mt-1 break-words font-semibold">{value}</dd></div>)}
        </dl>
        <h3 className="mt-5 text-sm font-bold">Tiêu chí và mức ưu tiên</h3>
        {requirement.requirements?.length ? <ul className="mt-2 space-y-2 text-sm">
          {requirement.requirements.map((item, index) => <li key={index} className="rounded-xl bg-slate-50 p-3">
            <strong>{item.name}</strong>: {item.value || "Chưa có giá trị"}
            <span className="ml-2 text-slate-500">Ưu tiên: {item.priority == null ? "Chưa cung cấp" : `${item.priority}/5`}</span>
          </li>)}
        </ul> : <p className="mt-2 text-sm text-slate-500">Chưa có tiêu chí cụ thể.</p>}
        <p className="mt-4 text-sm"><strong>Loại trừ:</strong> {requirement.excluded_requirements?.join(", ") || "Không có tiêu chí loại trừ được cung cấp"}</p>
      </>}
    </section>
  );
}
