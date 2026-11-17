# SIGMA VIAL

Aplicación de escritorio de **SIGMA SOFTWARE SOLUTIONS** para una futura simulación
vial virtual. Estado actual: entorno, interfaz vectorial y primera simulación virtual local ejecutable.

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
  velocidad y vista. La configuración de demanda y escenarios está plegada al inicio;
  las métricas detalladas también se pueden desplegar.
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
no representa seguridad vial certificada. Hardware ESP32 y semáforos físicos siguen
fuera de alcance.
No utiliza cámaras, IA, nube, bases de datos ni hardware. ESP32 y semáforos físicos
se considerarán en una etapa posterior.

## Ramas y próxima etapa

La preparación del entorno está en el commit `5806bd6`
(`setup/development-environment`). La interfaz se desarrolló en `feature/intersection-ui`; la simulación funcional se
desarrolla en `feature/functional-simulation`.

Siguiente etapa: integración física, cuando la simulación local quede revisada e integrada.

## Revisión de la interfaz

La captura real de la ventana se guarda en
[`docs/intersection-ui.png`](docs/intersection-ui.png).
La revisión manual y los resultados de esta entrega están documentados en
[`docs/validation-intersection-ui.md`](docs/validation-intersection-ui.md).
