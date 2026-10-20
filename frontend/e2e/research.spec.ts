import { test, expect } from "@playwright/test";

test("Research validation reports the API reason rather than a network error", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Chế độ dữ liệu").selectOption("research");
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("điện thoại dưới 19.95 USD");
  await page.getByRole("button", { name: "Tìm bằng AI" }).click();
  await expect(page.getByText(/MVP Research nhận ngân sách số nguyên/)).toBeVisible();
  await expect(page.getByText(/Chưa thể kết nối để tìm kiếm/)).toHaveCount(0);
});

test("Research historical-price filters work and refresh creates a new snapshot", async ({ page }) => {
  await page.route("**/*", route => ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.goto("/");
  await page.getByLabel("Chế độ dữ liệu").selectOption("research");
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("phụ kiện điện thoại");
  await page.getByRole("button", { name: "Tìm bằng AI" }).click();
  await page.waitForURL(/\/results\//);
  const previous = page.url();
  await expect(page.locator("article.product-card").first()).toBeVisible();
  await page.getByLabel("Giá tối thiểu lịch sử (USD)").fill("1000000");
  await expect(page.getByText("Không có sản phẩm khớp bộ lọc", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Đặt lại bộ lọc", exact: true }).first().click();
  await expect(page.locator("article.product-card").first()).toBeVisible();
  await page.getByRole("combobox", { name: "Sắp xếp", exact: true }).selectOption("price_asc");
  await page.getByRole("button", { name: "Refresh Search", exact: true }).click();
  await page.waitForURL(url => url.pathname.startsWith("/results/") && url.href !== previous);
  await expect(page.getByLabel("Nguồn dữ liệu nghiên cứu").first()).toBeVisible();
  await page.goto(previous);
  await expect(page.locator("article.product-card").first()).toBeVisible();
});

test("Research catalog search, snapshot detail, comparison and history", async ({ page }) => {
  await page.route("**/*", route => {
    const host = new URL(route.request().url()).hostname;
    return ["127.0.0.1", "localhost"].includes(host) ? route.continue() : route.abort();
  });
  await page.goto("/");
  await page.getByLabel("Chế độ dữ liệu").selectOption("research");
  await expect(page.getByLabel("URL sản phẩm trực tiếp (không bắt buộc)")).toHaveCount(0);
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("phụ kiện điện thoại");
  await page.getByRole("button", { name: "Tìm bằng AI" }).click();
  await page.waitForURL(/\/results\//);
  const resultsUrl = page.url();
  await expect(page.getByLabel("Nguồn dữ liệu nghiên cứu").first()).toContainText("không phải giá bán hiện tại");
  await expect(page.getByText("Chưa rõ tồn kho", { exact: true })).toHaveCount(0);
  const cards = page.locator("article.product-card");
  await expect(cards.first()).toBeVisible();
  await cards.nth(0).getByRole("button", { name: "+ So sánh" }).click();
  await cards.nth(1).getByRole("button", { name: "+ So sánh" }).click();
  await page.getByRole("button", { name: /So sánh.*2|So sánh ngay/ }).click();
  await page.waitForURL(/\/compare\//);
  await expect(page.getByLabel("Nguồn dữ liệu nghiên cứu")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Offer, shop và độ mới" })).toHaveCount(0);
  await page.getByRole("link", { name: "Xem chi tiết", exact: true }).first().click();
  await page.waitForURL(/\/products\//);
  await expect(page.getByLabel("Nguồn dữ liệu nghiên cứu")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Nơi bán trong catalog" })).toHaveCount(0);
  await page.goto(resultsUrl);
  await expect(page.getByLabel("Nguồn dữ liệu nghiên cứu").first()).toBeVisible();
  await page.goto("/history");
  await expect(page.getByText("phụ kiện điện thoại", { exact: true }).first()).toBeVisible();
});
