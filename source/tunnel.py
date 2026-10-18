"""Conexión por internet: ejecuta cloudflared (Cloudflare Tunnel) con token.

La app arranca cloudflared al abrir (si está configurado) y mantiene el túnel
vivo con reintentos. El token se guarda en config.json (tunnelToken) y viene
del dashboard de Cloudflare (Networking → Tunnels → Create a tunnel), donde
también se define el hostname público hacia https://localhost:8443 con
"Disable TLS certificate verification" (el certificado del PC es autofirmado).

El binario se busca: junto al .exe, embebido en el bundle, o en el PATH; si
no está, la GUI puede descargarlo (download_cloudflared).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from paths import app_dir, resource_path

CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/"
    "download/cloudflared-windows-amd64.exe"
)
WINDOWS = os.name == "nt"
_BIN_NAME = "cloudflared.exe" if WINDOWS else "cloudflared"


def find_cloudflared():
    """Devuelve la ruta del binario o None."""
    for cand in (os.path.join(app_dir(), _BIN_NAME), resource_path(_BIN_NAME)):
        if os.path.isfile(cand):
            return cand
    return shutil.which("cloudflared") or shutil.which("cloudflared.exe")


def download_cloudflared(progress_cb=None):
    """Descarga cloudflared a la carpeta de la app y devuelve la ruta."""
    target = os.path.join(app_dir(), _BIN_NAME)
    req = urllib.request.Request(CLOUDFLARED_URL, headers={"User-Agent": "Volante"})
    fd, tmp = tempfile.mkstemp(prefix="cloudflared-", suffix=".tmp", dir=app_dir())
    os.close(fd)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            read = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if progress_cb and total:
                    try:
                        progress_cb(read / total)
                    except Exception:
                        pass
        if os.path.exists(target):
            os.remove(target)
        os.replace(tmp, target)
        if not WINDOWS:
            os.chmod(target, 0o755)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return target


def classify_line(line):
    """Interpreta una línea del log de cloudflared.

    Devuelve None, "connected", "bad_token" o "error".
    """
    if "Registered tunnel connection" in line:
        return "connected"
    if "Unauthorized" in line or "Failed to get tunnel" in line:
        return "bad_token"
    if " ERR " in line or line.startswith("ERR") or "error=" in line.lower():
        return "error"
    return None


class TunnelManager:
    """Ejecuta `cloudflared tunnel run --token ...` y expone su estado."""

    def __init__(self, config):
        self.config = config
        self._thread = None
        self._stop = threading.Event()
        self._proc = None
        self._lock = threading.Lock()
        self.state = "off"      # off | starting | connected | error
        self.detail = ""
        self.last_line = ""

    # ---- estado/config ------------------------------------------------
    @property
    def token(self):
        return (self.config.get("tunnelToken") or "").strip()

    @property
    def enabled(self):
        return bool(self.config.get("internetEnabled")) and bool(self.token)

    def status(self):
        return {"state": self.state, "detail": self.detail, "binary": find_cloudflared()}

    def set_enabled(self, enabled, token=None):
        if token is not None:
            self.config["tunnelToken"] = token.strip()
        self.config["internetEnabled"] = bool(enabled)

    # ---- ciclo de vida ------------------------------------------------
    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            if not self.token:
                self.state = "error"
                self.detail = "Falta el token de Cloudflare"
                return
            self._stop.clear()
            self.state = "starting"
            self.detail = ""
            self._thread = threading.Thread(target=self._run, name="volante-tunnel",
                                            daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._terminate()
        self.state = "off"
        self.detail = ""

    def _terminate(self):
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    # ---- bucle --------------------------------------------------------
    def _spawn_cmd(self):
        binary = find_cloudflared()
        if not binary:
            return None
        return [binary, "tunnel", "run", "--token", self.token]

    def _run(self):
        backoff = 3
        while not self._stop.is_set():
            cmd = self._spawn_cmd()
            if cmd is None:
                self.state = "error"
                self.detail = "cloudflared no encontrado (usa «Descargar cloudflared»)"
                return
            self.state = "starting"
            self.detail = ""
            kwargs = {}
            if WINDOWS:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors="replace", **kwargs)
                self._proc = proc
            except Exception as exc:
                self.state = "error"
                self.detail = f"No se pudo iniciar cloudflared: {exc}"
                return

            registered = 0
            bad_token = False
            try:
                for raw in proc.stdout:
                    if self._stop.is_set():
                        break
                    line = raw.strip()
                    if not line:
                        continue
                    self.last_line = line
                    kind = classify_line(line)
                    if kind == "connected":
                        registered += 1
                        self.state = "connected"
                        self.detail = f"conexión registrada ({registered})"
                    elif kind == "bad_token":
                        bad_token = True
                        self.state = "error"
                        self.detail = "Token no válido: revísalo en el dashboard de Cloudflare"
                        break
                    elif kind == "error" and self.state != "connected":
                        self.state = "error"
                        self.detail = line[:180]
            except Exception as exc:
                if not self._stop.is_set():
                    self.state = "error"
                    self.detail = str(exc)[:180]
            finally:
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                if self._proc is proc:
                    self._proc = None

            if self._stop.is_set() or bad_token:
                break
            # El proceso murió solo: reintenta con backoff creciente.
            self.state = "starting"
            if self._stop.wait(backoff):
                break
            backoff = min(backoff * 2, 30)

        if self._stop.is_set() and self.state != "error":
            self.state = "off"
        time.sleep(0.05)
