"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import Link from "next/link";

import {
  useParams,
} from "next/navigation";

import {
  SiteHeader,
} from "@/components/site-header";

import {
  getComparison,
} from "@/lib/api";

import type {
  ComparisonProduct,
  ComparisonResponse,
} from "@/types/shopping";


function formatPrice(
  price?: number | null,
  currency = "VND",
) {
  if (price == null) {
    return "Chưa có giá";
  }

  if (currency === "VND") {
    return new Intl.NumberFormat(
      "vi-VN",
      {
        style: "currency",
        currency: "VND",
      },
    ).format(price);
  }

  return `${price.toLocaleString()} ${currency}`;
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


export default function ComparePage() {
  const params = useParams<{
    comparisonId: string;
  }>();

  const comparisonId = Number(
    params.comparisonId,
  );


  const [data, setData] =
    useState<ComparisonResponse | null>(
      null,
    );


  const [loading, setLoading] =
    useState(true);


  const [error, setError] =
    useState<string | null>(null);


  useEffect(() => {
    let active = true;


    async function load() {
      if (
        !Number.isInteger(
          comparisonId,
        ) ||
        comparisonId <= 0
      ) {
        if (active) {
          setError(
            "ID so sánh không hợp lệ.",
          );

          setLoading(false);
        }

        return;
      }


      try {
        const result =
          await getComparison(
            comparisonId,
          );

        if (active) {
          setData(result);
        }
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Không thể tải bảng so sánh.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }


    load();


    return () => {
      active = false;
    };
  }, [comparisonId]);


  const products =
    data?.result?.products ?? [];


  const winnerId =
    data?.result
      ?.winner_product_id;


  const specificationKeys =
    useMemo(() => {
      const keys =
        new Set<string>();

      for (
        const product
        of products
      ) {
        Object.keys(
          product.specifications ??
            {},
        ).forEach(
          (key) =>
            keys.add(key),
        );
      }

      return Array.from(keys);
    }, [products]);


  return (
    <main className="min-h-screen">
      <SiteHeader />

      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-12 lg:px-8">
          <Link
            href="/"
            className="text-sm font-bold text-blue-600 transition hover:text-blue-800"
          >
            ← Trang chủ
          </Link>

          <div className="mt-5 inline-flex rounded-full bg-violet-50 px-3 py-1 text-xs font-extrabold text-violet-700">
            AI PRODUCT COMPARISON
          </div>

          <h1 className="mt-4 text-3xl font-black text-slate-950 sm:text-4xl">
            So sánh sản phẩm
          </h1>

          <p className="mt-3 max-w-2xl text-slate-500">
            AI đối chiếu điểm phù hợp,
            độ tin cậy, giá, rating,
            thông số, ưu điểm và nhược
            điểm của từng sản phẩm.
          </p>
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-5 py-10 lg:px-8">
        {loading && (
          <div className="flex min-h-80 flex-col items-center justify-center">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />

            <p className="mt-5 font-bold text-slate-600">
              AI đang tải bảng so sánh...
            </p>
          </div>
        )}


        {error && (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
            <div className="font-extrabold">
              Không thể tải so sánh
            </div>

            <p className="mt-2 text-sm">
              {error}
            </p>
          </div>
        )}


        {!loading &&
          !error &&
          data &&
          !data.result && (
          <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center">
            <div className="text-5xl">
              🔎
            </div>

            <h2 className="mt-4 text-xl font-black">
              Chưa có dữ liệu so sánh
            </h2>
          </div>
        )}


        {data?.result && (
          <>
            <div className="mb-8 rounded-[28px] border border-blue-100 bg-gradient-to-r from-blue-50 to-violet-50 p-6">
              <div className="text-sm font-extrabold uppercase tracking-wider text-blue-600">
                🤖 Kết luận của AI
              </div>

              <p className="mt-3 text-lg font-bold leading-8 text-slate-800">
                {data.result.summary}
              </p>
            </div>


            <div
              className={[
                "grid gap-5",

                products.length === 2
                  ? "md:grid-cols-2"
                  : "md:grid-cols-3",
              ].join(" ")}
            >
              {products.map(
                (product) => (
                  <ProductSummaryCard
                    key={
                      product.product_id
                    }
                    product={
                      product
                    }
                    winner={
                      product.product_id ===
                      winnerId
                    }
                  />
                ),
              )}
            </div>


            <section className="mt-10 overflow-hidden rounded-[30px] border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-200 p-6">
                <h2 className="text-2xl font-black text-slate-950">
                  Bảng so sánh chi tiết
                </h2>

                <p className="mt-2 text-sm text-slate-500">
                  Đối chiếu các tiêu chí
                  quan trọng giữa những
                  sản phẩm đã chọn.
                </p>
              </div>


              <div className="overflow-x-auto">
                <table className="w-full min-w-180 border-collapse">
                  <thead>
                    <tr className="bg-slate-50">
                      <th className="w-48 border-b border-slate-200 p-4 text-left text-xs font-extrabold uppercase tracking-wide text-slate-400">
                        Tiêu chí
                      </th>

                      {products.map(
                        (product) => (
                          <th
                            key={
                              product.product_id
                            }
                            className="min-w-55 border-b border-slate-200 p-4 text-left"
                          >
                            <div className="font-extrabold text-slate-950">
                              {product.name}
                            </div>

                            {product.product_id ===
                              winnerId && (
                              <div className="mt-1 text-xs font-bold text-amber-600">
                                🏆 AI đề xuất
                              </div>
                            )}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>


                  <tbody>
                    <ComparisonRow
                      label="AI Match"
                      products={products}
                      render={(
                        product,
                      ) =>
                        `${percent(
                          product.ai_score,
                        )}%`
                      }
                    />

                    <ComparisonRow
                      label="Độ tin cậy"
                      products={products}
                      render={(
                        product,
                      ) =>
                        `${percent(
                          product.confidence,
                        )}%`
                      }
                    />

                    <ComparisonRow
                      label="Giá tốt nhất"
                      products={products}
                      render={(
                        product,
                      ) =>
                        formatPrice(
                          product
                            .best_offer
                            ?.price,
                          product
                            .best_offer
                            ?.currency ??
                            "VND",
                        )
                      }
                    />

                    <ComparisonRow
                      label="Nhà bán"
                      products={products}
                      render={(
                        product,
                      ) =>
                        product
                          .best_offer
                          ?.merchant ??
                        "Chưa rõ"
                      }
                    />

                    <ComparisonRow
                      label="Rating"
                      products={products}
                      render={(
                        product,
                      ) =>
                        product.rating !=
                        null
                          ? `⭐ ${product.rating.toFixed(
                              1,
                            )}`
                          : "Chưa có"
                      }
                    />

                    <ComparisonRow
                      label="Lượt đánh giá"
                      products={products}
                      render={(
                        product,
                      ) =>
                        product.review_count !=
                        null
                          ? product.review_count.toLocaleString(
                              "vi-VN",
                            )
                          : "Chưa có"
                      }
                    />

                    <ComparisonRow
                      label="Thứ hạng AI"
                      products={products}
                      render={(
                        product,
                      ) =>
                        product.recommendation_rank !=
                        null
                          ? `#${product.recommendation_rank}`
                          : "—"
                      }
                    />


                    {specificationKeys.map(
                      (key) => (
                        <ComparisonRow
                          key={key}
                          label={key}
                          products={
                            products
                          }
                          render={(
                            product,
                          ) => {
                            const value =
                              product
                                .specifications?.[
                                key
                              ];

                            return value ==
                              null
                              ? "—"
                              : String(
                                  value,
                                );
                          }}
                        />
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </section>


            <section className="mt-10 grid gap-5 lg:grid-cols-2">
              <div className="rounded-[28px] border border-emerald-100 bg-emerald-50/60 p-6">
                <h2 className="text-xl font-black text-emerald-950">
                  ✓ Ưu điểm
                </h2>

                <div className="mt-5 space-y-5">
                  {products.map(
                    (product) => (
                      <div
                        key={
                          product.product_id
                        }
                      >
                        <div className="font-extrabold text-slate-900">
                          {product.name}
                        </div>

                        {product.pros
                          .length > 0 ? (
                          <ul className="mt-2 space-y-2">
                            {product.pros.map(
                              (
                                item,
                                index,
                              ) => (
                                <li
                                  key={`${item}-${index}`}
                                  className="text-sm font-medium text-emerald-800"
                                >
                                  ✓ {item}
                                </li>
                              ),
                            )}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-slate-500">
                            Chưa có dữ liệu
                            ưu điểm.
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </div>


              <div className="rounded-[28px] border border-red-100 bg-red-50/50 p-6">
                <h2 className="text-xl font-black text-red-950">
                  − Nhược điểm
                </h2>

                <div className="mt-5 space-y-5">
                  {products.map(
                    (product) => (
                      <div
                        key={
                          product.product_id
                        }
                      >
                        <div className="font-extrabold text-slate-900">
                          {product.name}
                        </div>

                        {product.cons
                          .length > 0 ? (
                          <ul className="mt-2 space-y-2">
                            {product.cons.map(
                              (
                                item,
                                index,
                              ) => (
                                <li
                                  key={`${item}-${index}`}
                                  className="text-sm font-medium text-red-800"
                                >
                                  − {item}
                                </li>
                              ),
                            )}
                          </ul>
                        ) : (
                          <p className="mt-2 text-sm text-slate-500">
                            Chưa có dữ liệu
                            nhược điểm.
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  );
}


function ProductSummaryCard({
  product,
  winner,
}: {
  product: ComparisonProduct;
  winner: boolean;
}) {
  return (
    <article
      className={[
        "relative overflow-hidden",
        "rounded-[28px]",
        "border bg-white p-6",
        "shadow-sm",

        winner
          ? "border-amber-300 ring-2 ring-amber-100"
          : "border-slate-200",
      ].join(" ")}
    >
      {winner && (
        <div className="absolute right-4 top-4 z-10 rounded-full bg-amber-400 px-3 py-1 text-xs font-extrabold text-amber-950">
          🏆 Tốt nhất
        </div>
      )}

      <div className="flex h-32 items-center justify-center rounded-2xl bg-slate-50">
        {product.image_url ? (
          <div
            className="h-28 w-full bg-contain bg-center bg-no-repeat"
            style={{
              backgroundImage:
                `url("${product.image_url}")`,
            }}
          />
        ) : (
          <span className="text-5xl">
            🛍️
          </span>
        )}
      </div>

      <div className="mt-5 text-xs font-extrabold uppercase tracking-wide text-blue-600">
        {product.brand ||
          product.category ||
          "Sản phẩm"}
      </div>

      <h2 className="mt-2 pr-16 text-lg font-black leading-7 text-slate-950">
        {product.name}
      </h2>

      <div className="mt-5 text-2xl font-black text-blue-600">
        {formatPrice(
          product.best_offer?.price,
          product.best_offer
            ?.currency ??
            "VND",
        )}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-blue-50 p-3">
          <div className="text-xs font-bold text-slate-500">
            AI Match
          </div>

          <div className="mt-1 text-xl font-black text-blue-600">
            {percent(
              product.ai_score,
            )}
            %
          </div>
        </div>

        <div className="rounded-2xl bg-emerald-50 p-3">
          <div className="text-xs font-bold text-slate-500">
            Tin cậy
          </div>

          <div className="mt-1 text-xl font-black text-emerald-600">
            {percent(
              product.confidence,
            )}
            %
          </div>
        </div>
      </div>

      <Link
        href={
          `/products/${product.product_id}`
        }
        className="mt-5 flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-extrabold text-white transition hover:bg-blue-600"
      >
        Xem chi tiết
      </Link>
    </article>
  );
}


function ComparisonRow({
  label,
  products,
  render,
}: {
  label: string;

  products: ComparisonProduct[];

  render: (
    product: ComparisonProduct,
  ) => string;
}) {
  return (
    <tr className="transition hover:bg-slate-50/70">
      <td className="border-b border-slate-100 p-4 text-sm font-bold text-slate-500">
        {label}
      </td>

      {products.map(
        (product) => (
          <td
            key={
              product.product_id
            }
            className="border-b border-slate-100 p-4 text-sm font-bold text-slate-800"
          >
            {render(product)}
          </td>
        ),
      )}
    </tr>
  );
}