"use strict";

/* The demo's Python side. Pyodide boots here, in a worker on its own thread, so loading the
   runtime and generating a queue never freeze the page. The page sends {warm: true} to start
   the runtime early and {id, payload} to generate a queue; the replies are {ready: true} and
   {id, ok, queue|error}. */

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
const PY_FILES = ["algorithm.py", "history.py", "ratings.py"];

let generatePromise = null;

function ensurePython() {
  if (!generatePromise) {
    generatePromise = (async () => {
      if (typeof loadPyodide === "undefined") {
        importScripts(PYODIDE_URL);
      }
      const py = await loadPyodide();
      py.FS.mkdirTree("/harmonica_src");
      for (const name of PY_FILES) {
        const res = await fetch("py/" + name);
        if (!res.ok) {
          throw new Error("missing py/" + name);
        }
        py.FS.writeFile("/harmonica_src/" + name, await res.text());
      }
      const driver = await (await fetch("py/driver.py")).text();
      py.runPython(driver);
      return py.globals.get("generate_queue");
    })();
    generatePromise.catch(() => {
      generatePromise = null;
    });
  }
  return generatePromise;
}

onmessage = async (event) => {
  const msg = event.data || {};
  if (msg.warm) {
    try {
      await ensurePython();
      postMessage({ ready: true });
    } catch {
      /* the page retries when it actually needs a queue */
    }
    return;
  }
  try {
    const generate = await ensurePython();
    postMessage({ id: msg.id, ok: true, queue: generate(msg.payload) });
  } catch (err) {
    postMessage({ id: msg.id, ok: false, error: String(err) });
  }
};
