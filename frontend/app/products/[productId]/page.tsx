"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getProduct } from "@/lib/api";
import { formatMoney, safeSalesUrl, safeHttpUrl } from "@/lib/results-utils";
import { RecommendationDetails } from "@/components/recommendation-details";
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
        setLoading(true); setError(false);
        const productId = Number(params.productId);
        if (!Number.isFinite(productId)) throw new Error('Invalid product');
        const result = await getProduct(productId, new URLSearchParams(window.location.search).get('sessionId'));
        if (active) setProduct(result);
      } catch { if (active) setError(true); }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [params.productId, attempt]);
  const sortedOffers = useMemo(() => [...(product?.offers ?? [])].sort((a,b) => a.price == null ? 1 : b.price == null ? -1 : a.price-b.price), [product]);
  if (loading) return <main id="main-content" tabIndex={-1} className="page-container page-content"><PipelineProgress phase="read" /></main>;
  if (error || !product) return <main id="main-content" tabIndex={-1} className="page-container page-content"><ErrorState title="Không thể tải sản phẩm" retry={() => setAttempt(value => value+1)} /></main>;
  // Every hero field comes from the same saved recommendation when available.
  // Catalog offers remain a separate section, never combined with the saved score.
  const snapshot = product.recommendation;
  const identity = snapshot ?? product;
  const offer = snapshot ?? sortedOffers[0];
  const name = identity.name || 'Sản phẩm';
  const shopUrl = safeSalesUrl(offer?.product_url, offer?.product_page_valid);
  const sourceUrl = safeHttpUrl(offer?.evidence_url || offer?.product_url);
  const image = snapshot ? snapshot.image_url : sortedOffers[0]?.product_page_valid ? sortedOffers[0].image_url : product.image_url;
  const specs = Object.entries(identity.specifications || {}).filter(([,value]) => value != null && String(value).trim());
  const pros = identity.pros ?? [], cons = identity.cons ?? [];
  return <main id="main-content" tabIndex={-1}>
    <div className="page-container pt-6"><button type="button" className="text-link" onClick={() => router.back()}>← Quay lại kết quả tìm kiếm</button></div>
    <section className="page-container grid gap-8 py-8 lg:grid-cols-2 lg:gap-14">
      <div className="surface self-start p-3"><ProductImage src={image} name={name} className="!aspect-square" /></div>
      <div className="py-2">
        <div className="flex flex-wrap gap-2">{identity.brand && <span className="tag">{identity.brand}</span>}{identity.category && <span className="tag">{identity.category}</span>}<AvailabilityBadge value={offer?.availability} /></div>
        <h1 className="page-title mt-5">{name}</h1>
        {identity.model && <p className="muted mt-3 text-sm">Model: {identity.model}</p>}
        {snapshot?.variant && <p className="muted mt-2 text-xs">{Object.entries(snapshot.variant).map(([key,value]) => `${key.replaceAll('_',' ')}: ${value}`).join(' · ')}</p>}
        <p className="muted mt-4 text-sm">{identity.rating != null ? `★ ${identity.rating.toFixed(1)}/5` : 'Chưa có rating'}{identity.review_count != null ? ` · ${identity.review_count.toLocaleString('vi-VN')} lượt đánh giá` : ''}</p>
        <div className="mt-6 border-y border-[#dce4de] py-6">
          <p className="muted text-xs">{snapshot ? 'Giá tại thời điểm đề xuất' : 'Giá offer đã thu thập'}</p>
          <p className="money mt-2 !text-4xl">{formatMoney(offer?.price, offer?.currency)}</p>
          <p className="muted mt-2 text-sm">tại <strong className="text-[#283e30]">{offer?.merchant || 'Chưa rõ cửa hàng'}</strong></p>
        </div>
        {snapshot && <div className="mt-5"><ScoreBadge value={snapshot.score?.final_score} /></div>}
        <div className="mt-5 flex flex-col gap-3">{shopUrl && <a href={shopUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary">Xem sản phẩm tại {offer?.merchant || 'cửa hàng'} ↗</a>}{sourceUrl && sourceUrl !== shopUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">Xem nguồn ↗</a>}</div>
        <p className="muted mt-4 text-xs leading-5">Giá và tồn kho thuộc dữ liệu đã lưu. Kiểm tra thông tin mới nhất tại cửa hàng trước khi mua.</p>
      </div>
    </section>
    <div className="page-container space-y-6 pb-16">
      {snapshot && <section aria-label="Đề xuất của phiên tìm kiếm" className="surface p-6 sm:p-8"><p className="eyebrow">Theo nhu cầu của bạn</p><h2 className="section-title mt-2">Đề xuất của phiên tìm kiếm</h2><p className="muted mt-3 text-sm">AI Match, giá và bằng chứng dưới đây thuộc cùng kết quả đã lưu.</p><RecommendationDetails product={snapshot} /></section>}
      <section className="surface p-6 sm:p-8"><h2 className="section-title">Thông số kỹ thuật{snapshot ? ' khi đề xuất' : ''}</h2>{specs.length ? <dl className="mt-5 grid gap-x-10 sm:grid-cols-2">{specs.map(([key,value]) => <div key={key} className="flex min-w-0 justify-between gap-4 border-b border-[#e5eae2] py-3 text-sm"><dt className="muted">{key.replaceAll('_',' ')}</dt><dd className="max-w-[65%] text-right font-medium">{String(value)}</dd></div>)}</dl> : <p className="muted mt-4 text-sm">Chưa có thông số chi tiết từ nguồn cho sản phẩm này.</p>}</section>
      <div className="grid gap-6 md:grid-cols-2">{[['Ưu điểm',pros],['Hạn chế / đánh đổi',cons]].map(([title,items]) => <section key={String(title)} className="surface p-6"><h2 className="section-title">{String(title)}</h2>{(items as string[]).length ? <ul className="muted mt-4 list-disc space-y-2 pl-4 text-sm leading-6">{(items as string[]).map((item,index) => <li key={index}>{item}</li>)}</ul> : <p className="muted mt-4 text-sm">Chưa có dữ liệu được cung cấp.</p>}</section>)}</div>
      <section className="surface p-6 sm:p-8"><h2 className="section-title">Nơi bán trong catalog</h2><p className="muted mt-2 text-xs leading-5">Các offer catalog đã thu thập, sắp xếp theo giá. Dữ liệu này được trình bày riêng với kết quả đề xuất lịch sử phía trên.</p>
        {sortedOffers.length ? <ul className="mt-5 divide-y divide-[#dce4de]">{sortedOffers.map(item => {
          const sales = safeSalesUrl(item.product_url,item.product_page_valid), evidence = safeHttpUrl(item.evidence_url || item.product_url);
          return <li key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-5"><div className="min-w-0"><p className="font-semibold">{item.merchant || item.source_domain || 'Chưa rõ cửa hàng'}</p><div className="mt-2 flex flex-wrap gap-2"><AvailabilityBadge value={item.availability} />{item.source_domain && <span className="tag">{item.source_domain}</span>}</div>{item.source_title && <p className="muted mt-2 text-xs">{item.source_title}</p>}<p className="muted mt-2 text-xs">Kiểm tra: {item.last_checked_at || 'Chưa rõ'}{item.source_reliability_score != null ? ` · Tin cậy nguồn: ${item.source_reliability_score}/100` : ''}</p></div><div className="flex flex-wrap items-center gap-4"><span className="money !text-xl">{formatMoney(item.price,item.currency)}</span>{sales && <a href={sales} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">Xem sản phẩm ↗</a>}{evidence && evidence !== sales && <a href={evidence} target="_blank" rel="noopener noreferrer" className="text-link">Xem nguồn ↗</a>}</div></li>;
        })}</ul> : <p className="muted mt-5 text-sm">Chưa tìm thấy nơi bán.</p>}
      </section>
      <div className="flex flex-wrap justify-between gap-4 text-xs muted"><span>Mã sản phẩm #{product.id} · Catalog cập nhật: {product.updated_at || 'Chưa rõ'}</span><Link href="/" className="text-link">Tìm kiếm mới →</Link></div>
    </div>
  </main>;
}
