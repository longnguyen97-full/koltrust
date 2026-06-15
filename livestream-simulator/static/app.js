const state = {
  bundle: null,
  kols: [],
  activeKolId: "yt_beauty_02",
  frame: 0,
  particles: Array.from({ length: 38 }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: 1 + Math.random() * 3,
    s: 0.2 + Math.random() * 0.8,
  })),
};

const canvas = document.getElementById("liveCanvas");
const ctx = canvas.getContext("2d");
const chatList = document.getElementById("chatList");
const ids = {
  viewerPill: document.getElementById("viewerPill"),
  trustBadge: document.getElementById("trustBadge"),
  likes: document.getElementById("likes"),
  shares: document.getElementById("shares"),
  comments: document.getElementById("comments"),
  botRisk: document.getElementById("botRisk"),
  sentiment: document.getElementById("sentiment"),
  liveId: document.getElementById("liveId"),
  kolName: document.getElementById("kolName"),
  liveTitle: document.getElementById("liveTitle"),
  avatar: document.getElementById("avatar"),
  kolSelect: document.getElementById("kolSelect"),
  modeSelect: document.getElementById("modeSelect"),
  resetButton: document.getElementById("resetButton"),
  bundleLink: document.getElementById("bundleLink"),
  featuresLink: document.getElementById("featuresLink"),
  eventsLink: document.getElementById("eventsLink"),
};

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function drawLivestream() {
  const width = canvas.width;
  const height = canvas.height;
  const bundle = state.bundle;
  const risk = bundle ? bundle.metrics.bot_probability : 0;
  state.frame += 1;

  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#18352e");
  gradient.addColorStop(0.45, risk > 0.45 ? "#49303a" : "#6a4734");
  gradient.addColorStop(1, "#182632");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "rgba(255, 246, 214, 0.92)";
  ctx.fillRect(0, height * 0.68, width, height * 0.32);
  ctx.fillStyle = "#2f2117";
  ctx.fillRect(width * 0.08, height * 0.73, width * 0.84, height * 0.07);

  ctx.fillStyle = "#f0c086";
  ctx.beginPath();
  ctx.arc(width * 0.5, height * 0.35, 74, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#27201d";
  ctx.beginPath();
  ctx.arc(width * 0.5, height * 0.29, 86, Math.PI * 0.95, Math.PI * 2.05);
  ctx.fill();

  ctx.fillStyle = "#2f7c66";
  ctx.beginPath();
  ctx.roundRect(width * 0.39, height * 0.46, width * 0.22, height * 0.27, 28);
  ctx.fill();

  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.arc(width * 0.475, height * 0.35, 6, 0, Math.PI * 2);
  ctx.arc(width * 0.525, height * 0.35, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#7a3e36";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(width * 0.5, height * 0.39, 24, 0.15, Math.PI - 0.15);
  ctx.stroke();

  ctx.fillStyle = "#e6e0d2";
  ctx.fillRect(width * 0.13, height * 0.12, width * 0.18, height * 0.46);
  ctx.fillRect(width * 0.69, height * 0.12, width * 0.18, height * 0.46);
  ctx.fillStyle = "#c7465c";
  ctx.fillRect(width * 0.16, height * 0.18, width * 0.12, height * 0.16);
  ctx.fillStyle = "#4f83a7";
  ctx.fillRect(width * 0.72, height * 0.2, width * 0.12, height * 0.2);
  ctx.fillStyle = "#f1d38a";
  ctx.fillRect(width * 0.18, height * 0.39, width * 0.08, height * 0.12);
  ctx.fillRect(width * 0.74, height * 0.45, width * 0.08, height * 0.07);

  for (const particle of state.particles) {
    particle.y -= particle.s / 900;
    particle.x += Math.sin(state.frame / 40 + particle.r) / 3000;
    if (particle.y < -0.04) particle.y = 1.04;
    ctx.fillStyle = risk > 0.45 ? "rgba(255, 125, 145, 0.58)" : "rgba(255, 235, 180, 0.68)";
    ctx.beginPath();
    ctx.arc(particle.x * width, particle.y * height, particle.r, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = "rgba(255,255,255,0.12)";
  ctx.fillRect(0, 0, width, height);
  requestAnimationFrame(drawLivestream);
}

function render(bundle) {
  const profile = bundle.profile;
  const metrics = bundle.metrics;
  ids.kolName.textContent = profile.name;
  ids.liveTitle.textContent = metrics.title;
  ids.avatar.textContent = profile.name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  ids.viewerPill.textContent = `${formatNumber(metrics.viewers)} viewers`;
  ids.likes.textContent = formatNumber(metrics.likes);
  ids.shares.textContent = formatNumber(metrics.shares);
  ids.comments.textContent = formatNumber(metrics.comments);
  ids.botRisk.textContent = `${Math.round(metrics.bot_probability * 100)}%`;
  ids.sentiment.textContent = metrics.sentiment_score.toFixed(2);
  ids.liveId.textContent = `live_id: ${metrics.live_id}`;
  ids.bundleLink.href = `/api/kols/${profile.kol_id}/export/bundle`;
  ids.bundleLink.textContent = `/api/kols/${profile.kol_id}/export/bundle`;
  ids.featuresLink.href = `/api/kols/${profile.kol_id}/export/features`;
  ids.featuresLink.textContent = `/api/kols/${profile.kol_id}/export/features`;
  ids.eventsLink.href = `/api/kols/${profile.kol_id}/export/kol_events.jsonl`;
  ids.eventsLink.textContent = `/api/kols/${profile.kol_id}/export/kol_events.jsonl`;

  ids.trustBadge.textContent = metrics.trust_signal;
  ids.trustBadge.className = `trust ${metrics.trust_signal}`;

  const comments = bundle.recent_events
    .filter((event) => event.event_type === "comment")
    .slice(-18)
    .reverse();
  chatList.innerHTML = comments
    .map(
      (event) => `
        <div class="chat-item ${event.is_suspicious ? "suspicious" : ""}">
          <strong>${event.user_id}</strong> ${event.value}
        </div>
      `,
    )
    .join("");
}

async function refresh() {
  const response = await fetch(`/api/kols/${state.activeKolId}/live`);
  state.bundle = await response.json();
  render(state.bundle);
}

async function setMode(mode) {
  await fetch(`/api/kols/${state.activeKolId}/simulation/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, speed: 1.0, kol_id: state.activeKolId }),
  });
  await refresh();
}

async function reset() {
  await fetch(`/api/kols/${state.activeKolId}/simulation/reset`, { method: "POST" });
  await refresh();
}

async function loadKols() {
  const response = await fetch("/api/kols");
  state.kols = await response.json();
  if (!state.kols.find((kol) => kol.kol_id === state.activeKolId) && state.kols.length) {
    state.activeKolId = state.kols[0].kol_id;
  }
  ids.kolSelect.innerHTML = state.kols
    .map(
      (kol) =>
        `<option value="${kol.kol_id}">${kol.name} - ${kol.risk_profile}</option>`,
    )
    .join("");
  ids.kolSelect.value = state.activeKolId;
  const activeKol = state.kols.find((kol) => kol.kol_id === state.activeKolId);
  if (activeKol) {
    ids.modeSelect.value = activeKol.default_mode;
  }
}

async function setKol(kolId) {
  state.activeKolId = kolId;
  const activeKol = state.kols.find((kol) => kol.kol_id === kolId);
  if (activeKol) {
    ids.modeSelect.value = activeKol.default_mode;
  }
  await refresh();
}

ids.kolSelect.addEventListener("change", (event) => setKol(event.target.value));
ids.modeSelect.addEventListener("change", (event) => setMode(event.target.value));
ids.resetButton.addEventListener("click", reset);

if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function roundRect(x, y, w, h, r) {
    this.beginPath();
    this.moveTo(x + r, y);
    this.arcTo(x + w, y, x + w, y + h, r);
    this.arcTo(x + w, y + h, x, y + h, r);
    this.arcTo(x, y + h, x, y, r);
    this.arcTo(x, y, x + w, y, r);
    this.closePath();
    return this;
  };
}

drawLivestream();
loadKols().then(refresh);
setInterval(refresh, 1800);
