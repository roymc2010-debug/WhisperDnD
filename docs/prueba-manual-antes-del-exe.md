# Prueba manual de WhisperDnD antes del EXE

Preparada el 12 de noviembre de 2026. Esta prueba usa el código actual y el entorno de desarrollo de este equipo; todavía no es un instalador ni una comprobación en otro PC.

## Cómo abrirla

1. Abre `comprobar_antes_del_exe.bat`. Comprueba que no aparezca **FALTA** en las dependencias o recursos necesarios. La comprobación no arranca el servidor, graba ni descarga modelos.
2. Abre `probar_antes_del_exe.bat`. Espera a que se abra la ventana de la app. La dirección de esta prueba es **http://localhost:8082**.
3. Mantén abierta la ventana que inició la prueba. Antes de salir, termina grabaciones, procesamiento y sincronizaciones. Una vez inactiva, puedes volver a esa ventana y pulsar **Ctrl+C** para cerrar el servidor.

La app habitual puede seguir en su dirección anterior. Si el puerto de la prueba está ocupado por otro programa, se mostrará un aviso; no se cerrará ese programa ni se elegirá otra dirección silenciosamente. Si abres dos veces esta misma prueba, se reutiliza la instancia que ya está respondiendo. Si todavía está iniciando, espera y vuelve a abrirla.

Los archivos de esta prueba quedan en **`%LOCALAPPDATA%\WhisperDnD-Pruebas`**, separados de las campañas actuales. No se cargan automáticamente campañas antiguas, `.env`, claves de API ni autorizaciones personales de Google/Discord. El navegador usa otro origen y sus ajustes pueden empezar vacíos. Crea una campaña inventada para empezar. La carpeta de prueba se conserva entre aperturas; cerrar el servidor no borra tu trabajo.

El modo de prueba desactiva la restauración automática de Drive al arrancar. Si conectas y sincronizas Drive manualmente, sí puede descargar o actualizar archivos accesibles de esa cuenta: usa contenido desechable y revisa la operación antes de ejecutarla.

## Orden recomendado

Marca cada paso después de probarlo. Si falla, anota qué intentabas hacer y la hora; descarga el reporte desde Ajustes antes de repetir la operación.

### Primera apertura y grupo

- [ ] La prueba abre sin errores y sin mostrar campañas de la app habitual.
- [ ] Crea una campaña llamada `QA Manual`, con un DM inventado y al menos dos jugadores. Dale un personaje al jugador que marques como tú.
- [ ] Guarda el grupo, cambia de vista y recarga la página. Comprueba que el DM, los personajes y la marca de personaje propio permanezcan iguales.
- [ ] Abre otra campaña de prueba y vuelve a `QA Manual`. Comprueba que no se mezclen grupos ni sesiones.
- [ ] Vuelve a abrir el acceso de prueba. Debe mostrar la misma instancia y conservar los datos guardados.

### Ajustes, dispositivos y captura

- [ ] Selecciona micrófono y salida de audio. Comprueba las lecturas en Audio y Ajustes.
- [ ] Cuando quieras hacer la prueba real de Discord, prepara una llamada con voz y realiza una grabación breve con frases diferentes desde el micrófono y Discord.
- [ ] Al detener, comprueba que finaliza el guardado, que el audio se puede reproducir y que se oyen las fuentes elegidas. Comprueba que no se hayan cambiado el DM ni tu personaje.
- [ ] Repite una sesión numerada y verifica que la app conserva o solicita revisar el reemplazo de la sesión correcta, sin sobrescribir otra por accidente.
- [ ] Si pruebas modo clase, comprueba que captura solo la fuente anunciada y que el resultado se guarda en Trabajo y estudio.

**Antes de procesar:** Groq y Gemini pueden consumir cuota o generar cargos en tus cuentas. Configura tus claves en Ajustes solo cuando quieras hacer esas pruebas. La transcripción local puede necesitar descargar un modelo; no se ha descargado ninguno durante esta preparación. Elegir Whisper local no convierte la generación con Gemini en local.

### Transcripción, crónica y recuperación

- [ ] Procesa un audio breve y revisa la transcripción antes de utilizarla como fuente.
- [ ] Genera una crónica con nombres y hechos fáciles de comprobar. Revisa las propuestas antes de guardarlas.
- [ ] Rechaza una propuesta y confirma que no se incorpora al guardar.
- [ ] Comprueba que una sesión nueva aparece en Historial y Wiki dentro de la campaña correcta.
- [ ] Prueba el fallo de un servicio con una clave de prueba inválida: debe indicar el problema y conservar la fuente para reintentar. No repitas una generación facturable sin revisar primero qué resultado se guardó.
- [ ] Cuando exista una entrada recuperable, intenta la recuperación ofrecida por la app y comprueba que no duplica sesiones ni usa una fuente de otra campaña.

### Archivos y Trabajo y estudio

- [ ] Exporta Markdown y DOCX. Ábrelos y comprueba título, número de sesión y contenido.
- [ ] Crea o importa una nota de estudio de prueba. Edita, guarda, recarga y descarga el documento.
- [ ] Elimina únicamente una nota desechable. Comprueba que otra nota y la campaña permanezcan intactas.
- [ ] Comprueba que el historial y los documentos sobrevivan a cerrar y volver a abrir la prueba.

### Drive, cuando se configure para esta prueba

- [ ] Confirma primero que el perfil de prueba tiene la configuración del cliente OAuth de escritorio aprobado y que tu cuenta está permitida como usuario de prueba en Google Cloud.
- [ ] Conecta tu cuenta mediante Google, cancela una vez y vuelve a intentar. Verifica los avisos.
- [ ] Sincroniza solo archivos de prueba. Comprueba el destino, el comportamiento ante conflictos y que no se dupliquen campañas.
- [ ] Desconecta y vuelve a conectar. Cerrar sesión no debe borrar tus documentos de Drive.

La configuración común de OAuth no se copió del checkout al perfil ni se eligió automáticamente. Esta integración y la autorización real de Drive siguen pendientes de coordinar; que Drive figure sin configurar en un perfil nuevo no significa que las otras funciones fallen. No copies `token.json`, respaldos ni claves del desarrollador para habilitarlo.

### Reporte y salida

- [ ] Descarga **Ajustes → Descargar reporte de errores**. Abre el TXT y comprueba que se puede leer.
- [ ] Después de un fallo, vuelve a descargarlo. Debe mostrar fecha, categoría y tipo/código cuando el fallo esté cubierto por el historial; no debe contener claves, autorizaciones ni texto de sesiones.
- [ ] Comprueba que el archivo no se envíe automáticamente. Al compartirlo, añade qué esperabas y qué ocurrió.
- [ ] Cuando no haya trabajos activos, cierra el servidor con Ctrl+C y abre la prueba otra vez. Verifica conservación de grupo, sesiones y notas.

El cierre mediante Ctrl+C se rechaza si se detecta grabación, tarea en curso, petición de escritura/transferencia o sincronización en segundo plano. Esto no protege contra cerrar a la fuerza la consola desde Windows, terminar el proceso, apagar el equipo o un fallo del sistema. No uses esas acciones durante una operación.

## Cómo reportar un fallo

Incluye estos datos junto al TXT: paso realizado, resultado esperado, resultado observado, hora aproximada y si se repite al reintentar. Puedes añadir una captura revisada para que no muestre claves o contenido privado. No envíes `.env`, tokens, audios ni toda la carpeta de datos como reporte general.

## Qué queda para convertir y distribuir

Después de esta revisión manual hay que resolver los fallos encontrados, validar los flujos con cuentas/dispositivos reales y preparar una build con su lista de recursos, dependencias nativas, FFmpeg/ffprobe y avisos de licencias. También siguen pendientes la configuración común de Drive, la protección completa de autorizaciones, el instalador y la prueba en un Windows limpio. No se considera lista para distribuir por el solo hecho de pasar las pruebas automáticas.
