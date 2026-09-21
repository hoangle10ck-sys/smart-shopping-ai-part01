import { test, expect, type Page } from "@playwright/test";
import type { SearchPipelineResponse } from "../types/shopping";

const API = "http://127.0.0.1:18000";
const query = "Tai nghe 500 nghìn để học online, mic tốt, pin lâu";

test.beforeEach(async ({ page, request }) => {
  const status = await request.get(`${API}/api/system/status`);
  expect(status.ok()).toBeTruthy();
  expect((await status.json()).demo_mode).toBe(true);
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" && ["13000", "18000"].includes(url.port)
      ? route.continue() : route.abort("blockedbyclient");
  });
});

async function demoResult(page: Page): Promise<SearchPipelineResponse> {
  const analysis = await page.request.post(`${API}/api/requirements/analyze`, { data: { raw_query: query } });
  expect(analysis.ok()).toBeTruthy();
  const { session_id } = await analysis.json();
  const response = await page.request.post(`${API}/api/search`, { data: { session_id } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test("Demo journey: home, analysis, search, results, filters, detail, compare, feedback, history", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox").first().fill(query);
  const analysisResponse = page.waitForResponse((r) => r.url() === `${API}/api/requirements/analyze` && r.request().method() === "POST");
  const searchResponse = page.waitForResponse((r) => r.url() === `${API}/api/search` && r.request().method() === "POST");
  await page.getByRole("button", { name: /Tìm bằng AI/ }).click();
  const analysis = await analysisResponse;
  expect(analysis.ok()).toBeTruthy();
  expect(analysis.request().postDataJSON().raw_query).toBe(query);
  const searched = await searchResponse;
  expect(searched.ok()).toBeTruthy();
  // Home navigates with a full page load, which can evict response bodies from
  // browser memory. Read the persisted result through the real GET endpoint.
  const sessionId = searched.request().postDataJSON().session_id;
  const resultPath = `/results/${sessionId}`;
  await expect(page).toHaveURL(new RegExp(`${resultPath}$`));
  const resultResponse = await page.request.get(`${API}/api/search/${sessionId}`);
  expect(resultResponse.ok()).toBeTruthy();
  const data: SearchPipelineResponse = await resultResponse.json();
  expect(data.requirement?.category).toBe("tai nghe");
  expect(data.data_mode).toBe("demo");
  expect(data.recommendations.length).toBe(3);
  const cards = page.getByRole("article");
  await expect(cards).toHaveCount(3);
  await expect(page.getByRole("region", { name: "Nhu cầu đã phân tích" })).toContainText("tai nghe");
  await expect(page.getByText("Demo Mode — dữ liệu minh họa", { exact: true })).toBeVisible();
  const first = data.recommendations[0];
  await expect(cards.first().getByRole("heading", { name: first.name, exact: true })).toBeVisible();
  await expect(cards.first().getByLabel("Đối chiếu yêu cầu")).toContainText("✓ Đáp ứng");
  await cards.first().getByText("Điểm thành phần", { exact: true }).click();
  await expect(cards.first().getByRole("table")).toContainText("30%");
  await cards.first().getByText("Vì sao được đề xuất?", { exact: true }).click();
  await expect(cards.first().getByText("Giải thích Demo", { exact: true })).toBeVisible();
  await cards.first().getByText("Nguồn và bằng chứng", { exact: true }).click();
  await expect(cards.first().getByLabel("Bằng chứng theo trường")).toContainText(`price: ${first.price}`);

  const sorted = [...data.recommendations].sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity));
  await page.getByRole("combobox", { name: "Sắp xếp", exact: true }).selectOption("price_asc");
  await expect(cards.first().getByRole("heading", { name: sorted[0].name, exact: true })).toBeVisible();
  await page.getByRole("spinbutton", { name: "Giá tối đa", exact: true }).fill(String(sorted[0].price));
  await expect(cards).toHaveCount(data.recommendations.filter((item) => item.price != null && item.price <= sorted[0].price!).length);
  await page.getByRole("button", { name: "Đặt lại bộ lọc" }).click();
  await expect(cards).toHaveCount(3);

  await cards.first().getByRole("link", { name: "Xem chi tiết", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/products/${first.product_id}\\?sessionId=${data.session_id}$`));
  await expect(page.getByRole("region", { name: "Đề xuất của phiên tìm kiếm" })).toContainText("AI Match");
  await expect(page.getByRole("heading", { name: first.name, exact: true })).toBeVisible();
  await page.goto(resultPath);
  await expect(cards).toHaveCount(3);
  await cards.nth(0).getByRole("button", { name: "+ So sánh", exact: true }).click();
  await cards.nth(1).getByRole("button", { name: "+ So sánh", exact: true }).click();
  const comparisonResponse = page.waitForResponse((r) => r.url() === `${API}/api/comparisons` && r.request().method() === "POST");
  await page.getByRole("button", { name: "So sánh ngay (2)", exact: true }).click();
  expect((await comparisonResponse).ok()).toBeTruthy();
  await expect(page).toHaveURL(/\/compare\/\d+$/);
  await expect(page.getByRole("heading", { name: "Bảng so sánh chi tiết" })).toBeVisible();
  await page.goto(resultPath);
  const feedbackResponse = page.waitForResponse((r) => r.url() === `${API}/api/feedback` && r.request().method() === "POST");
  await cards.first().getByRole("button", { name: "👍 Hữu ích" }).click();
  const feedback = await feedbackResponse;
  expect(feedback.ok()).toBeTruthy();
  expect((await feedback.json()).is_helpful).toBe(true);
  await expect(cards.first().getByText("✓ Cảm ơn bạn đã phản hồi")).toBeVisible();
  await page.getByRole("link", { name: "Lịch sử", exact: true }).click();
  await expect(page).toHaveURL(/\/history$/);
  await page.getByRole("link", { name: `Xem lại: ${query}`, exact: true }).first().click();
  await expect(page).toHaveURL(new RegExp(`${resultPath}$`));
  await expect(cards).toHaveCount(3);
  const reloaded = await page.request.get(`${API}/api/search/${data.session_id}`);
  expect((await reloaded.json()).recommendations).toEqual(data.recommendations);
});

test("renders all backend match states and structured evidence without client inference", async ({ page }) => {
  const data = await demoResult(page);
  data.recommendations[0].requirement_matches = [
    { name: "ram", requested_value: "16GB", product_value: "16GB", status: "matched", reason: "Đủ RAM theo backend" },
    { name: "storage", requested_value: "512GB", product_value: "256GB", status: "unmet", reason: "Thiếu dung lượng theo backend" },
    { name: "camera", requested_value: "tốt", product_value: null, status: "unknown", reason: "Chưa có quan sát camera" },
  ];
  data.recommendations[0].evidence = { fields: [
    { field: "specifications.ram", value: "16GB", domain: "fixture.example", url: "https://fixture.example/product", retrieved_at: "2026-01-01T00:00:00Z", reliability: 75 },
    { field: "specifications.camera", value: "<script>alert(1)</script>", url: "javascript:alert(1)" },
  ] };
  await page.route(`${API}/api/search/${data.session_id}`, (route) => route.fulfill({ json: data }));
  await page.goto(`/results/${data.session_id}`);
  const card = page.getByRole("article").first();
  const matches = card.getByLabel("Đối chiếu yêu cầu");
  for (const text of ["✓ Đáp ứng", "✕ Không đáp ứng", "? Chưa đủ dữ liệu", "16GB", "512GB", "256GB", "Chưa có quan sát camera"]) {
    await expect(matches).toContainText(text);
  }
  await card.getByText("Nguồn và bằng chứng", { exact: true }).click();
  const evidence = card.getByLabel("Bằng chứng theo trường");
  await expect(evidence).toContainText("fixture.example");
  await expect(evidence).toContainText("2026-01-01T00:00:00Z");
  await expect(evidence).toContainText("75/100");
  await expect(evidence.getByRole("link")).toHaveCount(1);
  await expect(evidence.locator("script")).toHaveCount(0);
});

test("old snapshot renders empty metadata and preserves failure warning with recommendations", async ({ page }) => {
  const data = await demoResult(page);
  for (const item of data.recommendations) {
    delete item.requirement_matches;
    if (item.evidence) delete item.evidence.fields;
  }
  data.status = "FAILED";
  data.warnings = ["Provider thất bại; giữ kết quả thành công trước đó."];
  await page.route(`${API}/api/search/${data.session_id}`, (route) => route.fulfill({ json: data }));
  await page.goto(`/results/${data.session_id}`);
  const card = page.getByRole("article").first();
  await expect(page.getByRole("article")).toHaveCount(3);
  await expect(page.getByRole("alert").filter({ hasText: data.warnings[0] })).toBeVisible();
  await expect(card).toContainText("Backend chưa cung cấp đối chiếu từng yêu cầu");
  await card.getByText("Nguồn và bằng chứng", { exact: true }).click();
  await expect(card).toContainText("Chưa có evidence có cấu trúc");
});

test("sales links require page proof and broken remote images use the local placeholder", async ({ page }) => {
  const data = await demoResult(page);
  const item = data.recommendations[0];
  item.product_page_valid = true;
  item.product_url = "https://retailer.example/products/sounddemo-h20";
  item.evidence_url = "https://review.example/blog/sounddemo-h20";
  item.image_url = "http://127.0.0.1:13000/broken-product.jpg";
  await page.route("**/broken-product.jpg", (route) => route.fulfill({ status: 404, body: "missing" }));
  await page.route(`${API}/api/search/${data.session_id}`, (route) => route.fulfill({ json: data }));
  await page.goto(`/results/${data.session_id}`);
  const card = page.getByRole("article").first();
  const link = card.getByRole("link", { name: "Xem sản phẩm ↗", exact: true });
  await expect(link).toHaveAttribute("href", item.product_url);
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await expect(card.getByText("Chưa có ảnh sản phẩm", { exact: true })).toBeVisible();
  for (const url of ["https://retailer.example/", "https://retailer.example/xe-may/", "https://retailer.example/search?q=x", "https://retailer.example/blog/model"]) {
    item.product_url = url;
    await page.reload();
    await expect(card.getByRole("link", { name: "Xem sản phẩm ↗", exact: true })).toHaveCount(0);
    await expect(card.getByRole("link", { name: "Xem nguồn ↗", exact: true })).toHaveAttribute("href", item.evidence_url);
  }
});
