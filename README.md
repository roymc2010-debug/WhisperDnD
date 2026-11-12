# WhisperDnD

Aplicación para grabar o importar audio, transcribir sesiones, revisar crónicas de rol y organizar campañas. Incluye Trabajo y estudio para apuntes y documentos de reuniones, exportación Markdown/Word y sincronización opcional con Google Drive.

**Estado: evaluación privada, antes del primer instalador EXE.** Se ejecuta desde código. El arranque de escritorio y la separación de datos están preparados para pruebas manuales en Windows; todavía no hay un instalador probado en otro PC.

## Funciones actuales

- Grabación de micrófono y audio del sistema/Discord según el modo y los dispositivos compatibles.
- Transcripción remota con Groq o local con faster-whisper.
- Generación con Gemini de crónicas, apuntes y documentos según el espacio de trabajo.
- Campañas con grupo, DM, personajes, sesiones, Wiki y revisión de propuestas antes de incorporarlas.
- Exportación Markdown/DOCX, Drive opcional y reporte descargable de errores.

Las transcripciones y resultados de IA pueden contener errores: deben revisarse. Elegir transcripción local no convierte en local la generación con Gemini o la sincronización con Drive.

## Obtener y configurar las API keys

| Servicio | Uso | Enlace oficial |
| --- | --- | --- |
| Groq | Transcripción remota; no se requiere para Whisper local | [Conseguir una clave de Groq](https://console.groq.com/keys) |
| Gemini | Generación de crónicas y apuntes, incluso con transcripción local | [Conseguir una clave en Google AI Studio](https://aistudio.google.com/apikey) |
| Drive | Guardado y sincronización opcionales | Conexión OAuth; no se pega una API key de Drive |

En **Ajustes**, abre el enlace del proveedor, consigue tu clave, pégala en su campo y pulsa **Guardar Llaves**. Después utiliza **Probar Conexión**. Groq y Gemini se consultan en paralelo; Drive se consulta por separado. Verificar acceso no garantiza que todos los modelos estén habilitados o que haya cuota para una sesión completa.

Las claves se conservan en el almacenamiento del navegador del origen utilizado. Revisa cuotas y costes en tu cuenta antes de procesar. No compartas claves ni las incluyas en commits, capturas o reportes. Los enlaces no crean cuentas, aceptan condiciones ni generan claves automáticamente.

Fuentes: [Groq Quickstart](https://console.groq.com/docs/quickstart) y [claves de Gemini](https://ai.google.dev/gemini-api/docs/api-key).

## Ejecutar desde código

Las comprobaciones actuales utilizan Python 3.11.9 en Windows. No se certifica compatibilidad con todas las versiones de Python o Windows. La captura por proceso depende del sistema y hardware compatible; macOS y Linux no son plataformas certificadas para el futuro instalador Windows.

Necesitas Python y las dependencias de [requirements.txt](requirements.txt). FFmpeg y ffprobe son necesarios para determinados formatos, importaciones y segmentación. La transcripción local puede necesitar descargar un modelo. Node se utiliza para pruebas y herramientas frontend; no es un requisito previsto para quien instale el futuro EXE.

Preparar un entorno de desarrollo en PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No reinstales dependencias si ya tienes el entorno y solo quieres abrir la app. El archivo de requisitos establece mínimos; todavía no bloquea un entorno reproducible de build.

### App habitual y datos existentes

Abre `iniciar_whisper_dnd.bat`. Utiliza el entorno y la ubicación habitual del checkout. Modificar código no actualiza un proceso que ya está abierto: reinícialo cuando no haya grabación, procesamiento o transferencia activos, y conserva un respaldo antes de probar cambios con datos reales.

El arranque histórico permite usos de desarrollo/red y no debe confundirse con el perfil de escritorio enlazado solo a loopback. No se anuncia como un servicio web público con aislamiento entre usuarios.

### Prueba separada antes del EXE

1. Abre `comprobar_antes_del_exe.bat` para revisar el entorno sin arrancar el servidor.
2. Abre `probar_antes_del_exe.bat` para iniciar el perfil separado en `http://localhost:8082`.
3. Sigue la [guía manual](docs/prueba-manual-antes-del-exe.md).

La prueba utiliza `%LOCALAPPDATA%/WhisperDnD-Pruebas`, no copia campañas o autorizaciones del desarrollador y no carga `.env`. Sus datos y ajustes pueden empezar vacíos. Mantén abierta la ventana de inicio; cuando esté inactiva, Ctrl+C cierra el servidor. No lo cierres a la fuerza durante una operación.

La entrada común es `desktop.py`. Reserva el puerto, identifica la instancia y evita abrir un servidor ajeno. El BAT todavía requiere el Python de desarrollo: **no es un instalador**.

## Datos y Drive

En desarrollo se mantienen las rutas y overrides existentes. El modo escritorio separa grabaciones, exportaciones, campañas, cuotas, modelos, configuración y logs del programa. No migra campañas automáticamente.

Cada persona conecta su propia cuenta de Drive; las autorizaciones personales no deben distribuirse. Antes de distribuir se necesita una configuración común aprobada del cliente OAuth de escritorio y usuarios permitidos mientras el proyecto esté en Prueba. No se ha incluido esa configuración ni se ha probado la autorización desde una build real. Consulta la [preparación de Drive](docs/drive-desktop-distribution.md).

La protección completa de tokens sigue pendiente antes de distribuir a terceros. Desconectar no borra documentos de Drive ni todas las copias locales. Consulta [PRIVACY.md](PRIVACY.md).

## Reportar problemas

En Ajustes, descarga **Reporte de errores**, revísalo y envíalo por el canal acordado con quien te invitó. Añade qué estabas haciendo, qué esperabas, qué ocurrió y la hora aproximada.

El TXT contiene versión, entorno básico y hasta 200 fallos registrados. No envía nada automáticamente ni adjunta audios, campañas, claves o tokens. No cubre todos los fallos del navegador/arranque ni recupera errores anteriores a su incorporación. El registro completo del servidor es distinto y puede contener detalles privados de operaciones.

No subas `.env`, credenciales, tokens, campañas, grabaciones, modelos o respaldos a GitHub. Las investigaciones locales y sus copias internas se mantienen fuera del conjunto publicado.

## Pruebas

Backend con directorios temporales y conexiones salientes bloqueadas:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/run_offline_tests.py -q
```

Frontend:

```powershell
node --test tests/frontend/*.test.cjs
```

Arranque real con perfil temporal, sin navegador ni servicios externos:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_desktop_smoke.py
```

Estas comprobaciones no sustituyen captura real, autorización de cuentas, generación con el proveedor ni pruebas en un Windows limpio. No ejecutes grabaciones o solicitudes facturables automáticamente sin coordinarlas.

## Desarrollo y distribución

- [Contribuciones y reportes](CONTRIBUTING.md).
- [Hoja de ruta Windows](docs/windows-release-roadmap.md).
- [Guía de prueba manual](docs/prueba-manual-antes-del-exe.md).

Antes de distribuir quedan la revisión manual y sus correcciones, captura y OAuth reales, protección de autorizaciones, receta reproducible, dependencias nativas, avisos de licencias, instalador y pruebas de instalación/actualización/desinstalación. La web pública de presentación y recepción de reportes está pendiente.

## Licencia y documentos

WhisperDnD utiliza una **licencia de evaluación privada** para personas invitadas. No se permite vender ni redistribuir la app y no es una licencia de código abierto. Consultar el código en GitHub no amplía ese permiso.

- [LICENSE](LICENSE): permiso y restricciones del software original.
- [TERMS.md](TERMS.md): condiciones de la prueba privada.
- [PRIVACY.md](PRIVACY.md): aviso actual; la política pública/OAuth completa sigue en borrador.
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md): inventario preliminar; los terceros conservan sus propias licencias.

La identidad y contacto públicos del responsable siguen pendientes de confirmación. Estos documentos no certifican aprobación de Google ni cumplimiento de todas las obligaciones del futuro instalador.
