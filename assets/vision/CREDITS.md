# Origen y permisos de los recursos

- `yolox.onnx` y `nanodet.onnx`: OpenCV Zoo, modelos YOLOX (2022nov) y NanoDet
  (2022nov), Apache-2.0. Se incluyen sus licencias. Pesos sin modificar.
  https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox
  https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet
- Código de decodificación en `infrastructure/vendor`: OpenCV Zoo, Apache-2.0.
  Adaptaciones SIGMA: formato, zip estricto, NanoDet de tres niveles y asociación
  de salidas por sus dimensiones para OpenCV 5; no se cambian los pesos.
- `traffic-demo.mp4`: extracto de `person-bicycle-car-detection.mp4` del repositorio
  Intel IoT DevKit / sample-videos. Crédito: Intel IoT DevKit y contribuidores.
  Licencia declarada por ese repositorio: CC BY 4.0 (texto completo VIDEO-LICENSE).
  Modificaciones: segundos 42–50, reducción a 960x540, recodificación MPEG-4 a 12 fps,
  sin audio. Este extracto y sus imágenes derivadas se distribuyen con CC BY 4.0.
  https://github.com/intel-iot-devkit/sample-videos/blob/master/person-bicycle-car-detection.mp4
  https://github.com/intel-iot-devkit/sample-videos/blob/master/LICENSE
  https://creativecommons.org/licenses/by/4.0/
- `synthetic.png`: captura propia de gráficos de SIGMA VIAL; dos automóviles cenitales.
- `manifest.json`: tamaños y SHA-256 de los recursos evaluados y distribuidos.

No se distribuyen las descargas exploratorias de OpenCV Extra, cuya licencia
individual del video no pudo confirmarse. Las pruebas finales usan únicamente el
extracto con licencia CC BY 4.0 indicada arriba. Los intentos de descarga de Commons
y Pexels fueron bloqueados por HTTP 403/429; no son los videos evaluados ni incluidos.
