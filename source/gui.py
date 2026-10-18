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
from server import ServerManager, MAX_PLAYERS
from tunnel import TunnelManager, download_cloudflared, find_cloudflared
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
        # Con dominio guardado, el QR nace en modo público (internet).
        self.qr_mode = "public" if (config.get("publicUrl") or "").strip() else "local"
        self._clients_key = None
        self._inet_win = None
        self.inet_status = None
        self.tunnel = TunnelManager(config)

        root.title(f"Volante v{__version__}")
        root.configure(bg=BG)
        root.geometry("480x800")
        root.minsize(430, 700)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        log.info("GUI iniciada (v%s).", __version__)

        self.server.start()
        if self.tunnel.enabled:
            log.info("Conexión por internet habilitada: iniciando túnel...")
            self.tunnel.start()
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

        # URL pública (dominio tras Cloudflare Tunnel) + origen del QR
        pub = tk.Frame(card, bg=CARD)
        pub.pack(fill="x", pady=(10, 0))
        tk.Label(pub, text="URL pública (dominio, opcional):", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")
        pubrow = tk.Frame(pub, bg=CARD)
        pubrow.pack(fill="x", pady=(2, 0))
        self.public_var = tk.StringVar(value=(self.config.get("publicUrl") or ""))
        pub_entry = tk.Entry(pubrow, textvariable=self.public_var, justify="left",
                             font=("Consolas", 10), bd=0, readonlybackground="#0f1116",
                             fg=FG, insertbackground=FG)
        pub_entry.pack(side="left", fill="x", expand=True, ipady=4)
        ttk.Button(pubrow, text="Guardar", command=self._save_public_url).pack(
            side="left", padx=(6, 0))

        qrrow = tk.Frame(card, bg=CARD)
        qrrow.pack(fill="x", pady=(8, 0))
        tk.Label(qrrow, text="QR mostrado:", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(qrrow, text="Local (IP)", command=lambda: self._set_qr_mode("local")).pack(
            side="left", padx=(6, 2))
        ttk.Button(qrrow, text="Público (dominio)", command=lambda: self._set_qr_mode("public")).pack(
            side="left", padx=2)
        ttk.Button(qrrow, text="Internet…", command=self._open_internet_dialog).pack(
            side="right")

        self.internet_label = tk.Label(card, text="Internet: apagado", bg=CARD,
                                       fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.internet_label.pack(fill="x", pady=(6, 0))

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

        # clientes (teléfonos) conectados y activación
        cl_head = tk.Frame(wrap, bg=BG)
        cl_head.pack(fill="x", pady=(14, 0))
        tk.Label(cl_head, text="Clientes (teléfonos)", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(cl_head, text="Nuevo QR de cliente",
                   command=self._new_invite).pack(side="right")
        self.clients_frame = tk.Frame(wrap, bg=CARD, padx=10, pady=8)
        self.clients_frame.pack(fill="x", pady=(6, 0))
        self._clients_empty = None
        self.invite_only_var = tk.BooleanVar(
            value=bool(self.config.get("inviteOnly", True)))
        tk.Checkbutton(wrap, text="Solo códigos invitados (rechaza cualquier otro teléfono)",
                       variable=self.invite_only_var, command=self._toggle_invite_only,
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                       activeforeground=FG, font=("Segoe UI", 9),
                       highlightthickness=0, bd=0, anchor="w").pack(
            fill="x", pady=(6, 0))
        tk.Label(wrap, text=("Cada teléfono entra con su código/QR y maneja su propio mando "
                             "(hasta 4 jugadores). Crea un «Nuevo QR de cliente» por jugador."),
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=430,
                 justify="left").pack(anchor="w", pady=(4, 0))

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
        url = self.url_var.get() or self.server.url
        if url and not url.startswith("iniciando"):
            webbrowser.open(url)

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

    # ---- clientes / QR por cliente ------------------------------------
    def _use_public(self):
        return (self.qr_mode == "public" and
                bool((self.config.get("publicUrl") or "").strip()))

    def _refresh_qr(self):
        url = self.server.client_url(None, use_public=self._use_public())
        if not url:
            return
        self.url_var.set(url)
        self.qr_image = make_qr_image(url)
        if self.qr_image is not None:
            self.qr_label.configure(image=self.qr_image, text="", width=0, height=0)

    def _set_qr_mode(self, mode):
        if mode == "public" and not (self.config.get("publicUrl") or "").strip():
            messagebox.showinfo(
                "URL pública",
                "Primero guarda un dominio (p. ej. https://volante.hausetienda.com.ar) "
                "en el campo de arriba.")
            return
        self.qr_mode = mode
        self._refresh_qr()

    def _save_public_url(self):
        self.server.set_public_url(self.public_var.get())
        saved = (self.config.get("publicUrl") or "").strip()
        self.public_var.set(saved)
        if saved:
            self.qr_mode = "public"
        self._refresh_qr()

    def _new_invite(self):
        if len(self.server.invites) >= MAX_PLAYERS:
            messagebox.showinfo(
                "Clientes",
                f"Ya hay {MAX_PLAYERS} códigos creados (tope de jugadores). "
                "Quita uno antes de crear otro.")
            return
        cid = self.server.create_invite()
        self._show_client_qr(cid)

    def _show_client_qr(self, cid):
        top = tk.Toplevel(self.root)
        top.title(f"QR del cliente {cid}")
        top.configure(bg=BG)
        top.transient(self.root)
        box = tk.Frame(top, bg=BG, padx=18, pady=16)
        box.pack(fill="both", expand=True)
        url = self.server.client_url(cid, use_public=self._use_public())
        img = make_qr_image(url, size=240)
        if img is not None:
            tk.Label(box, image=img, bg=BG).pack()
            top.qr_image = img  # evita el recolector de basura
        tk.Label(box, text=f"ID del cliente: {cid}", bg=BG, fg=ACCENT,
                 font=("Consolas", 14, "bold")).pack(pady=(10, 2))
        tk.Label(box, text=url, bg=BG, fg=MUTED, font=("Consolas", 9),
                 wraplength=380, justify="center").pack()
        tk.Label(box, text=("Envía este QR o URL a ese teléfono. Al abrirlo entra como su\n"
                            "propio jugador (mando independiente). También puede escribir\n"
                            "el código a mano en la pantalla de inicio."),
                 bg=BG, fg=MUTED, font=("Segoe UI", 9), justify="left").pack(pady=(10, 0))
        ttk.Button(box, text="Cerrar", command=top.destroy).pack(pady=(12, 0))

    def _refresh_clients(self, rows):
        key = str([(r["id"], r.get("player"), r.get("pending"), r["device"],
                    r["latency"], r["battery"]) for r in rows])
        if key == self._clients_key:
            return
        self._clients_key = key
        for child in self.clients_frame.winfo_children():
            child.destroy()
        if not rows:
            tk.Label(self.clients_frame, text="Sin teléfonos conectados todavía.",
                     bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            return
        for r in rows[:12]:
            row = tk.Frame(self.clients_frame, bg=CARD)
            row.pack(fill="x", pady=2)
            if r.get("pending"):
                # Código reservado con su QR, aún sin abrir en ningún teléfono.
                num = f"Jugador {r['player']}" if r.get("player") else "Código"
                tk.Label(row, text=f"○ {num} · {r['id']} · esperando su QR",
                         bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
                ttk.Button(row, text="Quitar",
                           command=lambda cid=r["id"]: self._remove_invite(cid)).pack(
                    side="right")
                ttk.Button(row, text="QR",
                           command=lambda cid=r["id"]: self._show_client_qr(cid)).pack(
                    side="right", padx=(0, 6))
                continue
            num = f"Jugador {r['player']}" if r.get("player") else "Jugador"
            info = f"● {num} · {r['id']} · {r['device']}"
            if r["latency"] is not None:
                info += f" · {r['latency']} ms"
            if r["battery"] is not None:
                info += f" · {r['battery']}%"
            tk.Label(row, text=info, bg=CARD, fg=GREEN,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            ttk.Button(row, text="Quitar",
                       command=lambda cid=r["id"]: self.server.request_kick(cid)).pack(
                side="right")
            ttk.Button(row, text="QR",
                       command=lambda cid=r["id"]: self._show_client_qr(cid)).pack(
                side="right", padx=(0, 6))

    def _remove_invite(self, cid):
        if messagebox.askyesno("Quitar código",
                               f"¿Quitar el código {cid}? Su QR dejará de funcionar."):
            self.server.remove_invite(cid)

    def _toggle_invite_only(self):
        self.server.set_invite_only(bool(self.invite_only_var.get()))

    # ---- conexión por internet (Cloudflare Tunnel) ---------------------
    def _open_internet_dialog(self):
        if self._inet_win is not None:
            try:
                self._inet_win.lift()
                return
            except Exception:
                self._inet_win = None

        top = tk.Toplevel(self.root)
        top.title("Conexión por internet")
        top.configure(bg=BG)
        top.transient(self.root)
        self._inet_win = top
        top.protocol("WM_DELETE_WINDOW", self._close_internet_dialog)

        box = tk.Frame(top, bg=BG, padx=18, pady=16)
        box.pack(fill="both", expand=True)

        tk.Label(box, text="Conexión por internet (Cloudflare Tunnel)", bg=BG, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(box, text="Al conectar, Volante levanta el túnel solo cada vez que se abre.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))

        tokrow = tk.Frame(box, bg=BG)
        tokrow.pack(fill="x", pady=(4, 0))
        tk.Label(tokrow, text="Token:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self.token_var = tk.StringVar(value=(self.config.get("tunnelToken") or ""))
        tok = tk.Entry(tokrow, textvariable=self.token_var, show="*", bd=0,
                       font=("Consolas", 10), readonlybackground="#0f1116",
                       fg=FG, insertbackground=FG)
        tok.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=4)

        domrow = tk.Frame(box, bg=BG)
        domrow.pack(fill="x", pady=(8, 0))
        tk.Label(domrow, text="Dominio:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self.domain_var = tk.StringVar(value=(self.config.get("publicUrl") or ""))
        dom = tk.Entry(domrow, textvariable=self.domain_var, bd=0,
                       font=("Consolas", 10), readonlybackground="#0f1116",
                       fg=FG, insertbackground=FG)
        dom.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=4)
        tk.Label(box, text="Ej.: volante.hausetienda.com.ar  (el mismo hostname del túnel)",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(box, bg=BG)
        btns.pack(fill="x", pady=(10, 0))
        self.inet_connect_btn = ttk.Button(btns, text="Conectar y guardar",
                                           command=self._inet_connect)
        self.inet_connect_btn.pack(side="left")
        ttk.Button(btns, text="Desconectar", command=self._inet_disconnect).pack(
            side="left", padx=6)
        self.inet_dl_btn = ttk.Button(btns, text="Descargar cloudflared",
                                      command=self._download_cloudflared)
        self.inet_dl_btn.pack(side="left")

        self.inet_status = tk.Label(box, text="", bg=BG, fg=MUTED,
                                    font=("Segoe UI", 9), anchor="w", justify="left",
                                    wraplength=380)
        self.inet_status.pack(fill="x", pady=(10, 0))
        self._update_inet_labels()

        pasos = (
            "Pasos (una sola vez) en el dashboard de Cloudflare:\n"
            "1. Networking → Tunnels → Create a tunnel (tipo cloudflared), nombre «volante».\n"
            "2. Routes/Public Hostname → Add: "
            "volante.hausetienda.com.ar → https://localhost:8443\n"
            "   y activa TLS → Disable TLS certificate verification (cert autofirmado).\n"
            "3. Copia el token (el valor eyJ…) del comando de instalación y pégalo arriba.\n"
            "4. Pulsa «Conectar y guardar»: el QR y cada QR de cliente usarán el dominio.\n"
            "5. Borra el registro A naranja con IP privada si sigue existiendo."
        )
        tk.Label(box, text=pasos, bg=BG, fg=MUTED, font=("Segoe UI", 8),
                 justify="left").pack(anchor="w", pady=(12, 0))

        ttk.Button(box, text="Cerrar", command=self._close_internet_dialog).pack(
            anchor="e", pady=(10, 0))

        top.update_idletasks()
        top.geometry(f"+{self.root.winfo_rootx() + 30}+{self.root.winfo_rooty() + 50}")

    def _close_internet_dialog(self):
        win = self._inet_win
        self._inet_win = None
        try:
            if win is not None:
                win.destroy()
        except Exception:
            pass

    def _save_token(self):
        token = self.token_var.get().strip()
        self.config["tunnelToken"] = token
        return token

    def _inet_connect(self):
        token = self._save_token()
        if not token:
            messagebox.showinfo("Conexión por internet",
                                "Pega primero el token de Cloudflare (paso 3 del diálogo).")
            return
        domain = self.domain_var.get().strip()
        if domain:
            self.server.set_public_url(domain)
        self.config["internetEnabled"] = True
        save_config(self.config)
        self.tunnel.start()
        self._update_inet_labels()

    def _inet_disconnect(self):
        self._save_token()
        self.config["internetEnabled"] = False
        save_config(self.config)
        self.tunnel.stop()
        self._update_inet_labels()

    def _download_cloudflared(self):
        if find_cloudflared():
            messagebox.showinfo("cloudflared", "cloudflared ya está disponible.")
            return
        self.inet_dl_btn.configure(state="disabled", text="Descargando… 0%")

        def work():
            try:
                path = download_cloudflared(
                    progress_cb=lambda f: self.root.after(
                        0, lambda: self.inet_dl_btn.configure(
                            text=f"Descargando… {int(f * 100)}%")))
                self.root.after(0, lambda: self._dl_done(path, None))
            except Exception as exc:
                self.root.after(0, lambda: self._dl_done(None, exc))

        threading.Thread(target=work, daemon=True).start()

    def _dl_done(self, path, error):
        self.inet_dl_btn.configure(state="normal", text="Descargar cloudflared")
        if error is not None:
            messagebox.showerror("cloudflared", f"No se pudo descargar:\n{error}")
            return
        log.info("cloudflared descargado en %s", path)
        self._update_inet_labels()
        if self.tunnel.enabled:
            self.tunnel.start()

    def _update_inet_labels(self):
        st = self.tunnel.status()
        state = st.get("state")
        public = (self.config.get("publicUrl") or "").strip()
        if state == "connected":
            txt = "Internet: conectado ✓ " + public
            color = GREEN
        elif state == "starting":
            txt = "Internet: conectando…"
            color = MUTED
        elif state == "error":
            txt = "Internet: " + (st.get("detail") or "error")
            color = RED
        else:
            txt = "Internet: apagado"
            color = MUTED
        if not st.get("binary") and state != "off":
            txt = "Internet: falta cloudflared («Descargar cloudflared»)"
            color = RED
        self.internet_label.configure(text=txt, fg=color)
        if self.inet_status is not None and self._inet_win is not None:
            self.inet_status.configure(text=txt, fg=color)

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
            self.tunnel.stop()
        except Exception:
            log.exception("Error deteniendo el túnel")
        try:
            self.server.stop()
        except Exception:
            log.exception("Error deteniendo el servidor")
        self.root.destroy()

    # ---- refresco de estado -------------------------------------------
    def _poll(self):
        st = self.server.status()
        want_url = self.server.client_url(None, use_public=self._use_public())
        if want_url and self.url_var.get() != want_url:
            self._refresh_qr()

        rows = self.server.players_snapshot()
        self._refresh_clients(rows)
        self._update_inet_labels()

        if st.get("error"):
            self.footer.configure(text="Error: " + st["error"], fg=RED)
        elif st.get("connected"):
            self.dot.itemconfigure(self.dot_id, fill=GREEN)
            n = st.get("players", 0)
            self.status_label.configure(
                text=(f"Conectado ({n} jugador{'es' if n != 1 else ''})"
                      if n else "Esperando conexión del teléfono"))
            parts = []
            live = [r for r in rows if not r.get("pending")]
            lats = [r["latency"] for r in live if r.get("latency") is not None]
            if lats:
                parts.append(f"Latencia: {min(lats)} ms")
            bat = next((r["battery"] for r in live if r.get("battery") is not None), None)
            if bat is not None:
                parts.append(f"Batería: {bat}%")
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