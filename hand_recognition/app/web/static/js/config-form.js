document.getElementById("config-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("config-status");
  const data = Object.fromEntries(new FormData(e.target).entries());
  const modeRadio = e.target.querySelector("input[name='frigate_snapshot_mode']:checked");
  if (modeRadio) data["frigate_snapshot_mode"] = modeRadio.value;
  const cropBox = e.target.querySelector("input[name='frigate_snapshot_crop']");
  if (cropBox) data["frigate_snapshot_crop"] = cropBox.checked ? 1 : 0;
  ["mqtt_port","web_ui_port","max_snapshots","frigate_snapshot_quality","frigate_snapshot_height"]
    .forEach(k => { if (k in data) data[k] = parseInt(data[k], 10); });
  status.textContent = "Saving…"; status.className = "save-status";
  try {
    const res  = await fetch(URL_CONFIG, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data) });
    const json = await res.json();
    if (res.ok) { status.textContent = "Saved."; status.className = "save-status ok"; }
    else        { status.textContent = "Error: "+(json.error||res.statusText); status.className = "save-status err"; }
  } catch(err) { status.textContent = "Network error: "+err.message; status.className = "save-status err"; }
});
