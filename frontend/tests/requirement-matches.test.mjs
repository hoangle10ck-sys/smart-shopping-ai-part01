import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Reuse the installed TS compiler and React renderer; no additional unit framework.
const code = ts.transpileModule(readFileSync(new URL("../components/requirement-matches.tsx", import.meta.url), "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const mod = { exports: {} };
new Function("require", "module", "exports", code)(createRequire(import.meta.url), mod, mod.exports);
const render = (items) => renderToStaticMarkup(React.createElement(mod.exports.RequirementMatches, { items }));

for (const [status, label] of [["matched", "✓ Đáp ứng"], ["unmet", "✕ Không đáp ứng"], ["unknown", "? Chưa đủ dữ liệu"]]) {
  test(`renders backend ${status} without comparing values on the client`, () => {
    const html = render([{ name: "ram", requested_value: "16GB", product_value: "8GB", status, reason: "Backend reason" }]);
    for (const text of [label, "16GB", "8GB", "Backend reason"]) assert.ok(html.includes(text));
  });
}

test("missing historical matches stay unavailable and do not become unmet", () => {
  for (const value of [undefined, []]) {
    const html = render(value);
    assert.match(html, /Backend chưa cung cấp/);
    assert.doesNotMatch(html, /✕|✓/);
  }
});

test("renders null product data and escapes source text", () => {
  const html = render([{ name: "<script>alert(1)</script>", requested_value: "16GB", product_value: null, status: "unknown", reason: "<img onerror=alert(1)>" }]);
  assert.match(html, /Chưa có dữ liệu/);
  assert.doesNotMatch(html, /<script>|<img/);
});
