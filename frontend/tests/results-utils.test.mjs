import test from "node:test";
import assert from "node:assert/strict";
import {
  EMPTY_FILTERS, dataModeLabel, displayScore, filterAndSort, filterError, formatMoney,
  record, safeHttpUrl, scoreRows, textList,
} from "../lib/results-utils.ts";

const product = (id, overrides = {}) => ({
  product_id: id, rank: id, name: `Product ${id}`, brand: "ASUS", category: "laptop",
  currency: "VND", price: 100, rating: 4, score: { final_score: 90.12 }, specifications: {}, ...overrides,
});
const items = [product(1), product(2, { price: 200, rating: 5, score: { final_score: 80 } }), product(3, { price: null, rating: null })];

test("filter/sort preserves the original array, products, score and rank", () => {
  const frozen = items.map((item) => Object.freeze({ ...item, score: Object.freeze({ ...item.score }) }));
  Object.freeze(frozen);
  const before = JSON.stringify(frozen);
  const sorted = filterAndSort(frozen, { ...EMPTY_FILTERS, sort: "price_desc" });
  assert.deepEqual(sorted.map((item) => item.product_id), [2, 1, 3]);
  assert.equal(sorted[0], frozen[1]);
  assert.equal(JSON.stringify(frozen), before);
});

for (const [sort, expected] of [["ai", [1, 3, 2]], ["price_asc", [1, 2, 3]], ["price_desc", [2, 1, 3]], ["rating", [2, 1, 3]]]) {
  test(`${sort} uses backend values and places missing values last`, () => {
    assert.deepEqual(filterAndSort(items, { ...EMPTY_FILTERS, sort }).map((item) => item.product_id), expected);
  });
}

test("brand/category filters operate only on supplied session products", () => {
  const source = [product(1), product(2, { brand: "Dell" }), product(3, { category: "tai nghe" })];
  assert.deepEqual(filterAndSort(source, { ...EMPTY_FILTERS, brand: "ASUS", category: "laptop" }).map((item) => item.product_id), [1]);
  assert.equal(filterAndSort(source, { ...EMPTY_FILTERS, brand: "missing" }).length, 0);
  assert.equal(filterAndSort(source, EMPTY_FILTERS).length, 3);
});

test("price range is inclusive; unknown price does not satisfy a range", () => {
  assert.deepEqual(filterAndSort(items, { ...EMPTY_FILTERS, minPrice: "100", maxPrice: "200" }).map((item) => item.product_id), [1, 2]);
  assert.equal(filterAndSort([product(1, { price: 0 })], { ...EMPTY_FILTERS, maxPrice: "0" }).length, 1);
});

test("invalid ranges report an error and keep original results available", () => {
  for (const change of [{ minPrice: "201", maxPrice: "100" }, { minPrice: "-1" }, { maxPrice: "NaN" }]) {
    const filters = { ...EMPTY_FILTERS, ...change };
    assert.ok(filterError(filters, items));
    assert.deepEqual(filterAndSort(items, filters), items);
  }
});

test("price comparisons never silently mix currencies", () => {
  const mixed = [product(1), product(2, { currency: "USD", price: 1 })];
  assert.ok(filterError({ ...EMPTY_FILTERS, sort: "price_asc" }, mixed));
  assert.deepEqual(filterAndSort(mixed, { ...EMPTY_FILTERS, currency: "USD", sort: "price_asc" }).map((item) => item.product_id), [2]);
});

test("breakdown exposes raw components and unchanged 25/30/20/10/5/10 weights", () => {
  const score = Object.freeze({ budget_score: 80, requirement_score: 50, purpose_score: 20, rating_score: 40, review_score: 60, source_score: 70, final_score: 12.34 });
  const rows = scoreRows(score);
  assert.deepEqual(rows.map((row) => row.value), [80, 50, 20, 40, 60, 70]);
  assert.deepEqual(rows.map((row) => row.weight), [25, 30, 20, 10, 5, 10]);
  assert.equal(displayScore(score.final_score), "12.34/100");
});

test("missing values are not rendered as satisfied or zero", () => {
  assert.equal(displayScore(null), "Chưa có dữ liệu");
  assert.equal(displayScore(NaN), "Chưa có dữ liệu");
  assert.equal(displayScore(0), "0.00/100");
  assert.ok(scoreRows(null).every((row) => row.value === null));
  assert.equal(formatMoney(undefined, "VND"), "Chưa có dữ liệu");
  assert.ok(formatMoney(100).includes("chưa rõ"));
});

test("unknown historical data mode is not inferred from runtime or LLM mode", () => {
  assert.match(dataModeLabel("demo"), /Demo Mode/);
  assert.match(dataModeLabel("live"), /Live Data/);
  for (const mode of [undefined, null, "openai", false]) assert.match(dataModeLabel(mode), /Chưa xác định/);
});

test("only HTTP(S) product URLs become clickable", () => {
  assert.equal(safeHttpUrl("https://shop.example/product"), "https://shop.example/product");
  for (const url of ["javascript:alert(1)", "data:text/html,x", "/relative", undefined]) assert.equal(safeHttpUrl(url), null);
});

test("optional explanation/evidence fields are read without invented notes", () => {
  assert.deepEqual(record(null), {});
  assert.deepEqual(record([]), {});
  assert.deepEqual(textList([null, "", " ", "Backend evidence", { name: "unsupported" }]), ["Backend evidence"]);
});
