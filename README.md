# Volante

Convierte tu **iPhone en un volante** para juegos de carreras en el PC. Inclinas el teléfono para dirigir, usas pedales táctiles para acelerar y frenar, y el PC lo ve como un **mando Xbox 360 real** (funciona en cualquier juego con soporte de gamepad: Forza, Assetto Corsa, F1, Euro Truck, etc.).

## Cómo funciona

```
iPhone (Safari)  ── dispositivo + WebSocket (WiFi) ──▶  Volante.exe
   sensores de movimiento                                 vgamepad → ViGEmBus
   + pedales / botones táctiles                           → Xbox 360 virtual → juego
```

- **iPhone:** página web (`web/`) servida por el PC. Sin instalar nada.
- **PC:** `Volante.exe` crea un mando Xbox 360 virtual con `vgamepad` + ViGEmBus y traduce la entrada del teléfono.

## Requisitos

- Windows 10/11.
- El PC y el iPhone en la **misma red WiFi**.
- **Permisos de administrador una vez** (para instalar el driver ViGEmBus y la regla de firewall).
- Para **compilar** tú mismo: Python 3.11+ y `pip install -r source/requirements.txt`.
- ¿Solo quieres jugar? Descarga `dist/Volante.exe` — no necesitas compilar nada.

## Uso rápido (con el .exe compilado)

1. Ejecuta `Volante.exe`. La primera vez pedirá UAC para instalar el driver ViGEmBus (una sola vez).
2. Se abre una ventana con una **URL** y un **QR**. Ábrela en **Safari** del iPhone.
3. La primera vez, Safari avisará del certificado: acepta y entra.
4. Instala el certificado para que iOS permita los sensores:
   - Toca **"Abrir el certificado (/ca)"** (o abre `https://IP:8443/ca` en el iPhone).
   - Se descarga un perfil → **Ajustes → General → VPN y dispositivo → Instalar**.
   - **Ajustes → General → Información → Ajustes de confianza de certificados** → activa *Volante Local CA*.
5. Vuelve a la página, toca **"Activar sensores"** y concede el permiso de movimiento.
6. Coloca el iPhone en posición neutra y pulsa **Calibrar**. ¡A jugar!

> El teléfono funciona mejor en horizontal (modo volante). La dirección se ajusta sola a la orientación: ya no hay que invertir el giro al girarlo de lado. Los pedales son las zonas grandes inferiores (izquierda = freno, derecha = acelerador); en modo *Ambos* un toque da el 100% y deslizar el dedo modula la intensidad.

## Compilar el .exe

```powershell
powershell -ExecutionPolicy Bypass -File source\build.ps1
```

El resultado queda en `dist\Volante.exe` (un único archivo portátil).

## Ejecutar en desarrollo (sin compilar)

```powershell
python -m pip install -r source\requirements.txt
python source\main.py
```

## Controles y ajustes

Desde el engranaje ⚙ en el teléfono (se guardan en `config.json`):

| Ajuste | Descripción |
|---|---|
| Ángulo máx. | Grados de inclinación = dirección a tope |
| Zona muerta | Margen central sin respuesta |
| Curva/Expo | Sensibilidad progresiva |
| Suavizado | Filtro de la dirección |
| Eje de dirección | Auto (se adapta a vertical/horizontal) o forzar gamma/beta |
| Modo de pedales | Ambos / Todo o nada / Gradual |
| Invertir dirección | Cambia el sentido del giro |
| Gas/freno por inclinación | Usa el pitch en vez de (o además de) los pedales |

**Mapeo Xbox por defecto:** freno de mano → A · cambio arriba → RB · cambio abajo → LB · cámara → Y · bocina → B · D-Pad para menús. Editable en `config.json`.

## Estructura

```
Volante/
├─ source/                  # código fuente
│  ├─ main.py               # punto de entrada
│  ├─ gui.py                # ventana Tkinter (URL, QR, estado)
│  ├─ server.py             # HTTPS + WebSocket + mapeo a vgamepad
│  ├─ certgen.py            # certificado autofirmado + perfil iOS
│  ├─ setup_driver.py       # ViGEmBus + firewall + elevación
│  ├─ config_store.py       # ajustes persistentes
│  ├─ paths.py              # rutas dev/empaquetado
│  ├─ web/                  # interfaz del teléfono
│  ├─ Volante.spec          # empaquetado PyInstaller
│  ├─ build.ps1             # script de build
│  └─ requirements.txt
└─ dist/
   └─ Volante.exe           # ejecutable listo para usar
```

## Solución de problemas

- **El juego no detecta el mando:** verifica con `joy.cpl` (Win+R → `joy.cpl`). Debe aparecer "Xbox 360 Controller". Si no, reinstala el driver (botón *Reiniciar mando* no basta; reabre el .exe y acepta el UAC).
- **No conecta desde el iPhone:** mismo WiFi; comprueba la IP de la ventana; permite `Volante` en el Firewall de Windows.
- **No responde a la inclinación:** en iOS hay que (1) confiar el certificado y (2) tocar *Activar sensores* y aceptar el permiso. Revisa Ajustes → Safari → Movimiento y orientación.
- **Antivirus marca el .exe:** es habitual con empaquetados onefile; añade una exclusión.
- **Latencia alta:** acerca el iPhone al router; usa WiFi 5 GHz.
- **Algo no funciona:** pulsa *Abrir logs* en la ventana (o mira `volante.log`, junto al .exe) para ver los detalles.

## Licencias de terceros

- **ViGEmBus** (driver, por Nefarius Software Solutions e.U.) — BSD 3-Clause. Se empaqueta y auto-instala; es software de terceros ajeno a este proyecto.
- **vgamepad** — MIT.
- **aiohttp** — Apache 2.0. · **qrcode** — BSD. · **Pillow** — HPND. · **cryptography** — Apache 2.0/BSD.
