"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  useParams,
  useRouter,
} from "next/navigation";

import {
  ProductCard,
} from "@/components/product-card";

import {
  SiteHeader,
} from "@/components/site-header";

import {
  createComparison,
  getSearchResult,
} from "@/lib/api";

import type {
  SearchPipelineResponse,
} from "@/types/shopping";


export default function ResultsPage() {
  const params =
    useParams<{
      sessionId: string;
    }>();

  const router =
    useRouter();

  const sessionId =
    params.sessionId;


  const [
    data,
    setData,
  ] =
    useState<SearchPipelineResponse | null>(
      null,
    );

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );

  const [
    selectedProductIds,
    setSelectedProductIds,
  ] =
    useState<number[]>(
      [],
    );

  const [
    comparing,
    setComparing,
  ] =
    useState(false);

  const [
    compareError,
    setCompareError,
  ] =
    useState<string | null>(
      null,
    );


  useEffect(() => {
    let active = true;


    async function load() {
      try {
        setLoading(true);
        setError(null);

        const result =
          await getSearchResult(
            sessionId,
          );

        if (active) {
          setData(result);
        }
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Không thể tải kết quả.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }


    if (sessionId) {
      load();
    }


    return () => {
      active = false;
    };
  }, [sessionId]);


  function toggleCompare(
    productId: number,
  ) {
    setCompareError(null);

    setSelectedProductIds(
      (current) => {
        if (
          current.includes(
            productId,
          )
        ) {
          return current.filter(
            (id) =>
              id !== productId,
          );
        }


        if (
          current.length >= 3
        ) {
          return current;
        }


        return [
          ...current,
          productId,
        ];
      },
    );
  }


  async function handleCompare() {
    if (
      selectedProductIds.length < 2
    ) {
      setCompareError(
        "Hãy chọn ít nhất 2 sản phẩm để so sánh.",
      );

      return;
    }


    if (
      selectedProductIds.length > 3
    ) {
      setCompareError(
        "Chỉ có thể so sánh tối đa 3 sản phẩm.",
      );

      return;
    }


    try {
      setComparing(true);
      setCompareError(null);


      const comparison =
        await createComparison(
          sessionId,
          selectedProductIds,
        );


      if (
        !comparison.id
      ) {
        throw new Error(
          "Backend không trả về comparison id.",
        );
      }


      router.push(
        `/compare/${comparison.id}`,
      );
    } catch (caught) {
      setCompareError(
        caught instanceof Error
          ? caught.message
          : "Không thể tạo so sánh.",
      );
    } finally {
      setComparing(false);
    }
  }


  return (
    <main className="min-h-screen bg-slate-50">
      <SiteHeader />


      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-12 lg:px-8">
          <div className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-extrabold text-blue-700">
            AI RECOMMENDATION
          </div>


          <h1 className="mt-4 text-3xl font-black text-slate-950 sm:text-4xl">
            Sản phẩm AI đề xuất
          </h1>


          <p className="mt-3 max-w-2xl text-slate-500">
            Các sản phẩm được lọc và
            xếp hạng dựa trên nhu cầu,
            ngân sách, rating, nguồn dữ
            liệu và độ tin cậy.
          </p>
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-5 py-10 lg:px-8">
        {/* LOADING */}
        {loading && (
          <div className="flex min-h-80 flex-col items-center justify-center">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />

            <p className="mt-5 font-bold text-slate-600">
              Đang tải kết quả AI...
            </p>
          </div>
        )}


        {/* ERROR */}
        {error && (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
            <div className="font-extrabold">
              Không thể tải kết quả
            </div>

            <p className="mt-2 text-sm">
              {error}
            </p>
          </div>
        )}


        {/* DATA */}
        {data && (
          <>
            <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-2xl font-black text-slate-950">
                  {
                    data.total_recommended
                  }
                </span>

                <span className="ml-2 text-sm font-medium text-slate-500">
                  sản phẩm phù hợp nhất
                </span>
              </div>


              <div className="flex flex-wrap items-center gap-3">
                <div className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-500">
                  ⚡ Xử lý trong{" "}
                  {Math.round(
                    data.processing_time_ms,
                  )}
                  ms
                </div>


                {selectedProductIds.length >
                  0 && (
                  <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-bold text-blue-700">
                    Đã chọn{" "}
                    {
                      selectedProductIds.length
                    }
                    /3
                  </div>
                )}
              </div>
            </div>


            {/* PRODUCT GRID */}
            {data.recommendations.length >
            0 ? (
              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
                {data.recommendations.map(
                  (product) => (
                    <ProductCard
                      key={
                        product.product_id
                      }
                      product={
                        product
                      }
                      sessionId={
                        sessionId
                      }
                      selected={
                        selectedProductIds.includes(
                          product.product_id,
                        )
                      }
                      compareDisabled={
                        selectedProductIds.length >=
                          3 &&
                        !selectedProductIds.includes(
                          product.product_id,
                        )
                      }
                      onToggleCompare={
                        toggleCompare
                      }
                    />
                  ),
                )}
              </div>
            ) : (
              <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center">
                <div className="text-5xl">
                  🔎
                </div>

                <h2 className="mt-5 text-xl font-black">
                  Chưa tìm thấy sản phẩm
                  phù hợp
                </h2>

                <p className="mt-2 text-slate-500">
                  Hãy thử thay đổi ngân
                  sách hoặc yêu cầu.
                </p>
              </div>
            )}
          </>
        )}
      </section>


      {/* FLOATING COMPARE BAR */}
      {selectedProductIds.length >
        0 && (
        <div className="fixed bottom-5 left-1/2 z-50 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2">
          <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-2xl shadow-slate-950/20">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-extrabold text-slate-950">
                  So sánh sản phẩm
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Đã chọn{" "}
                  {
                    selectedProductIds.length
                  }{" "}
                  sản phẩm. Chọn từ 2
                  đến 3 sản phẩm.
                </p>
              </div>


              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={
                    comparing
                  }
                  onClick={() =>
                    setSelectedProductIds(
                      [],
                    )
                  }
                  className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
                >
                  Bỏ chọn
                </button>


                <button
                  type="button"
                  disabled={
                    selectedProductIds.length <
                      2 ||
                    comparing
                  }
                  onClick={
                    handleCompare
                  }
                  className="rounded-2xl bg-blue-600 px-5 py-3 text-sm font-extrabold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {comparing
                    ? "Đang so sánh..."
                    : `So sánh ngay (${selectedProductIds.length})`}
                </button>
              </div>
            </div>


            {compareError && (
              <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold text-red-600">
                {compareError}
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}