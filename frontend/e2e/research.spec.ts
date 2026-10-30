import { test, expect } from "@playwright/test";
import { installQaImageFixtures } from "./image-fixtures";

test("Unified validation reports the API reason rather than a network error", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("điện thoại dưới 19.95 USD");
  await page.getByRole("button", { name: "Tìm và đề xuất" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByText(/Chưa thể kết nối để tìm kiếm/)).toHaveCount(0);
});

test("Unified current offers can be filtered and the saved session can be refreshed", async ({ page }) => {
  await page.route("**/*", route => ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await installQaImageFixtures(page);
  await page.goto("/");
  const query = "Tai nghe 500 nghìn để học online, mic tốt, pin lâu";
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill(query);
  await page.getByRole("button", { name: "Tìm và đề xuất" }).click();
  await page.waitForURL(/\/results\//);
  const previous = page.url();
  await expect(page.locator("article.product-card").first()).toBeVisible();
  await expect(page.locator("article.product-card")).toHaveCount(3);
  await page.getByLabel("Giá tối đa").fill("100000");
  await expect(page.getByText("Không có sản phẩm khớp bộ lọc", { exact: true })).toBeVisible();
  await page.getByRole("region", { name: "Lọc và sắp xếp kết quả" })
    .getByRole("button", { name: "Đặt lại bộ lọc", exact: true }).click();
  await page.getByRole("combobox", { name: "Sắp xếp", exact: true }).selectOption("price_asc");
  const refresh = page.waitForResponse((response) => response.url().endsWith("/api/search") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Tìm lại sản phẩm", exact: true }).click();
  const refreshed = await refresh;
  expect(refreshed.ok()).toBeTruthy();
  expect(refreshed.request().postDataJSON().refresh).toBe(true);
  await expect(page).toHaveURL(previous);
  await expect(page.getByText("Đề xuất theo nhu cầu", { exact: true })).toBeVisible();
  await page.goto(previous);
  await expect(page.locator("article.product-card").first()).toBeVisible();
});

test("Unified catalog search, snapshot detail, comparison and history", async ({ page }) => {
  await page.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    return ["127.0.0.1", "localhost"].includes(host) ? route.continue() : route.abort();
  });
  await installQaImageFixtures(page);
  await page.goto("/");
  await expect(page.getByLabel("URL sản phẩm trực tiếp (không bắt buộc)")).toHaveCount(0);
  const query = "Tai nghe 500 nghìn để học online, mic tốt, pin lâu";
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill(query);
  await page.getByRole("button", { name: "Tìm và đề xuất" }).click();
  await page.waitForURL(/\/results\//);
  const resultsUrl = page.url();
  await expect(page.getByText("Chưa rõ tồn kho", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Đề xuất theo nhu cầu", { exact: true })).toBeVisible();
  const cards = page.locator("article.product-card");
  await expect(cards.first()).toBeVisible();
  await cards.nth(0).getByRole("button", { name: "+ So sánh" }).click();
  await cards.nth(1).getByRole("button", { name: "+ So sánh" }).click();
  await page.getByRole("button", { name: /So sánh.*2|So sánh ngay/ }).click();
  await page.waitForURL(/\/compare\//);
  await expect(page.getByRole("heading", { name: "So sánh cấu hình sản phẩm" })).toBeVisible();
  await expect(page.locator("main")).not.toContainText(/\b(FRESH|STALE|UNKNOWN)\b|Kiểm tra lần cuối/);
  await page.getByRole("link", { name: "Xem chi tiết", exact: true }).first().click();
  await page.waitForURL(/\/products\//);
  await expect(page.getByRole("heading", { name: "Nơi bán trong catalog" })).toBeVisible();
  await page.goto(resultsUrl);
  await expect(page.getByText("Đề xuất theo nhu cầu", { exact: true })).toBeVisible();
  await page.goto("/history");
  await expect(page.getByText(query, { exact: true }).first()).toBeVisible();
});
