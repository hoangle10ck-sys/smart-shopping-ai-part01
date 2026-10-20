"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getComparison } from "@/lib/api";
import {
  displayScore,
  formatMoney,
  safeHttpUrl,
  historicalPriceLabel,
} from "@/lib/results-utils";
import { ResearchNotice } from "@/components/research-notice";
import { RequirementMatches } from "@/components/requirement-matches";
import { ProductImage } from "@/components/product-image";
import { ScoreBadge } from "@/components/score-badge";
import { AvailabilityBadge } from "@/components/availability-badge";
import { PipelineProgress } from "@/components/pipeline-progress";
import { ErrorState, EmptyState } from "@/components/ui-state";
import type { ComparisonProduct, ComparisonResponse } from "@/types/shopping";

export default function ComparePage() {
  const params = useParams<{ comparisonId: string }>();
  const comparisonId = Number(params.comparisonId);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(false);
      try {
        if (!Number.isInteger(comparisonId) || comparisonId <= 0) {
          throw new Error("Invalid comparison");
        }
        const result = await getComparison(comparisonId);
        if (active) setData(result);
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
  }, [comparisonId, attempt]);

  const products = data?.result?.products ?? [];
  const research = products.some((p) => p.source_mode === "HISTORICAL_RESEARCH");
  const specificationKeys = Array.from(
    new Set(products.flatMap((product) => Object.keys(product.specifications ?? {})))
  );

  const rows: { label: string; render: (product: ComparisonProduct) => string }[] = [
    { label: "AI Match", render: (p) => displayScore(p.ai_score) },
    { label: "Độ tin cậy dữ liệu", render: (p) => displayScore(p.confidence) },
    {
      label: research ? "Giá tham khảo lịch sử (USD)" : "Giá đã lưu",
      render: (p) =>
        research
          ? historicalPriceLabel(p)
          : formatMoney(p.best_offer?.price, p.best_offer?.currency ?? undefined),
    },
    ...(research
      ? []
      : [
          {
            label: "Nhà bán",
            render: (p: ComparisonProduct) => p.best_offer?.merchant || "Chưa rõ",
          },
        ]),
    {
      label: "Rating",
      render: (p) => (p.rating == null ? "Chưa có dữ liệu" : `${p.rating.toFixed(1)}/5`),
    },
    {
      label: "Lượt đánh giá",
      render: (p) =>
        p.review_count == null ? "Chưa có dữ liệu" : p.review_count.toLocaleString("vi-VN"),
    },
    {
      label: "Thứ hạng AI",
      render: (p) => (p.recommendation_rank == null ? "Chưa có dữ liệu" : `#${p.recommendation_rank}`),
    },
    ...specificationKeys.map((key) => ({
      label: key.replaceAll("_", " "),
      render: (p: ComparisonProduct) =>
        p.specifications?.[key] == null ? "Chưa có dữ liệu" : String(p.specifications[key]),
    })),
  ];

  return (
    <main id="main-content" tabIndex={-1}>
      {/* Heading */}
      <section className="page-heading">
        <div className="page-container">
          <p className="eyebrow">Đặt các lựa chọn cạnh nhau</p>
          <h1 className="page-title mt-2.5">So sánh sản phẩm</h1>
          <p className="muted mt-2 text-xs sm:text-sm leading-relaxed">
            Cùng một góc nhìn. Rõ hơn những điều khác biệt để ra quyết định phù hợp.
          </p>
          {data?.session_id && (
            <Link
              href={`/results/${data.session_id}`}
              className="text-link mt-3.5 inline-flex items-center gap-1 text-xs font-semibold"
            >
              ← Về kết quả tìm kiếm
            </Link>
          )}
        </div>
      </section>

      <div className="page-container page-content">
        {loading && <PipelineProgress phase="read" />}

        {error && (
          <ErrorState
            title="Không thể tải so sánh"
            retry={() => setAttempt((value) => value + 1)}
          />
        )}

        {!loading && !error && !data?.result && (
          <EmptyState
            title="Chưa có dữ liệu so sánh"
            description="Chọn từ 2 đến 3 sản phẩm trên trang kết quả để bắt đầu."
          />
        )}

        {!loading && !error && data?.result && (
          <>
            {/* Summary Conclusion Box */}
            <section className="mb-6 rounded-2xl border border-[#c4ded0] bg-[#f0f8f4] p-5 sm:p-6 shadow-xs">
              <span className="eyebrow !text-xs text-[#0f5b44]">
                Kết luận trong bản so sánh đã lưu
              </span>
              <p className="mt-2.5 text-xs sm:text-sm leading-relaxed text-[var(--foreground)]">
                {data.result.summary}
              </p>
            </section>

            {/* Incomparability Alert */}
            {data.result.price_comparability === "NOT_COMPARABLE" && (
              <div role="alert" className="notice mb-6 !border-amber-300 !bg-amber-50">
                <span className="font-bold text-[#7d5214]">NOT_COMPARABLE</span> — Các mức giá không cùng model/SKU/điều kiện nên không được dùng để kết luận offer nào rẻ hơn.
              </div>
            )}

            {/* Side-by-side product cards */}
            <h2 className="section-title mb-4 text-base sm:text-lg">
              Sản phẩm và mức phù hợp
            </h2>
            <div
              className={`grid gap-5 ${
                products.length === 2 ? "md:grid-cols-2" : "md:grid-cols-3"
              }`}
            >
              {products.map((product) => {
                const source = safeHttpUrl(product.best_offer?.product_url);
                const isWinner = product.product_id === data.result?.winner_product_id;

                return (
                  <article
                    key={product.product_id}
                    className={`surface min-w-0 p-4 transition-all ${
                      isWinner ? "border-[var(--brand)] ring-2 ring-[var(--brand-light)]" : ""
                    }`}
                  >
                    <div className="overflow-hidden rounded-xl">
                      <ProductImage
                        src={product.image_url}
                        name={product.name || "Sản phẩm"}
                        className="!aspect-[4/3]"
                      />
                    </div>

                    <div className="p-1 pt-4">
                      {isWinner && (
                        <span className="tag tag-green mb-2.5 !py-1 font-semibold">
                          ★ Được đề xuất trong bản so sánh
                        </span>
                      )}
                      <p className="eyebrow !text-[10.5px]">
                        {product.brand || product.category || "Sản phẩm"}
                      </p>
                      <h2 className="mt-1.5 text-base sm:text-lg font-bold leading-snug text-[var(--foreground)]">
                        {product.name}
                      </h2>
                      {product.model && (
                        <p className="muted mt-1 text-xs">
                          Model: <span className="font-mono">{product.model}</span>
                        </p>
                      )}

                      <ResearchNotice product={product} />

                      {!research && (
                        <div className="mt-3.5 border-t border-[var(--line)] pt-3">
                          <p className="money !text-2xl font-bold text-[var(--foreground)]">
                            {formatMoney(
                              product.best_offer?.price,
                              product.best_offer?.currency ?? undefined
                            )}
                          </p>
                          <p className="muted mt-1 text-xs">
                            {product.best_offer?.merchant || "Chưa rõ cửa hàng"}
                          </p>
                          <div className="mt-2.5">
                            <AvailabilityBadge value={product.best_offer?.availability} />
                          </div>
                        </div>
                      )}

                      <div className="mt-3.5">
                        <ScoreBadge value={product.ai_score} />
                      </div>

                      <div className="mt-5 border-t border-[var(--line)] pt-3">
                        <Link
                          href={`/products/${product.product_id}?sessionId=${encodeURIComponent(
                            data.session_id
                          )}`}
                          className="btn btn-secondary w-full !min-h-[38px] !text-xs font-semibold"
                        >
                          Xem chi tiết
                        </Link>
                        {source && (
                          <a
                            href={source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-link mt-2.5 block text-center text-xs"
                          >
                            Xem nguồn ↗
                          </a>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>

            {/* Comparison Matrix Table */}
            <section className="surface mt-8 overflow-hidden">
              <div className="p-5 sm:p-6 border-b border-[var(--line)]">
                <h2 className="section-title text-base sm:text-lg">
                  So sánh cấu hình sản phẩm
                </h2>
                <p className="muted mt-1 text-xs">
                  Dữ liệu trong bản so sánh đã lưu. Trên điện thoại, cuộn ngang trong bảng để xem các sản phẩm.
                </p>
              </div>

              <div
                className="compare-scroll"
                role="region"
                aria-label="Bảng đối chiếu sản phẩm"
                tabIndex={0}
              >
                <table className="compare-table">
                  <caption className="sr-only">
                    So sánh thông tin các sản phẩm đã chọn
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className="w-[170px] font-semibold text-[var(--foreground)]">
                        Tiêu chí
                      </th>
                      {products.map((p) => (
                        <th
                          scope="col"
                          key={p.product_id}
                          className="font-bold text-xs sm:text-sm text-[var(--foreground)]"
                        >
                          {p.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--line)]">
                    {rows.map((row) => (
                      <tr key={row.label} className="hover:bg-white/60">
                        <th
                          scope="row"
                          className="font-medium text-xs text-[var(--muted)]"
                        >
                          {row.label}
                        </th>
                        {products.map((p) => (
                          <td
                            key={p.product_id}
                            className="text-xs sm:text-sm font-normal text-[var(--foreground)]"
                          >
                            {row.render(p)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Offer, shop và độ mới */}
            {!research && (
              <section className="surface mt-8 p-5 sm:p-6">
                <h2 className="section-title text-base sm:text-lg">
                  Offer, shop và độ mới
                </h2>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {products.map((product) => (
                    <div
                      key={product.product_id}
                      className="rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-4 text-xs"
                    >
                      <h3 className="font-bold text-sm text-[var(--foreground)]">
                        {product.name}
                      </h3>
                      <p className="muted mt-2 text-xs">
                        SKU: <span className="font-mono">{product.variant_id ?? "Chưa xác định"}</span> · Nền tảng:{" "}
                        <span className="font-semibold">{product.platform ?? "Chưa rõ"}</span> ·{" "}
                        <span className="font-mono">{product.freshness_status ?? "UNKNOWN"}</span>
                      </p>
                      <p className="muted mt-1.5 text-xs">
                        Có {product.alternate_offers?.length ?? 0} lựa chọn shop đã lưu.
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Pros & Cons matrices */}
            <div className="mt-6 grid gap-5 md:grid-cols-2">
              {(["pros", "cons"] as const).map((kind) => (
                <section key={kind} className="surface p-5 sm:p-6">
                  <h2 className="section-title text-base sm:text-lg">
                    {kind === "pros" ? "Ưu điểm" : "Hạn chế / đánh đổi"}
                  </h2>
                  {products.map((p) => (
                    <div
                      key={p.product_id}
                      className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--surface-subtle)] p-4"
                    >
                      <h3 className="text-xs sm:text-sm font-bold text-[var(--foreground)]">
                        {p.name}
                      </h3>
                      {p[kind]?.length ? (
                        <ul className="muted mt-2 list-disc space-y-1.5 pl-4 text-xs leading-relaxed">
                          {p[kind].map((item, index) => (
                            <li key={index}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted mt-2 text-xs">Chưa có dữ liệu.</p>
                      )}
                    </div>
                  ))}
                </section>
              ))}
            </div>

            {/* Requirement matching & evidence */}
            <section className="surface mt-6 p-5 sm:p-6">
              <h2 className="section-title text-base sm:text-lg">
                Đối chiếu yêu cầu và bằng chứng
              </h2>
              {research ? (
                products.map((p) => (
                  <div key={p.product_id} className="mt-4">
                    <h3 className="text-sm font-semibold">{p.name}</h3>
                    <RequirementMatches items={p.requirement_matches} />
                  </div>
                ))
              ) : (
                <p className="muted mt-3 text-xs sm:text-sm leading-relaxed">
                  Bản so sánh này chưa lưu đối chiếu matched / unmet / unknown hoặc evidence theo trường. Mở kết quả tìm kiếm để xem dữ liệu của phiên; thông tin đó không được ghép vào bản so sánh này.
                </p>
              )}
              <Link
                href={`/results/${data.session_id}`}
                className="text-link mt-4 inline-flex items-center gap-1 text-xs font-semibold"
              >
                Xem kết quả của phiên →
              </Link>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
