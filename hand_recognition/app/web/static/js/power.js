const powerMenu = document.getElementById("power-menu");

document.getElementById("power-btn").addEventListener("click", e => {
  e.stopPropagation(); powerMenu.classList.toggle("open");
});
document.addEventListener("click", () => powerMenu.classList.remove("open"));

function showRestartCountdown() {
  const restartModal = document.getElementById("restart-modal");
  const countdownEl  = document.getElementById("restart-countdown");
  restartModal.classList.remove("hidden");
  let n = 15;
  countdownEl.textContent = n;
  const timer = setInterval(() => {
    n--; countdownEl.textContent = n;
    if (n <= 0) { clearInterval(timer); location.reload(); }
  }, 1000);
  document.getElementById("btn-reload-now").addEventListener("click", () => {
    clearInterval(timer); location.reload();
  }, {once: true});
}

document.getElementById("btn-restart").addEventListener("click", () => {
  powerMenu.classList.remove("open");
  showConfirm("Restart", "Restart the add-on?", async () => {
    showRestartCountdown();
    fetch(URL_RESTART, {method:"POST"});
  });
});

document.getElementById("btn-shutdown").addEventListener("click", () => {
  powerMenu.classList.remove("open");
  showConfirm("Shutdown", "Stop the add-on? You will need to start it manually.", async () => {
    await fetch(URL_SHUTDOWN, {method:"POST"});
  });
});
