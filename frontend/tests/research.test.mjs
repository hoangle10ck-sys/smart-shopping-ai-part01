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
  assert.match(html, /không phải giá bán hiện tại/);
  assert.match(html, /19.95 USD/);
  assert.match(html, /OfferScore: N\/A/);
  assert.doesNotMatch(html, /19.950đ|Mua ngay/);
});
test("unknown and invalid currency never presented as verified USD", () => {
  for (const historical_price of [null, { amount: "19.95", currency: "VND" }, { amount: "NaN", currency: "USD" }]) {
    assert.match(render({ source_mode: "HISTORICAL_RESEARCH", historical_price }), /Chưa có giá trong dataset/);
  }
  assert.equal(render({}), "");
});
test("research provenance escapes text and never trusts arbitrary URLs", () => {
  const html = render({ source_mode: "HISTORICAL_RESEARCH", research_provenance: { parent_asin: "<script>attack</script>", revision: "test", dataset_url: "javascript:attack()" } });
  assert.doesNotMatch(html, /<script>|javascript:/);
  assert.match(html, /&lt;script&gt;/);
});
test("research mode uses historical price only, never offer price", () => {
  assert.match(utils.dataModeLabel("research"), /HISTORICAL_RESEARCH/);
  const item = (id, amount) => ({ product_id: id, rank: id, source_mode: "HISTORICAL_RESEARCH", currency: "USD", price: 999,
    historical_price: amount === null ? null : { amount, currency: "USD" } });
  const items = [item(1, "30.00"), item(2, "20.00"), item(3, null)];
  assert.deepEqual(utils.filterAndSort(items, { ...utils.EMPTY_FILTERS, sort: "price_asc" }).map(p => p.product_id), [2, 1, 3]);
  assert.deepEqual(utils.filterAndSort(items, { ...utils.EMPTY_FILTERS, minPrice: "20", maxPrice: "25" }).map(p => p.product_id), [2]);
  assert.equal(items[0].price, 999);
  assert.match(utils.filterError({ ...utils.EMPTY_FILTERS, sort: "price_asc" }, [...items, { price: 1, currency: "USD" }]), /lịch sử/);
});
