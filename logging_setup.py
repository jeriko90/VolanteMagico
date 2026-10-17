"""Configuracion de logging.

Escribe en `volante.log` (junto al ejecutable) con rotacion, y tambien a la
consola cuando esta disponible. Captura ademas excepciones no controladas.
"""
import logging
import logging.handlers
import os
import sys

from paths import app_dir

LOG_FILENAME = "volante.log"
LOG_PATH = None

_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
)


def log_path():
    return LOG_PATH or os.path.join(app_dir(), LOG_FILENAME)


def setup_logging(level=logging.INFO):
    global LOG_PATH
    LOG_PATH = os.path.join(app_dir(), LOG_FILENAME)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # Archivo rotativo (si el archivo esta bloqueado por otro proceso, se omite).
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8", delay=True
        )
        fh.setLevel(level)
        fh.setFormatter(_FMT)
        root.addHandler(fh)
    except Exception:
        pass

    # Consola (solo si existe stdout; en modo ventana no hay).
    if sys.stdout is not None:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(_FMT)
        root.addHandler(ch)

    def _excepthook(exc_type, exc, tb):
        root.critical("Excepcion no controlada", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    logging.getLogger("volante").info("=== Volante iniciado (log: %s) ===", LOG_PATH)
    return LOG_PATH
