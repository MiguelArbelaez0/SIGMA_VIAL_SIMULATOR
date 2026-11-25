# Cámara Freenove ESP32-WROVER-DEV

Abre esta carpeta con **PlatformIO → Open Project**. El entorno predeterminado `usb` entrega imágenes JPEG de 320 × 240 por el puente USB-serie a 460800 baudios. El PC solicita cada imagen enviando el byte ASCII J. La cámara responde con la marca SVJ1, el tamaño JPEG en cuatro bytes little-endian y la imagen. Cierra cualquier monitor serie antes de conectar la Central.

El entorno alternativo `presentacion` conecta la cámara al punto de acceso del procesador. Usa las macros privadas `SIGMA_AP_SSID` y `SIGMA_AP_PASSWORD` de `../esp32-procesador/include/ap_local.h`. Ejecuta `pio run -e presentacion` para compilar la variante inalámbrica. Para la variante de campus usa `pio run -e freenove_esp32_wrover` con la macro privada `SIGMA_WIFI_PASSWORD` en `include/wifi_local.h`.

Para instalar, identifica el puerto con `pio device list` antes y después de desconectar solo el USB de la cámara. Con la placa reconectada y el monitor cerrado, usa `pio run -t upload --upload-port PUERTO` sustituyendo PUERTO por el puerto verificado. En las variantes inalámbricas el monitor a 115200 baudios anuncia la IP asignada por DHCP y la URL del video.

Para la presentación USB, conecta ambas placas al PC. En **Cambiar dirección** introduce el puerto del procesador (`COM3` en el equipo verificado). En **Central de Monitoreo → Norte → Opciones → Editar URL** introduce solo el puerto de la cámara (`COM4`). SIGMA VIAL recuerda ambos valores.

Para la presentación Wi-Fi, alimenta primero el procesador y después la cámara. Conecta el PC a **SIGMA-VIAL-Prueba-cf98** y pulsa **Conectar al ESP32**. El procesador usa `192.168.4.1:5050`; la cámara anuncia su propia IP. Abre **Central de Monitoreo → Configurar cámara** (u **Opciones → Editar URL** si ya estaba asignada) y pega la URL anunciada. Si DHCP le asigna otra IP, actualiza esa URL. Se sirve un flujo MJPEG a 320 × 240 para un espectador a la vez. Cierra el navegador antes de conectar la central.

La asignación de pines corresponde al [ejemplo CameraWebServer de Freenove](https://github.com/Freenove/Freenove_ESP32_WROVER_Board/tree/main/C/Sketches/Sketch_06.1_CameraWebServer).

### Medición opcional en Norte por USB

La central envía `C` seguido de ocho coordenadas uint16 little-endian (x e y de los dos extremos de cada carril) para guardar la referencia vacía en RAM. Después solicita cada observación con `N`. Ambos comandos devuelven `SVJ2`, la longitud JPEG uint32 little-endian, un byte de conteo y el JPEG del mismo fotograma. El valor 255 indica una lectura no disponible. `J` conserva el formato de video `SVJ1`.

La placa decodifica el JPEG, compara el color a lo largo de las guías con el fondo y cuenta tramos contrastados cuyos extremos permanecen estables al menos 0,7 segundos. La muestra describe la fila visible en ese instante. Sigue los pasos de [calibración y presentación](../../README.md#medir-la-fila-de-norte-con-la-cámara).
