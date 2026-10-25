/* Local synthetic fixture QA; no user profile or production browser is used. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.INVESTO_PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.INVESTO_PREVIEW_URL || 'http://127.0.0.1:8873/insights/macro/';
assert.equal(new URL(url).hostname, '127.0.0.1');
const output = process.env.INVESTO_QA_OUTPUT || '/private/tmp/u181-browser';
fs.mkdirSync(output, {recursive:true});
(async () => {
 const browser = await chromium.launch({headless:true, executablePath:process.env.INVESTO_BROWSER_EXECUTABLE});
 const evidence = {kind:'actual local Chromium renders of explicitly synthetic data',cases:[], errors:[], browser:browser.version(), zoom:'200% equivalent CSS viewport divided by two and DPR2'};
 try {
  for (const [name,width,height] of [['mobile',390,844],['desktop',1440,900]]) {
   for (const theme of ['default','slate']) for (const zoom of [1,2]) for (const js of [true,false]) {
    if(process.argv.includes('--inspect-colors') && !(name==='desktop' && theme==='slate' && zoom===1 && js)) continue;
    const context = await browser.newContext({viewport:{width:width/zoom,height:height/zoom},deviceScaleFactor:zoom,javaScriptEnabled:js});
    const page = await context.newPage(); const errors=[]; const requests=[];
    page.on('pageerror', error=>errors.push(error.message));
    page.on('request', request=>{if(request.url().includes('/insights/_data/'))requests.push(request.url());});
    await context.route('**/*', route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
    await page.goto(url,{waitUntil:'networkidle'});
    await page.evaluate(theme=>{document.body.dataset.mdColorScheme=theme;},theme);
    await page.evaluate(async()=>{
      document.body.getBoundingClientRect();
      const transitions=document.getAnimations().filter(a=>a.effect?.target instanceof Element && a.effect.target.closest('.md-nav'));
      await Promise.all(transitions.map(a=>a.finished.catch(()=>{})));
    });
    if(process.argv.includes('--inspect-colors')) {
      console.log(JSON.stringify(await page.evaluate(()=>[document.body,document.querySelector('.insights-page'),...document.querySelectorAll('.md-sidebar--primary .md-nav__link')].slice(0,8).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.trim().slice(0,25),color:getComputedStyle(e).color,ink:getComputedStyle(e).getPropertyValue('--investo-ink'),accent:getComputedStyle(e).getPropertyValue('--investo-accent'),opacity:getComputedStyle(e).opacity,parent:e.parentElement.tagName}))),null,2));
      return;
    }
    assert.equal(await page.locator('[data-metric]').count(),13);
    const overflow = await page.evaluate(()=>({page:document.documentElement.scrollWidth>innerWidth+1,insights:document.querySelector('.insights-page').scrollWidth>document.querySelector('.insights-page').clientWidth+1}));
    if (overflow.page || overflow.insights) {
      console.log(JSON.stringify(await page.evaluate(()=>{const root=document.querySelector('.insights-page'),r=root.getBoundingClientRect();return {root:{x:r.x,width:r.width,client:root.clientWidth,scroll:root.scrollWidth},wide:[...root.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>r.right+1).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,scroll:e.scrollWidth,client:e.clientWidth}))};})));
      await page.screenshot({path:path.join(output,'overflow.png'),fullPage:true});
    }
    assert.deepEqual(overflow,{page:false,insights:false},`${name} ${theme} zoom${zoom} js${js} overflow`);
    assert.equal(requests.length,0,'history must not load before interaction');
    assert.deepEqual(errors,[]);
    const contrastFailures=await page.evaluate(()=>{
      const rgb=s=>(s.match(/[\d.]+/g)||[]).map(Number);
      const luminance=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((v,x,i)=>v+x*[.2126,.7152,.0722][i],0);
      return [...document.querySelectorAll('.md-sidebar--primary .md-nav__link,.insights-card h3,.insights-date')].filter(e=>{
        const r=e.getBoundingClientRect();return r.width&&r.height&&r.left>=0&&r.right<=innerWidth+1&&getComputedStyle(e).visibility!=='hidden';
      }).flatMap(e=>{
        const fg=rgb(getComputedStyle(e).color);let a=e,bg=[];
        while(a){bg=rgb(getComputedStyle(a).backgroundColor);if(bg.length===3||bg[3]>0)break;a=a.parentElement;}
        if(bg.length<3)return [];
        const f=luminance(fg),b=luminance(bg),ratio=(Math.max(f,b)+.05)/(Math.min(f,b)+.05);
        return ratio<4.5?[{text:e.textContent.trim().slice(0,20),ratio,fg,bg,bgTag:a?.tagName,bgClass:a?.className,ownBg:getComputedStyle(e).backgroundColor}]:[];
      });
    });
    assert.deepEqual(contrastFailures,[],`${name} ${theme} text contrast`);
    if (zoom===1 && js) { await page.screenshot({path:path.join(output,`${name}-${theme}.png`),fullPage:false}); if(name==='mobile' && theme==='default') await page.screenshot({path:path.join(output,'mobile-full.png'),fullPage:true}); }
    evidence.cases.push({name,theme,zoom,js,overflow,card_count:13,history_requests_before_interaction:0,page_errors:errors,text_contrast:'at least4.5:1'});
    await context.close();
   }
  }
  const context = await browser.newContext({viewport:{width:1440,height:900}});
  const page = await context.newPage(); const requests=[];
  page.on('request',request=>{if(request.url().includes('/insights/_data/'))requests.push(request.url());});
  await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  await page.goto(url,{waitUntil:'networkidle'});
  const button=page.locator('[data-load-history]'); await button.focus();
  await page.keyboard.press('Enter');
  await page.locator('[data-history-content] details').first().waitFor();
  assert.equal(requests.length,2); assert.equal(await page.locator('[data-history-content] table tbody tr').count(),6);
  const summary=page.locator('[data-history-content] summary').first(); await summary.focus(); await page.keyboard.press('Enter');
  assert.equal(await page.locator('[data-history-content] details').first().getAttribute('open'),'');
  evidence.lazy_history={requests:2,table_rows:6,keyboard_enter:true};
  await page.locator('label[for="__palette_1"]').click();
  await page.waitForFunction(()=>document.body.dataset.mdColorScheme==='slate');
  await page.locator('label[for="__palette_0"]').click();
  await page.waitForFunction(()=>document.body.dataset.mdColorScheme==='default');
  evidence.theme_toggle='pass';
  await summary.scrollIntoViewIfNeeded(); await page.screenshot({path:path.join(output,'history-open.png'),fullPage:false});
  await page.locator('.insights-method a[href="../"]').click();
  await page.waitForURL('**/insights/');
  await page.locator('.insights-hub-card').filter({hasText:'매크로 환경'}).click();
  await page.locator('[data-load-history]').waitFor({state:'visible'});
  await page.locator('[data-load-history]').click();
  await page.locator('[data-history-content] table').waitFor({state:'attached'});
  const sectors=await context.request.get(new URL('../../sectors/',url).href);
  assert.equal(sectors.status(),200); evidence.hub_reentry='pass'; evidence.original_sectors_url='pass';
  await context.close();
  for (const kind of ['hash_mismatch','snapshot_mismatch']) {
   const ctx=await browser.newContext(); const p=await ctx.newPage();
   await ctx.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
   if(kind==='hash_mismatch') await ctx.route('**/insights/_data/macro/history.json',route=>route.fulfill({status:200,contentType:'application/json',body:'{"altered":true}'}));
   else await ctx.route('**/insights/_data/manifest.json',route=>route.fulfill({status:200,contentType:'application/json',body:'{"modules":[{"module":"macro","snapshot_id":"changed","current_hash":"changed"}]}'}));
   await p.goto(url,{waitUntil:'networkidle'});await p.locator('[data-load-history]').click();
   await p.waitForFunction(()=>/확인하지 못|새 자료/.test(document.querySelector('[data-history-status]').textContent));
   assert.equal(await p.locator('[data-history-content] table').count(),0);
   assert.equal(await p.locator('[data-metric]').count(),13);
   evidence[kind]='blocked; current cards preserved'; await ctx.close();
  }
  evidence.status='pass'; fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');
  console.log(JSON.stringify({status:'pass',renders:evidence.cases.length,lazy_history:evidence.lazy_history}));
 } catch(error) { evidence.status='failed'; evidence.errors.push(String(error)); fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n'); throw error; }
 finally { await browser.close(); }
})();
