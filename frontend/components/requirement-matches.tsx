import type { RequirementMatch } from "@/types/shopping";

const STATUS_LABELS = {
  matched: "✓ Đáp ứng",
  unmet: "✕ Không đáp ứng",
  unknown: "? Chưa đủ dữ liệu",
};

export function RequirementMatches({ items }: { items?: RequirementMatch[] }) {
  if (!items?.length) return <p className="mt-3 text-slate-500">Backend chưa cung cấp đối chiếu từng yêu cầu cho kết quả này.</p>;
  return <ul aria-label="Đối chiếu yêu cầu" className="mt-3 space-y-3">
    {items.map((item, index) => <li key={index} className="rounded-xl bg-slate-50 p-3">
      <p className="font-bold">{STATUS_LABELS[item.status]} — {item.name}</p>
      <p>Yêu cầu: {item.requested_value}</p>
      <p>Sản phẩm: {item.product_value ?? "Chưa có dữ liệu"}</p>
      <p className="mt-1 text-xs text-slate-600">{item.reason}</p>
    </li>)}
  </ul>;
}
