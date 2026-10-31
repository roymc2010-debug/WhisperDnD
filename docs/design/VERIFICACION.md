# Verificación del rediseño

Fecha: 30 de octubre de 2026. Base: rama local laboratorio, b1f46ac, más sus nueve archivos locales, preservados en c879379.

## Resultado

- Antes de integrar: 234 pruebas Python correctas, 11 fallos, 38 subpruebas correctas.
- Después de corregir también el lanzador: 241 pruebas Python correctas, los mismos 11 fallos, 40 subpruebas correctas.
- Frontend: 9 pruebas Node correctas para temas, validación de regrabación, selección y color de clases, campañas vacías, endpoint de guardado, errores de guardado y conservación de multiclase/homebrew.
- Lanzador: 7 pruebas Python para copia sin sobrescrituras, exclusión de credenciales/audio, configuración aislada, puerto ocupado y apertura del navegador solo después del arranque. Están incluidas en las 241 anteriores.
- Compilación local de Tailwind y sintaxis de los scripts verificadas. El aviso de Browserslist sobre su base local antigua no impide compilar.

## Comprobaciones en la app real

Servidor FastAPI de esta rama en 127.0.0.1:8081, con una campaña ficticia aislada. Navegador normal de 1280×720 y verificación adicional de 390×844.

- Seis temas: selección, estado accesible, persistencia tras recargar y conservación entre D&D y Work & Study.
- Party dentro de grabación, abierta por defecto y plegable. Identidad agrupada, especie, clases en una sola celda, estado y eliminación conservados.
- Clérigo/Guerrero multiclase, colores originales y SVG del clérigo; sin relieve ni placas detrás.
- Menús flotantes de especies y clases. Clase correcta al abrir; cierre con Escape y devolución del foco.
- Selección de mi personaje, guardado mediante el endpoint vigente y persistencia comprobada tras recargar y en disco.
- Regrabar: sesiones existentes, preparación de sesión 2 y cancelación sin procesar ni eliminar datos.
- Campañas e importación dentro de Wiki; sesiones y controles de exportación accesibles.
- Work & Study sin party; plantillas académicas y ejecutivas y selección de fuente de audio.
- Audio y ganancias accesibles desde la vista Audio; ajustes y campos de API conservados.
- Barra de fuentes e idioma corregida a 390px: el ancho del contenido principal coincide con su ancho visible. La tabla de party tiene desplazamiento interno intencional.
- Ningún error de consola en la verificación final. Servidor y pestaña temporales cerrados al terminar.

## Límites

No se inició una grabación real ni se consumieron llamadas de transcripción, Gemini o YouTube. No se conectaron cuentas de Drive/Discord ni se verificó una sincronización remota. Estos flujos conservan sus módulos y requieren una prueba manual con las claves y permisos del usuario. El shell sigue siendo la aplicación local existente; esta rama no añade un instalador nativo.

## Fallos que ya existían

No fueron introducidos por el rediseño. Deben resolverse en una tarea de backend/pruebas separada.

- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_class_mode
- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_missing_audio
- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_roleplay_success
- tests/test_campaign_api.py::TestCampaignApi::test_deduplicate_campaign_endpoint
- tests/test_campaign_manager.py::TestCampaignManager::test_multi_session_continuity_and_merging
- tests/test_campaign_manager.py::TestCampaignManager::test_record_session_with_existing_universal_pc_player_matching_no_name_error
- tests/test_campaign_manager.py::TestCampaignManager::test_retroactive_deduplicate_campaign_entities_octus
- tests/test_groq_whisper.py::TestGroqWhisperTranscriber::test_chunk_percentage_calibration
- tests/test_groq_whisper.py::TestGroqWhisperTranscriber::test_transcribe_chunked_survives_failed_chunk
- tests/test_groq_whisper.py::TestTranscriptionPipeline::test_slice_audio_for_groq_ffmpeg_call
- tests/test_youtube_downloader.py::TestYouTubeDownloader::test_download_youtube_audio_progress_hook

Los tres casos de telemetría reciben 401 con las claves ficticias de las pruebas. Los demás afectan deduplicación/continuidad de campañas, calibración de progreso y un archivo de audio ficticio ausente. La suite completa sigue sin pasar.

## Corrección de arranque con otra copia abierta

Se observó un proceso main.py en 8081 que devolvía el HTML antiguo y 404 para /static/desktop.css. El temporizador del lanzador podía abrir esa dirección incluso si el servidor nuevo no lograba iniciar.

El lanzador reserva ahora un socket exclusivo en loopback, elige el siguiente puerto disponible y abre únicamente su URL cuando Uvicorn confirma el arranque. Se probó la selección de puerto con un socket real ocupado y se verificó el servidor corregido: HTML con desktop.js/desktop.css y respuesta 200 para esos estilos. El servidor temporal se cerró después de verificarlo.

## Ajuste a la referencia visual de escritorio

Verificado con la app real y la campaña ficticia aislada a 1919×897: raíz de 20px, barra lateral de 272,5px, contenido de 1475px y título de 33,75px. La vista principal no desborda horizontalmente. El selector de clases mide aproximadamente 960×715px y cabe dentro de la ventana.

A 1280×720 se conserva la raíz de 16px y Work & Study no muestra la party ni desborda horizontalmente. A 390×844, el contenido principal tiene 380px visibles y 380px de ancho total; solo la tabla conserva su desplazamiento interno de 810px. Las seis paletas no cambiaron.

La modificación es de CSS y la referencia de caché del stylesheet. No se modificó lógica Python o JavaScript. La suite de frontend se vuelve a ejecutar; los resultados generales de backend anteriores siguen documentados arriba.

## Escala intermedia y corrección de solapamientos

La expansión anterior de 20px fue reemplazada por 18px desde 1600px y 16px en ventanas menores, con contenido máximo independiente de 1480px. La Wiki separa título, campaña y exportaciones en filas; el selector de sesión acepta títulos largos sin imponer su ancho intrínseco. Los filtros pasan a dos columnas y el explorador se apila bajo 1100px. Apuntes recibe cabecera y columnas adaptables.

Se reprodujo el fallo a 1536×720: el título de Wiki se comprimía a unos 101px, existía desbordamiento horizontal y algunos filtros tenían 108px visibles para 143px de contenido. En la comprobación tras el ajuste, el título ocupó unos 568px en una línea, el contenido principal midió 1308px tanto visible como total y los seis filtros tuvieron 163px visibles y 163px de contenido.

También se recorrieron Sesión, Audio, Personaje, Proceso, Resultado, Apariencia y Ajustes a 1536px sin desbordamiento del contenido principal. Se inspeccionaron visualmente Wiki y Apuntes a 390×844, y Wiki a 1919×898. Tras agrupar el botón de recarga junto a la campaña, la conexión del navegador de prueba falló durante la última confirmación: esa comprobación final no pudo completarse. Las verificaciones de código comprueban CSS válido, paletas conservadas, IDs originales presentes y ninguna duplicación; las nueve pruebas de frontend pasan.

No se modifica lógica Python o JavaScript. Los cambios quedan limitados al HTML de distribución, CSS y esta documentación.

## Botones e iconos — 30 de octubre de 2026

- Frontend: node --test tests/frontend/*.test.cjs — 11 pruebas aprobadas. Incluye las 9 existentes y regresiones para nombres de iconos no confiables y detección de audífonos mediante metadatos. Se observó primero el fallo de las nuevas pruebas y después su paso.
- Todos los módulos JS analizados con node:vm sin errores de sintaxis; desktop.css analizado con PostCSS. git diff --check sin errores de espacios (Git informa conversión de LF a CRLF).
- Contraste calculado para los seis temas y los colores de acción en reposo, hover y pulsado: mínimo de texto 4.57:1, mínimo de borde en reposo 3.29:1 y mínimo de acción principal 7.53:1. Estas cifras cubren los estilos de acción calculados, no una certificación de toda la aplicación.
- Navegador local: Wiki con la campaña Candlekeep 2.0, 3 sesiones y sus entidades; tema oscuro a 1920 px y Papel y tinta a 1280 px. La cabecera no presenta desbordamiento horizontal en ninguna de esas dos comprobaciones.
- Navegación comprobada hacia Audio, Proceso, Resultado, Mi Personaje, Apariencia y Ajustes. Work & Study no muestra party; volver a D&D carga la party de seis integrantes.
- Selectores flotantes de clase y especie abiertos/cerrados sin cambiar las selecciones; cero emojis en sus botones y cero botones visibles sin nombre accesible. Los SVG de clase mantienen el mismo contenido que antes del cambio.
- Ajustes mantiene ocultas sincronización y desconexión de Drive cuando no hay una conexión. No se introdujeron llaves ni se inició una grabación o petición de procesamiento.
- Sin errores de consola registrados durante las comprobaciones. Capturas en outputs/ui-controls del directorio de trabajo del chat, fuera del repositorio. La pestaña temporal se cerró y se restableció el tamaño del navegador. No se inició ningún servidor adicional.
- Backend: se intentó ejecutar pytest con el venv de WhisperDnD-Lab, pero su Python base ya no está disponible en C:/Users/HP/AppData/Local/Programs/Python/Python311/python.exe. No se llegó a ejecutar la suite; esto no cambia el registro anterior de fallos pendientes.

## Simplificación y controles −/+ — 31 de octubre de 2026

- Frontend: 15 pruebas aprobadas; sintaxis de todos los módulos JS y CSS comprobada.
- Formatos y generación/exportación: 44 pruebas aprobadas en test_document_formats.py, test_gemini_client.py y test_docx_exporter.py. Incluyen 11 casos nuevos: seis flujos de procesamiento, validación del formato, prompt de reunión, extracción de acuerdos y tareas, biblioteca de resúmenes breves y Word.
- Suite completa: 252 aprobadas, 11 fallidas, 41 subtests aprobados. Los 11 fallos coinciden con la línea de base, antes de implementar este cambio. Los errores temporales de pytest se resolvieron usando un basetemp nuevo dentro del workspace.
- Compilación: scripts/build-frontend.cjs completado con Tailwind 3.4.19, usando la dependencia ya instalada en la copia design-current; 67 recursos locales. Se mantiene un aviso de Browserslist desactualizado.
- Python 3.11.9 sí está instalado. La restricción de acceso del entorno de ejecución causaba el fallo de la comprobación anterior; las pruebas se ejecutaron con acceso al intérprete existente y PYTHON_DOTENV_DISABLED=1. No se instalaron dependencias.
- Vista aislada en 127.0.0.1:64702, desde el directorio exacto de esta rama. El puerto 8081 estaba sirviendo otra copia anterior. Se verificó el selector único, conservación de título al cambiar formato, Más opciones cerrado/abierto y traslado del idioma entre los modos.
- D&D: botones comprobados con la campaña Candlekeep 2.0 de la copia de prueba; en Archivo cambian 4→5→4. Al preparar Regrabar avanzan entre sesiones guardadas y no superan la última; Cancelar reemplazo vuelve a la sesión siguiente. No se procesó audio ni se reemplazó ningún archivo.
- Capturas en outputs/simplified-ingest del directorio del chat. No hubo errores de consola originados por el puerto aislado; apareció un error anterior de fetch del puerto 8081 en el historial de la pestaña.
- La pestaña temporal y el servidor de prueba se cerraron. El servidor informó Application shutdown complete y Finished server process. El servidor ajeno del puerto 8081 no se detuvo.

### Fallos previos que permanecen

- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_class_mode
- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_missing_audio
- tests/test_api.py::TestAPIEndpoints::test_upload_with_telemetry_roleplay_success
- tests/test_campaign_api.py::TestCampaignApi::test_deduplicate_campaign_endpoint
- tests/test_campaign_manager.py::TestCampaignManager::test_multi_session_continuity_and_merging
- tests/test_campaign_manager.py::TestCampaignManager::test_record_session_with_existing_universal_pc_player_matching_no_name_error
- tests/test_campaign_manager.py::TestCampaignManager::test_retroactive_deduplicate_campaign_entities_octus
- tests/test_groq_whisper.py::TestGroqWhisperTranscriber::test_chunk_percentage_calibration
- tests/test_groq_whisper.py::TestGroqWhisperTranscriber::test_transcribe_chunked_survives_failed_chunk
- tests/test_groq_whisper.py::TestTranscriptionPipeline::test_slice_audio_for_groq_ffmpeg_call
- tests/test_youtube_downloader.py::TestYouTubeDownloader::test_download_youtube_audio_progress_hook
