import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const home = fs.readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const results = fs.readFileSync(new URL('../app/results/[sessionId]/page.tsx', import.meta.url), 'utf8');
const compare = fs.readFileSync(new URL('../app/compare/[comparisonId]/page.tsx', import.meta.url), 'utf8');
const card = fs.readFileSync(new URL('../components/product-card.tsx', import.meta.url), 'utf8');

test('smart search accepts one natural-language product command and has no direct URL input', () => {
  assert.doesNotMatch(home, /direct-product-url|directUrl|URL sản phẩm/);
  assert.match(home, /Tìm và đề xuất/);
  assert.match(home, /Máy tính/);
  assert.match(home, /executeSearch\(analyzed\.session_id/);
  assert.doesNotMatch(home, /Shopee|Lazada|clarification-answer/);
});
test('refresh is a real backend action and evidence statuses are visible', () => {
  assert.match(results, /executeSearch\(sessionId, \{ refresh: true \}\)/);
  assert.match(card, /Verified/); assert.match(card, /Stale/); assert.match(card, /Chưa xác minh/);
});
test('comparison separates product and offer views and warns on incomparable prices', () => {
  assert.match(compare, /So sánh cấu hình sản phẩm/); assert.match(compare, /Offer, shop và độ mới/);
  assert.match(compare, /NOT_COMPARABLE/);
});
