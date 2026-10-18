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
Teléfono (navegador) ── sensores + WebSocket ──▶  Volante.exe
   iPhone (Safari) / Android (Chrome)                vgamepad → ViGEmBus
   + pedales / botones táctiles                      → Xbox 360 virtual(s) → juego
        WiFi (misma red)  o  por dominio (Cloudflare Tunnel)
```

- **Teléfono:** página web (`source/web/`) servida por el PC. Sin instalar ninguna app (vale iPhone y Android). Cada teléfono usa su **código/QR**.
- **PC:** `Volante.exe` crea **un mando Xbox 360 virtual por jugador** con `vgamepad` + ViGEmBus (hasta 4) y traduce la entrada de cada teléfono.

## Requisitos

- Windows 10/11.
- Un teléfono **iPhone/iPad (Safari)** o **Android (Chrome/Edge)**.
- El PC y el teléfono en la **misma red WiFi** — o desde **cualquier lugar** si activas un dominio público (ver *Acceder con un dominio público* más abajo).
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
>
> **La app se ve en horizontal aunque la rotación automática del teléfono esté bloqueada.** Detecta la postura real con los sensores y, si el sistema no gira la pantalla, rota toda la interfaz 90° para que siempre la veas en horizontal. Si el teléfono está en vertical, la maquetación cambia a pedales abajo y los controles siguen siendo utilizables; nunca hay que girar nada a mano.

## Varios teléfonos: código por dispositivo, QR por cliente y multijugador

Cada teléfono tiene su **propio código** y su **propio mando Xbox 360 virtual**. Hay **máximo 4 jugadores** a la vez (tope del driver ViGEmBus), todos entrando por la misma URL (local o dominio).

- **Cómo se asocia el dispositivo.** El QR de cada jugador lleva un código en la URL (`?c=XXXXXX`): al escanearlo el teléfono se asocia a ese código y lo guarda en el navegador, así que al reabrirlo sigue siendo el mismo jugador. También puedes **escribir el código a mano** (pantalla *Conectar*, o ⚙ → *Cambiar*), por si pierdes el QR o abres el dominio a pelo.
- **Solo códigos invitados** (activado por defecto). El PC rechaza a cualquier teléfono cuyo código no esté reservado; en el teléfono aparece «Código no autorizado» y pide escribir otro. Desactiva la casilla **Solo códigos invitados** en la ventana del PC si prefieres que cualquiera con la URL pueda entrar.
- **En la ventana del PC**, la sección **Clientes** lista los jugadores (**Jugador N**, código, dispositivo, latencia, batería):
  - **QR** → el QR y la URL personal de ese jugador.
  - **Quitar** → expulsa a ese jugador (su mando se libera).
  - **Nuevo QR de cliente** → reserva un código con su QR/URL para enviárselo a esa persona de antemano (WhatsApp, etc.); aparece como *esperando su QR* hasta que alguien lo abra.
- El campo **URL pública** guarda tu dominio (p. ej. `https://volante.hausetienda.com.ar`) y los botones **Local (IP)** / **Público (dominio)** eligen qué QR se muestra en la ventana.

> **Multijugador:** al conectar un código válido, ese teléfono manda su propio mando. Si el juego admite varios gamepads (cada jugador en su coche), funciona directamente. **Nadie «activa» a nadie**: todo código invitado ya es un mando activo.

## Cuadro de mandos: velocidad real del juego

La pantalla del teléfono muestra **velocidad (km/h), cambio y barra de RPM** con el estilo de un cuadro de mandos:

- **Forza** (FH4, FH5, Forza Motorsport): en el juego activa **Data Out** con formato **Dash** hacia la IP del PC y **puerto 9999** (ajustable en `config.json` → `telemetryPort`).
- Sin telemetría el marcador queda en `--` y todo lo demás sigue funcionando igual.
- Los controles ahora son **3 botones grandes** (FRENO MANO, CAMBIO +, CAMBIO −) y **2 pequeños** (CÁMARA, BOCINA). El **D-Pad** es opcional: Ajustes → *Mostrar D-Pad* (apagado por defecto).

## Acceder con un dominio público (p. ej. `volante.hausetienda.com.ar`)

⚠️ Un registro DNS de Cloudflare con la **nube naranja** (proxy activo) **no puede apuntar a una IP privada** como `192.168.100.5`: Cloudflare no alcanza esa IP y los visitantes ven el error **1002**. La solución es un **Cloudflare Tunnel** y **Volante lo levanta solo, cada vez que se abre**:

1. En el dashboard de Cloudflare: **Networking → Tunnels → Create a tunnel** (tipo *cloudflared*), nombre `volante`.
2. **Routes → Add route** (Public Hostname): hostname `volante.hausetienda.com.ar` → servicio `https://localhost:8443`, y activa **TLS → Disable TLS certificate verification** (el certificado del PC es autofirmado).
3. Copia el **token** (el valor `eyJ…`) del comando de instalación que muestra el dashboard.
4. En la ventana de Volante: botón **Internet…** → pega el **token** y el **dominio** (`volante.hausetienda.com.ar`) → **Conectar y guardar**. Al hacerlo el programa guarda el dominio como URL pública y pasa a usarlo solo (el QR y cada **QR de cliente** salen con el dominio). Si falta `cloudflared.exe`, el propio diálogo lo descarga a la carpeta del `.exe` con **Descargar cloudflared**.
5. Borra el registro A naranja con IP privada (el túnel crea su CNAME).

Con eso, al abrir la app se conecta a internet y todos los clientes abren `https://volante.hausetienda.com.ar/?c=XXXXXX` con **certificado válido de Cloudflare**, sin avisos y sin instalar el perfil del certificado en el iPhone. El WebSocket atraviesa el túnel sin configurar nada más.

> Si el campo **dominio** está vacío, la ventana usa la IP local y puedes rellenarlo después en **URL pública** de la ventana principal.

> **Latencia:** por el dominio el tráfico va teléfono → Cloudflare → PC, con lo que se añade ida y vuelta por Internet. Para jugar en la misma red WiFi usa igualmente la URL local de la ventana del PC; el dominio es ideal para clientes remotos, demostraciones o probar desde fuera.

> **Seguridad:** con el dominio público cualquiera que lo conozca podría abrir la URL, por eso por defecto solo entran los **códigos invitados** (ver *Varios teléfonos* más arriba).

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

El `.exe` **se actualiza solo**: en la ventana del PC hay un botón **"Chequear actualizaciones"** (y también comprueba al abrir). Si hay una versión nueva, te pregunta y, al aceptar, **descarga la última versión, la instala y reinicia** la app. No hace falta volver a bajar nada del repositorio ni recompilar.

- Se comprueba contra el archivo `update.json` del repositorio (la versión, la URL del `.exe` y su hash **SHA-256**).
- Antes de aplicar la descarga se **verifica el hash**, así que no se instala un archivo corrupto.
- Tus ajustes (`config.json`) y los certificados (`certs/`) **se conservan**.
- Si la carpeta del `.exe` no se puede escribir (p. ej. `Program Files` sin permisos), en vez de fallar guarda la nueva versión en **Descargas** y te indica cómo reemplazarla.

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
| Tu código | El código con el que este teléfono está asociado al PC; **Cambiar** pide escribir otro |

**Mapeo Xbox por defecto:** freno de mano → A · cambio arriba → RB · cambio abajo → LB · cámara → Y · bocina → B · D-Pad para menús. Editable en `config.json`.

## Estructura

```
Volante/
├─ build.cmd                # compilar con doble clic (llama a source\build.ps1)
├─ source/                  # código fuente
│  ├─ main.py               # punto de entrada
│  ├─ gui.py                # ventana Tkinter (URL, QR, estado, actualizaciones)
│  ├─ server.py             # HTTPS + WebSocket + mapeo a vgamepad
│  ├─ certgen.py            # certificado autofirmado + perfil iOS
│  ├─ setup_driver.py       # ViGEmBus + firewall + elevación
│  ├─ config_store.py       # ajustes persistentes
│  ├─ tunnel.py             # Cloudflare Tunnel (acceso por dominio público)
│  ├─ update.py             # auto-actualización (descarga + reinicio)
│  ├─ version.py            # número de versión
│  ├─ paths.py              # rutas dev/empaquetado
│  ├─ web/                  # interfaz del teléfono (postura, código, controles)
│  ├─ Volante.spec          # empaquetado PyInstaller
│  ├─ build.ps1             # script de build (compila y genera update.json)
│  └─ requirements.txt
├─ update.json              # manifiesto de la última versión (para el auto-update)
└─ dist/
   ├─ Volante.exe           # ejecutable listo para usar
   └─ Volante-<version>.exe # copia con la versión (URL única para el auto-update)
```

## Solución de problemas

- **El juego no detecta el mando:** verifica con `joy.cpl` (Win+R → `joy.cpl`). Debe aparecer "Xbox 360 Controller". Si no, reinstala el driver (botón *Reiniciar mando* no basta; reabre el .exe y acepta el UAC).
- **No conecta desde el teléfono:** mismo WiFi; comprueba la IP de la ventana; permite `Volante` en el Firewall de Windows. En Android activa también los datos/permiso de ubicación del navegador si no detecta la red.
- **El teléfono dice «Código no autorizado»:** ese código no está reservado en el PC. Pulsa **Nuevo QR de cliente** y escanea el QR nuevo (o escribe el código que muestra el PC). Si desactivas **Solo códigos invitados** puede entrar cualquiera, pero no se recomienda con el dominio público.
- **El teléfono dice «No hay mandos libres»:** ya hay 4 jugadores conectados; **Quitar** a uno desde la ventana del PC para librar su mando.
- **La pantalla se ve en vertical:** pulsa *Activar sensores* (la app gira sola según la postura). Si el navegador no da sensores, fija el **Dispositivo** en ⚙ o comprueba el certificado.
- **No responde a la inclinación (iOS):** hay que (1) confiar el certificado y (2) tocar *Activar sensores* y aceptar el permiso. Revisa Ajustes → Safari → Movimiento y orientación.
- **No responde a la inclinación (Android):** debe ser HTTPS (esta app lo es) y aceptar el aviso de certificado; si no, recurre a la página desde el selector ⚙ → *Dispositivo → Android*.
- **Antivirus marca el .exe:** es habitual con empaquetados onefile; añade una exclusión.
- **Al compilar sale "Acceso denegado" o *file is being used*:** hay un `Volante.exe` abierto que bloquea `dist\Volante.exe`. El script intenta cerrarlo solo; si persiste, ciérralo a mano (incluida una consola/UAC elevada) y reintenta.
- **Al compilar sale "python no se reconoce":** instala Python 3.11+ desde python.org marcando *"Add python.exe to PATH"*, o usa `build.cmd` desde la raíz del repositorio.
- **Latencia alta:** acerca el teléfono al router; usa WiFi 5 GHz.
- **Algo no funciona:** pulsa *Abrir logs* en la ventana (o mira `volante.log`, junto al .exe) para ver los detalles.

## Licencias de terceros

- **ViGEmBus** (driver, por Nefarius Software Solutions e.U.) — BSD 3-Clause. Se empaqueta y auto-instala; es software de terceros ajeno a este proyecto.
- **vgamepad** — MIT.
- **aiohttp** — Apache 2.0. · **qrcode** — BSD. · **Pillow** — HPND. · **cryptography** — Apache 2.0/BSD.
