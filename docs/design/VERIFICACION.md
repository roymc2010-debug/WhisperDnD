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
