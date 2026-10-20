"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getProduct } from "@/lib/api";
import { formatMoney, safeSalesUrl, safeHttpUrl } from "@/lib/results-utils";
import { RecommendationDetails } from "@/components/recommendation-details";
import { ResearchNotice } from "@/components/research-notice";
import { ProductImage } from "@/components/product-image";
import { ScoreBadge } from "@/components/score-badge";
import { AvailabilityBadge } from "@/components/availability-badge";
import { PipelineProgress } from "@/components/pipeline-progress";
import { ErrorState } from "@/components/ui-state";
import type { ProductDetail } from "@/types/shopping";

export default function ProductPage() {
  const router = useRouter();
  const params = useParams<{ productId: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setLoading(true);
        setError(false);
        const productId = Number(params.productId);
        if (!Number.isFinite(productId)) throw new Error("Invalid product");
        const result = await getProduct(
          productId,
          new URLSearchParams(window.location.search).get("sessionId")
        );
        if (active) setProduct(result);
      } catch {
        if (active) setError(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [params.productId, attempt]);

  const sortedOffers = useMemo(
    () =>
      [...(product?.offers ?? [])].sort((a, b) =>
        a.price == null ? 1 : b.price == null ? -1 : a.price - b.price
      ),
    [product]
  );

  if (loading) {
    return (
      <main id="main-content" tabIndex={-1} className="page-container page-content">
        <PipelineProgress phase="read" />
      </main>
    );
  }

  if (error || !product) {
    return (
      <main id="main-content" tabIndex={-1} className="page-container page-content">
        <ErrorState
          title="Không thể tải sản phẩm"
          retry={() => setAttempt((value) => value + 1)}
        />
      </main>
    );
  }

  // Every hero field comes from the same saved recommendation when available.
  // Catalog offers remain a separate section, never combined with the saved score.
  const snapshot = product.recommendation;
  const identity = snapshot ?? product;
  const research = identity.source_mode === "HISTORICAL_RESEARCH";
  const offer = snapshot ?? sortedOffers[0];
  const name = identity.name || "Sản phẩm";
  const offerVerified =
    offer?.product_page_valid === true || offer?.source_observation_valid === true;
  const shopUrl = research ? null : safeSalesUrl(offer?.product_url, offerVerified);
  const sourceUrl = safeHttpUrl(offer?.evidence_url || offer?.product_url);
  const image = snapshot
    ? snapshot.image_url
    : sortedOffers[0]?.product_page_valid || sortedOffers[0]?.source_observation_valid
    ? sortedOffers[0].image_url
    : product.image_url;
  const specs = Object.entries(identity.specifications || {}).filter(
    ([, value]) => value != null && String(value).trim()
  );
  const pros = identity.pros ?? [];
  const cons = identity.cons ?? [];

  return (
    <main id="main-content" tabIndex={-1}>
      {/* Back button header */}
      <div className="page-container pt-6">
        <button
          type="button"
          className="text-link inline-flex items-center gap-1.5 text-xs font-semibold"
          onClick={() => router.back()}
        >
          ← Quay lại kết quả tìm kiếm
        </button>
      </div>

      {/* Hero Section */}
      <section className="page-container grid gap-8 py-8 lg:grid-cols-2 lg:gap-14">
        {/* Product Media Display */}
        <div className="surface self-start overflow-hidden !rounded-2xl p-4 shadow-sm">
          <ProductImage src={image} name={name} className="!aspect-square" />
        </div>

        {/* Product Identity & Hero Pricing */}
        <div className="flex flex-col justify-between py-1">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {identity.brand && (
                <span className="eyebrow !text-xs">{identity.brand}</span>
              )}
              {identity.category && (
                <span className="tag !text-[11px] font-medium">
                  {identity.category}
                </span>
              )}
              {!research && <AvailabilityBadge value={offer?.availability} />}
            </div>

            <ResearchNotice product={identity} />

            <h1 className="page-title mt-4 text-2xl sm:text-3xl font-bold text-[var(--foreground)]">
              {name}
            </h1>

            {identity.model && (
              <p className="muted mt-2 text-xs sm:text-sm font-medium">
                Model: <span className="font-mono text-[var(--foreground)]">{identity.model}</span>
              </p>
            )}

            {snapshot?.variant && (
              <p className="muted mt-2 text-xs leading-relaxed">
                {Object.entries(snapshot.variant)
                  .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
                  .join(" · ")}
              </p>
            )}

            <p className="muted mt-3 text-xs sm:text-sm">
              {identity.rating != null
                ? `★ ${identity.rating.toFixed(1)}/5`
                : "Chưa có rating"}
              {identity.review_count != null
                ? ` · ${identity.review_count.toLocaleString("vi-VN")} lượt đánh giá`
                : ""}
            </p>

            {/* Price Box */}
            {!research && (
              <div className="mt-5 rounded-2xl border border-[var(--line)] bg-[var(--surface-subtle)] p-5">
                <p className="muted text-xs font-medium">
                  {snapshot ? "Giá tại thời điểm đề xuất" : "Giá offer đã thu thập"}
                </p>
                <p className="money mt-1.5 !text-3xl sm:!text-4xl font-extrabold text-[var(--foreground)]">
                  {formatMoney(offer?.price, offer?.currency)}
                </p>
                <p className="muted mt-2 text-xs sm:text-sm">
                  tại <strong className="text-[var(--foreground)] font-semibold">{offer?.merchant || "Chưa rõ cửa hàng"}</strong>
                </p>
              </div>
            )}

            {snapshot && (
              <div className="mt-4">
                <ScoreBadge value={snapshot.score?.final_score} />
              </div>
            )}
          </div>

          {/* Outbound Actions */}
          <div className="mt-6 border-t border-[var(--line)] pt-5">
            <div className="flex flex-col gap-2.5">
              {shopUrl && (
                <a
                  href={shopUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary w-full !py-3 font-semibold shadow-xs"
                >
                  Xem sản phẩm tại {offer?.merchant || "cửa hàng"} ↗
                </a>
              )}
              {sourceUrl && sourceUrl !== shopUrl && (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary w-full !py-2.5 text-xs font-semibold"
                >
                  Xem nguồn ↗
                </a>
              )}
            </div>
            {!research && (
              <p className="muted mt-3 text-[11px] leading-relaxed">
                Giá và tồn kho thuộc dữ liệu đã lưu. Kiểm tra thông tin mới nhất tại cửa hàng trước khi mua.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Lower Details Sections */}
      <div className="page-container space-y-6 pb-20">
        {/* Recommendation snapshot details */}
        {snapshot && (
          <section
            aria-label="Đề xuất của phiên tìm kiếm"
            className="surface p-6 sm:p-8"
          >
            <p className="eyebrow">Theo nhu cầu của bạn</p>
            <h2 className="section-title mt-2 text-lg sm:text-xl">
              Đề xuất của phiên tìm kiếm
            </h2>
            <p className="muted mt-2 text-xs sm:text-sm">
              AI Match, giá và bằng chứng dưới đây thuộc cùng kết quả đã lưu.
            </p>
            <RecommendationDetails product={snapshot} />
          </section>
        )}

        {/* Specifications */}
        <section className="surface p-6 sm:p-8">
          <h2 className="section-title text-lg sm:text-xl">
            Thông số kỹ thuật{snapshot ? " khi đề xuất" : ""}
          </h2>
          {specs.length ? (
            <dl className="mt-5 grid gap-x-10 sm:grid-cols-2">
              {specs.map(([key, value]) => (
                <div
                  key={key}
                  className="flex min-w-0 justify-between gap-4 border-b border-[var(--line)] py-3 text-xs sm:text-sm"
                >
                  <dt className="muted font-medium">{key.replaceAll("_", " ")}</dt>
                  <dd className="max-w-[65%] text-right font-semibold text-[var(--foreground)] font-mono">
                    {String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="muted mt-4 text-xs sm:text-sm">
              Chưa có thông số chi tiết từ nguồn cho sản phẩm này.
            </p>
          )}
        </section>

        {/* Pros & Cons */}
        <div className="grid gap-6 md:grid-cols-2">
          {[
            ["Ưu điểm", pros],
            ["Hạn chế / đánh đổi", cons],
          ].map(([title, items]) => (
            <section key={String(title)} className="surface p-6">
              <h2 className="section-title text-base sm:text-lg">{String(title)}</h2>
              {(items as string[]).length ? (
                <ul className="muted mt-4 list-disc space-y-2 pl-4 text-xs sm:text-sm leading-relaxed">
                  {(items as string[]).map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted mt-4 text-xs sm:text-sm">Chưa có dữ liệu được cung cấp.</p>
              )}
            </section>
          ))}
        </div>

        {/* Catalog Offers */}
        {!research && (
          <section className="surface p-6 sm:p-8">
            <h2 className="section-title text-lg sm:text-xl">Nơi bán trong catalog</h2>
            <p className="muted mt-1.5 text-xs sm:text-sm leading-relaxed">
              Các offer catalog đã thu thập, sắp xếp theo giá. Dữ liệu này được trình bày riêng với kết quả đề xuất lịch sử phía trên.
            </p>
            {sortedOffers.length ? (
              <ul className="mt-5 divide-y divide-[var(--line)]">
                {sortedOffers.map((item) => {
                  const sales = safeSalesUrl(
                    item.product_url,
                    item.product_page_valid || item.source_observation_valid
                  );
                  const evidence = safeHttpUrl(item.evidence_url || item.product_url);
                  return (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-4 py-4 sm:py-5"
                    >
                      <div className="min-w-0">
                        <p className="font-bold text-sm sm:text-base text-[var(--foreground)]">
                          {item.merchant || item.source_domain || "Chưa rõ cửa hàng"}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <AvailabilityBadge value={item.availability} />
                          {item.source_domain && (
                            <span className="tag text-[10px]">{item.source_domain}</span>
                          )}
                        </div>
                        {item.source_title && (
                          <p className="muted mt-2 text-xs truncate max-w-md">{item.source_title}</p>
                        )}
                        <p className="muted mt-1.5 text-[11px]">
                          Kiểm tra: {item.last_checked_at || "Chưa rõ"}
                          {item.source_reliability_score != null
                            ? ` · Tin cậy nguồn: ${item.source_reliability_score}/100`
                            : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                        <span className="money !text-xl font-bold text-[var(--foreground)]">
                          {formatMoney(item.price, item.currency)}
                        </span>
                        {sales && (
                          <a
                            href={sales}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-secondary !min-h-[38px] !px-3.5 !py-1.5 !text-xs font-semibold"
                          >
                            Xem sản phẩm ↗
                          </a>
                        )}
                        {evidence && evidence !== sales && (
                          <a
                            href={evidence}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-link text-xs font-semibold"
                          >
                            Xem nguồn ↗
                          </a>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted mt-5 text-sm">Chưa tìm thấy nơi bán.</p>
            )}
          </section>
        )}

        {/* Footer meta */}
        <div className="flex flex-wrap items-center justify-between gap-4 text-xs muted border-t border-[var(--line)] pt-4">
          <span>
            Mã sản phẩm #{product.id} · Catalog cập nhật: {product.updated_at || "Chưa rõ"}
          </span>
          <Link href="/" className="text-link font-semibold">
            Tìm kiếm mới →
          </Link>
        </div>
      </div>
    </main>
  );
}
