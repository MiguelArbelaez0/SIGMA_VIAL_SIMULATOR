# Validación de la interfaz de la intersección

Fecha: 16 de noviembre de 2026.

- Proyecto: `C:\Users\USUARIO\Desktop\DESARROLLO\05_PYTHON\SIGMA_VIAL_SIMULATOR`.
- Base verificada: `5806bd6`, preparación del entorno en `setup/development-environment`.
- Rama de esta entrega: `feature/intersection-ui`.
- Entorno conservado: Python 3.14.7 x64, PySide6/Qt 6.12.0, pytest 9.2.0,
  pytest-qt 4.5.0 y Ruff 0.17.5. Sin actualización de dependencias.

## Comprobaciones automáticas

Ejecutadas con el Python de `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Resultado: 25 pruebas aprobadas, Ruff y formato correctos, sin dependencias rotas.
Las pruebas anteriores de apertura/cierre, arranque e importaciones se mantienen;
se sustituyó la expectativa del mensaje inicial por el estado actual de la interfaz.

Se comprueban cuatro accesos, dos entradas y dos salidas por acceso, cuatro
semáforos en rojo, colores realmente pintados para cada estado, flechas rectas
por la derecha en los cuatro brazos, posición de la detención antes del paso,
ausencia de semáforos y rótulos sobre las calzadas, zoom y restablecimiento, y
encuadre de la escena completa al reducir la ventana. Las importaciones se
ejecutan en procesos aislados sin crear QApplication; el dominio no carga Qt.

## Revisión visual real

Se abrió la aplicación mediante `.\.venv\Scripts\python.exe -m sigma_vial`
en el escritorio Windows. Se revisaron los sentidos de las flechas, los cuatro
pasos y líneas de detención, los semáforos correspondientes a cada entrada,
el centro libre y la legibilidad. Se corrigieron rótulos que invadían el extremo
de las calzadas y se aumentó el texto de los semáforos.

El botón Acercar fue comprobado en la ventana real; Alejar y Restablecer vista
se verifican además mediante clics automatizados de pytest-qt. El tamaño reducido
se revisó sobre una ventana real de 800 × 600, capturada con QWidget.grab()
después de procesar eventos, y cerrada automáticamente con salida 0.
La pantalla disponible utiliza DPR 1.0 y 96 DPI lógicos; no se certificaron
otros factores de escalado. En tamaño reducido se conserva el plano completo;
para leer detalles se usa zoom y el panel dispone de desplazamiento vertical.

- [Captura de la ventana en el escritorio](intersection-ui.png).
- [Captura de la ventana reducida](intersection-ui-compact.png).

Las capturas provienen de la interfaz PySide6 real; no son imágenes generadas
ni se utilizan para dibujar el escenario.

## Límites de la entrega

No se simula tráfico, no hay reloj ni transiciones automáticas de fases, controles
manuales de luces, algoritmos adaptativos ni conexión física. La escena mantiene
sus cuatro semáforos en rojo. El panel describe exclusivamente el escenario estático.
No se hicieron commits, push ni merge, ni se modificó `main` o la rama base.
