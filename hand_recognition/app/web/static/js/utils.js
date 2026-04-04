const GESTURE_EMOJI = {
  fist:"✊", thumbs_up:"👍", pointing:"☝️", peace:"✌️", open_palm:"🖐️",
  four_fingers:"🤚", rock_on:"🤘", call_me:"🤙", pinky:"🤙", three_fingers:"🤟", unknown:"🤔",
};

const COMPARATORS = ["==","!=",">","<",">=","<=","contains","not contains"];

function escHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Confirm modal ───────────────────────────────────────────────
const confirmModal = document.getElementById("confirm-modal");
let confirmCallback = null;

function showConfirm(title, message, onConfirm) {
  document.getElementById("confirm-title").textContent   = title;
  document.getElementById("confirm-message").textContent = message;
  confirmCallback = onConfirm;
  confirmModal.classList.remove("hidden");
}

function closeConfirm() { confirmModal.classList.add("hidden"); confirmCallback = null; }

document.getElementById("confirm-close").addEventListener("click", closeConfirm);
document.getElementById("confirm-cancel").addEventListener("click", closeConfirm);
document.getElementById("confirm-backdrop").addEventListener("click", closeConfirm);
document.getElementById("confirm-ok").addEventListener("click", () => {
  const cb = confirmCallback; closeConfirm(); if (cb) cb();
});
