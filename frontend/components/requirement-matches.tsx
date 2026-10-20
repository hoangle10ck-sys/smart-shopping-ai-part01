import type { RequirementMatch } from "@/types/shopping";

const STATUS_LABELS = {
  matched: "✓ Đáp ứng",
  unmet: "✕ Không đáp ứng",
  unknown: "? Chưa đủ dữ liệu",
};

export function RequirementMatches({ items }: { items?: RequirementMatch[] }) {
  if (!items?.length) {
    return (
      <p className="mt-3 text-xs text-[var(--muted)]">
        Backend chưa cung cấp đối chiếu từng yêu cầu cho kết quả này.
      </p>
    );
  }

  return (
    <ul aria-label="Đối chiếu yêu cầu" className="mt-3 space-y-2.5">
      {items.map((item, index) => (
        <li
          key={index}
          className={`rounded-xl border p-3 text-xs leading-relaxed transition-colors ${
            item.status === "matched"
              ? "border-[#cce5d4] bg-[#f0f8f3]"
              : item.status === "unmet"
              ? "border-[#f7d2d2] bg-[#fdf2f2]"
              : "border-[var(--line)] bg-[var(--surface-subtle)]"
          }`}
        >
          <p
            className={`font-semibold ${
              item.status === "matched"
                ? "text-[#165b39]"
                : item.status === "unmet"
                ? "text-[#9c2b2b]"
                : "text-[var(--muted)]"
            }`}
          >
            {STATUS_LABELS[item.status]} — {item.name}
          </p>
          <div className="mt-1.5 space-y-0.5 text-[var(--foreground)]">
            <p>
              <span className="text-[var(--muted)]">Yêu cầu:</span>{" "}
              <span className="font-medium">{item.requested_value}</span>
            </p>
            <p>
              <span className="text-[var(--muted)]">Sản phẩm:</span>{" "}
              <span className="font-medium">{item.product_value ?? "Chưa có dữ liệu"}</span>
            </p>
          </div>
          {item.reason && (
            <p className="muted mt-1.5 border-t border-black/5 pt-1 text-[11px] italic">
              {item.reason}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
