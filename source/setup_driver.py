"""Detección e instalación del driver ViGEmBus y de la regla de firewall.

El driver y el firewall necesitan privilegios de administrador, así que si faltan
relanzamos la app una sola vez con UAC (modo --elevate-setup).
"""
import ctypes
import logging
import os
import subprocess
import sys

from paths import is_frozen, resource_path

log = logging.getLogger("volante.driver")

VIGEM_SYS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "drivers", "ViGEmBus.sys")
FIREWALL_RULE = "Volante"


def vigem_installed():
    installed = os.path.isfile(VIGEM_SYS)
    return installed


def firewall_rule_exists(rule=FIREWALL_RULE):
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=" + rule],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        exists = result.returncode == 0
        log.debug("Comprobación de regla de firewall '%s': existe=%s", rule, exists)
        return exists
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo comprobar la regla de firewall: %s", exc)
        return False


def _msi_path():
    return resource_path("vigembus", "ViGEmBusSetup_x64.msi")


def install_vigembus():
    msi = _msi_path()
    if not os.path.isfile(msi):
        log.error("No se encontró el instalador de ViGEmBus en %s", msi)
        return False, f"No se encontró el instalador de ViGEmBus ({msi})"
    try:
        log.info("Instalando ViGEmBus desde %s ...", msi)
        result = subprocess.run(
            ["msiexec", "/i", msi, "/qn", "/norestart"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            log.info("ViGEmBus instalado correctamente.")
            return True, "ViGEmBus instalado."
        log.error("msiexec devolvió %s: %s", result.returncode, result.stderr or result.stdout)
        return False, f"msiexec devolvió {result.returncode}: {result.stderr or result.stdout}"
    except Exception as exc:  # noqa: BLE001
        log.exception("Error instalando ViGEmBus")
        return False, f"Error instalando ViGEmBus: {exc}"


def add_firewall_rule(port, rule=FIREWALL_RULE):
    try:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                "name=" + rule, "dir=in", "action=allow",
                "protocol=TCP", "localport=" + str(port),
            ],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        log.info("Regla de firewall '%s' añadida para el puerto %s.", rule, port)
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo añadir la regla de firewall: %s", exc)


def run_elevated_setup(port):
    """Modo --elevate-setup: se ejecuta con admin. Instala driver y firewall."""
    log.info("== Configuración elevada iniciada (puerto %s) ==", port)
    results = []
    if not vigem_installed():
        ok, msg = install_vigembus()
        results.append(("driver", ok, msg))
    else:
        results.append(("driver", True, "ViGEmBus ya estaba instalado."))

    add_firewall_rule(port)
    results.append(("firewall", True, f"Regla de firewall para el puerto {port}."))

    for _name, _ok, msg in results:
        print(msg)
    log.info("== Configuración elevada terminada ==")
    return 0


def _elevated_parameters():
    if is_frozen():
        return "--elevate-setup"
    script = os.path.abspath(sys.argv[0])
    return f'"{script}" --elevate-setup'


def relaunch_elevated():
    """Relanza la app con UAC. Devuelve True si el usuario aceptó."""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            _elevated_parameters(),
            None,
            1,
        )
        return True
    except Exception:
        return False


def ensure_setup(port, log=print):
    """Asegura driver + firewall. Si falta algo, pide UAC una vez."""
    need_driver = not vigem_installed()
    need_firewall = not firewall_rule_exists()
    if not need_driver and not need_firewall:
        return True

    if need_driver:
        log("Falta el driver ViGEmBus: se instalará (requiere administrador)...")
    if need_firewall:
        log("Añadiendo regla de firewall (requiere administrador)...")
    return relaunch_elevated()
