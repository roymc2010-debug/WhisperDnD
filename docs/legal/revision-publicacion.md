# Revisión previa a publicar los textos de WhisperDnD

Fecha de preparación: 12 de noviembre de 2026. Estado: borradores; no se publicaron páginas ni se modificó Google Cloud.

## Etapa acordada: prueba privada

El usuario distribuirá inicialmente la app a personas conocidas para recibir opiniones. La elección de responsable público y contacto, así como la publicación de estos textos, queda aplazada. No se completarán con datos personales obtenidos de otras fuentes. Esto no convierte la beta en exenta de informar a quienes prueben sobre grabaciones, servicios externos y datos enviados.

Render se usó como vista previa. El usuario plantea convertirlo más adelante en una página que explique la app mediante video o diapositivas y permita recibir reportes de errores. No está autorizado ni implementado aquí un formulario de recepción, alojamiento de archivos ni procesamiento web para terceros.

Se añadió en Ajustes la descarga manual de un reporte de texto con metadatos acotados de fallos. No copia registros completos ni incluye sesiones, claves o tokens y no hace envíos automáticos. Ver [alcance y verificación](../reviews/support-report-20261112.md).

## Decisiones pendientes del responsable

- Nombre del responsable y correo público de privacidad/soporte: aplazados hasta preparar la publicación.
- Confirmar el diseño definitivo de Render y las condiciones de recepción de reportes antes de habilitar envíos. No presentar almacenamiento del servidor como almacenamiento en el equipo del visitante. Si se ofrece procesamiento web, revisar su despliegue, separación entre usuarios, registros y retención antes de redactar ese aviso.
- Aprobar o ajustar el compromiso propuesto de no vender datos, no usarlos para publicidad/vigilancia ni para entrenar modelos generales. El código revisado no acredita por sí solo todas las prácticas del responsable ni las de proveedores.
- Identidad legal, domicilio y requisitos aplicables a solicitudes de privacidad; no se ha hecho una determinación de cumplimiento por jurisdicción.
- Precio/gratuidad de una futura distribución pública y condiciones de soporte. El usuario eligió para esta etapa licencia de evaluación privada, sin venta ni redistribución de la app: [LICENSE](../../LICENSE) y [TERMS.md](../../TERMS.md). No se inventa una limitación absoluta de responsabilidad.

## Evidencia del alcance técnico

| Tema | Código revisado | Consecuencia para el texto |
| --- | --- | --- |
| Motor local o Groq | `static/js/app.js`, `src/transcription/groq_whisper.py` | Local se refiere a transcripción; Groq recibe audio y parámetros/indicaciones. |
| Gemini | `src/summarizer/gemini_client.py`, flujo de contexto en `src/api/server.py` | La generación usa texto y contexto; no prometer procesamiento íntegramente local. |
| Drive | `src/storage/drive_client.py`, `src/api/routers/drive.py` | `drive.file`, metadatos, carga/actualización y descarga; desconexión elimina tokens locales, no revoca por sí misma en Google ni borra documentos. |
| Navegador | `static/js/api.js`, `static/js/drive.js`, `static/js/app.js` | Claves, token de Drive, preferencias y caché de resultados; no prometer cifrado propio. |
| Diagnóstico y uso | `src/summarizer/generation_diagnostics.py`, `src/storage/quota_tracker.py` | Estados, tiempos, errores y contadores; no prometer ausencia global de contenido en todos los logs. |

No se inspeccionaron audios, contenidos de campañas, valores de claves o tokens para redactar estos documentos. No se hicieron llamadas a Groq/Gemini ni se conectó o sincronizó Drive. El acceso público a la página principal mediante la herramienta web no permitió validar su contenido; no se asumió que el despliegue coincide con el checkout local.

## Preparación de la publicación

1. Resolver las decisiones anteriores y retirar todos los avisos de borrador, propuestas y campos pendientes únicamente después de revisarlos.
2. Preparar páginas públicas en el mismo dominio que la página principal. Rutas propuestas, todavía inexistentes/no comprobadas: `/privacidad` y `/terminos`. Añadir enlaces visibles desde la página principal y la aplicación. No se añadieron rutas ni cambios de interfaz en este bloque.
3. Verificar acceso sin iniciar sesión y contenido real de las páginas desplegadas. Revisar también la descripción pública de la app y la titularidad del dominio cuando Google lo solicite.
4. Completar la marca OAuth con las URLs verificadas y alinear la declaración de `drive.file`; revisar los requisitos que muestre Google antes de publicar. Los términos son opcionales para la marca según la documentación de Google, y no deben presentarse como bloqueo obligatorio por sí solos.
5. Comprobar protección de tokens y el flujo OAuth de escritorio pendiente antes de distribuir. Un texto de privacidad no sustituye esas comprobaciones.

## Fuentes consultadas

- [Política de datos de usuarios de servicios API de Google](https://developers.google.com/terms/api-services-user-data-policy): transparencia sobre acceso, uso, almacenamiento y compartición, y limitación a lo declarado.
- [Verificación de marca de OAuth](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification): página principal pública con descripción y enlaces, política en el mismo dominio y términos opcionales.

Los textos son una propuesta basada en el funcionamiento revisado, no una certificación de cumplimiento legal ni de aprobación por Google.
