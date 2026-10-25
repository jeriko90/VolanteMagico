"""Carga y guarda la configuracion persistente en config.json."""
import copy
import json
import os
import re
import secrets
import string

from paths import config_path

# Dominio público PERMANENTE de Volante. Fijo en el código: la GUI no lo
# edita, el servidor ignora cualquier otro valor y config.json se autocorrige.
PUBLIC_DOMAIN = "volante.hausetienda.com.ar"
PUBLIC_URL = "https://" + PUBLIC_DOMAIN

# Un ÚNICO código de emparejamiento (pairCode): la PC lo muestra con su QR
# y el teléfono lo escribe en la web para sincronizar. 1 código = 1 teléfono.
PAIR_CODE_RE = re.compile(r"^[A-Z0-9]{4,10}$")


def new_pair_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def is_valid_pair_code(code):
    return bool(PAIR_CODE_RE.match(code or ""))


DEFAULT_CONFIG = {
    "port": 8443,
    "publicUrl": PUBLIC_URL,
    "pairCode": "",
    "internetEnabled": False,
    "tunnelToken": "",
    "showDpad": False,
    "telemetryPort": 9999,
    "maxSteerDegrees": 45,
    "axis": "auto",
    "deadzone": 0.05,
    "expo": 1.0,
    "invert": False,
    "autoCenter": True,
    "smoothing": 0.35,
    "pedalMode": "both",
    "pitchPedals": False,
    "buttons": {
        "handbrake": "A",
        "shiftUp": "RB",
        "shiftDown": "LB",
        "camera": "Y",
        "horn": "B",
    },
}


def load_config():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    path = config_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update(user)
                if isinstance(user.get("buttons"), dict):
                    merged = dict(DEFAULT_CONFIG["buttons"])
                    merged.update(user["buttons"])
                    cfg["buttons"] = merged
        except Exception:
            pass
    else:
        save_config(cfg)
    # Dominio fijo: lo que diga config.json (editado o borrado a mano) se
    # ignora; si el archivo discrepa, se reescribe corregido.
    if cfg.get("publicUrl") != PUBLIC_URL:
        cfg["publicUrl"] = PUBLIC_URL
        save_config(cfg)
    # Sistema antiguo de códigos múltiples: eliminado (1 código = 1 teléfono).
    changed = False
    for legacy in ("invites", "inviteOnly"):
        if legacy in cfg:
            cfg.pop(legacy, None)
            changed = True
    # Único código de emparejamiento: existe siempre (se genera al primer uso).
    if not is_valid_pair_code(cfg.get("pairCode")):
        cfg["pairCode"] = new_pair_code()
        changed = True
    if changed:
        save_config(cfg)
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
