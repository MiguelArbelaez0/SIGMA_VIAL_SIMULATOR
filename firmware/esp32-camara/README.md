# Cámara Freenove ESP32-WROVER-DEV

Abre esta carpeta con **PlatformIO → Open Project**. El entorno predeterminado `presentacion` conecta la cámara al punto de acceso del procesador. Usa las macros privadas `SIGMA_AP_SSID` y `SIGMA_AP_PASSWORD` de `../esp32-procesador/include/ap_local.h`. Ejecuta `pio run` para compilar. Para la variante de campus usa `pio run -e freenove_esp32_wrover` con la macro privada `SIGMA_WIFI_PASSWORD` en `include/wifi_local.h`.

Para instalar, identifica el puerto con `pio device list` antes y después de desconectar solo el USB de la cámara. Con la placa reconectada y el monitor cerrado, usa `pio run -t upload --upload-port PUERTO` sustituyendo PUERTO por el puerto verificado. El monitor a 115200 baudios anuncia la IP asignada por DHCP y la URL del video.

Para presentar, alimenta primero el procesador y después la cámara. Conecta el PC a **SIGMA-VIAL-Prueba-cf98** y pulsa **Conectar al ESP32**. El procesador usa `192.168.4.1:5050`; la cámara anuncia su propia IP. Abre **Central de Monitoreo → Configurar cámara** (u **Opciones → Editar URL** si ya estaba asignada) y pega la URL anunciada. Si DHCP le asigna otra IP, actualiza esa URL. Se sirve un flujo MJPEG a 320 × 240 para un espectador a la vez. Cierra el navegador antes de conectar la central.

La asignación de pines corresponde al [ejemplo CameraWebServer de Freenove](https://github.com/Freenove/Freenove_ESP32_WROVER_Board/tree/main/C/Sketches/Sketch_06.1_CameraWebServer).
