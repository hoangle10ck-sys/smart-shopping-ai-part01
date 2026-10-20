import type { ParsedRequirement } from "@/types/shopping";
import { finiteNumber, formatMoney } from "@/lib/results-utils";

export function RequirementSummary({ requirement }: { requirement?: ParsedRequirement | null }) {
  const confidence = finiteNumber(requirement?.confidence);
  const mode = requirement?.budget_mode;

  return (
    <section
      aria-label="Nhu cầu đã phân tích"
      className="surface mb-6 border-[var(--line)] p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-4">
        <div>
          <h2 className="section-title text-base sm:text-lg">Nhu cầu đã phân tích</h2>
          <p className="muted mt-1 text-xs">
            Các tiêu chí được trích xuất từ câu mô tả của bạn để lọc và xếp hạng sản phẩm.
          </p>
        </div>
        {mode && (
          <span className="tag tag-green !px-3 !py-1 !text-xs font-semibold">
            {mode === "FLEXIBLE_TARGET"
              ? "Ngân sách linh hoạt"
              : mode === "HARD_MAX"
              ? "Giới hạn ngân sách"
              : "Khoảng ngân sách"}
          </span>
        )}
      </div>

      {!requirement ? (
        <p className="muted mt-4 text-sm">Phiên này chưa có dữ liệu nhu cầu đã phân tích.</p>
      ) : (
        <>
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Danh mục", requirement.category || "Chưa xác định"],
              ...(mode === "FLEXIBLE_TARGET"
                ? [
                    ["Ngân sách mục tiêu", formatMoney(requirement.budget_target, requirement.currency)],
                    [
                      "Khoảng giá tham khảo",
                      `${formatMoney(requirement.preferred_min, requirement.currency)} – ${formatMoney(requirement.preferred_max, requirement.currency)}`,
                    ],
                  ]
                : mode === "RANGE"
                ? [
                    [
                      "Khoảng ngân sách",
                      `${formatMoney(requirement.budget_min, requirement.currency)} – ${formatMoney(requirement.budget_max, requirement.currency)}`,
                    ],
                  ]
                : [
                    ...(requirement.budget_min != null
                      ? [["Ngân sách tối thiểu", formatMoney(requirement.budget_min, requirement.currency)]]
                      : []),
                    ["Ngân sách tối đa", formatMoney(requirement.budget_max, requirement.currency)],
                  ]),
              ["Mục đích", requirement.purpose?.join(", ") || "Chưa cung cấp"],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-3.5"
              >
                <dt className="muted text-xs font-medium">{label}</dt>
                <dd className="mt-1 font-semibold text-[var(--foreground)]">{value}</dd>
              </div>
            ))}
          </dl>

          {requirement.requirements?.length ? (
            <div className="mt-5">
              <p className="field-label mb-2">Tiêu chí quan tâm & mức độ ưu tiên:</p>
              <ul aria-label="Tiêu chí và mức ưu tiên" className="flex flex-wrap gap-2">
                {requirement.requirements.map((item, index) => (
                  <li
                    key={index}
                    className="tag !rounded-lg !bg-white !px-3 !py-1.5 shadow-2xs border-[var(--line)]"
                  >
                    <strong className="text-[var(--foreground)] font-semibold">{item.name}</strong>:{" "}
                    <span className="text-[var(--foreground)]">{item.value || "Chưa có giá trị"}</span>
                    {item.priority != null && (
                      <span className="muted ml-1 font-mono text-[10px]">· Ưu tiên {item.priority}/5</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="muted mt-4 text-xs">Chưa có tiêu chí cụ thể.</p>
          )}

          <details className="mt-4 border-t border-[var(--line)] pt-3 text-xs">
            <summary className="muted cursor-pointer hover:text-[var(--foreground)] font-medium">
              Thông tin nhu cầu bổ sung
            </summary>
            <div className="muted mt-2 space-y-1.5 rounded-lg bg-[var(--surface-subtle)] p-3">
              <p>Thương hiệu: {requirement.brands?.join(", ") || "Không chỉ định"}</p>
              <p>
                Loại trừ:{" "}
                {requirement.excluded_requirements?.join(", ") || "Không có tiêu chí loại trừ được cung cấp"}
              </p>
              <p>
                Tiền tệ: {requirement.currency || "Chưa xác định"} · Confidence phân tích:{" "}
                {confidence === null ? "Chưa có dữ liệu" : `${(confidence * 100).toFixed(1)}%`}
              </p>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
