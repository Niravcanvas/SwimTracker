let startTime = null;
let elapsed = 0;       // in ms
let running = false;
let rafId = null;

const displayTime = document.getElementById("displayTime");
const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnReset = document.getElementById("btnReset");
const timeMs = document.getElementById("timeMs");

const laps = document.getElementById("laps");
const poolLen = document.getElementById("poolLen");
const distancePreview = document.getElementById("distancePreview");

// optional (exists in upgraded UI)
const timePreview = document.getElementById("timePreview");

function fmt(ms) {
  const total = ms / 1000;
  const m = Math.floor(total / 60);
  const s = total - m * 60;
  const ss = s.toFixed(2).padStart(5, "0"); // "SS.xx"
  return `${String(m).padStart(2, "0")}:${ss}`;
}

function setButtons() {
  if (!btnStart || !btnStop || !btnReset) return;
  btnStart.disabled = running;
  btnStop.disabled = !running;
  btnReset.disabled = running && elapsed === 0; // can reset any time, but keep nice UX
}

function syncOutputs(ms) {
  if (displayTime) displayTime.textContent = fmt(ms);
  if (timeMs) timeMs.value = String(Math.floor(ms));
  if (timePreview) timePreview.textContent = fmt(ms);
}

function tick(now) {
  if (!running) return;
  const diff = now - startTime;
  const current = elapsed + diff;
  syncOutputs(current);
  rafId = requestAnimationFrame(tick);
}

btnStart?.addEventListener("click", () => {
  if (running) return;
  running = true;
  startTime = performance.now();
  setButtons();
  rafId = requestAnimationFrame(tick);
});

btnStop?.addEventListener("click", () => {
  if (!running) return;
  running = false;

  const diff = performance.now() - startTime;
  elapsed += diff;

  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  startTime = null;

  syncOutputs(elapsed);
  setButtons();
});

btnReset?.addEventListener("click", () => {
  running = false;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;

  startTime = null;
  elapsed = 0;

  syncOutputs(0);
  setButtons();
});

function updateDistance() {
  if (!distancePreview) return;
  const l = parseInt(laps?.value || "0", 10);
  const pl = parseFloat(poolLen?.value || "25");
  const dist = (l > 0 ? l : 0) * (pl > 0 ? pl : 0);

  // Support both old and new UI text
  // If preview element already contains "Distance:", keep that style
  if (distancePreview.textContent?.toLowerCase().includes("distance")) {
    distancePreview.textContent = `Distance: ${dist.toFixed(0)} m`;
  } else {
    distancePreview.textContent = `${dist.toFixed(0)} m`;
  }
}

laps?.addEventListener("input", updateDistance);
poolLen?.addEventListener("change", updateDistance);

// init
syncOutputs(0);
updateDistance();
setButtons();