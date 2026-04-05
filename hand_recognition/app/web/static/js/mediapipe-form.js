(function buildGestureCheckboxes() {
  const container = document.getElementById("gesture-checkboxes");
  ALL_GESTURES.forEach(([value, label]) => {
    const checked = INIT_ENABLED.size === 0 || INIT_ENABLED.has(value);
    const wrap = document.createElement("label");
    wrap.style.cssText = "display:flex;align-items:center;gap:.5rem;cursor:pointer;font-size:.85rem;color:#c9d1d9";
    wrap.innerHTML = `<input type="checkbox" name="enabled_gestures" value="${value}"
      style="accent-color:#58a6ff;cursor:pointer" ${checked ? "checked" : ""} />
      <code style="font-size:.8rem">${value}</code><span style="color:#8b949e">— ${label}</span>`;
    container.appendChild(wrap);
  });
})();

document.getElementById("mediapipe-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("mediapipe-status");
  const enabledGestures   = [...document.querySelectorAll("input[name='enabled_gestures']:checked")].map(cb => cb.value);
  const complexityRadio   = e.target.querySelector("input[name='mediapipe_model_complexity']:checked");
  const backendRadio      = e.target.querySelector("input[name='recognizer_backend']:checked");
  const payload = {
    enabled_gestures: enabledGestures,
    mediapipe_min_detection_confidence: parseFloat(document.getElementById("mediapipe_min_detection_confidence").value),
    mediapipe_max_num_hands:            parseInt(document.getElementById("mediapipe_max_num_hands").value, 10),
    mediapipe_model_complexity:         complexityRadio ? parseInt(complexityRadio.value, 10) : 1,
    landmark_sigmoid_k:                 parseFloat(document.getElementById("landmark_sigmoid_k").value),
    landmark_score_threshold:           parseFloat(document.getElementById("landmark_score_threshold").value),
    landmark_thumb_angle:               parseFloat(document.getElementById("landmark_thumb_angle").value),
    recognizer_backend:                 backendRadio ? backendRadio.value : "landmarks",
    gesture_recognizer_model_path:      document.getElementById("gesture_recognizer_model_path").value.trim(),
    invert_hand_labels:                 document.getElementById("mp-invert-hand-labels").checked,
  };
  status.textContent = "Saving…"; status.className = "save-status";
  try {
    const res  = await fetch(URL_CONFIG, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
    const json = await res.json();
    if (res.ok) { status.textContent = "Saved. Restart the add-on to apply model setting changes."; status.className = "save-status ok"; }
    else        { status.textContent = "Error: " + (json.error || res.statusText); status.className = "save-status err"; }
  } catch(err) { status.textContent = "Network error: " + err.message; status.className = "save-status err"; }
});

function updateBackendVisibility() {
  const backend = document.querySelector("input[name='recognizer_backend']:checked")?.value || "landmarks";
  document.getElementById("landmark-settings").style.display = backend === "landmarks"           ? "" : "none";
  document.getElementById("gr-model-section").style.display  = backend === "gesture_recognizer" ? "" : "none";
}
document.querySelectorAll("input[name='recognizer_backend']").forEach(r =>
  r.addEventListener("change", updateBackendVisibility)
);
updateBackendVisibility();

async function refreshModelStatus() {
  const badge = document.getElementById("model-status-badge");
  try {
    const res  = await fetch(URL_GESTURE_MODEL_STATUS);
    const json = await res.json();
    if (json.exists) {
      badge.textContent = `Model present (${json.size_mb} MB)`;
      badge.style.cssText = "font-size:.8rem;color:#3fb950";
    } else {
      badge.textContent = "Model not found";
      badge.style.cssText = "font-size:.8rem;color:#f85149";
    }
  } catch { badge.textContent = ""; }
}
refreshModelStatus();

document.getElementById("btn-download-model").addEventListener("click", async () => {
  const btn    = document.getElementById("btn-download-model");
  const status = document.getElementById("download-status");
  btn.disabled = true; btn.textContent = "Downloading…";
  status.textContent = "Downloading model, this may take a moment…"; status.className = "save-status";
  try {
    const res  = await fetch(URL_GESTURE_MODEL_DOWNLOAD, { method: "POST" });
    const json = await res.json();
    if (res.ok) {
      status.textContent = `Downloaded successfully (${json.size_mb} MB) → ${json.path}`;
      status.className = "save-status ok";
      refreshModelStatus();
    } else {
      status.textContent = "Error: " + (json.error || res.statusText); status.className = "save-status err";
    }
  } catch(err) { status.textContent = "Network error: " + err.message; status.className = "save-status err"; }
  finally { btn.disabled = false; btn.textContent = "Download model"; }
});
