# Preparación de Drive para la distribución de escritorio

Actualizado: 12 de noviembre de 2026.

## Estado comprobado

El archivo local `credentials.json` contiene un cliente de tipo `installed` (Aplicación de escritorio). La inspección solo emitió ese tipo, la presencia del identificador y el número de redirecciones; no mostró identificadores, secretos o tokens. No hay `GOOGLE_CREDENTIALS_JSON` dentro del `.env` inspeccionado.

La revisión de lectura de Google Cloud del 12 de noviembre de 2026 encontró el proyecto `whisper-dnd`, con nombre Whisper-DnD, audiencia externa y estado **Prueba**, con una cuenta de prueba. Hay dos clientes: Whisper-DnD (Escritorio) y WhisperDnD Web (Aplicación web). No se comparó el identificador del cliente local con los de la consola; el tipo coincidente no demuestra por sí solo que sean el mismo cliente.

La marca tiene nombre, correo de soporte y contacto del desarrollador configurados. Los campos de página principal, política de privacidad y términos están vacíos; el dominio autorizado es `whisperdnd.onrender.com`. Publicar app aparece deshabilitado, con indicación de completar la marca. El usuario confirmó como página pública https://whisperdnd.onrender.com/ y que todavía no dispone de política de privacidad ni términos. No se validó el contenido público de esa página en esta revisión.

La sección Acceso a los datos no muestra permisos declarados en ninguna categoría. El código solicita `https://www.googleapis.com/auth/drive.file`; falta alinear la declaración de Cloud con ese alcance, sin ampliarlo. La consola indica que la verificación no se requiere mientras la app está en Prueba; esto no confirma los requisitos al pasar a producción. No se comprobó la activación de Drive API en esta revisión.

No se cambió de cliente ni se renovó la sesión actual. No se copió la configuración real a una distribución, no se creó un EXE ni se modificó Google Cloud.

## Contrato implementado de archivos

En desarrollo se conservan los archivos y overrides actuales. Para una ejecución empaquetada, las ubicaciones predeterminadas son:

| Contenido | Ubicación |
| --- | --- |
| Configuración OAuth de la instalación | `%LOCALAPPDATA%/WhisperDnD/config/credentials.json` |
| Token personal de Drive | `%LOCALAPPDATA%/WhisperDnD/config/token.json` |
| Respaldo del token de esa persona | `%LOCALAPPDATA%/WhisperDnD/config/token_backup.json` |
| Configuración común de escritorio aprobada para el paquete | `<recursos>/oauth/drive-desktop.json` |

El cliente común identifica a WhisperDnD ante Google. No representa la cuenta ni la sesión del desarrollador. Solo se provisionan los campos de configuración OAuth de escritorio admitidos; nunca se extrae un token de ese archivo. Los archivos `token.json` y respaldos que accidentalmente aparezcan junto al programa no se consideran fuentes de autorización en modo empaquetado.

Precedencia de configuración empaquetada: ruta explícita del constructor; configuración existente del perfil; `GOOGLE_CREDENTIALS_JSON` del entorno; archivo común dedicado del paquete. En las fuentes predeterminadas empaquetadas se exige un cliente de escritorio con identificador y endpoints de autorización/token; no se convierte silenciosamente un cliente web. Las rutas explícitas de los consumidores existentes mantienen su contrato.

El perfil guarda una copia de la configuración común para que la edición o carga posterior no escriba dentro de los recursos del programa. El instalador futuro deberá añadir únicamente el archivo común aprobado a una lista explícita de recursos. Esta entrega no copia el `credentials.json` de desarrollo a esa ubicación ni genera una configuración de Google inventada.

Una configuración de Drive ausente o inválida no bloquea la preparación del resto de la aplicación. El intento de usar Drive conserva su diagnóstico; no se escribe una configuración inválida como fallback. Un fallo obligatorio al resolver el perfil de datos es distinto de un servicio opcional sin configurar.

## Trabajo pendiente en Google Cloud

Esta parte se realiza una vez para WhisperDnD, no una vez por computadora:

1. Confirmar el proyecto y la identidad de la aplicación que se utilizarán para distribución; mantener separados los entornos de desarrollo y producción cuando corresponda.
2. Confirmar Drive API y que el cliente local corresponde al cliente de escritorio aprobado para distribuir. La audiencia externa y la existencia de un cliente de escritorio ya se observaron en Cloud.
3. Preparar y revisar la política de privacidad según los flujos reales de datos y servicios de la app; definir los términos de uso. Validar los enlaces públicos y completar la marca con ellos y la página principal confirmada por el usuario. Declarar `drive.file` y revisar los requisitos que Google muestre antes de publicar. Durante pruebas externas, administrar las cuentas de prueba permitidas. No se ha cambiado ninguna de esas opciones en esta tarea.
4. Revisar y aprobar el JSON de configuración común que se incorporará al paquete. No incluir `.env`, `token.json`, `token_backup.json`, tokens Discord, campañas, audios o datos privados.
5. Probar autorización, retorno local, cancelación, renovación, desconexión y reconexión desde una build real y otro PC. Coordinar la conexión real con el usuario; no usar su sesión de desarrollo como prueba implícita.

Cada usuario instalará la app y conectará su cuenta desde el navegador de Google. No deberá crear un proyecto Cloud propio para usar la configuración distribuida de WhisperDnD.

## Límites pendientes antes de publicar

- Se prepararon borradores de [política de privacidad](legal/politica-de-privacidad.md) y [términos de uso](legal/terminos-de-uso.md). Todavía no son páginas públicas ni textos aprobados. Faltan responsable, contacto y decisiones sobre la versión web y distribución; ver [revisión de publicación](legal/revision-publicacion.md). Google describe los términos como opcionales para la marca; la política de privacidad sí debe estar accesible y reflejar los tratamientos reales.
- Aún no existe un ejecutable construido ni una configuración común añadida al paquete.
- Las pruebas de este bloque son offline y con perfiles/clientes/tokens ficticios.
- El callback actual, state/PKCE y el comportamiento de ventanas/puertos no se reescribieron aquí; requieren su verificación de escritorio antes de distribuir.
- Los tokens mantienen el formato JSON existente. Este bloque separa perfiles y elimina fallbacks de contenedor en modo empaquetado; no implementa cifrado adicional ni cambia la caché de tokens del navegador. Su protección completa sigue pendiente antes de publicación.
- `drive.file` es el permiso actual; no se ampliaron scopes. Debe comprobarse la continuidad de acceso a archivos existentes con el cliente que se apruebe para distribución.

Referencias: [OAuth de escritorio de Google](https://developers.google.com/identity/protocols/oauth2/native-app), [permisos de Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [preparación para producción](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).
