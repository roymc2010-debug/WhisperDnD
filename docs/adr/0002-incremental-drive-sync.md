# Sincronización incremental de Drive

Estado: implementada; transferencias verificadas con proveedor simulado.

## Contexto
La descarga secuencial seguida de subida podía sustituir un cambio local por una versión remota anterior. Las subidas paralelas compartían una conexión HTTP no segura entre hilos. Autenticación síncrona de Drive bloqueaba solicitudes independientes, incluidas comprobaciones de claves.

## Decisión
Comparar MD5 local/remoto con un checkpoint por espacio de datos. Transferir solo el lado que cambió; bloquear y comunicar conflictos, nombres duplicados y discrepancias sin base común. Nunca inferir igualdad por tamaño. La primera comparación de una campaña desconocida requiere descargarla y validar su esquema con el importador existente; el plan de solo lectura la marca como `probe`.

Usar hasta cuatro transferencias simultáneas con transportes HTTP independientes, aplicar importaciones locales en serie y agrupar solicitudes simultáneas del mismo espacio de datos. Subir instantáneas inmutables y cerrar sus streams incluso ante errores. No borrar archivos. Limitar búsquedas a carpetas de la aplicación y a una ubicación local configurada.

Separar comprobaciones de Groq/Gemini de Drive y ejecutar autenticación y operaciones bloqueantes fuera del bucle de eventos. Conservar compatibilidad del endpoint de estado, ofreciendo `include_drive=false`. El diagnóstico puede arrancar con `WHISPER_SKIP_STARTUP_DRIVE_SYNC=1`; no cambia el comportamiento predeterminado.

## Consecuencias
Los conflictos requieren revisión: no se escoge una copia por fecha o tamaño. El checkpoint ocupa un JSON pequeño escrito atómicamente. La agrupación de trabajos protege un proceso; no coordina servidores independientes. Se sigue consultando metadatos y calculando hashes; no se garantiza cero tráfico ni aceleración proporcional al número de hilos. Las validaciones del importador y sus respaldos permanecen vigentes. No se incorporan dependencias.

Referencia: [seguridad de hilos del cliente oficial de Google](https://googleapis.github.io/google-api-python-client/docs/thread_safety.html).
