import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as utils from "../lib/results-utils.ts";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL("../components/research-notice.tsx", import.meta.url), "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const mod = { exports: {} };
new Function("require", "module", "exports", code)(path => path === "@/lib/results-utils" ? utils : require(path), mod, mod.exports);
const render = product => renderToStaticMarkup(React.createElement(mod.exports.ResearchNotice, { product }));
test("research notice labels historical USD, no live purchase claim", () => {
  const html = render({ source_mode: "HISTORICAL_RESEARCH", historical_price: { amount: "19.95", currency: "USD" } });
  assert.match(html, /không phải giá đang bán/);
  assert.match(html, /tham khảo lịch sử/);
  assert.match(html, /19.95 USD/);
  assert.match(html, /Không có thông tin bán hàng, còn hàng hoặc mã hàng được xác minh/);
  assert.doesNotMatch(html, /HISTORICAL_RESEARCH|OfferScore|N\/A/);
  assert.doesNotMatch(html, /19.950đ|Mua ngay/);
});
test("unknown and invalid currency never presented as verified USD", () => {
  for (const historical_price of [null, { amount: "19.95", currency: "VND" }, { amount: "NaN", currency: "USD" }]) {
    assert.match(render({ source_mode: "HISTORICAL_RESEARCH", historical_price }), /Chưa có giá trong dữ liệu tham khảo/);
  }
  assert.equal(render({}), "");
});
test("research provenance escapes text and never trusts arbitrary URLs", () => {
  const html = render({ source_mode: "HISTORICAL_RESEARCH", research_provenance: { parent_asin: "<script>attack</script>", revision: "test", dataset_url: "javascript:attack()" } });
  assert.doesNotMatch(html, /<script>|javascript:/);
  assert.match(html, /&lt;script&gt;/);
});
test("ABO research notice attributes the dataset and license without claiming live prices", () => {
  const html = render({ source_mode: "HISTORICAL_RESEARCH", historical_price: null, research_provenance: {
    dataset_id: "Amazon-Berkeley-Objects", dataset_name: "Amazon Berkeley Objects", external_product_id: "B012345678",
    identifier_label: "item_id", revision: "abo-v1", license: "CC BY 4.0",
    dataset_url: "javascript:ignored()", license_url: "javascript:ignored()",
  } });
  assert.match(html, /Amazon Berkeley Objects/);
  assert.match(html, /Mã mặt hàng trong dữ liệu: B012345678/);
  assert.match(html, /CC BY 4\.0/);
  assert.match(html, /amazon-berkeley-objects\.s3\.amazonaws\.com/);
  assert.match(html, /creativecommons\.org\/licenses\/by\/4\.0/);
  assert.match(html, /không phải giá đang bán/);
  assert.doesNotMatch(html, /javascript:/);
});
test("Open Facts research notice separates database and image licenses and links to the source product", () => {
  const html = render({ source_mode: "HISTORICAL_RESEARCH", historical_price: null, research_provenance: {
    dataset_id: "OpenProductsFacts", dataset_name: "Open Products Facts", external_product_id: "0884116295433",
    identifier_label: "barcode", revision: "openfacts-products-sample", content_license: "ODbL 1.0",
    content_license_url: "https://opendatacommons.org/licenses/odbl/1-0/",
    database_license: "Database Contents License (DbCL) v1.0", image_license: "CC BY-SA 4.0",
    image_license_url: "https://creativecommons.org/licenses/by-sa/4.0/",
    source_product_url: "https://world.openproductsfacts.org/product/0884116295433",
  } });
  assert.match(html, /Open Products Facts/);
  assert.match(html, /ODbL 1\.0/);
  assert.match(html, /CC BY-SA 4\.0/);
  assert.match(html, /Database Contents License/);
  assert.match(html, /world\.openproductsfacts\.org\/product\/0884116295433/);
  assert.match(html, /không phải giá đang bán/);
  assert.match(html, /tham khảo từ nguồn cộng đồng/);
  assert.doesNotMatch(html, /tham khảo lịch sử/);
  assert.doesNotMatch(html, /javascript:/);
});
test("research mode uses historical price only, never offer price", () => {
  assert.match(utils.dataModeLabel("research"), /Dữ liệu tham khảo lịch sử/);
  assert.doesNotMatch(utils.dataModeLabel("research"), /HISTORICAL_RESEARCH/);
  const item = (id, amount) => ({ product_id: id, rank: id, source_mode: "HISTORICAL_RESEARCH", currency: "USD", price: 999,
    historical_price: amount === null ? null : { amount, currency: "USD" } });
  const items = [item(1, "30.00"), item(2, "20.00"), item(3, null)];
  assert.deepEqual(utils.filterAndSort(items, { ...utils.EMPTY_FILTERS, sort: "price_asc" }).map(p => p.product_id), [2, 1, 3]);
  assert.deepEqual(utils.filterAndSort(items, { ...utils.EMPTY_FILTERS, minPrice: "20", maxPrice: "25" }).map(p => p.product_id), [2]);
  assert.equal(items[0].price, 999);
  assert.match(utils.filterError({ ...utils.EMPTY_FILTERS, sort: "price_asc" }, [...items, { price: 1, currency: "USD" }]), /lịch sử/);
});
