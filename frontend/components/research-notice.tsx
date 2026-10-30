import type { ResearchMetadata } from "@/types/shopping";
import { historicalPriceLabel } from "@/lib/results-utils";

function safeSourceUrl(value: string | undefined, hosts: string[]): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && hosts.includes(url.hostname) ? url.toString() : null;
  } catch {
    return null;
  }
}

export function ResearchNotice({ product }: { product: ResearchMetadata }) {
  if (product.source_mode !== "HISTORICAL_RESEARCH") return null;
  const provenance = product.research_provenance;
  const isCommunityCatalog = ["OpenFoodFacts", "OpenProductsFacts"].includes(provenance?.dataset_id || "");
  const isAbo = provenance?.dataset_id === "Amazon-Berkeley-Objects";
  const fallbackDatasetUrl = isAbo
    ? "https://amazon-berkeley-objects.s3.amazonaws.com/index.html"
    : provenance?.dataset_id === "Amazon-Reviews-2023"
      ? "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
      : provenance?.dataset_id === "OpenFoodFacts"
        ? "https://world.openfoodfacts.org/"
        : provenance?.dataset_id === "OpenProductsFacts"
          ? "https://world.openproductsfacts.org/"
      : null;
  const datasetUrl = safeSourceUrl(provenance?.dataset_url, [
    "amazon-berkeley-objects.s3.amazonaws.com", "huggingface.co", "world.openfoodfacts.org",
    "world.openproductsfacts.org",
  ]) || fallbackDatasetUrl;
  const sourceProductUrl = safeSourceUrl(provenance?.source_product_url, [
    "world.openfoodfacts.org", "world.openproductsfacts.org",
  ]);
  const contentLicenseUrl = safeSourceUrl(provenance?.content_license_url, ["opendatacommons.org"]);
  const imageLicenseUrl = safeSourceUrl(provenance?.image_license_url, ["creativecommons.org"]);
  const identifier = provenance?.external_product_id || provenance?.parent_asin;
  const identifierLabel = provenance?.parent_asin ? "Mã sản phẩm trong dữ liệu" : "Mã mặt hàng trong dữ liệu";

  return (
    <aside
      className="notice mt-3 rounded-xl border-[#eddcb6] bg-[#fdfbf6] p-3 text-xs leading-relaxed text-[#755519]"
      aria-label="Nguồn dữ liệu nghiên cứu"
    >
      <p className="font-semibold text-[#664913]">
        {isCommunityCatalog
          ? "Dữ liệu tham khảo từ nguồn cộng đồng — không phải giá đang bán"
          : "Dữ liệu tham khảo lịch sử — không phải giá đang bán"}
      </p>
      <p className="mt-1.5 font-mono text-[11px]">
        {historicalPriceLabel(product)}
      </p>
      <p className="mt-1 text-[11px]">
        {isCommunityCatalog
          ? "Dữ liệu có thể chưa đầy đủ hoặc chưa được xác minh; không xác nhận giá bán, tồn kho hay nhà bán."
          : "Không có thông tin bán hàng, còn hàng hoặc mã hàng được xác minh."}
      </p>
      {provenance && (
        <p className="mt-1 break-all text-[11px] opacity-90">
          {provenance.dataset_name || "Nguồn dữ liệu"}{identifier ? ` · ${identifierLabel}: ${identifier}` : ""}
        </p>
      )}
      {provenance?.license === "CC BY 4.0" && (
        <p className="mt-1 text-[11px]">
          Giấy phép: <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer" className="underline">CC BY 4.0</a>
        </p>
      )}
      {provenance?.content_license && (
        <p className="mt-1 text-[11px]">
          Giấy phép dữ liệu: {contentLicenseUrl ? (
            <a href={contentLicenseUrl} target="_blank" rel="noopener noreferrer" className="underline">
              {provenance.content_license}
            </a>
          ) : provenance.content_license}
          {provenance.database_license ? ` · ${provenance.database_license}` : ""}
        </p>
      )}
      {provenance?.image_license && (
        <p className="mt-1 text-[11px]">
          Giấy phép ảnh: {imageLicenseUrl ? (
            <a href={imageLicenseUrl} target="_blank" rel="noopener noreferrer" className="underline">
              {provenance.image_license}
            </a>
          ) : provenance.image_license}
        </p>
      )}
      {sourceProductUrl && (
        <a className="text-link mt-2 mr-3 inline-block text-[11.5px] font-semibold text-[#805b16] underline"
           href={sourceProductUrl} target="_blank" rel="noopener noreferrer">
          Xem bản ghi nguồn ↗
        </a>
      )}
      {datasetUrl && (
      <a
        className="text-link mt-2 inline-block text-[11.5px] font-semibold text-[#805b16] underline hover:text-[#5e410b]"
        href={datasetUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        Xem bộ dữ liệu gốc ↗
      </a>
      )}
    </aside>
  );
}
