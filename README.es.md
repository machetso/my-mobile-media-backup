# My Mobile Media Backup

**Versión 0.9.9.0**

Copia las fotos y los vídeos de tu teléfono Android en una o varias unidades externas, comprobados
archivo por archivo, ordenados por año y mes, con un informe después de cada copia. Para Windows y
Linux.

## Funciones principales

* **Un clic**: el teléfono y el equipo muestran cuántas fotos y vídeos están todavía sin copiar (y
  cuánto ocupan); un toque en el teléfono o un clic en el equipo actualiza la copia.
* **Solo se copian las fotos y los vídeos nuevos**: la segunda copia tarda minutos, no horas.
* **Se comprueba cada archivo.** El teléfono calcula una huella (SHA-256) de cada archivo y el
  programa la compara con lo que ha llegado y otra vez con lo que se ha escrito en la unidad.
* **Varias unidades a la vez**: el teléfono se lee solo una vez.
* **Ordenadas automáticamente** en carpetas de año y mes (`2026/26.11`), las fotos RAW aparte.
* **Nunca se borra nada**: ni en el teléfono ni en la copia.
* **Siempre la conexión más rápida**: cable USB, Wi-Fi o el propio Wi-Fi del equipo; el programa
  elige por sí solo.
* **Nunca el teléfono equivocado**: cada copia conoce su teléfono; otro teléfono se rechaza.
* **Copias automáticas**: cuando un teléfono conocido vuelve a casa, el programa puede copiarlo por
  sí solo.
* **Segunda copia** en otra unidad o en Google Drive, conservando los estados anteriores
  (Abuelo-Padre-Hijo), y **restauración** con un clic.
* **Teléfonos y discos antiguos** se pueden añadir a una copia o tener una copia propia.
* Un informe (texto, página web y tabla) después de cada copia.
* En alemán, inglés, francés, español, rumano, hebreo y klingon.

## Cómo funciona, en resumen

El programa copia las fotos y los vídeos de tu teléfono en una unidad externa (por ejemplo, un disco
duro USB). Cada teléfono tiene su propia carpeta en la unidad: *Propietario / Teléfono*, por ejemplo
*Karen / Pixel 10 Pro*. Dentro, las fotos y los vídeos se ordenan en una carpeta por mes.

El programa recuerda lo que ya está en la unidad. Cada copia posterior solo añade lo nuevo: por eso
basta con pulsar **Actualizar copia** una vez a la semana.

### Tu primera copia

1. **Descarga** el programa desde la [página de versiones (Releases)](https://github.com/machetso/my-mobile-media-backup/releases)
   e inícialo: no hay que instalar nada. Windows: el archivo `.exe`. Linux: el archivo `.tar.gz`.
2. **Conecta la unidad externa.**
3. **Conecta el teléfono con su cable USB** y desbloquéalo. Si el teléfono pregunta para qué es la
   conexión USB, elige **Transferencia de archivos**. La barra de color de arriba muestra si el
   teléfono está conectado.
4. Haz clic en **Nueva copia…**, escribe tu nombre como **propietario** (el nombre del teléfono se
   rellena solo), revisa las **carpetas del teléfono** (la carpeta de la cámara ya está) y marca la
   **unidad de copia**.
5. Haz clic en **Iniciar copia**. La barra de abajo muestra cuánto falta y cuánto tarda.
6. Cuando termine, **Abrir informe** muestra lo que se ha copiado y **Abrir carpeta de copia** abre
   las fotos en la unidad.

### Cada copia siguiente

Conecta la unidad. En la pantalla de inicio, tu teléfono tiene su propio botón **Actualizar copia**:
haz clic en él. Solo se copian las fotos y los vídeos nuevos. Con la app del teléfono (ver
*Consejos*) ni siquiera hace falta conectar el teléfono: cuando está en el mismo Wi-Fi, su línea
dice por ejemplo *Cerca – 23 fotos y 4 vídeos (1,5 GB) todavía sin copiar*, y basta con un clic. O
toca **Copiar ahora** en el teléfono.

### Consejos

* **Más rápido:** activa una vez la *depuración por USB* en el teléfono (el programa te enseña cómo,
  paso a paso, para tu modelo de teléfono). Así la copia es de dos a cuatro veces más rápida.
* **Sin cable:** instala la app del teléfono *My Mobile Media Backup* (*Conectar teléfono…* en la
  pantalla de inicio muestra un código QR). Así la copia funciona por Wi-Fi, y el teléfono y el
  equipo se encuentran por sí solos.
* **Dos unidades** son más seguras que una: marca las dos y se escriben a la vez.

## Manual detallado

### La ventana

* **Pantalla de inicio:** el estado de la conexión (rojo = ningún teléfono conectado, amarillo = hay
  algo que hacer en el teléfono, verde = conectado), **Conectar teléfono…** y **Conexiones
  posibles**. Un teléfono conocido en el mismo Wi-Fi aparece como *cerca*, con **Copiar ahora**.
  **Nueva copia…** inicia una copia de otro teléfono, o con otras carpetas o unidades. Debajo, **Tus
  teléfonos**: una entrada por copia con la fecha de la última copia, cuántas fotos y vídeos están
  todavía sin copiar (cuando el teléfono está cerca o conectado) y su propio botón **Actualizar
  copia**. El botón está gris mientras un clic no pueda iniciar la copia; entonces un clic te dice
  qué falta.
* **Barra lateral:** Copia, Gestionar copias, el engranaje (ajustes del programa), Manual y Acerca
  de. El globo de arriba a la derecha cambia el idioma.
* **Abajo:** progreso, velocidad y tiempo restante, con **Cancelar** (se detiene después del archivo
  actual), **Abrir informe** y **Abrir carpeta de copia**. Cada tarea escribe también un archivo de
  registro.

### Conectar el teléfono

El programa usa siempre la **conexión más rápida que encuentra**. Si el teléfono aparece en el cable
USB durante una copia por Wi-Fi, la copia continúa por el cable. **Conexiones posibles** muestra
todas las formas de llegar al teléfono con su velocidad; **Buscar la conexión más rápida** comprueba
el cable, el Wi-Fi y el Bluetooth.

| Conexión | Velocidad |
|---|---|
| Cable USB + depuración por USB (activada por la app del teléfono o a mano) | 45–50 MB/s (USB 3), unos 20–30 MB/s (USB 2) |
| Cable USB, transferencia de archivos normal (MTP) | 10–20 MB/s |
| Wi-Fi: app del teléfono o Depuración inalámbrica | 10–40 MB/s, según el Wi-Fi |
| Wi-Fi directo a este equipo (sin router) | 10–30 MB/s |

**Depuración por USB (ADB).** ADB (Android Debug Bridge) es la herramienta USB de Google para
Android. Es la forma más rápida y segura: el propio teléfono calcula la huella de cada archivo.
Android exige activarla una vez a mano; ningún programa puede hacerlo antes:

1. En el teléfono: *Ajustes → Acerca del teléfono* → toca 7 veces *Número de compilación*
   (opciones para desarrolladores activadas).
2. *Ajustes → Sistema → Opciones para desarrolladores* → activa **Depuración por USB**.
3. Conecta el teléfono, desbloquéalo y confirma *Permitir depuración por USB* con **Permitir siempre
   desde este ordenador**.

*Activar la depuración por USB (primera vez)…* es una guía paso a paso. Reconoce el teléfono en el
cable y tiene los pasos para Pixel, Samsung, Xiaomi / Redmi / POCO, OnePlus / OPPO / realme,
Motorola, Huawei / Honor, Sony y Nothing; para otros teléfonos, *Buscar en la web para este
teléfono*.

El programa ADB en sí es de Google y no se puede incluir con este programa.
*Ajustes del programa → Descargar ADB…* lo descarga directamente de Google en la carpeta del propio
programa: un clic, sin instalación, sin derechos de administrador. En Linux también sirve el paquete
`adb` del sistema.

Si ADB no funciona, el programa lo dice claramente y usa en su lugar la **transferencia de
archivos** normal del teléfono (MTP). En Linux el teléfono se abre automáticamente; elige
*Transferencia de archivos* en la notificación USB del teléfono. MTP es más lento y el teléfono no
puede calcular huellas; el informe lo indica.

**La app del teléfono *My Mobile Media Backup*.** Con la app, las copias funcionan por Wi-Fi sin
depuración por USB, la app activa y desactiva por ti la conexión más rápida, y el teléfono y el
equipo muestran lo que está todavía sin copiar.

* **Instalar:** *Conectar teléfono…* muestra dos códigos QR: uno conecta la app y el otro la
  descarga de la página de versiones. Por el cable USB, el programa puede instalar la app él mismo;
  siempre **pregunta antes** y dice qué teléfono, qué versión y por qué.
* **Copia:** muestra cuántas fotos y vídeos están todavía sin copiar y cuánto ocupan, por ejemplo
  *23 fotos y 4 vídeos (1,5 GB) todavía sin copiar*. **Copiar ahora** inicia la copia: el teléfono
  se conecta y el equipo actualiza la copia por sí solo. Cuando falta algo (el programa del equipo
  no está abierto, la unidad de copia no está conectada, …) el botón está gris y un toque te dice
  qué hacer.
* **Permitir copia:** un solo interruptor. Activado = la conexión más rápida: la depuración por USB
  y la Depuración inalámbrica, donde la app puede activarlas, y el acceso de solo lectura de la
  propia app por el Wi-Fi. Al lado: *Conexión establecida* o *No conectado*; debajo, cuánto tiempo
  sigue activado. **Desconectar** lo desactiva todo. Después de cada copia, el equipo vuelve a
  desactivar la depuración (*Desactivar … después de la copia*, activado por defecto). Las opciones
  para desarrolladores siguen activadas.
* **Cuando tu equipo quiera una copia:**
  * **Preguntarme** (por defecto): el teléfono pregunta *¿Permitir copia?*; nada empieza sin tu
    toque.
  * **Permitir sin preguntar**: un clic en el equipo inicia la copia, sin tocar el teléfono. Con
    **Iniciar también automáticamente**, las fotos y los vídeos más recientes se copian cuando el
    equipo encuentra el teléfono en el Wi-Fi o cuando conectas el cable (como mucho una vez por
    hora).
  * **Nunca**: el equipo no puede preguntar y no encuentra el teléfono cerca.
* **VPN en el teléfono:** una VPN que envía todo por el túnel impide que el equipo llegue a la app
  por el Wi-Fi. La app muestra un aviso: excluye *My Mobile Media Backup* de la VPN, o usa el cable.
* **Misma versión:** la app del teléfono tiene el mismo número de versión que el programa. Cuando es
  más antigua, la pantalla de inicio y *Gestionar copias → Resumen* muestran **Actualizar la app del
  teléfono**. Las copias antiguas de la app se quitan automáticamente.
* La app solo puede leer fotos y vídeos. El equipo pide cada archivo; el teléfono solo responde al
  equipo emparejado y nunca envía nada por sí solo.

**Cuándo se vuelve a desactivar la depuración** (la app del teléfono lo hace aunque el equipo ya no
esté):

1. Las copias por Wi-Fi normalmente pasan por la app del teléfono con la depuración desactivada; la
   Depuración inalámbrica solo se usa para teléfonos sin la app.
2. Una conexión por copia: por el cable, la Depuración inalámbrica se desactiva al principio; a
   través de la app por Wi-Fi, la depuración por USB se desactiva al principio.
3. Mientras el cable USB está conectado, la depuración sigue activada; 5 minutos después de
   desconectarlo se desactiva (cuenta atrás en el teléfono).
4. Cable nunca conectado: se desactiva 5 minutos después de *Permitir copia* si no ha empezado
   ninguna copia.
5. Durante una copia por Wi-Fi, el equipo dice "sigo aquí" cada 30 segundos; nada durante 2 minutos
   → desactivada.
6. Justo después de la copia, el equipo la desactiva.

**Wi-Fi sin la app (Depuración inalámbrica, Android 11 y posteriores).** Todo funciona como por el
cable, incluidas las huellas en el teléfono, solo que más lento.

1. Teléfono: *Ajustes → Sistema → Opciones para desarrolladores → Depuración inalámbrica* → activar.
2. Programa: **Emparejar por Wi-Fi…** → en el teléfono, *Vincular dispositivo con código QR* y
   escanea el código (o *Vincular dispositivo con código de vinculación* y escribe los 6 dígitos).
   Solo hace falta una vez.
3. A partir de ahí, el teléfono se encuentra siempre que la Depuración inalámbrica esté activada y
   los dos estén en el mismo Wi-Fi.

**¿Sin router? Wi-Fi directo.** **Wi-Fi directo…** hace que el equipo abra su propia red Wi-Fi
(Linux: a 5 GHz si es posible; Windows: su *Zona con cobertura inalámbrica móvil*). El teléfono se
une con un código QR. En Linux, la mayoría de los equipos dejan mientras tanto el Wi-Fi normal;
vuelve cuando se detiene el Wi-Fi directo. En Windows, el Wi-Fi normal se mantiene.

**Cómo se reconoce el teléfono de forma segura.** Cuando la app se empareja, crea una clave en el
chip de seguridad del teléfono; el equipo guarda su huella. Nunca se confía solo en el modelo, el
número de serie o los nombres: cada conexión comprueba esta clave (conexión cifrada con el
certificado recordado) antes de enviar nada más.

* **Cable:** el equipo llega a la app a través del cable y comprueba la clave; el estado dice
  entonces *verificado*. Emparejar por el cable no necesita código: tocas **Emparejar** en el
  teléfono.
* **Wi-Fi:** la app se anuncia con un nombre aleatorio y un código que cambia cada 10 minutos y que
  solo un equipo emparejado puede reconocer. Los demás en la misma red no pueden ver qué teléfono
  es.
* **Bluetooth** (solo para encontrar el teléfono): el mismo código cambiante más la dirección Wi-Fi
  del teléfono, cifrados. Después el equipo se conecta por Wi-Fi. **Nunca se envían archivos por
  Bluetooth.** Para ello, la app del teléfono necesita el permiso "Dispositivos cercanos".

### Carpetas del teléfono

**Cámara** añade la carpeta de la cámara de Android (`DCIM/Camera`). **Elegir carpetas…** muestra las
carpetas del teléfono (por ejemplo, capturas de pantalla (`Pictures/Screenshots`, en Samsung
`DCIM/Screenshots`), imágenes de WhatsApp, `Movies`, `Download`) o te deja escribir una.

**Mantener la estructura de carpetas original** (opción): los archivos de carpetas distintas de la
carpeta de la cámara conservan sus carpetas en la copia, por ejemplo *Karen / Pixel 10 Pro /
Pictures / Screenshots*. La carpeta de la cámara siempre se ordena en carpetas de año y mes.

### Unidades de copia y planes de copia

*Añadir unidad…* muestra las unidades externas conectadas, también las que están enchufadas pero
todavía no abiertas (Linux: se abren con un clic, sin contraseña). *Añadir carpeta…* te deja elegir
cualquier carpeta. Una vista previa muestra exactamente dónde irán los archivos. Un teléfono muestra
solo las unidades que ya se usaron con él, ya marcadas.

Cada unidad tiene un **plan de copia**:

* **Simple**: una carpeta que crece; solo se añaden las fotos y los vídeos nuevos.
* **Abuelo-Padre-Hijo**: copias con fecha: una copia **completa** cada 3 meses, una
  **diferencial** cada mes e **incrementales** entre medias. Las copias completas y diferenciales
  contienen también los archivos anteriores que necesitan, así que las fotos borradas del teléfono
  siguen en cada copia completa.

Se pueden combinar, por ejemplo *Simple* en una unidad y *Abuelo-Padre-Hijo* en la otra.

### Qué hay en la unidad

* **PhoneBackups**: la carpeta en la unidad
  * **Karen**: una carpeta por propietario
    * **Pixel 10 Pro**: la copia de este teléfono
      * **Logs**: los informes (`.txt`, `.html`, `.csv`), p. ej. *Backup Pixel 10 Pro Karen 2026-11-02*
      * **2026**
        * **26.01 … 26.12**: las fotos y los vídeos de cada mes
        * **raw / 26.01 …**: solo si hay fotos RAW / DNG
      * **.phonebackup**: lo que ya está copiado (por favor, no lo borres)

* Carpeta del mes = año + mes: `26.02` es febrero de 2026.
* Las carpetas solo se crean cuando entra un archivo en ellas: no hay carpetas vacías.
* El mes se toma de la fecha en que se hizo la foto o el vídeo; si no, del nombre del archivo
  (`PXL_20261102_…`); si no, de la fecha del archivo.
* Las fotos en movimiento, HEIC, PNG, etc. cuentan como fotos; DNG y otros archivos RAW van a `raw`.
* Mismo nombre, contenido distinto → el archivo nuevo se guarda como `name_1.jpg`. Los archivos
  idénticos se guardan solo una vez.
* A un segundo informe del mismo día se le añade la hora en el nombre.
* Las copias hechas con versiones anteriores (carpetas de mes como `02.February-photos`, carpetas de
  copia como `Pixel 10 Pro - Karen`, informes junto a las fotos) se convierten antes de la siguiente
  copia. Antes de renombrar las carpetas de mes, el programa las muestra y puedes conservar los
  nombres antiguos. Los archivos solo se mueven, nunca se borran.

### Seguridad

* **Teléfono → equipo:** con ADB y con la app del teléfono, el teléfono calcula la huella (SHA-256)
  de cada archivo y el programa la compara con los datos recibidos.
* **Equipo → unidad:** cada copia se escribe en el disco, se vuelve a leer y se compara su huella.
* Los archivos se escriben con un nombre temporal y solo se renombran después de la comprobación.
  Una copia interrumpida nunca deja archivos a medias; la siguiente copia simplemente continúa.
* Primero se comprueba el espacio libre. Si una unidad falla o se llena, la copia continúa en la
  otra unidad y el informe lo muestra en rojo.
* **Nunca el teléfono equivocado:** cada copia recuerda su teléfono (modelo, número de serie, la
  clave de la app del teléfono). Antes de la copia se comprueba el teléfono conectado: otro número
  de serie u otra clave → **rechazado, no se copia nada**. Si solo se puede comparar el modelo,
  tienes que confirmarlo. Justo antes del primer archivo, el teléfono se comprueba una segunda vez.

### Gestionar copias

**Copias** muestra todas tus copias. Elige una para ver sus pestañas:

* **Resumen**: la última copia, qué unidades de copia están completas, las copias Abuelo-Padre-Hijo
  y las copias que no terminaron. Después de cada copia, el programa pregunta si está completa.
* **Carpetas del teléfono**: las carpetas que copia *Actualizar copia*.
* **Unidades de copia**: las unidades de esta copia y sus planes.
* **Carpetas de importación**: añade fotos antiguas a esta copia (ver más abajo).
* **Historial de copias**: cada copia con su resultado y su informe.

**Teléfonos y discos antiguos.** *Nueva copia de un teléfono o disco antiguo…* crea una copia
propia (por ejemplo "Galaxy S7 – Kevin" o "Disco antiguo – Kevin"); *Carpetas de importación* añade
a una copia existente. Añade las carpetas (por ejemplo, la copia de un teléfono antiguo y de su
tarjeta SD) y haz clic en *Elegir carpetas que importar…*: cada carpeta con archivos aparece con sus
fotos, vídeos y otros archivos; los datos de apps, cachés, miniaturas, papelera y carpetas ocultas se
omiten. Para cada carpeta elige:

* **Ordenar en carpetas de año/mes**: ordenada por fecha exactamente como una copia del teléfono.
* **Dejar la carpeta tal como está**: se copia con su nombre en el nivel superior de la copia (por
  ejemplo *Holiday Italy 2019 / Day 1*). Las subcarpetas son líneas aparte: márcalas también para
  conservar todo el árbol.

Cada archivo se comprueba como en una copia del teléfono, los archivos idénticos se guardan solo una
vez y las carpetas antiguas solo se leen.

**Copias seguras (segunda copia).** Copia una copia en una segunda unidad o en **Google
Drive**. Cada copia tiene su propia carpeta con fecha.

| Tipo | Copia |
|---|---|
| completa | todo |
| diferencial | todo lo nuevo desde la última copia **completa** |
| incremental | todo lo nuevo desde la **última** copia (de cualquier tipo) |

**Automático – Abuelo-Padre-Hijo** (por defecto) elige el tipo: completa cada 3 meses (abuelo),
diferencial cada mes (padre), incremental entre medias (hijo). Conserva las 4 copias completas, 3
diferenciales y 6 incrementales más recientes y todo lo que necesitan para una restauración. Las más
antiguas se proponen para quitarlas y se borran **solo después de que lo confirmes** (*Limpiar
exportaciones antiguas…*). Cada archivo copiado se compara con la huella de la copia: un archivo que
se dañó en la primera unidad se indica como advertencia.

**Google Drive.** *Añadir al almacenamiento en la nube → Google Drive* inicia sesión a través del
navegador. El programa solo puede ver los archivos que ha subido él mismo; el inicio de sesión se
queda en este equipo.

* **Copia**: un espejo de la copia en *Mi unidad / My Smartphone Media Backup*: solo se suben los
  archivos nuevos, no se borra ni se sobrescribe nada.
* **Abuelo-Padre-Hijo**: cada foto se guarda solo **una vez**; las copias posteriores enlazan a ella
  (accesos directos, sin espacio extra). Por favor, no borres allí fotos sueltas a mano: todas las
  copias que enlazan a ellas las perderían.

Cada subida se comprueba con la propia huella de Google. Política de privacidad:
<https://machetso.github.io/my-smartphone-media-backup/privacy.html>

**Restaurar.** Elige la copia (en una unidad o en Google Drive), la fecha y la carpeta de destino.
El programa reconstruye una carpeta completa a partir del menor número posible de copias y comprueba
cada archivo.

### Ajustes del programa

* **Idioma** (también en el globo de arriba a la derecha): cambia después de reiniciar.
* **ADB**: se encuentra automáticamente; *Descargar ADB…* lo descarga de Google.
* **Forzar la escritura de los datos en el disco antes de verificar**: más seguro, algo más lento
  (activado por defecto).
* **Mantener el equipo activo** durante la copia, la importación, la copia de las copias y la
  restauración (activado por defecto). Los ajustes de energía en sí no se cambian. Linux: la
  suspensión, cerrar la tapa y apagar quedan bloqueados mientras se ejecuta una tarea, y la pantalla
  sigue encendida. Windows: se evita la suspensión y Windows pregunta antes de apagar; la tapa y el
  botón de encendido siguen los ajustes de Windows.
* **Buscar una versión nueva al iniciar**: una vez al día. *Actualizar ahora* descarga la nueva
  versión, comprueba que está firmada por el proyecto, sustituye el programa y lo reinicia. Los
  ajustes, las unidades, los teléfonos y los emparejamientos se conservan. Si la nueva versión no
  arranca, la anterior se restablece automáticamente.
* **Teléfonos conocidos**: los teléfonos emparejados, la versión de la app del teléfono y las
  actualizaciones automáticas de la app.

Los ajustes se guardan en `~/.config/phonebackup/config.json` (Windows:
`%APPDATA%\PhoneBackup\config.json`).

**Icono de inicio (Linux):** el script *install-linux-desktop.sh* de la carpeta del programa pone el
programa en el menú de aplicaciones y en el escritorio.

### Probado con

* Linux (Pop!_OS) con un Google Pixel 10 Pro (Android 17) por USB 3 con ADB: 1372 archivos / 20 GB
  en dos unidades externas a la vez, unos 24 MB/s.
* Samsung Galaxy S20 FE por USB (ADB) y por Wi-Fi con la app del teléfono: 12,4 MB/s por Wi-Fi.
* Google Drive: Copia y Abuelo-Padre-Hijo con una copia de 20 GB, limpieza y restauración.
* Todavía sin probar en hardware real: la alternativa de transferencia de archivos (MTP) y Windows
  en general.

## Licencia

MIT: consulta [LICENSE](LICENSE). Novedades: [CHANGELOG.md](CHANGELOG.md).
