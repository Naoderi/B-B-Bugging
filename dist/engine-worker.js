"use strict";
const runtimeURL = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
self.onmessage = async ({data}) => {
  try {
    importScripts(runtimeURL + "pyodide.js");
    const engine = await loadPyodide({indexURL:runtimeURL});
    await engine.loadPackage("tzdata");
    engine.FS.mkdirTree("/campus/evidence/multi-seed");
    const files = ["agent.py","market.py","strategy.py","verifier.py","coach.py","planner.py","guardian.py","tools.py","backtest.py","evidence/multi-seed/summary.json"];
    await Promise.all(files.map(async name => {
      const response = await fetch(new URL("engine/"+name,self.location.href));
      if (!response.ok) throw new Error("Engine module unavailable");
      engine.FS.writeFile("/campus/"+name,await response.text());
    }));
    engine.globals.set("campus_inputs",JSON.stringify(data.input));
    engine.globals.set("campus_existing",JSON.stringify(data.existing));
    engine.globals.set("campus_mode",data.mode);
    engine.globals.set("campus_report",line=>self.postMessage({kind:"event",payload:JSON.parse(line)}));
    engine.runPython(`
import sys, json
sys.path.insert(0, '/campus')
import agent, coach
from planner import Planner
inputs = json.loads(campus_inputs)
existing = json.loads(campus_existing)
events = coach.converse(inputs.get('messages'), existing, Planner()) if campus_mode == 'coach' else agent.work(inputs, existing)
for event in events:
    campus_report(json.dumps(event, ensure_ascii=False, allow_nan=False))
`);
    self.postMessage({kind:"complete"});
  } catch (error) { console.error("Campus engine", String(error)); self.postMessage({kind:"error",message:String(error)}); }
};
