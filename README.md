# SIGMA VIAL

Aplicación de escritorio de **SIGMA SOFTWARE SOLUTIONS** con simulación vial local,
control por demanda, percepción simulada e identificación por OCR y registro SQLite.

![Interfaz actual de SIGMA VIAL: simulación e identificación por placa](docs/dashboard.png)

La captura es de la aplicación real en Windows, con una lectura de Tesseract y una
ficha recuperada del registro ficticio. No es una imagen generada ni un fondo estático.

## Preparación en Windows / PowerShell

Se utiliza **CPython 3.14 de 64 bits** (validado con 3.14.7). El paquete admite
exclusivamente la serie 3.14 por ahora; ampliar ese rango requiere validación.
Se necesitan Git, Python con `venv` y acceso a PyPI durante la instalación.
No hace falta instalar Qt por separado, activar PowerShell ni cambiar su política.

Desde la carpeta del proyecto:

```powershell
Set-Location 'C:\Users\USUARIO\Desktop\DESARROLLO\05_PYTHON\SIGMA_VIAL_SIMULATOR'
# Si Python está instalado en otra ubicación, ajustar únicamente esta ruta.
& "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e '.[dev]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m sigma_vial
```

Si `.venv` ya existe, comprobar primero `.\.venv\Scripts\python.exe --version`
y reutilizarlo si corresponde a Python 3.14. No es necesario recrearlo.
La instalación editable permite importar `sigma_vial` desde cualquier carpeta sin
configurar `PYTHONPATH`. También instala el lanzador `.\.venv\Scripts\sigma-vial.exe`.

## Dependencias y reproducibilidad

`pyproject.toml` es la fuente de declaración de dependencias, rangos y herramientas.
`requirements-dev.lock` se genera desde ese archivo con pip-tools y fija versiones
y hashes de dependencias directas, transitivas y herramientas de construcción.
El bloqueo está destinado a Windows x64 con Python 3.14; no certifica otras plataformas.
La instalación anterior usa las herramientas de construcción fijadas en el entorno
mediante `--no-build-isolation` y evita resolver de nuevo el paquete editable.

Para actualizar, editar los rangos en `pyproject.toml` solo cuando sea necesario y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m piptools compile --extra dev --allow-unsafe --generate-hashes --upgrade --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e '.[dev]'
.\.venv\Scripts\python.exe -m pip check
```

Revisar el diff del bloqueo y repetir las verificaciones antes de integrar cambios.
Para regenerarlo sin solicitar actualizaciones, omitir `--upgrade`.
No editar manualmente el archivo generado ni copiar listas alternativas de versiones.

Compatibilidad consultada en fuentes oficiales:
[Qt for Python](https://doc.qt.io/qtforpython-6/gettingstarted.html),
[metadatos PySide6](https://pypi.org/project/PySide6/),
[pytest](https://docs.pytest.org/en/stable/getting-started.html),
[pytest-qt](https://github.com/pytest-dev/pytest-qt) y
[Ruff](https://docs.astral.sh/ruff/faq/).
Se eligió un intérprete instalado de la serie 3.14, en lugar del predeterminado 3.15.
La resolución de paquetes y las pruebas locales complementan esa comprobación.

## Verificación y formato

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
# Aplicar formato cuando se edite código:
.\.venv\Scripts\python.exe -m ruff format .
```

Las pruebas comprueban textos, construcción, apertura, cambio de tamaño y cierre,
cuatro accesos, 16 carriles, sentidos de las flechas realmente dibujadas, cuatro
semáforos inicialmente rojos, colores renderizados por estado y controles de zoom.
También verifican pausado, reanudación, reinicio, velocidad, sincronización de
entidades, escenarios, separación de cola, salida bloqueada, despeje y que los
semáforos y rótulos no invadan las calzadas.
Las importaciones se prueban en procesos independientes con tiempo límite, sin
crear una QApplication. pytest-qt administra su propia aplicación y no deja un
bucle gráfico bloqueado. En equipos sin pantalla se puede establecer temporalmente
`$env:QT_QPA_PLATFORM = 'offscreen'`; eso no constituye verificación visual.
Retirar esa variable con `Remove-Item Env:QT_QPA_PLATFORM` antes de abrir la ventana.
En Windows, el control de zoom automatizado prueba la vista sin mostrar otra ventana
nativa durante el ciclo de eventos de pytest. Mostrar la vista en esa prueba producía
`Windows fatal exception: 0x8001010d` en `pytestqt.plugin._process_events`; el proceso
seguía reportando pruebas aprobadas. La prueba conserva las comprobaciones de zoom y
encuadre, y la apertura nativa se valida por separado ejecutando la aplicación normal.

## Organización

- `src/sigma_vial/domain/`: accesos, configuración de carriles y estados de luz; sin Qt.
- `src/sigma_vial/application/`: futura coordinación de casos de uso.
- `src/sigma_vial/presentation/`: composición de la ventana (`main_window.py`),
  geometría común (`geometry.py`), pavimento y marcas (`road_items.py`), semáforo
  reutilizable (`traffic_light.py`), escena (`intersection_scene.py`) y vista
  con encuadre y zoom (`intersection_view.py`).
- `src/sigma_vial/infrastructure/`: futuros adaptadores externos.
- `src/sigma_vial/bootstrap.py`: composición y ciclo de vida de QApplication.
- `src/sigma_vial/__main__.py`: ejecución mediante `python -m sigma_vial`.
- `tests/`: pruebas automáticas y contratos de importación.

El motor determinista está en `src/sigma_vial/domain/simulation.py`; la ventana
coordina el temporizador y dibuja entidades desde el estado del motor.

## Simulación funcional

Intersección ficticia en “+” con accesos norte, sur, oriente y occidente; cada acceso
tiene un semáforo vehicular, dos carriles de entrada y dos de salida. El motor mueve
vehículos y peatones virtuales, decide por demanda, espera y ocupación, y administra
fases de inicio, pausa, reinicio y despeje.

Supuestos del modelo: solo movimientos rectos; norte-sur comparte fase y
oriente-occidente comparte otra. Los peatones tienen fase exclusiva con admisión y
despeje separados. Implementado:

- Cruce en “+” con norte arriba, sur abajo, oriente a la derecha y occidente a la izquierda.
- Dos carriles de entrada y dos de salida por brazo (8 + 8 en total), circulación
  por la derecha, flechas rectas, separación de sentidos y líneas discontinuas.
- Aceras, cuatro pasos peatonales y detención antes del paso en cada entrada.
- Cuatro semáforos etiquetados, inicialmente rojos, sincronizados con las fases del
  motor y los dos carriles de entrada de cada acceso.
- Vehículos vectoriales con aceleración, frenado, cola espaciada y salida tras despejar
  el cruce; peatones vectoriales visibles en los pasos y aceras. El indicador de fase,
  colas, peatones y luces se actualiza desde el estado de la simulación.
- Controles principales siempre visibles para iniciar, pausar/reanudar, reiniciar,
  velocidad y vista. Las pestañas separan tráfico automático y altas manuales;
  las métricas, sensores y demostraciones se despliegan aparte.
- El escenario inicial equilibrado genera 12 vehículos/minuto por acceso y 2,4
  peatones/minuto. Las llegadas empiezan al pulsar Iniciar y pueden ajustarse.
- Ajuste de escena al redimensionar, tamaño mínimo de ventana de 800 × 600 unidades
  lógicas y desplazamiento vertical del panel cuando falta espacio. Para inspeccionar
  detalles en ventanas pequeñas, usar Acercar y después Restablecer vista.
- Gráficos vectoriales locales con QGraphicsScene/QGraphicsView. La aplicación
  instalada funciona sin internet y no depende de la captura para dibujar el cruce.

La simulación implementa avance determinista con pasos de 0,05 s, semilla configurable,
demanda por cada acceso y medición por los dos ejes. La demanda pendiente incluye
vehículos detenidos, aproximándose y llegadas diferidas; los que salen del cruce no
cuentan para retener el verde. Después del mínimo de verde se comparan cantidades y
esperas; la diferencia debe persistir 1 s, mientras la espera máxima tiene prioridad.
Un carril activo vacío durante 4 s solicita el relevo. Si ambos ejes esperan, el verde
continuo se limita a 32 s. Sin demanda incompatible ni peatones, el verde puede
mantenerse. El contador del verde comienza al habilitar la fase y no se reinicia con
nuevas llegadas. Los parámetros (verde mínimo 8 s, amarillo 3 s, despeje 2 s,
admisión peatonal 8 s) son supuestos didácticos, no tiempos certificados para una vía.

La posición de parada se comparte con la geometría de dibujo y descuenta la mitad de
la longitud del vehículo y un margen de 4 unidades: la carrocería queda antes de la
línea, que está antes de la cebra. Las filas conservan al menos 8 unidades entre
carrocerías. Al cambiar de fase, amarillo cierra nuevas admisiones; los vehículos
comprometidos pueden entrar y el rojo de despeje espera a que la parte trasera de
cualquier vehículo comprometido salga de la zona de conflicto. Una salida bloqueada
impide la entrada y el vehículo recupera el movimiento al liberarla.

El panel de detalles muestra demanda pendiente por eje, detenidos y aproximándose,
vehículos saliendo, espera máxima por eje, duración del verde y motivo de decisión.

La interfaz incluye iniciar, pausar/reanudar, reiniciar conservando tasas de demanda,
ritmo 0,5×/1×/2×/4×, demanda en vehículos/minuto y peatones/minuto, incorporación
manual y escenarios reproducibles cargados en pausa. Dibujos, luces y métricas proceden
del motor. Acercar, alejar y restablecer vista son independientes del reloj simulado.

Parámetros pendientes de mayor validación: restricciones reales de capacidad de las
salidas por carril, geometría individual de los cuatro cruces peatonales, calibración
de velocidades y políticas de espera bajo obstrucciones prolongadas. La demostración
no representa seguridad vial certificada. El ESP32 opcional procesa la demanda
por Wi-Fi. El simulador conserva el control de los semáforos.
Incluye percepción simulada, detección por píxeles opcional, OCR local y SQLite.
La percepción funciona localmente con vehículos simulados.

## Versión de presentación

La rama `main` reúne el simulador, la interfaz y el firmware del primer ESP32.
El procesador recibe los cuatro conteos por Wi-Fi o por USB. Esta rama añade
la medición opcional de la fila de Norte con la cámara física por USB.

## Revisión de la interfaz

La captura real de la ventana se guarda en
[`docs/intersection-ui.png`](docs/intersection-ui.png).
La revisión manual y los resultados de esta entrega están documentados en
[`docs/validation-intersection-ui.md`](docs/validation-intersection-ui.md).


## Tráfico mixto y presentación visual

En **Tráfico automático**, el selector de tipos permite **Aleatorio** o Moto,
Automóvil pequeño, Sedán, Camioneta/SUV, Furgoneta, Bus, Camión pequeño y Camión
grande. Afecta tanto a llegadas automáticas como a incorporaciones manuales.
El porcentaje de buses y camiones ajusta la mezcla aleatoria (10 % inicialmente);
los demás tipos mantienen sus proporciones relativas. Reiniciar conserva esta selección.
Cada vehículo cuenta como una unidad de demanda, independientemente de su tamaño.

Las longitudes van de 20 a 88 unidades y los anchos de 9 a 26, dentro de carriles
de 58 unidades. El catálogo del dominio centraliza velocidad, aceleración y frenada.
El dibujo recibe las mismas dimensiones: se calculan frente, parte trasera,
separación entre carrocerías (8 unidades), espacio de aparición, capacidad mínima
de salida y eliminación después de salir completamente. Los vehículos lentos
siguen limitando a sus seguidores también dentro del cruce y en la salida.
Las salidas bloqueadas siguen impidiendo nuevas entradas; no hay cambios de carril.

Los cuatro semáforos vehiculares tienen carcasa amarilla, panel oscuro, viseras
y soportes horizontales. Cuatro indicadores peatonales adicionales muestran una
mano naranja al detenerse y una persona blanca exclusivamente durante admisión.
Durante despeje no se permite iniciar; quienes cruzan terminan antes del verde
vehicular. Los peatones en espera se distribuyen en la acera; el color turquesa
identifica a quienes cruzan y el violeta a quienes esperan.

![Tráfico mixto con dimensiones compartidas por motor y dibujo](docs/mixed-traffic.png)

Validación de esta entrega: pruebas de filas mixtas, los ocho tipos en los cuatro
accesos, capacidad de salida, despeje trasero del camión, dimensiones gráficas,
indicadores, pausa y reinicio. Se ejecutó Qt con plataforma `windows`, se renderizó
la captura, se ejercitaron zoom repetido y tamaños 1500×1000 y 800×600 mediante
controles programáticos. Una medición de 120 segundos simulados con actualización
de entidades, luces y métricas tomó aproximadamente 1,8 segundos de CPU/tiempo
transcurrido en esta máquina (55 vehículos y 7 peatones al finalizar); no es una
medición de FPS ni una revisión humana continua del movimiento. Los tamaños y
prestaciones son didácticos, no una calibración de vehículos reales.


## Percepción simulada y placas sintéticas

**Sensores** despliega estado y última lectura de las cuatro cámaras virtuales,
ocupación actual, cola (velocidad ≤ 0,5 unidades/s), tipos observados y paso histórico.
La lectura es configurable entre 0,05 y 1 segundo simulado. La casilla de cobertura
muestra zonas turquesa y líneas de paso magenta; no son imágenes de una cámara real.
Cada sensor cubre los dos carriles de entrada de su acceso, desde posición longitudinal
0 a 270; la línea de conteo está en 250. La salida del área de cobertura elimina la
detección activa en la lectura siguiente. La demanda excluye entidades que ya cruzan
o salen y no se confunde con el acumulado histórico de pasos. El seguimiento público
usa identificadores propios de cámara, distintos del identificador del mundo.

`domain/perception.py` define `ObservationSource`, `ObservationBatch`, `Detection`,
`SensorStatus` y `TrafficSummary`. El adaptador `SimulatedObservationSource` obtiene
observaciones de entidades internas, filtradas por cobertura y frecuencia. No ejecuta
clasificación de píxeles, OCR ni reconocimiento real de imágenes. La fuente define
también observaciones de espera peatonal. El controlador consulta demanda, espera y
estado a través del contrato; las entidades completas se conservan para movimiento,
distancias y protección del cruce. Esas protecciones son capacidades del simulador,
no de las cámaras. Las llegadas diferidas fuera del mundo visible no son detecciones.

**Sin datos no significa vacío.** Si falta una de las cuatro lecturas, su estado es
sin datos/desconectado, o la antigüedad supera 1 segundo simulado, se solicita amarillo
y luego rojo; no se habilita otra fase hasta recuperar las observaciones válidas.
Quienes están comprometidos terminan de salir y los peatones siguen protegidos por
el estado del mundo. Las últimas lecturas se conservan hasta la siguiente muestra,
no indefinidamente como demanda válida. Pausar detiene el reloj, el movimiento y las
lecturas del control; reiniciar limpia seguimientos y contadores, pero conserva
el registro SQLite. La cámara OCR tiene su propio reloj de observación: puede leer
un vehículo detenido o la simulación pausada.

Una futura fuente de imágenes implementará el mismo contrato, entregando detecciones,
seguimientos, tiempos y disponibilidad. Puede usar tipo desconocido y confianza
opcional; el contrato admite `confidence=None`. Debe aportar su propia lectura de
peatones. El argumento de mundo del adaptador simulado puede ignorarse en una fuente
externa. La visión opcional se documenta más adelante; no se incorpora hardware.

`domain/catalog.py` es el catálogo Python local, ampliable y validado: identificador
de modelo, tipo, marca/modelo ficticios, dimensiones, prestaciones y variante gráfica.
No es un conjunto de entrenamiento. Al seleccionar un vehículo, **Datos del escenario**
muestra tipo, marca, modelo y placa; la detección actual aparece separada. El detector
no deduce marca o modelo de una imagen.

`PlateService` genera identificadores ficticios de formato colombiano: `ABC123` para
vehículos de cuatro ruedas y `ABC12D` para motos. No corresponden necesariamente a
vehículos registrados. El registro de sesión impide reutilizarlos incluso después
de salir de escena, y una semilla reproduce la secuencia. Incorporación manual,
llegadas automáticas y escenarios usan el mismo servicio. Con el registro SQLite,
reiniciar o volver a abrir la aplicación evita también duplicados de sesiones anteriores.
El motor aislado sin registro conserva la secuencia reproducible por semilla. Las placas están en los datos del
vehículo, en amarillo/negro cuando la escala lo permite y completas en la selección.
El sensor las etiqueta **Lectura simulada**. Un sistema externo necesitará un módulo
independiente de lectura de placas; detectar, contar y seguir no depende de leerlas.

![Cobertura de cámaras virtuales y panel de sensores](docs/simulated-perception.png)

Se verificó arranque y cierre con Qt `windows`, avance mediante temporizador nativo,
pausa, selección con placa completa y detección diferenciada, reinicio y cambio de
tamaño/zoom mediante controles programáticos. La captura se revisó visualmente;
no se afirma una revisión humana continua del movimiento ni validación de cámaras reales.


## Generación automática e incorporación manual

La barra fija encima del plano incluye **Iniciar / Pausar / Continuar**, **Reiniciar**,
velocidad y estado. Zoom y restablecimiento están junto al plano. Cambiar de pestaña
solo cambia el formulario visible: ambas fuentes de llegada pueden coexistir y el
control semafórico sigue siendo automático, basado en sensores.

**Tráfico automático** tiene un interruptor independiente y cinco perfiles. Elegir
uno aplica inmediatamente las tasas a las llegadas futuras y a los campos, sin borrar
entidades, modificar la fase ni reiniciar el reloj. Editar una tasa selecciona
**Personalizado**. Las tasas son por acceso, no por carril.

| Perfil | Norte | Sur | Oriente | Occidente | Peatones/min |
| --- | ---: | ---: | ---: | ---: | ---: |
| Equilibrado | 12 | 12 | 12 | 12 | 2,4 |
| Mayor tráfico Norte–Sur | 18 | 18 | 3 | 3 | 2,4 |
| Mayor tráfico Oriente–Occidente | 3 | 3 | 18 | 18 | 2,4 |
| Más peatones | 4 | 4 | 4 | 4 | 12 |

Las columnas vehiculares están en vehículos/minuto. El selector de tipos y el
porcentaje de buses/camiones configuran exclusivamente las nuevas altas automáticas;
la pestaña manual usa su propio selector. Los ajustes avanzados están plegados al
inicio y explican la política de solicitudes.

**Al apagar la generación**, se congelan los acumuladores de llegadas nuevas, tanto
vehiculares como peatonales. No se acumulan llegadas durante el apagado ni se produce
una ráfaga para recuperar ese tiempo al encenderla. Se conserva la fracción de llegada
que ya había transcurrido. Las solicitudes completas pendientes, automáticas o
manuales, siguen intentando incorporarse cuando hay espacio: conservan su tipo en
una cola por acceso, no se descartan al apagar. Las entidades presentes siguen
moviéndose si la simulación está iniciada. Pausar congela el tiempo y esos reintentos.

**Agregar manualmente** contiene dos formularios: acceso, tipo y cantidad de
vehículos; paso y cantidad de peatones. Cada botón admite entre 1 y 100 solicitudes.
La confirmación informa cuántos vehículos entraron y cuántos quedaron pendientes por
falta de espacio. Los peatones se incorporan en la acera y esperan su fase. La placa
se asigna al materializar un vehículo y conserva unicidad dentro de la sesión.
Cambiar de pestaña conserva los valores; reiniciar limpia el mundo y sus solicitudes,
pero conserva las tasas, mezcla y estado del interruptor automático.

El resumen fuera de las pestañas muestra fase, vehículos pendientes por eje, peatones
en espera/cruzando y motivo actual. **Detalles y semáforos**, **Sensores** y
**Demostraciones y pruebas** son desplegables independientes. Las demostraciones son
casos técnicos, separados de los perfiles: al cargarlas se borra el mundo, reinicia
el tiempo y se deja detenido. Una advertencia visible explica ese efecto. Cada caso
define sus tasas desde cero, mezcla, tipo y generación habilitada, de modo que no
hereda la configuración de la demostración anterior.

![Controles generales y tráfico automático](docs/arrival-controls.png)

![Formulario manual en ventana reducida](docs/arrival-controls-small.png)

Validación: pruebas de pestañas sin efectos, perfiles durante ejecución, campos y tasas,
automático desactivado, solicitudes mixtas y múltiples, capacidad insuficiente,
conservación de tipo en pendientes, pausa/reinicio y placas. Se ejecutó la ventana con
Qt nativo `windows`, temporizador, cambio de perfil, apagado automático, incorporación
manual y reinicio programáticos. Las capturas de 1500×1000 y 800×600 se revisaron
visualmente. En la ventana pequeña se desplazan los formularios y los diagnósticos,
mientras la barra general permanece visible; no se afirma una prueba humana continua.


## Centro de monitoreo y laboratorio de visión

El botón **Centro de monitoreo**, en la barra general, abre una ventana independiente
sin detener el cruce. En **Percepción simulada** aparecen cuatro imágenes del plano,
una por acceso, con cobertura, carriles, línea/sentido de conteo, estado, antigüedad,
recuadros, tipo, movimiento e ID. **Ampliar** abre una vista mayor. Seleccionar un
recuadro muestra primera/última observación, estado y trayectoria. El plano y su
selección conservan los datos del escenario separados de los observados.

La ruta real de imágenes es opcional. Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,vision]"
.\.venv\Scripts\python.exe -m sigma_vial
```

- **Video de demostración** reproduce el pequeño extracto incluido y ejecuta YOLOX
  sobre sus píxeles. También se puede **Abrir video local**. No se envía ese video a
  servicios externos y no se descarga nada al arrancar la aplicación.
- **Captura del simulador · prueba de píxeles** envía imágenes de la vista Norte al
  mismo detector. Los dos modelos evaluados fallaron en los dibujos actuales; esta
  opción es experimental y no reemplaza a la percepción simulada del controlador.
- Los otros tres recuadros indican que no tienen fuente asignada en el laboratorio
  de un video, para evitar representar una única grabación como cuatro cámaras.
- Línea de conteo y sentido son configurables. La velocidad es **px/s**, nunca km/h;
  la cola es un conteo de vehículos con velocidad estimada ≤ 3 px/s, no metros.
  No se calcula velocidad al primer avistamiento; se confirma con otra observación.
- Solo se exponen las categorías del modelo: automóvil, motocicleta, bus y camión.
  No se deducen marca/modelo ni se muestran confianzas inventadas. Placas: **Sin
  lectura** en el laboratorio YOLOX: este detector no localiza ni lee placas.
  El modo de identificación separado incorpora OCR sobre recortes explícitos.
  La lectura del escenario conserva su etiqueta **Lectura simulada** y no completa videos.

`ImageSource`/`ImageFrame` permiten incorporar posteriormente una fuente externa.
El detector y `ImageTracker` reciben exclusivamente imágenes/tiempos y calibración;
no consultan entidades del simulador. `traffic_from_tracks` convierte sus resultados
al contrato `TrafficSummary` existente, separando cola, ocupación, demanda y paso
histórico. El laboratorio utiliza ese resumen para mostrar métricas, pero **no
conecta la grabación al control del cruce**. No se implementa reproducción de demanda
en esta etapa: los vehículos filmados no reaccionan a nuestros semáforos. El
control automático existente sigue usando sus cámaras simuladas y las protecciones
del mundo; no se altera la política de respaldo por ausencia de observaciones.

Las imágenes se procesan fuera del hilo gráfico: un trabajador, un fotograma en curso
y sin cola creciente. Se saltan solicitudes cuando está ocupado. Fin de video
finaliza detecciones activas y se identifica como ausencia de imagen. Los dibujos del
cruce se capturan en el hilo de Qt, pero la inferencia y decodificación de video se
realizan en el trabajador. No se conectó hardware ni se entrenó un modelo.

La comparación visual, errores, límites y tiempos están en
[`docs/vision-evaluation/REPORT.md`](docs/vision-evaluation/REPORT.md). Para repetirla:

```powershell
.\.venv\Scripts\python.exe tools/evaluate_vision.py
```

YOLOX localizó las cinco apariciones del automóvil en la pequeña muestra real;
NanoDet una. Ambos omitieron los dos automóviles dibujados. Esto no demuestra precisión
general. Modelos, código y pesos: Apache-2.0 de OpenCV Zoo; extracto de video:
CC BY 4.0 de Intel IoT DevKit/sample-videos, con crédito y cambios documentados en
[`assets/vision/CREDITS.md`](assets/vision/CREDITS.md). La ruta fue comprobada con
Python 3.14, OpenCV headless 5.1.0.95 y NumPy 2.5.5 en Windows/CPU; no requiere GPU.
OpenCV 5 puede emitir un aviso sobre `setPreferableTarget`; las inferencias evaluadas
terminaron correctamente en CPU. Los pesos se ubican en `assets/vision` desde la raíz
fuente; una instalación redistribuible necesitará empaquetar esos recursos o seleccionar
el archivo ONNX compatible con YOLOX mediante el botón del centro de monitoreo.

![Cuatro cámaras de percepción simulada](docs/monitoring-simulated.png)

![Detección del modelo sobre video local](docs/monitoring-video.png)

El fotograma de video dentro de la última captura deriva del clip CC BY 4.0 citado;
se distribuye con esa licencia y atribución. Las pruebas de seguimiento y la revisión
de capturas complementan la evaluación anotada; no sustituyen una validación de
precisión con cámaras representativas, ni una prueba humana continua de operación.

### Monitoreo: sesiones y retención

Cada cambio de seguimiento, modo o sesión invalida los trabajos anteriores mediante una generación. Un resultado pendiente nunca restaura el reloj de la sesión anterior. Las ventanas se destruyen al cerrarlas; los puntos por trayectoria se limitan a 128 y los seguimientos sin observaciones caducan a los 10 segundos. El seguidor por píxeles mantiene como máximo 512 pistas/detecciones por imagen (prioriza detecciones de mayor confianza; los contadores acumulados se mantienen). Los mapas de cámaras simuladas retienen únicamente vehículos presentes; el contador acumulado se conserva. El registro de placas usadas es independiente y no se poda con los historiales.

### Registro persistente de vehículos ficticios

La aplicación registra cada incorporación (manual, automática o demostración) en SQLite antes de mostrarla. Placa PRIMARY KEY/UNIQUE, tipo, marca y modelo del catálogo ficticio, color hexadecimal del dibujo y dimensiones en unidades simuladas. Las colisiones entre sesiones se resuelven generando otra placa e intentando la inserción atómica; reiniciar no borra filas. Ubicación Windows: `%LOCALAPPDATA%/SIGMA SOFTWARE SOLUTIONS/SIGMA VIAL/vehicles.sqlite3`; `SIGMA_VIAL_REGISTRY` permite elegir otra ruta (las pruebas siempre usan archivos temporales). No es un registro oficial. El motor sin adaptador SQLite conserva su modo determinista en memoria.

### Cámara trasera sintética

El renderizador `rear_camera` crea una imagen RGB frontal al plano trasero del vehículo. La escala y posición dependen de su avance, con una placa amarilla de al menos 200 × 45 píxeles en cobertura. La imagen se etiqueta sintética: el renderizador usa la placa para dibujarla, nunca para reconocerla. El recorte sale de la geometría conocida, no de YOLOX ni de un localizador aprendido. Sin vehículo produce una imagen vacía de vehículos y ningún recorte. Es una proyección simplificada, no una cámara fotorealista ni una recuperación desde la vista cenital.

### OCR local independiente (Tesseract)

Instalar en Windows: `winget install --id UB-Mannheim.TesseractOCR --exact --silent --accept-package-agreements --accept-source-agreements`. Versión evaluada 5.4.0.20240606 (instalador verificado por winget SHA256 `c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9`). El ejecutable externo evita ABI de Python; probado en Python 3.14.7 / Windows. Se descubre en PATH, Program Files o con `SIGMA_VIAL_TESSERACT`. Sin instalación el monitoreo informa indisponibilidad; los semáforos no dependen del OCR.

Motor [Tesseract](https://github.com/tesseract-ocr/tesseract) y [modelos eng](https://github.com/tesseract-ocr/tessdata) Apache-2.0; documentación y licencia oficial en sus repositorios. Modelo eng instalado SHA256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`; no se redistribuyen ejecutables/DLL/modelos en Git. El paquete Windows contiene bibliotecas con sus propios avisos: conservar los de la instalación.

`TesseractPlateReader.read(png, timestamp)` solo recibe bytes y tiempo (configuración: ejecutable, tessdata, confianza y timeout). Usa LSTM eng, PSM 7, alfabeto alfanumérico y acepta únicamente formatos colombianos a partir de confianza 40. No sustituye caracteres ambiguos, consulta catálogo ni accede a placas del motor. Sin imagen: “Sin lectura”; texto inválido o baja confianza: “No legible”. La confirmación exige tres observaciones consecutivas iguales con tiempos distintos; se invalida con lectura diferente o fallida y caduca tras 10 s. YOLOX sigue siendo detector de vehículos, sin OCR.

Evaluación reproducible: `python tools/evaluate_ocr.py`; imágenes y resultados en `docs/ocr-evaluation`. Motor real con el renderizador actual: 15/16 recortes con placa exactos; un rechazo de NSD900 a posición 230 (texto bruto NSD9080, confianza 26,77), más 2/2 negativos sin placa aceptada. Son ocho textos sintéticos del catálogo de tipos en dos posiciones, no dieciséis placas independientes ni una medición con cámaras reales. Los fallos quedan publicados; no se corrigen usando el texto esperado. La suite separa la prueba real (se omite explícitamente si falta Tesseract) de pruebas de consenso con dobles.

### Identificación por texto confirmado

`IdentificationSession` recibe cámara, ID de seguimiento opaco y lectura OCR. Solo después de tres observaciones consecutivas consulta SQLite mediante igualdad exacta de placa (sin búsqueda por ID, modelo o marca ni correcciones). Una coincidencia distingue “Placa leída por OCR” de “Ficha recuperada del registro”; un texto válido desconocido produce “Placa leída, vehículo no registrado”. Sin lectura no hay consulta ni ficha actual. Las lecturas son hipótesis, no una garantía de identidad: tres errores iguales también podrían confirmar una placa incorrecta.

Eventos acotados a 200, caché de consultas a 512 / 60 s; el mismo seguimiento y placa no repite evento ni consulta por fotograma dentro de ese intervalo. La identidad de seguimiento incluye cámara; reiniciar la sesión limpia evidencia y eventos, nunca el registro persistente.

### Demostración visible de identificación

1. Abrir **Centro de monitoreo**, seleccionar **Identificación · cámara trasera sintética / recorte OCR**.
2. Elegir acceso y añadir vehículos desde el formulario manual, o activar llegadas automáticas.
3. La cámara sigue un vehículo en cobertura 0–270 unidades, manteniéndolo hasta salir; después pasa al siguiente. Vista trasera sintética y recorte geométrico se muestran juntos. La cámara emplea un reloj de observación independiente del reloj del mundo, por lo que también lee vehículos detenidos o con simulación pausada.
4. Consultar seguimiento, cámara, tiempo, texto provisional, confianza del motor, confirmación, ficha y evento. La ficha corresponde exclusivamente al texto confirmado: nunca a la selección interna del plano. Cambiar vehículo limpia la ficha visible hasta obtener una lectura del nuevo seguimiento.
5. **Abrir recorte de placa (imagen)** permite procesar una imagen independiente: toda la imagen se considera recorte aportado por el usuario, sin localización automática ni ficha interna asociada. **Volver a cámara sintética** restaura la fuente renderizada. Una imagen importada fija se observa varias veces; esto comprueba consistencia del motor, no evidencia visual independiente de varios fotogramas reales.

Hay un único trabajo OCR en vuelo, con timeout de 4 s y generación de sesión; reinicio, cambio de fuente o cámara invalidan resultados pendientes. La cola de trabajos no crece. El trabajador recibe exclusivamente PNG y tiempo. Los errores del lector muestran “Sin lectura” y no impiden al controlador servir tráfico. En el modo YOLOX de video se conserva “Sin lectura”: conectar detección/localización de placas en video real requiere calibración y un localizador adicional; la demostración actual admite recortes proporcionados, no reconocimiento integral de una cámara física.

Validación de esta etapa: 161 pruebas, incluyendo motor, interfaz, registro en procesos separados, OCR real por píxeles, textos diferentes a la placa interna, negativos, consultas exactas, deduplicación, fallo de trabajador y resultado t=50 rechazado tras reinicio. Ruff y formato se verifican aparte. Ejecución nativa programada en backend `windows`, sin offscreen: apertura/cierre, lectura y ficha reales por Tesseract, inicio/pausa, velocidad 2×, movimiento, zoom repetido, reinicio durante monitoreo y segunda identificación desde otro acceso. Revisión de capturas en tamaño 1150×850 y reducido 850×650. Un temporizador del motor y una conexión timeout; el monitor usa su propio temporizador. No equivale a observación humana continua ni a validación con cámaras físicas.

![Cámara sintética, OCR real y ficha recuperada por placa](docs/identification-native.png)

## Tablero visual SIGMA actual

Composición basada en la referencia de intersección inteligente: cabecera azul oscuro,
barra fija de ejecución y reloj, tarjeta principal a la izquierda (2/3) y dos tarjetas
a la derecha (1/3). La primera contiene **Automático** y **Agregar**; la segunda muestra
la cámara elegida, procedencia, recorte, texto leído, estado y ficha. Los estilos,
componentes ligeros y tarjeta de cámara están separados en `dashboard_style.py`,
`dashboard_components.py` y `camera_card.py`.

- **Iniciar / Pausar / Continuar**, **Reiniciar**, velocidad y reloj simulado permanecen
  arriba. El indicador de la cabecera cambia con el estado real. El reloj es HH:MM:SS.
- El plano conserva **−**, **Restablecer** y **+**. Abajo aparecen las demandas del
  controlador por eje, peatones esperando y su motivo. “Próximo turno” solo aparece
  cuando existe una fase solicitada; en caso contrario se muestra la fase actual.
- **Automático** conserva interruptor y perfil. **Ajustes avanzados** despliega las
  tasas por acceso, peatones/min y mezcla de tipos. **Agregar** conserva acceso,
  tipo, cantidad y cruces peatonales. Las pestañas cambian únicamente el formulario.
- **Herramientas: detalles, sensores y pruebas** permite acceder a las métricas,
  cobertura opcional, lecturas de sensores y demostraciones técnicas existentes.
- En la cámara principal se elige Norte, Sur, Oriente u Occidente. El recuadro turquesa
  del plano acompaña al vehículo seguido; el recuadro de placa es geométrico. La imagen
  trasera varía con posición, tipo y color. **Abrir recorte…** procesa una imagen propia;
  **Cámara sintética** restaura la fuente renderizada. El selector se deshabilita mientras
  se procesa un recorte importado, que no representa una cámara del mundo.
- Solo una lectura confirmada recibe estado verde. La ficha y el nombre de color
  proceden del registro consultado por OCR. Las placas no legibles permanecen sin ficha.
  **Centro de monitoreo** conserva el laboratorio completo y sus fuentes de video;
  la tarjeta principal no simula una cámara física que no existe.
- Bajo 1100 píxeles las tarjetas se apilan y el cuerpo permite desplazamiento vertical.
  La cabecera y los controles generales permanecen fijos; formularios y herramientas
  admiten su propio desplazamiento sin barra horizontal ni texto reducido.

La decoración de asfalto, aceras, jardineras y árboles se pinta una vez por escena.
Vehículos y peatones mantienen objetos gráficos persistentes. El monitoreo embebido
reutiliza el lector, sus trabajos de una sola entrada, generaciones y consultas existentes;
es un componente vivo de la pantalla principal, no una ventana cerrada retenida. Se
cierra con la ventana principal y no procesa mientras esta no se muestra.

Diferencias concretas respecto a la referencia: escena y vehículos vectoriales
estilizados, cámara trasera simplificada y modelos ficticios del catálogo; no se
redistribuyen fotografías de Chevrolet ni se inventa una lectura ABC123. No había un
archivo de logo en el proyecto: el símbolo SIGMA se dibuja localmente con vectores.
Se conserva la escala física existente de las carrocerías, los cuatro semáforos,
dos carriles de entrada y dos de salida por acceso y la circulación por la derecha,
aunque la ilustración de referencia no respete exactamente esas proporciones.
No se incorporan recursos externos ni nuevas licencias/dependencias gráficas.

Validación visual: capturas nativas revisadas a 1580×980, ventana maximizada y 800×600;
ejecución, pausa, continuación, zoom repetido, cambio de pestañas, incorporación múltiple
(con falta de capacidad), OCR real y reinicio comprobados con código de salida 0.
Una sola conexión del temporizador del motor. Las pruebas del tablero verifican
proporción 2:1, ausencia de desplazamiento en ventana grande, adaptación vertical,
controles generales visibles, demandas reales, ausencia de ficha inventada y
conservación de objetos estáticos. Esto no es una validación de cámaras físicas.

[Captura maximizada](docs/dashboard-maximized.png) ·
[Ventana reducida](docs/dashboard-small.png) ·
[Formulario en ventana reducida](docs/dashboard-small-manual.png)

## Presentación con el ESP32 por Wi-Fi

1. Alimenta por USB la placa con el firmware `presentacion` y conecta Windows a **SIGMA-VIAL-Prueba-cf98**.
   Si aparece **Sin conexión**, pulsa **Abrir Wi-Fi de Windows** en el panel y selecciona esa red. También puedes usar el perfil guardado con `netsh wlan connect name="SIGMA-VIAL-Prueba-cf98"`. Mantén esa red durante la demostración aunque Windows indique «Sin Internet». Una vez solicitado el enlace, el panel reintenta automáticamente.
2. Desde la raíz del repositorio ejecuta `.\.venv\Scripts\python.exe -m sigma_vial`.
3. Pulsa **Conectar al ESP32** en la cabecera y espera **ESP32 conectado**. El primer intento usa `192.168.4.1:5050`. Para otra IP, usa **Cambiar dirección** en **Procesador ESP32**. El panel recuerda la última IP que respondió PONG.
4. Pulsa **Iniciar** y agrega vehículos desde **Agregar**. Al llegar a la zona de detección y detenerse, aparecerán en la siguiente muestra automática. El panel muestra el eje de mayor cola, los cuatro conteos enviados y la respuesta de la placa.

[Guía para reproducir ambas colas](firmware/esp32-procesador/README.md) · [Captura con tráfico](docs/esp32-trafico-eo.png)

## Central de Monitoreo de cámaras Wi-Fi

1. En Windows, abre PowerShell en la raíz del repositorio. La central reutiliza OpenCV del extra de visión. Para instalarlo en el entorno del proyecto ejecuta `.\.venv\Scripts\python.exe -m pip install -e ".[vision]"`. Abre SIGMA VIAL con `.\.venv\Scripts\python.exe -m sigma_vial`.
2. Alimenta la cámara y conecta el PC a una red desde la que puedas abrir su transmisión HTTP. Pulsa **Central de Monitoreo** en la ventana principal. Los paneles superiores son **Norte** y **Sur**. Los inferiores son **Oriente** y **Occidente**.
3. En el acceso elegido pulsa **Configurar cámara**. Confirma la sugerencia `http://172.20.10.2/stream` o escribe la URL de video HTTP(S) de tu cámara. **Aceptar** guarda la asignación en este PC e inicia la conexión. **En vivo** aparece al decodificar video. Si la cámara pierde señal, se retira la imagen y aparece **Reintentar**.
4. Repite el paso anterior en cada acceso cuando tengas las otras cámaras. En **Opciones** puedes editar la URL, mover la cámara a un acceso libre o quitar la asignación. **Desconectar** conserva la URL. Al volver a abrir la central, pulsa **Conectar** en los accesos que quieras ver.
5. Usa **Ampliar** y **Volver a la cuadrícula** para cambiar de vista. Cerrar la central detiene las transmisiones. Desde la misma ventana puedes abrir **Monitoreo simulado y laboratorio de visión**.

Las cámaras HTTP permiten ver video. Para ver cámaras y procesador por Wi-Fi al mismo tiempo, el PC necesita una ruta de red hacia cada dispositivo.

En este PC, al pulsar **Conectar al ESP32** para la IP de presentación, si falla TCP desde **Estudiantes-CEIPA**, SIGMA VIAL solicita a Windows conectarse al perfil guardado **SIGMA-VIAL-Prueba-cf98**. El panel confirma la conexión al recibir PONG. En la red del iPhone mantiene la conexión de las cámaras; para pasar al Wi-Fi del procesador usa **Abrir Wi-Fi de Windows**.

## Presentación por USB directo

Conecta el procesador y la cámara al PC con cables USB de datos y cierra los monitores serie. En **Cambiar dirección**, escribe el puerto del procesador (COM3 en este PC). En **Central de Monitoreo → Norte → Opciones → Editar URL**, escribe el puerto de la cámara (COM4). En las sesiones siguientes, pulsa **Conectar al ESP32**, inicia la simulación y pulsa **Conectar** en Norte. La aplicación conserva los puertos elegidos. [Firmware y protocolo de la cámara USB](firmware/esp32-camara/README.md).

### Medir la fila de Norte con la cámara

1. Con la simulación detenida y el acceso vacío, apunta la cámara a los dos carriles de Norte que llegan a la cebra. Usa el zoom para que se distingan los vehículos y el espacio entre ellos. Deja la cámara fija.
2. En **Central de Monitoreo → Norte**, espera **En vivo** y activa **Medir la fila con esta cámara**. En la intersección aparecen dos cuadrados blancos y negros. Encuádralos completos y deja quieta la cámara. OpenCV localiza los dos carriles y las guías verdes aparecen cuando el encuadre se estabiliza. El sistema espera a que Norte esté vacío para tomar la referencia. Si mueves la cámara, busca las marcas de nuevo. También puedes usar **Marcar los dos carriles**, señalar los extremos de cada carril y pulsar **Calibrar con los carriles vacíos**.
3. Pulsa **Iniciar** y agrega vehículos. Puedes minimizar la central. La cámara estima cuántos vehículos permanecen detenidos sobre las guías. SIGMA VIAL combina esa lectura con las filas simuladas de Sur, Oriente y Occidente, y manda una muestra por segundo al procesador.
4. El panel identifica la fuente de la muestra. En este modo la respuesta del ESP32 da prioridad al eje con mayor fila. El simulador aplica el verde mínimo, la prioridad peatonal, los límites de espera, el amarillo y el despeje. Con empate, vía vacía, lectura caducada o placa desconectada, decide el controlador habitual. Desmarca la casilla para volver al modo simulado.

La casilla **Identificar vehículos en el video** activa YOLOX en el PC. Dibuja recuadros alrededor de los automóviles, motos, buses y camiones que reconoce en cada fotograma, incluso si están en movimiento. El modelo se incluye en el repositorio y funciona sin Internet. Los recuadros ayudan a revisar el video. El dato enviado al procesador sigue siendo la fila detenida que mide la placa con cámara.

La cámara USB con PSRAM entrega 640 × 480 píxeles. La medida de fila aprovecha la longitud en píxeles de cada guía. Para contar dos vehículos, la cámara necesita ver la separación entre ellos. La luz, los reflejos, el movimiento de la cámara y el tamaño de los vehículos en pantalla influyen en la precisión. YOLOX puede pasar por alto los vehículos dibujados en la simulación.
