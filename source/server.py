"""Servidor HTTPS + WebSocket que traduce la entrada del teléfono a un mando Xbox 360 virtual."""
import asyncio
import json
import logging
import os
import random
import re
import socket
import ssl
import string
import struct
import threading
import time

from aiohttp import WSMsgType, web

from certgen import build_mobileconfig, ca_der, ca_pem, ensure_certs
from config_store import save_config
from paths import certs_dir, web_dir

try:
    import vgamepad as vg
except Exception:  # pragma: no cover - entorno sin driver
    vg = None

log = logging.getLogger("volante.server")

WEB_DIR = web_dir()

BUTTON_MAP = {}
DPAD_MAP = {}

if vg is not None:
    X = vg.XUSB_BUTTON
    BUTTON_MAP = {
        "A": X.XUSB_GAMEPAD_A,
        "B": X.XUSB_GAMEPAD_B,
        "X": X.XUSB_GAMEPAD_X,
        "Y": X.XUSB_GAMEPAD_Y,
        "LB": X.XUSB_GAMEPAD_LEFT_SHOULDER,
        "RB": X.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "L3": X.XUSB_GAMEPAD_LEFT_THUMB,
        "R3": X.XUSB_GAMEPAD_RIGHT_THUMB,
        "START": X.XUSB_GAMEPAD_START,
        "BACK": X.XUSB_GAMEPAD_BACK,
        "GUIDE": X.XUSB_GAMEPAD_GUIDE,
    }
    DPAD_MAP = {
        "up": X.XUSB_GAMEPAD_DPAD_UP,
        "down": X.XUSB_GAMEPAD_DPAD_DOWN,
        "left": X.XUSB_GAMEPAD_DPAD_LEFT,
        "right": X.XUSB_GAMEPAD_DPAD_RIGHT,
    }


# ------------------------- clientes (IDs) -------------------------
# Cada teléfono tiene un código/ID corto. El código viaja en la URL como
# ?c=XXXXXX (así el QR de cada cliente es único) o se escribe a mano. Con
# "solo invitados" activado, solo los códigos reservados desde el PC pueden
# entrar; cada uno maneja su propio mando Xbox 360 virtual (multijugador).
CLIENT_ID_RE = re.compile(r"^[A-Z0-9]{4,10}$")
MAX_PLAYERS = 4


def new_client_id():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(6))


# ------------------------- telemetría de Forza (UDP) -------------------------
# Formato "Dash" de Forza Data Out (little endian). El juego envía paquetes
# UDP al puerto configurado (config: telemetryPort). Tamaños y offsets según
# la documentación oficial y los decoders de referencia:
#  - FH4 / FH5 (paquete 324 B):  Speed @256 (m/s), Boost @284, Fuel @288, Gear @319
#  - Forza Motorsport 2023 (331 B): Speed @244 (m/s), Boost @272, Fuel @276, Gear @307
# Comunes: IsRaceOn S32 @0, TimestampMS U32 @4, MaxRpm F32 @8, IdleRpm @12, Rpm @16.
# Gear: 0 = marcha atrás, 1 = neutral, 2 = 1ª, ...
FH_DASH_SIZE = 324
FM23_DASH_SIZE = 331


def parse_forza(data):
    """Devuelve un dict con speed(km/h), rpm, maxRpm, gear, fuel, boost o None."""
    try:
        size = len(data)
        if size == FH_DASH_SIZE:
            speed_off, boost_off, fuel_off, gear_off = 256, 284, 288, 319
        elif size == FM23_DASH_SIZE:
            speed_off, boost_off, fuel_off, gear_off = 244, 272, 276, 307
        else:
            return None
        if struct.unpack_from("<i", data, 0)[0] != 1:  # IsRaceOn
            return None
        max_rpm = struct.unpack_from("<f", data, 8)[0]
        rpm = struct.unpack_from("<f", data, 16)[0]
        speed_ms = struct.unpack_from("<f", data, speed_off)[0]
        boost = struct.unpack_from("<f", data, boost_off)[0]
        fuel = struct.unpack_from("<f", data, fuel_off)[0]
        gear = data[gear_off]
    except Exception:
        return None
    if not (0.0 <= rpm <= 30000.0) or not (0.0 <= speed_ms <= 200.0):
        return None
    if gear == 0:
        gear_label = "R"
    elif gear == 1:
        gear_label = "N"
    else:
        gear_label = str(min(gear - 1, 99))
    return {
        "speed": int(round(speed_ms * 3.6)),
        "rpm": int(round(rpm)),
        "maxRpm": int(round(max_rpm)) if max_rpm > 500 else 9000,
        "gear": gear_label,
        "fuel": max(0.0, min(1.0, fuel)),
        "boost": round(max(0.0, boost), 1),
    }


class ForzaTelemetry(threading.Thread):
    """Escucha UDP de Forza Data Out y guarda la última muestra válida."""

    def __init__(self, port):
        super().__init__(name="volante-telemetry", daemon=True)
        self.port = int(port)
        self._latest = None
        self._ts = 0.0

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(1.0)
        except Exception as exc:
            log.warning("No se pudo abrir el puerto UDP de telemetría %s: %s",
                        self.port, exc)
            return
        log.info("Telemetría escuchando en UDP %s (Forza Data Out, formato Dash).",
                 self.port)
        try:
            while True:
                try:
                    data, _addr = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                sample = parse_forza(data)
                if sample is not None:
                    self._latest = sample
                    self._ts = time.time()
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def snapshot(self):
        if self._latest is None or (time.time() - self._ts) > 1.5:
            return None
        return dict(self._latest)


def get_lan_ips():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            ips.append(ip)
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


class ServerManager:
    def __init__(self, config):
        self.config = config
        self.port = int(config.get("port", 8443))
        self.loop = None
        self.thread = None
        self.runner = None
        self.clients = set()   # WebSockets conectados
        # code -> {code, ws, gamepad, pressed, slot, device, latency, battery, connected_at}
        self.players = {}
        self.invites = set(self.config.get("invites") or [])
        # Slots de jugador SOLO en memoria (no se guardan en config):
        # si se persistieran, en modo abierto cada código libre se
        # quedaría un slot para siempre y al cuarto se agotarían los 4.
        self._slot_alloc = {}
        self.telemetry = None
        self.url = None
        self.lan_ip = None
        self.connected = False
        self.latency_ms = None
        self.battery = None
        self.last_error = None
        self._started = False

    # ---- ciclo de vida -------------------------------------------------
    def start(self):
        if self._started:
            return
        self._started = True
        log.info("Iniciando servidor (puerto %s)...", self.port)
        self.thread = threading.Thread(target=self._run, name="volante-server", daemon=True)
        self.thread.start()

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            log.exception("El servidor se detuvo por un error: %s", exc)
        finally:
            try:
                self.loop.close()
            except Exception:
                pass

    async def _main(self):
        if vg is None:
            raise RuntimeError("La librería vgamepad no está disponible.")
        log.info("vgamepad listo: los mandos virtuales se crean al conectar cada jugador.")

        ips = get_lan_ips()
        self.lan_ip = ips[0] if ips else "127.0.0.1"
        self.url = f"https://{self.lan_ip}:{self.port}"
        log.info("IP LAN detectada: %s (todas: %s)", self.lan_ip, ips)

        cert_path, key_path, ca_cert_path = ensure_certs(certs_dir(), ips)
        self.ca_cert_path = ca_cert_path
        log.info("Certificado listo: %s | CA: %s", cert_path, ca_cert_path)
        with open(ca_cert_path, "rb") as f:
            self._ca_pem_bytes = f.read()
        self._ca_der_bytes = ca_der(ca_cert_path)
        self._mobileconfig = build_mobileconfig(ca_cert_path)

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)

        app = web.Application()
        app.router.add_get("/ws", self._ws_handler)
        app.router.add_get("/ca", self._ca_mobileconfig)
        app.router.add_get("/ca.crt", self._ca_crt)
        app.router.add_get("/ca.pem", self._ca_pem)
        app.router.add_get("/health", self._health)
        app.router.add_get("/", self._index)
        if WEB_DIR and isinstance(WEB_DIR, str):
            app.router.add_static("/", WEB_DIR, show_index=False)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host="0.0.0.0", port=self.port, ssl_context=ssl_ctx)
        await site.start()
        log.info("Servidor HTTPS escuchando en %s (y en 0.0.0.0:%s)", self.url, self.port)

        # Telemetría del juego (Forza Data Out por UDP) -> velocidad/RPM/cambio
        # para el cuadro de mandos del teléfono.
        tport = int(self.config.get("telemetryPort", 9999) or 0)
        if tport > 0:
            self.telemetry = ForzaTelemetry(tport)
            self.telemetry.start()
        self._dash_task = asyncio.ensure_future(self._dash_loop())

        # Mantener el bucle vivo sirviendo peticiones hasta que se cierre.
        self._stop_event = asyncio.Event()
        await self._stop_event.wait()
        dash = getattr(self, "_dash_task", None)
        if dash is not None:
            dash.cancel()
            try:
                await dash
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        try:
            await self.runner.cleanup()
        except Exception:
            pass

    def stop(self):
        loop = self.loop
        if loop is None:
            return
        ev = getattr(self, "_stop_event", None)
        if ev is not None:
            loop.call_soon_threadsafe(ev.set)

    # ---- handlers ------------------------------------------------------
    async def _health(self, request):
        return web.json_response({"ok": True, "name": "Volante"})

    async def _index(self, request):
        index = os.path.join(WEB_DIR, "index.html")
        if os.path.isfile(index):
            return web.FileResponse(index)
        return web.Response(text="Volante", content_type="text/html")

    async def _ca_mobileconfig(self, request):
        data = self._mobileconfig
        return web.Response(
            body=data,
            content_type="application/x-apple-aspen-config",
            headers={"Content-Disposition": 'attachment; filename="volante-ca.mobileconfig"'},
        )

    async def _ca_crt(self, request):
        return web.Response(
            body=self._ca_der_bytes,
            content_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": 'attachment; filename="volante-ca.crt"'},
        )

    async def _ca_pem(self, request):
        return web.Response(
            body=self._ca_pem_bytes,
            content_type="application/x-pem-file",
            headers={"Content-Disposition": 'attachment; filename="volante-ca.pem"'},
        )

    def _invite_only(self):
        return bool(self.config.get("inviteOnly", True))

    def _slot_of(self, code):
        return self._slot_alloc.get(code)

    def _assign_slot(self, code):
        """Índice de jugador (0..MAX_PLAYERS-1) para ese código, solo en memoria."""
        if code in self._slot_alloc:
            return self._slot_alloc[code]
        used = set(self._slot_alloc.values())
        for slot in range(MAX_PLAYERS):
            if slot not in used:
                self._slot_alloc[code] = slot
                return slot
        return None

    def _new_gamepad(self):
        try:
            return vg.VX360Gamepad()
        except Exception:
            log.exception("No se pudo crear el mando virtual")
            return None

    async def _reject(self, ws, reason, detail=""):
        try:
            await ws.send_json({"type": "rejected", "reason": reason, "detail": detail})
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

    async def _ws_handler(self, request):
        peer = request.remote
        code = (request.query.get("c") or "").strip().upper()
        ws = web.WebSocketResponse(max_msg_size=1024 * 64)
        await ws.prepare(request)

        if not CLIENT_ID_RE.match(code):
            await self._reject(ws, "code", "Falta el código del dispositivo")
            return ws
        if self._invite_only() and code not in self.invites:
            log.info("Conexión rechazada de %s: código %s no invitado", peer, code)
            await self._reject(ws, "code", "Código no autorizado")
            return ws
        slot = self._assign_slot(code)
        if slot is None:
            await self._reject(ws, "full", "No hay mandos libres (máximo %d)" % MAX_PLAYERS)
            return ws
        gp = self._new_gamepad()
        if gp is None:
            await self._reject(ws, "error", "No se pudo crear el mando virtual")
            return ws

        ws.client_id = code
        # Reconexión con el mismo código: cierra y libera la conexión anterior.
        old = self.players.get(code)
        if old is not None:
            try:
                await old["ws"].close()
            except Exception:
                pass
            if self.players.get(code) is old:
                self.players.pop(code, None)
            self._reset_player(old)

        rec = {
            "code": code,
            "ws": ws,
            "gamepad": gp,
            "pressed": set(),
            "slot": slot,
            "device": "?",
            "latency": None,
            "battery": None,
            "connected_at": time.time(),
        }
        self.players[code] = rec
        self.clients.add(ws)
        self.connected = True
        log.info("Jugador %s conectado desde %s (jugador %d, conectados=%d)",
                 code, peer, slot + 1, len(self.clients))
        try:
            await ws.send_json(
                {
                    "type": "welcome",
                    "config": self._client_config(),
                    "serverVersion": 3,
                    "clientId": code,
                    "player": slot + 1,
                    "maxPlayers": MAX_PLAYERS,
                }
            )
            self._broadcast_players()
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    self._handle_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    log.warning("Error de WebSocket con %s: %s", peer, ws.exception())
                    break
        finally:
            self.clients.discard(ws)
            # Solo borra el registro si esta conexión sigue siendo la vigente
            # (podría haber llegado una reconexión con el mismo código).
            if self.players.get(code) is rec:
                self.players.pop(code, None)
                self._reset_player(rec)
            # Si el código no es un invite reservado, su slot queda libre para
            # otro dispositivo; si lo es, se conserva para el mismo número.
            if code not in self.invites:
                self._slot_alloc.pop(code, None)
            if not self.clients:
                self.connected = False
            log.info("Jugador %s desconectado (conectados=%d)", code, len(self.clients))
            self._broadcast_players()
        return ws

    def _client_config(self):
        priv = {"invites", "publicUrl", "port", "telemetryPort",
                "tunnelToken", "internetEnabled", "inviteOnly"}
        return {k: v for k, v in self.config.items() if k not in priv}

    def _broadcast_players(self):
        payload = {
            "type": "players",
            "players": [
                {"code": r["code"], "player": r["slot"] + 1,
                 "device": r.get("device") or "?"}
                for r in sorted(self.players.values(), key=lambda r: r["slot"])
            ],
        }
        for ws in list(self.clients):
            asyncio.ensure_future(ws.send_json(payload))

    async def _dash_loop(self):
        """Reenvía telemetría del juego a los teléfonos (~14 Hz)."""
        while True:
            await asyncio.sleep(0.07)
            if not self.clients:
                continue
            snap = self.telemetry.snapshot() if self.telemetry else None
            payload = {"type": "dash"}
            if snap is not None:
                payload.update(snap)
                payload["live"] = True
            else:
                payload["live"] = False
            for ws in list(self.clients):
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass

    # ---- lógica de entrada --------------------------------------------
    def _handle_message(self, ws, raw):
        try:
            data = json.loads(raw)
        except Exception:
            return
        mtype = data.get("type")
        if mtype == "input":
            # Cada jugador maneja su propio mando.
            rec = self.players.get(getattr(ws, "client_id", ""))
            if rec is not None:
                self._apply_input(rec, data)
            ping = data.get("ping")
            if ping is not None:
                asyncio.ensure_future(ws.send_json({"type": "pong", "ts": ping}))
        elif mtype == "ping":
            ping = data.get("ts")
            asyncio.ensure_future(ws.send_json({"type": "pong", "ts": ping}))
        elif mtype == "stat":
            rec = self.players.get(getattr(ws, "client_id", ""))
            if rec is None:
                return
            if "latency" in data:
                try:
                    rec["latency"] = int(data["latency"])
                except Exception:
                    pass
            if "battery" in data:
                rec["battery"] = data["battery"]
            if data.get("device"):
                rec["device"] = str(data["device"])[:24]
        elif mtype == "config":
            incoming = data.get("config")
            if isinstance(incoming, dict):
                # Nada de claves privadas: invites, puertos, túnel ni flags de
                # seguridad. Todo lo demás son ajustes del teléfono.
                priv = {"invites", "inviteOnly", "publicUrl",
                        "port", "telemetryPort", "tunnelToken", "internetEnabled"}
                applied = {k: v for k, v in incoming.items() if k not in priv}
                if applied:
                    self.config.update(applied)
                    save_config(self.config)
                    log.info("Configuración actualizada desde el teléfono: %s",
                             sorted(applied))

    def _apply_input(self, rec, data):
        gp = rec.get("gamepad")
        if gp is None:
            return
        pressed = rec["pressed"]
        try:
            steer = float(data.get("steer", 0.0))
        except Exception:
            steer = 0.0
        steer = max(-1.0, min(1.0, steer))
        try:
            gp.left_joystick_float(x_value_float=steer, y_value_float=0.0)

            throttle = self._clamp01(data.get("throttle", 0.0))
            brake = self._clamp01(data.get("brake", 0.0))
            gp.right_trigger_float(value_float=throttle)
            gp.left_trigger_float(value_float=brake)

            wanted = set()
            for name in data.get("buttons") or []:
                code = BUTTON_MAP.get(str(name).upper())
                if code is not None:
                    wanted.add(code)
            dpad = data.get("dpad")
            if dpad:
                code = DPAD_MAP.get(str(dpad).lower())
                if code is not None:
                    wanted.add(code)

            for code in list(pressed):
                if code not in wanted:
                    gp.release_button(button=code)
                    pressed.discard(code)
            for code in wanted:
                if code not in pressed:
                    gp.press_button(button=code)
                    pressed.add(code)

            gp.update()
        except Exception:
            log.exception("Error aplicando la entrada al mando del jugador %s",
                          rec.get("code"))

    @staticmethod
    def _clamp01(value):
        try:
            value = float(value)
        except Exception:
            return 0.0
        return max(0.0, min(1.0, value))

    def _reset_player(self, rec):
        gp = rec.get("gamepad")
        if gp is None:
            return
        try:
            gp.reset()
            gp.update()
            log.info("Mando del jugador %s reiniciado (inputs liberados).", rec.get("code"))
        except Exception:
            log.exception("Error reiniciando el mando del jugador %s", rec.get("code"))
        rec.get("pressed", set()).clear()

    def _reset_all_locked(self):
        for rec in list(self.players.values()):
            self._reset_player(rec)

    # ---- API para la GUI ----------------------------------------------
    def players_snapshot(self):
        """Lista para la ventana del PC: jugadores conectados + invites libres.

        Cada código reservado con «Nuevo QR de cliente» es un mando propio
        (multijugador). Los que aún no se han abierto aparecen como pendientes.
        """
        now = time.time()
        out = []
        for rec in list(self.players.values()):
            out.append({
                "id": rec["code"],
                "player": rec["slot"] + 1,
                "pending": False,
                "device": rec.get("device") or "?",
                "latency": rec.get("latency"),
                "battery": rec.get("battery"),
                "seconds": int(now - rec.get("connected_at", now)),
            })
        conectados = {r["id"] for r in out}
        for cid in sorted(self.invites):
            if cid not in conectados:
                slot = self._slot_of(cid)
                out.append({
                    "id": cid,
                    "player": (slot + 1) if slot is not None else None,
                    "pending": True,
                    "device": "",
                    "latency": None,
                    "battery": None,
                    "seconds": -1,
                })
        out.sort(key=lambda r: (r.get("pending", False),
                                r["player"] if r["player"] else 99, r["id"]))
        return out

    def request_kick(self, client_id):
        log.info("GUI: expulsar cliente %s", client_id)
        if self.loop is None:
            return
        code = (client_id or "").upper()

        def _kick():
            rec = self.players.get(code)
            if rec is not None and rec.get("ws") is not None:
                asyncio.ensure_future(rec["ws"].close())

        self.loop.call_soon_threadsafe(_kick)

    def create_invite(self):
        """Crea un código reservado para el QR de un cliente concreto."""
        cid = None
        for _ in range(50):
            cand = new_client_id()
            if cand not in self.players and cand not in self.invites:
                cid = cand
                break
        cid = cid or new_client_id()
        self.invites.add(cid)
        self.config["invites"] = sorted(self.invites)
        # Reserva ya el número de jugador para que el PC lo muestre desde el QR.
        self._assign_slot(cid)
        save_config(self.config)
        log.info("GUI: invite de cliente creado: %s", cid)
        return cid

    def remove_invite(self, client_id):
        """Quita un código reservado (y su número de jugador) del PC."""
        code = (client_id or "").upper()
        self.invites.discard(code)
        self._slot_alloc.pop(code, None)
        self.config["invites"] = sorted(self.invites)
        save_config(self.config)
        log.info("GUI: invite eliminado: %s", code)

    def set_invite_only(self, value):
        self.config["inviteOnly"] = bool(value)
        save_config(self.config)
        log.info("GUI: solo invitados = %s", bool(value))

    def set_public_url(self, url):
        url = (url or "").strip().rstrip("/")
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.config["publicUrl"] = url
        save_config(self.config)
        log.info("GUI: URL pública = %s", url or "(sin definir)")

    def base_url(self, use_public=True):
        public = (self.config.get("publicUrl") or "").strip()
        if use_public and public:
            return public
        return self.url or ""

    def client_url(self, client_id, use_public=True):
        base = self.base_url(use_public)
        if not base:
            return ""
        if client_id:
            return f"{base}/?c={client_id}"
        return base

    def request_reset(self):
        log.info("GUI: reiniciar mandos solicitado.")
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._reset_all_locked)

    def request_calibrate(self):
        if self.loop is None:
            return
        log.info("GUI: calibrar solicitado (enviado al teléfono).")
        loop = self.loop

        def _broadcast():
            for client in list(self.clients):
                asyncio.ensure_future(client.send_json({"type": "calibrate"}))

        loop.call_soon_threadsafe(_broadcast)

    def request_recenter(self):
        if self.loop is None:
            return
        log.info("GUI: recentrar solicitado (enviado al teléfono).")
        loop = self.loop

        def _broadcast():
            for client in list(self.clients):
                asyncio.ensure_future(client.send_json({"type": "recenter"}))

        loop.call_soon_threadsafe(_broadcast)

    def status(self):
        return {
            "url": self.url,
            "public_url": (self.config.get("publicUrl") or "").strip(),
            "lan_ip": self.lan_ip,
            "port": self.port,
            "connected": self.connected,
            "clients": len(self.clients),
            "players": len(self.players),
            "latency_ms": self.latency_ms,
            "battery": self.battery,
            "error": self.last_error,
        }
