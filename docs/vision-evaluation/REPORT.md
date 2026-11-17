# Viabilidad de visión por píxeles

Evaluación reproducible con `python tools/evaluate_vision.py`. Los datos detallados,
recuadros predichos y confianza original están en `results.json`; anotaciones en
`annotations.json`. Umbral del modelo: 0,35. Emparejamiento de localización: IoU ≥ 0,5.
Los seis fotogramas reales tienen 960×540 píxeles; cinco muestran **el mismo automóvil**
en instantes distintos (incluidas apariciones parciales) y uno no contiene vehículos.
Las cajas aproximadas se revisaron visualmente durante esta tarea; no cuentan con
una segunda revisión independiente. No se anotan peatones/bicicletas porque el
pipeline de esta entrega filtra vehículos de cuatro categorías de COCO.

| Modelo | Real: aciertos / omisiones / falsos positivos | Gráficos SIGMA: aciertos / omisiones / falsos positivos | Mediana CPU real |
| --- | --- | --- | --- |
| NanoDet, 3,8 MB | 1 / 4 / 0 | 0 / 2 / 0 | 25 ms |
| YOLOX, 35,9 MB | 5 / 0 / 0 | 0 / 2 / 0 | 87 ms |

Los tiempos son mediciones locales de inferencia/preprocesado, no FPS de la GUI.
Se eligió YOLOX para video local. **No se eligió ninguno para controlar el simulador
mediante sus dibujos**, porque ambos omitieron los dos autos cenitales de la captura.
La opción de captura sintética queda como laboratorio que muestra ese fallo sin
sustituir sus resultados por entidades internas. La percepción del cruce sigue
siendo explícitamente simulada y conserva las protecciones y política de sensores.

La muestra es pequeña y sesgada: no demuestra precisión general, reconocimiento de
motos/buses/camiones en cámaras reales, robustez nocturna, ni lectura de placas.
No hay OCR; las placas reales se muestran como **Sin lectura**. No se valida
compatibilidad con placas colombianas. La prueba automatizada de cola con imagen
real congelada verifica que se detecta apariencia sin exigir movimiento; no equivale
a validar colas reales con oclusiones. Los ensayos de oclusión, dirección de conteo,
IDs, expiración y duplicados prueban el algoritmo de seguimiento con recuadros
controlados, no la precisión de detección de objetos en un dataset independiente.

El seguimiento asocia centros con predicción de velocidad y tolerancia por tamaño; confirma en dos
observaciones, conserva un ID en oclusiones de hasta 1,5 s y finaliza después.
Una variación puntual de clase del modelo no crea por sí sola otro ID.
Puede intercambiar IDs cuando vehículos similares se cruzan o reaparecen tras una
oclusión larga. Las trayectorias conservan los últimos 128 puntos y primera/última
observación. Cada trayectoria cuenta una vez al cruzar la línea en el sentido
seleccionado. El video de demostración circula hacia arriba: el botón correspondiente
selecciona sentido negativo. La división de carriles por mitad de imagen es una
calibración de demostración; requiere calibración por escena para usos reales.

Fuentes, licencias, modificaciones del clip y hashes en
[`assets/vision/CREDITS.md`](../../assets/vision/CREDITS.md). El video de Intel IoT
DevKit se distribuye como extracto CC BY 4.0 con su atribución. Los modelos y su
código de OpenCV Zoo llevan Apache-2.0. No se entrenó ningún modelo ni se descargó
un dataset. Los recursos incluidos suman aproximadamente 40 MB.

Validación nativa: Qt Windows, cuatro vistas renderizadas, video procesado por el
modelo en un trabajador, cambio a captura sintética y cierre sin errores. Las capturas
se revisaron visualmente; no se afirma una prueba humana continua ni una instalación
física de cámara. La prueba de carga es un solo trabajador y un fotograma en curso;
se omiten nuevas solicitudes mientras esté ocupado, evitando colas de video atrasado.

En una reproducción adicional a 5 lecturas/s del extracto completo se observó una
clasificación puntual como camión del automóvil. Esa inconsistencia no aparece en
los seis fotogramas elegidos y confirma que el resultado de la tabla no debe
interpretarse como precisión del video completo. No se oculta ni se reemplaza esa
clasificación con metadatos del escenario.

La comprobación nativa final del extracto, tras tolerar cambios puntuales de clase,
conservó un ID y registró un paso para el automóvil. Se comprobó mediante ejecución
y aserciones del programa, además de revisar la captura; no demuestra ausencia de
intercambios de ID en tráfico con múltiples vehículos superpuestos.
