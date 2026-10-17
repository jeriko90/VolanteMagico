"""Punto de entrada de Volante.

Uso:
  python main.py                 -> arranca la GUI (y pide UAC una vez si falta el driver)
  python main.py --elevate-setup -> instala ViGEmBus + firewall con permisos de admin
"""
import logging
import sys
import time

from config_store import load_config
from logging_setup import setup_logging
from setup_driver import (
    ensure_setup,
    firewall_rule_exists,
    run_elevated_setup,
    vigem_installed,
)

log = logging.getLogger("volante.main")


def _wait_for_driver(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        if vigem_installed():
            log.info("Driver ViGEmBus detectado tras %.1fs", time.time() - start)
            return True
        time.sleep(1)
    ok = vigem_installed()
    log.warning("Espera del driver terminada. Instalado=%s", ok)
    return ok


def main():
    setup_logging()

    if "--elevate-setup" in sys.argv:
        cfg = load_config()
        log.info("Modo elevado: instalando driver y firewall (puerto %s)", cfg.get("port"))
        return run_elevated_setup(int(cfg.get("port", 8443)))

    config = load_config()
    port = int(config.get("port", 8443))
    log.info("Configuracion cargada: puerto=%s axis=%s maxSteer=%s pedalMode=%s",
             port, config.get("axis"), config.get("maxSteerDegrees"), config.get("pedalMode"))

    if not vigem_installed() or not firewall_rule_exists():
        log.info("Falta driver y/o regla de firewall: preparando el sistema (UAC una vez)...")
        ensure_setup(port, log=lambda m: log.info(m))
        _wait_for_driver(timeout=60)
    else:
        log.info("ViGEmBus instalado y regla de firewall presente.")

    from gui import run_gui

    run_gui(config)
    log.info("=== Volante finalizado ===")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
