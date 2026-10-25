"""Ventana Tkinter mínima: muestra el QR y el código del teléfono."""
import logging
import tkinter as tk
from tkinter import ttk

from config_store import load_config
from server import ServerManager
from version import __version__

try:
    import qrcode
    from PIL import ImageTk
except Exception:  # pragma: no cover
    qrcode = None
    ImageTk = None

log = logging.getLogger("volante.gui")

BG = "#05060c"
CARD = "#0b0f1a"
CARD2 = "#101728"
FG = "#e8f7ff"
MUTED = "#7d8db0"
ACCENT = "#00e5ff"
ACCENT_D = "#0091b3"
PINK = "#ff2bd6"
PURPLE = "#9d4bff"
LINE = "#153243"


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
        self.qr_url = ""

        root.title(f"Volante v{__version__}")
        root.configure(bg=BG)
        root.geometry("440x660")
        root.minsize(400, 580)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._apply_theme()
        self._build()
        log.info("GUI iniciada (v%s).", __version__)

        self.server.start()
        self.root.after(400, self._poll)

    # ---- construcción de la UI ----------------------------------------
    def _apply_theme(self):
        """Tema neón: botones ttk en clave oscura con acentos cian."""
        try:
            style = ttk.Style(self.root)
            style.theme_use("clam")
        except Exception:
            log.exception("No se pudo aplicar el tema ttk")
            return
        btn = {
            "background": CARD2,
            "foreground": ACCENT,
            "bordercolor": LINE,
            "darkcolor": CARD2,
            "lightcolor": CARD2,
            "arrowcolor": ACCENT,
            "borderwidth": 1,
            "focusthickness": 1,
            "focuscolor": ACCENT,
            "padding": (10, 7),
            "font": ("Consolas", 9, "bold"),
        }
        style.configure("TButton", **btn)
        style.map(
            "TButton",
            background=[("active", ACCENT), ("pressed", ACCENT_D),
                        ("disabled", CARD), ("!active", CARD2)],
            foreground=[("active", "#04070e"), ("pressed", "#04070e"),
                        ("disabled", MUTED), ("!active", ACCENT)],
            bordercolor=[("active", ACCENT), ("!active", LINE)],
            focuscolor=[("active", ACCENT)],
        )

    def _neon_bar(self, parent, colors=(ACCENT, PURPLE, PINK), height=3):
        """Barra degradada cian→violeta→magenta (versión Tk del glow del web)."""
        bar = tk.Canvas(parent, height=height, bg=BG,
                        highlightthickness=0, bd=0)
        bar.pack(fill="x")

        def _draw(evt=None):
            w = bar.winfo_width()
            if w <= 1:
                return
            bar.delete("all")
            n = max(w, 1)
            for i in range(n):
                t = i / max(n - 1, 1)
                if t < 0.5:
                    a, b, u = colors[0], colors[1], t * 2
                else:
                    a, b, u = colors[1], colors[2], (t - 0.5) * 2
                col = "#%02x%02x%02x" % tuple(
                    int(int(a[j:j + 2], 16) * (1 - u) + int(b[j:j + 2], 16) * u)
                    for j in (1, 3, 5))
                bar.create_rectangle(i, 0, i + 1, height,
                                     fill=col, outline="")
        bar.bind("<Configure>", _draw)
        bar.after(60, _draw)
        return bar

    def _build(self):
        wrap = tk.Frame(self.root, bg=BG, padx=18, pady=16)
        wrap.pack(fill="both", expand=True)

        # Cabecera con glitch cromático: sombra magenta 3px detrás del título
        # cian (estética cyberpunk; el texto sigue siendo «VOLANTE»).
        head = tk.Frame(wrap, bg=BG)
        head.pack(anchor="w")
        tk.Label(head, text="VOLANTE", bg=BG, fg="#4b0f3f",
                 font=("Consolas", 26, "bold")).place(x=3, y=3)
        tk.Label(head, text="VOLANTE", bg=BG, fg=ACCENT,
                 font=("Consolas", 26, "bold")).pack()

        self._neon_bar(wrap)
        tk.Label(wrap, text="Tu teléfono (iPhone o Android) como volante para juegos de carreras en PC",
                 bg=BG, fg=MUTED, font=("Consolas", 8),
                 wraplength=400, justify="left").pack(anchor="w", pady=(6, 12))

        card = tk.Frame(wrap, bg=CARD, padx=16, pady=16,
                        highlightthickness=1, highlightbackground=ACCENT_D)
        card.pack(fill="x")
        self._brackets(card, CARD)  # esquinas HUD: cian arriba, magenta abajo

        # Marco fino alrededor del QR (el QR se mantiene negro sobre blanco).
        qrbox = tk.Frame(card, bg=CARD, highlightthickness=1,
                         highlightbackground="#14506a")
        qrbox.pack()
        self.qr_label = tk.Label(qrbox, bg=CARD, fg=MUTED, text="Generando QR...",
                                 font=("Consolas", 11), width=28, height=12)
        self.qr_label.pack()

        # UN solo código de emparejamiento: 1 teléfono = 1 jugador.
        codefr = tk.Frame(card, bg=CARD)
        codefr.pack(fill="x", pady=(12, 0))
        tk.Label(codefr, text="CÓDIGO DEL TELÉFONO (escríbelo en la web)",
                 bg=CARD, fg=PINK, font=("Consolas", 9, "bold")).pack(anchor="w")
        self.code_var = tk.StringVar(value=self.server.pair_code())
        tk.Label(codefr, textvariable=self.code_var, bg="#04070e", fg=ACCENT,
                 font=("Consolas", 30, "bold"), padx=16, pady=6,
                 highlightthickness=1, highlightbackground=ACCENT_D,
                 highlightcolor=ACCENT).pack(fill="x", pady=(4, 0))
        crow = tk.Frame(card, bg=CARD)
        crow.pack(fill="x", pady=(8, 0))
        self.copy_btn = ttk.Button(
            crow, text="Copiar código",
            command=lambda: self._copy_code(self.server.pair_code(), self.copy_btn))
        self.copy_btn.pack()

        # Textura Tron (rejilla + scanlines) en el hueco inferior y cierre neón.
        self.tex = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0, height=70)
        self.tex.pack(fill="both", expand=True, pady=(14, 0))
        self.tex.bind("<Configure>", lambda evt: self._draw_texture())
        self._draw_texture()
        self._neon_bar(wrap, colors=(PINK, PURPLE, ACCENT))

    # ---- decoración cyberpunk -----------------------------------------
    def _bracket(self, parent, corner, color, bg, size=15, thick=2):
        """Esquina en L (corchete HUD) anclada a una esquina del parent."""
        cv = tk.Canvas(parent, width=size, height=size, bg=bg,
                       highlightthickness=0, bd=0)
        s = size - 1
        if corner == "tl":
            cv.create_line(0, 0, s, 0, fill=color, width=thick)
            cv.create_line(0, 0, 0, s, fill=color, width=thick)
            cv.place(x=1, y=1, anchor="nw")
        elif corner == "tr":
            cv.create_line(0, 0, s, 0, fill=color, width=thick)
            cv.create_line(s, 0, s, s, fill=color, width=thick)
            cv.place(relx=1.0, x=-1, y=1, anchor="ne")
        elif corner == "bl":
            cv.create_line(0, s, s, s, fill=color, width=thick)
            cv.create_line(0, 0, 0, s, fill=color, width=thick)
            cv.place(x=1, rely=1.0, y=-1, anchor="sw")
        else:  # br
            cv.create_line(0, s, s, s, fill=color, width=thick)
            cv.create_line(s, 0, s, s, fill=color, width=thick)
            cv.place(relx=1.0, rely=1.0, x=-1, y=-1, anchor="se")
        return cv

    def _brackets(self, parent, bg):
        self._bracket(parent, "tl", ACCENT, bg)
        self._bracket(parent, "tr", ACCENT, bg)
        self._bracket(parent, "bl", PINK, bg)
        self._bracket(parent, "br", PINK, bg)

    def _draw_texture(self):
        """Rejilla Tron + scanlines en el lienzo inferior (se redibuja al redimensionar)."""
        cv = getattr(self, "tex", None)
        if cv is None:
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        if w <= 2 or h <= 2:
            return
        cv.delete("all")
        for y in range(0, h, 3):          # scanlines CRT (un tono más oscuro)
            cv.create_line(0, y, w, y, fill="#02030a")
        grid = "#0e3a52"                  # rejilla cian oscura
        for x in range(0, w, 26):
            cv.create_line(x, 0, x, h, fill=grid)
        for y in range(0, h, 26):
            cv.create_line(0, y, w, y, fill=grid)

    # ---- acciones ------------------------------------------------------
    def _refresh_qr(self):
        # La web corre en el PC (HTTPS con certificado local). El QR apunta a la
        # IP de la WiFi para que el teléfono entre desde la red local.
        url = self.server.client_url(None, use_public=False)
        if not url or url == self.qr_url:
            return
        self.qr_url = url
        img = make_qr_image(url)
        if img is not None:
            self.qr_image = img
            self.qr_label.configure(image=img, text="", width=0, height=0)

    def _copy_code(self, cid, btn=None):
        """Copia el código al portapapeles (para escribirlo en el móvil)."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(cid)
            log.info("Código copiado al portapapeles: %s", cid)
        except Exception:
            log.exception("No se pudo copiar el código %s", cid)
        if btn is not None:
            try:
                old = btn.cget("text")
                btn.configure(text="¡Copiado!", state="disabled")
                self.root.after(1200, lambda: btn.configure(text=old, state="normal"))
            except Exception:
                pass

    def _on_close(self):
        log.info("GUI: cerrando Volante...")
        try:
            self.server.stop()
        except Exception:
            log.exception("Error deteniendo el servidor")
        self.root.destroy()

    # ---- refresco ------------------------------------------------------
    def _poll(self):
        self._refresh_qr()
        self.root.after(500, self._poll)


def run_gui(config=None):
    config = config or load_config()
    root = tk.Tk()
    VolanteGUI(root, config)
    root.mainloop()
