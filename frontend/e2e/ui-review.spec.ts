import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { SearchPipelineResponse, ProductDetail } from "../types/shopping";

const API = "http://127.0.0.1:18000";
test.beforeEach(async ({ page, request }) => {
  expect((await (await request.get(`${API}/api/system/status`)).json()).demo_mode).toBe(true);
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" && ["13000", "18000"].includes(url.port) ? route.continue() : route.abort("blockedbyclient");
  });
});
async function result(page: Page): Promise<SearchPipelineResponse> {
  const analysis = await page.request.post(`${API}/api/requirements/analyze`, {data:{raw_query:"Tai nghe 500 nghìn để học online, mic tốt, pin lâu"}});
  expect(analysis.ok()).toBeTruthy();
  const {session_id} = await analysis.json();
  const search = await page.request.post(`${API}/api/search`,{data:{session_id}});
  expect(search.ok()).toBeTruthy();
  return search.json();
}
async function noPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

for (const width of [375,768,1366,1920]) {
  test(`responsive review at ${width}px: all five routes, keyboard and comparison scrolling`, async ({page},info) => {
    await page.setViewportSize({width,height:900});
    const data = await result(page);
    const comparison = await page.request.post(`${API}/api/comparisons`,{data:{session_id:data.session_id,product_ids:data.recommendations.slice(0,2).map(p => p.product_id)}});
    expect(comparison.ok()).toBeTruthy();
    const compareId = (await comparison.json()).id;
    const paths = ["/",`/results/${data.session_id}`,`/products/${data.recommendations[0].product_id}?sessionId=${data.session_id}`,`/compare/${compareId}`,"/history"];
    for (let i=0;i<paths.length;i++) {
      await page.goto(paths[i]);
      await expect(page.locator('main h1')).toBeVisible();
      if (i===1) await expect(page.getByRole('article')).toHaveCount(3);
      if (i===2) await expect(page.getByRole('region',{name:'Đề xuất của phiên tìm kiếm'})).toBeVisible();
      if (i===3) await expect(page.getByRole('table')).toBeVisible();
      if (i===4) await expect(page.getByRole('link',{name:/Xem lại:/}).first()).toBeVisible();
      await noPageOverflow(page);
      await expect(page.getByRole('banner')).toHaveCount(1);
      await expect(page.getByRole('contentinfo')).toBeVisible();
      await page.screenshot({path:info.outputPath(`${['home','results','detail','compare','history'][i]}-${width}.png`),fullPage:true});
    }
    await page.goto('/');
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link',{name:'Đến nội dung chính'})).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
  });
}

test('prompt chips do not submit; clarification and keyboard search preserve the real API flow', async ({page}) => {
  let analysisCalls=0;
  page.on('request', r => { if(r.url()===`${API}/api/requirements/analyze`) analysisCalls++; });
  await page.goto('/');
  const prompt='TV khoảng 10 triệu để xem phim';
  await page.getByRole('button',{name:prompt}).click();
  await expect(page.getByLabel('Bạn đang tìm sản phẩm gì?')).toHaveValue(prompt);
  expect(analysisCalls).toBe(0);
  await page.getByLabel('Bạn đang tìm sản phẩm gì?').fill('Tôi cần tai nghe 500 nghìn');
  await page.getByLabel('Bạn đang tìm sản phẩm gì?').press('Control+Enter');
  await expect(page.getByRole('region',{name:'Bổ sung nhu cầu'})).toBeVisible();
  const answer='học online, mic tốt, pin lâu';
  await page.getByLabel('Câu trả lời của bạn').fill(answer);
  const response=page.waitForResponse(r => r.url()===`${API}/api/requirements/clarify`);
  await page.getByRole('button',{name:'Tiếp tục với AI →'}).click();
  expect((await response).request().postDataJSON().answer).toBe(answer);
  await expect(page).toHaveURL(/\/results\//);
  await expect(page.getByRole('article').first()).toBeVisible();
});

test('negative feedback preserves selection, payload and success acknowledgement', async ({page}) => {
  const data=await result(page);
  await page.goto(`/results/${data.session_id}`);
  const card=page.getByRole('article').first();
  await card.getByRole('button',{name:'👎 Không phù hợp'}).click();
  await expect(card.getByRole('button',{name:'👎 Không phù hợp'})).toHaveAttribute('aria-pressed','true');
  await card.getByRole('button',{name:'Thông tin chưa đủ',exact:true}).click();
  await card.getByLabel('Ý kiến thêm').fill('Cần thêm bằng chứng về pin.');
  const response=page.waitForResponse(r => r.url()===`${API}/api/feedback` && r.request().method()==='POST');
  await card.getByRole('button',{name:'Gửi phản hồi',exact:true}).click();
  const sent=await response;
  expect(sent.ok()).toBeTruthy();
  expect(sent.request().postDataJSON()).toEqual({session_id:data.session_id,product_id:data.recommendations[0].product_id,is_helpful:false,reason:'Thông tin chưa đủ',comment:'Cần thêm bằng chứng về pin.'});
  await expect(card.getByRole('status')).toContainText('Cảm ơn bạn đã phản hồi');
});

test('loading, empty and error states offer recovery without displaying raw API errors', async ({page},info) => {
  const data=await result(page);
  let release: () => void = () => {};
  const gate=new Promise<void>(resolve => {release=resolve;});
  await page.route(`${API}/api/search/${data.session_id}`,async route => {await gate;await route.fulfill({status:500,json:{detail:'Traceback PRIVATE_INTERNAL_ERROR'}});});
  await page.goto(`/results/${data.session_id}`);
  await expect(page.getByRole('status')).toContainText('Đang tải');
  await page.screenshot({path:info.outputPath('loading.png'),fullPage:true});
  release();
  await expect(page.locator('main').getByRole('alert')).toContainText('Không thể tải kết quả');
  await expect(page.locator('body')).not.toContainText('PRIVATE_INTERNAL_ERROR');
  await page.screenshot({path:info.outputPath('error.png'),fullPage:true});
  await page.unroute(`${API}/api/search/${data.session_id}`);
  await page.route(`${API}/api/search/${data.session_id}`,route => route.fulfill({json:{...data,recommendations:[],total_recommended:0}}));
  await page.getByRole('button',{name:'Thử lại',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Chưa tìm thấy sản phẩm phù hợp.'})).toBeVisible();
  await page.screenshot({path:info.outputPath('empty.png'),fullPage:true});
});

test('detail hero keeps historical price and score separate from newer catalog offers', async ({page}) => {
  const data=await result(page), item=data.recommendations[0];
  const response=await page.request.get(`${API}/api/products/${item.product_id}?session_id=${data.session_id}`);
  expect(response.ok()).toBeTruthy();
  const detail:ProductDetail=await response.json();
  expect(detail.recommendation?.price).toBe(item.price);
  // Deliberately different catalog fixture proves that the hero renders the snapshot.
  detail.offers.forEach(offer => {offer.price=99000000;});
  detail.name='NEW CATALOG IDENTITY';
  detail.image_url='https://catalog.example/new-product.jpg';
  detail.offers.forEach(offer => {offer.merchant='NEW CATALOG MERCHANT';offer.image_url='https://catalog.example/new-product.jpg';});
  await page.route(`${API}/api/products/${item.product_id}?session_id=${data.session_id}`,route => route.fulfill({json:detail}));
  await page.goto(`/products/${item.product_id}?sessionId=${data.session_id}`);
  const hero=page.locator('main > section').first();
  await expect(hero).toContainText(`${item.price!.toLocaleString('vi-VN')}đ`);
  await expect(hero).not.toContainText('99.000.000đ');
  await expect(hero.getByRole('heading',{name:item.name,exact:true})).toBeVisible();
  await expect(hero).toContainText(item.merchant!);
  await expect(hero).toContainText(`${item.score.final_score.toFixed(2)}/100`);
  await expect(hero).not.toContainText('NEW CATALOG');
  await expect(hero.locator('img[src="https://catalog.example/new-product.jpg"]')).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Nơi bán trong catalog'}).locator('..')).toContainText('99.000.000đ');
});

test('comparison missing score and broken image stay unavailable, never zero or in stock', async ({page},info) => {
  const data=await result(page);
  const response=await page.request.post(`${API}/api/comparisons`,{data:{session_id:data.session_id,product_ids:data.recommendations.slice(0,2).map(p=>p.product_id)}});
  expect(response.ok()).toBeTruthy();
  const comparison=await response.json();
  comparison.result.products[0].ai_score=null;
  comparison.result.products[0].confidence=null;
  comparison.result.products[0].image_url='http://127.0.0.1:13000/broken-comparison.jpg';
  comparison.result.products[0].best_offer.availability=null;
  await page.route('**/broken-comparison.jpg',route=>route.fulfill({status:404,body:'missing'}));
  await page.route(`${API}/api/comparisons/${comparison.id}`,route=>route.fulfill({json:comparison}));
  await page.goto(`/compare/${comparison.id}`);
  const card=page.getByRole('article').first();
  await expect(card).toContainText('Chưa có dữ liệu');
  await expect(card).not.toContainText('0.00/100');
  await expect(card).toContainText('Chưa rõ tồn kho');
  await expect(card.getByText('Chưa rõ tồn kho')).not.toHaveClass(/tag-green|tag-red/);
  await expect(card.getByText('Chưa có ảnh sản phẩm',{exact:true})).toBeVisible();
  await expect(card.getByRole('link',{name:'Xem chi tiết'})).toHaveAttribute('href',`/products/${comparison.result.products[0].product_id}?sessionId=${data.session_id}`);
  await page.screenshot({path:info.outputPath('comparison-missing-data.png'),fullPage:true});
});

test('history error can retry into an honest empty state', async ({page},info) => {
  await page.route(`${API}/api/history?limit=50`,route=>route.fulfill({status:500,json:{detail:'PRIVATE_HISTORY_TRACE'}}));
  await page.goto('/history');
  await expect(page.locator('main').getByRole('alert')).toContainText('Không thể tải lịch sử');
  await expect(page.locator('body')).not.toContainText('PRIVATE_HISTORY_TRACE');
  await page.unroute(`${API}/api/history?limit=50`);
  await page.route(`${API}/api/history?limit=50`,route=>route.fulfill({json:{items:[],total:0,limit:50,offset:0}}));
  await page.getByRole('button',{name:'Thử lại',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Bạn chưa có lịch sử tìm kiếm.'})).toBeVisible();
  await expect(page.getByRole('link',{name:'Bắt đầu tìm kiếm',exact:true})).toHaveAttribute('href','/');
  await page.screenshot({path:info.outputPath('history-empty.png'),fullPage:true});
});

test('archived Live TV, motorcycle and phone snapshots render without substituting Demo offers', async ({page},info) => {
  // Read-only replay of the actual previous Live audit; no provider calls and no production DB.
  const audit=JSON.parse(readFileSync('../docs/LIVE_TV_CHECK.json','utf8'));
  const base=await result(page);
  for (const index of [0,2,3]) {
    const saved=audit.scenarios[index];
    const recommendations=saved.recommendations.map((p:Record<string,unknown>,rank:number) => ({...p,product_id:rank+1,rank:rank+1,currency:saved.requirement.currency,specifications:{}}));
    const session_id=`ui-replay-${index}`;
    await page.route(`${API}/api/search/${session_id}`,route => route.fulfill({json:{...base,session_id,requirement:saved.requirement,data_mode:'live',recommendations,total_found:saved.counts.total_found,total_filtered:saved.counts.total_filtered,total_recommended:recommendations.length,warnings:[]}}));
    await page.goto(`/results/${session_id}`);
    await expect(page.getByRole('article')).toHaveCount(recommendations.length);
    await expect(page.getByText('Live Data — dữ liệu đã thu thập',{exact:true})).toBeVisible();
    for (let j=0;j<recommendations.length;j++) {
      const card=page.getByRole('article').nth(j), original=saved.recommendations[j];
      await expect(card.getByRole('heading',{name:original.name,exact:true})).toBeVisible();
      await expect(card).toContainText(`${original.price.toLocaleString('vi-VN')}đ`);
      await expect(card.getByRole('link',{name:'Xem sản phẩm ↗',exact:true})).toHaveAttribute('href',original.product_url);
    }
    if(index===2) await expect(page.getByText('Chưa có ảnh sản phẩm',{exact:true})).toHaveCount(recommendations.length);
    await noPageOverflow(page);
    await page.screenshot({path:info.outputPath(`live-replay-${index}.png`),fullPage:true});
  }
});
