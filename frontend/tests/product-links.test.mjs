import test from "node:test";
import assert from "node:assert/strict";
import { safeSalesUrl, safeProductImageUrl } from "../lib/results-utils.ts";

for (const url of ["https://shop.vn/", "https://shop.vn/xe-may/", "https://shop.vn/category/phones", "https://shop.vn/search?q=honda", "https://shop.vn/blog/review-honda", "javascript:alert(1)"]) {
  test(`rejects nonsales link ${url}`, () => assert.equal(safeSalesUrl(url, true), null));
}
test("direct path requires backend proof", () => {
  const url = "https://shop.vn/products/iphone-15-128gb";
  assert.equal(safeSalesUrl(url), null);
  assert.equal(safeSalesUrl(url, false), null);
  assert.equal(safeSalesUrl(url, true), url);
});
for (const url of [null, "javascript:bad()", "data:image/png;base64,x", "https://shop.vn/logo.png", "https://shop.vn/banner.jpg", "https://shop.vn/favicon.ico"]) {
  test(`rejects invalid image ${url}`, () => assert.equal(safeProductImageUrl(url), null));
}
