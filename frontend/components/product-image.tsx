"use client";

import { useState } from "react";
import { safeProductImageUrl } from "@/lib/results-utils";
import type { ProductImageEvidence } from "@/types/shopping";

export function ProductImage({
  src,
  evidence,
  name,
  className = "",
  onInvalid,
}: {
  src?: string | null;
  evidence?: ProductImageEvidence | null;
  name: string;
  className?: string;
  onInvalid?: () => void;
}) {
  const url = evidence?.status === "VERIFIED" && evidence.image_url === src
    ? safeProductImageUrl(src)
    : null;
  return <ImageContent key={url ?? "missing"} url={url} name={name} className={className} onInvalid={onInvalid} />;
}

function ImageContent({
  url,
  name,
  className,
  onInvalid,
}: {
  url: string | null;
  name: string;
  className: string;
  onInvalid?: () => void;
}) {
  const [failed, setFailed] = useState(false);

  if (!url || failed) return null;
  return (
    <div className={`product-media ${className}`}>
      {/* Product images are rendered only with matching server-side evidence. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt={name}
        loading="lazy"
        decoding="async"
        onError={() => { setFailed(true); onInvalid?.(); }}
        className="transition-transform duration-300 hover:scale-[1.02]"
      />
    </div>
  );
}
