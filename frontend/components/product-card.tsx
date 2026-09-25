"use client";
import Link from "next/link";
import { RecommendationDetails } from "@/components/recommendation-details";
import { FeedbackPanel } from "@/components/feedback-panel";
import { ProductImage } from "@/components/product-image";
import { ScoreBadge } from "@/components/score-badge";
import { AvailabilityBadge } from "@/components/availability-badge";
import { formatMoney, safeHttpUrl, safeSalesUrl, record } from "@/lib/results-utils";
import type { RecommendationItem } from "@/types/shopping";

interface ProductCardProps {
  product: RecommendationItem; sessionId: string; selected?: boolean; compareDisabled?: boolean;
  onToggleCompare?: (productId: number) => void;
}
export function ProductCard({ product, sessionId, selected = false, compareDisabled = false, onToggleCompare }: ProductCardProps) {
  const shopUrl = safeSalesUrl(product.product_url, product.product_page_valid);
  const sourceUrl = safeHttpUrl(product.evidence_url || product.product_url);
  const explanation = record(product.explanation);
  const summary = typeof explanation.summary === 'string' ? explanation.summary : typeof product.explanation === 'string' ? product.explanation : null;
  return <article className={`product-card surface ${selected ? 'is-selected' : ''}`}>
    <div className="relative">
      <ProductImage src={product.image_url} name={product.name} />
      <span className="tag absolute left-3 top-3 !bg-white/95">#{product.rank} Đề xuất</span>
      {selected && <span className="tag tag-green absolute bottom-3 right-3">✓ Đã chọn</span>}
    </div>
    <div className="flex flex-1 flex-col px-2 pb-2 pt-5">
      <div className="flex flex-wrap items-center gap-2"><span className="eyebrow">{product.brand || 'Chưa rõ thương hiệu'}</span>{product.category && <span className="muted text-[11px]">/ {product.category}</span>}</div>
      <h2 className="mt-2 text-lg font-semibold leading-6 tracking-tight">{product.name}</h2>
      {product.model && <p className="muted mt-1 text-xs">Model: {product.model}</p>}
      {product.variant && Object.keys(product.variant).length > 0 && <p className="muted mt-2 text-xs leading-5">{Object.entries(product.variant).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ')}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2"><p className="money">{formatMoney(product.price, product.currency)}</p><AvailabilityBadge value={product.availability} /></div>
      <p className="muted mt-1 text-xs">{product.merchant ? `tại ${product.merchant}` : 'Chưa rõ cửa hàng'}{product.rating != null ? ` · ★ ${product.rating.toFixed(1)}/5` : ''}{product.review_count != null ? ` · ${product.review_count.toLocaleString('vi-VN')} đánh giá` : ''}</p>
      <div className="mt-4"><ScoreBadge value={product.score?.final_score} /></div>
      {product.confidence != null && <p className="muted mt-2 text-[11px]">Độ tin cậy dữ liệu: {product.confidence.toFixed(2)}/100</p>}
      {summary && <p className="muted mt-3 line-clamp-2 text-xs leading-5">{summary}</p>}
      <RecommendationDetails product={product} compact />
      <div className="mt-auto pt-4">
        <div className="grid grid-cols-2 gap-2">
          <Link href={`/products/${product.product_id}?sessionId=${encodeURIComponent(sessionId)}`} className="btn btn-secondary">Xem chi tiết</Link>
          <button type="button" aria-pressed={selected} disabled={compareDisabled && !selected} onClick={() => onToggleCompare?.(product.product_id)} className="btn btn-secondary">{selected ? '✓ Đã chọn' : '+ So sánh'}</button>
        </div>
        {shopUrl && <a href={shopUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary mt-2 w-full">Xem sản phẩm ↗</a>}
        {sourceUrl && sourceUrl !== shopUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-link mt-3 block text-center">Xem nguồn ↗</a>}
      </div>
      <FeedbackPanel sessionId={sessionId} productId={product.product_id} />
    </div>
  </article>;
}
