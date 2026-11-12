# Distribución instalable de WhisperDnD para Windows

Fecha: 12 de noviembre de 2026.

## Estado

Propuesta. El usuario autorizó continuar los planes para llegar a una aplicación instalable mediante EXE en otras computadoras. No se ha construido un ejecutable, instalado herramientas de empaquetado, migrado datos ni verificado compatibilidad en otro PC.

## Contexto comprobado

La aplicación existente combina FastAPI, interfaz web local, captura WASAPI/Discord, transcripción Groq/faster-whisper, crónicas Gemini y Drive opcional. Debe conservarse su comportamiento; no es necesario reescribir la interfaz para preparar una distribución de escritorio.

El lanzador `scripts/launch_desktop.py` depende de `.venv/Scripts/pythonw.exe` y `main.py`. `main.py` también intenta reejecutarse dentro de `.venv`, escribe logs junto al código y escucha actualmente en `0.0.0.0`. Varias rutas de campañas, modelos, tokens y salidas dependen del checkout o del directorio de trabajo. `requirements.txt` declara versiones mínimas, no una resolución reproducible. La inspección dirigida no encontró una receta PyInstaller ni un instalador.

La captura aislada comprueba `build >= 20348` en `src/transcription/discord_audio_capture.py`. No debe prometerse soporte genérico para Windows 10 a partir de ese comentario: se debe contrastar el build real y probar cada plataforma. La primera plataforma propuesta es Windows 11 x64.

## Opciones consideradas

| Opción | Beneficio | Coste o límite |
| --- | --- | --- |
| Distribuir código y exigir Python | Mantiene el flujo de desarrollo | No cumple el objetivo de instalar sin preparación técnica |
| PyInstaller en carpeta + instalador EXE | Conserva arquitectura; permite inspeccionar dependencias; entrega un único instalador al usuario | Exige adaptar arranque/rutas y validar DLL, datos e importaciones dinámicas |
| PyInstaller de archivo único | Un solo ejecutable de aplicación | Extrae dependencias temporales al iniciar; añade otra variable al diagnóstico de arranque |
| Reescribir o añadir un contenedor de escritorio distinto | Podría controlar más detalles de ventana | Introduce dependencias y trabajo que no son necesarios para probar primero la distribución actual |

## Propuesta

1. Mantener FastAPI y la SPA. Empaquetar backend/intérprete y assets con PyInstaller en modo de carpeta para la primera prueba de distribución.
2. Tras validar esa carpeta en un entorno limpio, preparar un instalador con Inno Setup, preferentemente por usuario y sin elevación. El entregable será un `Setup.exe`; la carpeta interna de dependencias no será una tarea del usuario.
3. Separar recursos del programa de almacenamiento persistente por usuario antes de empaquetar. Proponer `%LOCALAPPDATA%/WhisperDnD/` como raíz de datos de la instalación, con subcarpetas para campañas, grabaciones, exportaciones, logs, configuración y modelos. Los recursos estáticos se leerán desde la distribución.
4. Conservar el comportamiento actual del checkout durante el desarrollo y respetar los overrides explícitos de pruebas. No copiar, mover ni reconstruir datos históricos automáticamente. Una importación desde otra copia será un flujo explícito, con respaldo y validación de esquema.
5. Preparar un arranque empaquetado independiente de `.venv`. Establecer identidad/versionado de instancia y resolver conflictos de puerto sin conectarse por error a otra copia. Mantener estable el origen del navegador para los datos que aún dependan de él; un puerto alternativo debe considerar esa dependencia, no elegirse sin más.
6. Para el perfil instalado de uso local, proponer loopback como predeterminado. El acceso LAN/túnel, existente en desarrollo, deberá conservar una selección explícita y pruebas propias; no se deshabilita ahora ni se cambia de forma silenciosa.
7. Cada usuario configura sus claves y vínculos. Nunca distribuir `.env`, tokens, campañas, grabaciones ni datos del desarrollador. La configuración OAuth de Drive distribuible se determinará aparte de los tokens personales.
8. Incluir o resolver FFmpeg/ffprobe y bibliotecas nativas de forma trazable, con versiones, hashes y avisos correspondientes. Definir descarga de modelos locales opcional y comprobable, sin ejecutarla durante esta planificación.
9. Actualizar y desinstalar sin eliminar campañas ni grabaciones por defecto. No cerrar una captura o transferencia activa para reemplazar archivos.

## Consecuencias

El instalador no sustituye las pruebas funcionales: captura real coordinada, generación/revisión, recuperación y actualización deben tener evidencia por separado. El primer candidato puede seguir necesitando internet y claves para Groq/Gemini; la transcripción local no convierte automáticamente la generación de crónicas en local.

Las herramientas propuestas y cualquier descarga de binarios/modelos siguen pendientes de autorización según las restricciones vigentes. La firma del instalador y un canal de actualización se decidirán antes de distribuir públicamente; no se compran certificados ni se publican artefactos en este trabajo.

## Fuentes consultadas

- [PyInstaller: modos de distribución](https://pyinstaller.org/en/stable/operating-mode.html): incluye el intérprete; describe carpeta y archivo único, y recomienda validar primero el modo de carpeta.
- [PyInstaller: rutas en ejecución](https://pyinstaller.org/en/stable/runtime-information.html): diferencia recursos empaquetados y ejecutable.
- [Inno Setup: privilegios](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm): `lowest` permite instalación sin solicitar elevación.
- [Inno Setup: borrado al desinstalar](https://jrsoftware.org/ishelp/topic_uninstalldeletesection.htm): cuidado con borrar datos creados por el usuario.
- [Microsoft: Application Loopback](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/): requisito de build 20348 y captura por proceso.
- [FFmpeg: distribución y licencias](https://www.ffmpeg.org/legal.html): revisar el binario concreto y sus obligaciones antes de incluirlo.
