import type { RecommendationItem } from "@/types/shopping";
import { EMPTY_FILTERS, filterError, type ResultFilters as Filters, type ResultSort } from "@/lib/results-utils";

export function ResultFilters({ products, value, onChange, visibleCount }: {
  products: RecommendationItem[]; value: Filters; onChange: (value: Filters) => void; visibleCount: number;
}) {
  const options = (field: "brand" | "category" | "currency") => [...new Set(products.map((item) => item[field]).filter((item): item is string => !!item))].sort();
  const update = (key: keyof Filters, next: string) => onChange({ ...value, [key]: next });
  const error = filterError(value, products);
  return <section aria-label="Lọc và sắp xếp kết quả" className="mb-6 rounded-2xl border border-slate-200 bg-white p-5">
    <h2 className="font-extrabold">Lọc và sắp xếp trong phiên này</h2>
    <p className="mt-1 text-xs text-slate-500">Chỉ thay đổi cách hiển thị, không đổi điểm hoặc dữ liệu đã lưu. Các sản phẩm đã chọn so sánh được giữ nguyên.</p>
    <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      {([ ["brand", "Thương hiệu"], ["category", "Danh mục"], ["currency", "Tiền tệ"] ] as const).map(([key, label]) =>
        <label key={key}>{label}<select className="mt-1 block w-full rounded-lg border border-slate-300 p-2" value={value[key]} onChange={(event) => update(key, event.target.value)}>
          <option value="">Tất cả</option>{options(key).map((option) => <option key={option} value={option}>{option}</option>)}
        </select></label>)}
      {([ ["minPrice", "Giá tối thiểu"], ["maxPrice", "Giá tối đa"] ] as const).map(([key, label]) =>
        <label key={key}>{label}<input type="number" min="0" step="any" placeholder="Không giới hạn" value={value[key]} onChange={(event) => update(key, event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 p-2" /></label>)}
      <label>Sắp xếp<select value={value.sort} onChange={(event) => onChange({ ...value, sort: event.target.value as ResultSort })} className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
        <option value="ai">AI Match cao → thấp</option><option value="price_asc">Giá thấp → cao</option><option value="price_desc">Giá cao → thấp</option><option value="rating">Rating cao → thấp</option>
      </select></label>
    </div>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error} Tạm hiển thị danh sách gốc.</p>}
    <div className="mt-4 flex items-center justify-between gap-3 text-sm"><span aria-live="polite">Hiển thị {visibleCount}/{products.length} đề xuất</span><button type="button" onClick={() => onChange({ ...EMPTY_FILTERS })} className="font-bold text-blue-700">Đặt lại bộ lọc</button></div>
  </section>;
}
