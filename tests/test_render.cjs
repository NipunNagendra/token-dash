/* Execute embedded renderers with a tiny DOM/Plotly adapter, not a browser.
   Checks missing IDs, JS exceptions, emitted non-finite values and chart shapes. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('site/index.html','utf8'),code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function run(transform){const nodes=new Map(),charts=[];
 class Element{constructor(id){this.id=id;this.content='';this.classList={toggle(){},add(){},remove(){}}}set innerHTML(v){this.content=v;for(const m of v.matchAll(/\bid="([^"]+)"/g))if(!nodes.has(m[1]))nodes.set(m[1],new Element(m[1]))}get innerHTML(){return this.content}querySelectorAll(){return []}scrollIntoView(){}}
 for(const id of ['nav','main'])nodes.set(id,new Element(id));
 const chart=(id,tr)=>{assert(nodes.has(id),'Chart target '+id);for(const t of tr){if(t.x&&t.y)assert.equal(t.x.length,t.y.length,id+' lengths');if(t.y)assert(t.y.every(v=>v==null||Number.isFinite(v)),id+' nonfinite')}charts.push(id)};
 const context={console,Date,Set,Map,Number,Math,JSON,Array,Object,String,RegExp,Intl,location:{hash:''},localStorage:{setItem(){}},requestAnimationFrame:f=>f(),ResizeObserver:class{observe(){}},document:{getElementById:id=>{assert(nodes.has(id),'Missing ID '+id);return nodes.get(id)},querySelectorAll:()=>[]},window:{addEventListener(){},print(){}},Plotly:{react:chart,newPlot:chart,Plots:{resize(){}}}};
 vm.createContext(context);vm.runInContext(code.replace('/* ---------- boot ---------- */',`${transform||''}\n/* ---------- boot ---------- */`),context);
 for(const id of ['overview','openrouter','vercel','pricing','cloudflare','ramp','disclosures','method'])vm.runInContext(`show('${id}')`,context);
 for(const lag of [1,4,13])vm.runInContext(`deskLag=${lag};BUILD.overview(document.getElementById('p-overview'))`,context);
 for(const node of nodes.values())assert(!/\bNaN\b|\bInfinity\b/.test(node.content),'Invalid rendered number in '+node.id);
 return charts.length;
}
console.log('Real-data rendering:',run(),'chart calls');
console.log('Empty-source rendering:',run("for(const id of D.sourceOrder){D[id]={ok:false};D.sources[id].ok=false;D.sources[id].asof=null}"),'chart calls');
