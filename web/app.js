"use strict";

const $ = (q, scope = document) => scope.querySelector(q);
const main = $("#main");
const icons = {
  setup: '<path d="M5 5h14v14H5zM8 9h8m-8 3h8m-8 3h5"/>',
  analysis: '<path d="M3 13h4l2-7 4 12 2-5h6"/>',
  paper: '<path d="M3 7h18v13H3zM8 7V4h8v3M3 12h18m-11 0v3h4v-3"/>',
  chart: '<path d="M4 4v16h16M8 15l4-4 3 2 5-6"/>',
  audit: '<path d="M6 4h12v16H6zM9 8h6m-6 4h6m-6 4h4"/>',
  right: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  left: '<path d="M19 12H5m6 6-6-6 6-6"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  shield: '<path d="M12 3 5 6v5c0 4 3 7 7 9 4-2 7-5 7-9V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  lock: '<rect x="6" y="10" width="12" height="10" rx="2"/><path d="M9 10V7a3 3 0 0 1 6 0v3m-3 4v2"/>',
  scale: '<path d="M12 3v17m-5 0h10M5 7h14M5 7l-3 6h6L5 7Zm14 0-3 6h6l-3-6Z"/>',
  spark: '<path d="M12 3 7 11l5 10 5-10-5-8Z"/><path d="M12 11v4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  pause: '<path d="M9 5v14m6-14v14"/>',
  tick: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M12 6v8m0 4v.5"/>',
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">${icons[name] || icons.spark}</svg>`;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const cashFormat = new Intl.NumberFormat("en-GB", {style:"currency",currency:"GBP",minimumFractionDigits:0,maximumFractionDigits:2});
const decimal = new Intl.NumberFormat("en-GB", {maximumFractionDigits:2});
const gbp = pennies => cashFormat.format(pennies / 100);
const pct = (value, places = 1) => value == null ? "—" : `${(value * 100).toFixed(places)}%`;
const signed = value => `${value > 0 ? "+" : value < 0 ? "−" : ""}${gbp(Math.abs(value))}`;
const dt = value => new Date(value).toLocaleString("en-GB", {timeZone:"Europe/London",dateStyle:"medium",timeStyle:"short"});
const colour = ["#1d2a44","#4a6aa0","#8a6a2c","#7f9cc8","#5e7387","#c4d2e6"];
const nav = [
  ["coach","Rent-safe coach","Coach","spark"],
  ["setup","Portfolio setup","Setup","setup"],["analysis","Agent analysis","Analysis","analysis"],
  ["paper","Paper portfolio","Portfolio","paper"],["evidence","Benchmark evidence","Evidence","chart"],
  ["audit","Audit history","Audit","audit"],
];
const steps = ["Your goals","Risk & resilience","Paper holdings"];
let data, form, page = "setup", step = 0, visited = 0, result, busy = false, actionBusy = false;
let events = {}, evidence, evidenceError, stateError, toastTimeout;
let chat = [], trail = [], coachFinal = null, coachBusy = false, coachError = "";

async function request(path, body) {
  const options = body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json","X-Campus-Paper":"1"},body:JSON.stringify(body)};
  const response = await fetch(path, options);
  const json = await response.json();
  if (!response.ok) throw new Error(json.error || "The workspace is temporarily unavailable.");
  return json;
}

function notify(message) {
  const node = $("#toast");
  node.hidden = false;
  node.textContent = message;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { node.hidden = true; }, 4300);
}

function button(label, action, type = "secondary", glyph = "", extra = "") {
  return `<button type="button" class="btn ${type}" data-action="${action}" ${extra}>${glyph ? icon(glyph) : ""}${label}</button>`;
}
function head(label, title, intro) {
  return `<header class="page-head"><p class="eyebrow">${label}</p><h1>${title}</h1><p>${intro}</p></header>`;
}
function pill(text, variant = "paper") { return `<span class="pill ${variant}">${text}</span>`; }
function callout(title, text, warning = false) {
  return `<div class="notice${warning ? " warn" : ""}"><strong>${title}</strong>${text}</div>`;
}
function renderNav() {
  const row = ([id, label, mobile, glyph], compact) => `<button class="nav-link" data-page="${id}" ${page===id ? 'aria-current="page"' : ""}>${icon(glyph)}${compact ? mobile : label}${page===id ? '<span class="nav-end" aria-hidden="true">•</span>' : ""}</button>`;
  $("#nav").innerHTML = nav.slice(0,4).map(x => row(x,false)).join("");
  $("#research-nav").innerHTML = nav.slice(4).map(x => row(x,false)).join("");
  $("#mobile-nav").innerHTML = nav.map(x => row(x,true)).join("");
  $("#crumb").textContent = nav.find(x => x[0] === page)[1];
}
async function navigate(next) {
  page = next;
  stateError = "";
  render();
  window.scrollTo({top:0,behavior:"instant"});
  $("h1",main)?.setAttribute("tabindex","-1");
  $("h1",main)?.focus({preventScroll:true});
  if (next === "audit" || next === "paper") {
    try { Object.assign(data, await request("/api/state")); }
    catch (err) { stateError = err.message; }
    if (page === next) render();
  }
  if (next === "evidence" && !evidence) await getEvidence();
}
async function getEvidence() {
  evidenceError = "";
  try { evidence = await request("/api/evidence"); }
  catch (err) { evidenceError = err.message; }
  if (page === "evidence") render();
}

function numberInput(key, label, units, min, max, stepBy, prefix = false, help = "") {
  return `<label class="field"><span>${label}</span><span class="input">${prefix ? `<span>${units}</span>` : ""}<input type="number" name="${key}" value="${esc(form[key])}" required min="${min}" max="${max}" step="${stepBy}" inputmode="decimal">${prefix ? "" : `<span>${units}</span>`}</span>${help ? `<small>${help}</small>` : ""}</label>`;
}
function choice(key, value, label, caption, glyph = "") {
  return `<label class="option"><input type="radio" name="${key}" value="${value}" ${String(form[key]) === String(value) ? "checked" : ""}><span class="option-content">${glyph ? icon(glyph) : ""}<span><b>${label}</b><small>${caption}</small></span></span></label>`;
}
function select(key, label, options) {
  return `<label class="field"><span>${label}</span><span class="input"><select name="${key}">${options.map(([v,l])=>`<option value="${v}" ${String(form[key]) === String(v) ? "selected" : ""}>${l}</option>`).join("")}</select></span></label>`;
}
function safety() {
  return `<div class="safety">${icon("shield")}<div><h2>Fictional inputs only</h2><p>Use made-up figures and holdings. Each paper change needs your approval.</p></div></div>`;
}
function snapshot() {
  return `<section class="snapshot card" aria-label="Your fictional plan">
    <p class="eyebrow">YOUR FICTIONAL PLAN</p><h2 id="snapshot-budget">${gbp((Number(form.budget) || 0)*100)}</h2><p class="snapshot-copy">Starting paper balance</p>
    <dl><div><dt>Annual target</dt><dd id="snapshot-target">${decimal.format(Number(form.target) || 0)}%</dd></div><div><dt>Monthly top-up</dt><dd id="snapshot-monthly">${gbp((Number(form.monthly) || 0)*100)}</dd></div></dl>
  </section>`;
}
function scenarioList() {
  const marks = {conservative:"shield",balanced:"scale",aggressive:"chart",rent:"lock"};
  return `<section class="scenarios card"><h2>Try a student scenario</h2><p>Load a fictional profile to explore the agent.</p>
    ${Object.entries(data.presets).map(([key,p])=>`<button class="scenario" data-preset="${key}"><span class="scenario-icon">${icon(marks[key])}</span><span><strong>${esc(p.label)}</strong><small>${esc(p.caption)}</small></span>${icon("chevron")}</button>`).join("")}
  </section>`;
}
function goalStep() {
  return `<h2 class="form-title">What are you planning for?</h2><p class="description">Set a target and a timeframe for your fictional portfolio.</p>
    <div class="field-grid">${numberInput("target","Annual return target","%",0,1000000,"any",false,"An aspiration for the agent to assess.")}
    ${numberInput("years","Investment horizon","years",.25,50,"any",false,"When you might need the invested funds.")}
    ${numberInput("budget","Starting paper balance","£",0,10000000,.01,true)}
    ${numberInput("monthly","Monthly contribution","£",0,100000,.01,true)}</div>
    <fieldset><legend>Main investment objective</legend><div class="choices">
    ${choice("objective","stability","Stability","Smaller swings","shield")}${choice("objective","balance","Balance","Growth with limits","scale")}${choice("objective","growth","Growth","Accept bigger swings","chart")}
    </div></fieldset>`;
}
function riskStep() {
  const needs = form.essential || Number(form.runway) < 3 || Number(form.years) < 1;
  return `<h2 class="form-title">How much risk can you take?</h2><p class="description">Use fictional circumstances to set a loss budget and keep essential spending protected.</p>
    <div class="field-grid">${numberInput("loss","Maximum tolerable loss","%",0,95,"any")}
    ${numberInput("runway","Emergency cash runway","months",0,60,"any")}
    ${select("volatility","Tolerance for short-term swings",[["low","Low"],["moderate","Moderate"],["high","High"]])}
    ${select("essential","Could these funds cover essentials?",[["false","No"],["true","Yes, possibly"]])}</div>
    <div id="affordability" aria-live="polite">${needs ? callout("Affordability check", "This profile will trigger a safety veto. Continue to see the reason in the analysis.",true) : ""}</div>
    <fieldset><legend>Leverage in simulation</legend><div class="choices two">
    ${choice("leverage",false,"Standard exposure","Up to 1.0×","shield")}${choice("leverage",true,"Explore leverage","Separate scenario","chart")}
    </div></fieldset>
    ${form.leverage ? `<div class="stack notice"><div class="field-grid">${numberInput("maxLeverage","Maximum factor","×",1,2,.1)}</div><label class="checkline"><input type="checkbox" name="acknowledged" ${form.acknowledged ? "checked" : ""}><span>I understand daily reset can magnify losses and make multi-day returns diverge from the stated multiplier. This scenario is for paper research only.</span></label></div>` : ""}`;
}
function holdingsStep() {
  let extra = "";
  if (form.mode === "manual") {
    extra = `<datalist id="fund-list">${data.funds.map(f=>`<option value="${f.ticker}">${esc(f.name)} · ${f.isin}</option>`).join("")}</datalist>
    ${form.positions.map((p,i)=>`<div class="holding-row"><label class="field"><span>Ticker or ISIN</span><span class="input"><input data-row="${i}" data-field="identifier" list="fund-list" required maxlength="16" value="${esc(p.identifier)}"></span></label>
    <label class="field"><span>Fictional units</span><span class="input"><input data-row="${i}" data-field="quantity" type="number" min="0.00000001" max="1000000" step="any" value="${esc(p.quantity)}" required></span></label>
    <button type="button" class="icon-btn" data-remove="${i}" aria-label="Remove position ${i+1}" ${form.positions.length===1?"disabled":""}>${icon("close")}</button></div>`).join("")}
    ${button("Add a position","add","secondary","plus",form.positions.length>=60?"disabled":"")}`;
  }
  if (form.mode === "csv") {
    extra = `<div class="upload"><label class="field"><span>Upload fictional holdings</span><input id="csv-upload" type="file" accept=".csv,text/csv" ${form.csv ? "" : "required"}></label>
    <p class="help">Up to 16 KB. Use two columns, <code>ticker</code> (or <code>isin</code>) and <code>quantity</code>. Example <code>VWRP,2.5</code>.</p>
    ${form.csv ? `<p class="mono">${esc(form.csv.split(/\r?\n/)[0])}</p><label class="checkline"><input type="checkbox" name="mappingConfirmed" required ${form.mappingConfirmed?"checked":""}>I confirm the identifier and quantity mapping. The positions are fictional.</label>` : ""}</div>`;
  }
  if (form.mode === "sample") extra = callout("Sample portfolio", "6 VWRP units and 7 VAGS units. The remainder stays as fictional cash.");
  if (form.mode === "paper") extra = callout("Use approved holdings", "The agent will value the latest approved paper positions using the selected dataset.");
  return `<h2 class="form-title">How should your paper portfolio start?</h2><p class="description">Choose a blank portfolio, a sample, or your own fictional ETF positions.</p>
    ${select("mode","Starting holdings",[["zero","Start with paper cash"],["sample","Use the sample student portfolio"],["manual","Enter fictional holdings"],["csv","Upload a synthetic CSV"],...(data.paper?[["paper","Use my approved paper positions"]]:[])])}
    ${extra}<div class="notice">${iconInline("lock")} <b>Human approval required.</b> Analysis prepares a proposal for your review.</div>`;
}
function iconInline(name) { return `<span class="inline-icon">${icon(name)}</span>`; }
function setupPage() {
  const content = [goalStep,riskStep,holdingsStep][step]();
  const nextLabel = ["Continue to risk","Continue to holdings","Analyse my portfolio"][step];
  return `${head("STUDENT PORTFOLIO STRATEGIST","Set up your portfolio","Set your goals and let the agent check which ETF allocations fit your fictional budget.")}
  <div class="layout"><section class="card" aria-label="Portfolio setup">
    <nav class="progress" aria-label="Setup steps">${steps.map((s,i)=>`${i?'<span class="connector"></span>':""}<button type="button" data-step="${i}" ${step===i?'aria-current="step"':""} ${i>visited?"disabled":""} class="${i<step?"done":""}"><span class="step-index">${i<step?icon("tick"):`0${i+1}`}</span>${s}</button>`).join("")}</nav>
    <form id="profile-form"><div class="form-body"><p class="error-text" id="form-error" role="alert" hidden></p>${content}</div>
    <div class="form-actions">${step ? button("Back","back","secondary","left") : '<p class="help">Step 1 of 3</p>'}<button class="btn primary" type="submit" ${busy?"disabled":""}>${nextLabel}${icon("right")}</button></div></form>
    </section><aside class="side-col">${snapshot()}${scenarioList()}${safety()}</aside></div>`;
}

function progressPanel() {
  const hasEvents = Object.keys(events).length > 0;
  if (!busy && !hasEvents) return "";
  return `<section class="card card-pad"><h2 class="section-title">Agent activity</h2><p class="meta">The backend records each operation as it completes.</p>
  <ol class="agent-list" id="agent-events" aria-live="polite">${data.tools.map(([key,label],i)=>{
    const event = events[key];
    return `<li><span class="agent-icon ${event ? event.type==="blocked"?"failed":"" : "pending"}">${event ? event.type==="blocked"?icon("alert"):icon("tick") : i+1}</span><span><b>${label}</b>${event?`<span class="agent-detail">${esc(event.detail)}</span>`:(!busy?'<span class="agent-detail">Skipped after safety or validation gate</span>':"")}</span></li>`;
  }).join("")}</ol></section>`;
}
function stat(value,label) { return `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`; }
function traceLine(label, value) { return `<p><b>${label}</b> ${value}</p>`; }
function allocationRows(rows,cash,nav,showTrace = null) {
  const all = [...rows.map((row,i)=>({...row,colour:colour[i % colour.length]})),{ticker:"Cash",name:"Uninvested paper cash",value:cash,weight:cash/nav,colour:"#dbe4f0"}];
  const scale = `<div class="alloc-bar" aria-hidden="true">${all.map(x=>`<span style="width:${x.weight*100}%;background:${x.colour}"></span>`).join("")}</div>`;
  const list = all.map(row=>{
    const s = showTrace?.scores?.[row.ticker];
    const body = s ? `<div class="trace">
      ${traceLine("Input",`${esc(row.isin)} · ${esc(row.index)} · ${esc(row.income)}`)}
      ${traceLine("Data",`${esc(showTrace.provenance.last)} close £${s.close.toFixed(4)}. Base closes for 5, 20 and 60 observations £${s.base5.toFixed(4)}, £${s.base20.toFixed(4)}, £${s.base60.toFixed(4)}.`)}
      ${traceLine("Formula",`Momentum = latest ÷ base − 1. M5 ${pct(s.m5)}, M20 ${pct(s.m20)}, M60 ${pct(s.m60)}. Annualised realised volatility ${pct(s.vol20)}.`)}
      ${traceLine("Rule",`RO = 0.55 × M60 + 0.35 × M20 + 0.10 × M5 − 0.20 × daily volatility × √20. Ranking subtracts ${pct(s.costPenalty,2)} estimated fee and execution penalty and adds ${pct(s.retentionCredit,2)} retention credit.`)}
      ${traceLine("Result",`Rank score ${pct(s.score,2)}. ${esc(row.group)} exposure with a ${pct(row.weight)} target. ${signed(row.trade)} paper adjustment.`)}
      <p><a href="${esc(row.source)}" target="_blank" rel="noopener">Issuer metadata</a> · OCF ${pct(row.fee,2)} · ${esc(row.listing)} · ${esc(row.domicile)} · ${esc(row.share_currency)} share class · ${esc(row.wrapper || 'Wrapper eligibility unverified')}</p></div>` :
      `<div class="trace">${row.ticker==="Cash" ? "Cash remaining after ETF allocations and simulated execution costs." : `${esc(row.isin)} · ${decimal.format(row.quantity)} fictional units · ${esc(row.income)} <a href="${esc(row.source)}" target="_blank" rel="noopener">Issuer</a>`}</div>`;
    return `<details class="alloc-row"><summary><span class="swatch" style="background:${row.colour}"></span><span><b>${esc(row.ticker)}</b><small>${esc(row.name)}</small></span><span class="numbers"><b>${gbp(row.value)}</b><small>${pct(row.weight)}</small></span>${icon("chevron")}</summary>${body}</details>`;
  }).join("");
  return `${scale}<div class="allocation-list">${list}</div>`;
}

function resultPanel(r) {
  if (!r) {
    return busy ? `<section class="card card-pad"><h2 class="section-title">Analysing your fictional plan</h2><p class="meta" role="status">The agent is running the data and suitability checks.</p></section>` :
    `<section class="card card-pad"><h2 class="section-title">Ready when you are</h2><p class="meta">Complete the three setup steps to get a traceable paper proposal.</p>${button("Open portfolio setup","setup","primary","right")}</section>`;
  }
  if (r.state === "error" || r.state === "veto") {
    const veto = r.state === "veto";
    return `<section class="card card-pad"><div class="summary-top"><div><p class="eyebrow">AGENT DECISION</p><h2>${veto ? "No suitable allocation" : "Analysis needs your review"}</h2></div>${pill(veto?"Safety veto":"Input or data check","warning")}</div>
    ${callout(veto?esc(r.riskRule):"Check the details",esc(r.reason),true)}
    ${veto ? `<div class="stat-grid">${stat(pct(r.target,0),"Annual return target")}${stat(`${r.category} / 5`,"Risk category")}${stat("Blocked","Paper action")}</div>
    <p class="meta">${r.target >= 1 ? "The evidence does not support the 100%+ annual objective. " : ""}${esc(r.fit)} ${esc(r.leverage?.reason || "")}</p>` : ""}
    <div class="button-row">${button("Edit my profile","setup","primary","left")}${button("View audit history","audit")}</div></section>`;
  }
  const m = r.metrics;
  const worst = Math.max(...Object.values(m.stress));
  const ready = r.state === "ready";
  const riskText = r.target >= 1 ? "Return target needs a reality check" : r.target > Math.max(0,m.annualised) ? "Target exceeds the observed sample" : "Review the trade-offs";
  const exposure = r.leverage;
  const scenario = exposure.state !== "off" ? `<details class="details" open><summary>Experimental leverage ${exposure.state === "veto" ? "· blocked" : "· preview"}</summary>
    <p>${esc(exposure.reason)} Maximum permitted scenario factor ${exposure.maximum.toFixed(1)}×. Standard allocation 1.0×.</p>
    ${exposure.requested ? `<p>${exposure.requested.toFixed(1)}× requested · ${pct(exposure.grossExposure)} of NAV gross exposure · ${pct(exposure.stress)} stressed loss · ${pct(exposure.drawdown)} sample drawdown · ${pct(exposure.financing)} annual financing assumption on exposure above NAV.</p>` : ""}
    <p>Daily reset compounds each day’s move. Volatility can erode multi-day results and losses can exceed the model. This illustration represents synthetic exposure with no ETF product or order attached.</p></details>` : "";
  return `<section class="card card-pad${r.state==="rejected"?" rejected":""}"><div class="summary-top"><div><p class="eyebrow">AGENT DECISION</p><h2>${r.state==="approved"?"Paper changes applied":r.state==="rejected"?"Proposal rejected":r.state==="hold"?"Keep current holdings":"Proposed allocation"}</h2></div>${pill(r.state==="ready"?"Awaiting review":r.state==="approved"?"Approved":r.state==="hold"?"Within review bands":"Closed",r.state==="approved"?"paper":r.state==="ready"?"pending":r.state==="rejected"?"struck":"neutral")}</div>
    <div class="stat-grid">${stat(pct(r.target,r.target*100%1?1:0),"Annual return target")}${stat(`${r.category} / 5`,r.risk)}${stat(`${r.portfolioLeverage.toFixed(1)}×`,"Standard exposure ceiling")}</div>
    ${callout(riskText,esc(r.fit),r.target >= 1 || r.target > m.annualised)}
    <p class="meta">${esc(r.riskRule)}. Net paper balance ${gbp(r.nav)} · Fund exposure ${pct(r.exposure)} · Worst modelled stress ${pct(worst)}.</p>
    ${r.provenance.synthetic ? '<p class="meta"><b>Synthetic prices.</b> Sample returns describe a generated scenario.</p>' : ""}
  </section>
  <section class="card card-pad${r.state==="rejected"?" rejected":""}"><h2 class="section-title">Target holdings</h2><p class="meta">Expand an ETF to inspect the inputs, rules and calculations.</p>
  ${allocationRows(r.positions,r.cash,r.nav,r)}
  <details class="details"><summary>Proposed paper changes (${r.diffs.length})</summary>
  <div class="table-wrap"><table><thead><tr><th>ETF</th><th>Paper value change</th></tr></thead><tbody>${r.diffs.map(x=>`<tr><td>${x.ticker}</td><td>${signed(x.delta)}</td></tr>`).join("")}</tbody></table></div></details>
  <details class="details"><summary>Risk, costs and affordability</summary>
    <div class="stat-grid">${stat(pct(m.volatility),"Sample volatility")}${stat(pct(m.drawdown),"Sample drawdown")}${stat(pct(m.feeDrag,2),"Annual fund charges")}</div>
    <p>Estimated one-off cost ${gbp(r.fee)} on ${gbp(r.traded)} traded. One-way turnover ${pct(r.turnover)}. Fictional contributions are context only and are excluded from the return calculation.</p>
    <p>Cash runway ${r.runway} months · horizon ${r.horizon} years · loss limit ${pct(r.lossLimit)}. ${esc(r.allocationRule)}</p>
    <ul>${Object.entries(m.stress).map(([name,value])=>`<li>${name} · ${pct(value)} loss (${gbp(Math.round(value*r.nav))})</li>`).join("")}</ul>
    <p>Stress losses use fixed equity and bond shocks. Volatility and drawdown use daily constant-weight replay, so realised outcomes can differ.</p></details>
  ${scenario}
  <details class="details"><summary>Existing holdings and diversification</summary>
  <p>${r.existing.length} existing ETF positions · ${gbp(r.existingMetrics.cash)} paper cash · ${pct(r.existingMetrics.equity)} equity · ${pct(r.existingMetrics.maxPosition)} largest position · ${pct(r.existingMetrics.volatility)} sample volatility · ${pct(r.existingMetrics.drawdown)} sample drawdown.</p>
  <p>Holdings overlap and full sector/geography look-through are unresolved. The agent limits repeated index exposures and screens 60-day return correlations.</p>
  <ul>${Object.entries(r.exclusions).map(([t,reason])=>`<li><b>${t}</b> ${esc(reason)}</li>`).join("")}</ul></details>
  <details class="details"><summary>Decision rules, data and verification</summary>
  <p>Equity breadth ${pct(r.breadth)} × exposure multiplier ${r.breadthScale.toFixed(2)}. Positive 20-day equity trends divided by the valid equity count. The multiplier is 0.65 below 35%, 0.85 below 50%, and 1.00 otherwise.</p>
  <p>${esc(r.provenance.source)} · ${esc(r.provenance.retrieved)} · ${r.provenance.observations} observations ${r.provenance.first} to ${r.provenance.last} · GBP price observations · ${esc(r.provenance.licence)}</p>
  <p>Point-in-time cutoff ${r.provenance.cutoff}. Position and exposure-group cap 30%. Category fund cap ${pct(r.exposureCap)} and equity cap ${pct(r.equityCap)}.</p>
  <ul>${r.verified.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
  <p><button class="quiet" type="button" data-page="evidence">Open benchmark evidence</button></p></details>
  </section>
  ${ready ? `<section class="card card-pad"><h2 class="section-title">Review and confirm</h2>
    <p class="meta">Approving applies these changes to this workspace’s paper ledger.</p>
    ${r.replacesSnapshot ? callout("Replace existing snapshot", "This proposal starts from a separate fictional scenario. Approval replaces the current snapshot.") : ""}
    ${data.paused ? callout("Paper actions paused","Resume from the paper portfolio before approving.",true):""}
    <label class="checkline"><input type="checkbox" id="confirm-paper" ${data.paused?"disabled":""}>I approve the listed changes to my fictional paper portfolio.</label>
    <p class="error-text" id="action-error" role="alert" hidden></p>
    <div class="button-row">${button("Approve paper changes","approve","primary","tick","disabled")}${button("Reject proposal","reject","secondary","close")}${button("Edit goals","setup","secondary")}</div>
  </section>` : `<div class="button-row">${r.state==="approved"?button("View paper portfolio","paper","primary","right"):""}${button("Edit and rerun","setup")}</div>`}`;
}
function analysisPage() {
  return `${head("PORTFOLIO RESEARCH","Agent analysis","Review the decision, see how it was calculated and choose whether to apply it to your paper portfolio.")}
  <div class="layout"><div class="stack">${busy?progressPanel():""}${resultPanel(result)}${!busy?progressPanel():""}</div>
  <aside class="side-col">${snapshot()}${scenarioList()}${safety()}</aside></div>`;
}
function paperPage() {
  const p = data.paper;
  return `${head("SIMULATED LEDGER","Paper portfolio","See your most recent approved snapshot and control whether future paper actions can run.")}
    <div class="layout"><div class="stack"><section class="card card-pad">
    <div class="summary-top"><div><p class="eyebrow">APPROVED HOLDINGS</p><h2>${p ? gbp(p.nav) : "No approved portfolio yet"}</h2></div>${pill(data.paused?"Actions paused":"Paper only",data.paused?"warning":"paper")}</div>
    ${p ? `<p class="meta">Approved ${dt(p.approved)} · ${p.provenance.synthetic?"Synthetic prices":"Licensed price file"} · Snapshot at ${p.provenance.last}</p>${allocationRows(p.positions,p.cash,p.nav)}` :
      `<p class="meta">Your paper holdings will appear here after you explicitly approve a verified proposal.</p>${button(data.pending?"Review proposal":"Set up my portfolio",data.pending?"analysis":"setup","primary","right")}`}
    </section><section class="card card-pad"><h2 class="section-title">Execution control</h2><p class="meta">Pausing blocks approvals in the backend. You can still analyse a profile and review the audit history.</p>
    ${stateError?callout("Workspace error",esc(stateError),true):""}
    ${button(data.paused?"Resume paper actions":"Pause paper actions","pause","secondary",data.paused?"right":"pause",actionBusy?"disabled":"")}
    </section></div><aside class="side-col">${snapshot()}${safety()}</aside></div>`;
}

function benchmarkChart(e) {
  const paths = e.paths;
  const values = paths.flatMap(p=>p.curve);
  const min = Math.floor(Math.min(...values)*10)/10;
  const max = Math.max(min+.2,Math.ceil(Math.max(...values)*10)/10);
  const y = v => 172-(v-min)/(max-min)*149;
  const marks = Array.from({length:4},(_,i)=>max-(max-min)*i/3);
  return `<svg class="chart" viewBox="0 0 490 205" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">Chronological benchmark curves</title><desc id="chart-desc">Growth of £100 after estimated costs. Exact results are in the table below.</desc>
  ${marks.map(v=>`<line x1="44" x2="475" y1="${y(v)}" y2="${y(v)}" stroke="#e2e8de"/><text x="38" y="${y(v)+3}" text-anchor="end">£${Math.round(v*100)}</text>`).join("")}
  ${paths.map((p,k)=>`<polyline fill="none" stroke="${colour[k]}" stroke-width="${k===0?3:2}" ${k===2?'stroke-dasharray="5 3"':""} stroke-linejoin="round" points="${p.curve.map((v,i)=>`${44+i/(p.curve.length-1)*431},${y(v).toFixed(2)}`).join(" ")}"/>`).join("")}
  <text x="44" y="194">${e.first}</text><text x="475" y="194" text-anchor="end">${e.last}</text></svg>
  <div class="legend">${paths.map((p,i)=>`<span><span class="swatch" style="background:${colour[i]}"></span>${esc(p.name)}</span>`).join("")}</div>`;
}
function evidencePage() {
  const e = evidence;
  const rows = e?.paths.map(p=>`<tr><td>${esc(p.name)}</td><td>${pct(p.total)}</td><td>${pct(p.volatility)}</td><td>${pct(p.drawdown)}</td><td>${p.sharpe?.toFixed(2)??"—"}</td><td>${pct(p.turnover)}</td><td>${pct(p.costDrag,2)}</td></tr>`).join("");
  const range = (p,key,format=pct) => {
    const values = p.windows.map(window => window[key]).filter(v => v != null);
    return values.length ? `${format(Math.min(...values))} to ${format(Math.max(...values))}` : "—";
  };
  const ranges = e?.paths.map(p => `<tr><td>${esc(p.name)}</td><td>${range(p,"total")}</td><td>${range(p,"volatility")}</td><td>${range(p,"drawdown")}</td><td>${range(p,"sharpe",v=>v.toFixed(2))}</td><td>${range(p,"turnover")}</td><td>${range(p,"costDrag",v=>pct(v,2))}</td></tr>`).join("");
  return `${head("METHODS AND RESULTS","Benchmark evidence","Compare the strategy with passive baselines using completed observations, next-close fills and explicit costs.")}
    <div class="stack">${e ? `<section class="card card-pad"><div class="summary-top"><div><h2 class="section-title">Growth of £100</h2><p class="meta">${esc(e.source)} · ${e.observations} forward observations after ${e.warmup} warm-up closes.</p></div>${pill(e.synthetic?"Synthetic evaluation":"Licensed observations","neutral")}</div>
    ${benchmarkChart(e)}
    <div class="stat-grid">${stat(pct(e.paths[0].total),"RO net total return")}${stat(`${e.difference>=0?"+":""}${(e.difference*100).toFixed(1)} pp`,"Versus 60/40")}${stat(pct(e.paths[0].compliance,0),`Target-limit checks · ${e.paths[0].decisionCount}`)}</div>
    <div class="table-wrap"><table aria-label="Benchmark results"><thead><tr><th>Portfolio</th><th>Net return</th><th>Volatility</th><th>Max drawdown</th><th>Sharpe</th><th>Traded / NAV</th><th>Cost / start</th></tr></thead><tbody>${rows}</tbody></table></div>
    <details class="details" open><summary>Uncertainty across 252-observation windows</summary><div class="table-wrap"><table aria-label="Ranges across replay windows"><thead><tr><th>Portfolio</th><th>Net return</th><th>Volatility</th><th>Max drawdown</th><th>Sharpe</th><th>Traded / NAV</th><th>Cost / start</th></tr></thead><tbody>${ranges}</tbody></table></div><p>${esc(e.notes.at(-1))} ${e.synthetic?"Generated regimes cannot establish an ETF performance edge.":""}</p></details>
    <details class="details"><summary>Replay and cost assumptions</summary><ul>${e.notes.slice(0,-1).map(s=>`<li>${esc(s)}</li>`).join("")}</ul></details>
    </section>` : `<section class="card card-pad">${evidenceError?callout("Evaluation unavailable",esc(evidenceError),true):'<p class="meta" role="status">Running the chronological evaluation…</p>'}${evidenceError?button("Retry","retry"):""}</section>`}
    <section class="card card-pad"><h2 class="section-title">Fund register</h2><p class="meta">Issuer-sourced identities for LSE GBP UCITS ETF listings. See each issuer for current factsheets and eligibility.</p>
    <details class="details"><summary>View ${data.funds.length} supported listings</summary><div class="table-wrap"><table><thead><tr><th>Fund</th><th>ISIN</th><th>Income</th><th>OCF</th></tr></thead><tbody>${data.funds.map(f=>`<tr><td><a href="${esc(f.source)}" target="_blank" rel="noopener">${f.ticker}</a><br><small>${esc(f.name)}</small></td><td>${f.isin}</td><td>${f.income}</td><td>${pct(f.fee,2)}</td></tr>`).join("")}</tbody></table></div></details>
    <p class="meta">The agent’s decision replay uses a seeded factor model for the offline demo. The kit’s synthetic single-instrument challenge exercises the shared RO signal separately.</p>
    <a class="btn secondary" href="/pitch.html" target="_blank" rel="noopener">Open pitch evidence ${icon("right")}</a></section></div>`;
}

function auditPage() {
  return `${head("DECISION RECORD","Audit history","Inspect the latest 150 recorded tool calls, safety decisions and confirmed paper actions for this workspace.")}
    <section class="card card-pad">${stateError?callout("Audit unavailable",esc(stateError),true):""}
    ${data.audit.length?`<div class="table-wrap"><table aria-label="Audit history"><thead><tr><th>Time (UK)</th><th>Event</th><th>Detail</th></tr></thead>
    <tbody>${data.audit.map(event=>`<tr><td>${dt(event.time)}</td><td>${esc(event.action)}</td><td>${esc(event.detail)}${event.run?`<br><small class="mono">${esc(event.run.slice(0,8))}</small>`:""}</td></tr>`).join("")}</tbody></table></div>`:
    `<h2 class="section-title">No activity yet</h2><p class="meta">Run your first analysis to start the decision record.</p>${button("Open portfolio setup","setup","primary","right")}`}</section>`;
}
const prompts = [
  ["Rent at risk","My £1,500 is for rent next term and I have about 1 month saved. My mate says go all in on Nasdaq for 100% a year."],
  ["Summer job savings","I have £2,000 from my summer job that I won't need for rent or bills. I keep 4 months of costs in my current account and won't touch this for 3 years. I'd like balanced growth."],
];
function cited(text, facts = {}) {
  const ids = Object.keys(facts);
  return esc(text).replace(/( ?)\[([A-Za-z0-9_.\-]+)\]/g, (_, space, id) => id === "student" ? `${space}<span class="cite">you said</span>` :
    facts[id] ? `<sup><a class="cite" href="#fact-${id}" title="${esc(facts[id])}">${ids.indexOf(id)+1}</a></sup>` : `${space}<span class="cite bad">${esc(id)}</span>`);
}
function bubble(m) {
  const facts = m.cited || {};
  const list = Object.keys(facts).length ? `<details class="facts"><summary>${Object.keys(facts).length} cited facts</summary><ol>${Object.entries(facts).map(([id,v])=>`<li id="fact-${id}"><span class="mono">${esc(id)}</span> ${esc(v)}</li>`).join("")}</ol></details>` : "";
  return `<div class="bubble ${m.role}"><p class="eyebrow">${m.role === "user" ? "You" : "Coach"}</p><p>${m.role === "user" ? esc(m.content) : cited(m.content, facts)}</p>${list}</div>`;
}
function trailItem({type, value}) {
  if (type === "tool") return `<li class="tool"><span class="agent-icon">${icon("spark")}</span><span><b>${esc(value.name.replace("_"," "))}</b><span class="agent-detail">${esc(value.summary)}</span>
    ${Object.entries(value.quotes || {}).map(([k,q])=>`<span class="agent-detail">${esc(k)} ← “${esc(q)}”</span>`).join("")}
    ${Object.entries(value.rejected || {}).map(([k,r])=>`<span class="agent-detail warn-text">${esc(k)} rejected: ${esc(r)}</span>`).join("")}</span></li>`;
  if (type === "step") {
    const label = (data.tools.find(([key]) => key === value.key) || [, value.key])[1];
    return `<li class="sub"><span class="agent-icon ${value.status === "blocked" ? "failed" : ""}">${value.status === "blocked" ? icon("alert") : icon("tick")}</span><span><b>${esc(label)}</b><span class="agent-detail">${esc(value.detail)}</span></span></li>`;
  }
  if (type === "whatif") {
    const r = value.result;
    const body = r.state === "ready" ? `Sample drawdown ${pct(r.metrics.drawdown)} · annualised ${pct(r.metrics.annualised)} · loss limit ${pct(r.lossLimit)} · ${esc(r.risk)}` : esc(r.reason || r.state);
    return `<li><span class="agent-icon pending">${esc(value.id)}</span><span><b>What-if: ${esc(value.label)}</b><span class="agent-detail">${esc(Object.entries(value.changes).map(([k,v])=>`${k} → ${v}`).join(", "))}</span><span class="agent-detail">${body}. Comparison only, not approvable.</span></span></li>`;
  }
  if (type === "guardian") {
    const ok = value.status === "countersigned";
    return `<li class="guardian"><span class="agent-icon ${ok ? "" : "failed"}">${icon("shield")}</span><span><b>Risk Guardian ${esc(value.status)}</b><span class="agent-detail">${esc(value.agent || "")}${value.fallback ? " · model explanation replaced by the verified template" : ""}</span>
      ${value.checks.map(c=>`<span class="agent-detail">✓ ${esc(c)}</span>`).join("")}${[...value.reasons,...value.grounding].map(c=>`<span class="agent-detail warn-text">✗ ${esc(c)}</span>`).join("")}</span></li>`;
  }
  return "";
}
function coachOutcome() {
  if (!coachFinal) return "";
  const r = coachFinal.result, v = coachFinal.verdict;
  if (r.state === "ready" && v.status === "countersigned" && r.id) return `<section class="card card-pad"><div class="summary-top"><div><p class="eyebrow">COUNTERSIGNED PROPOSAL</p><h2>Ready for your review</h2></div>${pill("Awaiting review","pending")}</div>
    <p class="meta">The Risk Guardian independently reran the analysis and matched digest <span class="mono">${esc(v.digest.slice(0,12))}</span>. Nothing changes until you approve.</p>${button("Review and approve","coach-review","primary","right")}</section>`;
  if (r.state === "veto") return callout(esc(r.riskRule || "Safety veto"), `${esc(r.reason)} No proposal was created.`, true);
  if (r.state === "hold") return callout("Keep current holdings", esc(r.reason));
  if (r.state === "approved") return `<div class="notice closed"><strong>Paper portfolio updated.</strong></div>`;
  if (r.state === "rejected") return `<div class="notice struck"><strong>Proposal rejected.</strong></div>`;
  return callout("No proposal", esc(r.reason || (v.reasons || []).join(" ") || "The Guardian did not countersign this answer."), true);
}
function coachPage() {
  const intro = head("AGENTIC ETF COACH","Rent-safe coach","Describe your situation in your own words. The coach asks for anything safety-critical, runs the verified engine as tools, and an independent Risk Guardian rechecks every figure before you see a proposal.");
  const starters = [...prompts, ...(data.paper ? [["Check in","Check in on my approved paper portfolio. My situation is the same as before."]] : [])];
  return `${intro}<div class="layout"><div class="stack"><section class="card card-pad chat">
    <div class="button-row">${pill(`Coach: ${esc(data.coach.model)}`,"neutral")}${pill(`Checked by: ${esc(data.coach.guardian)}`,"paper")}</div>
    ${chat.length ? chat.map(bubble).join("") : `<p class="meta">Try a fictional situation:</p><div class="button-row">${starters.map(([label],i)=>`<button type="button" class="btn secondary" data-prompt="${i}">${esc(label)}</button>`).join("")}</div>`}
    ${coachBusy ? '<p class="meta" role="status">The coach is working. Tool calls appear in the trace as they finish.</p>' : ""}
    ${coachError ? callout("Coach unavailable",esc(coachError),true) : ""}
    <form id="coach-form" class="chat-form"><label class="field"><span>Your message</span><textarea name="message" rows="3" maxlength="2000" required ${coachBusy||data.paused?"disabled":""} placeholder="e.g. I've saved £800 from tutoring and want to start investing for after uni."></textarea></label>
    <div class="button-row"><button class="btn primary" type="submit" ${coachBusy||data.paused?"disabled":""}>Send${icon("right")}</button>${chat.length ? button("New conversation","coach-reset","secondary","close",coachBusy?"disabled":"") : ""}</div>
    ${data.paused ? callout("Paper actions paused","Resume from the paper portfolio to use the coach.",true) : ""}</form></section>
    ${coachOutcome()}</div>
    <aside class="side-col"><section class="card card-pad"><h2 class="section-title">Agent trace</h2><p class="meta">Every tool call, quote and Guardian check from the latest turn. Also stored in the audit history.</p>
    ${trail.length ? `<ol class="agent-list">${trail.map(trailItem).join("")}</ol>` : '<p class="meta">No tool calls yet.</p>'}</section>${safety()}</aside></div>`;
}
async function sendCoach(text) {
  if (coachBusy || !text.trim()) return;
  chat.push({role:"user",content:text.trim()});
  coachBusy = true; trail = []; coachFinal = null; coachError = "";
  render();
  try {
    const response = await fetch("/api/coach",{method:"POST",headers:{"Content-Type":"application/json","X-Campus-Paper":"1"},
      body:JSON.stringify({messages:chat.slice(-12).map(({role,content})=>({role,content}))})});
    if (!response.ok) throw new Error((await response.json()).error);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", reply = null;
    const handle = line => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "ask") reply = {role:"assistant",content:event.value.text};
      else if (event.type === "answer") reply = {role:"assistant",content:event.value.text,cited:event.value.cited};
      else if (event.type === "final") { coachFinal = event.value; if (coachFinal.result.id) data.pending = coachFinal.result; }
      else if (event.type === "error") coachError = event.value.reason;
      else trail.push(event);
      if (page === "coach") render();
    };
    for (;;) {
      const {done,value} = await reader.read();
      buffer += decoder.decode(value,{stream:!done});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach(handle);
      if (done) break;
    }
    if (buffer) handle(buffer);
    if (reply) chat.push(reply);
    else if (!coachError) coachError = "The coach stream ended without a reply.";
  } catch (err) { coachError = err.message; chat.pop(); }
  finally {
    coachBusy = false;
    if (page === "coach") { render(); $("#coach-form textarea")?.focus(); }
  }
}
function render() {
  renderNav();
  main.innerHTML = {coach:coachPage,setup:setupPage,analysis:analysisPage,paper:paperPage,evidence:evidencePage,audit:auditPage}[page]();
}
function advance(to) {
  step = to;
  visited = Math.max(visited,step);
  render();
  $(".form-title",main)?.setAttribute("tabindex","-1");
  $(".form-title",main)?.focus({preventScroll:true});
  window.scrollTo({top:0,behavior:"instant"});
}
async function analyse() {
  if (busy) return;
  busy = true;
  result = null;
  events = {};
  await navigate("analysis");
  try {
    const response = await fetch("/api/analyse",{method:"POST",headers:{"Content-Type":"application/json","X-Campus-Paper":"1"},body:JSON.stringify(form)});
    if (!response.ok) throw new Error((await response.json()).error);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const handle = line => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "result") { result = event.value; data.pending = result.state==="ready" ? result : null; }
      else events[event.key] = event;
      if (page === "analysis") {
        const node = $("#agent-events");
        if (node) node.innerHTML = new DOMParser().parseFromString(progressPanel(),"text/html").querySelector("ol").innerHTML;
      }
    };
    for (;;) {
      const {done,value} = await reader.read();
      buffer += decoder.decode(value,{stream:!done});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach(handle);
      if (done) break;
    }
    if (buffer) handle(buffer);
    if (!result) throw new Error("The analysis stream ended before a decision arrived.");
  } catch (err) { result = {state:"error",reason:err.message}; }
  finally {
    busy = false;
    if (page === "analysis") {
      render();
      const decision = $(".summary-top h2",main);
      if (decision) { decision.tabIndex = -1; decision.focus({preventScroll:true}); }
    }
  }
}

function showError(selector,message) {
  const node = $(selector);
  if (node) { node.hidden = false; node.textContent = message; }
  else notify(message);
}
async function proposal(operation) {
  if (!result?.id || actionBusy) return;
  const confirmed = $("#confirm-paper")?.checked === true;
  actionBusy = true;
  for (const key of ["approve","reject"]) $(`[data-action="${key}"]`).disabled = true;
  try {
    const outcome = await request("/api/proposal",{operation,id:result.id,confirmed});
    data.pending = null;
    if (operation === "approve") data.paper = outcome.paper;
    result.state = operation === "approve" ? "approved" : "rejected";
    render();
    notify(operation==="approve"?"Paper portfolio updated.":"Proposal rejected.");
  } catch (err) {
    showError("#action-error",err.message);
    const approve = $('[data-action="approve"]');
    const reject = $('[data-action="reject"]');
    if (approve) approve.disabled = !confirmed || data.paused;
    if (reject) reject.disabled = false;
  } finally { actionBusy = false; }
}

document.addEventListener("click", async event => {
  if (!data) return;
  const control = event.target.closest("button");
  if (!control) return;
  if (control.dataset.page) { await navigate(control.dataset.page); return; }
  if (control.dataset.prompt !== undefined) {
    const starters = [...prompts, ["Check in","Check in on my approved paper portfolio. My situation is the same as before."]];
    await sendCoach(starters[Number(control.dataset.prompt)][1]);
    return;
  }
  if (control.dataset.preset && !busy) {
    const preset = data.presets[control.dataset.preset];
    form = structuredClone(preset.form);
    step = 0;
    visited = 0;
    await navigate("setup");
    notify(`${preset.label} loaded.`);
    return;
  }
  if (control.dataset.step !== undefined) {
    const next = Number(control.dataset.step);
    if (next <= step || $("#profile-form").reportValidity()) advance(next);
    return;
  }
  if (control.dataset.remove !== undefined) {
    form.positions.splice(Number(control.dataset.remove),1);
    render();
    return;
  }
  const action = control.dataset.action;
  if (action === "back") advance(step-1);
  else if (action === "add") {
    form.positions.push({identifier:"",quantity:""});
    render();
    $(`[data-row="${form.positions.length-1}"]`)?.focus();
  } else if (["setup","paper","analysis","audit"].includes(action)) await navigate(action);
  else if (action === "approve" || action === "reject") await proposal(action);
  else if (action === "coach-review" && coachFinal) { result = coachFinal.result; events = {}; await navigate("analysis"); }
  else if (action === "coach-reset" && !coachBusy) { chat = []; trail = []; coachFinal = null; coachError = ""; render(); }
  else if (action === "retry") { evidenceError = ""; render(); await getEvidence(); }
  else if (action === "pause" && !actionBusy) {
    actionBusy = true;
    control.disabled = true;
    try {
      Object.assign(data,await request("/api/pause",{paused:!data.paused}));
      stateError = "";
      notify(data.paused?"Paper actions paused.":"Paper actions resumed.");
    } catch (err) { stateError = err.message; }
    finally { actionBusy = false; render(); }
  }
});

document.addEventListener("submit", event => {
  if (event.target.id === "coach-form") {
    event.preventDefault();
    sendCoach(new FormData(event.target).get("message") || "");
    return;
  }
  if (event.target.id !== "profile-form") return;
  event.preventDefault();
  if (step < 2) advance(step+1);
  else analyse();
});

document.addEventListener("input", event => {
  if (!form) return;
  const node = event.target;
  if (node.id === "confirm-paper") {
    const approve = $('[data-action="approve"]');
    if (approve) approve.disabled = !node.checked || data.paused || actionBusy;
  }
  if (node.dataset.row !== undefined) form.positions[Number(node.dataset.row)][node.dataset.field] = node.value;
  const key = node.name;
  if (node.type === "number" && key) form[key] = node.value;
  if (key === "target") $("#snapshot-target").textContent = `${decimal.format(Number(form.target)||0)}%`;
  if (key === "budget") $("#snapshot-budget").textContent = gbp((Number(form.budget)||0)*100);
  if (key === "monthly") $("#snapshot-monthly").textContent = gbp((Number(form.monthly)||0)*100);
  if (key === "runway") $("#affordability").innerHTML = form.essential || Number(form.runway)<3 || Number(form.years)<1 ?
    callout("Affordability check","This profile will trigger a safety veto. Continue to see the reason in the analysis.",true) : "";
});
document.addEventListener("change", async event => {
  if (!form) return;
  const node = event.target;
  if (node.id === "csv-upload") {
    const file = node.files[0];
    if (!file) return;
    if (file.size > 16000) { showError("#form-error","Use a fictional CSV up to 16 KB."); node.value = ""; return; }
    try { form.csv = await file.text(); form.mappingConfirmed = false; render(); }
    catch { showError("#form-error","The CSV file could not be read."); }
    return;
  }
  if (node.type === "checkbox" && node.name) form[node.name] = node.checked;
  if (node.type === "radio" || node.tagName === "SELECT") {
    form[node.name] = ["essential","leverage"].includes(node.name) ? node.value === "true" : node.value;
    if (node.name === "mode" && node.value === "manual" && !form.positions.length) form.positions = [{identifier:"",quantity:""}];
    if (node.name === "mode" || node.name === "leverage" || node.name === "essential") {
      const selector = `[name="${node.name}"]${node.type === "radio" ? ":checked" : ""}`;
      render();
      $(selector)?.focus({preventScroll:true});
    }
  }
});

request("/api/bootstrap").then(payload=>{
  data = payload;
  form = structuredClone(data.defaults);
  result = data.pending;
  if (data.coach?.available) page = "coach";
  render();
}).catch(err => {
  main.innerHTML = `${head("LOCAL WORKSPACE","Campus Index","The local server could not open the workspace.")}${callout("Try reloading this page",esc(err.message),true)}`;
});
