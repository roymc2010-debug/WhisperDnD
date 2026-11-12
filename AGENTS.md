# WhisperDnD — Arquitectura de Módulos y Verificación

## 1. Mapa de Módulos
- `src/api/`: Servidor FastAPI y endpoints REST (`routers/audio.py`, `routers/transcription.py`, dependencias y configuración).
- `src/transcription/`: Motor de transcripción local y remoto (`local_whisper.py`, gestión de modelos Whisper, segmentación de audio).
- `src/summarizer/`: Generación de resúmenes de sesiones de D&D, prompts de contexto y enlace con modelos de lenguaje.
- `src/storage/`: Persistencia local, tokens de autenticación y cliente de Google Drive (`drive_client.py`).
- `src/exporters/`: Exportación estructurada de sesiones (Markdown y DOCX).
- `static/`: Frontend web SPA (`index.html`, Tailwind CSS, `js/app.js`, `js/api.js`, `js/audio.js`).
- `tests/`: Suite de pruebas automatizadas con `pytest`.

## 2. Pautas de Exploración Mínima en el Proyecto
- **Foco por módulo:** Dirigir la inspección directamente al módulo afectado por la tarea; evitar escaneos cruzados o lecturas de archivos fuera del alcance.
- **Evitar búsquedas recursivas en carpetas pesadas:** No realizar búsquedas recursivas ni escaneos masivos en directorios de dependencias o datos (`.venv/`, `node_modules/`, `models/`, `data/`, `outputs/`); consultarlos puntualmente solo si la tarea técnica lo exige.
- **Inspección dirigida:** Priorizar la lectura de rangos de líneas sobre archivos objetivo específicos antes de leer archivos completos.

## 3. Protocolo de Verificación
- **Pruebas pertinentes:** Ejecutar las pruebas existentes relacionadas con el cambio: `pytest` para backend Python y las pruebas o compilación frontend correspondientes para HTML/CSS/JavaScript.
- **Validación proporcional:** Comprobar sintaxis, dependencias o compilación según los archivos modificados. Empezar con las secciones relevantes y ampliar la inspección cuando una dependencia concreta lo requiera.

## 4. Guías específicas bajo demanda
- Al trabajar en crónicas, prompts narrativos, continuidad o canon, consultar [Crónicas y canon](docs/agent-guides/cronicas-y-canon.md).
- Al investigar procesamiento, contaminación entre sesiones o eficiencia de contexto, consultar [Contexto y diagnóstico](docs/agent-guides/contexto-y-diagnostico.md).
- Al diseñar o revisar límites de módulos, persistencia, reintentos o recuperación de trabajos, consultar [Arquitectura y recuperación](docs/agent-guides/arquitectura-y-recuperacion.md). Usar `architecture-decision-records` para decisiones importantes y `find-skills` para búsquedas; los resultados del catálogo requieren revisión antes de incorporarse.
- Leer solo la guía pertinente. Son instrucciones de desarrollo; no implican cambios ya implementados en la app ni autorizan modificar campañas, instalar dependencias o consumir servicios.
- Para interfaz, reutilizar Impeccable y `emil-design-eng`; para problemas móviles de la web/PWA, usar `mobile-native` cuando esté disponible. Mantener la tecnología y los patrones del proyecto, sin añadir bibliotecas por los ejemplos de una skill.
