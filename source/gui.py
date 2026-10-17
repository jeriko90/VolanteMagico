"""Ventana Tkinter: muestra la URL, el QR, el estado y los botones de control."""
import logging
import os
import tkinter as tk
import webbrowser
from tkinter import ttk

from config_store import load_config, save_config
from logging_setup import log_path
from server import ServerManager

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

        root.title("Volante")
        root.configure(bg=BG)
        root.geometry("480x720")
        root.minsize(420, 640)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        log.info("GUI iniciada.")

        self.server.start()
        self.root.after(400, self._poll)

    # ---- construcción de la UI ----------------------------------------
    def _build(self):
        wrap = tk.Frame(self.root, bg=BG, padx=18, pady=16)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Volante", bg=BG, fg=FG,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(wrap, text="Tu iPhone como volante para juegos de carreras en PC",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12))

        card = tk.Frame(wrap, bg=CARD, padx=16, pady=16)
        card.pack(fill="x")

        self.qr_label = tk.Label(card, bg=CARD, fg=MUTED, text="Generando URL...",
                                 font=("Segoe UI", 11), width=28, height=12)
        self.qr_label.pack()

        tk.Label(card, text="Abre esta dirección en Safari (iPhone):",
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

        tk.Label(card, text="iPhone: abrir la URL → aceptar aviso → descargar/instalar el "
                            "perfil del certificado → Ajustes → General → VPN y "
                            "dispositivo → activar confianza → volver y tocar 'Activar sensores'.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8), wraplength=400, justify="left").pack(
            anchor="w", pady=(12, 0))

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

        self.footer = tk.Label(wrap, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8),
                               wraplength=430, justify="left")
        self.footer.pack(anchor="w", pady=(14, 0))

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