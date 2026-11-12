# Política de privacidad de WhisperDnD

**Borrador para revisión — no publicado.** Preparado el 12 de noviembre de 2026. La fecha de entrada en vigor se fijará al publicar.

> Antes de publicar: completar responsable y contacto, confirmar el funcionamiento de la versión web y revisar los compromisos editoriales señalados en `revision-publicacion.md`. Este texto describe la aplicación de escritorio en preparación; no acredita que el instalador ya esté disponible.

## Responsable y contacto

WhisperDnD es una herramienta para grabar o importar audio, transcribirlo, generar documentos y organizar sesiones y campañas.

Responsable: **[pendiente de confirmar]**. Contacto para privacidad y soporte: **[pendiente de confirmar]**.

## Datos que utiliza la aplicación

Según las funciones que utilices, WhisperDnD trata:

- Audio del micrófono, del dispositivo o aplicación que selecciones, archivos importados y enlaces que facilites para obtener audio.
- Transcripciones, instrucciones, resúmenes, crónicas, documentos exportados e información de campañas, como nombres de participantes, personajes y notas de sesión.
- Preferencias de interfaz, idioma, modelo y dispositivos de audio.
- Claves de API que introduzcas y autorizaciones de Google Drive, necesarias para conectar los servicios elegidos.
- Datos operativos, como tiempos, estados, errores y contadores de uso de los proveedores. Los nombres de archivos y otros detalles de una operación pueden aparecer en registros.

Las grabaciones pueden contener voces y datos personales de otras personas. Informa a los participantes y obtén las autorizaciones necesarias antes de grabar, importar o compartir su contenido. Evita incluir información sensible innecesaria.

## Finalidades y servicios externos

Los datos se utilizan para ejecutar las funciones solicitadas, conservar el trabajo, recuperar operaciones y diagnosticar problemas.

| Función | Tratamiento de datos |
| --- | --- |
| Transcripción con Whisper local | El motor de transcripción procesa el audio en el equipo donde se ejecuta WhisperDnD. La descarga inicial de modelos puede requerir conexión. Esto no convierte las otras funciones de la app en locales. |
| Transcripción con Groq | Se envía a Groq el audio necesario, que puede dividirse en fragmentos, y los parámetros o indicaciones de transcripción correspondientes. |
| Generación con Gemini | Se envían a Google el texto de la sesión, las instrucciones y el contexto de campaña que la aplicación incluya en la solicitud para generar el documento. Ese contexto puede proceder de archivos previamente sincronizados con Drive. |
| Google Drive | Si conectas tu cuenta y utilizas carga o sincronización, se consultan y transfieren los archivos y metadatos accesibles mediante el permiso concedido. |
| Importación desde enlaces | El servicio de origen recibe la solicitud de acceso al recurso que indiques. Debes contar con permiso para obtenerlo y procesarlo. |

Elegir transcripción local no impide los envíos que correspondan a Gemini, Drive u otras funciones conectadas que utilices. Los proveedores aplican sus propias condiciones, ubicaciones de procesamiento y reglas de conservación, que pueden depender del servicio, cuenta y plan. Esta política no garantiza sus plazos de borrado ni sus condiciones de uso para entrenamiento.

Consulta las políticas de [Google](https://policies.google.com/privacy), las condiciones de [Gemini API](https://ai.google.dev/gemini-api/terms) y la información de privacidad de [Groq](https://groq.com/privacy-policy/).

## Acceso a Google Drive

La conexión es opcional. WhisperDnD solicita `https://www.googleapis.com/auth/drive.file`: acceso por archivo a los archivos que la aplicación cree o a los que se le conceda acceso, dentro de lo permitido por Google. No solicita acceso general a todos los archivos de tu Drive.

Para guardar y sincronizar el trabajo, la aplicación puede consultar nombres, identificadores y metadatos, crear carpetas, cargar o actualizar documentos y descargar archivos accesibles. Conectar Drive no significa publicar esos documentos. Su visibilidad también depende de los permisos y comparticiones que tengan en tu cuenta.

La autorización se realiza en Google; no debes entregar tu contraseña de Google a WhisperDnD. La aplicación conserva tokens para mantener y renovar la conexión. Puedes desconectarla desde la app y revocar el acceso desde las [conexiones de tu Cuenta de Google](https://myaccount.google.com/connections).

Desconectar o revocar acceso no borra por sí solo archivos ya guardados en Drive, copias locales ni contenido enviado previamente a otro proveedor. Si vuelves a procesar con Gemini una campaña sincronizada, se aplica el envío de texto y contexto descrito arriba.

## Almacenamiento, conservación y eliminación

En ejecución de escritorio, los archivos se almacenan en el equipo donde corre la aplicación. El navegador también conserva preferencias, claves de API y una copia de la autorización de Drive; algunos resultados se guardan temporalmente en el almacenamiento de la pestaña. La aplicación mantiene archivos de autorización y respaldos para recuperar la conexión. No se afirma que esos archivos estén cifrados por WhisperDnD.

Los datos de trabajo y sus copias pueden permanecer hasta que los elimines. No existe un plazo general de borrado automático garantizado. Cerrar la aplicación o desinstalarla no debe interpretarse como borrado de todo el contenido. La limpieza de archivos temporales o de una sesión no garantiza la eliminación de todas sus copias, exportaciones y respaldos.

Para eliminar información, revisa las campañas, audios, exportaciones y respaldos del equipo, el almacenamiento del navegador y las copias de Drive. Para dejar de usar una clave, elimínala de la configuración; para invalidarla, revócala también en su proveedor. Para la conexión de Drive, desconecta la app y revoca el acceso en Google. Las solicitudes relativas a copias bajo control del responsable pueden dirigirse al contacto indicado al inicio; el responsable no puede borrar directamente archivos que solo existan en tu equipo o en cuentas ajenas.

## Protección y decisiones del usuario

Protege el acceso al equipo, al perfil del navegador y a las cuentas conectadas. No compartas claves, tokens, registros ni respaldos sin revisar su contenido. Ningún sistema permite garantizar seguridad absoluta.

Puedes elegir entre transcripción local y remota, utilizar Drive de forma opcional y decidir qué contenido importas, procesas y compartes. Las funciones que dependen de un proveedor requieren transmitirle los datos necesarios.

## Compromisos sobre el uso de datos

**Propuesta pendiente de aprobación del responsable:** WhisperDnD no venderá datos personales ni utilizará el contenido de sesiones o los datos obtenidos de Google Drive para publicidad, vigilancia o entrenamiento de modelos generales. El envío a proveedores se limitará a las funciones descritas en esta política. Este compromiso corresponde al responsable de WhisperDnD y no sustituye las condiciones de cada proveedor externo.

## Cambios y consultas

La versión publicada indicará su fecha de actualización. Los cambios de finalidad o del uso de datos de Google se comunicarán antes de aplicar el nuevo tratamiento y se solicitará una nueva autorización cuando corresponda. Dirige tus consultas y solicitudes de acceso, corrección o eliminación al contacto indicado al inicio.
