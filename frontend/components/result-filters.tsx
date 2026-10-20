import type { RecommendationItem } from "@/types/shopping";
import {
  EMPTY_FILTERS,
  filterError,
  type ResultFilters as Filters,
  type ResultSort,
} from "@/lib/results-utils";

export function ResultFilters({
  products,
  value,
  onChange,
  visibleCount,
  research = false,
}: {
  products: RecommendationItem[];
  value: Filters;
  onChange: (value: Filters) => void;
  visibleCount: number;
  research?: boolean;
}) {
  const options = (field: "brand" | "category" | "currency") =>
    [
      ...new Set(
        products
          .map((item) => item[field])
          .filter((item): item is string => !!item)
      ),
    ].sort();

  const update = (key: keyof Filters, next: string) =>
    onChange({ ...value, [key]: next });

  const error = filterError(value, products);

  return (
    <section
      aria-label="Lọc và sắp xếp kết quả"
      className="surface mb-6 border-[var(--line)] p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-3">
        <h2 className="section-title text-base sm:text-lg">
          Lọc và sắp xếp trong phiên này
        </h2>
        <span aria-live="polite" className="font-mono text-xs font-semibold text-[var(--muted)]">
          Hiển thị {visibleCount}/{products.length} đề xuất
        </span>
      </div>

      {research && (
        <p className="notice mt-3 text-xs leading-relaxed">
          Chỉ lọc các đề xuất đang hiển thị theo giá tham khảo lịch sử USD, không phải giá bán hiện tại. Sản phẩm thiếu giá không đáp ứng khoảng giá; muốn tìm toàn catalog hãy tạo truy vấn mới.
        </p>
      )}

      <div className="mt-4 grid gap-3.5 text-xs font-semibold text-[#3b4e45] sm:grid-cols-2 lg:grid-cols-6">
        {(
          [
            ["brand", "Thương hiệu"],
            ["category", "Danh mục"],
            ["currency", "Tiền tệ"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex flex-col gap-1.5">
            <span>{label}</span>
            <select
              className="field !h-10 !py-1.5 !text-xs font-normal"
              value={value[key]}
              onChange={(event) => update(key, event.target.value)}
            >
              <option value="">Tất cả</option>
              {options(key).map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ))}

        {(
          [
            ["minPrice", "Giá tối thiểu"],
            ["maxPrice", "Giá tối đa"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex flex-col gap-1.5">
            <span>{research ? `${label} lịch sử (USD)` : label}</span>
            <input
              type="number"
              min="0"
              step="any"
              placeholder="Không giới hạn"
              value={value[key]}
              onChange={(event) => update(key, event.target.value)}
              className="field !h-10 !py-1.5 !text-xs font-normal"
            />
          </label>
        ))}

        <label className="flex flex-col gap-1.5">
          <span>Sắp xếp</span>
          <select
            value={value.sort}
            onChange={(event) =>
              onChange({ ...value, sort: event.target.value as ResultSort })
            }
            className="field !h-10 !py-1.5 !text-xs font-normal"
          >
            <option value="ai">AI Match cao → thấp</option>
            <option value="price_asc">
              {research ? "Giá lịch sử thấp → cao" : "Giá thấp → cao"}
            </option>
            <option value="price_desc">
              {research ? "Giá lịch sử cao → thấp" : "Giá cao → thấp"}
            </option>
            <option value="rating">Rating cao → thấp</option>
          </select>
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-xs font-medium text-red-700">
          {error} Tạm hiển thị danh sách gốc.
        </p>
      )}

      <div className="mt-4 flex items-center justify-end gap-3 border-t border-[var(--line)] pt-3 text-xs">
        <button
          type="button"
          onClick={() => onChange({ ...EMPTY_FILTERS })}
          className="btn btn-secondary !min-h-[36px] !px-3.5 !py-1.5 !text-xs font-medium"
        >
          Đặt lại bộ lọc
        </button>
      </div>
    </section>
  );
}
