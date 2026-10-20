"use client";

import Link from "next/link";
import { RecommendationDetails } from "@/components/recommendation-details";
import { FeedbackPanel } from "@/components/feedback-panel";
import { ProductImage } from "@/components/product-image";
import { ScoreBadge } from "@/components/score-badge";
import { AvailabilityBadge } from "@/components/availability-badge";
import { ResearchNotice } from "@/components/research-notice";
import { formatMoney, safeHttpUrl, safeSalesUrl, record } from "@/lib/results-utils";
import type { RecommendationItem } from "@/types/shopping";

interface ProductCardProps {
  product: RecommendationItem;
  sessionId: string;
  selected?: boolean;
  compareDisabled?: boolean;
  onToggleCompare?: (productId: number) => void;
}

export function ProductCard({
  product,
  sessionId,
  selected = false,
  compareDisabled = false,
  onToggleCompare,
}: ProductCardProps) {
  const research = product.source_mode === "HISTORICAL_RESEARCH";
  const sourceVerified =
    product.product_page_valid === true || product.source_observation_valid === true;
  const shopUrl = research ? null : safeSalesUrl(product.product_url, sourceVerified);
  const sourceUrl = safeHttpUrl(product.evidence_url || product.product_url);
  const explanation = record(product.explanation);
  const summary =
    typeof explanation.summary === "string"
      ? explanation.summary
      : typeof product.explanation === "string"
      ? product.explanation
      : null;

  const status =
    product.freshness_status === "STALE"
      ? "Stale"
      : product.source_observation_valid === true
      ? "API verified"
      : product.product_page_valid === true
      ? "Verified"
      : product.evidence?.warnings?.length
      ? "Partial"
      : "Chưa xác minh";

  return (
    <article
      className={`product-card surface group ${
        selected ? "is-selected !border-[var(--brand)] ring-2 ring-[var(--brand-light)]" : ""
      }`}
    >
      <div className="relative overflow-hidden rounded-[14px]">
        <ProductImage src={product.image_url} name={product.name} />
        <span className="tag absolute left-2.5 top-2.5 !bg-white/95 !shadow-xs backdrop-blur-xs font-semibold">
          #{product.rank} Đề xuất
        </span>
        {selected && (
          <span className="tag tag-green absolute bottom-2.5 right-2.5 !shadow-xs font-semibold">
            ✓ Đã chọn
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col px-1.5 pb-2 pt-4">
        {/* Brand, category & status badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="eyebrow !text-[10.5px]">{product.brand || "Chưa rõ thương hiệu"}</span>
          {product.category && (
            <span className="muted text-[11px] font-normal">/ {product.category}</span>
          )}
          <span
            className={`tag !py-0.5 !text-[10px] ${
              status === "Verified" || status === "API verified"
                ? "tag-green"
                : status === "Stale"
                ? "tag-red"
                : ""
            }`}
          >
            {status}
          </span>
          {product.platform && (
            <span className="tag !py-0.5 !text-[10px] uppercase">{product.platform}</span>
          )}
        </div>

        {/* Product Title */}
        <h2 className="mt-2 text-[16px] font-bold leading-snug tracking-tight text-[var(--foreground)] group-hover:text-[var(--brand)] transition-colors">
          {product.name}
        </h2>

        {product.model && (
          <p className="muted mt-1 text-xs">Model: <span className="font-mono">{product.model}</span></p>
        )}

        {product.variant && Object.keys(product.variant).length > 0 && (
          <p className="muted mt-1.5 text-xs leading-relaxed">
            {Object.entries(product.variant)
              .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
              .join(" · ")}
          </p>
        )}

        <ResearchNotice product={product} />

        {/* Price & Availability */}
        {!research && (
          <div className="mt-3.5 flex flex-wrap items-baseline justify-between gap-2 border-t border-[var(--line)] pt-3">
            <p className="money !text-[1.4rem] font-bold text-[var(--foreground)]">
              {formatMoney(product.price, product.currency)}
            </p>
            <AvailabilityBadge value={product.availability} />
          </div>
        )}

        <p className="muted mt-1 text-[11.5px]">
          {research
            ? "Rating lịch sử"
            : product.merchant
            ? `tại ${product.merchant}`
            : "Chưa rõ cửa hàng"}
          {product.rating != null ? ` · ★ ${product.rating.toFixed(1)}/5` : ""}
          {product.review_count != null
            ? ` · ${product.review_count.toLocaleString("vi-VN")} đánh giá`
            : ""}
        </p>

        {/* Score Badge */}
        <div className="mt-3.5">
          <ScoreBadge value={product.score?.final_score} />
        </div>

        {product.product_suitability &&
          typeof product.product_suitability.score === "number" && (
            <p className="muted mt-2 text-[11px]">
              Phù hợp sản phẩm:{" "}
              <strong className="text-[var(--foreground)] font-mono">
                {product.product_suitability.score}/100
              </strong>
            </p>
          )}

        {product.offer_quality && typeof product.offer_quality.score === "number" && (
          <p className="muted mt-0.5 text-[11px]">
            Chất lượng offer:{" "}
            <strong className="text-[var(--foreground)] font-mono">
              {product.offer_quality.score}/100
            </strong>
          </p>
        )}

        {product.last_checked_at && (
          <p className="muted mt-0.5 text-[11px]">
            Quan sát: {new Date(product.last_checked_at).toLocaleString("vi-VN")}
          </p>
        )}

        {product.confidence != null && (
          <p className="muted mt-1.5 text-[11px]">
            {research ? "Độ đầy đủ metadata" : "Độ tin cậy dữ liệu"}:{" "}
            <span className="font-mono font-medium">{product.confidence.toFixed(2)}/100</span>
          </p>
        )}

        {summary && (
          <p className="muted mt-2.5 line-clamp-2 text-xs leading-relaxed">
            {summary}
          </p>
        )}

        {/* Detailed breakdown disclosures */}
        <RecommendationDetails product={product} compact />

        {/* Actions Footer */}
        <div className="mt-auto border-t border-[var(--line)] pt-3.5">
          <div className="grid grid-cols-2 gap-2">
            <Link
              href={`/products/${product.product_id}?sessionId=${encodeURIComponent(sessionId)}`}
              className="btn btn-secondary !min-h-[38px] !py-1.5 !text-xs font-semibold"
            >
              Xem chi tiết
            </Link>
            <button
              type="button"
              aria-pressed={selected}
              disabled={compareDisabled && !selected}
              onClick={() => onToggleCompare?.(product.product_id)}
              className={`btn btn-secondary !min-h-[38px] !py-1.5 !text-xs font-semibold ${
                selected ? "!border-[var(--brand)] !bg-[var(--brand-light)] !text-[var(--brand)]" : ""
              }`}
            >
              {selected ? "✓ Đã chọn" : "+ So sánh"}
            </button>
          </div>

          {shopUrl && (
            <a
              href={shopUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary mt-2 w-full !min-h-[38px] !py-1.5 !text-xs font-semibold shadow-xs"
            >
              Xem sản phẩm ↗
            </a>
          )}

          {sourceUrl && sourceUrl !== shopUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-link mt-2.5 block text-center text-xs"
            >
              Xem nguồn ↗
            </a>
          )}
        </div>

        {/* Feedback component */}
        <FeedbackPanel sessionId={sessionId} productId={product.product_id} />
      </div>
    </article>
  );
}
