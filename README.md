# 🐉 WhisperDnD & Study / ⚡ AudioWorkspace

> **Plataforma Integral de Transcripción de Audio, Crónicas Vivas de Rol, Síntesis Académica y Apuntes Ejecutivos con IA.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Cloud%20Run%20Ready-2496ed.svg)](https://cloud.google.com/run)
[![PWA Ready](https://img.shields.io/badge/PWA-Installable%20Mobile%20%26%20Desktop-success.svg)](https://web.dev/progressive-web-apps/)
[![STT Groq](https://img.shields.io/badge/STT-Groq%20Whisper%20Large--v3-f55036.svg)](https://groq.com)
[![LLM Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20%2F%201.5-8e75ff.svg)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-152%20passing-brightgreen.svg)](#-pruebas-automatizadas)

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

### 2. 👥 Deduplicación Inteligente de Entidades (Retroactiva & Proactiva)
- **Filtro Proactivo**: Previene la fragmentación de entidades cuando un personaje se menciona por nombre de pila o título.
- **Deduplicación Retroactiva en Servidor**:
  - Al iniciar el servidor o cargar una campaña, el sistema analiza las entidades existentes.
  - Si detecta nombres que son subcadenas de otros más completos (ej. `"Octus"` y `"Octus Taconis"`), fusiona automáticamente su biografía, rol, notas y misiones en la ficha completa, añade el nombre corto a `aliases: ["Octus"]` y elimina de disco el fichero JSON duplicado huérfano.
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

### 6. 🎧 Integración Discord RPC (Local)
- **Detección Local**: Cliente WebSocket que localiza la instancia de Discord abierta en los puertos `6463` a `6472`.
- **Canal de Voz en Tiempo Real**: Detecta quién está en el canal, quién está hablando y vincula automáticamente sus identificadores al Roster de la partida.
- **Captura Dual de Audio (PC Host)**:
  - **Canal 1 (Izquierdo)**: Micrófono local.
  - **Canal 2 (Derecho)**: Audio de retorno (Discord/auriculares) mediante `soundcard`.
  - Etiquetado diferencial automático (`[Tu]` vs `[Discord]`).

---

### 7. 📄 Exportación & Sincronización en la Nube
- **Formatos de Descarga**:
  - **Markdown (`.md`)**: Tablas de misiones, directorio de PNJs y capítulos cronológicos.
  - **Microsoft Word (`.docx`)**: Formateado profesional con estilos universitarios o de fantasía medieval, tablas estilizadas y márgenes normalizados.
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

El proyecto incluye una suite completa de **152 pruebas automatizadas** que validan endpoints REST, aislamiento de espacios, deduplicación de entidades, exportadores Word/Markdown, motor Groq y cliente Gemini:

```bash
# Ejecutar toda la suite de pruebas
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# Resultado esperado:
# Ran 152 tests in ~16s -> OK
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
│   └── transcription/          # Groq Whisper, faster-whisper, YouTube y Discord RPC
├── static/                     # Activos web estáticos y cliente PWA
│   ├── icon-192.png            # Icono PWA (192x192 maskable)
│   ├── icon-512.png            # Icono PWA (512x512 maskable)
│   ├── manifest.json           # Manifiesto Web PWA oficial
│   ├── sw.js                   # Service Worker PWA (Network-first / Offline shell)
│   └── index.html              # Interfaz interactiva SPA (Dual Workspace)
├── tests/                      # Suite de 152 pruebas automatizadas
├── .dockerignore               # Exclusiones de construcción Docker
├── Dockerfile                  # Contenedor optimizado para Google Cloud Run
├── requirements.txt            # Dependencias de Python
├── main.py                     # Lanzador principal Uvicorn
└── render.yaml                 # Manifiesto de despliegue en Render
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.