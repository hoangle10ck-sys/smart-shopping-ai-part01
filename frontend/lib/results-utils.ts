import type { RecommendationItem, ScoreBreakdown } from "../types/shopping";

export const SCORE_COMPONENTS = [
  { key: "budget_score", label: "Ngân sách", weight: 25 },
  { key: "requirement_score", label: "Yêu cầu", weight: 30 },
  { key: "purpose_score", label: "Mục đích", weight: 20 },
  { key: "rating_score", label: "Rating", weight: 10 },
  { key: "review_score", label: "Lượt đánh giá", weight: 5 },
  { key: "source_score", label: "Nguồn", weight: 10 },
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
  return `${number.toLocaleString("vi-VN")} ${currency || "(chưa rõ tiền tệ)"}`;
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

export function dataModeLabel(mode: unknown): string {
  return mode === "demo" ? "Demo Mode — dữ liệu minh họa" : mode === "live" ? "Live Data — dữ liệu đã thu thập" : "Chưa xác định chế độ dữ liệu của phiên";
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
  const currencies = new Set(products.map((item) => item.currency || ""));
  if (priceOperation && !filters.currency && (currencies.size > 1 || currencies.has(""))) return "Chọn một loại tiền tệ để lọc hoặc sắp xếp giá; không tự quy đổi tiền tệ.";
  return null;
}

export function filterAndSort(products: readonly RecommendationItem[], filters: ResultFilters): RecommendationItem[] {
  const min = priceBound(filters.minPrice), max = priceBound(filters.maxPrice);
  if (filterError(filters, products)) return [...products];
  const filtered = products.filter((item) => {
    if (filters.brand && item.brand !== filters.brand) return false;
    if (filters.category && item.category !== filters.category) return false;
    if (filters.currency && item.currency !== filters.currency) return false;
    const price = finiteNumber(item.price);
    if ((min !== null || max !== null) && price === null) return false;
    return (min === null || price! >= min) && (max === null || price! <= max);
  });
  return filtered.sort((a, b) => {
    const field = (item: RecommendationItem) => filters.sort === "ai" ? item.score?.final_score : filters.sort === "rating" ? item.rating : item.price;
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
  return url.username || url.password || url.pathname.toLowerCase().endsWith(".svg") ? null : safe;
}
