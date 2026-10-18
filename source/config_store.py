"""Carga y guarda la configuracion persistente en config.json."""
import copy
import json
import os

from paths import config_path

DEFAULT_CONFIG = {
    "port": 8443,
    "publicUrl": "",
    "internetEnabled": False,
    "tunnelToken": "",
    "invites": [],
    "inviteOnly": True,
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
                if not isinstance(cfg.get("invites"), list):
                    cfg["invites"] = []
                if cfg.get("publicUrl") is None:
                    cfg["publicUrl"] = ""
        except Exception:
            pass
    else:
        save_config(cfg)
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
