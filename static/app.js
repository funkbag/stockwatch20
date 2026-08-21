const grid = document.getElementById('grid');
const detail = document.getElementById('detail');
const updated = document.getElementById('updated');
const summary = document.getElementById('summary');
const refreshBtn = document.getElementById('refresh');
const signalFilters = document.getElementById('signalFilters');
const movementFilters = document.getElementById('movementFilters');
const signalFilterBoxes = [...document.querySelectorAll('#signalFilters input[type="checkbox"]')];
const movementFilterBoxes = [...document.querySelectorAll('#movementFilters input[type="checkbox"]')];
const onlyAlertsBtn = document.getElementById('onlyAlerts');
const showAllBtn = document.getElementById('showAll');
const onlyMoversBtn = document.getElementById('onlyMovers');
const showAllMovementBtn = document.getElementById('showAllMovement');
let state = null;

function cls(score){ return score > 10 ? 'positive' : score < -10 ? 'negative' : 'neutral'; }
function deltaCls(delta){ return delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral'; }
function fmt(x,d=2){ return (x===null || x===undefined || Number.isNaN(Number(x))) ? '—' : Number(x).toFixed(d); }
function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
function normalizedLabel(item){
  const label = String(item?.signal?.label || 'NO DATA').trim().toUpperCase();
  return label === 'ERROR' ? 'NO DATA' : label;
}
function movementClass(item){
  const raw = item?.signal?.score_change;
  if(raw===null || raw===undefined || Number.isNaN(Number(raw))) return 'STABLE';
  const delta=Number(raw);
  if(delta>=10) return 'IMPROVING';
  if(delta<=-10) return 'DETERIORATING';
  return 'STABLE';
}
function movementText(item){
  const kind=movementClass(item);
  if(kind==='IMPROVING') return 'Fast improving';
  if(kind==='DETERIORATING') return 'Fast deteriorating';
  return 'Stable';
}
function deltaText(delta){
  if(delta===null || delta===undefined || Number.isNaN(Number(delta))) return 'Δ —';
  const n=Number(delta);
  return `Δ ${n>0?'+':''}${fmt(n,1)}`;
}
function sparkline(values, positive=true){
  if(!values || values.length<2) return '';
  const w=220,h=42,min=Math.min(...values),max=Math.max(...values),rng=(max-min)||1;
  const pts=values.map((v,i)=>`${(i/(values.length-1))*w},${h-((v-min)/rng)*h}`).join(' ');
  const color=positive?'#4bd7a3':'#ff6d7a';
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="${color}" stroke-width="2" points="${pts}"/></svg>`;
}
function card(item){
  const t=item.technical||{}, s=item.signal||{score:0,label:'NO DATA'}, ta=item.technical_alert||{};
  const d=s.score_change;
  const early = ta.active ? `<div class="early-badge ${String(ta.direction||'').toLowerCase()}">${esc(ta.label)} · ${fmt(ta.confidence,0)}%</div>` : '';
  return `<article class="card ${(s.is_alert||ta.active)?'alert':''}" data-symbol="${esc(item.symbol)}" data-label="${esc(normalizedLabel(item))}" data-movement="${movementClass(item)}">
    <div class="top"><div class="symbol">${esc(item.symbol)}</div><div class="score-wrap"><div class="score ${cls(s.score)}">${s.score>0?'+':''}${s.score}</div><div class="score-delta ${deltaCls(d)}">${deltaText(d)}</div></div></div>
    <div class="label-row"><div class="label">${esc(s.label || 'NO DATA')}</div><div class="movement-badge ${movementClass(item).toLowerCase()}">${movementText(item)}</div></div>
    ${early}
    <div class="metrics">
      <span>Price <b>${fmt(t.price, t.price<10?3:2)}</b></span><span>1h <b class="${cls(t.change_1h_pct||0)}">${fmt(t.change_1h_pct)}%</b></span>
      <span>RSI <b>${fmt(t.rsi14,1)}</b></span><span>Vol z <b>${fmt(t.volume_z,1)}</b></span>
      <span>ATR <b>${fmt(t.atr_pct,1)}%</b></span><span>RS 20d <b>${fmt(t.relative_strength_20d_pct,1)}%</b></span>
    </div>
    <div class="spark">${sparkline(t.sparkline, s.score>=0)}</div>
  </article>`;
}
function priceFmt(x){
  if(x===null || x===undefined || Number.isNaN(Number(x))) return '—';
  const n=Number(x);
  return n<10 ? n.toFixed(3) : n.toFixed(2);
}
function technicalAlertHtml(item){
  const a=item.technical_alert||{};
  const hist=item.alert_history||[];
  const active=Boolean(a.active);
  const reasons=(a.reasons||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  const confirm=a.confirm_level!=null ? `${esc(a.confirm_direction||'')} <b>${priceFmt(a.confirm_level)}</b>` : '—';
  const invalidate=a.invalidate_level!=null ? `${esc(a.invalidate_direction||'')} <b>${priceFmt(a.invalidate_level)}</b>` : '—';
  const histHtml=hist.length ? [...hist].reverse().map(h=>`<div class="alert-history-row">
      <div><b>${esc(h.label||'Alert')}</b><div class="meta">${h.timestamp?new Date(h.timestamp).toLocaleString():''}</div></div>
      <div class="history-numbers"><span>${h.score>0?'+':''}${fmt(h.score,0)}</span><span class="${deltaCls(h.score_change)}">${deltaText(h.score_change)}</span><span>${fmt(h.confidence,0)}%</span></div>
    </div>`).join('') : '<div class="empty compact">No material early-alert transitions recorded yet.</div>';
  return `<section class="technical-alert ${active?String(a.direction||'').toLowerCase():'inactive'}">
      <div class="alert-head"><div><div class="alert-kicker">Technical Early Alert</div><div class="alert-title">${esc(a.label||'NO ACTIVE EARLY ALERT')}</div></div><div class="confidence">${fmt(a.confidence,0)}%</div></div>
      <div class="alert-status">${active?'Active deterministic setup':'No material setup at this scan'}</div>
      ${reasons?`<ul class="alert-reasons">${reasons}</ul>`:''}
      <div class="alert-levels"><div><span>Confirm</span>${confirm}</div><div><span>Invalidate</span>${invalidate}</div></div>
    </section>
    <h3>Technical alert history</h3>${histHtml}`;
}
function detailHtml(item){
  const t=item.technical||{}, s=item.signal||{}, fib=t.fibonacci||{}, e=t.elliott||{};
  const reasons=(s.reasons||[]).map(x=>`<div class="reason">${esc(x)}</div>`).join('') || '<div class="empty">No strong drivers detected.</div>';
  const fibHtml = fib.swing_low ? Object.entries(fib).filter(([k])=>!['direction'].includes(k)).map(([k,v])=>`<div>${esc(k)}</div><div>${typeof v==='number'?fmt(v,3):esc(v)}</div>`).join('') : '<div>Not available</div>';
  const news=(item.news||[]).map(n=>`<div class="news ${n.important?'important':''}"><a href="${esc(n.url||'#')}" target="_blank" rel="noopener">${esc(n.title)}</a><div class="meta">${esc(n.publisher||'')} · sentiment ${fmt(n.sentiment,2)}${n.published?' · '+esc(n.published):''}</div></div>`).join('') || '<div class="empty">No headlines available.</div>';
  const events=(item.calendar||[]).map(x=>`<div class="event"><span>${esc(x.event)}</span><span>${esc(x.date)}</span></div>`).join('') || '<div class="empty">No calendar items available.</div>';
  return `<h2>${esc(item.symbol)} <span class="${cls(s.score)}">${s.score>0?'+':''}${s.score}</span> <span class="detail-delta ${deltaCls(s.score_change)}">${deltaText(s.score_change)}</span></h2><div class="label">${esc(s.label)}</div>
    <div class="score-history">Previous scan: <b>${s.previous_score===null || s.previous_score===undefined?'—':(s.previous_score>0?'+':'')+fmt(s.previous_score,0)}</b> · Current: <b>${s.score>0?'+':''}${fmt(s.score,0)}</b></div>
    ${technicalAlertHtml(item)}
    <h3>Signal drivers</h3>${reasons}
    <h3>Technical structure</h3><div class="fib"><div>EMA20</div><div>${fmt(t.ema20,3)}</div><div>EMA50</div><div>${fmt(t.ema50,3)}</div><div>EMA200</div><div>${fmt(t.ema200,3)}</div><div>MACD</div><div>${fmt(t.macd,4)} / ${fmt(t.macd_signal,4)}</div></div>
    <h3>Fibonacci swing (${esc(fib.direction||'—')})</h3><div class="fib">${fibHtml}</div>
    <h3>Elliott heuristic</h3><div>${esc(e.label||'—')} · confidence ${fmt((e.confidence||0)*100,0)}%</div>
    <h3>Upcoming / known dates</h3>${events}
    <h3>News & headline sentiment</h3>${news}`;
}
function selectedLabels(){ return new Set(signalFilterBoxes.filter(x=>x.checked).map(x=>x.value.toUpperCase())); }
function selectedMovements(){ return new Set(movementFilterBoxes.filter(x=>x.checked).map(x=>x.value.toUpperCase())); }
function render(){
  if(!state) return;
  const items=state.items||[];
  const labels=selectedLabels();
  const movements=selectedMovements();
  const visible=items.filter(x=>labels.has(normalizedLabel(x)) && movements.has(movementClass(x)));
  const bull=items.filter(x=>(x.signal?.score||0)>=25).length;
  const bear=items.filter(x=>(x.signal?.score||0)<=-25).length;
  const alerts=items.filter(x=>x.signal?.is_alert).length;
  const movers=items.filter(x=>Math.abs(Number(x.signal?.score_change||0))>=10).length;
  const earlyAlerts=items.filter(x=>x.technical_alert?.active).length;
  summary.innerHTML=`<span class="chip">Showing ${visible.length}/${items.length}</span><span class="chip">Bullish watches ${bull}</span><span class="chip">Bearish watches ${bear}</span><span class="chip">Alerts ${alerts}</span><span class="chip">Early alerts ${earlyAlerts}</span><span class="chip">Score movers ≥10: ${movers}</span><span class="chip">Benchmark ${esc(state.benchmark||'SPY')}</span>`;
  grid.innerHTML=visible.length ? visible.map(card).join('') : '<div class="empty">No stocks match the selected signal and movement filters.</div>';
  grid.querySelectorAll('.card').forEach(el=>el.addEventListener('click',()=>{ const item=items.find(x=>x.symbol===el.dataset.symbol); if(item) detail.innerHTML=detailHtml(item); }));
}
async function load(){
  try{
    const r=await fetch('/api/state?ts='+Date.now(),{cache:'no-store'});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    state=await r.json();
    updated.textContent=state.updated_at ? 'Updated '+new Date(state.updated_at).toLocaleString() : 'Initializing…';
    render();
  }catch(e){ updated.textContent='Dashboard API unavailable'; }
}
// Signal and movement filters combine with AND logic.
if(signalFilters) signalFilters.addEventListener('change', e=>{ if(e.target.matches('input[type="checkbox"]')) render(); });
if(movementFilters) movementFilters.addEventListener('change', e=>{ if(e.target.matches('input[type="checkbox"]')) render(); });
signalFilterBoxes.forEach(x=>x.addEventListener('change',render));
movementFilterBoxes.forEach(x=>x.addEventListener('change',render));
onlyAlertsBtn.addEventListener('click',()=>{ signalFilterBoxes.forEach(x=>x.checked=['BULLISH ALERT','BEARISH ALERT'].includes(x.value.toUpperCase())); render(); });
showAllBtn.addEventListener('click',()=>{ signalFilterBoxes.forEach(x=>x.checked=true); render(); });
onlyMoversBtn.addEventListener('click',()=>{ movementFilterBoxes.forEach(x=>x.checked=['IMPROVING','DETERIORATING'].includes(x.value.toUpperCase())); render(); });
showAllMovementBtn.addEventListener('click',()=>{ movementFilterBoxes.forEach(x=>x.checked=true); render(); });
refreshBtn.addEventListener('click',async()=>{ refreshBtn.disabled=true; refreshBtn.textContent='Refreshing…'; try{await fetch('/api/refresh',{method:'POST',cache:'no-store'});}finally{refreshBtn.disabled=false;refreshBtn.textContent='Refresh now';load();}});
load(); setInterval(load,60000);
