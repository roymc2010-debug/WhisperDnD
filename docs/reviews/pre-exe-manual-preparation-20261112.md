# Preparación de prueba manual previa al EXE

Fecha: 12 de noviembre de 2026. Alcance: dejar un punto de entrada comprobable y un perfil separado para revisión manual; no compilar ni distribuir.

## Resultado

Se añadieron `desktop.py`, `src/desktop_app.py`, `probar_antes_del_exe.bat` y `comprobar_antes_del_exe.bat`, con la [guía manual](../prueba-manual-antes-del-exe.md). La entrada utiliza el mismo resolvedor que el modo empaquetado, mediante `WHISPER_DESKTOP_MODE=1` y una raíz absoluta explícita de datos. No simula `sys.frozen` ni altera el intérprete. En modo manual, el perfil predeterminado es `%LOCALAPPDATA%/WhisperDnD-Pruebas` y el origen es `http://localhost:8082`. El futuro modo de escritorio sin `--manual` utilizaría el perfil WhisperDnD y puerto 8080; todavía no es una build certificada.

El entorno de ese proceso no hereda claves/API tokens de desarrollo, overrides de almacenamiento o URL de Render, y los consumidores de dotenv omiten la carga del checkout en modo escritorio. No se migran datos ni se importan credenciales personales. Las preferencias y tokens del navegador habitual pertenecen a otro origen. Se conserva el comportamiento de desarrollo sin activar este modo.

## Cierre de rutas y recuperación de contratos

- Grabaciones, archivos auxiliares, timeline y copias de entrada del grabador usan el resolvedor. Se mantiene la nomenclatura y las operaciones existentes.
- La segmentación/limpieza de Groq utiliza la entrada del perfil en escritorio. El legado temporal de Linux se mantiene en desarrollo. Solo se limpian fragmentos de la ejecución correspondiente.
- El token de Discord se resuelve por perfil al acceder, incluyendo el reset de autorización. No se copia el token de desarrollo.
- El default del descargador de YouTube y los informes locales de transcripción respetan el perfil. El directorio explícito del consumidor sigue teniendo prioridad.
- Los fallbacks de lectura/escritura/borrado de exportaciones y notas académicas quedan restringidos al perfil en escritorio. Se añadieron regresiones que antes reproducían la lectura de una nota ajena y el borrado de un TXT del directorio de desarrollo. Los archivos de esas regresiones son sintéticos.
- El historial académico de escritorio queda en exportaciones, alineado con consolidación, importación y sincronización Drive. Se probó con el proveedor simulado; no se sincronizó con una cuenta real.
- Drive y caché Whisper reconocen el modo manual además de la detección de ejecutable. Las fuentes heredadas de tokens de contenedor quedan deshabilitadas en ambos casos. El reporte de soporte identifica el modo escritorio.

## Arranque

Un bloqueo de archivo del sistema operativo distingue propiedad de instancia de la mera existencia de un archivo. El proceso reserva el puerto IPv4 loopback antes de importar el backend. El segundo inicio reutiliza la instancia solo si coincide la identidad del perfil con la respuesta de salud WhisperDnD. No se elige otro puerto silenciosamente ni se cierra un proceso ajeno.

Se añaden identidad y versión a salud únicamente cuando la entrada de escritorio ha inicializado esa instancia. Los logs de arranque usan el perfil; stdout/stderr ausentes se proporcionan antes de configurar Uvicorn para preparar el caso sin consola. No se invoca el lanzador histórico que requiere `.venv`; el BAT manual sí usa el entorno de desarrollo existente.

Cerrar una pestaña no mata el backend. El cierre Ctrl+C comprueba grabación, tareas en progreso, peticiones no GET y trabajos Drive en segundo plano antes de aceptar la salida. El cierre forzado de Windows/apagado no queda protegido. No se implementó actualizador, bandeja del sistema ni un ciclo de instalación/desinstalación.

## Verificación y límites

Pruebas nuevas se ejecutaron primero con el comportamiento faltante en fallo, y después aprobadas. Durante la construcción de fixtures se corrigieron un doble de hilo que nunca terminaba y una expectativa de timeline en modo clase (los timelines corresponden a rol). No se alteró el grabador para satisfacer esos errores de fixture.

La suite backend offline completa dio **688 aprobadas, 2 omitidas y 46 subpruebas aprobadas**, con cinco avisos de dependencias, en 33,60 s. La suite frontend dio **115 aprobadas y 2 omitidas**, sin fallos. No hubo cambios de interfaz en este bloque.

`scripts/verify_desktop_smoke.py` arrancó el backend real desde otro directorio de trabajo y un perfil temporal con acentos, sin navegador y con restauración Drive desactivada. Comprobó salud con identidad, HTML actual, reporte de soporte, lista vacía de campañas y segunda apertura sin duplicar instancia. Cerró únicamente su proceso después de esas consultas de lectura. La limpieza temporal necesitó reintentos acotados por una liberación transitoria del archivo de bloqueo en Windows; la última ejecución terminó con código cero y perfil temporal eliminado.

`desktop.py --manual --check` detectó las dependencias consultadas, FFmpeg, ffprobe y los recursos estáticos principales en este equipo. No valida ABI de todas las bibliotecas nativas ni compara con un entorno de build bloqueado; no sustituye una prueba en máquina limpia.

No se abrió el perfil manual definitivo ni se reinició la app habitual, inició una grabación de sesión, autorizó Google/Discord, utilizó Groq/Gemini o descargó modelos. No se instalaron dependencias ni se compiló un EXE. Captura real, OAuth, protección completa de tokens, receta de empaquetado y licencias quedan pendientes antes de distribuir; están diferenciados de la disponibilidad de la prueba manual.

Los hashes de los cinco archivos privados existentes incluidos en la referencia (credenciales, tokens, `.env` y token Discord) y los siete JSON directamente en `data/campaigns` se conservaron: doce archivos comprobados. No se presenta esa muestra como inventario recursivo. Se guardaron copias de referencia de los módulos afectados fuera del checkout y se revisó la lista de cambios contra ellas, además del estado Git acumulado. `main.py` y el lanzador habitual no se modificaron en este paso. La guarda de dotenv de Gemini se contrastó con la lectura inicial del archivo; su copia de referencia se tomó después de ese ajuste.

`git diff --check` sobre los módulos de producción afectados terminó sin errores; solo avisó de conversión futura de finales de línea. Los archivos nuevos también se comprobaron por sintaxis/espacios finales. Los numerosos cambios locales previos se conservaron sin commit, push, reset, cambio de rama o mezcla de copias.
