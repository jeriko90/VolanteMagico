"""Ventana Tkinter: muestra la URL, el QR, el estado y los botones de control."""
import logging
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import update
from config_store import load_config, save_config
from logging_setup import log_path
from server import ServerManager
from version import __version__

try:
    import qrcode
    from PIL import ImageTk
except Exception:  # pragma: no cover
    qrcode = None
    ImageTk = None

log = logging.getLogger("volante.gui")

BG = "#14161c"
CARD = "#1d212b"
FG = "#e8eaf0"
MUTED = "#9aa3b2"
ACCENT = "#3ea6ff"
GREEN = "#37d67a"
RED = "#ff5c5c"


def make_qr_image(url, size=260):
    if qrcode is None or ImageTk is None:
        return None
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size))
    return ImageTk.PhotoImage(img)


class VolanteGUI:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.server = ServerManager(config)
        self.qr_image = None
        self._pending_update = None
        self._updating = False

        root.title(f"Volante v{__version__}")
        root.configure(bg=BG)
        root.geometry("480x700")
        root.minsize(430, 640)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        log.info("GUI iniciada (v%s).", __version__)

        self.server.start()
        self.root.after(400, self._poll)
        self.root.after(1500, lambda: self._check_updates(manual=False))

    # ---- construcción de la UI ----------------------------------------
    def _build(self):
        wrap = tk.Frame(self.root, bg=BG, padx=18, pady=16)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Volante", bg=BG, fg=FG,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(wrap, text="Tu teléfono (iPhone o Android) como volante para juegos de carreras en PC",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12))

        card = tk.Frame(wrap, bg=CARD, padx=16, pady=16)
        card.pack(fill="x")

        self.qr_label = tk.Label(card, bg=CARD, fg=MUTED, text="Generando URL...",
                                 font=("Segoe UI", 11), width=28, height=12)
        self.qr_label.pack()

        tk.Label(card, text="Abre esta dirección en el navegador del teléfono:",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(10, 2))

        self.url_var = tk.StringVar(value="iniciando...")
        url_entry = tk.Entry(card, textvariable=self.url_var, justify="center",
                             font=("Consolas", 13, "bold"), bd=0, readonlybackground="#0f1116",
                             fg=FG, insertbackground=FG)
        url_entry.configure(state="readonly")
        url_entry.pack(fill="x", pady=4, ipady=6)

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Abrir en este PC", command=self._open_url).pack(side="left")
        ttk.Button(row, text="Abrir el certificado (/ca)", command=self._open_ca).pack(side="left", padx=6)
        ttk.Button(row, text="Abrir logs", command=self._open_logs).pack(side="left")

        ttk.Button(card, text="¿Cómo conectar el teléfono? (iOS / Android)",
                   command=self._open_help).pack(fill="x", pady=(10, 0))

        # estado
        status = tk.Frame(wrap, bg=BG)
        status.pack(fill="x", pady=(14, 0))
        self.dot = tk.Canvas(status, width=14, height=14, bg=BG, highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(2, 2, 12, 12, fill=RED, outline="")
        self.status_label = tk.Label(status, text="Esperando conexión del teléfono",
                                     bg=BG, fg=FG, font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=8)
        self.meta_label = tk.Label(wrap, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.meta_label.pack(anchor="w", pady=(4, 0))

        # botones
        btns = tk.Frame(wrap, bg=BG)
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text="Calibrar", command=self.server.request_calibrate).pack(
            side="left", expand=True, fill="x", padx=3)
        ttk.Button(btns, text="Recentrar", command=self.server.request_recenter).pack(
            side="left", expand=True, fill="x", padx=3)
        ttk.Button(btns, text="Reiniciar mando", command=self.server.request_reset).pack(
            side="left", expand=True, fill="x", padx=3)

        # actualizaciones
        upd = tk.Frame(wrap, bg=BG)
        upd.pack(fill="x", pady=(14, 0))
        self.update_btn = ttk.Button(upd, text="Chequear actualizaciones",
                                     command=self._on_update_click)
        self.update_btn.pack(side="left")
        self.update_label = tk.Label(upd, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9),
                                     wraplength=240, justify="left")
        self.update_label.pack(side="left", padx=8)
        tk.Label(upd, text=f"v{__version__}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="right")

        self.footer = tk.Label(wrap, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8),
                               wraplength=430, justify="left")
        self.footer.pack(anchor="w", pady=(12, 0))

        tk.Label(wrap, text="Logs: " + log_path(), bg=BG, fg=MUTED,
                 font=("Segoe UI", 7), wraplength=430, justify="left").pack(
            anchor="w", pady=(4, 0))

    # ---- acciones ------------------------------------------------------
    def _open_url(self):
        if self.server.url:
            webbrowser.open(self.server.url)

    def _open_ca(self):
        if self.server.url:
            webbrowser.open(self.server.url + "/ca")

    def _open_logs(self):
        path = log_path()
        try:
            if os.path.isfile(path):
                os.startfile(path)
            else:
                os.startfile(os.path.dirname(path))
        except Exception:
            log.exception("No se pudieron abrir los logs")

    def _open_help(self):
        top = tk.Toplevel(self.root)
        top.title("Cómo conectar el teléfono")
        top.configure(bg=BG)
        top.transient(self.root)
        top.resizable(False, False)

        box = tk.Frame(top, bg=BG, padx=20, pady=18)
        box.pack(fill="both", expand=True)

        tk.Label(box, text="Cómo conectar el teléfono", bg=BG, fg=FG,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")

        steps = (
            "1. Abre la URL (o escanea el QR) en el navegador del teléfono.\n\n"
            "iPhone / iPad (Safari):\n"
            "   - Acepta el aviso del certificado.\n"
            "   - Pulsa «Abrir el certificado (/ca)», instala el perfil y confíalo en\n"
            "     Ajustes → General → VPN y dispositivo → Ajustes de confianza.\n\n"
            "Android (Chrome / Edge):\n"
            "   - Acepta «La conexión no es privada» → Continuar.\n\n"
            "En ambos: vuelve a la página y toca «Activar sensores»."
        )
        tk.Label(box, text=steps, bg=BG, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", pady=(10, 14))

        btns = tk.Frame(box, bg=BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="Abrir el certificado (/ca)", command=self._open_ca).pack(side="left")
        ttk.Button(btns, text="Cerrar", command=top.destroy).pack(side="right")

        top.update_idletasks()
        top.geometry(f"+{self.root.winfo_rootx() + 40}+{self.root.winfo_rooty() + 60}")

    # ---- actualizaciones ----------------------------------------------
    def _on_update_click(self):
        if self._updating:
            return
        if self._pending_update:
            self._prompt_update(self._pending_update)
        else:
            self._check_updates(manual=True)

    def _check_updates(self, manual=True):
        if not update.is_frozen():
            self.update_label.configure(text="Actualizaciones solo en el .exe")
            return
        self.update_btn.configure(state="disabled")
        self.update_label.configure(text="Buscando actualizaciones...")
        threading.Thread(target=self._check_worker, args=(manual,), daemon=True).start()

    def _check_worker(self, manual):
        error = None
        info = None
        try:
            info = update.check_update()
        except Exception as exc:  # sin red, github caido, etc.
            error = exc
            log.warning("No se pudieron comprobar actualizaciones: %s", exc)
        self.root.after(0, lambda: self._update_result(info, error, manual))

    def _update_result(self, info, error, manual):
        self.update_btn.configure(state="normal")
        if error is not None:
            self.update_label.configure(text="No se pudo comprobar (¿sin internet?)")
            return
        if not info:
            self.update_label.configure(text="Ya tienes la última versión.")
            if manual:
                messagebox.showinfo("Actualizaciones",
                                    f"Ya tienes la última versión (v{__version__}).")
            return
        self._pending_update = info
        remote = info.get("version")
        self.update_label.configure(text=f"¡Nueva versión {remote} disponible!")
        if manual:
            self._prompt_update(info)
        else:
            log.info("Actualizacion disponible notificada en la GUI: %s", remote)

    def _prompt_update(self, info):
        remote = info.get("version")
        notes = info.get("notes")
        msg = f"Hay una nueva versión de Volante ({remote}).\n\n¿Descargar y reiniciar ahora?"
        if notes:
            msg = f"Hay una nueva versión de Volante ({remote}).\n\n{notes}\n\n¿Descargar y reiniciar ahora?"
        if not messagebox.askyesno("Actualización disponible", msg):
            return
        self._do_update(info)

    def _do_update(self, info):
        self._updating = True
        self._pending_update = None
        self.update_btn.configure(state="disabled", text="Actualizando...")
        self.update_label.configure(text="Descargando... 0%")
        threading.Thread(target=self._download_worker, args=(info,), daemon=True).start()

    def _download_worker(self, info):
        def on_progress(fraction):
            pct = int(fraction * 100)
            self.root.after(0, lambda: self.update_label.configure(text=f"Descargando... {pct}%"))

        try:
            mode, path = update.download_and_restart(info, progress_cb=on_progress)
        except Exception as exc:
            self.root.after(0, lambda: self._update_failed(exc))
            return
        self.root.after(0, lambda: self._update_done(mode, path))

    def _update_failed(self, exc):
        log.exception("Fallo al actualizar: %s", exc)
        self._updating = False
        self.update_btn.configure(state="normal", text="Chequear actualizaciones")
        self.update_label.configure(text="Error al actualizar.")
        messagebox.showerror("Actualización", f"No se pudo actualizar:\n{exc}")

    def _update_done(self, mode, path):
        if mode == "restart":
            self.update_label.configure(text="Reiniciando con la nueva versión...")
            self.root.after(400, self._restart)
        else:
            self._updating = False
            self.update_btn.configure(state="normal", text="Chequear actualizaciones")
            self.update_label.configure(text="Descargada (reemplazar a mano).")
            messagebox.showinfo(
                "Actualización descargada",
                "Se descargó la nueva versión en:\n\n" + path +
                "\n\nCierra Volante y reemplaza el .exe por este archivo.",
            )

    def _restart(self):
        log.info("Reinicio para aplicar la actualización.")
        try:
            self.server.stop()
        except Exception:
            log.exception("Error deteniendo el servidor antes de actualizar")
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _on_close(self):
        log.info("GUI: cerrando Volante...")
        try:
            self.server.stop()
        except Exception:
            log.exception("Error deteniendo el servidor")
        self.root.destroy()

    # ---- refresco de estado -------------------------------------------
    def _poll(self):
        st = self.server.status()
        if st.get("url") and self.url_var.get() != st["url"]:
            self.url_var.set(st["url"])
            self.qr_image = make_qr_image(st["url"])
            if self.qr_image is not None:
                self.qr_label.configure(image=self.qr_image, text="", width=0, height=0)

        if st.get("error"):
            self.footer.configure(text="Error: " + st["error"], fg=RED)
        elif st.get("connected"):
            self.dot.itemconfigure(self.dot_id, fill=GREEN)
            self.status_label.configure(text=f"Conectado ({st['clients']} dispositivo/s)")
            parts = []
            if st.get("latency_ms") is not None:
                parts.append(f"Latencia: {st['latency_ms']} ms")
            if st.get("battery") is not None:
                parts.append(f"Batería: {st['battery']}%")
            self.meta_label.configure(text="   ".join(parts))
        else:
            self.dot.itemconfigure(self.dot_id, fill=RED)
            self.status_label.configure(text="Esperando conexión del teléfono")
            self.meta_label.configure(text="")

        self.root.after(500, self._poll)


def run_gui(config=None):
    config = config or load_config()
    root = tk.Tk()
    VolanteGUI(root, config)
    root.mainloop()