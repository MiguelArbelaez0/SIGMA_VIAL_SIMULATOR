# Proyecto base de ESP32

En VS Code, abre **PlatformIO Home → Open Project** y selecciona esta carpeta, que contiene `platformio.ini`. El entorno `esp32dev` usa Arduino y tiene configurada una velocidad de monitor de 115200 baudios.

Para compilar, abre la terminal de PlatformIO en esta carpeta y ejecuta:

```sh
pio run
```

PlatformIO guarda el resultado en `.pio/`, excluido de Git. La compilación se puede realizar con la placa desconectada.

En una etapa futura, SIGMA VIAL enviará por USB las fases que decida el simulador. El ESP32 confirmará la recepción y encenderá los LED correspondientes. COM3 fue el puerto observado en el PC de desarrollo.

La implementación física anterior se conserva en el historial, en el commit `0e3ac6353eb21822b21df786ceff070d575cd8fb`.
