"use client";

import Link from "next/link";
import { RecommendationDetails } from "@/components/recommendation-details";
import { displayScore, safeHttpUrl, safeSalesUrl, safeProductImageUrl } from "@/lib/results-utils";
import {
  useState,
} from "react";

import {
  FeedbackPanel,
} from "@/components/feedback-panel";

import type {
  RecommendationItem,
} from "@/types/shopping";


interface ProductCardProps {
  product: RecommendationItem;
  sessionId: string;
  selected?: boolean;
  compareDisabled?: boolean;

  onToggleCompare?: (
    productId: number,
  ) => void;
}


function formatPrice(
  price?: number | null,
  currency = "VND",
) {
  if (price == null) {
    return "Liên hệ";
  }

  if (currency === "VND") {
    return new Intl.NumberFormat(
      "vi-VN",
      {
        style: "currency",
        currency: "VND",
        maximumFractionDigits: 0,
      },
    ).format(price);
  }

  return (
    `${price.toLocaleString("vi-VN")} ${currency}`
  );
}


function percent(
  value?: number | null,
) {
  if (value == null) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(value),
    ),
  );
}


export function ProductCard({
  product,
  sessionId,
  selected = false,
  compareDisabled = false,
  onToggleCompare,
}: ProductCardProps) {
  const [
    imageFailed,
    setImageFailed,
  ] = useState(false);

  const [imageUrl, setImageUrl] = useState(product.image_url);

  // Reset only image state when the source changes, preserving feedback drafts.
  if (imageUrl !== product.image_url) {
    setImageUrl(product.image_url);
    setImageFailed(false);
  }


  const aiMatch = percent(
    product.score.final_score,
  );

  const confidence = percent(
    product.confidence,
  );

  const shopUrl = safeSalesUrl(product.product_url, product.product_page_valid);
  const sourceUrl = safeHttpUrl(product.evidence_url || product.product_url);
  const safeImage = safeProductImageUrl(product.image_url);

  const hasImage = Boolean(
    safeImage
    && !imageFailed
  );


  return (
    <article
      className={[
        "group overflow-hidden",
        "rounded-[26px] border",
        "bg-white shadow-sm",
        "transition-all duration-300",
        "hover:-translate-y-1",
        "hover:shadow-xl",

        selected
          ? "border-blue-500 ring-2 ring-blue-100"
          : "border-slate-200 hover:border-blue-200",
      ].join(" ")}
    >
      {/* IMAGE */}
      <div className="relative h-56 overflow-hidden bg-gradient-to-br from-slate-50 via-white to-blue-50">
        {hasImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={
              safeImage!
            }
            alt={
              product.name
            }
            loading="lazy"
            onError={() =>
              setImageFailed(true)
            }
            className="h-full w-full object-contain p-5 transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-white text-4xl shadow-sm">
                🛍️
              </div>

              <p className="mt-3 text-xs font-semibold text-slate-400">
                Chưa có ảnh sản phẩm
              </p>
            </div>
          </div>
        )}


        <div className="absolute left-4 top-4 rounded-full bg-slate-950 px-3 py-1.5 text-xs font-bold text-white shadow-lg">
          #{product.rank} AI đề xuất
        </div>


        {product.rank === 1 && (
          <div className="absolute right-4 top-4 rounded-full bg-amber-400 px-3 py-1.5 text-xs font-extrabold text-amber-950 shadow">
            🏆 Tốt nhất
          </div>
        )}


        {selected && (
          <div className="absolute bottom-4 right-4 flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-lg font-black text-white shadow-lg">
            ✓
          </div>
        )}
      </div>


      <div className="p-5">
        {/* META */}
        <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wide text-blue-600">
          <span>
            {product.brand
              || "Chưa rõ thương hiệu"}
          </span>

          {product.category && (
            <>
              <span className="text-slate-300">
                •
              </span>

              <span className="text-slate-400">
                {product.category}
              </span>
            </>
          )}
        </div>


        {/* NAME */}
        <h2 className="mt-2 min-h-14 line-clamp-2 text-lg font-black leading-7 text-slate-950">
          {product.name}
        </h2>


        {/* PRICE */}
        <div className="mt-4 flex items-end justify-between gap-4">
          <div>
            <p className="text-xl font-black text-blue-600">
              {formatPrice(
                product.price,
                product.currency,
              )}
            </p>

            {product.merchant && (
              <p className="mt-1 truncate text-xs font-medium text-slate-400">
                tại {product.merchant}
              </p>
            )}
          </div>


          <div className="text-right">
            {product.rating != null ? (
              <>
                <p className="font-extrabold text-amber-600">
                  ⭐ {product.rating.toFixed(1)}
                </p>

                {product.review_count != null && (
                  <p className="text-xs text-slate-400">
                    {product.review_count.toLocaleString(
                      "vi-VN",
                    )} đánh giá
                  </p>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-400">
                Chưa có rating
              </p>
            )}
          </div>
        </div>


        {/* SCORE */}
        <div className="mt-5 grid grid-cols-2 gap-3">
          <div className="rounded-2xl bg-blue-50 p-3">
            <p className="text-xs font-bold text-slate-500">
              AI Match
            </p>

            <p className="mt-1 text-xl font-black text-blue-600">
              {displayScore(product.score?.final_score)}
            </p>

            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-blue-100">
              <div
                className="h-full rounded-full bg-blue-600"
                style={{
                  width:
                    `${aiMatch}%`,
                }}
              />
            </div>
          </div>


          <div className="rounded-2xl bg-emerald-50 p-3">
            <p className="text-xs font-bold text-slate-500">
              Độ tin cậy dữ liệu
            </p>

            <p className="mt-1 text-xl font-black text-emerald-600">
              {displayScore(product.confidence)}
            </p>

            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-emerald-100">
              <div
                className="h-full rounded-full bg-emerald-500"
                style={{
                  width:
                    `${confidence}%`,
                }}
              />
            </div>
          </div>
        </div>


        <RecommendationDetails product={product} />

        {/* ACTION */}
        <div className="mt-5 grid grid-cols-2 gap-3">
          <Link
            href={
              `/products/${product.product_id}?sessionId=${encodeURIComponent(sessionId)}`
            }
            className="flex items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-bold text-white transition hover:bg-blue-600"
          >
            Xem chi tiết
          </Link>


          <button
            type="button"
            disabled={
              compareDisabled
              && !selected
            }
            onClick={() =>
              onToggleCompare?.(
                product.product_id,
              )
            }
            className={[
              "rounded-2xl border px-4 py-3",
              "text-sm font-bold transition",

              selected
                ? "border-blue-600 bg-blue-50 text-blue-700"
                : "border-slate-200 text-slate-700 hover:border-blue-300 hover:bg-blue-50",

              compareDisabled
              && !selected
                ? "cursor-not-allowed opacity-40"
                : "",
            ].join(" ")}
          >
            {selected
              ? "✓ Đã chọn"
              : "+ So sánh"}
          </button>
        </div>


        {/* DIRECT SHOP LINK */}
        {shopUrl && (
          <a
            href={
              shopUrl
            }
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 flex w-full items-center justify-center rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-bold text-blue-700 transition hover:bg-blue-100"
          >
            Xem sản phẩm ↗
          </a>
        )}


        {!shopUrl && sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="mt-3 block text-sm text-blue-700">Xem nguồn ↗</a>}
        <FeedbackPanel
          sessionId={sessionId}
          productId={
            product.product_id
          }
        />
      </div>
    </article>
  );
}
