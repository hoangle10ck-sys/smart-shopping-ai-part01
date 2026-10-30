import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as utils from "../lib/results-utils.ts";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL("../components/product-card.tsx", import.meta.url), "utf8"), {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const empty = () => null;
const LinkMock = ({ href, children, ...props }) => React.createElement("a", { href, ...props }, children);
LinkMock.default = LinkMock;
const components = {
  "next/link": LinkMock,
  "@/components/recommendation-details": { RecommendationDetails: empty },
  "@/components/feedback-panel": { FeedbackPanel: empty },
  "@/components/product-image": { ProductImage: empty },
  "@/components/score-badge": { ScoreBadge: empty },
  "@/components/availability-badge": { AvailabilityBadge: empty },
  "@/components/research-notice": { ResearchNotice: empty },
  "@/lib/results-utils": utils,
};
const mod = { exports: {} };
new Function("require", "module", "exports", code)(path => components[path] ?? require(path), mod, mod.exports);
const render = product => renderToStaticMarkup(React.createElement(mod.exports.ProductCard, {
  product: {
    product_id: 1, name: "ABO product", rank: 1, source_mode: "HISTORICAL_RESEARCH", specifications: {},
    image_url: "https://images.example/product.jpg",
    image_evidence: { status: "VERIFIED", image_url: "https://images.example/product.jpg", content_sha256: "a".repeat(64) },
    ...product,
  },
  sessionId: "test-session",
}));

test("research card states when ratings and review counts are missing", () => {
  const html = render({ rating: null, review_count: null });
  assert.match(html, /Chưa có đánh giá hoặc lượt nhận xét trong dữ liệu tham khảo/);
  assert.doesNotMatch(html, /Đánh giá tham khảo/);
});

test("research card labels observed ratings as historical", () => {
  const html = render({ rating: 4.2, review_count: 18 });
  assert.match(html, /Đánh giá tham khảo/);
  assert.match(html, /4\.2\/5/);
  assert.match(html, /18 đánh giá/);
  assert.doesNotMatch(html, /Chưa có đánh giá hoặc lượt nhận xét trong dữ liệu tham khảo/);
});

test("product freshness status is written in Vietnamese for shoppers", () => {
  const stale = render({ source_mode: null, freshness_status: "STALE" });
  assert.match(stale, /Cần kiểm tra lại/);
  assert.doesNotMatch(stale, />Stale</);
});

test("product card is excluded without matching verified image evidence", () => {
  assert.equal(render({ image_evidence: null }), "");
  assert.equal(render({ image_evidence: { status: "VERIFIED", image_url: "https://images.example/other.jpg" } }), "");
});
