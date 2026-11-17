# SIGMA VIAL

Aplicación de escritorio de **SIGMA SOFTWARE SOLUTIONS** para una futura simulación
vial virtual. Estado actual: entorno de desarrollo e interfaz vectorial de la
intersección ejecutable. La simulación de tráfico todavía está pendiente.

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
También verifican que los semáforos y rótulos no invadan las calzadas.
Las importaciones se prueban en procesos independientes con tiempo límite, sin
crear una QApplication. pytest-qt administra su propia aplicación y no deja un
bucle gráfico bloqueado. En equipos sin pantalla se puede establecer temporalmente
`$env:QT_QPA_PLATFORM = 'offscreen'`; eso no constituye verificación visual.
Retirar esa variable con `Remove-Item Env:QT_QPA_PLATFORM` antes de abrir la ventana.

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

Los paquetes de aplicación e infraestructura siguen mínimos y documentados. La ventana
no contiene reglas de tráfico y los módulos no arrancan la interfaz al importarse.

## Alcance previsto y pendientes

Intersección ficticia en “+” con accesos norte, sur, oriente y occidente; cada acceso
tendrá un semáforo vehicular, dos carriles de entrada y dos de salida. Se prevén
vehículos y peatones virtuales, decisiones centralizadas por demanda, espera y
ocupación, transiciones con amarillo y despeje, controles de inicio, pausa,
reinicio y demanda, y visualización de filas, esperas y fase actual.

Supuestos iniciales: solo movimientos rectos; norte-sur comparte fase y
oriente-occidente comparte otra. **Los peatones tendrán una fase exclusiva**.
Implementado en esta etapa:

- Cruce en “+” con norte arriba, sur abajo, oriente a la derecha y occidente a la izquierda.
- Dos carriles de entrada y dos de salida por brazo (8 + 8 en total), circulación
  por la derecha, flechas rectas, separación de sentidos y líneas discontinuas.
- Aceras, cuatro pasos peatonales y detención antes del paso en cada entrada.
- Cuatro semáforos etiquetados, inicialmente rojos, fuera de las calzadas. El
  componente puede representar rojo, amarillo o verde, sin cambios automáticos
  ni controles manuales de fases. Cada uno corresponde a los dos carriles de entrada.
- Panel informativo, estado «Vista inicial · Simulación detenida» y controles
  **Acercar**, **Alejar** y **Restablecer vista**. Se puede arrastrar el plano al
  ampliar. El zoom está acotado; restablecer encuadra los cuatro brazos.
- Ajuste de escena al redimensionar, tamaño mínimo de ventana de 800 × 600 unidades
  lógicas y desplazamiento vertical del panel cuando falta espacio. Para inspeccionar
  detalles en ventanas pequeñas, usar Acercar y después Restablecer vista.
- Gráficos vectoriales locales con QGraphicsScene/QGraphicsView. La aplicación
  instalada funciona sin internet y no depende de la captura para dibujar el cruce.

Pendiente: vehículos y peatones animados, reloj de simulación, generación de demanda,
inicio/pausa/reinicio, métricas y reportes, transiciones semafóricas y control adaptativo.
No hay resultados inventados ni controles de simulación todavía inexistentes.
No utiliza cámaras, IA, nube, bases de datos ni hardware. ESP32 y semáforos físicos
se considerarán en una etapa posterior.

## Ramas y próxima etapa

La preparación del entorno está en el commit `5806bd6`
(`setup/development-environment`). Esta interfaz se desarrolla en
`feature/intersection-ui`, creada directamente desde ese commit verificado,
aunque `main` no exista. No se modifica la rama base ni se ejecutan commits, push o
merge automáticamente; los cambios se dejan para revisión.

Próxima etapa: `feature/traffic-simulation`. Después:
`feature/adaptive-control`, `feature/simulation-controls` y
`feature/hardware-integration`. Estas ramas futuras no se crean ahora. Cada una
deberá partir de una base que incluya los cambios anteriores revisados e integrados.

## Revisión de la interfaz

La captura real de la ventana se guarda en
[`docs/intersection-ui.png`](docs/intersection-ui.png).
La revisión manual y los resultados de esta entrega están documentados en
[`docs/validation-intersection-ui.md`](docs/validation-intersection-ui.md).
