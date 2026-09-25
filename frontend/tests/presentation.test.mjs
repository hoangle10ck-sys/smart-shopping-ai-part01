import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as utils from "../lib/results-utils.ts";

const require = createRequire(import.meta.url);
function component(name) {
  const code = ts.transpileModule(readFileSync(new URL(`../components/${name}.tsx`, import.meta.url), "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const mod = { exports: {} };
  new Function("require", "module", "exports", code)(path => path === "@/lib/results-utils" ? utils : path === "./icon" ? component("icon") : require(path), mod, mod.exports);
  return mod.exports;
}
const { ScoreBadge } = component("score-badge"), { AvailabilityBadge } = component("availability-badge"), { ProductImage } = component("product-image");
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));

test("missing comparison score stays unknown, while an observed zero stays zero", () => {
  const missing = render(ScoreBadge, { value: null });
  assert.match(missing, /Chưa có dữ liệu/);
  assert.doesNotMatch(missing, /0\.00|width:/);
  assert.match(render(ScoreBadge, { value: 0 }), /0\.00\/100/);
});
test("AI Match presents the exact backend score without recalculating or rounding to an integer", () => {
  assert.match(render(ScoreBadge, { value: 61.81 }), /61\.81\/100/);
});
test("unknown stock uses a neutral state, never the in-stock or out-of-stock style", () => {
  for (const value of [null, undefined, "unknown", "not_published"]) {
    const html = render(AvailabilityBadge, { value });
    assert.match(html, /Chưa rõ tồn kho/);
    assert.doesNotMatch(html, /tag-green|tag-red/);
  }
});
test("explicit source stock values remain distinct", () => {
  assert.match(render(AvailabilityBadge, {value: "https://schema.org/InStock"}), /Còn hàng/);
  assert.match(render(AvailabilityBadge, {value: "out_of_stock"}), /Hết hàng/);
});
test("missing or unsafe product images render a local placeholder without an img element", () => {
  for (const src of [null, "javascript:alert(1)", "https://shop.example/logo.png"]) {
    const html = render(ProductImage, {src, name: "Observed product"});
    assert.match(html, /Chưa có ảnh sản phẩm/);
    assert.doesNotMatch(html, /<img/);
  }
});
test("money formatting preserves currency and missing data", () => {
  assert.equal(utils.formatMoney(9790000, "VND"), "9.790.000đ");
  assert.equal(utils.formatMoney(45, "USD"), "45 USD");
  assert.match(utils.formatMoney(45), /chưa rõ tiền tệ/);
  assert.match(utils.formatMoney(null, "VND"), /Chưa có dữ liệu/);
});
