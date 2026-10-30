import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const home = fs.readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const results = fs.readFileSync(new URL('../app/results/[sessionId]/page.tsx', import.meta.url), 'utf8');
const compare = fs.readFileSync(new URL('../app/compare/[comparisonId]/page.tsx', import.meta.url), 'utf8');
const card = fs.readFileSync(new URL('../components/product-card.tsx', import.meta.url), 'utf8');

test('customer pages hide internal performance telemetry and database ids', () => {
  assert.doesNotMatch(results, /processing_time_ms|total_found|total_filtered/);
  assert.match(results, /visibleProducts\.length} sản phẩm phù hợp/);
  assert.doesNotMatch(compare, /SKU:|variant_id/);
  assert.doesNotMatch(compare, /last_checked_at|freshness_status|thời điểm cập nhật/i);
});

test('smart search uses one automatic flow with optional clarification and no direct URL input', () => {
  assert.doesNotMatch(home, /direct-product-url|directUrl|URL sản phẩm/);
  assert.match(home, /Tìm và đề xuất/);
  assert.match(home, /Máy tính/);
  assert.match(home, /executeSearch\(analyzed\.session_id/);
  assert.doesNotMatch(home, /Shopee|Lazada/);
  assert.match(home, /clarification-answer/);
});
test('refresh is a real backend action and evidence statuses are visible', () => {
  assert.match(results, /executeSearch\(sessionId, \{ refresh: true \}\)/);
  assert.match(results, /Tìm lại sản phẩm/);
  assert.match(card, /Nguồn đã kiểm tra/); assert.match(card, /Cần kiểm tra lại/); assert.match(card, /Chưa xác minh/);
  assert.doesNotMatch(card, /API verified|>Verified<|>Stale</);
});
test('comparison separates product and offer views and warns on incomparable prices', () => {
  assert.match(compare, /So sánh cấu hình sản phẩm/);
  assert.match(compare, /best_offer\?\.merchant/);
  assert.match(compare, /Chưa thể so sánh giá/);
  assert.doesNotMatch(compare, /AI Match|Offer, shop|last_checked_at|freshness_status/i);
});
