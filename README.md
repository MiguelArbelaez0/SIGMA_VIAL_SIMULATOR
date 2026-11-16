# SIGMA VIAL

Aplicación de escritorio de **SIGMA SOFTWARE SOLUTIONS** para una futura simulación
vial virtual. Estado actual: entorno de desarrollo y ventana inicial ejecutable.
Todavía no se implementa la simulación.

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

Las pruebas comprueban textos, construcción, apertura, cambio de tamaño y cierre.
Las importaciones se prueban en procesos independientes con tiempo límite, sin
crear una QApplication. pytest-qt administra su propia aplicación y no deja un
bucle gráfico bloqueado. En equipos sin pantalla se puede establecer temporalmente
`$env:QT_QPA_PLATFORM = 'offscreen'`; eso no constituye verificación visual.
Retirar esa variable con `Remove-Item Env:QT_QPA_PLATFORM` antes de abrir la ventana.

## Organización

- `src/sigma_vial/domain/`: futuras entidades y reglas puras, sin PySide6.
- `src/sigma_vial/application/`: futura coordinación de casos de uso.
- `src/sigma_vial/presentation/`: ventana y componentes PySide6.
- `src/sigma_vial/infrastructure/`: futuros adaptadores externos.
- `src/sigma_vial/bootstrap.py`: composición y ciclo de vida de QApplication.
- `src/sigma_vial/__main__.py`: ejecución mediante `python -m sigma_vial`.
- `tests/`: pruebas automáticas y contratos de importación.

Los paquetes futuros se documentan sin clases o servicios anticipados. La ventana
no contiene reglas de tráfico y los módulos no arrancan la interfaz al importarse.

## Alcance previsto y pendientes

Intersección ficticia en “+” con accesos norte, sur, oriente y occidente; cada acceso
tendrá un semáforo vehicular, dos carriles de entrada y dos de salida. Se prevén
vehículos y peatones virtuales, decisiones centralizadas por demanda, espera y
ocupación, transiciones con amarillo y despeje, controles de inicio, pausa,
reinicio y demanda, y visualización de filas, esperas y fase actual.

Supuestos iniciales: solo movimientos rectos; norte-sur comparte fase y
oriente-occidente comparte otra. **Los peatones tendrán una fase exclusiva**.
Todo lo anterior está pendiente. La etapa actual solo muestra el título, la empresa
y el mensaje de preparación, sin botones ficticios ni resultados inventados.
No utiliza cámaras, IA, nube, bases de datos ni hardware. ESP32 y semáforos físicos
se considerarán en una etapa posterior.

## Ramas y próxima etapa

Esta preparación se realiza en `setup/development-environment`, para revisión sin
commit, push ni merge automáticos. El repositorio inicial no tenía commits;
`main` no tendrá una referencia consolidada hasta el primer commit acordado.
El remoto `origin` ya existía y no se ha modificado ni sincronizado.

Próxima etapa: interfaz de la intersección en `feature/intersection-ui`.
Después: `feature/traffic-simulation`, `feature/adaptive-control`,
`feature/simulation-controls` y `feature/hardware-integration`.
Estas ramas no se crean ahora. Cada una deberá partir de una base que incluya
los cambios anteriores revisados e integrados.
