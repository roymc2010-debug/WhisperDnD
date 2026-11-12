# Rutas de logs del arranque — 12 de noviembre de 2026

## Alcance

Continuación autorizada del bloque de arranque y logs de la hoja de ruta. No se inició/reinició la aplicación, se grabó una sesión, se instaló software, se modificaron credenciales/campañas ni se consumieron servicios de pago. Se conservaron los cambios locales anteriores.

## Cambios acotados

- `main.py` obtiene `log_dir` del resolvedor común. Desarrollo sigue en `outputs/server.log`; el modo empaquetado escribe en `%LOCALAPPDATA%/WhisperDnD/logs/server.log`. La rotación existente y las salidas silenciosas stdout/stderr siguen usando ese archivo. Se impide la reejecución a una `.venv` cuando `sys.frozen` indica un ejecutable empaquetado.
- `scripts/launch_desktop.py` usa el mismo directorio para redirigir stdout/stderr del servidor. Los errores de espera de arranque indican la ruta efectiva del registro. El script añade su raíz a la búsqueda de módulos antes de importar el resolvedor para que funcione cuando se ejecuta directamente desde otra carpeta.
- No se cambió la URL, el sondeo de salud, la ventana de espera, el orden servidor/disponibilidad/navegador, el host del backend, la configuración de servicios ni la carga de `.env`.

El lanzador todavía construye un comando de desarrollo con `.venv/Scripts/pythonw.exe` y `main.py`. Su ruta de logs queda preparada para empaquetado, pero no se afirma que este lanzador pueda ejecutar ya una distribución EXE sin Python. Ese flujo, la identidad de instancia y conflictos de puerto siguen siendo trabajo posterior.

## Pruebas nuevas

`tests/test_startup_logging_paths.py` ejecuta copias del punto de entrada en recursos sintéticos, sin el nombre `__main__` y sin invocar `main()`/uvicorn. Se desactiva la lectura de dotenv, se excluye la creación de credenciales desde variables y se restauran handlers, streams, hooks y filtros del proceso de pruebas.

Las pruebas comprueban:

1. Conservación de `outputs/server.log` en desarrollo y escritura de un mensaje real mediante su handler.
2. Log en el perfil empaquetado, tanto con streams normales como con stdout/stderr ausentes (simulación de pythonw).
3. Ausencia de intento de ejecutar una `.venv` sintética en modo empaquetado.
4. Fallo explícito si falta LocalAppData, sin escribir logs en los recursos del programa.
5. Log del lanzador en el perfil y apertura de ventana únicamente después de disponibilidad simulada; ante fallo, mensaje con ruta correcta y ninguna ventana.
6. Ejecución del script desde un directorio ajeno, con `PYTHONPATH` retirado. Un intérprete corto de prueba ejecuta el script copiado y simula dentro de él tanto servidor como navegador; no se inicia un servidor real.

En la primera ejecución, seis casos fallaron al detectar escrituras en recursos del programa y un control de desarrollo pasó. Tras integrar las rutas y añadir la comprobación de ejecución independiente, las ocho pruebas nuevas pasan.

## Verificación nueva

| Comprobación | Resultado |
| --- | --- |
| Logs/arranque y contrato de rutas | 25 aprobadas |
| Suite backend offline completa | 642 aprobadas, 2 omitidas, 45 subpruebas aprobadas; 30,20 s |
| Avisos de dependencias | Cinco, sin fallos |
| `git diff --check` de los dos archivos de aplicación tocados | Sin errores de whitespace; aviso de normalización de finales de línea en main.py |
| SHA-256 de 17 JSON de campaña/sesiones/entidades/respaldos registrados al inicio | Sin cambios |

Se registraron hashes de 72 archivos al comenzar para distinguir este trabajo de los cambios locales previos. Los cambios de esta tarea se limitan a los dos puntos de entrada, la prueba nueva, la hoja de ruta y este informe. No se reejecutó el frontend porque no se modificó. La suite se ejecutó con almacenamiento temporal y red bloqueada; los mensajes de Drive corresponden al bloqueo, sin transferencias.

## Siguiente bloque

Separar credenciales y tokens mediante rutas por usuario, conservando los overrides, el funcionamiento de desarrollo y los vínculos existentes. No mover ni renovar tokens reales como parte implícita de la integración. Cuotas, modelos y escritores de grabación siguen pendientes. No hay ejecutable construido ni activación de estos cambios en un servidor verificado en esta tarea.
