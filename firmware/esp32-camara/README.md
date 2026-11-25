# Cámara Freenove ESP32-WROVER-DEV

Abre esta carpeta con **PlatformIO → Open Project**. Crea localmente `include/wifi_local.h` con la macro de texto `SIGMA_WIFI_PASSWORD` que contiene la clave de Estudiantes-CEIPA. Git excluye este archivo. Ejecuta `pio run` para compilar.

Para instalar, identifica el puerto con `pio device list` antes y después de desconectar solo el USB de la cámara. Con la placa reconectada y el monitor cerrado, usa `pio run -t upload --upload-port PUERTO` sustituyendo PUERTO por el puerto verificado. El monitor a 115200 baudios anuncia la IP asignada por DHCP y la URL del video.

Desde el PC conectado a Estudiantes-CEIPA, abre la URL anunciada. Después abre **Central de Monitoreo → Configurar cámara** (u **Opciones → Editar URL** si ya estaba asignada) y pega esa URL en el acceso elegido. Se sirve un flujo MJPEG a 320 × 240 para un espectador a la vez. Cierra el navegador antes de conectar la central.

La asignación de pines corresponde al [ejemplo CameraWebServer de Freenove](https://github.com/Freenove/Freenove_ESP32_WROVER_Board/tree/main/C/Sketches/Sketch_06.1_CameraWebServer).
