import type { ResearchMetadata } from "@/types/shopping";
import { historicalPriceLabel } from "@/lib/results-utils";

export function ResearchNotice({ product }: { product: ResearchMetadata }) {
  if (product.source_mode !== "HISTORICAL_RESEARCH") return null;

  return (
    <aside
      className="notice mt-3 rounded-xl border-[#eddcb6] bg-[#fdfbf6] p-3 text-xs leading-relaxed text-[#755519]"
      aria-label="Nguồn dữ liệu nghiên cứu"
    >
      <p className="font-semibold text-[#664913]">
        Dữ liệu nghiên cứu (2023) — không phải giá bán hiện tại
      </p>
      <p className="mt-1.5 font-mono text-[11px]">
        HISTORICAL_RESEARCH · {historicalPriceLabel(product)}
      </p>
      <p className="mt-1 text-[11px]">
        OfferScore: N/A · Không xác minh tồn kho hoặc SKU.
      </p>
      {product.research_provenance && (
        <p className="mt-1 break-all text-[11px] opacity-90">
          Amazon Reviews 2023 · parent_asin: {product.research_provenance.parent_asin} (không phải SKU) · revision: {product.research_provenance.revision}
        </p>
      )}
      <a
        className="text-link mt-2 inline-block text-[11.5px] font-semibold text-[#805b16] underline hover:text-[#5e410b]"
        href="https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
        target="_blank"
        rel="noopener noreferrer"
      >
        Nguồn: McAuley Lab ↗
      </a>
    </aside>
  );
}
