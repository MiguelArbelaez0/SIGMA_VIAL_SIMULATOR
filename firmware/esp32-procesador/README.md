# ESP32 procesador de SIGMA VIAL

El procesador recibe por USB una muestra de cuatro conteos en orden Norte, Sur, Oriente y Occidente. Calcula las sumas de los ejes, el total y el eje con mayor demanda en esa muestra. La decisión de cambiar semáforos queda para otra etapa. Se prevé incorporar video desde otro ESP32; el formato del video y el enlace entre placas están pendientes de definición.

## Demostración en Windows

Abre esta carpeta en VS Code con PlatformIO IDE. Cierra el monitor serial con **Ctrl + C** para liberar el puerto. En una terminal PowerShell situada junto a `platformio.ini`, ejecuta:

```powershell
$pio = "$env:USERPROFILE\.platformio\penv\Scripts"
& "$pio\pio.exe" run
& "$pio\pio.exe" run -t upload --upload-port COM3
& "$pio\python.exe" .\demo.py --port COM3
```

Usa el puerto que corresponda a tu placa en ambos comandos. La carga reemplaza su firmware. Para repetir la demostración basta ejecutar el último comando después de definir `$pio`. La utilidad usa pySerial del entorno de PlatformIO, espera el arranque y comprueba las respuestas recibidas, incluidos errores y recuperación.

## Protocolo

USB serial a 115200 baudios, 8N1. Envía una línea ASCII de hasta 64 bytes, más LF o CRLF. `PING` devuelve `PONG`. `TRAFICO` acepta exactamente cuatro enteros decimales sin signo entre 0 y 9999 inclusive. Separa los campos con espacios o tabuladores. Las entradas inválidas devuelven `ERROR` con el motivo; la siguiente línea inicia una nueva orden.

```text
PC envía: TRAFICO 4 2 7 1
ESP32 responde: OK NS=6 EO=8 TOTAL=14 MAYOR=EO
```

Los valores de `MAYOR` son `NS`, `EO`, `EMPATE` y `SIN_DEMANDA` (total cero).
## Conexión Wi-Fi desde SIGMA VIAL

El firmware usa el SSID `Estudiantes-CEIPA` y obtiene su IPv4 por DHCP. Antes de compilar para la placa, guarda la clave en el archivo privado `include/wifi_local.h` de este proyecto. Git excluye ese archivo. En un checkout nuevo créalo con estas dos líneas y escribe la clave entre los paréntesis:

```cpp
#pragma once
#define SIGMA_WIFI_PASSWORD R"wifi()wifi"
```

Después de cargar el firmware, abre el monitor serie a 115200 baudios. Si la conexión ya se estableció antes de abrirlo, pulsa EN para reiniciar la placa. Copia la dirección de la línea `IP=<dirección asignada> TCP=5050` en **ESP32 por Wi-Fi** en el simulador y pulsa **Conectar**. El PC debe tener acceso a la IP de la placa por TCP 5050. La confirmación aparece al recibir la línea `PONG`. El procesamiento de muestras por USB sigue disponible.

El mensaje `LISTEN` se emite después de abrir la escucha IPv4. Con el panel desconectado, la orden serie `TEST TCP` prueba el servidor mediante una conexión TCP interna del ESP32 por 127.0.0.1. Para verificar el trayecto inalámbrico, conecta el panel y compara su confirmación con la IP del cliente y el envío de PONG que registra la placa.

## Presentación con tráfico del simulador

1. Abre esta carpeta en PlatformIO. El entorno `presentacion` usa el SSID y la clave WPA2 del archivo privado `include/ap_local.h` (macros de texto `SIGMA_AP_SSID` y `SIGMA_AP_PASSWORD`). En el PC de la demostración ya está preparado para la red **SIGMA-VIAL-Prueba-cf98**. Para reproducirla en otro PC, copia ese archivo por un medio privado.
2. Con el monitor cerrado, ejecuta desde PowerShell:

   ```powershell
   & "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -e presentacion -t upload --upload-port COM3
   ```

3. Abre el monitor a 115200 baudios y pulsa EN si necesitas repetir el anuncio. Conecta Windows al SSID de presentación usando la clave local. En **ESP32 por Wi-Fi**, escribe la IP anunciada en `LISTEN` y pulsa **Conectar**. En la prueba física se anunció `192.168.4.1` y el puerto TCP fue 5050.
4. Desactiva la generación automática, abre **Agregar** y agrega cinco vehículos en Norte. Pulsa **Iniciar**. Cuando Norte esté en verde, agrega doce vehículos en Oriente y ocho en Occidente. Deja que se aproximen a las cebras y formen fila. Puedes pausar la simulación para conservar el instante de la muestra.
5. Pulsa **Enviar muestra de cola**. El panel toma una sola observación y envía los vehículos detenidos dentro de las zonas de detección en orden Norte, Sur, Oriente y Occidente. Debajo aparece la línea recibida por TCP del procesador. Para probar el caso inverso, pulsa **Reiniciar**, comienza por Oriente y agrega la demanda mayor en Norte y Sur.
6. Al terminar, pulsa **Desconectar**, vuelve a **Estudiantes-CEIPA** desde Windows y cierra el monitor. Restaura en la placa el entorno que usa DHCP:

   ```powershell
   & "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -e esp32dev -t upload --upload-port COM3
   ```

Capturas físicas de la demostración: [cola mayor en Oriente–Occidente](../../docs/esp32-trafico-eo.png) y [cola mayor en Norte–Sur](../../docs/esp32-trafico-ns.png).
