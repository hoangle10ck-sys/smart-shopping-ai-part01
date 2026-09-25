"use client";
import { useState } from "react";
import { safeProductImageUrl } from "@/lib/results-utils";
import { Icon } from "./icon";

export function ProductImage({ src, name, className = "" }: { src?: string | null; name: string; className?: string }) {
  const url = safeProductImageUrl(src);
  return <ImageContent key={url ?? "missing"} url={url} name={name} className={className} />;
}
function ImageContent({ url, name, className }: { url: string | null; name: string; className: string }) {
  const [failed, setFailed] = useState(false);
  return <div className={`product-media ${className}`}>
    {url && !failed ?
      // Remote product images retain their original URL and use the existing URL guard.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt={name} loading="lazy" onError={() => setFailed(true)} /> :
      <div className="product-placeholder"><span className="rounded-2xl border border-[#dbe4d8] bg-white/70 p-4"><Icon name="image" width="28" height="28" /></span><span>Chưa có ảnh sản phẩm</span></div>}
  </div>;
}
