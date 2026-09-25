"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  useParams,
  useRouter,
} from "next/navigation";

import { RequirementSummary } from "@/components/requirement-summary";
import { PipelineProgress } from "@/components/pipeline-progress";
import { ResultFilters } from "@/components/result-filters";
import { EMPTY_FILTERS, filterAndSort, dataModeLabel, type ResultFilters as Filters } from "@/lib/results-utils";

import {
  ProductCard,
} from "@/components/product-card";

import Link from "next/link";
import { EmptyState, ErrorState } from "@/components/ui-state";

import {
  createComparison,
  getSearchResult,
} from "@/lib/api";

import type {
  SearchPipelineResponse,
} from "@/types/shopping";


export default function ResultsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return <SessionResults key={sessionId} sessionId={sessionId} />;
}

function SessionResults({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [filters, setFilters] = useState<Filters>({ ...EMPTY_FILTERS });
  const [reload, setReload] = useState(0);

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
  }, [sessionId, reload]);


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


  const visibleProducts = filterAndSort(data?.recommendations ?? [], filters);

  return (
    <main id="main-content" tabIndex={-1} className={selectedProductIds.length ? 'pb-36' : ''}>
      <section className="page-heading"><div className="page-container">
        <div className="flex flex-wrap items-center justify-between gap-4"><p className="eyebrow">Được chọn theo nhu cầu của bạn</p><Link href="/" className="text-link">← Tìm kiếm mới</Link></div>
        <h1 className="page-title mt-3">Khám phá lựa chọn phù hợp.</h1>
        <p className="muted mt-3 max-w-2xl text-sm leading-6">Đối chiếu giá, mức đáp ứng và thông tin nguồn để chọn điều phù hợp với bạn.</p>
      </div></section>
      <section className="page-container page-content">
        {loading && <PipelineProgress phase="read" />}
        {error && <ErrorState title="Không thể tải kết quả" retry={() => setReload(value => value + 1)} />}
        {data && !loading && !error && <>
          <div className="mb-5 flex flex-wrap items-center gap-3"><span className={`tag ${data.data_mode === 'live' ? 'tag-green' : 'tag-amber'}`}>{dataModeLabel(data.data_mode)}</span><p className="muted text-xs">{data.data_semantics === 'snapshot' ? 'Kết quả đã lưu · Giá có thể khác thời điểm hiện tại.' : data.data_semantics === 'legacy_recomputed' ? 'Phiên cũ: dữ liệu được tính lại đồng bộ.' : 'Chưa có kết quả được tạo.'}</p></div>
          {data.status && data.status !== 'COMPLETED' && <PipelineProgress phase={data.status} />}
          {(data.status === 'PROCESSING' || data.status === 'PENDING' || data.status === 'FAILED') && <button type="button" onClick={() => setReload(value => value + 1)} className="btn btn-secondary mb-5">Tải lại trạng thái đã lưu</button>}
          {!!data.warnings?.length && <div role="alert" className="notice mb-6">
            <p className="font-semibold">Lưu ý về dữ liệu</p><p className="mt-1 break-words">{data.warnings[0]}</p>
            {data.warnings.length > 1 && <details className="mt-2"><summary>Xem thêm {data.warnings.length - 1} lưu ý về nguồn</summary><ul className="mt-3 space-y-2">{data.warnings.slice(1).map((warning,index) => <li key={index}>{warning}</li>)}</ul></details>}
          </div>}
          <RequirementSummary requirement={data.requirement} />
          <ResultFilters products={data.recommendations} value={filters} onChange={setFilters} visibleCount={visibleProducts.length} />
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="section-title">{data.total_recommended} đề xuất dành cho bạn</h2><p className="muted text-xs">{data.total_found} ứng viên · {data.total_filtered} sau bộ lọc · {Math.round(data.processing_time_ms)} ms</p></div>
          {visibleProducts.length ? <div className="grid items-start gap-5 md:grid-cols-2 xl:grid-cols-3">
            {visibleProducts.map(product => <ProductCard key={product.product_id} product={product} sessionId={sessionId} selected={selectedProductIds.includes(product.product_id)} compareDisabled={selectedProductIds.length >= 3 && !selectedProductIds.includes(product.product_id)} onToggleCompare={toggleCompare} />)}
          </div> : <EmptyState title={data.recommendations.length ? 'Không có sản phẩm khớp bộ lọc' : 'Chưa tìm thấy sản phẩm phù hợp.'} description={data.recommendations.length ? 'Đặt lại bộ lọc để xem đầy đủ kết quả đã lưu.' : 'Bạn có thể thử ngân sách khác, giảm bớt tiêu chí hoặc mô tả thêm nhu cầu.'} action={data.recommendations.length ? <button type="button" onClick={() => setFilters({...EMPTY_FILTERS})} className="btn btn-primary">Đặt lại bộ lọc</button> : undefined} />}
        </>}
      </section>
      {selectedProductIds.length > 0 && <aside aria-label="Sản phẩm đã chọn so sánh" className="fixed bottom-4 left-1/2 z-40 w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2">
        <div className="surface !border-[#aac2ad] p-4 !shadow-xl"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div><p className="text-sm font-semibold">So sánh sản phẩm</p><p className="muted mt-1 text-xs">Đã chọn {selectedProductIds.length}/3 · Chọn ít nhất 2 sản phẩm</p></div>
          <div className="flex gap-2"><button type="button" disabled={comparing} onClick={() => setSelectedProductIds([])} className="btn btn-secondary">Bỏ chọn</button><button type="button" disabled={selectedProductIds.length < 2 || comparing} onClick={handleCompare} className="btn btn-primary">{comparing ? 'Đang so sánh...' : `So sánh ngay (${selectedProductIds.length})`}</button></div>
        </div>{compareError && <p role="alert" className="mt-3 text-xs text-red-700">Chưa thể tạo so sánh. Vui lòng thử lại.</p>}</div>
      </aside>}
    </main>
  );
}
