# ESP32 procesador de SIGMA VIAL

## Presentación por Wi-Fi

1. Alimenta por USB el ESP32 que tiene grabado el entorno `presentacion`. Al arrancar crea la red **SIGMA-VIAL-Prueba-cf98**. La compilación y la carga solo se necesitan para instalar o actualizar el firmware.
2. Conecta el PC a esa red desde Windows. Si el perfil ya está guardado, ejecuta `netsh wlan connect name="SIGMA-VIAL-Prueba-cf98" interface="Wi-Fi"`. En otro PC, usa la clave privada de `include/ap_local.h`.
3. Desde la raíz del repositorio, abre el simulador con `.\.venv\Scripts\python.exe -m sigma_vial`. En **ESP32 por Wi-Fi**, introduce `192.168.4.1` y pulsa **Conectar**. El monitor USB a 115200 baudios permite consultar el anuncio `LISTEN IP=192.168.4.1 TCP=5050`. El panel confirma el enlace cuando recibe `PONG`.
4. Pulsa **Iniciar**. Cada segundo de reloj, el panel toma los cuatro conteos de vehículos detenidos dentro de las zonas de detección. Si hay una petición pendiente, espera a la siguiente oportunidad. **Esperando primera muestra** indica que falta la primera respuesta. **Datos actuales** identifica la pareja de petición y respuesta visible. **Enviar muestra de cola** permite solicitar una lectura de diagnóstico.
5. Para mostrar una fila EO, desactiva la generación automática, agrega cinco vehículos en Norte y comienza la simulación. Agrega doce en Oriente y ocho en Occidente durante el verde de Norte. Observa el resultado cuando lleguen a la zona de detección. Para NS, pulsa **Reiniciar** e invierte los ejes. **Pausar** conserva la lectura marcada como pausada. **Reiniciar** descarta la sesión anterior.
6. Si se pierde el enlace aparece **Sin conexión**. La simulación continúa. Con el PC de vuelta en la red de la placa, el panel reintenta la conexión y exige un nuevo PONG y una nueva respuesta de tráfico para indicar **Datos actuales**. Al terminar, pulsa **Desconectar** y devuelve el PC a su red con `netsh wlan connect name="Estudiantes-CEIPA" interface="Wi-Fi"`. Deja el entorno de presentación en la placa.

Capturas del panel con tráfico generado desde la interfaz: [Oriente–Occidente](../../docs/esp32-trafico-eo.png) y [Norte–Sur](../../docs/esp32-trafico-ns.png).

## Protocolo y fuente de demanda

El PC abre una conexión TCP IPv4 al puerto 5050 del ESP32. Envía una orden ASCII por línea, de hasta 64 bytes más LF o CRLF. La placa responde con una línea. `PING` recibe `PONG`. La orden `TRAFICO N S E O` lleva exactamente cuatro enteros decimales entre 0 y 9999 inclusive, en orden Norte, Sur, Oriente y Occidente, separados por espacios o tabuladores. Un error devuelve `ERROR` y el motivo. La siguiente línea inicia otra petición.

| PC envía | ESP32 responde |
| --- | --- |
| `TRAFICO 0 0 5 3` | `OK NS=0 EO=8 TOTAL=8 MAYOR=EO` |
| `TRAFICO 5 3 0 0` | `OK NS=8 EO=0 TOTAL=8 MAYOR=NS` |

El procesador suma los dos ejes, calcula el total y compara la demanda. Los otros resultados posibles son `EMPATE` y `SIN_DEMANDA` (total cero). El simulador conserva el control de los semáforos.

La única fuente activa es `SimulatedObservationSource`. El punto de integración para una futura cámara es `ObservationSource.read()` en [perception.py](../../src/sigma_vial/domain/perception.py). El panel toma los campos de cola de una sola llamada a `Simulation.observations()`. Para la siguiente etapa queda por decidir si la cámara entregará imágenes o conteos, por qué enlace y qué acceso cubrirá. Un acceso fuera de su campo de visión queda sin observar. Habrá que seleccionar una sola fuente por acceso y conservar la cobertura de los demás antes de construir una muestra completa. Un cero representa una cola observada y vacía.

## Instalación y diagnóstico

Abre esta carpeta en VS Code con PlatformIO. Para preparar el entorno de presentación en otro equipo, proporciona el archivo privado `include/ap_local.h` con las macros de texto `SIGMA_AP_SSID` y `SIGMA_AP_PASSWORD`. El entorno alternativo `esp32dev` usa DHCP en Estudiantes-CEIPA y toma la contraseña de la macro `SIGMA_WIFI_PASSWORD` en `include/wifi_local.h`. Git ignora ambos archivos.

Desde esta carpeta, con el monitor cerrado y el ESP32 identificado en COM3, estos comandos compilan e instalan el firmware de presentación:

```powershell
$pio = "$env:USERPROFILE\.platformio\penv\Scripts"
& "$pio\pio.exe" run -e presentacion
& "$pio\pio.exe" run -e presentacion -t upload --upload-port COM3
```

El protocolo también está disponible por USB (115200, 8N1). Para probarlo ejecuta `& "$pio\python.exe" .\demo.py --port COM3`. Con el panel desconectado, la orden serie `TEST TCP` comprueba la escucha mediante loopback en la propia placa.
