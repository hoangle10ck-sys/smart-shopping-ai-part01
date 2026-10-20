"use client";

import { useState } from "react";
import { safeProductImageUrl } from "@/lib/results-utils";
import { Icon } from "./icon";

export function ProductImage({
  src,
  name,
  className = "",
}: {
  src?: string | null;
  name: string;
  className?: string;
}) {
  const url = safeProductImageUrl(src);
  return <ImageContent key={url ?? "missing"} url={url} name={name} className={className} />;
}

function ImageContent({
  url,
  name,
  className,
}: {
  url: string | null;
  name: string;
  className: string;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <div className={`product-media ${className}`}>
      {url && !failed ? (
        // Remote product images retain their original URL and use the existing URL guard.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={name}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="transition-transform duration-300 hover:scale-[1.02]"
        />
      ) : (
        <div className="product-placeholder">
          <span className="flex size-14 items-center justify-center rounded-2xl border border-[#d9e4dc] bg-white/90 text-[#4c6957] shadow-xs">
            <Icon name="image" width="26" height="26" />
          </span>
          <span className="text-xs font-medium text-[var(--muted)]">Chưa có ảnh sản phẩm</span>
        </div>
      )}
    </div>
  );
}
