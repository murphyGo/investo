"use strict";
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../site_docs/assets/investo-chart-init.js'),'utf8');

class Element {
  constructor(tag, attrs={}) {this.tag=tag;this.attrs={...attrs};this.children=[];this.listeners={};this.style={};this.isConnected=true;this.id='';}
  getAttribute(name) {return this.attrs[name] ?? null;}
  setAttribute(name,value) {this.attrs[name]=value;}
  appendChild(child) {this.children.push(child);}
  replaceWith(element) {this.replacement=element;}
  addEventListener(event,callback) {this.listeners[event]=callback;}
  set textContent(value) {this.text=value;this.children=[];}
  get textContent() {return this.text || this.children.map(c=>c.textContent).join('');}
}

function harness({url='https://example.test/investo/archive/us-equity/2026/10/2026-10-08/',src='2026-10-08.assets/charts/us-equity-gspc.json',body='default',html=null,fetcher=null,count=1}={}) {
  const divs=Array.from({length:count},()=>new Element('div',{'data-history-src':src,'data-ticker':'^GSPC','data-label':'S&P 500','data-close':'6710.12','data-pct':'-1.2'}));
  const bodyElement=new Element('body',body===null?{}:{'data-md-color-scheme':body});
  const htmlElement=new Element('html',html===null?{}:{'data-md-color-scheme':html});
  const document={body:bodyElement,documentElement:htmlElement,readyState:'complete',querySelectorAll:()=>divs,createElement:tag=>new Element(tag)};
  const requests=[],charts=[],observers=[];
  const history=[{t:'2026-10-07',o:100,h:103,l:99,c:102},{t:'2026-10-08',o:102,h:104,l:101,c:103}];
  class Observer {constructor(callback) {this.callback=callback;this.owners=[];observers.push(this);}observe(owner) {this.owners.push(owner);}}
  const LightweightCharts={LineStyle:{Dashed:2,Dotted:1},createChart(container,options) {
    const series={options:[],setData(data){this.data=data;},applyOptions(o){this.options.push(o);},createPriceLine(){}};
    const chart={initial:options,options:[],series,addCandlestickSeries:()=>series,applyOptions(o){this.options.push(o);},timeScale:()=>({fitContent(){}})};
    charts.push(chart);return chart;
  }};
  const context=vm.createContext({document,window:{location:{href:url},LightweightCharts,requestAnimationFrame:callback=>callback()},MutationObserver:Observer,URL,console:{log(){},warn(){}},fetch:async (target,options)=>{
    requests.push({url:target,options});return fetcher ? fetcher(target,requests.length) : {ok:true,json:async()=>({history})};
  }});
  vm.runInContext(source,context,{filename:'investo-chart-init.js'});
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  const toggle=async (index=0,open=true)=>{const details=divs[index].replacement;details.open=open;details.listeners.toggle();await flush();return details;};
  const scheme=(owner,value)=>{if(value===null)delete owner.attrs['data-md-color-scheme'];else owner.setAttribute('data-md-color-scheme',value);observers.filter(o=>o.owners.includes(owner)).forEach(o=>o.callback());};
  return {divs,requests,charts,observers,toggle,scheme,body:bodyElement,html:htmlElement,flush};
}


module.exports={harness};
