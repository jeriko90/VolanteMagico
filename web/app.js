"use strict";

/* ---------------------------------------------------------------
   Volante - cliente del teléfono
   Lee los sensores de movimiento, calcula la dirección y envía el
   estado por WebSocket al PC (que lo convierte en un mando Xbox 360).
----------------------------------------------------------------*/

const config = {
  maxSteerDegrees: 45,
  axis: "auto",
  deadzone: 0.05,
  expo: 1.0,
  invert: false,
  autoCenter: true,
  smoothing: 0.35,
  pedalMode: "both",
  pitchPedals: false,
  buttons: { handbrake: "A", shiftUp: "RB", shiftDown: "LB", camera: "Y", horn: "B" },
};

const state = {
  ws: null,
  connected: false,
  sensorOn: false,
  calibrated: false,
  center: { sx: 0, sy: 0 },
  last: { beta: 0, gamma: 0 },
  hasData: false,
  targetSteer: 0,
  steer: 0,
  touchThrottle: 0,
  touchBrake: 0,
  pitchThrottle: 0,
  pitchBrake: 0,
  throttle: 0,
  brake: 0,
  activeKeys: new Set(),
  dpad: null,
  wantPing: false,
  pingTs: 0,
  latency: null,
  battery: null,
  pointerInfo: {},
};

const $ = (id) => document.getElementById(id);

/* ------------------------- conexión ------------------------- */
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  let ws;
  try {
    ws = new WebSocket(`${proto}://${location.host}/ws`);
  } catch (e) {
    setTimeout(connect, 1500);
    return;
  }
  state.ws = ws;
  ws.onopen = () => { state.connected = true; updateConn(); };
  ws.onclose = () => { state.connected = false; updateConn(); setTimeout(connect, 1500); };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
  ws.onmessage = onMessage;
}

function onMessage(ev) {
  let msg;
  try { msg = JSON.parse(ev.data); } catch (e) { return; }
  if (msg.type === "welcome") {
    if (msg.config) { Object.assign(config, msg.config); }
    applyConfigToUI();
  } else if (msg.type === "pong") {
    if (typeof msg.ts === "number") {
      state.latency = Math.max(0, Date.now() - msg.ts);
      sendStat();
    }
  } else if (msg.type === "calibrate") {
    calibrate();
  } else if (msg.type === "recenter") {
    recenter();
  }
}

function send(obj) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(obj));
  }
}

function sendStat() {
  send({ type: "stat", latency: state.latency, battery: state.battery });
}

/* ------------------------- sensores ------------------------- */
async function enableSensors() {
  const statusEl = $("startStatus");
  try {
    if (typeof DeviceOrientationEvent !== "undefined" &&
        typeof DeviceOrientationEvent.requestPermission === "function") {
      const res = await DeviceOrientationEvent.requestPermission();
      if (res !== "granted") {
        statusEl.textContent = "Permiso denegado. Actívalo en Ajustes de iOS.";
        return;
      }
    }
  } catch (e) {
    statusEl.textContent = "No se pudo pedir permiso: " + e.message;
    return;
  }

  window.addEventListener("deviceorientation", onOrientation, true);
  state.sensorOn = true;

  goFullscreen();
  $("startOverlay").classList.add("hidden");
}

function onOrientation(e) {
  if (e.gamma === null && e.beta === null) return;
  state.last.gamma = e.gamma || 0;
  state.last.beta = e.beta || 0;
  state.hasData = true;
  if (!state.calibrated) {
    calibrate();
  }
}

function calibrate() {
  const tilt = currentTilt();
  state.center.sx = tilt.sx;
  state.center.sy = tilt.sy;
  state.calibrated = true;
  state.steer = 0;
  state.targetSteer = 0;
}

function recenter() {
  state.steer = 0;
  state.targetSteer = 0;
}

function goFullscreen() {
  const el = document.documentElement;
  try {
    if (el.requestFullscreen) el.requestFullscreen();
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
  } catch (e) {}
  try {
    if (screen.orientation && screen.orientation.lock) {
      screen.orientation.lock("landscape").catch(() => {});
    }
  } catch (e) {}
}

/* ------------------------- pedales ------------------------- */
function pedalPosValue(el, ev) {
  const rect = el.getBoundingClientRect();
  let v = (ev.clientY - rect.top) / rect.height;
  return Math.max(0, Math.min(1, v));
}

function setupPedal(el, which) {
  el.addEventListener("pointerdown", (ev) => {
    ev.preventDefault();
    el.setPointerCapture(ev.pointerId);
    state.pointerInfo[ev.pointerId] = { which, gradual: false };
    setPedalValue(which, config.pedalMode === "gradual" ? pedalPosValue(el, ev) : 1.0);
  });
  el.addEventListener("pointermove", (ev) => {
    const info = state.pointerInfo[ev.pointerId];
    if (!info) return;
    const mode = config.pedalMode;
    if (mode === "gradual") {
      setPedalValue(which, pedalPosValue(el, ev));
    } else if (mode === "both") {
      if (!info.gradual) info.gradual = true;
      setPedalValue(which, pedalPosValue(el, ev));
    }
  });
  const end = (ev) => {
    if (!state.pointerInfo[ev.pointerId]) return;
    delete state.pointerInfo[ev.pointerId];
    setPedalValue(which, 0);
  };
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
  el.addEventListener("pointerleave", (ev) => {
    if (state.pointerInfo[ev.pointerId]) end(ev);
  });
}

function setPedalValue(which, value) {
  if (which === "throttle") state.touchThrottle = value;
  else state.touchBrake = value;
}

function resetPedalsIfReleased() {
  let anyThrottle = false, anyBrake = false;
  for (const id in state.pointerInfo) {
    const info = state.pointerInfo[id];
    if (info.which === "throttle") anyThrottle = true;
    if (info.which === "brake") anyBrake = true;
  }
  if (!anyThrottle) state.touchThrottle = 0;
  if (!anyBrake) state.touchBrake = 0;
}

/* ------------------------- botones ------------------------- */
function setupButtons() {
  document.querySelectorAll(".ctl").forEach((btn) => {
    const key = btn.dataset.key;
    const down = (ev) => { ev.preventDefault(); state.activeKeys.add(key); btn.classList.add("active"); };
    const up = (ev) => { state.activeKeys.delete(key); btn.classList.remove("active"); };
    btn.addEventListener("pointerdown", down);
    btn.addEventListener("pointerup", up);
    btn.addEventListener("pointercancel", up);
    btn.addEventListener("pointerleave", up);
  });

  document.querySelectorAll(".dp").forEach((btn) => {
    const dir = btn.dataset.dpad;
    const down = (ev) => { ev.preventDefault(); state.dpad = dir; btn.classList.add("active"); };
    const up = () => { if (state.dpad === dir) state.dpad = null; btn.classList.remove("active"); };
    btn.addEventListener("pointerdown", down);
    btn.addEventListener("pointerup", up);
    btn.addEventListener("pointercancel", up);
    btn.addEventListener("pointerleave", up);
  });
}

function activeButtonCodes() {
  const out = new Set();
  state.activeKeys.forEach((key) => {
    const code = config.buttons[key];
    if (code) out.add(code);
  });
  return Array.from(out);
}

/* ------------------------- cálculo ------------------------- */
// Ángulo de la pantalla (0/90/180/270) según screen.orientation (con
// respaldo a window.orientation en navegadores antiguos).
function getScreenAngle() {
  if (typeof screen !== "undefined" && screen.orientation &&
      typeof screen.orientation.angle === "number") {
    return ((screen.orientation.angle % 360) + 360) % 360;
  }
  if (typeof window !== "undefined" && typeof window.orientation === "number") {
    return ((-window.orientation % 360) + 360) % 360;
  }
  return 0;
}

// Reasigna (beta, gamma) al marco de la pantalla: sx = inclinación
// izquierda-derecha tal como la percibe el usuario, sy = adelante-atrás.
// Esto hace que el volante funcione igual en vertical y en horizontal.
function remapToScreen(beta, gamma, angle) {
  switch (angle) {
    case 90: return [beta, -gamma];
    case 180: return [-gamma, -beta];
    case 270: return [-beta, gamma];
    default: return [gamma, beta];
  }
}

// Devuelve la inclinación ya alineada con la pantalla según el eje elegido.
function currentTilt() {
  const beta = state.last.beta;
  const gamma = state.last.gamma;
  if (config.axis === "gamma") return { sx: gamma, sy: beta };
  if (config.axis === "beta") return { sx: beta, sy: gamma };
  const remap = remapToScreen(beta, gamma, getScreenAngle());
  return { sx: remap[0], sy: remap[1] };
}

function computeSteering(tilt) {
  const max = Math.max(1, config.maxSteerDegrees || 45);
  let n = (tilt.sx - state.center.sx) / max;
  n = Math.max(-1, Math.min(1, n));

  const dz = config.deadzone || 0;
  if (Math.abs(n) <= dz) n = 0;
  else n = Math.sign(n) * ((Math.abs(n) - dz) / (1 - dz));

  const expo = config.expo || 1;
  if (expo !== 1) n = Math.sign(n) * Math.pow(Math.abs(n), expo);

  if (config.invert) n = -n;

  state.targetSteer = n;

  const a = Math.max(0, Math.min(0.95, config.smoothing ?? 0.35));
  state.steer = state.steer * a + state.targetSteer * (1 - a);
  if (Math.abs(state.steer) < 0.001) state.steer = 0;
}

function computePedals(tilt) {
  resetPedalsIfReleased();

  if (config.pitchPedals) {
    const max = Math.max(5, config.maxSteerDegrees || 45);
    const pb = tilt.sy - state.center.sy;
    state.pitchThrottle = Math.max(0, Math.min(1, pb / max));
    state.pitchBrake = Math.max(0, Math.min(1, -pb / max));
  } else {
    state.pitchThrottle = 0;
    state.pitchBrake = 0;
  }

  state.throttle = Math.max(state.touchThrottle, state.pitchThrottle);
  state.brake = Math.max(state.touchBrake, state.pitchBrake);
}

/* ------------------------- bucle principal ------------------------- */
function tick() {
  const tilt = currentTilt();
  if (state.sensorOn) computeSteering(tilt);
  computePedals(tilt);

  let steer = state.steer;
  if (!state.hasData) steer = 0;

  const msg = {
    type: "input",
    steer: round3(steer),
    throttle: round3(state.throttle),
    brake: round3(state.brake),
    buttons: activeButtonCodes(),
  };
  if (state.dpad) msg.dpad = state.dpad;
  if (state.wantPing) { msg.ping = state.pingTs; state.wantPing = false; }
  send(msg);

  updateVisuals(steer, state.throttle, state.brake);
}

function round3(v) { return Math.round(v * 1000) / 1000; }

/* ------------------------- visual ------------------------- */
function updateVisuals(steer, throttle, brake) {
  const marker = $("steerMarker");
  const pct = 50 + steer * 50;
  marker.style.left = pct + "%";

  const deg = Math.round(steer * (config.maxSteerDegrees || 45));
  $("steerValue").textContent = deg + "\u00B0";

  const tEl = $("throttle");
  const bEl = $("brake");
  tEl.querySelector(".fill").style.height = (throttle * 100) + "%";
  bEl.querySelector(".fill").style.height = (brake * 100) + "%";

  const tPct = tEl.querySelector(".pedalPct");
  if (tPct) tPct.textContent = throttle > 0.005 ? Math.round(throttle * 100) + "%" : "";
  const bPct = bEl.querySelector(".pedalPct");
  if (bPct) bPct.textContent = brake > 0.005 ? Math.round(brake * 100) + "%" : "";
}

function updateConn() {
  const el = $("conn");
  if (state.connected) {
    el.textContent = "conectado";
    el.className = "pill on";
  } else {
    el.textContent = "desconectado";
    el.className = "pill off";
  }
}

function updateStats() {
  $("lat").textContent = (state.latency === null ? "--" : state.latency) + " ms";
  $("bat").textContent = (state.battery === null ? "--" : state.battery) + " %";
}

/* ------------------------- ajustes ------------------------- */
function applyConfigToUI() {
  $("maxSteerDegrees").value = config.maxSteerDegrees;
  $("deadzone").value = config.deadzone;
  $("expo").value = config.expo;
  $("smoothing").value = config.smoothing;
  $("axis").value = config.axis;
  $("pedalMode").value = config.pedalMode;
  $("invert").checked = !!config.invert;
  $("pitchPedals").checked = !!config.pitchPedals;
  updateConfigLabels();
}

function updateConfigLabels() {
  $("vMax").textContent = config.maxSteerDegrees;
  $("vDz").textContent = Number(config.deadzone).toFixed(2);
  $("vExpo").textContent = Number(config.expo).toFixed(2);
  $("vSm").textContent = Number(config.smoothing).toFixed(2);
}

function persistConfig() {
  send({ type: "config", config });
}

function setupSettings() {
  const map = [
    ["maxSteerDegrees", "maxSteerDegrees", parseFloat],
    ["deadzone", "deadzone", parseFloat],
    ["expo", "expo", parseFloat],
    ["smoothing", "smoothing", parseFloat],
    ["axis", "axis", (v) => v],
    ["pedalMode", "pedalMode", (v) => v],
    ["invert", "invert", (v, el) => el.checked],
    ["pitchPedals", "pitchPedals", (v, el) => el.checked],
  ];
  map.forEach(([id, key, parse]) => {
    const el = $(id);
    const handler = () => {
      config[key] = parse(el.value, el);
      updateConfigLabels();
      persistConfig();
    };
    el.addEventListener("input", handler);
    el.addEventListener("change", handler);
  });

  $("settingsBtn").addEventListener("click", () => $("settingsOverlay").classList.remove("hidden"));
  $("closeSettings").addEventListener("click", () => $("settingsOverlay").classList.add("hidden"));
  $("calibBtn").addEventListener("click", calibrate);
  $("recenterBtn").addEventListener("click", recenter);
}

/* ------------------------- batería ------------------------- */
function setupBattery() {
  if (!navigator.getBattery) return;
  navigator.getBattery().then((b) => {
    const update = () => { state.battery = Math.round(b.level * 100); updateStats(); };
    update();
    b.addEventListener("levelchange", update);
  }).catch(() => {});
}

/* ------------------------- arranque ------------------------- */
function init() {
  $("startBtn").addEventListener("click", enableSensors);
  setupButtons();
  setupPedal($("throttle"), "throttle");
  setupPedal($("brake"), "brake");
  setupSettings();
  setupBattery();
  applyConfigToUI();
  connect();

  setInterval(tick, 16);
  setInterval(() => { state.pingTs = Date.now(); state.wantPing = true; }, 1000);
  setInterval(updateStats, 500);

  document.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });
  document.addEventListener("gesturestart", (e) => e.preventDefault());
}

document.addEventListener("DOMContentLoaded", init);
