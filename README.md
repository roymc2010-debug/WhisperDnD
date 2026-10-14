# 🐉 WhisperDnD & Study / ⚡ AudioWorkspace

> **Plataforma Integral de Transcripción de Audio, Crónicas Vivas de Rol, Síntesis Académica y Apuntes Ejecutivos con IA.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Cloud%20Run%20Ready-2496ed.svg)](https://cloud.google.com/run)
[![PWA Ready](https://img.shields.io/badge/PWA-Installable%20Mobile%20%26%20Desktop-success.svg)](https://web.dev/progressive-web-apps/)
[![STT Groq](https://img.shields.io/badge/STT-Groq%20Whisper%20Large--v3-f55036.svg)](https://groq.com)
[![LLM Gemini](https://img.shields.io/badge/LLM-Gemini%203.5%20%2F%203.8-8e75ff.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-234%20passing-brightgreen.svg)](#-pruebas-automatizadas)

---

## 📖 Visión General

**WhisperDnD & Study** (también conocido como **AudioWorkspace**) es una plataforma de alto rendimiento para transcripción, análisis y síntesis de audio de larga duración. Su arquitectura desacoplada combina dos motores de transcripción (**Groq Whisper Cloud** y **faster-whisper local**), modelos de lenguaje multimodal (**Google Gemini**), un motor de exportación a Word (`.docx`) y Markdown (`.md`), y una interfaz reactiva diseñada bajo rigurosos principios ergonómicos táctiles.

El sistema cuenta con una **arquitectura de espacios de trabajo duales estrictamente aislados**:

1. **🐉 Modo D&D (Grimorio de Campaña)**: Para mesas de rol (D&D 5e/5.5e, Pathfinder), con memoria acumulativa entre sesiones, deduplicación inteligente de entidades (PNJs y PCs), seguimiento vivo de misiones, registro de combate, coaching narrativo y exportación del Grimorio consolidado.
2. **⚡ Modo Work & Study (Productividad & Academia)**: Para conferencias universitarias, clases magistrales y reuniones ejecutivas, con una **Directiva Backend de Profundidad Explicativa** que produce apuntes exhaustivos, conservando analogías técnicas, fórmulas LaTeX (KaTeX), glosarios y compromisos adquiridos (*action items*).

---

## ✨ Características Principales

### 1. 🎛️ Arquitectura de Espacios de Trabajo Duales con Aislamiento Estricto
- **Selector Segmentado Superior**: Alterna instantáneamente de contexto con persistencia en `localStorage`.
- **Aislamiento Total de Pestañas y Datos en el Visor de Resultados**:
  - **Work & Study (4 pestañas permitidas)**:
    1. `[ 📄 Executive Briefing / Apuntes ]`: Resumen ejecutivo estructurado con soporte de fórmulas KaTeX.
    2. `[ ⭐ Puntos Clave y Glosario ]`: Conceptos clave, definiciones técnicas y taxonomías.
    3. `[ ✅ Tareas y Encargos ]`: Compromisos, fechas de entrega y tareas detectadas (desacopladas totalmente de misiones de rol).
    4. `[ 📝 Transcripción ]`: Transcripción completa con marcas de tiempo.
    *Ocultamiento estricto de elementos de rol (PNJs, PCs, Grimorio y Misiones).*
  - **D&D Roleplay (6 pestañas completas)**:
    1. `[ 📖 Crónica de Sesión ]`: Relato narrativo inmersivo.
    2. `[ 🗺️ Misiones Activas ]`: Registro de misiones nuevas, avanzadas y completadas.
    3. `[ 🎭 Directorio PNJs ]`: Fichas de personajes no jugadores con roles, ubicaciones y notas.
    4. `[ 🛡️ Directorio PCs ]`: Personajes jugadores y ficha personal del usuario.
    5. `[ 📜 Grimorio Completo (.md) ]`: Documento vivo acumulativo de campaña.
    6. `[ 📝 Transcripción ]`: Transcripción con etiquetado de hablantes.

---

### 2. 👥 Deduplicación Inteligente de Entidades, Ítems y Ubicaciones
- **Filtro Proactivo**: Previene la fragmentación de entidades cuando un personaje se menciona por nombre de pila o título.
- **Deduplicación Retroactiva en Servidor**:
  - Al iniciar el servidor o cargar una campaña, el sistema analiza las entidades existentes.
  - Si detecta nombres que son subcadenas de otros más completos (ej. `"Octus"` y `"Octus Taconis"`), fusiona automáticamente su biografía, rol, notas y misiones en la ficha completa, añade el nombre corto a `aliases: ["Octus"]` y elimina de disco el fichero JSON duplicado huérfano.
- **Deduplicación Bilingüe de Ítems y Lugares**:
  - Algoritmo de equiparación cruzada español-inglés para inventario y localizaciones (ej. `"Healing Potion"` &harr; `"Poción de Curación"`, `"The Well"` &harr; `"El Pozo"`), preservando la versión más descriptiva y consolidando portadores y notas sin duplicar entradas.
  - **Canonización de Reliquias Clave**: Unificación automática de artefactos centrales de campaña bajo nomenclaturas estandarizadas (ej. `"Collar / Rosario Sagrado de Zun (Medallón del Pozo)"`).
  - **Depuración Estructural de Sesiones y Campañas**: Eliminación de bloques redundantes (`detected_party`, `detected_pcs`) tanto en los registros de sesión como en la raíz de los archivos JSON de campaña para optimizar la ventana de contexto de Gemini y garantizar una persistencia limpia.
- **Botón Manual de Reparación**: Accesible con 1 clic en la cabecera de la Wiki de Campaña (`[ 🔄 Reparar y Fusionar Duplicados ]`).

---

### 3. 🎙️ Tres Vías de Ingesta Universal

| Vía de Entrada | Descripción | Casos de Uso |
| :--- | :--- | :--- |
| **🎙️ Grabación en Vivo (Mic)** | Captura en tiempo real con monitoreo visual VU (RMS) reactivo. Permite elegir entre **PC Host (Dual-Canal)** o **Móvil / Mic Navegador (`MediaRecorder`)**. | Partidas en Discord, partidas presenciales, conferencias en el aula, reuniones de trabajo. |
| **📺 Enlace de YouTube** | Descarga de audio optimizada con `yt-dlp` en streaming ligero y transcripción directa. Limpieza automática del audio descargado tras el procesado. | VODs de sesiones, tutoriales técnicos, podcasts, conferencias grabadas. |
| **📁 Archivo Local** | Carga por arrastrar y soltar de archivos de audio (`.mp3`, `.wav`, `.m4a`, `.webm`, `.flac`, `.ogg`). | Grabaciones de notas de voz, audios de grabadora, reuniones exportadas. |

---

### 4. 📱 Progressive Web App (PWA) & Micrófono Móvil
- **PWA Instalable Nativa**:
  - Instalable en **Android (Chrome)** e **iOS (Safari)** sin necesidad de pasar por tiendas de aplicaciones.
  - Manifest oficial configurado (`WhisperDnD & Study`, `display: standalone`, `orientation: portrait-primary`, `viewport-fit=cover`).
  - **Service Worker (`/sw.js`)**: Estrategia de red prioritaria (*Network-First*) con respaldo en caché (*Cache Fallback*) para navegación offline y cabecera `Service-Worker-Allowed: /`.
- **Grabación Móvil (`MediaRecorder` API)**:
  - Graba directamente con el micrófono de tu teléfono móvil a través de la Web Audio API con indicador VU a 60 fps.
- **Lanzador de Túneles HTTPS con 1 Clic**:
  - Scripts interactivos para habilitar permisos de micrófono y PWA en dispositivos remotos:
    - **Cloudflare Quick Tunnel**: `cloudflared tunnel --url http://localhost:8080` (gratuito, sin registro).
    - **Localtunnel**: `npx -y localtunnel --port 8080`.
    - **Lanzadores Windows**: `scripts\start_tunnel.bat` o `.\scripts\tunnel.ps1`.

---

### 5. ☁️ Preparado para Google Cloud Run & Docker

La aplicación incluye soporte nativo para despliegue en contenedores sin estado:

- **`Dockerfile` optimizado**: Basado en `python:3.10-slim` con `ffmpeg`, `libasound2` y dependencias compiladas.
- **Puerto Dinámico**: Lectura automática de `${PORT:-8080}` y enlace a `0.0.0.0`.
- **Almacenamiento Efímero en Memoria (`/tmp` y `outputs/`)**:
  - En Cloud Run o entornos Linux, el audio temporal se aloja en `/tmp` (tmpfs en RAM) y se elimina automáticamente tras la transcripción para evitar fugas de memoria.
  - Los documentos generados (`.docx`, `.md`) se canalizan a la carpeta configurable `outputs/` mediante las variables `WHISPER_INPUT_DIR`, `WHISPER_OUTPUT_DIR` y `WHISPER_CAMPAIGNS_DIR`.

---

### 6. 🎧 Integración Discord RPC, Grabación Dual y Persistencia de Timeline
- **Detección Local Discord RPC**: Cliente WebSocket que localiza la instancia de Discord abierta en los puertos `6463` a `6472`. Detecta en tiempo real quién está en el canal de voz y quién está hablando en cada instante.
- **Captura Dual de Audio en Pistas Separadas (PC Host)**:
  - **Canal 1 (Izquierdo / Mic)**: Entrada de micrófono local del usuario.
  - **Canal 2 (Derecho / Discord)**: Audio de retorno (Discord/auriculares) mediante loopback de `soundcard`.
- **Transcripción Aislada por Canales (Isolated Dual-Channel Transcription)**:
  - El backend separa físicamente el audio estéreo en dos pistas monoaurales temporales independientes.
  - Cada pista se procesa de forma aislada a través del motor de transcripción (Groq o Local).
  - **Independencia Total de Volumen**: Evita que el micrófono del usuario tape o enmascare las voces más bajas de los compañeros de Discord.
  - **Diálogo Simultáneo**: Si el usuario y otro jugador hablan al mismo tiempo, ambas intervenciones se transcriben nítidamente y se entrelazan en orden cronológico por marca de tiempo (`start`).
- **Persistencia de Timeline (`.timeline.json`)**:
  - Al detener la grabación, se genera automáticamente un archivo `session_<timestamp>.timeline.json` junto al archivo `.wav`.
  - **Reprocesado Local sin Pérdida**: Si se re-transcribe o reprocesa una sesión desde un archivo local, el backend detecta y asocia automáticamente su `.timeline.json`, conservando la diarización de quién habló en cada momento sin requerir una conexión activa a Discord.

---

### 7. 📄 Exportación Granular & Sincronización en la Nube
- **Formatos de Descarga y Modalidades de Crónica en Word (`.docx`)**:
  - **`📄 Sesión Actual (.docx)`**: Formato completo para el Dungeon Master con transcripción de combate, notas de dirección y coaching narrativo personal.
  - **`👥 Versión para Jugadores (.docx)`**: Crónica narrativa limpia de la sesión sin notas personales de DM ni reflexiones privadas, lista para compartir con la mesa.
  - **`📚 Toda la Campaña (.docx)`**: Grimorio consolidado que compila el libro vivo de todas las sesiones de la aventura.
  - **`⬇️ Transcripción (.txt)` & `📋 Copiar`**: Exportación rápida de texto plano y copiado directo de cualquier pestaña con marcas de tiempo.
  - **Selector Dinámico en Wiki de Campaña**: Permite descargar cualquier sesión histórica individual (con o sin notas de rol) directamente desde el explorador wiki.
  - **Barra de Acciones Segmentada y Menú de Herramientas IA (`✨ Herramientas IA ▾`)**: Interfaz ergonómica que agrupa las descargas en un pill de un solo renglón y aísla las funciones de reprocesado ("Regenerar con Gemini" y "Traducir") en un menú secundario con descripciones claras.
  - **Pestañas Compactas Anti-Desbordamiento**: Visualización horizontal adaptativa de las 6 pestañas de rol sin partirse en múltiples renglones.
- **Exportación e Importación Completa de Campañas (ZIP / JSON Bundle)**:
  - **Exportar Campaña (`GET /api/campaigns/{id}/export`)**: Empaqueta en un archivo comprimido descargable (`Campaña_[Nombre]_[Fecha].zip`) toda la configuración de la campaña (DM, jugadores, Discord, clases), las entidades de la Wiki (PNJs, lugares, misiones, protagonistas), crónicas de sesión y transcripciones (`.txt`, `.md`, `.docx`), junto a su `manifest.json`.
  - **Importar Campaña (`POST /api/campaigns/import`)**: Permite subir archivos `.zip` o `.json` para restaurar instantáneamente el estado completo de la campaña, regenerar el Grimorio vivo y, si Google Drive está conectado, generar una copia de respaldo automática en la nube.
  - **Persistencia Multi-Dispositivo**: Al importar o sincronizar una campaña en el servidor (ej. `whisperdnd.onrender.com`), las sesiones, fichas y Wiki quedan registradas centralmente, permitiendo que cualquier dispositivo (móvil, tablet o PC) acceda inmediatamente a los mismos datos.
- **Google Drive OAuth 2.0 Dinámico & Sincronización Bidireccional**:
  - Detección automática del dominio en producción mediante `RENDER_EXTERNAL_URL` o cabeceras de proxy (`Host`, `X-Forwarded-Proto`).
  - Soporte de rutas duales de callback: `/oauth2callback` y `/api/auth/drive/callback`.
  - Soporte de inyección de credenciales mediante variables de entorno en Render/Cloud Run (`GOOGLE_CREDENTIALS_JSON` y `GOOGLE_TOKEN_JSON`).
  - **Sincronización Bidireccional y Restauración Automática**:
    - **Startup en la nube**: Al iniciar el servidor en entornos efímeros (como Render Docker), si Google Drive está conectado, descarga y restaura automáticamente el estado de todas las campañas (`.json`) y notas/crónicas (`.md`, `.docx`, `.txt`).
    - **Botón `[ 🔄 Sincronizar Campañas con Drive ]`**: Disponible en la cabecera, en la sección de Ajustes y en el gestor de "Mis Campañas" para descargar y fusionar campañas existentes y respaldar las locales en tiempo real sin recargar la página.
    - **Respaldos automáticos**: Cada guardado o modificación de campaña sincroniza el estado directamente con Google Drive en segundo plano.

---

### 8. 🔑 Credenciales Multi-Tenant en el Cliente (BYOK - Bring Your Own Key)
- **Ajustes Personales en el Navegador**:
  - Los usuarios pueden ingresar sus claves personales de **Groq** (`GROQ_API_KEY`) y **Gemini** (`GEMINI_API_KEY`) desde la sección `[ ⚙️ Ajustes ]`.
  - Las claves se almacenan exclusivamente en el navegador (`localStorage: user_groq_key, user_gemini_key`) y se envían cifradas en cada petición mediante cabeceras HTTP (`X-Groq-Api-Key`, `X-Gemini-Api-Key`).
- **Prioridad Backend Estricta (Cabeceras > Entorno)**:
  - El servidor prioriza las llaves enviadas por el cliente sobre las variables de entorno locales.
  - Si un usuario no proporciona claves y el servidor no tiene variables configuradas, se devuelve un error HTTP 401 estructurado (`{"error": "API_KEYS_REQUIRED", "message": "..."}`) que redirige automáticamente a la pantalla de Ajustes.

---

### 9. 🧙‍♂️ Gestión de Personajes, Coaching Narrativo y Crónicas Vivas
- **Vista Dedicada "Mi Personaje"**: Selector jerárquico **Campaña ➔ Personaje ➔ Trasfondo** con sincronización en tiempo real.
- **Soporte Multi-Personaje por Campaña**: Múltiples personajes registrados en la misma campaña con historias y personalidades independientes (`character_backstories` y fichas de roster sin sobreescrituras).
- **Coaching Narrativo Exclusivo del Personaje Activo (⭐)**:
  - El informe de *Roleplay Coaching* evalúa única y exclusivamente al personaje marcado con estrella (`is_user_character: true`), sin diluirse con otros jugadores o PNJs.
  - La evaluación se fundamenta de forma estricta en las intervenciones y diálogos efectivamente pronunciados por el personaje durante la sesión, contrastándolos con su trasfondo y código moral.
- **Separación Estricta de Lore vs. Acciones de Hoy**:
  - Inyección de contexto histórico y recap que previene confusiones en el LLM entre antecedentes pasados y los acontecimientos reales de la sesión actual.
  - Las intenciones y misiones del día se vinculan de forma nítida con los objetivos activos.
- **Escenas Paralelas y Sobrecarga Mágica**:
  - Instrucciones de crónica para capturar arcos divididos simultáneos (ej. combate exterior mientras otro grupo investiga en un ático) y registrar con fidelidad eventos de magia salvaje o sobrecarga de artefactos mágicos.
- **Idempotencia de Sesión y Regeneración Multilingüe Segura**:
  - Al alternar el idioma de la crónica (`English` &harr; `Español`) o solicitar el reprocesado de una sesión, el sistema preserva de forma estricta el `session_number` activo en lugar de autoincrementar el contador de campaña (`last_session + 1`), garantizando que la sesión en curso se actualice in-situ sin generar sesiones fantasma o duplicadas.
  - Los endpoints de la API (`switch_summary_language` y `reprocess_campaign`) y el cliente web sincronizan bidireccionalmente el identificador de sesión y campaña en el payload `TranscribeResponse`.
- **Creación en Caliente**: Botón `[ + Crear Nuevo Personaje ]` para incorporar nuevos personajes a cualquier campaña y persistirlos de inmediato en disco y en Google Drive.
- **Diseño Ergonómico y Seguro**: Prevención estricta de selección accidental en áreas de texto (`user-select: none`) y guías de redacción separadas visualmente de la caja de edición.

---

### 10. ⚡ Auto-Cierre Limpio y Lanzamiento Silencioso (Windows)
- **Auto-Cierre por Baliza (Beacon)**: Detección instantánea de cierre de pestaña/ventana mediante `navigator.sendBeacon('/api/shutdown')` para liberar memoria y recursos del sistema sin procesos huérfanos.
- **Lanzador Invisible (`WhisperDnD.vbs`)**: Ejecución en segundo plano sin ventana de consola CMD/Python intrusiva.
- **Scripts de Control**: `iniciar_whisper_dnd.bat` para arranque automático del navegador y `detener_app.bat` para detención forzada limpia.

---

### 11. 🛡️ Motor Anti-Alucinaciones de Whisper y Normalizador Fonético de Roster
- **Limpieza de Prefijos y Siglas Parasitarias**:
  - Filtro estricto que elimina prefijos residuales de subtitulado (`E. `, `B. `, `T. `, `I. `) tanto al comienzo como intercalados tras puntuación en oraciones.
  - Detección y supresión de secuencias de siglas en bucle infinito (`S.I.C.I.`, `S.T.A.A.R.`, etc.).
  - Poda de bucles de repetición multi-palabra y cadenas cíclicas antes de la persistencia del texto.
- **Calibración de Umbrales STT**:
  - `no_speech_prob > 0.55` y `compression_ratio > 1.8` para descarte de segmentos fantasma.
  - `condition_on_previous_text=False` en Whisper local para evitar que alucinaciones tempranas se propaguen recursivamente por toda la transcripción.
- **Normalizador Fonético Universal de Roster**:
  - Reemplazo y corrección fónica automática de nombres de personajes y entidades (ej. `Atou`, `Atú` &rarr; `Atou`).
  - **Preservación Contextual Gramatical**: Análisis léxico y sintáctico que previene la corrupción de sustantivos comunes legítimos (ej. `"el ataúd"`, `"un ataúd"`, `"dentro del ataúd"` se mantienen intactos, mientras que `"ataúd atacó"` o vocativos se corrigen a `"Atou"`).

---

## 🛠️ Requisitos Previos

1. **Python 3.10 o superior**:
   ```bash
   python --version
   ```
2. **FFmpeg**:
   Requerido para la decodificación de audio, segmentación ultrarrápida y `yt-dlp`.
   - **Windows (Winget)**:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **macOS (Homebrew)**:
     ```bash
     brew install ffmpeg
     ```
   - **Linux (Ubuntu/Debian)**:
     ```bash
     sudo apt update && sudo apt install ffmpeg libasound2
     ```
3. *(Opcional para túnel móvil)* **Node.js** (para `npx localtunnel`) o **Cloudflare CLI** (`cloudflared`).

---

## 🚀 Instalación y Puesta en Marcha Local

### 1. Clonar el Repositorio
```bash
git clone https://github.com/roymc2010-debug/WhisperDnD.git
cd WhisperDnD
```

### 2. Crear y Activar el Entorno Virtual
```powershell
# En Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# En Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copia el archivo de ejemplo `.env.example` a `.env`:
```powershell
Copy-Item .env.example .env
```
Edita `.env` con tus claves API:
```env
# Clave API de Google Gemini (Requerida para síntesis y crónicas)
# Obtén tu clave en: https://aistudio.google.com/
GEMINI_API_KEY=tu_clave_gemini_aqui

# Clave API de Groq Cloud (Opcional, pero muy recomendada para transcripción ultrarrápida)
# Obtén tu clave gratuita en: https://console.groq.com/
GROQ_API_KEY=tu_clave_groq_aqui

# Configuración del Servidor
PORT=8080
HOST=0.0.0.0
```

### 5. Iniciar la Aplicación
```bash
python main.py
```
Abre tu navegador en: **`http://localhost:8080`**

---

## 🐳 Despliegue con Docker y Google Cloud Run

### Construcción Local de la Imagen Docker
```bash
docker build -t whisperdnd:latest .
docker run -p 8080:8080 --env-file .env whisperdnd:latest
```

### Despliegue en Google Cloud Run
```bash
# 1. Autenticar en Google Cloud
gcloud auth login
gcloud config set project TU_PROYECTO_GCP

# 2. Desplegar directamente desde el código fuente
gcloud run deploy whisperdnd \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY="tu_clave_gemini",GROQ_API_KEY="tu_clave_groq" \
  --memory 2Gi \
  --cpu 2
```

---

## 🌐 Conexión desde el Móvil (PWA & Túnel HTTPS)

1. Con el servidor corriendo localmente, ejecuta el túnel:
   - **Windows**: Doble clic en `scripts\start_tunnel.bat` o en PowerShell: `.\scripts\tunnel.ps1`.
   - **Cloudflare**: `cloudflared tunnel --url http://localhost:8080`.
   - **Localtunnel**: `npx -y localtunnel --port 8080`.
2. Abre la URL HTTPS en tu smartphone (ej. `https://xxxx.trycloudflare.com`).
3. **Instala la PWA**:
   - En **Android (Chrome)**: Toca `⋮` &rarr; *"Instalar aplicación"*.
   - En **iOS (Safari)**: Toca Compartir `⎋` &rarr; *"Añadir a pantalla de inicio"*.
4. Selecciona la fuente **📱 Móvil / Mic Navegador** y pulsa *"Iniciar Grabación"*.

---

## 🧪 Pruebas Automatizadas

El proyecto incluye una suite completa de **234 pruebas automatizadas** que validan endpoints REST, aislamiento de espacios, normalización fonética, transcripción dual aislada, persistencia de timeline, deduplicación de entidades e ítems, exportadores Word/Markdown, motor Groq, cliente Gemini y gestión multi-personaje:

```bash
# Ejecutar toda la suite de pruebas
.\.venv\Scripts\python.exe -m pytest -q

# Resultado esperado:
# 234 passed in ~12s
```

---

## 📂 Estructura del Proyecto

```text
WhisperDnD/
├── data/                       # Almacenamiento local persistente
│   ├── campaigns/              # Ficheros JSON de campañas y fichas de personajes
│   ├── input/                  # Archivos de audio subidos o grabados localmente
│   └── output/                 # Documentos .md y .docx generados
├── outputs/                    # Directorio de trabajo unificado para exportaciones
├── docs/                       # Guías técnicas y manuales de arquitectura
│   └── mobile_pwa_and_tunnel.md# Manual detallado de PWA y túneles HTTPS
├── scripts/                    # Scripts de automatización y túneles
│   ├── start_tunnel.bat        # Lanzador rápido de túnel para Windows
│   ├── tunnel.ps1              # Script PowerShell interactivo de túneles
│   └── test_transcription.py   # Diagnóstico de audio por consola
├── src/                        # Código fuente modular
│   ├── api/                    # Servidor FastAPI, endpoints REST y WebSockets
│   │   ├── server.py           # Enrutamiento, PWA, aislamiento de tabs y deduplicación
│   │   ├── app.py              # Alias de inicialización de FastAPI
│   │   └── templates/          # Plantilla HTML sincronizada
│   ├── exporters/              # Generadores de Word (.docx) y Markdown (.md)
│   ├── storage/                # Gestor de campañas vivas y cliente Google Drive
│   ├── summarizer/             # Cliente Gemini, directiva académica y prompts
│   └── transcription/          # Groq Whisper, faster-whisper, YouTube, Discord RPC y Roster Normalizer
├── static/                     # Activos web estáticos y cliente PWA
│   ├── icon-192.png            # Icono PWA (192x192 maskable)
│   ├── icon-512.png            # Icono PWA (512x512 maskable)
│   ├── manifest.json           # Manifiesto Web PWA oficial
│   ├── sw.js                   # Service Worker PWA (Network-first / Offline shell)
│   └── index.html              # Interfaz interactiva SPA (Dual Workspace)
├── tests/                      # Suite de 234 pruebas automatizadas
├── .dockerignore               # Exclusiones de construcción Docker
├── Dockerfile                  # Contenedor optimizado para Google Cloud Run
├── requirements.txt            # Dependencias de Python
├── main.py                     # Lanzador principal Uvicorn
└── render.yaml                 # Manifiesto de despliegue en Render
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.