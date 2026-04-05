(function() {
  let webcamStream = null;
  const video       = document.getElementById("debug-webcam");
  const placeholder = document.getElementById("debug-webcam-placeholder");
  const btnStart    = document.getElementById("btn-start-webcam");
  const btnStop     = document.getElementById("btn-stop-webcam");
  const statusEl    = document.getElementById("debug-webcam-status");
  const camSelect   = document.getElementById("debug-cam-select");
  const secureCtx   = !!navigator.mediaDevices;

  function showInsecureWarning() {
    placeholder.innerHTML =
      `<svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="#e3b341" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>` +
      `<span style="color:#e3b341;font-weight:600">Camera unavailable</span>` +
      `<span style="color:#8b949e;font-size:.78rem;max-width:320px;text-align:center">` +
      `Camera access requires a secure context (HTTPS or localhost).<br>` +
      `The add-on is served over HTTP, so the browser blocks <code>getUserMedia</code>.<br>` +
      `Access the UI via <strong>HTTPS</strong> or an SSL-terminated proxy to use this feature.` +
      `</span>`;
    btnStart.disabled  = true;
    camSelect.disabled = true;
  }

  async function populateCameras() {
    if (!secureCtx) { showInsecureWarning(); return; }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cams = devices.filter(d => d.kind === "videoinput");
      const prev = camSelect.value;
      camSelect.innerHTML = "";
      if (!cams.length) {
        const o = document.createElement("option"); o.textContent = "No cameras found";
        camSelect.appendChild(o); return;
      }
      cams.forEach((cam, i) => {
        const o = document.createElement("option");
        o.value = cam.deviceId; o.textContent = cam.label || `Camera ${i + 1}`;
        camSelect.appendChild(o);
      });
      if (prev) camSelect.value = prev;
    } catch(e) { statusEl.textContent = "Cannot enumerate cameras: " + e.message; }
  }

  async function startWebcam() {
    if (!secureCtx) { showInsecureWarning(); return; }
    const deviceId = camSelect.value;
    try {
      statusEl.textContent = "Requesting camera…";
      webcamStream = await navigator.mediaDevices.getUserMedia({
        video: deviceId ? { deviceId: { exact: deviceId } } : true,
        audio: false,
      });
      video.srcObject = webcamStream;
      placeholder.style.display = "none";
      video.style.display = "block";
      btnStart.disabled = true;
      btnStop.disabled  = false;
      const track = webcamStream.getVideoTracks()[0];
      statusEl.textContent = track ? `Active: ${track.label}` : "Camera active";
      await populateCameras();
    } catch(e) { statusEl.textContent = "Error: " + e.message; }
  }

  function stopWebcam() {
    if (webcamStream) { webcamStream.getTracks().forEach(t => t.stop()); webcamStream = null; }
    video.srcObject = null;
    video.style.display = "none";
    placeholder.style.display = "";
    btnStart.disabled = false;
    btnStop.disabled  = true;
    statusEl.textContent = "Camera stopped";
    clearSkeleton();
    if (capturing) { stopAutoTimer(); setCaptureState(false); }
  }

  btnStart.addEventListener("click", startWebcam);
  btnStop.addEventListener("click",  stopWebcam);

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.tab !== "debug") {
        if (webcamStream) stopWebcam();
        if (capturing) setCaptureState(false);
        stopAutoTimer();
      }
    });
  });

  populateCameras();

  // ── Slider ↔ number input sync ────────────────────────────────
  [
    ["debug-sigmoid-k",    "debug-sigmoid-k-num"   ],
    ["debug-score-thresh", "debug-score-thresh-num"],
    ["debug-thumb-angle",  "debug-thumb-angle-num" ],
    ["debug-det-conf",     "debug-det-conf-num"    ],
  ].forEach(([sliderId, numId]) => {
    const s = document.getElementById(sliderId);
    const n = document.getElementById(numId);
    s.addEventListener("input", () => { n.value = s.value; });
    n.addEventListener("input", () => { s.value = n.value; });
  });

  // ── Live analysis ──────────────────────────────────────────────
  const analysisBody  = document.getElementById("debug-analysis-body");
  const btnCapture    = document.getElementById("btn-capture-analyze");
  const intervalSel   = document.getElementById("debug-interval-select");
  const captureCanvas = document.createElement("canvas");
  let   autoTimer     = null;
  let   analyzing     = false;
  let   capturing     = false;

  const FINGER_ORDER = ["pinky", "ring", "middle", "index", "thumb"];

  btnCapture.classList.add("btn-off");

  function fingerBars(fingerScores) {
    return FINGER_ORDER.map(name => {
      const s = fingerScores ? (fingerScores[name] ?? 0) : 0;
      const pct = Math.round(s * 100);
      return `<div class="debug-bar-row">
        <span class="debug-bar-name">${name}</span>
        <div class="debug-bar-track"><div class="debug-bar-fill" style="width:${pct}%"></div></div>
        <span class="debug-bar-pct">${pct}%</span>
      </div>`;
    }).join("");
  }

  function gestureRows(allScores, winner) {
    const scores = allScores && allScores.length
      ? allScores
      : ALL_GESTURES.map(([g]) => ({ gesture: g, score: 0 }));
    return scores.map(g =>
      `<div class="debug-gesture-row${g.gesture === winner ? " winner" : ""}">
        <span class="debug-gesture-name">${GESTURE_EMOJI[g.gesture] || "?"} ${g.gesture.replace(/_/g," ")}</span>
        <span class="debug-gesture-pct">${Math.round(g.score * 100)}%</span>
      </div>`).join("");
  }

  function handCard(label, gesture, scorePct, meta, fingerScores, allScores, winner) {
    return `<div class="debug-hand">
      <div class="debug-hand-header">
        <span class="debug-hand-gesture">${gesture}</span>
        <span class="debug-hand-score">${scorePct}%</span>
        <span class="debug-hand-meta">${label} hand${meta}</span>
      </div>
      <div class="debug-hand-body">
        <div class="debug-hand-section"><div class="debug-section-label">Fingers</div>${fingerBars(fingerScores)}</div>
        <div class="debug-hand-section"><div class="debug-section-label">Gestures</div>${gestureRows(allScores, winner)}</div>
      </div>
    </div>`;
  }

  function renderAnalysis(json) {
    if (!json.detections || !json.detections.length) {
      analysisBody.innerHTML =
        handCard("Left",  "No hand", 0, "", null, null, null) +
        handCard("Right", "No hand", 0, "", null, null, null);
      return;
    }
    analysisBody.innerHTML = json.detections.map(d => {
      const rotation = d.rotation_deg !== undefined ? ` · ${d.rotation_deg}°` : "";
      const facing   = d.facing ? ` · ${d.facing === "camera" ? "facing camera" : "facing away"}` : "";
      const gesture  = `${GESTURE_EMOJI[d.gesture] || "?"} ${d.gesture.replace(/_/g," ")}`;
      return handCard(
        escHtml(d.hand),
        gesture,
        Math.round(d.score * 100),
        rotation + facing,
        d.finger_scores,
        d.all_scores,
        d.gesture,
      );
    }).join("");
  }

  // ── Skeleton overlay ───────────────────────────────────────────
  const skelCanvas = document.getElementById("debug-skeleton");
  const skelCtx    = skelCanvas.getContext("2d");

  const SKEL_GROUPS = [
    { color: "#8b949e", pairs: [[0,1],[0,5],[0,9],[0,13],[0,17],[5,9],[9,13],[13,17]] },
    { color: "#e3b341", pairs: [[1,2],[2,3],[3,4]]             },
    { color: "#58a6ff", pairs: [[5,6],[6,7],[7,8]]             },
    { color: "#3fb950", pairs: [[9,10],[10,11],[11,12]]         },
    { color: "#f78166", pairs: [[13,14],[14,15],[15,16]]        },
    { color: "#d2a8ff", pairs: [[17,18],[18,19],[19,20]]        },
  ];

  function videoRenderRect() {
    const vw = video.videoWidth, vh = video.videoHeight;
    const cw = video.clientWidth, ch = video.clientHeight;
    if (!vw || !vh) return { x: 0, y: 0, w: cw, h: ch };
    const scale = Math.min(cw / vw, ch / vh);
    const rw = vw * scale, rh = vh * scale;
    return { x: (cw - rw) / 2, y: (ch - rh) / 2, w: rw, h: rh };
  }

  function drawSkeleton(detections) {
    skelCanvas.width  = video.clientWidth;
    skelCanvas.height = video.clientHeight;
    skelCtx.clearRect(0, 0, skelCanvas.width, skelCanvas.height);
    const hasLandmarks = detections && detections.some(d => d.landmarks && d.landmarks.length);
    skelCanvas.style.display = hasLandmarks ? "block" : "none";
    if (!hasLandmarks) return;
    const r = videoRenderRect();
    detections.forEach(d => {
      if (!d.landmarks) return;
      const lms = d.landmarks;
      const px = i => r.x + lms[i].x * r.w;
      const py = i => r.y + lms[i].y * r.h;
      skelCtx.lineWidth = 2; skelCtx.lineCap = "round";
      SKEL_GROUPS.forEach(({ color, pairs }) => {
        skelCtx.strokeStyle = color;
        pairs.forEach(([a, b]) => {
          skelCtx.beginPath(); skelCtx.moveTo(px(a), py(a)); skelCtx.lineTo(px(b), py(b)); skelCtx.stroke();
        });
      });
      lms.forEach((lm, i) => {
        skelCtx.beginPath();
        skelCtx.arc(r.x + lm.x * r.w, r.y + lm.y * r.h, i === 0 ? 4 : 3, 0, Math.PI * 2);
        skelCtx.fillStyle = i === 0 ? "#ffffff" : "#58a6ff";
        skelCtx.fill();
      });
    });
  }

  function clearSkeleton() {
    skelCtx.clearRect(0, 0, skelCanvas.width, skelCanvas.height);
    skelCanvas.style.display = "none";
  }

  async function captureAndAnalyze() {
    if (analyzing || !webcamStream) return;
    analyzing = true; btnCapture.disabled = true;
    try {
      captureCanvas.width  = video.videoWidth  || 640;
      captureCanvas.height = video.videoHeight || 480;
      captureCanvas.getContext("2d").drawImage(video, 0, 0);
      const blob = await new Promise(res => captureCanvas.toBlob(res, "image/jpeg", 0.92));
      const fd   = new FormData(); fd.append("image", blob, "frame.jpg");
      const res  = await fetch(URL_DEBUG_ANALYZE, { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) {
        analysisBody.innerHTML = `<div class="debug-analysis-idle" style="color:#f85149">Error: ${escHtml(json.error || res.statusText)}</div>`;
        clearSkeleton();
      } else {
        renderAnalysis(json);
        drawSkeleton(json.detections);
      }
    } catch(e) {
      analysisBody.innerHTML = `<div class="debug-analysis-idle" style="color:#f85149">Network error: ${escHtml(e.message)}</div>`;
      clearSkeleton();
    } finally { analyzing = false; btnCapture.disabled = false; }
  }

  function startAutoTimer() {
    stopAutoTimer();
    autoTimer = setInterval(() => { if (webcamStream) captureAndAnalyze(); }, parseInt(intervalSel.value, 10));
  }
  function stopAutoTimer() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } }

  function setCaptureState(on) {
    capturing = on;
    btnCapture.classList.toggle("btn-on",  on);
    btnCapture.classList.toggle("btn-off", !on);
    btnCapture.textContent = on ? "Stop Capturing" : "Start Capturing";
  }

  btnCapture.addEventListener("click", () => {
    if (capturing) { stopAutoTimer();  setCaptureState(false); }
    else           { startAutoTimer(); setCaptureState(true);  }
  });
  intervalSel.addEventListener("change", () => { if (capturing) startAutoTimer(); });

  // ── Save parameters ────────────────────────────────────────────
  document.getElementById("btn-debug-save-params").addEventListener("click", async () => {
    const st = document.getElementById("debug-params-status");
    const payload = {
      landmark_sigmoid_k:                 parseFloat(document.getElementById("debug-sigmoid-k-num").value),
      landmark_score_threshold:           parseFloat(document.getElementById("debug-score-thresh-num").value),
      landmark_thumb_angle:               parseFloat(document.getElementById("debug-thumb-angle-num").value),
      mediapipe_min_detection_confidence: parseFloat(document.getElementById("debug-det-conf-num").value),
    };
    st.textContent = "Saving…"; st.className = "save-status";
    try {
      const res  = await fetch(URL_CONFIG, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
      const json = await res.json();
      if (res.ok) { st.textContent = "Saved."; st.className = "save-status ok"; }
      else        { st.textContent = "Error: " + (json.error || res.statusText); st.className = "save-status err"; }
    } catch(e) { st.textContent = "Network error: " + e.message; st.className = "save-status err"; }
  });
})();
