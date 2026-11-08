"use strict";
(() => {
  const nativeFetch = window.fetch.bind(window);
  const storageKey = "campus-index-public-v2";
  const stamp = () => new Date().toISOString();
  const response = (data, status = 200) => Response.json(data, {status});
  let state = {paused:false, paper:null, pending:null, audit:[]};
  let latestRun = null;
  let labels = new Map();
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved && Array.isArray(saved.audit)) state = saved;
  } catch {}
  function record(action, detail, run = null) {
    state.audit = [{time:stamp(),action,detail,run}, ...state.audit].slice(0,150);
    try { sessionStorage.setItem(storageKey, JSON.stringify(state)); } catch {}
  }
  function runEngine(input, mode) {
    if (state.paused) return response({error:"Paper actions are paused. Resume them to continue."},422);
    const run = crypto.randomUUID();
    latestRun = run;
    state.pending = null;
    record(mode === "coach" ? "Coach turn started" : "Analysis started", "Running locally in this browser with synthetic data.",run);
    let worker, closed = false, timer;
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        const emit = event => { if (!closed) controller.enqueue(encoder.encode(JSON.stringify(event)+"\n")); };
        const close = () => {
          if (closed) return;
          closed = true;
          clearTimeout(timer);
          worker?.terminate();
          controller.close();
        };
        const fail = () => {
          record("Engine unavailable","The browser engine could not complete. Try again.",run);
          emit(mode === "coach" ? {type:"error",value:{reason:"The browser engine could not load or complete. Please try again."}} :
            {type:"result",value:{state:"error",reason:"The browser engine could not load or complete. Please try again."}});
          close();
        };
        timer = setTimeout(fail,90000);
        try {
          worker = new Worker(new URL("engine-worker.js",document.baseURI));
          worker.onerror = fail;
          worker.onmessage = ({data}) => {
            if (closed) return;
            if (data.kind === "error") return fail();
            if (data.kind === "complete") return close();
            const [kind, value, detail] = data.payload;
            if (state.paused || latestRun !== run) return fail();
            if (mode === "coach") {
              if (kind === "final") {
                const result = value.result;
                value.verdict.agent = "in-browser Guardian";
                if (result.state === "ready" && value.verdict.status === "countersigned") {
                  state.pending = {...result,id:run,created:stamp(),countersignature:value.verdict,coachQuotes:value.quotes};
                  value.result = state.pending;
                }
                record("Coach decision recorded",result.state,run);
              } else if (kind === "tool") record("Coach tool • " + value.name,value.summary,run);
              else if (kind === "guardian") record("Guardian " + value.status,"Independent calculations checked.",run);
              emit({type:kind,value});
            } else if (kind === "result") {
              if (value.state === "ready") state.pending = {...value,id:run,created:stamp()};
              record("Decision recorded",value.state,run);
              emit({type:"result",value:state.pending ?? value});
            } else {
              record(labels.get(value) ?? value,detail,run);
              emit({type:kind,key:value,detail});
            }
          };
          worker.postMessage({input,existing:state.paper,mode});
        } catch { fail(); }
      },
      cancel() { closed = true; clearTimeout(timer); worker?.terminate(); }
    });
    return new Response(stream,{headers:{"Content-Type":"application/x-ndjson"}});
  }
  function proposal(input) {
    const p = state.pending;
    const blocked = error => response({error},422);
    if (!p || p.id !== input.id) return blocked("This proposal is no longer available. Run a new analysis.");
    if (input.operation === "reject") {
      state.pending = null;
      record("Proposal rejected","The student declined the proposed changes.",p.id);
      return response({paper:state.paper});
    }
    if (input.operation !== "approve" || input.confirmed !== true) return blocked("Explicit human confirmation is required.");
    if (state.paused) return blocked("Paper actions are paused.");
    if (p.state !== "ready" || !p.verified?.length || p.portfolioLeverage !== 1 || p.exposure > 1+1e-10 || p.provenance?.synthetic !== true)
      return blocked("A verified unlevered paper proposal is required.");
    state.paper = Object.fromEntries(["positions","cash","nav","fee","exposure","provenance"].map(k=>[k,p[k]]));
    Object.assign(state.paper,{approved:stamp(),proposalId:p.id});
    state.pending = null;
    record("Paper allocation applied","Student approved fictional positions in this browser tab.",p.id);
    return response({paper:state.paper});
  }
  window.fetch = async (path, options = {}) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) return nativeFetch(path,options);
    if (path === "/api/bootstrap") {
      const result = await nativeFetch(new URL("data/bootstrap.json",document.baseURI));
      if (!result.ok) return response({error:"Could not load the demo."},503);
      const data = await result.json();
      labels = new Map(data.tools);
      return response({...data,...state});
    }
    if (path === "/api/state") return response(state);
    if (path === "/api/evidence") return nativeFetch(new URL("data/evidence.json",document.baseURI));
    if (typeof options.body !== "string" || new TextEncoder().encode(options.body).length > 32000)
      return response({error:"Request is empty or too large."},422);
    let input;
    try { input = JSON.parse(options.body); } catch { return response({error:"Invalid request."},422); }
    if (path === "/api/coach") return runEngine(input,"coach");
    if (path === "/api/analyse") return runEngine(input,"analyse");
    if (path === "/api/proposal") return proposal(input);
    if (path === "/api/pause" && typeof input.paused === "boolean") {
      latestRun = null;
      state.paused = input.paused;
      record(state.paused ? "Paper actions paused" : "Paper actions resumed","The student changed the stop control.");
      return response(state);
    }
    return response({error:"Unknown action."},404);
  };
})();
