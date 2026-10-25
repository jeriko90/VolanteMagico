# Volante

**Convierte tu teléfono en un volante para juegos de carreras en el PC.** Inclinas el teléfono para dirigir, usas pedales táctiles para acelerar y frenar, y el PC lo ve como un **mando Xbox 360 real** (funciona en cualquier juego con soporte de gamepad: Forza, Assetto Corsa, F1, Euro Truck, etc.).

> ### Funciona con iPhone **y** Android
> La misma app sirve para los dos: **iPhone / iPad** (Safari) y **Android** (Chrome / Edge). **No hay que instalar ninguna aplicación en el teléfono** — todo es una **página web** (en el dominio fijo). Además, la página **detecta tu dispositivo automáticamente** y adapta las instrucciones; también puedes elegirlo a mano en ⚙ → *Dispositivo*.

## Compatibilidad

| Plataforma | Navegador | Estado | Qué necesitas |
|---|---|---|---|
| **iPhone / iPad** | Safari | Sí | Instalar el perfil del certificado (un toque) |
| **Android** | Chrome / Edge | Sí | Solo aceptar el aviso de certificado |
| **PC** | Windows 10 / 11 | Sí | Ejecutar `Volante.exe` (permisos de admin una vez) |

Ambos teléfonos usan los mismos **sensores de movimiento**; el cálculo de dirección es idéntico en iOS y Android. La única diferencia está en cómo se confía el certificado (ver la sección *Uso rápido* más abajo).

## Cómo funciona

```
Teléfono (navegador) ── sensores + WebSocket ──▶  Volante.exe
   iPhone (Safari) / Android (Chrome)                vgamepad → ViGEmBus
   + pedales / botones táctiles                      → Xbox 360 virtual → juego
        web en el dominio fijo (ya publicada)
```

- **Teléfono:** una **página web** (puede funcionar iPhone y Android, sin instalar ninguna app). Se abre escaneando el **QR** o escribiendo el **código** que muestra la PC.
- **PC:** `Volante.exe` abre una ventana **mínima** con el **QR** y el **código**; crea **un mando Xbox 360 virtual** con `vgamepad` + ViGEmBus y traduce la entrada del teléfono.

## Requisitos

- Windows 10/11.
- Un teléfono **iPhone/iPad (Safari)** o **Android (Chrome/Edge)**.
- La **web** publicada en el dominio fijo `volante.hausetienda.com.ar` (ya en línea); el teléfono la abre escaneando el QR o escribiendo el código.
- **Permisos de administrador una vez** (para instalar el driver ViGEmBus y la regla de firewall).
- Para **compilar** tú mismo: Python 3.11+ y `pip install -r source/requirements.txt`.
- ¿Solo quieres jugar? Descarga `dist/Volante.exe` — no necesitas compilar nada.

## Uso rápido (con el .exe compilado)

1. Ejecuta `Volante.exe` en el PC. La primera vez pedirá UAC para instalar el driver ViGEmBus (una sola vez).
2. Se abre una ventana con un **código** y un **QR** (el QR ya lleva el código dentro). Escanea el QR o escribe el código en la web del teléfono (iPhone o Android, el que tengas). El teléfono debe estar en la **misma red WiFi** que el PC.
3. Confía en el certificado. **Sigue los pasos según tu dispositivo:**

   **iPhone / iPad — Safari** (hay que instalar el perfil porque iOS lo exige):
   - Abre `https://volante.hausetienda.com.ar/ca` en el iPhone.
   - Se descarga un perfil → **Ajustes → General → VPN y dispositivo → Instalar**.
   - **Ajustes → General → Información → Ajustes de confianza de certificados** → activa *Volante Local CA*.

   **Android — Chrome / Edge** (no hace falta instalar nada):
   - Acepta el aviso **"La conexión no es privada"** → *Continuar*.
   - *(Opcional)* puedes instalar el certificado desde `https://volante.hausetienda.com.ar/ca` para que no vuelva a avisar.

4. Vuelve a la página, toca **"Activar sensores"** (en iPhone concede el permiso de movimiento; en Android se activa al instante).
5. Coloca el teléfono en posición neutra y pulsa **Calibrar**. ¡A jugar!

> **Los dos dispositivos funcionan igual** una vez conectados: mismos controles, misma calibración, misma respuesta. La página detecta cuál usas y te muestra los pasos que corresponden.

> El teléfono funciona mejor en horizontal (modo volante). La dirección se ajusta sola a la orientación: ya no hay que invertir el giro al girarlo de lado. Los pedales son las zonas grandes inferiores (izquierda = freno, derecha = acelerador); en modo *Ambos* un toque da el 100% y deslizar el dedo modula la intensidad.
>
> **La app se ve en horizontal aunque la rotación automática del teléfono esté bloqueada.** Detecta la postura real con los sensores y, si el sistema no gira la pantalla, rota toda la interfaz 90° para que siempre la veas en horizontal. Si el teléfono está en vertical, la maquetación cambia a pedales abajo y los controles siguen siendo utilizables; nunca hay que girar nada a mano.

## Un solo código: cómo se empareja el teléfono

Volante usa **un único código** (y un único QR) para **un teléfono**. La PC lo muestra en grande en su ventana; el teléfono lo escribe en la pantalla *Conectar* de la web —o escanea el QR, que ya lo lleva— y quedan sincronizados.

- **La ventana del PC solo tiene esto:** el **QR** (apunta a la IP de la WiFi del PC) y el **código grande** con **Copiar código**. Nada más.
- **El QR abre la web con el código dentro.** Codifica `https://<IP-del-PC>:8443/?c=<código>`: al escanearlo, el teléfono abre la web y **autocompleta** el código (y lo guarda en el navegador, así que al reabrirlo sigue emparejado). Funciona cuando el teléfono y el PC están en la **misma red WiFi** (sin pasar por Internet).
- **El código es privado.** El PC solo acepta **su** código: cualquier otro recibe «Código incorrecto». No se envía al teléfono por la red.
- **Un teléfono = un jugador.** Si el mismo código se vuelve a conectar, **reemplaza** la sesión anterior (nunca hay dos a la vez).

## Cuadro de mandos: velocidad real del juego

La pantalla del teléfono muestra **velocidad (km/h), cambio y barra de RPM** con el estilo de un cuadro de mandos:

- **Forza** (FH4, FH5, Forza Motorsport): en el juego activa **Data Out** con formato **Dash** hacia la IP del PC y **puerto 9999** (ajustable en `config.json` → `telemetryPort`).
- Sin telemetría el marcador queda en `--` y todo lo demás sigue funcionando igual.
- Los controles ahora son **3 botones grandes** (FRENO MANO, CAMBIO +, CAMBIO −) y **2 pequeños** (CÁMARA, BOCINA). El **D-Pad** es opcional: Ajustes → *Mostrar D-Pad* (apagado por defecto).

## La web y el dominio fijo

La web de Volante corre en el **PC** (HTTPS con certificado local). La app de Windows **no necesita configurar nada de red**: solo muestra el **QR** y el **código**.

- El QR codifica `https://<IP-del-PC>:8443/?c=<código>`, así que al escanearlo el teléfono **abre la web con el código ya puesto** (misma red WiFi).
- Si prefieres no escanear, abre la URL del PC en el navegador del teléfono y **escribe el código** que muestra la ventana del PC.
- La app **no levanta ningún túnel** ni pide tokens.

> **Seguridad:** cualquiera en la misma red podría abrir la página, pero **solo entra quien tiene el código** que muestra el PC: cualquier otro código se rechaza (ver *Un solo código* más arriba).

## Compilar el .exe

Necesitas **Python 3.11 o superior** instalado con la opción *"Add python.exe to PATH"*.

Desde la raíz del repositorio (la carpeta que contiene `source/`):

```powershell
powershell -ExecutionPolicy Bypass -File source\build.ps1
```

O simplemente **haz doble clic en `build.cmd`** (hace lo mismo).

El script:

1. **Cierra cualquier `Volante.exe` que esté abierto** (si no, el archivo queda bloqueado y el build falla con *Acceso denegado*).
2. Instala las dependencias (`pip install -r source/requirements.txt`).
3. Compila con PyInstaller y deja:
   - `dist\Volante.exe` → el ejecutable portátil para compartir.
   - `dist\Volante-<version>.exe` → copia con el número de versión (así el auto-update nunca sirve una copia cacheada).
   - `update.json` → manifiesto con la versión, la URL y el hash **SHA-256**.

> Para publicar una versión nueva, sube el número en `source/version.py` **antes** de compilar; el script lo detecta y genera todo con esa versión.

## Ejecutar en desarrollo (sin compilar)

```powershell
python -m pip install -r source\requirements.txt
python source\main.py
```

## Actualizaciones

La ventana del PC es **mínima** (solo QR + código) y **no** incluye botón de actualización. Para pasar a una versión nueva, vuelve a descargar/copiar `dist\Volante.exe` y sustituye el anterior; tus ajustes (`config.json`) y los certificados (`certs/`) **se conservan**.

**Publicar una versión nueva (mantenedor):** sube el número en `source/version.py`, ejecuta `powershell -ExecutionPolicy Bypass -File source\build.ps1` (o `build.cmd`) —esto regenera `dist\Volante.exe`, `dist\Volante-<version>.exe` **y** `update.json` con el hash— y haz *push* de los `.exe` de `dist/` **y** `update.json`.

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
| Mostrar D-Pad | Muestra/oculta la cruz direccional (apagada por defecto) |
| Tu código | El código único de la PC con el que este teléfono está emparejado; **Cambiar** pide escribir otro |

**Mapeo Xbox por defecto:** freno de mano → A · cambio arriba → RB · cambio abajo → LB · cámara → Y · bocina → B · D-Pad para menús. Editable en `config.json`.

## Estructura

```
Volante/
├─ build.cmd                # compilar con doble clic (llama a source\build.ps1)
├─ source/                  # código fuente
│  ├─ main.py               # punto de entrada
│  ├─ gui.py                # ventana Tkinter mínima (solo QR + código)
│  ├─ server.py             # HTTPS + WebSocket + mapeo a vgamepad
│  ├─ certgen.py            # certificado autofirmado + perfil iOS
│  ├─ setup_driver.py       # ViGEmBus + firewall + elevación
│  ├─ config_store.py       # ajustes persistentes
│  ├─ version.py            # número de versión
│  ├─ paths.py              # rutas dev/empaquetado
│  ├─ web/                  # interfaz del teléfono (postura, código, controles)
│  ├─ tunnel.py             # (sin uso) Cloudflare Tunnel, antes gestionado por la GUI
│  ├─ update.py             # (sin uso) auto-actualización, antes gestionada por la GUI
│  ├─ Volante.spec          # empaquetado PyInstaller
│  ├─ build.ps1             # script de build (compila y genera update.json)
│  └─ requirements.txt
├─ update.json              # manifiesto de la última versión (build/publicación)
└─ dist/
   ├─ Volante.exe           # ejecutable listo para usar
   └─ Volante-<version>.exe # copia con el número de versión
```

## Solución de problemas

- **El juego no detecta el mando:** verifica con `joy.cpl` (Win+R → `joy.cpl`). Debe aparecer "Xbox 360 Controller". Si no, reabre el `.exe` y acepta el UAC para reinstalar el driver.
- **No conecta desde el teléfono:** comprueba que la web (`volante.hausetienda.com.ar`) abre y que la app `Volante` está permitida en el Firewall de Windows. En Android activa también los datos/permiso de ubicación del navegador si no detecta la red.
- **El teléfono dice «Código incorrecto»:** el código no coincide con el que muestra la PC. Escanea su QR o escribe el **código grande** de la ventana del PC.
- **El juego no ve un segundo mando:** Volante usa **un solo teléfono = un solo mando**. Desconecta el otro teléfono (o cierra su pestaña); si vuelve el mismo código, reemplaza la sesión.
- **La pantalla se ve en vertical:** pulsa *Activar sensores* (la app gira sola según la postura). Si el navegador no da sensores, fija el **Dispositivo** en ⚙ o comprueba el certificado.
- **No responde a la inclinación (iOS):** hay que (1) confiar el certificado y (2) tocar *Activar sensores* y aceptar el permiso. Revisa Ajustes → Safari → Movimiento y orientación.
- **No responde a la inclinación (Android):** debe ser HTTPS (esta app lo es) y aceptar el aviso de certificado; si no, recurre a la página desde el selector ⚙ → *Dispositivo → Android*.
- **Antivirus marca el .exe:** es habitual con empaquetados onefile; añade una exclusión.
- **Al compilar sale "Acceso denegado" o *file is being used*:** hay un `Volante.exe` abierto que bloquea `dist\Volante.exe`. El script intenta cerrarlo solo; si persiste, ciérralo a mano (incluida una consola/UAC elevada) y reintenta.
- **Al compilar sale "python no se reconoce":** instala Python 3.11+ desde python.org marcando *"Add python.exe to PATH"*, o usa `build.cmd` desde la raíz del repositorio.
- **Latencia alta:** acerca el teléfono al router; usa WiFi 5 GHz.
- **Algo no funciona:** mira `volante.log`, junto al `.exe`, para ver los detalles.

## Licencias de terceros

- **ViGEmBus** (driver, por Nefarius Software Solutions e.U.) — BSD 3-Clause. Se empaqueta y auto-instala; es software de terceros ajeno a este proyecto.
- **vgamepad** — MIT.
- **aiohttp** — Apache 2.0. · **qrcode** — BSD. · **Pillow** — HPND. · **cryptography** — Apache 2.0/BSD.
