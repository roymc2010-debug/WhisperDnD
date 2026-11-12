# Descarga manual del reporte de errores — 12 de noviembre de 2026

## Cambio y alcance

En Ajustes se añadió «Ayuda y reporte de errores», con un botón para descargar `WhisperDnD-reporte-errores.txt`, explicación de contenido y estado de descarga/error. No hay subida ni envío automático. Los borradores legales continúan sin publicar; la etapa acordada es prueba privada con conocidos.

El endpoint `GET /api/support/report` genera texto con versión de la app, fecha UTC, familia de sistema, arquitectura, versión de Python, modo y hasta 200 fallos. Los fallos HTTP se registran por categoría de operación, método y código de respuesta. `set_task_error` registra también fallos de procesamiento en segundo plano, con tipos conocidos mediante lista permitida; cualquier otro tipo se convierte en una categoría genérica. No guarda identificadores de tareas ni mensajes de excepción.

Se mantiene un historial dedicado `support-errors.json`, con reemplazo mediante archivo temporal y bloqueo entre hilos. En desarrollo utiliza el directorio de salida efectivo; empaquetado, la carpeta de logs del perfil. Se lee como máximo 64 KiB y se conservan solo campos y valores admitidos. Un fallo de escritura deja el historial en memoria y no cambia la respuesta de la operación original. No se exporta `server.log`, no se recorren campañas/audios y no se leen claves, tokens, cabeceras, cuerpos, URLs concretas ni parámetros de consulta para elaborar el reporte. El endpoint responde como adjunto con `no-store`.

## Límites explícitos

- No recupera errores anteriores a esta integración ni garantiza capturar todos los fallos de arranque, del navegador o de proveedores. El reporte lo indica. Algunas operaciones se clasifican como `application` cuando su ruta no coincide con una categoría conocida.
- El reporte omite deliberadamente mensajes libres y trazas; para diagnosticar, quien pruebe debe acompañarlo con lo que intentaba hacer y la hora aproximada. No contiene el detalle completo de cada error.
- La versión incluida es la declarada por FastAPI (`3.0.0`); todavía falta definir un identificador por build del instalador.
- Historial por proceso/perfil de ejecución, sin separación entre visitantes de un servidor web compartido. Está destinado al flujo de escritorio; no se debe presentar Render como servicio multiusuario aislado por este cambio.
- El historial persiste hasta su eliminación o sustitución por eventos nuevos. No se añadió limpieza automática al desinstalar ni un sistema de recepción remota de reportes.
- No se reinició la app principal ni se ejecutó una grabación o una llamada a servicios externos.

## Verificación

Regresiones nuevas verificadas primero en fallo y después aprobadas: cinco backend y tres frontend. Cubren descarga vacía, persistencia de fallos HTTP y excepciones, exclusión de datos privados sintéticos, límite de 200, lectura de historial alterado, fallo de escritura sin alterar la respuesta, fallo de tarea en segundo plano, descarga sin claves/cuerpo, liberación del enlace temporal, recuperación del botón y doble activación.

Suite offline completa: **662 aprobadas, 2 omitidas y 46 subpruebas aprobadas**, con cinco avisos de dependencias. Suite frontend: **115 aprobadas y 2 omitidas**, sin fallos.

La vista de Ajustes se revisó en navegador con el HTML, CSS y controlador reales, sirviendo únicamente archivos estáticos y un reporte sintético mediante un servidor temporal local. No se arrancó FastAPI ni se consultaron campañas, dispositivos, cuentas o servicios. El botón descargó el archivo y mostró que no se había enviado a nadie. En una ventana de 520 × 900 el control permaneció visible y la página midió 520 px de ancho y 520 px de contenido, sin desbordamiento horizontal. Se restauró el tamaño de ventana y se cerró la pestaña temporal.

El detector visual revisó los archivos modificados. Señaló problemas de contraste, tipografía y decoración del documento completo ya existente; no se cambió el diseño de otras secciones para resolverlos. La sección añadida conserva el tema, usa foco visible, estado deshabilitado y mensajes accesibles. No se afirma que toda la interfaz pase una auditoría visual.

La comparación con la referencia tomada antes de editar conservó los hashes de los cuatro archivos privados (`credentials.json`, `token.json`, `token_backup.json`, `.env`) y los siete JSON situados directamente en `data/campaigns` incluidos en esa referencia. No se presenta esta comprobación como inventario recursivo de todas las campañas. Se leyó el TXT sintético descargado y coincidió con el reporte esperado. El servidor temporal terminó al finalizar la revisión.

La sintaxis de `support-report.js` se comprobó con Node. `git diff --check` señaló espacios finales en tres líneas antiguas de ingestión/idioma de `static/index.html`, fuera de la sección añadida; no se corrigieron para no ampliar el cambio. No se afirma que el diff acumulado esté limpio. Las pruebas usan temporales y red bloqueada; no se instalaron dependencias ni se construyó un EXE.
