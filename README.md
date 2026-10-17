# Volante

**Convierte tu teléfono en un volante para juegos de carreras en el PC.** Inclinas el teléfono para dirigir, usas pedales táctiles para acelerar y frenar, y el PC lo ve como un **mando Xbox 360 real** (funciona en cualquier juego con soporte de gamepad: Forza, Assetto Corsa, F1, Euro Truck, etc.).

> ### Funciona con iPhone **y** Android
> La misma app sirve para los dos: **iPhone / iPad** (Safari) y **Android** (Chrome / Edge). **No hay que instalar ninguna aplicación en el teléfono** — todo es una página web que sirve el propio PC. Además, la página **detecta tu dispositivo automáticamente** y adapta las instrucciones; también puedes elegirlo a mano en ⚙ → *Dispositivo*.

## Compatibilidad

| Plataforma | Navegador | Estado | Qué necesitas |
|---|---|---|---|
| **iPhone / iPad** | Safari | Sí | Instalar el perfil del certificado (un toque) |
| **Android** | Chrome / Edge | Sí | Solo aceptar el aviso de certificado |
| **PC** | Windows 10 / 11 | Sí | Ejecutar `Volante.exe` (permisos de admin una vez) |

Ambos teléfonos usan los mismos **sensores de movimiento**; el cálculo de dirección es idéntico en iOS y Android. La única diferencia está en cómo se confía el certificado (ver la sección *Uso rápido* más abajo).

## Cómo funciona

```
Teléfono (navegador) ── sensores + WebSocket (WiFi) ──▶  Volante.exe
   iPhone (Safari) / Android (Chrome)                      vgamepad → ViGEmBus
   + pedales / botones táctiles                            → Xbox 360 virtual → juego
```

- **Teléfono:** página web (`source/web/`) servida por el PC. Sin instalar ninguna app (vale iPhone y Android).
- **PC:** `Volante.exe` crea un mando Xbox 360 virtual con `vgamepad` + ViGEmBus y traduce la entrada del teléfono.

## Requisitos

- Windows 10/11.
- Un teléfono **iPhone/iPad (Safari)** o **Android (Chrome/Edge)**.
- El PC y el teléfono en la **misma red WiFi**.
- **Permisos de administrador una vez** (para instalar el driver ViGEmBus y la regla de firewall).
- Para **compilar** tú mismo: Python 3.11+ y `pip install -r source/requirements.txt`.
- ¿Solo quieres jugar? Descarga `dist/Volante.exe` — no necesitas compilar nada.

## Uso rápido (con el .exe compilado)

1. Ejecuta `Volante.exe` en el PC. La primera vez pedirá UAC para instalar el driver ViGEmBus (una sola vez).
2. Se abre una ventana con una **URL** y un **QR**. Escanéalo o abre la URL en el navegador del teléfono (iPhone o Android, el que tengas).
3. Confía en el certificado. **Sigue los pasos según tu dispositivo:**

   **iPhone / iPad — Safari** (hay que instalar el perfil porque iOS lo exige):
   - Toca **"Abrir el certificado (/ca)"** en la ventana del PC (o abre `https://IP:8443/ca` en el iPhone).
   - Se descarga un perfil → **Ajustes → General → VPN y dispositivo → Instalar**.
   - **Ajustes → General → Información → Ajustes de confianza de certificados** → activa *Volante Local CA*.

   **Android — Chrome / Edge** (no hace falta instalar nada):
   - Acepta el aviso **"La conexión no es privada"** → *Continuar*.
   - *(Opcional)* puedes instalar el certificado desde `/ca` para que no vuelva a avisar.

4. Vuelve a la página, toca **"Activar sensores"** (en iPhone concede el permiso de movimiento; en Android se activa al instante).
5. Coloca el teléfono en posición neutra y pulsa **Calibrar**. ¡A jugar!

> **Los dos dispositivos funcionan igual** una vez conectados: mismos controles, misma calibración, misma respuesta. La página detecta cuál usas y te muestra los pasos que corresponden.

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

## Actualizaciones

El `.exe` **se actualiza solo**: en la ventana del PC hay un botón **"Chequear actualizaciones"** (y también comprueba al abrir). Si hay una versión nueva, te pregunta y, al aceptar, **descarga la última versión, la instala y reinicia** la app. No hace falta volver a bajar nada del repositorio ni recompilar.

- Se comprueba contra el archivo `update.json` del repositorio (la versión, la URL del `.exe` y su hash **SHA-256**).
- Antes de aplicar la descarga se **verifica el hash**, así que no se instala un archivo corrupto.
- Tus ajustes (`config.json`) y los certificados (`certs/`) **se conservan**.
- Si la carpeta del `.exe` no se puede escribir (p. ej. `Program Files` sin permisos), en vez de fallar guarda la nueva versión en **Descargas** y te indica cómo reemplazarla.

**Publicar una versión nueva (mantenedor):** sube el número en `source/version.py`, ejecuta `powershell -ExecutionPolicy Bypass -File source\build.ps1` (esto regenera `dist\Volante.exe` **y** `update.json` con el hash) y haz *push* de `dist/Volante.exe` + `update.json`.

## Controles y ajustes

Desde el engranaje ⚙ en el teléfono (se guardan en `config.json`):

| Ajuste | Descripción |
|---|---|
| Dispositivo | Automático (detecta iOS/Android y adapta las instrucciones) o forzarlo a mano |
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
│  ├─ gui.py                # ventana Tkinter (URL, QR, estado, actualizaciones)
│  ├─ server.py             # HTTPS + WebSocket + mapeo a vgamepad
│  ├─ certgen.py            # certificado autofirmado + perfil iOS
│  ├─ setup_driver.py       # ViGEmBus + firewall + elevación
│  ├─ config_store.py       # ajustes persistentes
│  ├─ update.py             # auto-actualización (descarga + reinicio)
│  ├─ version.py            # número de versión
│  ├─ paths.py              # rutas dev/empaquetado
│  ├─ web/                  # interfaz del teléfono
│  ├─ Volante.spec          # empaquetado PyInstaller
│  ├─ build.ps1             # script de build (compila y genera update.json)
│  └─ requirements.txt
├─ update.json              # manifiesto de la última versión (para el auto-update)
└─ dist/
   └─ Volante.exe           # ejecutable listo para usar
```

## Solución de problemas

- **El juego no detecta el mando:** verifica con `joy.cpl` (Win+R → `joy.cpl`). Debe aparecer "Xbox 360 Controller". Si no, reinstala el driver (botón *Reiniciar mando* no basta; reabre el .exe y acepta el UAC).
- **No conecta desde el teléfono:** mismo WiFi; comprueba la IP de la ventana; permite `Volante` en el Firewall de Windows. En Android activa también los datos/permiso de ubicación del navegador si no detecta la red.
- **No responde a la inclinación (iOS):** hay que (1) confiar el certificado y (2) tocar *Activar sensores* y aceptar el permiso. Revisa Ajustes → Safari → Movimiento y orientación.
- **No responde a la inclinación (Android):** debe ser HTTPS (esta app lo es) y aceptar el aviso de certificado; si no, recurre a la página desde el selector ⚙ → *Dispositivo → Android*.
- **Antivirus marca el .exe:** es habitual con empaquetados onefile; añade una exclusión.
- **Latencia alta:** acerca el teléfono al router; usa WiFi 5 GHz.
- **Algo no funciona:** pulsa *Abrir logs* en la ventana (o mira `volante.log`, junto al .exe) para ver los detalles.

## Licencias de terceros

- **ViGEmBus** (driver, por Nefarius Software Solutions e.U.) — BSD 3-Clause. Se empaqueta y auto-instala; es software de terceros ajeno a este proyecto.
- **vgamepad** — MIT.
- **aiohttp** — Apache 2.0. · **qrcode** — BSD. · **Pillow** — HPND. · **cryptography** — Apache 2.0/BSD.
