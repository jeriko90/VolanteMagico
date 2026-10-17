"""Auto-actualizacion de Volante.

Como el .exe contiene TODO el codigo, actualizar = descargar el .exe mas
reciente y reemplazar el actual. El manifiesto `update.json` vive en el repo
publico y dice la ultima version, la URL del .exe y su hash SHA-256.

Solo funciona cuando corre empaquetado (PyInstaller). En desarrollo se omite.
"""
import hashlib
import json
import logging
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request

from version import __version__

log = logging.getLogger("volante.update")

REPO = "jeriko90/VolanteMagico"
BRANCH = "main"

# Varias fuentes por si raw.githubusercontent esta lento o cachea un 404.
_MANIFEST_SOURCES = [
    (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/update.json", None),
    (f"https://api.github.com/repos/{REPO}/contents/update.json",
     {"Accept": "application/vnd.github.raw"}),
    (f"https://cdn.jsdelivr.net/gh/{REPO}@{BRANCH}/update.json", None),
]


def is_frozen():
    return getattr(sys, "frozen", False)


def current_version():
    return __version__


# --------------------------------------------------------------- utilidades
def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _parse_version(value):
    parts = []
    for piece in str(value).strip().lstrip("vV").split("."):
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _fetch(url, timeout, headers=None):
    merged = {"User-Agent": "Volante-Updater"}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read().decode("utf-8")


def _dir_writable(path):
    try:
        probe = os.path.join(path, ".volante_write_test")
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        return True
    except Exception:
        return False


# ------------------------------------------------------------- comprobacion
def check_update(timeout=8):
    """Devuelve el dict del manifiesto si hay version nueva, si no None.

    Prueba varias fuentes (raw, API, jsDelivr). Lanza una excepcion solo si
    ninguna respondio (sin red, etc.).
    """
    last_error = None
    for base, headers in _MANIFEST_SOURCES:
        url = f"{base}{'&' if '?' in base else '?'}_={int(time.time())}"
        try:
            manifest = json.loads(_fetch(url, timeout, headers))
        except Exception as exc:
            last_error = exc
            log.warning("Manifiesto no disponible en %s: %s", base, exc)
            continue
        remote = manifest.get("version")
        if not remote:
            continue
        if _parse_version(remote) > _parse_version(__version__):
            log.info("Actualizacion disponible: %s -> %s", __version__, remote)
            return manifest
        log.info("Sin actualizaciones (local=%s remoto=%s)", __version__, remote)
        return None
    if last_error:
        raise last_error
    return None


# --------------------------------------------------------------- descarga
def _download(url, dest, expected_sha, progress_cb):
    url = f"{url}{'&' if '?' in url else '?'}_={int(time.time())}"
    req = urllib.request.Request(url, headers={"User-Agent": "Volante-Updater"})
    sha = hashlib.sha256()
    tmp = dest + ".part"
    received = 0
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                received += len(chunk)
                if progress_cb and total:
                    progress_cb(min(1.0, received / total))

    if expected_sha and sha.hexdigest().lower() != expected_sha.lower():
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RuntimeError("El archivo descargado no coincide con el hash esperado.")

    os.replace(tmp, dest)
    log.info("Descarga completada: %s (%d bytes)", dest, received)
    return dest


def _spawn_swapper(exe, new_exe):
    """Lanza un .bat que espera, reemplaza el .exe y reinicia la app."""
    bat = os.path.join(tempfile.gettempdir(), "volante_update.bat")
    script = (
        "@echo off\r\n"
        "ping 127.0.0.1 -n 2 >nul\r\n"
        ":wait\r\n"
        f'move /Y "{new_exe}" "{exe}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="ascii", newline="") as f:
        f.write(script)

    detached = 0x00000008          # DETACHED_PROCESS
    new_group = 0x00000200         # CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        ["cmd", "/c", bat],
        creationflags=detached | new_group,
        close_fds=True,
    )
    log.info("Actualizador lanzado; reemplazara %s al cerrar.", exe)


def download_and_restart(info, progress_cb=None):
    """Descarga la nueva version y la aplica.

    Devuelve ("restart", ruta) si se reiniciara solo, o ("manual", ruta) si no
    se pudo escribir junto al .exe y hay que reemplazarlo a mano.
    """
    url = info.get("url")
    if not url:
        raise RuntimeError("El manifiesto no incluye una URL de descarga.")
    expected_sha = (info.get("sha256") or "").strip().lower()

    exe = sys.executable
    exe_dir = os.path.dirname(exe) or "."
    writable = is_frozen() and _dir_writable(exe_dir)

    if writable:
        dest = os.path.join(exe_dir, os.path.basename(exe) + ".new")
    else:
        dest = os.path.join(_downloads_dir(), os.path.basename(exe))

    _download(url, dest, expected_sha, progress_cb)

    if writable:
        _spawn_swapper(exe, dest)
        return ("restart", dest)
    return ("manual", dest)


def _downloads_dir():
    base = os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = tempfile.gettempdir()
    return base
