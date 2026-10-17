"""Servidor HTTPS + WebSocket que traduce la entrada del teléfono a un mando Xbox 360 virtual."""
import asyncio
import json
import logging
import os
import socket
import ssl
import threading

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
        self.gamepad = None
        self.runner = None
        self.clients = set()
        self.pressed = set()
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
        self.gamepad = vg.VX360Gamepad()
        log.info("Mando Xbox 360 virtual creado (ViGEmBus).")

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

        # Mantener el bucle vivo sirviendo peticiones hasta que se cierre.
        self._stop_event = asyncio.Event()
        await self._stop_event.wait()
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

    async def _ws_handler(self, request):
        peer = request.remote
        ws = web.WebSocketResponse(max_msg_size=1024 * 64)
        await ws.prepare(request)
        self.clients.add(ws)
        self.connected = True
        log.info("Teléfono conectado desde %s (clientes=%d)", peer, len(self.clients))
        try:
            await ws.send_json(
                {"type": "welcome", "config": self.config, "serverVersion": 1}
            )
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    self._handle_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    log.warning("Error de WebSocket con %s: %s", peer, ws.exception())
                    break
        finally:
            self.clients.discard(ws)
            if not self.clients:
                self.connected = False
                self._reset_gamepad_locked()
            log.info("Teléfono desconectado %s (clientes=%d)", peer, len(self.clients))
        return ws

    # ---- lógica de entrada --------------------------------------------
    def _handle_message(self, ws, raw):
        try:
            data = json.loads(raw)
        except Exception:
            return
        mtype = data.get("type")
        if mtype == "input":
            self._apply_input(data)
            ping = data.get("ping")
            if ping is not None:
                asyncio.ensure_future(ws.send_json({"type": "pong", "ts": ping}))
        elif mtype == "ping":
            ping = data.get("ts")
            asyncio.ensure_future(ws.send_json({"type": "pong", "ts": ping}))
        elif mtype == "stat":
            if "latency" in data:
                try:
                    self.latency_ms = int(data["latency"])
                except Exception:
                    pass
            if "battery" in data:
                self.battery = data["battery"]
        elif mtype == "config":
            incoming = data.get("config")
            if isinstance(incoming, dict):
                self.config.update(incoming)
                save_config(self.config)
                log.info("Configuración actualizada desde el teléfono: %s",
                         {k: incoming.get(k) for k in
                          ("maxSteerDegrees", "axis", "deadzone", "expo",
                           "smoothing", "invert", "pedalMode", "pitchPedals")
                          if k in incoming})

    def _apply_input(self, data):
        gp = self.gamepad
        if gp is None:
            return
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

            for code in list(self.pressed):
                if code not in wanted:
                    gp.release_button(button=code)
                    self.pressed.discard(code)
            for code in wanted:
                if code not in self.pressed:
                    gp.press_button(button=code)
                    self.pressed.add(code)

            gp.update()
        except Exception:
            log.exception("Error aplicando la entrada al mando virtual")

    @staticmethod
    def _clamp01(value):
        try:
            value = float(value)
        except Exception:
            return 0.0
        return max(0.0, min(1.0, value))

    def _reset_gamepad_locked(self):
        gp = self.gamepad
        if gp is None:
            return
        try:
            gp.reset()
            gp.update()
            log.info("Mando virtual reiniciado (inputs liberados).")
        except Exception:
            log.exception("Error reiniciando el mando virtual")
        self.pressed.clear()

    # ---- API para la GUI ----------------------------------------------
    def request_reset(self):
        log.info("GUI: reiniciar mando solicitado.")
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._reset_gamepad_locked)

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
            "lan_ip": self.lan_ip,
            "port": self.port,
            "connected": self.connected,
            "clients": len(self.clients),
            "latency_ms": self.latency_ms,
            "battery": self.battery,
            "error": self.last_error,
        }
