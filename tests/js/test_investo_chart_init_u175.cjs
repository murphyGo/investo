"use strict";
const test = require('node:test');
const assert = require('node:assert/strict');
const {harness}=require('./chart_harness.cjs');

for(const prefix of ['/investo','/demo','']) {
  for(const suffix of ['2026-10-08/','2026-10-08/index.html','2026-10-08.html','2026-10-08.md']) {
    test('sibling URL '+prefix+'/'+suffix,async()=>{
      const base='https://example.test'+prefix+'/archive/us-equity/2026/10/';
      const h=harness({url:base+suffix+'?edition=1#chart',src:'2026-10-08.assets/charts/us-equity-gspc.json?x=1#bars'});
      assert.equal(h.requests.length,0);await h.toggle();
      assert.equal(h.requests[0].url,base+'2026-10-08.assets/charts/us-equity-gspc.json?x=1#bars');
      assert.equal(h.requests[0].options.credentials,'same-origin');
    });
  }
}

for(const src of ['../2026-10-08.assets/charts/x.json','/demo/archive/x.json','https://example.test/archive/x.json','other.assets/charts/x.json','nested/history.json']) {
  test('normal URL semantics '+src,async()=>{
    const url='https://example.test/demo/archive/2026-10-08/';
    const h=harness({url,src});await h.toggle();assert.equal(h.requests[0].url,new URL(src,url).href);
  });
}
test('stem mismatch is not guessed',async()=>{const url='https://example.test/demo/archive/other/';const h=harness({url});await h.toggle();assert.equal(h.requests[0].url,new URL('2026-10-08.assets/charts/us-equity-gspc.json',url).href);});

test('lazy initialisation, reopen and themes never refetch or recreate',async()=>{
  const h=harness({body:'slate'});assert.equal(h.requests.length,0);h.scheme(h.body,'default');assert.equal(h.requests.length,0);
  await h.toggle();assert.equal(h.charts[0].initial.layout.textColor,'#212121');
  await h.toggle(0,false);await h.toggle();h.scheme(h.body,'slate');
  assert.equal(h.charts[0].options.at(-1).layout.textColor,'#d0d0d0');h.scheme(h.body,'default');
  assert.equal(h.charts[0].options.at(-1).layout.textColor,'#212121');
  assert.equal(h.requests.length,1);assert.equal(h.charts.length,1);
});
test('body priority and live HTML fallback including attr add/remove',async()=>{
  const h=harness({body:null,html:'slate'});await h.toggle();assert.equal(h.charts[0].initial.layout.textColor,'#d0d0d0');
  h.scheme(h.html,'default');assert.equal(h.charts[0].options.at(-1).layout.textColor,'#212121');
  h.scheme(h.html,'slate');assert.equal(h.charts[0].options.at(-1).layout.textColor,'#d0d0d0');
  h.scheme(h.body,'default');h.scheme(h.html,'default');h.scheme(h.html,'slate');
  assert.equal(h.charts[0].options.at(-1).layout.textColor,'#212121');
  h.scheme(h.body,null);assert.equal(h.charts[0].options.at(-1).layout.textColor,'#d0d0d0');
  assert.equal(h.requests.length,1);assert.equal(h.charts.length,1);
});
test('initial body slate wins over html default',async()=>{const h=harness({body:'slate',html:'default'});await h.toggle();assert.equal(h.charts[0].initial.layout.textColor,'#d0d0d0');});
test('theme changes during loading apply to initial chart',async()=>{
  let release;const h=harness({fetcher:()=>new Promise(resolve=>{release=resolve;})});await h.toggle();h.scheme(h.body,'slate');
  release({ok:true,json:async()=>({history:[{t:'2026-10-08',o:1,h:2,l:1,c:2}]})});await h.flush();
  assert.equal(h.charts[0].initial.layout.textColor,'#d0d0d0');assert.equal(h.requests.length,1);
});
for(const failure of ['http','json','empty','invalid','network']) {
  test('failure isolation '+failure,async()=>{
    const h=harness({count:2,fetcher:async (url,n)=>{
      if(n===2)return {ok:true,json:async()=>({history:[{t:'2026-10-08',o:1,h:2,l:1,c:2}]})};
      if(failure==='network')throw new Error('offline');
      return {ok:failure!=='http',json:async()=>{if(failure==='json')throw new Error('json');return {history:failure==='empty'?[]:[{t:'bad',o:0,h:0,l:0,c:0}]};}};
    }});
    const broken=await h.toggle();assert.ok(broken.children[1].textContent.includes('차트 데이터를 불러오지 못했습니다.'));
    await h.toggle(1);assert.equal(h.charts.length,1);await h.toggle(0,false);await h.toggle(0);assert.equal(h.requests.length,2);
  });
}
test('missing-src legacy fetches nothing and remains hidden',async()=>{const h=harness({src:null});assert.equal(h.divs[0].style.display,'none');assert.equal(h.requests.length,0);});
test('five-card cap is preserved',async()=>{const h=harness({count:6});assert.ok(h.divs[4].replacement);assert.equal(h.divs[5].replacement,undefined);assert.equal(h.requests.length,0);});
