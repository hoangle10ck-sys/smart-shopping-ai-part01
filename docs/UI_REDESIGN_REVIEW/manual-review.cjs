// Run from frontend: node ../docs/UI_REDESIGN_REVIEW/manual-review.cjs
const localRequire = require('node:module').createRequire(require('node:path').resolve('package.json'));
const { chromium, expect } = localRequire('@playwright/test');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const out = path.resolve('../docs/UI_REDESIGN_REVIEW');
fs.mkdirSync(out, { recursive: true });
const API = 'http://127.0.0.1:18000';
const WEB = 'http://127.0.0.1:13000';
const audit = JSON.parse(fs.readFileSync('../docs/LIVE_TV_CHECK.json', 'utf8'));
const imageURLs = new Set(audit.scenarios.flatMap(s => s.recommendations.map(r => r.image_url).filter(Boolean)));
const summary = { method: 'Agent browser navigation and screenshot review after final automated validation', viewports: [], flows: [], liveImages: [], externalRequests: [] };
const backend = spawn('../backend/.venv/Scripts/python.exe', ['-B', '-X', 'utf8', '../backend/scripts/run_e2e_backend.py'], { windowsHide: true, stdio: 'ignore' });
const frontend = spawn(process.execPath, [localRequire.resolve('next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '13000'], { windowsHide: true, stdio: 'ignore', env: {...process.env, NEXT_TELEMETRY_DISABLED:'1'} });
async function ready(url) {
  for(let i=0;i<60;i++) {
    try { if((await fetch(url)).ok) return; } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error('Local server unavailable: '+url);
}
let browser;
(async () => {
  try {
    await Promise.all([ready(API+'/api/system/status'),ready(WEB)]);
    expect((await (await fetch(API+'/api/system/status')).json()).demo_mode).toBe(true);
    browser=await chromium.launch({channel:'msedge',headless:true});
    const context=await browser.newContext({viewport:{width:1366,height:900},serviceWorkers:'block'});
    const page=await context.newPage();
    await page.route('**/*',route=>{
      const req=route.request(),url=new URL(req.url());
      if(url.hostname==='127.0.0.1' && ['13000','18000'].includes(url.port)) return route.continue();
      if(req.resourceType()==='image' && imageURLs.has(req.url())) {summary.externalRequests.push(req.url());return route.continue();}
      return route.abort('blockedbyclient');
    });
    async function capture(name) {
      await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
      await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    }
    await page.goto(WEB);
    await page.getByRole('button',{name:'TV khoảng 10 triệu để xem phim'}).click();
    await expect(page.getByLabel('Bạn đang tìm sản phẩm gì?')).toHaveValue('TV khoảng 10 triệu để xem phim');
    await page.getByLabel('Bạn đang tìm sản phẩm gì?').fill('Tôi cần tai nghe 500 nghìn');
    await page.getByLabel('Bạn đang tìm sản phẩm gì?').press('Control+Enter');
    await expect(page.getByRole('region',{name:'Bổ sung nhu cầu'})).toBeVisible();
    await capture('clarification');
    await page.getByLabel('Câu trả lời của bạn').fill('học online, mic tốt, pin lâu');
    let release; const gate=new Promise(r=>release=r);
    await page.route(API+'/api/search',async route=>{await gate;return route.continue();});
    await page.getByRole('button',{name:'Tiếp tục với AI →'}).click();
    await expect(page.getByRole('status')).toContainText('Đang tìm kiếm');
    await capture('search-loading');
    release();
    await page.waitForURL('**/results/**');
    const sessionId=page.url().split('/').pop();
    const data=await (await page.request.get(API+'/api/search/'+sessionId)).json();
    const resultsPath='/results/'+sessionId;
    const cards=page.getByRole('article');
    await expect(cards).toHaveCount(3);
    summary.flows.push('home prompt chip, Ctrl+Enter, clarification, search loading, results');
    await page.getByRole('combobox',{name:'Sắp xếp',exact:true}).selectOption('price_asc');
    const low=Math.min(...data.recommendations.map(p=>p.price));
    await page.getByRole('spinbutton',{name:'Giá tối đa',exact:true}).fill(String(low));
    await expect(cards).toHaveCount(data.recommendations.filter(p=>p.price<=low).length);
    await page.getByRole('button',{name:'Đặt lại bộ lọc'}).click();
    await expect(cards).toHaveCount(3);
    await cards.first().getByText('Mức đáp ứng yêu cầu',{exact:true}).click();
    await cards.first().getByText('Nguồn và bằng chứng',{exact:true}).click();
    await capture('matching-evidence');
    await cards.first().getByRole('button',{name:'👍 Hữu ích'}).click();
    await expect(cards.first().getByRole('status')).toContainText('Cảm ơn');
    await capture('feedback');
    await cards.first().getByRole('link',{name:'Xem chi tiết',exact:true}).click();
    await expect(page.getByRole('region',{name:'Đề xuất của phiên tìm kiếm'})).toBeVisible();
    await page.goto(WEB+resultsPath);
    await cards.nth(0).getByRole('button',{name:'+ So sánh',exact:true}).click();
    await cards.nth(1).getByRole('button',{name:'+ So sánh',exact:true}).click();
    await page.getByRole('button',{name:'So sánh ngay (2)',exact:true}).click();
    await page.waitForURL('**/compare/**');
    const comparePath=new URL(page.url()).pathname;
    await expect(page.getByRole('table')).toBeVisible();
    await page.getByRole('link',{name:'Lịch sử',exact:true}).click();
    await page.getByRole('link',{name:/Xem lại:/}).first().click();
    await expect(cards).toHaveCount(3);
    summary.flows.push('filter, sort, reset, matching/evidence disclosure, positive feedback, detail, compare, history reopen');
    const routes={home:'/',results:resultsPath,detail:`/products/${data.recommendations[0].product_id}?sessionId=${sessionId}`,compare:comparePath,history:'/history'};
    for(const width of [375,768,1366,1920]) {
      await page.setViewportSize({width,height:900});
      for(const [name,url] of Object.entries(routes)) {
        await page.goto(WEB+url);
        await expect(page.locator('main h1')).toBeVisible();
        if(name==='results') await expect(cards).toHaveCount(3);
        if(name==='detail') await expect(page.getByRole('region',{name:'Đề xuất của phiên tìm kiếm'})).toBeVisible();
        if(name==='compare') await expect(page.getByRole('table')).toBeVisible();
        if(name==='history') await expect(page.getByRole('link',{name:/Xem lại:/}).first()).toBeVisible();
        await capture(name+'-'+width);
      }
      summary.viewports.push({width,routes:5,documentOverflow:false});
    }
    await page.setViewportSize({width:1366,height:900});
    for(const index of [0,2,3]) {
      const saved=audit.scenarios[index],id='manual-replay-'+index;
      const recs=saved.recommendations.map((p,i)=>({...p,product_id:i+1,rank:i+1,currency:saved.requirement.currency,specifications:{}}));
      await page.route(API+'/api/search/'+id,route=>route.fulfill({json:{...data,session_id:id,requirement:saved.requirement,data_mode:'live',recommendations:recs,total_found:saved.counts.total_found,total_filtered:saved.counts.total_filtered,total_recommended:recs.length,warnings:[]}}));
      await page.goto(WEB+'/results/'+id);
      await expect(cards).toHaveCount(recs.length);
      for(let i=0;i<recs.length;i++) {
        const card=cards.nth(i);
        await card.scrollIntoViewIfNeeded();
        await expect(card.getByRole('heading',{name:recs[i].name,exact:true})).toBeVisible();
        const img=card.locator('img');
        if(await img.count()) await img.evaluate(img=>Promise.race([new Promise(r=>{if(img.complete)r();else{img.addEventListener('load',r,{once:true});img.addEventListener('error',r,{once:true});}}),new Promise(r=>setTimeout(r,8000))]));
        const loaded=await img.count() ? await img.evaluate(img=>img.complete && img.naturalWidth>0) : false;
        summary.liveImages.push({scenario:index,name:recs[i].name,url:recs[i].image_url,loaded});
      }
      await capture('live-replay-'+index);
      await page.setViewportSize({width:375,height:900});
      await capture('live-replay-'+index+'-375');
      await page.setViewportSize({width:1366,height:900});
    }
    summary.flows.push('archived real Live motorcycle variants, TV null image, phone flexible window, unknown matches; desktop and mobile');
    await page.route(API+'/api/search/'+sessionId,route=>route.fulfill({status:500,json:{detail:'PRIVATE_TRACE'}}));
    await page.goto(WEB+resultsPath);
    await expect(page.locator('main').getByRole('alert')).toContainText('Không thể tải kết quả');
    await expect(page.locator('main')).not.toContainText('PRIVATE_TRACE');
    await capture('error');
    await page.unroute(API+'/api/search/'+sessionId);
    await page.route(API+'/api/search/'+sessionId,route=>route.fulfill({json:{...data,recommendations:[],total_recommended:0}}));
    await page.getByRole('button',{name:'Thử lại',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Chưa tìm thấy sản phẩm phù hợp.'})).toBeVisible();
    await capture('empty');
    summary.flows.push('server error without trace, retry, empty results');
    fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(summary,null,2));
    console.log(JSON.stringify(summary,null,2));
  } finally {
    if(browser) await browser.close();
    frontend.kill();backend.kill();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
