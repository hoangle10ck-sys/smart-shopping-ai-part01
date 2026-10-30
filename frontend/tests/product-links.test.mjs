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
for (const url of [
  "http://localhost:8000/admin",
  "http://127.0.0.1:8000/admin",
  "http://2130706433/admin",
  "http://10.0.0.8/image.jpg",
  "http://172.16.0.5/image.jpg",
  "http://192.168.1.10/image.jpg",
  "http://100.64.1.10/image.jpg",
  "http://169.254.169.254/latest/meta-data",
  "http://192.0.2.10/image.jpg",
  "http://198.18.0.1/image.jpg",
  "http://203.0.113.10/image.jpg",
  "http://[::1]:8000/admin",
  "https://metadata.google.internal/image.jpg",
  "https://shop.local/product.jpg",
]) {
  test(`rejects internal product image ${url}`, () => assert.equal(safeProductImageUrl(url), null));
}
test("allows a public merchant image URL", () => {
  const url = "https://cdn.shop.vn/products/headphones.jpg";
  assert.equal(safeProductImageUrl(url), url);
});
