/* Explicit synthetic UI evidence. Use a temporary browser profile and localhost only. */
const {chromium} = require(process.env.INVESTO_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = process.env.INVESTO_BROWSER_OUTPUT || '/private/tmp/u182-browser';
const url = process.env.INVESTO_CALENDAR_PREVIEW || 'http://127.0.0.1:8874/insights/calendar/';

(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({executablePath:process.env.INVESTO_BROWSER_EXECUTABLE, headless:true});
  const evidence={kind:'actual local Chromium renders of explicitly synthetic schedules',browser:browser.version(),cases:[],zoom:'200% equivalent half CSS viewport and DPR2',errors:[]};
  try {
    for (const [name,width,height] of [['mobile',390,844],['desktop',1440,900]]) {
      for (const theme of ['default','slate']) for (const zoom of [1,2]) for (const js of [true,false]) {
        const context=await browser.newContext({viewport:{width:width/zoom,height:height/zoom},deviceScaleFactor:zoom,javaScriptEnabled:js});
        const page=await context.newPage();const errors=[],requests=[];
        page.on('pageerror',e=>errors.push(e.message));
        page.on('request',r=>{if(r.url().includes('/insights/_data/'))requests.push(r.url());});
        await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
        await page.goto(url,{waitUntil:'networkidle'});
        await page.evaluate(theme=>{document.body.dataset.mdColorScheme=theme;},theme);
        await page.evaluate(async()=>{
          document.body.getBoundingClientRect();
          await Promise.all(document.getAnimations().filter(a=>a.effect?.target instanceof Element && a.effect.target.closest('.md-nav')).map(a=>a.finished.catch(()=>{})));
        });
        assert.equal(await page.locator('[data-event]').count(),8);
        assert.equal(await page.locator('[data-event]:visible').count(),js?6:8);
        const overflow=await page.evaluate(()=>({page:document.documentElement.scrollWidth>innerWidth+1,module:document.querySelector('.insights-page').scrollWidth>document.querySelector('.insights-page').clientWidth+1}));
        assert.deepEqual(overflow,{page:false,module:false},`${name}/${theme}/zoom${zoom}/js${js}`);
        assert.deepEqual(errors,[]);
        assert.equal(requests.length,0);
        const wrongClock=await page.locator('.calendar-date').allTextContents();
        assert(wrongClock.some(t=>t.includes('21:30') && t.includes('KST')));
        assert(wrongClock.some(t=>t.includes('2026-10-27 ~ 2026-10-28') && t.includes('시간 미정')));
        assert(!wrongClock.some(t=>t.includes('09:00')));
        const badContrast=await page.evaluate(()=>{
          const rgb=s=>(s.match(/[\d.]+/g)||[]).map(Number);
          const lum=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((v,x,i)=>v+x*[.2126,.7152,.0722][i],0);
          return [...document.querySelectorAll('.calendar-event h3,.calendar-date,.calendar-source,.calendar-filters button,.md-sidebar--primary .md-nav__link')].filter(e=>{
            const r=e.getBoundingClientRect();return r.width&&r.height&&r.left>=0&&r.right<=innerWidth+1&&getComputedStyle(e).visibility!=='hidden';
          }).flatMap(e=>{
            const fg=rgb(getComputedStyle(e).color);let a=e,bg=[];
            while(a){bg=rgb(getComputedStyle(a).backgroundColor);if(bg.length===3||bg[3]>0)break;a=a.parentElement;}
            if(bg.length<3)return [];
            const f=lum(fg),b=lum(bg),ratio=(Math.max(f,b)+.05)/(Math.min(f,b)+.05);
            return ratio<4.5?[{text:e.textContent.trim().slice(0,20),ratio}]:[];
          });
        });
        assert.deepEqual(badContrast,[],`${name}/${theme} text contrast`);
        if(js) {
          const thirty=page.locator('[data-days="30"]');
          await thirty.focus();await page.keyboard.press('Enter');
          assert.equal(await page.locator('[data-event]:visible').count(),8);
          await page.locator('[data-category-filter="economic_release"]').focus();await page.keyboard.press('Enter');
          assert.equal(await page.locator('[data-event]:visible').count(),3);
          assert.equal(await page.locator('[data-category-filter="economic_release"]').getAttribute('aria-pressed'),'true');
          await page.locator('[data-category-filter="treasury_auction"]').click();
          assert.equal(await page.locator('[data-event]:visible').count(),1);
          await page.locator('[data-category-filter="all"]').click();
          await page.locator('[data-days="7"]').click();
          assert.equal(await page.locator('[data-event]:visible').count(),6);
          assert.equal(requests.length,0);
        } else {
          assert.equal(await page.locator('[data-calendar-filters]:visible').count(),0);
          assert.equal(await page.locator('[data-testid="calendar-thirty-anchor"]').getAttribute('href'),'#calendar-events');
        }
        if(zoom===1 && js) {
          await page.screenshot({path:path.join(output,`${name}-${theme}.png`)});
          if(name==='mobile' && theme==='default') await page.screenshot({path:path.join(output,'mobile-full.png'),fullPage:true});
        }
        evidence.cases.push({name,theme,zoom,js,events:8,initial_visible:js?6:8,overflow,page_errors:errors,data_requests:requests.length,text_contrast:'>=4.5:1',keyboard_filters:js?'pass':'noJS30 list'});
        await context.close();
      }
    }
    const context=await browser.newContext({viewport:{width:1440,height:900}});
    const page=await context.newPage();
    await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
    await page.goto(url,{waitUntil:'networkidle'});
    await page.locator('[data-days="30"]').click();
    await page.goto(new URL('../',url).href,{waitUntil:'networkidle'});
    await page.locator('.insights-hub-card[href="calendar/"]').click();
    await page.locator('[data-event]').first().waitFor();
    assert.equal(await page.locator('[data-event]:visible').count(),6);
    const toggle=page.locator('label.md-header__button[for^="__palette_"]:visible').first();
    const before=await page.locator('body').getAttribute('data-md-color-scheme');
    await toggle.click();
    assert.notEqual(await page.locator('body').getAttribute('data-md-color-scheme'),before);
    assert.equal((await page.request.get(new URL('../../sectors/',url).href)).status(),200);
    await page.locator('[data-testid="calendar-thirty-anchor"]').click();
    assert.equal(await page.locator('[data-event]:visible').count(),8);
    evidence.hub_reentry='pass: filters reset once and respond';
    evidence.theme_toggle='pass';evidence.original_sectors_url='HTTP200';evidence.thirty_anchor='pass';
    await context.close();evidence.status='pass';
  } catch(error) {
    evidence.status='fail';evidence.errors.push(error.message);throw error;
  } finally {
    fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');
    await browser.close();
    console.log(JSON.stringify({status:evidence.status,cases:evidence.cases.length,errors:evidence.errors}));
  }
})();
