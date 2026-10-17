"""Rutas de la aplicacion, tanto en modo desarrollo como empaquetado (PyInstaller)."""
import os
import sys

APP_NAME = "Volante"


def is_frozen():
    return getattr(sys, "frozen", False)


def app_dir():
    """Carpeta donde vive el .exe (o el codigo fuente en desarrollo). Aqui se escriben datos del usuario."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    """Recurso embebido (web/, assets/) dentro del bundle o del repo."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def web_dir():
    return resource_path("web")


def config_path():
    return os.path.join(app_dir(), "config.json")


def certs_dir():
    d = os.path.join(app_dir(), "certs")
    os.makedirs(d, exist_ok=True)
    return d
