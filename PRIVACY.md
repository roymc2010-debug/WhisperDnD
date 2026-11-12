# Privacidad en la evaluación de WhisperDnD

Actualizado: 12 de noviembre de 2026. Este aviso describe los flujos actuales para que quienes prueben puedan decidir qué datos utilizar. **No es todavía la política final para publicación OAuth o para operar un servicio web público.**

- La aplicación utiliza el audio, las transcripciones, instrucciones y contexto de campaña necesarios para las funciones que elijas.
- Whisper local procesa la transcripción en el equipo. Groq recibe audio cuando eliges transcripción remota. Gemini recibe texto, instrucciones y el contexto incluido al generar documentos, incluso cuando el audio se transcribió localmente.
- Si conectas Drive y utilizas sincronización, se transfieren documentos y metadatos dentro del acceso concedido mediante `drive.file`. Una campaña descargada de Drive puede formar parte del contexto enviado a Gemini si vuelves a procesarla.
- El navegador conserva preferencias, claves de API y una copia de la autorización de Drive. El backend mantiene archivos de autorización y respaldos. No se afirma que WhisperDnD cifre esos archivos.
- Los archivos pueden permanecer en el equipo o en Drive hasta que los elimines. Cerrar, desconectar o desinstalar no garantiza eliminar todas las copias ni el contenido enviado a proveedores.
- El reporte descargable incluye versión, entorno básico y un historial acotado de fallos. No adjunta audio, sesiones, claves o tokens ni se envía automáticamente. Los registros completos del servidor son distintos y pueden contener detalles de las operaciones.

Antes de grabar o compartir, informa a las personas involucradas. Utiliza material desechable en las primeras pruebas y revisa cualquier reporte que envíes. Puedes revocar el acceso de Drive en las [conexiones de tu cuenta de Google](https://myaccount.google.com/connections), eliminar las claves guardadas y revocarlas en su proveedor. Revisa también archivos, exportaciones, respaldos y almacenamiento del navegador para eliminar tus copias.

Los servicios externos aplican sus propias condiciones y reglas de conservación. No se garantiza aquí su política de entrenamiento o eliminación. Para dudas sobre copias bajo control del proyecto, contacta a la persona que te invitó; el proyecto no puede borrar directamente lo que solo está en tu equipo o en cuentas ajenas.

El [borrador completo de privacidad](docs/legal/politica-de-privacidad.md) identifica los detalles y compromisos aún pendientes de aprobación. La identidad del responsable, contacto público y los requisitos aplicables deberán completarse antes de publicar la política final.
