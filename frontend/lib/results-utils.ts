import type { RecommendationItem, ScoreBreakdown, ResearchMetadata } from "../types/shopping";

export function historicalPriceLabel(product: ResearchMetadata): string {
  const ref = product.historical_price;
  return ref && ref.currency === "USD" && /^\d+\.\d{2}$/.test(ref.amount)
    ? `Giá tham khảo lịch sử (USD): ${ref.amount} USD`
    : "Chưa có giá trong dữ liệu tham khảo";
}

export const SCORE_COMPONENTS = [
  { key: "budget_score", label: "Ngân sách", weight: 25 },
  { key: "requirement_score", label: "Yêu cầu", weight: 30 },
  { key: "purpose_score", label: "Mục đích", weight: 20 },
  { key: "rating_score", label: "Đánh giá sản phẩm", weight: 10 },
  { key: "review_score", label: "Lượt đánh giá", weight: 5 },
  { key: "source_score", label: "Chất lượng nguồn", weight: 10 },
] as const;

export function scoreRows(score?: Partial<ScoreBreakdown> | null) {
  return SCORE_COMPONENTS.map((component) => ({ ...component, value: finiteNumber(score?.[component.key]) }));
}

export function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function displayScore(value: unknown): string {
  const number = finiteNumber(value);
  return number === null ? "Chưa có dữ liệu" : `${number.toFixed(2)}/100`;
}

export function formatMoney(value: unknown, currency?: string): string {
  const number = finiteNumber(value);
  if (number === null) return "Chưa có dữ liệu";
  // Do not invent VND if currency is missing in an older response.
  return currency === "VND" ? `${number.toLocaleString("vi-VN")}đ` : `${number.toLocaleString("vi-VN")} ${currency || "(chưa rõ tiền tệ)"}`;
}

export function safeHttpUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && !!item.trim()) : [];
}

export function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function dataModeLabel(mode: unknown, recommendations: unknown = []): string {
  if (mode === "research") {
    const products = Array.isArray(recommendations) ? recommendations : [];
    const includesCommunityCatalog = products.some((item) => {
      const provenance = record(record(item).research_provenance);
      return provenance.dataset_id === "OpenFoodFacts" || provenance.dataset_id === "OpenProductsFacts";
    });
    if (includesCommunityCatalog) {
      const includesOtherResearch = products.some((item) => {
        const provenance = record(record(item).research_provenance);
        return provenance.dataset_id !== "OpenFoodFacts" && provenance.dataset_id !== "OpenProductsFacts";
      });
      return includesOtherResearch ? "Dữ liệu tham khảo gồm nguồn cộng đồng" : "Dữ liệu tham khảo từ nguồn cộng đồng";
    }
    return "Dữ liệu tham khảo lịch sử";
  }
  if (mode === "unified") return "Đề xuất theo nhu cầu";
  return mode === "demo" ? "Dữ liệu minh họa" : mode === "live" ? "Tìm từ nguồn trực tuyến" : "Nguồn dữ liệu chưa rõ";
}

export function unifiedSourceName(source: unknown): string {
  if (source === "database_catalog") return "Danh mục sản phẩm";
  if (source === "research_catalog") return "Dữ liệu nghiên cứu";
  if (source === "configured_web_search") return "Tìm kiếm trên web";
  if (source === "demo_mock") return "Dữ liệu minh họa";
  return "Nguồn tìm kiếm khác";
}

export function unifiedSourceStatusLabel(source: {
  available: boolean;
  matched_products?: number;
  error?: string | null;
}): string {
  const error = source.error?.toLowerCase() ?? "";
  if (error.startsWith("chưa cấu hình") || error.startsWith("not configured")) {
    return "Tìm kiếm trên web chưa khả dụng; kết quả có thể chưa đầy đủ.";
  }
  if (error.includes("access_restricted") || error.includes("restricted")) {
    return "Nguồn này giới hạn truy cập; kết quả có thể chưa đầy đủ.";
  }
  if (error.includes("timeout") || error.includes("timed out")) {
    return "Nguồn không phản hồi kịp thời; kết quả có thể chưa đầy đủ.";
  }
  if (source.error && source.available) return "Tìm kiếm một phần; kết quả có thể chưa đầy đủ.";
  if (source.error) return "Nguồn tạm thời không khả dụng.";
  if (!source.available) return "Nguồn chưa khả dụng trong lần tìm kiếm này.";
  if (source.matched_products === 0) return "Đã tìm nhưng chưa có kết quả phù hợp.";
  return "Đã tìm kiếm";
}

export function userFacingWarning(warning: string): string {
  const code = warning.match(/^([A-Z][A-Z0-9_]*):\s*/)?.[1];
  if (code === "BUDGET_NOT_COMPARABLE") {
    return "Ngân sách của bạn là VND, còn giá tham khảo trong dữ liệu là USD. Hệ thống không tự quy đổi nên không dùng mức giá này để lọc hoặc chấm điểm.";
  }
  if (code === "PURPOSE_NOT_SCORED") {
    return "Dữ liệu hiện có chưa đủ để xác minh sản phẩm phù hợp với mục đích này, nên hệ thống chưa cộng điểm cho tiêu chí đó.";
  }
  if (code) return "Có lưu ý về độ đầy đủ của dữ liệu sản phẩm.";
  if (warning === "Online source failed; other available results are retained.") {
    return "Nguồn tìm kiếm trực tuyến gặp sự cố; kết quả từ các nguồn khác vẫn được giữ lại.";
  }
  if (warning === "Research catalog is unavailable for this search.") {
    return "Dữ liệu tham khảo chưa khả dụng trong lần tìm kiếm này.";
  }
  return warning;
}

export type ResultSort = "ai" | "price_asc" | "price_desc" | "rating";
export interface ResultFilters {
  brand: string;
  category: string;
  currency: string;
  minPrice: string;
  maxPrice: string;
  sort: ResultSort;
}
export const EMPTY_FILTERS: ResultFilters = { brand: "", category: "", currency: "", minPrice: "", maxPrice: "", sort: "ai" };

export function priceBound(value: string): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

export function filterError(filters: ResultFilters, products: readonly RecommendationItem[]): string | null {
  const min = priceBound(filters.minPrice), max = priceBound(filters.maxPrice);
  if ((filters.minPrice.trim() && min === null) || (filters.maxPrice.trim() && max === null)) return "Giá lọc phải là số không âm.";
  if (min !== null && max !== null && min > max) return "Giá tối thiểu không được lớn hơn giá tối đa.";
  const priceOperation = min !== null || max !== null || filters.sort.startsWith("price_");
  const researchCount = products.filter(item => item.source_mode === "HISTORICAL_RESEARCH").length;
  if (priceOperation && researchCount > 0 && researchCount !== products.length) return "Không so sánh lẫn giá lịch sử và giá offer.";
  const currencies = new Set(products.map((item) => item.currency || ""));
  if (priceOperation && !filters.currency && (currencies.size > 1 || currencies.has(""))) return "Chọn một loại tiền tệ để lọc hoặc sắp xếp giá; không tự quy đổi tiền tệ.";
  return null;
}

export function resultPrice(item: RecommendationItem): number | null {
  if (item.source_mode !== "HISTORICAL_RESEARCH") return finiteNumber(item.price);
  const ref = item.historical_price;
  return ref?.currency === "USD" && /^\d+\.\d{2}$/.test(ref.amount)
    ? finiteNumber(Number(ref.amount)) : null;
}

export function filterAndSort(products: readonly RecommendationItem[], filters: ResultFilters): RecommendationItem[] {
  const min = priceBound(filters.minPrice), max = priceBound(filters.maxPrice);
  if (filterError(filters, products)) return [...products];
  const filtered = products.filter((item) => {
    if (filters.brand && item.brand !== filters.brand) return false;
    if (filters.category && item.category !== filters.category) return false;
    if (filters.currency && item.currency !== filters.currency) return false;
    const price = resultPrice(item);
    if ((min !== null || max !== null) && price === null) return false;
    return (min === null || price! >= min) && (max === null || price! <= max);
  });
  return filtered.sort((a, b) => {
    const field = (item: RecommendationItem) => filters.sort === "ai" ? item.score?.final_score : filters.sort === "rating" ? item.rating : resultPrice(item);
    const left = finiteNumber(field(a)), right = finiteNumber(field(b));
    // Missing data always sorts last, including descending sorts.
    if (left === null && right !== null) return 1;
    if (right === null && left !== null) return -1;
    const difference = left !== null && right !== null ? left - right : 0;
    return (filters.sort === "price_asc" ? difference : -difference) || a.rank - b.rank || a.product_id - b.product_id;
  });
}
/** A backend page proof is required; URL shape alone never certifies a sale. */
export function safeSalesUrl(value: unknown, verified?: boolean | null): string | null {
  const safe = safeHttpUrl(value);
  if (!safe || verified !== true) return null;
  const url = new URL(safe);
  if (url.username || url.password || (url.port && !["80", "443"].includes(url.port))) return null;
  let path: string;
  try { path = decodeURIComponent(url.pathname).toLowerCase().replace(/^\/+|\/+$/g, ""); }
  catch { return null; }
  if (!path || /^(xe-may|dien-thoai|laptop|tv|tivi|tai-nghe|san-pham|products?|shop)$/.test(path)) return null;
  if (/(^|\/)(category|categories|collections?|search|tim-kiem|blog|news|tin-tuc|reviews?|bai-viet|brands?|thuong-hieu)(\/|$)/.test(path)) return null;
  if (["q", "query", "search", "s"].some((key) => url.searchParams.has(key))) return null;
  return safe;
}

export function safeProductImageUrl(value: unknown): string | null {
  const safe = safeHttpUrl(value);
  if (!safe || /logo|favicon|icon|banner|category|placeholder|sprite|tracking|avatar/i.test(safe)) return null;
  const url = new URL(safe);
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  if (url.username || url.password || url.pathname.toLowerCase().endsWith(".svg") || isInternalImageHost(host)) return null;
  return safe;
}

function isInternalImageHost(host: string): boolean {
  if (
    !host.includes(".")
    || host === "localhost"
    || host.endsWith(".localhost")
    || host.endsWith(".local")
    || host.endsWith(".internal")
    || host.endsWith(".lan")
    || host.endsWith(".home.arpa")
    || (host.startsWith("[") && host.endsWith("]"))
  ) return true;

  const octets = host.split(".");
  if (octets.length !== 4 || octets.some((part) => !/^\d{1,3}$/.test(part))) return false;
  const [first, second, third] = octets.map(Number);
  return first === 0
    || first === 10
    || first === 127
    || (first === 169 && second === 254)
    || (first === 172 && second >= 16 && second <= 31)
    || (first === 192 && (second === 0 || second === 168))
    || (first === 100 && second >= 64 && second <= 127)
    || (first === 198 && (second === 18 || second === 19 || second === 51))
    || (first === 203 && second === 0 && third === 113)
    || first >= 224;
}
