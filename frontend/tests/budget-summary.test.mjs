import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as utils from "../lib/results-utils.ts";

const code = ts.transpileModule(readFileSync(new URL("../components/requirement-summary.tsx", import.meta.url), "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const mod = { exports: {} };
const require = createRequire(import.meta.url);
new Function("require", "module", "exports", code)(name => name === "@/lib/results-utils" ? utils : require(name), mod, mod.exports);
const render = requirement => renderToStaticMarkup(React.createElement(mod.exports.RequirementSummary, { requirement }));

test("flexible summary renders backend target and window, without deriving tolerance", () => {
  const html = render({ budget_mode: "FLEXIBLE_TARGET", budget_max: 33000000, budget_target: 33000000,
    preferred_min: 31234567, preferred_max: 35123456, currency: "VND" });
  for (const text of ["Ngân sách mục tiêu", "Khoảng giá tham khảo", "33.000.000", "31.234.567", "35.123.456"]) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /Ngân sách tối đa/);
});
test("hard maximum and explicit range have distinct labels", () => {
  const hard = render({ budget_mode: "HARD_MAX", budget_max: 33000000 });
  assert.match(hard, /Ngân sách tối đa/);
  assert.doesNotMatch(hard, /Khoảng giá tham khảo/);
  const range = render({ budget_mode: "RANGE", budget_min: 31000000, budget_max: 35000000 });
  assert.match(range, /Khoảng ngân sách/);
  assert.doesNotMatch(range, /Ngân sách mục tiêu/);
});
test("historical missing budget mode retains legacy labels", () => {
  assert.match(render({ budget_max: 33000000 }), /Ngân sách tối đa/);
});
