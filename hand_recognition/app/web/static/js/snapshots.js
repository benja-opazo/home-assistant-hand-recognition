function snapImageUrl(id)  { return URL_SNAPSHOTS.replace(/\/api\/snapshots.*/, `/api/snapshots/${id}/image`); }
function snapDeleteUrl(id) { return URL_SNAPSHOTS.replace(/\/api\/snapshots.*/, `/api/snapshots/${id}`); }

let allSnaps = [], visibleSnaps = [], newSnapIds = new Set(), isFirstLoad = true;
let activeGestureFilter = "", activeCamFilter = "";
let modalSnap = null, modalSnapIndex = -1;
let selectedIds = new Set();

const gestureFilter = document.getElementById("gesture-filter");
const camFilter     = document.getElementById("snap-cam-filter");
const grid          = document.getElementById("snapshots-grid");
const bulkBar       = document.getElementById("bulk-bar");
const bulkCount     = document.getElementById("bulk-count");

function updateBulkBar() {
  const n = selectedIds.size;
  bulkCount.textContent = n + " selected";
  bulkBar.classList.toggle("visible", n > 0);
  grid.classList.toggle("selection-active", n > 0);
}

document.getElementById("bulk-deselect").addEventListener("click", () => {
  selectedIds.clear();
  grid.querySelectorAll(".snap-card").forEach(c => {
    c.classList.remove("snap-selected");
    c.querySelector(".snap-check").checked = false;
  });
  updateBulkBar();
});

document.getElementById("bulk-delete").addEventListener("click", async () => {
  const ids = [...selectedIds];
  await Promise.all(ids.map(id => fetch(snapDeleteUrl(id), {method:"DELETE"})));
  allSnaps = allSnaps.filter(x => !ids.includes(x.id));
  selectedIds.clear();
  rebuildSnapFilters(); renderGrid();
});

document.getElementById("bulk-download").addEventListener("click", async () => {
  const ids = [...selectedIds];
  const res = await fetch(URL_SNAPS_DOWNLOAD, {
    method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ids}),
  });
  if (!res.ok) { alert("Download failed"); return; }
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "snapshots.zip"; a.click();
  URL.revokeObjectURL(url);
});

gestureFilter.addEventListener("change", () => { activeGestureFilter = gestureFilter.value; renderGrid(); });
camFilter.addEventListener("change",     () => { activeCamFilter     = camFilter.value;     renderGrid(); });
document.getElementById("btn-refresh-snaps").addEventListener("click", loadSnapshots);
document.getElementById("btn-clear-snaps").addEventListener("click", () => {
  showConfirm("Clear all snapshots", "Delete all snapshots? This cannot be undone.", async () => {
    await fetch(URL_SNAPS_CLEAR, { method:"DELETE" });
    allSnaps = []; selectedIds.clear(); renderGrid();
  });
});

async function loadSnapshots() {
  const prevIds = new Set(allSnaps.map(s => s.id));
  const res = await fetch(URL_SNAPSHOTS);
  allSnaps  = await res.json();
  if (isFirstLoad) { newSnapIds = new Set(); isFirstLoad = false; }
  else { newSnapIds = new Set(allSnaps.filter(s => !prevIds.has(s.id)).map(s => s.id)); }
  rebuildSnapFilters(); renderGrid();
}

function rebuildSnapFilters() {
  const gestures = new Set(), cameras = new Set();
  allSnaps.forEach(s => {
    cameras.add(s.camera);
    if (!s.detections.length) gestures.add("__none__");
    else s.detections.forEach(d => gestures.add(d.gesture));
  });
  const curG = gestureFilter.value;
  gestureFilter.innerHTML = '<option value="">All</option><option value="__none__">No detection</option>';
  [...gestures].filter(g => g !== "__none__").sort().forEach(g => {
    const o = document.createElement("option"); o.value = g;
    o.textContent = `${GESTURE_EMOJI[g]||"?"} ${g.replace(/_/g," ")}`;
    gestureFilter.appendChild(o);
  });
  gestureFilter.value = curG;
  const curC = camFilter.value;
  camFilter.innerHTML = '<option value="">All</option>';
  [...cameras].sort().forEach(c => {
    const o = document.createElement("option"); o.value = c; o.textContent = c;
    camFilter.appendChild(o);
  });
  camFilter.value = curC;
}

function matchSnap(s) {
  if (activeCamFilter && s.camera !== activeCamFilter) return false;
  if (!activeGestureFilter) return true;
  if (activeGestureFilter === "__none__") return !s.detections.length;
  return s.detections.some(d => d.gesture === activeGestureFilter);
}

function gestureTagsHtml(d) {
  if (!d.length) return `<span class="gesture-tag none">No hands</span>`;
  return d.map(x =>
    `<span class="gesture-tag detected">${GESTURE_EMOJI[x.gesture]||"?"} ${x.gesture.replace(/_/g," ")} <span style="opacity:.6;font-weight:400">${Math.round(x.score*100)}%</span></span>`
  ).join("");
}

function renderGrid() {
  visibleSnaps = allSnaps.filter(matchSnap);
  if (!visibleSnaps.length) {
    grid.innerHTML = `<div class="snap-empty">No snapshots${allSnaps.length?" match the current filter":" yet"}.</div>`;
    return;
  }
  grid.innerHTML = "";
  visibleSnaps.forEach(s => {
    const card = document.createElement("div"); card.className = "snap-card";
    if (selectedIds.has(s.id)) card.classList.add("snap-selected");
    if (newSnapIds.has(s.id))  card.classList.add("snap-new");
    card.innerHTML = `
      <div class="snap-check-wrap">
        <input type="checkbox" class="snap-check" title="Select" ${selectedIds.has(s.id) ? "checked" : ""} />
      </div>
      <img src="${snapImageUrl(s.id)}" alt="snapshot" loading="lazy" />
      <div class="snap-info">
        <div class="snap-camera">${escHtml(s.camera)}</div>
        <div class="snap-time">${s.timestamp}</div>
        <div class="snap-gesture-row">${gestureTagsHtml(s.detections)}</div>
      </div>
      <div class="snap-card-actions">
        <button class="snap-icon-btn dl"    title="Download">↓</button>
        <button class="snap-icon-btn reclf" title="Reclassify">↺</button>
        <button class="snap-icon-btn del"   title="Delete">✕</button>
      </div>`;
    card.querySelector(".snap-check").addEventListener("change", e => {
      e.stopPropagation();
      if (e.target.checked) { selectedIds.add(s.id);    card.classList.add("snap-selected"); }
      else                  { selectedIds.delete(s.id); card.classList.remove("snap-selected"); }
      updateBulkBar();
    });
    card.addEventListener("click", e => {
      if (e.target.closest(".snap-card-actions") || e.target.closest(".snap-check-wrap")) return;
      if (selectedIds.size > 0) {
        const cb = card.querySelector(".snap-check");
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event("change", {bubbles: false}));
      } else { openModal(s); }
    });
    card.querySelector(".dl").addEventListener("click",  e => { e.stopPropagation(); downloadSnap(s); });
    card.querySelector(".reclf").addEventListener("click", e => {
      e.stopPropagation();
      const btn = e.currentTarget;
      btn.disabled = true; btn.textContent = "…";
      reclassifySnap(s.id).then(json => {
        card.querySelector(".snap-gesture-row").innerHTML = reclassifyTagsHtml(json);
      }).catch(err => {
        card.querySelector(".snap-gesture-row").innerHTML =
          `<span class="gesture-tag none" title="${escHtml(err.message)}">Error</span>`;
      }).finally(() => { btn.disabled = false; btn.textContent = "↺"; });
    });
    card.querySelector(".del").addEventListener("click", e => {
      e.stopPropagation();
      showConfirm("Delete snapshot", "Delete this snapshot? This cannot be undone.", async () => {
        await fetch(snapDeleteUrl(s.id), {method:"DELETE"});
        allSnaps = allSnaps.filter(x => x.id !== s.id);
        selectedIds.delete(s.id);
        rebuildSnapFilters(); renderGrid();
      });
    });
    grid.appendChild(card);
  });
  updateBulkBar();
}

function downloadSnap(s) {
  const a = document.createElement("a"); a.href = snapImageUrl(s.id);
  a.download = `${s.camera}_${s.timestamp.replace(/[: ]/g,"-")}.jpg`; a.click();
}

// ── Snapshot modal ───────────────────────────────────────────────
const modal    = document.getElementById("snapshot-modal");
const modalImg = document.getElementById("modal-img");

function updateNavArrows() {
  document.getElementById("modal-prev").disabled = modalSnapIndex <= 0;
  document.getElementById("modal-next").disabled = modalSnapIndex >= visibleSnaps.length - 1;
}

function openModal(s) {
  modalSnap      = s;
  modalSnapIndex = visibleSnaps.findIndex(x => x.id === s.id);
  document.getElementById("modal-title").textContent = `${s.camera} — ${s.timestamp}`;
  modalImg.src = snapImageUrl(s.id);
  const gt = s.detections.length
    ? s.detections.map(d=>`${GESTURE_EMOJI[d.gesture]||"?"} ${d.gesture.replace(/_/g," ")} (${d.hand}, ${d.score})`).join(", ")
    : "None";
  document.getElementById("modal-meta").innerHTML = `
    <div class="meta-row"><span class="meta-label">Camera</span><span class="meta-val">${escHtml(s.camera)}</span></div>
    <div class="meta-row"><span class="meta-label">Time</span><span class="meta-val">${s.timestamp}</span></div>
    <div class="meta-row"><span class="meta-label">Frigate score</span><span class="meta-val">${s.frigate_score}</span></div>
    <div class="meta-row"><span class="meta-label">Event ID</span><span class="meta-val" style="font-size:.75rem;word-break:break-all">${escHtml(s.event_id)}</span></div>
    <div class="meta-row"><span class="meta-label">Gesture(s)</span><span class="meta-val">${gt}</span></div>`;
  updateNavArrows();
  modal.classList.remove("hidden");
}

function closeModal() { modal.classList.add("hidden"); modalSnap = null; modalImg.src = ""; }

function navigateModal(dir) {
  const idx = modalSnapIndex + dir;
  if (idx >= 0 && idx < visibleSnaps.length) openModal(visibleSnaps[idx]);
}

document.getElementById("modal-prev").addEventListener("click", () => navigateModal(-1));
document.getElementById("modal-next").addEventListener("click", () => navigateModal(1));
document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-backdrop").addEventListener("click", closeModal);
document.addEventListener("keydown", e => {
  if (modal.classList.contains("hidden")) return;
  if (e.key === "Escape")      closeModal();
  if (e.key === "ArrowLeft")   navigateModal(-1);
  if (e.key === "ArrowRight")  navigateModal(1);
});

let touchStartX = 0;
modal.addEventListener("touchstart", e => { touchStartX = e.touches[0].clientX; }, {passive:true});
modal.addEventListener("touchend",   e => {
  const dx = e.changedTouches[0].clientX - touchStartX;
  if (Math.abs(dx) > 50) navigateModal(dx < 0 ? 1 : -1);
}, {passive:true});

document.getElementById("modal-download").addEventListener("click", () => { if (modalSnap) downloadSnap(modalSnap); });
document.getElementById("modal-delete").addEventListener("click", () => {
  if (!modalSnap) return;
  showConfirm("Delete snapshot", "Delete this snapshot? This cannot be undone.", async () => {
    await fetch(snapDeleteUrl(modalSnap.id), {method:"DELETE"});
    allSnaps = allSnaps.filter(x => x.id !== modalSnap.id);
    rebuildSnapFilters(); renderGrid(); closeModal();
  });
});

async function reclassifySnap(id) {
  const url = URL_SNAPSHOTS.replace(/\/api\/snapshots.*/, `/api/snapshots/${id}/reclassify`);
  const res  = await fetch(url, {method:"POST"});
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); }
  catch(_) { throw new Error(`Server returned non-JSON (${res.status}): ${text.slice(0, 300)}`); }
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}

function reclassifyTagsHtml(json) {
  if (!json.detections.length) return `<span class="gesture-tag none">No hands</span>`;
  return json.detections.map(d => {
    const winner = `${GESTURE_EMOJI[d.gesture]||"?"} ${d.gesture.replace(/_/g," ")} <span style="opacity:.6;font-weight:400">${Math.round(d.score*100)}%</span>`;
    if (!json.debug || !d.all_scores) return `<span class="gesture-tag detected">${winner}</span>`;
    const fingerRows = d.finger_scores
      ? Object.entries(d.finger_scores).map(([name, s]) =>
          `<span style="display:flex;justify-content:space-between;gap:1rem">`+
          `<span style="opacity:.7">${name}</span><span>${Math.round(s*100)}%</span></span>`
        ).join("")
      : "";
    const gestureRows = d.all_scores.map(g =>
      `<span style="display:flex;justify-content:space-between;gap:1rem;${g.gesture===d.gesture?"color:#58a6ff":""}">`+
      `<span>${GESTURE_EMOJI[g.gesture]||"?"} ${g.gesture.replace(/_/g," ")}</span>`+
      `<span>${Math.round(g.score*100)}%</span></span>`
    ).join("");
    const rotation = d.rotation_deg !== undefined
      ? `<span style="display:block;opacity:.55;font-size:.7rem;margin-bottom:.3rem">${d.hand} hand · rotation ${d.rotation_deg}°</span>`
      : `<span style="display:block;opacity:.55;font-size:.7rem;margin-bottom:.3rem">${d.hand} hand</span>`;
    return `<span class="gesture-tag detected" style="display:block;padding:.4rem .5rem">${winner}`+
           `<span style="display:block;margin-top:.4rem;font-size:.72rem;font-weight:400;opacity:.85">`+
           `${rotation}`+
           `<span style="display:block;opacity:.5;font-size:.68rem;margin:.2rem 0 .1rem">fingers</span>${fingerRows}`+
           `<span style="display:block;opacity:.5;font-size:.68rem;margin:.35rem 0 .1rem">gestures</span>${gestureRows}`+
           `</span></span>`;
  }).join("");
}

document.getElementById("modal-reclassify").addEventListener("click", async () => {
  if (!modalSnap) return;
  const btn = document.getElementById("modal-reclassify");
  btn.disabled = true; btn.textContent = "Classifying…";
  try {
    const json = await reclassifySnap(modalSnap.id);
    const row  = document.querySelector("#modal-meta .meta-row:last-child");
    if (row) row.querySelector(".meta-val").innerHTML =
      reclassifyTagsHtml(json) +
      `<span style="font-size:.75rem;color:#8b949e;margin-left:.4rem">reclassified</span>`;
  } catch(err) { alert("Reclassify failed: " + err.message); }
  finally { btn.disabled = false; btn.textContent = "Reclassify"; }
});

// ── Auto-refresh ─────────────────────────────────────────────────
loadSnapshots();
setInterval(() => {
  if (document.getElementById("tab-snapshots").classList.contains("active")) loadSnapshots();
}, 10000);
