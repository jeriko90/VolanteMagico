# -*- mode: python ; coding: utf-8 -*-
"""Empaqueta Volante en un único .exe portátil (onefile).

Incluye el intérprete de Python, todas las librerías, los archivos web/,
la DLL ViGEmClient y el instalador MSI de ViGEmBus (para auto-instalarlo).
"""
import importlib.util
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH)

# Localizar vgamepad sin importarlo (importarlo se conecta a ViGEmBus, que no
# existe en una máquina de build) y así acceder a sus DLLs/MSI.
_vg_spec = importlib.util.find_spec("vgamepad")
if _vg_spec is None or not _vg_spec.submodule_search_locations:
    raise SystemExit("vgamepad no está instalado. Ejecuta: pip install vgamepad")
vg_root = Path(_vg_spec.submodule_search_locations[0])

_aio_datas, _aio_bins, _aio_hidden = collect_all("aiohttp")
_qr_datas, _qr_bins, _qr_hidden = collect_all("qrcode")
_vg_datas, _vg_bins, _vg_hidden = collect_all("vgamepad")

# DLL de ViGEmClient (x64/x86)
_dll_datas = []
_client_root = vg_root / "win" / "vigem" / "client"
for _arch in ("x64", "x86"):
    _dll = _client_root / _arch / "ViGEmClient.dll"
    if _dll.is_file():
        _dll_datas.append((str(_dll), f"vgamepad/win/vigem/client/{_arch}"))
if not _dll_datas:
    raise SystemExit(f"No se encontró ViGEmClient.dll en {_client_root}")

# MSI de ViGEmBus para auto-instalación en el primer arranque
_msi = vg_root / "win" / "vigem" / "install" / "x64" / "ViGEmBusSetup_x64.msi"
if not _msi.is_file():
    raise SystemExit(f"No se encontró el instalador de ViGEmBus en {_msi}")
_msi_datas = [(str(_msi), "vigembus")]

_web_data = (str(project_root / "web"), "web")

_hiddenimports = sorted(set(
    _vg_hidden + _aio_hidden + _qr_hidden
    + collect_submodules("multidict")
    + collect_submodules("yarl")
    + collect_submodules("frozenlist")
    + collect_submodules("aiosignal")
    + ["cryptography", "cryptography.x509", "cryptography.hazmat",
       "plistlib", "PIL._tkinter_finder", "tkinter", "tkinter.ttk"]
))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=_aio_bins + _vg_bins,
    datas=_aio_datas + _qr_datas + _vg_datas + _dll_datas + _msi_datas + [_web_data],
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "pandas", "matplotlib", "scipy", "PIL.ImageQt"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Volante",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
