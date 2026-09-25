"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getComparison } from "@/lib/api";
import { displayScore, formatMoney, safeHttpUrl } from "@/lib/results-utils";
import { ProductImage } from "@/components/product-image";
import { ScoreBadge } from "@/components/score-badge";
import { AvailabilityBadge } from "@/components/availability-badge";
import { PipelineProgress } from "@/components/pipeline-progress";
import { ErrorState, EmptyState } from "@/components/ui-state";
import type { ComparisonProduct, ComparisonResponse } from "@/types/shopping";

export default function ComparePage() {
  const params = useParams<{comparisonId: string}>();
  const comparisonId = Number(params.comparisonId);
  const [data,setData] = useState<ComparisonResponse | null>(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState(false);
  const [attempt,setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true); setError(false);
      try {
        if (!Number.isInteger(comparisonId) || comparisonId <= 0) throw new Error('Invalid comparison');
        const result = await getComparison(comparisonId);
        if (active) setData(result);
      } catch { if (active) setError(true); }
      finally { if (active) setLoading(false); }
    }
    void load(); return () => { active = false; };
  },[comparisonId,attempt]);
  const products = data?.result?.products ?? [];
  const specificationKeys = Array.from(new Set(products.flatMap(product => Object.keys(product.specifications ?? {}))));
  const rows: {label:string; render:(product:ComparisonProduct) => string}[] = [
    {label:'AI Match',render:p => displayScore(p.ai_score)},
    {label:'Độ tin cậy dữ liệu',render:p => displayScore(p.confidence)},
    {label:'Giá đã lưu',render:p => formatMoney(p.best_offer?.price,p.best_offer?.currency ?? undefined)},
    {label:'Nhà bán',render:p => p.best_offer?.merchant || 'Chưa rõ'},
    {label:'Rating',render:p => p.rating == null ? 'Chưa có dữ liệu' : `${p.rating.toFixed(1)}/5`},
    {label:'Lượt đánh giá',render:p => p.review_count == null ? 'Chưa có dữ liệu' : p.review_count.toLocaleString('vi-VN')},
    {label:'Thứ hạng AI',render:p => p.recommendation_rank == null ? 'Chưa có dữ liệu' : `#${p.recommendation_rank}`},
    ...specificationKeys.map(key => ({label:key.replaceAll('_',' '),render:(p:ComparisonProduct) => p.specifications?.[key] == null ? 'Chưa có dữ liệu' : String(p.specifications[key])})),
  ];
  return <main id="main-content" tabIndex={-1}>
    <section className="page-heading"><div className="page-container"><p className="eyebrow">Đặt các lựa chọn cạnh nhau</p><h1 className="page-title mt-3">So sánh sản phẩm</h1><p className="muted mt-3 text-sm">Cùng một góc nhìn. Rõ hơn những điều khác biệt.</p>{data?.session_id && <Link href={`/results/${data.session_id}`} className="text-link mt-4 inline-block">← Về kết quả tìm kiếm</Link>}</div></section>
    <div className="page-container page-content">
      {loading && <PipelineProgress phase="read" />}
      {error && <ErrorState title="Không thể tải so sánh" retry={() => setAttempt(value => value+1)} />}
      {!loading && !error && !data?.result && <EmptyState title="Chưa có dữ liệu so sánh" description="Chọn từ 2 đến 3 sản phẩm trên trang kết quả để bắt đầu." />}
      {!loading && !error && data?.result && <>
        <section className="mb-6 rounded-2xl border border-[#cddfc7] bg-[#eef4e8] p-6"><p className="eyebrow">Kết luận trong bản so sánh đã lưu</p><p className="mt-3 text-sm leading-7">{data.result.summary}</p></section>
        <div className={`grid gap-5 ${products.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-3'}`}>{products.map(product => {
          const source = safeHttpUrl(product.best_offer?.product_url);
          return <article key={product.product_id} className="surface min-w-0 p-4">
            <ProductImage src={product.image_url} name={product.name || 'Sản phẩm'} />
            <div className="p-2 pt-4">{product.product_id === data.result?.winner_product_id && <span className="tag tag-green mb-3">Được đề xuất trong bản so sánh</span>}<p className="eyebrow">{product.brand || product.category || 'Sản phẩm'}</p><h2 className="mt-2 text-lg font-semibold">{product.name}</h2>{product.model && <p className="muted mt-2 text-xs">{product.model}</p>}
              <p className="money mt-4">{formatMoney(product.best_offer?.price,product.best_offer?.currency ?? undefined)}</p><p className="muted mt-1 text-xs">{product.best_offer?.merchant || 'Chưa rõ cửa hàng'}</p>
              <div className="mt-3"><AvailabilityBadge value={product.best_offer?.availability} /></div><div className="mt-4"><ScoreBadge value={product.ai_score} /></div>
              <Link href={`/products/${product.product_id}?sessionId=${encodeURIComponent(data.session_id)}`} className="btn btn-secondary mt-4 w-full">Xem chi tiết</Link>{source && <a href={source} target="_blank" rel="noopener noreferrer" className="text-link mt-3 block text-center">Xem nguồn ↗</a>}
            </div>
          </article>;
        })}</div>
        <section className="surface mt-7 overflow-hidden"><div className="p-6"><h2 className="section-title">Bảng so sánh chi tiết</h2><p className="muted mt-2 text-xs">Dữ liệu trong bản so sánh đã lưu. Trên điện thoại, cuộn ngang trong bảng để xem các sản phẩm.</p></div>
          <div className="compare-scroll" role="region" aria-label="Bảng đối chiếu sản phẩm" tabIndex={0}><table className="compare-table"><caption className="sr-only">So sánh thông tin các sản phẩm đã chọn</caption><thead><tr><th scope="col">Tiêu chí</th>{products.map(p => <th scope="col" key={p.product_id}>{p.name}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.label}><th scope="row">{row.label}</th>{products.map(p => <td key={p.product_id}>{row.render(p)}</td>)}</tr>)}</tbody></table></div>
        </section>
        <div className="mt-6 grid gap-5 md:grid-cols-2">{(['pros','cons'] as const).map(kind => <section key={kind} className="surface p-6"><h2 className="section-title">{kind === 'pros' ? 'Ưu điểm' : 'Hạn chế / đánh đổi'}</h2>{products.map(p => <div key={p.product_id} className="mt-5"><h3 className="text-sm font-semibold">{p.name}</h3>{p[kind]?.length ? <ul className="muted mt-2 list-disc space-y-2 pl-4 text-xs leading-5">{p[kind].map((item,index) => <li key={index}>{item}</li>)}</ul> : <p className="muted mt-2 text-xs">Chưa có dữ liệu.</p>}</div>)}</section>)}</div>
        <section className="surface mt-6 p-6"><h2 className="section-title">Đối chiếu yêu cầu và bằng chứng</h2><p className="muted mt-3 text-sm leading-6">Bản so sánh này chưa lưu đối chiếu matched / unmet / unknown hoặc evidence theo trường. Mở kết quả tìm kiếm để xem dữ liệu của phiên; thông tin đó không được ghép vào bản so sánh này.</p><Link href={`/results/${data.session_id}`} className="text-link mt-4 inline-block">Xem kết quả của phiên →</Link></section>
      </>}
    </div>
  </main>;
}
