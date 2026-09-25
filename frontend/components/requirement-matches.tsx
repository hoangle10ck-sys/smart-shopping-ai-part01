import type { RequirementMatch } from "@/types/shopping";

const STATUS_LABELS = {
  matched: "✓ Đáp ứng",
  unmet: "✕ Không đáp ứng",
  unknown: "? Chưa đủ dữ liệu",
};

export function RequirementMatches({ items }: { items?: RequirementMatch[] }) {
  if (!items?.length) return <p className="mt-3 text-slate-500">Backend chưa cung cấp đối chiếu từng yêu cầu cho kết quả này.</p>;
  return <ul aria-label="Đối chiếu yêu cầu" className="mt-3 space-y-3">
    {items.map((item, index) => <li key={index} className="rounded-xl border border-[#e4e9e1] p-3 text-xs leading-5">
      <p className={`font-semibold ${item.status === 'matched' ? 'text-[#24623d]' : item.status === 'unmet' ? 'text-[#a3423e]' : 'text-[#69756d]'}`}>{STATUS_LABELS[item.status]} — {item.name}</p>
      <p className="mt-1">Yêu cầu: {item.requested_value}</p>
      <p>Sản phẩm: {item.product_value ?? "Chưa có dữ liệu"}</p>
      <p className="muted mt-1 text-xs">{item.reason}</p>
    </li>)}
  </ul>;
}
