/* Calendar-based comparisons. Null means unavailable, never zero. */
const T = (() => {
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const add=(d,n)=>{const x=new Date(d+'T00:00:00Z');x.setUTCDate(x.getUTCDate()+n);return x.toISOString().slice(0,10)};
 const ratio=(a,b)=>finite(a)&&finite(b)&&b>0?a/b:null;
 const change=(a,b)=>finite(a)&&finite(b)?a-b:null;
 const growth=(a,b)=>{const r=ratio(a,b);return r===null?null:r-1};
 const at=(dates,v,d)=>v?.[dates.indexOf(d)]??null;
 function weekly(dates,values){
  const groups={}; dates.forEach((d,i)=>{const x=new Date(d+'T00:00:00Z'), start=add(d,-((x.getUTCDay()+6)%7));(groups[start]??=[]).push([d,values?.[i]])});
  const out={};for(const [w,rows] of Object.entries(groups))if(new Set(rows.map(r=>r[0])).size===7&&rows.every(r=>finite(r[1])))out[w]=rows.reduce((s,r)=>s+r[1],0)/7;
  return out;
 }
 function orSummary(o,lag=1){
  if(!o.ok||!o.weeks?.length)return null;
  const n=o.weeks.length-1,date=o.weeks[n],prev=add(date,-7*lag),j=o.weeks.indexOf(prev),p1=o.weeks.indexOf(add(date,-7)),p2=o.weeks.indexOf(add(date,-14));
  const sum=(v,i)=>i>=0?v?.[i]??null:null;
  const now=o.total[n],before=sum(o.total,j),wow=growth(now,sum(o.total,p1)),prior=growth(sum(o.total,p1),sum(o.total,p2));
  const models=Object.entries(o.models).map(([model,m])=>({model,...m,tokens:m.v[n],share:ratio(m.v[n],now),delta:change(ratio(m.v[n],now),ratio(sum(m.v,j),before)),tokenDelta:change(m.v[n],sum(m.v,j))}));
  return {n,j,date,end:add(date,6),prev,now,before,wow,prior,growth:growth(now,before),acceleration:change(wow,prior),open:ratio(o.open?.[n],now),openDelta:change(ratio(o.open?.[n],now),ratio(sum(o.open,j),before)),closed:ratio(o.closed?.[n],now),unknown:ratio(now-(o.open?.[n]??0)-(o.closed?.[n]??0),now),free:ratio(o.free?.[n],now),models};
 }
 function board(D,lag){
  const o=orSummary(D.openrouter,lag), v=D.vercel,r=D.ramp,c=D.cloudflare;
  const metrics=['tokens','spend','requests'];const vw={};
  if(v.ok)for(const [lab,m] of Object.entries(v.labs))vw[lab]=Object.fromEntries(metrics.map(k=>[k,weekly(v.dates,m[k])]));
  const dates=[...new Set(Object.values(vw).flatMap(m=>Object.keys(m.tokens)))].sort(),vd=dates.at(-1),vp=vd?add(vd,-7*lag):null;
  const cd=c.ok?c.dates.at(-1):null,cp=cd?add(cd,-7*lag):null;
  const rm=r.ok?r.months.at(-1):null;let rp=null;if(rm){const d=new Date(rm+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()-1);rp=d.toISOString().slice(0,10)}
  const aliases={'ChatGPT / OpenAI':'OpenAI','Claude / Anthropic':'Anthropic','Google Gemini':'Google','Grok / xAI':'xAI','Meta AI':'Meta','DeepSeek':'DeepSeek','Mistral':'Mistral','Qwen':'Qwen'};
  const cr={};if(c.ok)for(const [s,vals]of Object.entries(c.services)){if(aliases[s])cr[aliases[s]]={value:at(c.dates,vals,cd),delta:change(at(c.dates,vals,cd),at(c.dates,vals,cp))}}
  const labs=[...new Set([...Object.keys(D.openrouter.labs||{}),...Object.keys(vw),...Object.keys(r.vendors||{}),...Object.keys(cr)])].filter(l=>!l.startsWith('Other')&&!['all','census'].includes(l));
  const cell=(value,prev)=>({value:value??null,delta:change(value,prev)});
  const rows=labs.map(l=>({lab:l,or:cell(o?ratio(D.openrouter.labs[l]?.[o.n],o.now):null,o?ratio(D.openrouter.labs[l]?.[o.j],o.before):null),tokens:cell(vw[l]?.tokens?.[vd],vw[l]?.tokens?.[vp]),spend:cell(vw[l]?.spend?.[vd],vw[l]?.spend?.[vp]),requests:cell(vw[l]?.requests?.[vd],vw[l]?.requests?.[vp]),ramp:cell(r.ok?ratio(at(r.months,r.vendors[l],rm),100):null,r.ok?ratio(at(r.months,r.vendors[l],rp),100):null),cf:cr[l]||{value:null,delta:null}}));
  rows.sort((a,b)=>(b.or.value??b.tokens.value??0)-(a.or.value??a.tokens.value??0));
  return {rows,orDate:o?.date,orPrev:o?.prev,vercelDate:vd,vercelPrev:vp,rampDate:rm,rampPrev:rp,cfDate:cd,cfPrev:cp};
 }
 function freshness(D,id){const s=D.sources[id];if(!s.ok)return {state:'Missing',date:null};let d=s.asof;
  if(id==='openrouter')d=add(d,6);
  const age=Math.floor((new Date(D.built)-new Date(d))/86400000);
  if(id==='disclosures')return {state:'Event log',date:d};
  return {state:age>(id==='ramp'?75:10)?'Stale':id==='ramp'?'Monthly':'Current',date:d,age};
 }
 function envelope(rows,key){let best=Infinity;return rows.filter(r=>finite(r.idx)&&finite(r[key])&&r[key]>0).sort((a,b)=>b.idx-a.idx||a[key]-b[key]).filter(r=>{if(r[key]<best){best=r[key];return true}return false}).reverse()}
 return {finite,add,ratio,change,growth,at,weekly,orSummary,board,freshness,envelope};
})();
if(typeof module!=='undefined')module.exports=T;
