# ESP32 de pantalla de SIGMA VIAL

Este proyecto prepara el firmware del ESP32 que recibirá datos de SIGMA VIAL, los procesará y mostrará los resultados en una pantalla. La base usa Arduino y el entorno PlatformIO `esp32dev`.

## Compilar en VS Code

1. En VS Code con la extensión PlatformIO IDE instalada, abre **Archivo → Abrir carpeta** y selecciona `firmware/esp32-pantalla/`, donde está `platformio.ini`.
2. Abre una terminal de PlatformIO en esa carpeta y ejecuta `pio run`.
3. Comprueba que el resultado del entorno `esp32dev` sea **SUCCESS**. Puedes compilar con el ESP32 desconectado.
