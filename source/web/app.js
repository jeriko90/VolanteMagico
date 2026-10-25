"use strict";

/* ---------------------------------------------------------------
   Volante - cliente del teléfono
   Lee los sensores de movimiento, calcula la dirección y envía el
   estado por WebSocket al PC (que lo convierte en un mando Xbox 360).
----------------------------------------------------------------*/

const config = {
  showDpad: false,
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
  clientId: null,
  player: null,
  maxPlayers: null,
  rejected: false,
  rejectDetail: "",
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
  devicePref: "auto",
};

const $ = (id) => document.getElementById(id);

/* ------------------------- código de conexión -------------------------
   UN solo código de emparejamiento (pairCode): la PC lo muestra con su QR
   (?c=XXXXXX, el QR ya lo trae) o se escribe a mano en «Conectar».
   Se guarda en localStorage para que al reabrir la web conserve el acceso.
   El PC solo acepta su propio código: cualquier otro se rechaza. */
const CODE_KEY = "volante.clientId";

function urlCode() {
  try {
    const q = new URLSearchParams(location.search).get("c");
    if (q && /^[a-z0-9]{4,10}$/i.test(q.trim())) return q.trim().toUpperCase();
  } catch (e) {}
  return "";
}

function storedCode() {
  try { return (localStorage.getItem(CODE_KEY) || "").toUpperCase(); } catch (e) { return ""; }
}

function saveCode(c) {
  try { localStorage.setItem(CODE_KEY, c); } catch (e) {}
}

function validCode(c) {
  return /^[A-Z0-9]{4,10}$/.test((c || "").toUpperCase());
}

const fromUrl = urlCode();
if (validCode(fromUrl)) saveCode(fromUrl);
const CLIENT_ID = validCode(fromUrl) ? fromUrl : (validCode(storedCode()) ? storedCode() : "");

/* ------------------------- conexión ------------------------- */
function connect() {
  if (state.rejected) return;
  const code = currentCode();
  if (!validCode(code)) { showCodeOverlay(); return; }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  let ws;
  try {
    ws = new WebSocket(`${proto}://${location.host}/ws?c=${encodeURIComponent(code)}`);
  } catch (e) {
    setTimeout(connect, 1500);
    return;
  }
  state.ws = ws;
  ws.onopen = () => { state.connected = true; updateConn(); };
  ws.onclose = () => {
    state.connected = false;
    updateConn();
    if (!state.rejected) setTimeout(connect, 1500);
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
  ws.onmessage = onMessage;
}

function onMessage(ev) {
  let msg;
  try { msg = JSON.parse(ev.data); } catch (e) { return; }
  if (msg.type === "welcome") {
    if (msg.config) { Object.assign(config, msg.config); }
    if (msg.clientId) state.clientId = String(msg.clientId).toUpperCase();
    if (msg.player) state.player = msg.player;
    if (msg.maxPlayers) state.maxPlayers = msg.maxPlayers;
    state.rejected = false;
    hideCodeOverlay();
    applyClientUI();
    applyConfigToUI();
  } else if (msg.type === "rejected") {
    state.rejected = true;
    state.rejectDetail = msg.detail || "";
    if (msg.reason === "full") {
      showCodeOverlay("El PC ya tiene un teléfono conectado. Desconéctalo e inténtalo otra vez.");
    } else {
      showCodeOverlay(msg.detail || "Código incorrecto. Escanea el QR de la PC o pídeselo.");
    }
  } else if (msg.type === "players") {
    applyPlayers(msg.players || []);
  } else if (msg.type === "dash") {
    updateDash(msg);
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
  send({ type: "stat", latency: state.latency, battery: state.battery,
         device: effectiveDevice() });
}

/* ------------------- identidad / código / jugador ------------------- */
function currentCode() {
  return state.clientId || CLIENT_ID || storedCode();
}

function applyClientUI() {
  const id = currentCode();
  const pill = $("clientIdPill");
  if (pill) pill.textContent = "ID " + (id || "----");
  const shown = $("codeShown");
  if (shown) shown.textContent = id || "----";
  const pp = $("playerPill");
  if (pp) pp.textContent = state.player ? ("Jugador " + state.player) : "Jugador --";
}

function applyPlayers(list) {
  const mine = list.find((p) => p.code === currentCode());
  if (mine && mine.player) {
    state.player = mine.player;
    applyClientUI();
  }
}

/* ------------------- entrada del código ------------------- */
function showCodeOverlay(message) {
  const ov = $("codeOverlay");
  if (!ov) return;
  const err = $("codeError");
  if (err) err.textContent = message || "";
  ov.classList.remove("hidden");
  const inp = $("codeInput");
  if (inp) {
    inp.value = currentCode();
    setTimeout(() => { try { inp.focus(); } catch (e) {} }, 50);
  }
}

function hideCodeOverlay() {
  const ov = $("codeOverlay");
  if (ov) ov.classList.add("hidden");
}

function submitCode() {
  const inp = $("codeInput");
  const raw = (inp ? inp.value : "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!validCode(raw)) {
    const err = $("codeError");
    if (err) err.textContent = "Código inválido. Usa 4–10 letras o números.";
    return;
  }
  saveCode(raw);
  state.rejected = false;
  state.rejectDetail = "";
  state.clientId = raw;
  hideCodeOverlay();
  applyClientUI();
  const old = state.ws;
  if (old) { old.onclose = null; try { old.close(); } catch (e) {} }
  connect();
}

function changeCode() {
  state.rejected = true; // detiene la reconexión hasta que ponga otro código
  try { if (state.ws) state.ws.close(); } catch (e) {}
  showCodeOverlay("Escribe el código que muestra la PC.");
}

/* ------------------- cuadro de mandos (telemetría) -------------------
   Velocidad, vueltas y cambio llegan del PC (Forza Data Out por UDP).
   Sin telemetría el marcador queda en "--" y el resto sigue funcionando. */
function updateDash(msg) {
  const live = !!msg.live;
  const sv = $("speedVal");
  if (sv) sv.textContent = live ? String(Math.round(msg.speed || 0)) : "--";
  const g = $("gear");
  if (g) g.textContent = live ? String(msg.gear || "\u2013") : "\u2013";
  const rf = $("rpmFill");
  if (rf) {
    const maxRpm = msg.maxRpm > 0 ? msg.maxRpm : 9000;
    const pct = live ? Math.max(0, Math.min(100, (msg.rpm || 0) / maxRpm * 100)) : 0;
    rf.style.width = pct + "%";
    rf.classList.toggle("redline", !!(live && msg.rpm / maxRpm > 0.88));
  }
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
  state.hasData = false;

  goFullscreen();
  $("startOverlay").classList.add("hidden");
  setTimeout(updatePosture, 200);
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

/* ---------------- postura real (horizontal aunque la rotación esté bloqueada) ----------------
   La rotación automática del sistema puede estar bloqueada: el viewport sigue
   en vertical aunque el teléfono esté horizontal. Detectamos la postura real
   con los sensores y, si no coincide con el viewport, rotamos todo el lienzo
   (#stage) 90º para que la UI se vea horizontal igualmente. También cambiamos
   la maquetación (clases en <body>) según la postura percibida, no según el
   viewport, que con la rotación bloqueada no refleja la realidad. */
function postureAngle() {
  // Ángulo del "arriba" del mundo respecto al viewport (0 = vertical).
  let a = -spinAngle();
  a = ((a % 360) + 540) % 360 - 180;
  return a;
}

function updatePosture() {
  const body = document.body;
  const hasSensor = state.hasData;
  const angle = hasSensor ? postureAngle() : 0;
  const physLandscape = hasSensor && Math.abs(angle) > 45 && Math.abs(angle) < 135;
  const viewportLandscape = window.innerWidth > window.innerHeight;

  // Rotación solo cuando la postura no coincide con el viewport (rotación
  // automática bloqueada). Si el viewport ya está en horizontal no rotamos
  // (el sistema lo hizo bien y rotar de nuevo lo pondría de través).
  let rot = 0;
  if (physLandscape && !viewportLandscape) rot = angle > 0 ? 90 : -90;

  // La maquetación sigue la postura REAL del teléfono si la conocemos
  // (sensores activos); si no, la del viewport.
  const effLandscape = hasSensor ? physLandscape : viewportLandscape;

  body.classList.toggle("posture-landscape", effLandscape);
  body.classList.toggle("posture-portrait", !effLandscape);
  body.classList.toggle("rot", rot !== 0);
  body.classList.toggle("rot-cw", rot === 90);
  body.classList.toggle("rot-ccw", rot === -90);
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
  try { updatePosture(); } catch (e) {}
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
const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

// Diferencia angular con signo en el rango (-180, 180].
function angleDiff(a, b) {
  let d = (a - b) % 360;
  if (d > 180) d -= 360;
  if (d <= -180) d += 360;
  return d;
}

// "Giro" del teléfono sobre el eje de la pantalla, como si fuera el
// volante de un coche. Se calcula solo con beta y gamma, así que da igual
// si el teléfono está en vertical u horizontal y funciona igual en iOS y
// Android (no depende de screen.orientation, que en Android a veces no
// refleja bien la postura real).
function spinAngle() {
  const b = state.last.beta * DEG2RAD;
  const g = state.last.gamma * DEG2RAD;
  return Math.atan2(Math.cos(b) * Math.sin(g), Math.sin(b)) * RAD2DEG;
}

// Devuelve la inclinación alineada con la pantalla según el eje elegido.
function currentTilt() {
  const beta = state.last.beta;
  const gamma = state.last.gamma;
  if (config.axis === "gamma") return { sx: gamma, sy: beta };
  if (config.axis === "beta") return { sx: beta, sy: gamma };
  return { sx: spinAngle(), sy: beta };
}

function computeSteering(tilt) {
  const max = Math.max(1, config.maxSteerDegrees || 45);
  const raw = config.axis === "auto"
    ? angleDiff(tilt.sx, state.center.sx)
    : (tilt.sx - state.center.sx);
  let n = raw / max;
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

  const ro = $("tiltReadout");
  if (ro) {
    const b = Math.round(state.last.beta);
    const g = Math.round(state.last.gamma);
    const s = Math.round(spinAngle());
    ro.innerHTML = "Giro: <b>" + deg + "&deg;</b> &nbsp;·&nbsp; sensor " +
      (state.hasData ? "OK" : "sin datos") + " &nbsp;·&nbsp; b=" + b + " g=" + g + " spin=" + s;
  }
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

/* ------------------------- dispositivo ------------------------- */
// Textos que se adaptan a iOS / Android / otro. Los sensores funcionan igual
// en ambos; solo cambian las instrucciones (sobre todo lo del certificado).
const DEVICE_TEXT = {
  ios: {
    intro: "Convierte tu iPhone o iPad en un volante para juegos de carreras en el PC.",
    cert: "Si no aparecen los sensores, instala el certificado abriendo /ca en este mismo navegador.",
  },
  android: {
    intro: "Convierte tu teléfono Android en un volante para juegos de carreras en el PC.",
    cert: "",
  },
  other: {
    intro: "Convierte tu teléfono en un volante para juegos de carreras en el PC.",
    cert: "",
  },
};

function detectPlatform() {
  const ua = navigator.userAgent || "";
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  if (/Android/i.test(ua)) return "android";
  // iPadOS 13+ se identifica como Mac; se distingue por el soporte táctil.
  if (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1) return "ios";
  return "other";
}

function loadDevicePref() {
  try { return localStorage.getItem("volante.device") || "auto"; } catch (e) { return "auto"; }
}

function saveDevicePref(v) {
  try { localStorage.setItem("volante.device", v); } catch (e) {}
}

function effectiveDevice() {
  return state.devicePref === "auto" ? detectPlatform() : state.devicePref;
}

function deviceLabel() {
  const d = effectiveDevice();
  return d === "ios" ? "iPhone/iPad (iOS)" : d === "android" ? "Android" : "otro";
}

function applyDevice() {
  const t = DEVICE_TEXT[effectiveDevice()] || DEVICE_TEXT.other;
  const intro = $("deviceIntro");
  if (intro) intro.textContent = t.intro;
  const hint = $("certHint");
  if (hint) {
    hint.textContent = t.cert;
    hint.style.display = t.cert ? "" : "none";
  }
  const det = $("deviceDetected");
  if (det) {
    det.textContent = deviceLabel() + (state.devicePref === "auto" ? " (automático)" : " (manual)");
  }
}

function setupDevice() {
  state.devicePref = loadDevicePref();
  const sel = $("device");
  if (sel) {
    sel.value = state.devicePref;
    sel.addEventListener("change", () => {
      state.devicePref = sel.value;
      saveDevicePref(state.devicePref);
      applyDevice();
    });
  }
  applyDevice();
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
  if ($("showDpad")) $("showDpad").checked = !!config.showDpad;
  updateConfigLabels();
}

function updateConfigLabels() {
  $("vMax").textContent = config.maxSteerDegrees;
  $("vDz").textContent = Number(config.deadzone).toFixed(2);
  $("vExpo").textContent = Number(config.expo).toFixed(2);
  $("vSm").textContent = Number(config.smoothing).toFixed(2);
  document.body.classList.toggle("show-dpad", !!config.showDpad);
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
    ["showDpad", "showDpad", (v, el) => el.checked],
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

  const overlay = $("settingsOverlay");
  const openSettings = () => overlay.classList.remove("hidden");
  const closeSettings = () => overlay.classList.add("hidden");

  $("settingsBtn").addEventListener("click", () => {
    if (overlay.classList.contains("hidden")) openSettings();
    else closeSettings();
  });
  $("closeSettings").addEventListener("click", closeSettings);
  $("closeX").addEventListener("click", closeSettings);
  // Tocar el fondo oscuro (fuera del panel) también cierra.
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeSettings();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSettings();
  });

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
function setupCodeUI() {
  const btn = $("codeBtn");
  if (btn) btn.addEventListener("click", submitCode);
  const inp = $("codeInput");
  if (inp) {
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") submitCode(); });
  }
  const change = $("changeCodeBtn");
  if (change) change.addEventListener("click", changeCode);
}

function init() {
  $("startBtn").addEventListener("click", enableSensors);
  setupCodeUI();
  applyClientUI();
  setupButtons();
  setupPedal($("throttle"), "throttle");
  setupPedal($("brake"), "brake");
  setupSettings();
  if (location.hash === "#ajustes") $("settingsOverlay").classList.remove("hidden");
  setupDevice();
  setupBattery();
  applyConfigToUI();
  updatePosture();

  if (!validCode(CLIENT_ID)) {
    showCodeOverlay("Escribe el código que muestra la PC.");
  } else {
    connect();
  }

  window.addEventListener("resize", updatePosture);
  window.addEventListener("orientationchange", () => setTimeout(updatePosture, 150));
  setInterval(updatePosture, 250);

  setInterval(tick, 16);
  setInterval(() => { state.pingTs = Date.now(); state.wantPing = true; }, 1000);
  setInterval(updateStats, 500);

  // Bloquea el scroll/zoom al conducir, pero PERMITE desplazarse dentro de
  // los paneles (Ajustes), que pueden ser más altos que la pantalla.
  document.addEventListener("touchmove", (e) => {
    if (e.target.closest && e.target.closest(".overlay")) return;
    e.preventDefault();
  }, { passive: false });
  document.addEventListener("gesturestart", (e) => e.preventDefault());
}

document.addEventListener("DOMContentLoaded", init);
