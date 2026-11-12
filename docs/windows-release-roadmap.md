# Hoja de ruta hacia una versión instalable de WhisperDnD

Fecha de revisión: 12 de noviembre de 2026.

## Resultado buscado

Una persona en otro PC Windows compatible descarga un instalador EXE, instala y abre WhisperDnD desde un acceso directo, configura sus propias claves y puede grabar, transcribir, revisar una crónica y exportar sus sesiones sin preparar Python, Node, `.venv` o una terminal. Al actualizar o desinstalar, sus datos permanecen disponibles.

La primera plataforma propuesta es Windows 11 x64. La arquitectura y herramientas candidatas están en [ADR 0004](adr/0004-windows-installable-distribution.md), todavía como propuesta, no como compatibilidad certificada.

## Estado de partida

- Se conserva la SPA y el backend actuales, con Groq/faster-whisper, Gemini configurado, Drive opcional y revisión de canon.
- Los arreglos de DM/roster y carga se documentaron y probaron previamente. Sus cifras de pruebas no son una ejecución nueva del 12 de noviembre.
- La verificación visual sintética del grupo se cerró el 11 de noviembre. La captura real de micrófono y Discord se pospuso a petición del usuario; sigue pendiente.
- Hay numerosos cambios locales acumulados. No se mezclan copias ni se hace commit, push, reset o cambio de rama como parte de este plan.
- No hay evidencia de una build instalable funcionando en otro PC.

## Etapas y criterios de salida

| Etapa | Trabajo acotado | Cómo se considera terminada |
| --- | --- | --- |
| 1. Separar recursos y datos | Resolver rutas por modo desarrollo/instalado; campañas, salidas, logs, modelos y tokens fuera de recursos de programa; respetar overrides de tests | Pruebas con instalación simulada de solo lectura y datos temporales, desde otro directorio de trabajo y rutas con espacios/acentos; ninguna escritura en campañas reales |
| 2. Arranque de aplicación | Entrada independiente de `.venv`, recursos localizados en distribución, identidad de instancia, disponibilidad HTTP, errores visibles, salida controlada | Abre la instancia correcta; segundo inicio no duplica servidor; un puerto ocupado no abre otra app; no interrumpe grabación/proceso activo |
| 3. Compilación reproducible | Registrar versiones resueltas en entorno de build separado, manifiesto de assets/DLL/binarios, reglas de exclusión, receta PyInstaller | Carpeta ejecutable verificable sin Python/Node instalados; manifiesto sin datos personales; dependencias nativas y FFmpeg/ffprobe comprobados |
| 4. Primera ejecución | Configurar claves y Drive por usuario, diagnósticos claros, detección de OS/dispositivos, modelos locales opcionales y descarga controlada | Un usuario nuevo llega al estado listo sin editar archivos; un servicio opcional ausente no bloquea lo demás; claves no aparecen en logs |
| 5. Validación funcional | Probar captura real, WAV/timeline, transcripción elegida, fallo de Gemini y recuperación, revisión de canon, exportación y Drive opcional | Matriz de flujos con evidencia; originales preservados; resultados generados no aplicados sin revisión. Las llamadas de pago se coordinan y autorizan por separado |
| 6. Instalador EXE | Instalar candidato probado, accesos directos, versión/identidad del producto y desinstalación | Instalar, abrir, actualizar y desinstalar como usuario normal; conservar datos; no actualizar mientras haya trabajos activos |
| 7. Candidato distribuible | Prueba en PC/VM limpios, segundo usuario Windows y otra máquina física para audio; documentación y avisos de dependencias | Sin rutas del equipo de desarrollo, sin dependencias manuales inesperadas, sin datos privados, con limitaciones y procedimiento de recuperación documentados |

Cada etapa puede dividirse en cambios pequeños. No se exige completar una reescritura ni incorporar nuevas funciones narrativas para producir el primer instalador. Las optimizaciones de memoria/reintentos de audio largo se mantienen como una línea de trabajo independiente, priorizada por mediciones, y no se mezclan automáticamente con una modificación de rutas.

## Primer cambio de código recomendado

Crear y probar un resolvedor común de rutas que distinga **recursos de la aplicación** y **datos del usuario**, empezando por su contrato y regresiones. El primer cambio debe ser aditivo y conservar los defaults actuales del checkout; conectar los módulos se hará después por grupos pequeños, manteniendo sus pruebas de aislamiento.

Inspección dirigida ya realizada:

- `main.py`: reejecución dentro de `.venv`, logs en `outputs`, generación de archivo de credenciales y host/puerto.
- `scripts/launch_desktop.py`: dependencia del intérprete y del script de desarrollo, URL y comprobación de disponibilidad.
- `src/api/server.py`: recursos estáticos y overrides `WHISPER_INPUT_DIR`, `WHISPER_OUTPUT_DIR`, `WHISPER_CAMPAIGNS_DIR`.
- `src/storage/campaign_manager.py`, `quota_tracker.py`, `drive_client.py`: campañas, exportaciones, cuotas y tokens.
- `src/transcription/local_whisper.py`, `discord_rpc.py`: caché de modelos y token Discord relativo al directorio actual.

Antes de conectar cada módulo, identificar sus demás escritores por búsquedas concretas. Esta lista no afirma una auditoría exhaustiva de todas las rutas del repositorio.

Pruebas iniciales del contrato: modo desarrollo mantiene rutas existentes; modo instalado no escribe en recursos; overrides explícitos prevalecen; directorio de trabajo diferente no cambia la ubicación de datos; dos perfiles de usuario no comparten tokens; resolver rutas no mueve ni importa datos por sí solo. El instalador y la migración histórica no se implementan en ese primer cambio.

### Avance del 12 de noviembre

Se añadió `src/runtime_paths.py`, un contrato sin efectos secundarios para calcular las rutas de recursos y datos. Incluye detección de ejecución empaquetada, defaults de desarrollo, almacenamiento por usuario en modo instalado y los overrides ya usados para campañas, entradas, salidas, cuotas y modelos. No crea carpetas, importa campañas ni modifica variables de entorno. Su primera entrega no se conectaba a los módulos existentes; la integración posterior se describe a continuación.

Sus diez regresiones en `tests/test_runtime_paths.py` pasan. La suite backend offline completa ejecutada después de añadirlo dio **626 aprobadas, 2 omitidas y 45 subpruebas aprobadas**, con cinco avisos de dependencias, en 37,98 s. No hubo instalaciones, descargas, llamadas de pago ni cambios de campañas. No se reejecutó el frontend porque no se modificó.

Se conectaron después los proveedores de rutas de entrada/salida/campañas del servidor y las rutas de campañas/salidas de `CampaignManager`. Las pruebas simulan recursos que rechazan escrituras y perfiles de usuario dentro de directorios temporales. Comprueban guardado agregado/modular de una campaña sintética, lectura de HTML desde recursos, overrides explícitos y defaults de desarrollo, incluida la ruta temporal existente de entradas en Linux. No hay migración automática ni cambio de ubicación de datos en desarrollo.

La verificación posterior a esa integración dio **634 aprobadas, 2 omitidas y 45 subpruebas aprobadas** en la suite backend offline completa, con cinco avisos de dependencias, en 31,77 s. Los 17 JSON de campaña registrados al comenzar conservaron sus hashes. Ver [informe de integración](reviews/runtime-path-integration-20261112.md).

Se conectaron también los logs de `main.py` y del lanzador al resolvedor: desarrollo conserva `outputs/server.log`; el modo empaquetado utiliza la carpeta `logs` del perfil. Se conservaron la espera de disponibilidad y el origen del navegador. El punto de entrada empaquetado ya no intenta reejecutar una `.venv`; el flujo completo de ejecución del lanzador empaquetado aún requiere su adaptación posterior.

Esta segunda integración añadió ocho regresiones de arranque/logs. La suite backend offline completa dio **642 aprobadas, 2 omitidas y 45 subpruebas aprobadas** en 30,20 s, con cinco avisos de dependencias. Los procesos de servidor/navegador fueron simulados; un intérprete corto de prueba verificó la ejecución independiente del script desde otra carpeta. Ver [informe de logs](reviews/startup-logs-paths-20261112.md).

También se conectó la configuración OAuth y los tokens de Drive al perfil del usuario en modo empaquetado. El cliente local ya era de escritorio; no se cambió ni se renovó su sesión. Se preparó el contrato para una configuración común aprobada del instalador, sin incluir tokens personales. Las rutas explícitas y el funcionamiento de desarrollo se conservan; Drive sigue siendo opcional. Ver [preparación de Drive](drive-desktop-distribution.md) e [informe del cambio](reviews/drive-desktop-profiles-20261112.md).

La verificación offline final de ese bloque dio **657 aprobadas, 2 omitidas y 45 subpruebas aprobadas**, con cinco avisos de dependencias, en 32,61 s. Los cuatro archivos privados reales inspeccionados y los 17 JSON de campaña registrados conservaron sus hashes. El inicio de sesión real desde una build sigue sin comprobarse.

La revisión de lectura de Google Cloud del 12 de noviembre encontró audiencia externa en Prueba, una cuenta de prueba y clientes de escritorio y web existentes. La publicación está deshabilitada por marca incompleta; faltan los enlaces en Cloud y la declaración del permiso `drive.file` que solicita el código. El usuario confirmó la página https://whisperdnd.onrender.com/, pero aún no tiene política de privacidad ni términos. El siguiente paso es preparar esos textos a partir de los flujos reales, revisarlos y hacerlos accesibles públicamente antes de completar la marca y revisar la publicación. No se cambió la configuración de Cloud. Ver los detalles y comprobaciones aún pendientes en [preparación de Drive](drive-desktop-distribution.md).

La primera distribución será una prueba privada con conocidos. Se aplaza la publicación de los textos legales y la elección de identidad/contacto públicos. Render queda como futuro sitio de presentación y recepción de reportes, todavía sin formulario ni subida implementados. Se añadió la descarga manual desde Ajustes de un reporte acotado y sin contenido de sesiones; ver [verificación de soporte](reviews/support-report-20261112.md). OAuth sigue sin cambios en Prueba; las cuentas de quienes prueben deberán autorizarse como usuarios de prueba antes de usar Drive.

Se conectaron las cuotas y la caché de Whisper local al perfil del usuario en modo empaquetado: `quota/system_quota.json` y `models` dentro de `%LOCALAPPDATA%/WhisperDnD`. Se conservaron los defaults de desarrollo, los overrides y la carga diferida de modelos. No se descargaron pesos ni se migró el contador existente. Ver [verificación de cuotas y modelos](reviews/quota-model-profile-paths-20261112.md).

Se preparó después la [prueba manual previa al EXE](prueba-manual-antes-del-exe.md), con un punto de entrada común de escritorio, perfil separado, exclusión de instancias, reserva de puerto e identidad de salud. Se conectaron grabaciones/fragmentos, token Discord, informes y los fallbacks académicos/exportaciones al perfil. Se conserva la app habitual y no se copia el contenido real. Ver [alcance y verificación](reviews/pre-exe-manual-preparation-20261112.md).

La suite backend final de este bloque dio **688 aprobadas, 2 omitidas y 46 subpruebas aprobadas**; frontend, **115 aprobadas y 2 omitidas**. El arranque real desde otra carpeta pasó con perfil temporal y consultas locales de lectura; no certifica una build empaquetada. La entrada manual sigue usando el Python de desarrollo, pero el punto de entrada nuevo no depende de buscar o reejecutar `.venv`.

La siguiente puerta es la revisión manual del usuario y la corrección de los fallos que encuentre. Antes de distribuir siguen pendientes protección completa de tokens, configuración común OAuth y autorización real, captura con dispositivos, receta reproducible de build con exclusiones, binarios/avisos de licencias, instalador y prueba en Windows limpio. La separación de rutas está comprobada para los consumidores enumerados; no se presenta como una auditoría exhaustiva de cualquier dependencia o escritor futuro. No se ha generado el EXE.

## Reglas de conservación durante el trabajo

Registrar hashes/diff iniciales de los archivos y datos pertinentes. Definir el alcance técnico desde la investigación; no exigir al usuario elegir archivos. Escribir primero la regresión del comportamiento que se modifica y verificar también lo que debe conservarse. Comparar el resultado contra el inicio de la tarea, no solo contra HEAD. Mantener separados código listo, proceso que lo está ejecutando y resultado realmente probado.

Las copias Lab y de respaldo no se seleccionan ni mezclan automáticamente. Las pruebas usan perfiles temporales y campañas sintéticas. Las campañas actuales no se migran a LocalAppData sin un flujo autorizado y revisable. Las instalaciones de herramientas, descargas de modelos, pruebas de pago y publicación no se desprenden de este documento.

## Definición de versión instalable completa

- Instala, abre y funciona en una máquina limpia compatible sin entorno de desarrollo.
- Conserva las funciones actuales que se anuncian; las limitaciones de OS y hardware se detectan y explican.
- Mantiene datos y credenciales separados por usuario; el instalador no contiene secretos ni campañas del desarrollador.
- Captura y procesamiento tienen pruebas reales además de mocks; los fallos conservan fuentes y permiten recuperación.
- Actualizar/desinstalar conserva campañas y no corta trabajos activos.
- Artefacto reproducible y verificable, instrucciones para usuario y matriz de compatibilidad basada en pruebas.

El tamaño, tiempo de instalación, rendimiento mínimo, requisitos de RAM/disco y lista final de Windows soportados siguen sin medirse en una build. No se fijan cifras por suposición.
