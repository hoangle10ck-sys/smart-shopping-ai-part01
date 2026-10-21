import { test, expect } from "@playwright/test";

const API = "http://127.0.0.1:18000";

test("Home submits one automatic unified search without requiring source or mode selection", async ({ page }) => {
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return ["127.0.0.1", "localhost"].includes(url.hostname) ? route.continue() : route.abort("blockedbyclient");
  });
  await page.goto("/");
  await expect(page.getByLabel("Chế độ dữ liệu")).toHaveCount(0);
  await expect(page.getByLabel("Nguồn sàn hỗ trợ")).toHaveCount(0);

  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("Tai nghe 500 nghìn để học online, mic tốt, pin lâu");
  const request = page.waitForRequest((req) => req.url() === `${API}/api/search` && req.method() === "POST");
  await page.getByRole("button", { name: /Tìm bằng AI/ }).click();
  const search = await request;
  expect(search.postDataJSON().search_scope).toBeUndefined();
  await page.waitForURL(/\/results\//);
});

test("a short product name such as Máy tính can be submitted without clarification", async ({ page }) => {
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return ["127.0.0.1", "localhost"].includes(url.hostname) ? route.continue() : route.abort("blockedbyclient");
  });
  await page.goto("/");
  await page.getByLabel("Bạn đang tìm sản phẩm gì?").fill("Máy tính");
  const analysis = page.waitForResponse((response) => response.url().endsWith("/api/requirements/analyze"));
  const search = page.waitForRequest((request) => request.url() === `${API}/api/search` && request.method() === "POST");
  await page.getByRole("button", { name: /Tìm và đề xuất/ }).click();
  expect((await analysis).request().postDataJSON().raw_query).toBe("Máy tính");
  await search;
  await expect(page.getByRole("region", { name: "Bổ sung nhu cầu" })).toHaveCount(0);
});