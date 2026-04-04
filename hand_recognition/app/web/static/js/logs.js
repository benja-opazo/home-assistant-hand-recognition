const logContainer = document.getElementById("log-container");
const logStatus    = document.getElementById("log-status");
const sourceFilter = document.getElementById("source-filter");
let paused = false, activeLevels = new Set(["DEBUG","INFO","WARNING","ERROR","CRITICAL"]);
let activeSource = "", allEntries = [], knownSources = new Set(), entryCount = 0;

document.querySelectorAll(".level-badge").forEach(badge => {
  badge.addEventListener("click", () => {
    const lvl = badge.dataset.level;
    if (activeLevels.has(lvl)) { activeLevels.delete(lvl); badge.classList.remove("active"); }
    else                       { activeLevels.add(lvl);    badge.classList.add("active"); }
    rerenderLogs();
  });
});
sourceFilter.addEventListener("change", () => { activeSource = sourceFilter.value; rerenderLogs(); });

function logOk(e) { return activeLevels.has(e.level) && (!activeSource || e.source === activeSource); }

function makeLogRow(e) {
  const row = document.createElement("div"); row.className = `log-entry ${e.level}`;
  row.innerHTML = `<span class="log-ts">${e.timestamp.slice(11)}</span><span class="log-lvl">${e.level}</span><span class="log-src" title="${e.source}">${e.source}</span><span class="log-msg">${escHtml(e.message)}</span>`;
  return row;
}

function rerenderLogs() {
  logContainer.innerHTML = "";
  allEntries.filter(logOk).forEach(e => logContainer.appendChild(makeLogRow(e)));
  if (!paused) logContainer.scrollTop = logContainer.scrollHeight;
}

function appendLogEntry(e) {
  allEntries.push(e);
  if (!knownSources.has(e.source)) {
    knownSources.add(e.source);
    const opt = document.createElement("option"); opt.value = e.source; opt.textContent = e.source;
    sourceFilter.appendChild(opt);
  }
  if (!logOk(e)) return;
  logContainer.appendChild(makeLogRow(e));
  entryCount++;
  if (!paused) logContainer.scrollTop = logContainer.scrollHeight;
  logStatus.textContent = `${entryCount} entries`;
}

document.getElementById("btn-pause").addEventListener("click", function() {
  paused = !paused; this.textContent = paused ? "Resume" : "Pause"; this.classList.toggle("active", paused);
  if (!paused) logContainer.scrollTop = logContainer.scrollHeight;
});

document.getElementById("btn-clear-logs").addEventListener("click", () => {
  showConfirm("Clear logs", "Clear all log entries?", async () => {
    await fetch(URL_LOGS_CLEAR, {method:"DELETE"});
    allEntries = []; knownSources.clear(); entryCount = 0; logContainer.innerHTML = "";
    sourceFilter.innerHTML = '<option value="">All sources</option>'; activeSource = "";
    logStatus.textContent = "Cleared";
  });
});

document.getElementById("btn-download-logs").addEventListener("click", () => {
  const lines = allEntries.filter(logOk).map(e => `${e.timestamp} [${e.level}] ${e.source}: ${e.message}`).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines], {type:"text/plain"}));
  a.download = `hand-recognition-${new Date().toISOString().slice(0,19).replace(/:/g,"-")}.log`;
  a.click();
});

function connectStream() {
  logStatus.textContent = "Connecting…";
  const es = new EventSource(URL_LOGS_STREAM);
  es.onopen    = () => { logStatus.textContent = `${entryCount} entries`; };
  es.onmessage = e  => { try { appendLogEntry(JSON.parse(e.data)); } catch(_){} };
  es.onerror   = () => { logStatus.textContent = "Disconnected — reconnecting in 3 s…"; es.close(); setTimeout(connectStream, 3000); };
}
connectStream();
