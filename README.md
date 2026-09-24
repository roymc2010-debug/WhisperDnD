# 🐉 WhisperDnD / ⚡ AudioWorkspace

> **Plataforma Integral de Transcripción de Audio, Crónicas Vivas de Rol y Síntesis Ejecutiva con Inteligencia Artificial**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-v3-38bdf8.svg)](https://tailwindcss.com)
[![Groq Whisper](https://img.shields.io/badge/STT-Groq%20Whisper%20Large--v3-f55036.svg)](https://groq.com)
[![faster-whisper](https://img.shields.io/badge/STT-faster--whisper-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini%202.5%20%2F%201.5-8e75ff.svg)](https://ai.google.dev/)
[![PWA Ready](https://img.shields.io/badge/PWA-Installable%20Mobile%20%26%20Desktop-success.svg)](https://web.dev/progressive-web-apps/)

---

## 📖 Visión General

**WhisperDnD** (también conocido como **AudioWorkspace**) es una aplicación web local de alto rendimiento diseñada para transcribir, analizar y sintetizar audio de larga duración. Su arquitectura integra dos motores de reconocimiento de voz (**Groq Whisper Cloud** y **faster-whisper local**), modelos de lenguaje de última generación (**Google Gemini**) y una interfaz reactiva diseñada bajo los más exigentes estándares de diseño táctil (`@ui-ux-pro-max`, `impeccable` y `emil-design-eng`).

La aplicación incorpora una **arquitectura de espacios duales** que adapta la experiencia visual, operativa y los modelos de IA según el contexto:
1. **🐉 Modo D&D (Grimorio de Campaña)**: Diseñado para mesas de rol (D&D 5e/5.5e, Pathfinder, etc.), con seguimiento continuo de misiones, personajes (PCs y PNJs), coaching de rol narrativo y generación de crónicas épicas continuas.
2. **⚡ Modo Work & Study (Productividad & Academia)**: Diseñado para conferencias universitarias, clases magistrales y reuniones ejecutivas, con una **Directiva de Profundidad Explicativa** que produce apuntes exhaustivos, conservando ejemplos reales, casos de estudio y derivaciones técnicas.

---

## ✨ Características Principales

### 1. 🎛️ Arquitectura de Espacios de Trabajo Duales
- **Selector Segmentado Superior**: Alterna instantáneamente entre contextos con objetivos táctiles de $\ge 44 \times 44\text{ px}$ y persistencia en `localStorage`.
- **Tema A: D&D (`theme-dnd`)**:
  - Estética de grimorio de fantasía oscura: Fondo obsidiana (`#0c0d12`), superficies de piedra pulida (`#14161f`), acentos en oro viejo/ámbar (`#d97706`, `#fbbf24`) y tipografía medieval `Cinzel`.
  - **Diario Vivo de Campaña**: Memoria acumulativa entre sesiones, control automático de numeración de sesiones con candado en vivo (`#sessionLockBadge`) para prevenir sobrescritura accidental.
  - **Barra Compacta de Fichas (Party Chips Bar)**: Visualización limpia de jugadores, razas, clases y DM con drawer colapsable.
  - **Wiki de Campaña Desacoplada**: Consultoría de misiones activas/completadas, catálogo de PNJs y Directorio Universal de Aventureros.
- **Tema B: Work & Study (`theme-work-study`)**:
  - Estética minimalista de alta densidad (estilo Linear / Raycast): Fondo carbón profundo (`#090a0f`), bordes sutiles y acentos en cyan eléctrico (`#0ea5e9`).
  - **Intake Rápido**: Formulario minimalista de un solo campo para tema/reunión con fecha auto-asignada.
  - Ocultamiento inteligente de elementos de rol (wiki, fichas de jugadores, razas) para máxima concentración.

---

### 2. 🧠 Directiva Backend de Profundidad Explicativa (Work & Study)
En `src/summarizer/prompts.py`, el sistema rechaza resúmenes superficiales y viñetas vagas mediante una regla explícita:
- **Introducción y Contexto**: Tesis central del ponente y marco conceptual.
- **Recorrido Temático Exhaustivo**: Progresión temática profunda que **conserva y explica todos los ejemplos del mundo real, analogías técnicas, casos de estudio y casos extremos (*edge cases*)**.
- **Conclusiones y Datos Concretos (Al Cierre)**: Métricas numéricas, herramientas citadas, compromisos adquiridos y preguntas de autoevaluación.

---

### 3. 🎙️ Tres Vías de Ingesta Universal

| Vía de Entrada | Descripción | Casos de Uso |
| :--- | :--- | :--- |
| **🎙️ Grabación en Vivo (Mic)** | Captura en tiempo real con monitoreo visual VU (RMS) reactivo. Permite elegir entre **PC Host (Dual-Canal)** o **Móvil / Mic Navegador (`MediaRecorder`)**. | Partidas en Discord, partidas presenciales, conferencias en el aula, reuniones de trabajo. |
| **📺 Enlace de YouTube** | Descarga directa de audio en streaming ligero con `yt-dlp` y transcripción inmediata. | VODs de Critical Role, tutoriales técnicos, podcasts, conferencias grabadas. |
| **📁 Archivo Local** | Subida por arrastrar y soltar de archivos de audio (`.mp3`, `.wav`, `.m4a`, `.webm`, `.flac`, `.ogg`). | Grabaciones previas con grabadora de voz, audios de WhatsApp, notas de voz. |

---

### 4. 📱 PWA & Grabación Móvil con Túnel HTTPS
- **Progressive Web App (PWA)**:
  - Instalable nativamente en **Android (Chrome)** e **iOS (Safari)** sin necesidad de tiendas de aplicaciones.
  - Interfaz a pantalla completa (`display: standalone`), sin barras de navegador y con iconos de alta resolución.
  - Service Worker (`/sw.js`) con estrategia network-first para funcionamiento offline y caché de activos estáticos.
- **Captura con Micrófono del Teléfono (`MediaRecorder` API)**:
  - Al conectarte desde tu smartphone, la app puede grabar directamente con el micrófono de tu teléfono en lugar de usar la tarjeta de sonido de la PC.
  - Medidor de audio en vivo a 60 fps mediante la **Web Audio API** (`AudioContext` + `AnalyserNode`).
- **Lanzador de Túneles HTTPS con 1 Clic**:
  - Los navegadores móviles exigen HTTPS para habilitar el micrófono y la instalación PWA. WhisperDnD incluye scripts automáticos para exponer el servidor:
    - **Cloudflare Quick Tunnel**: `cloudflared tunnel --url http://localhost:8080` (gratuito, sin registro).
    - **Localtunnel**: `npx -y localtunnel --port 8080` (solo requiere Node.js).
    - **Lanzador Windows**: Doble clic en `scripts\start_tunnel.bat` o ejecución de `.\scripts\tunnel.ps1`.
  - Soporte CORS completo para túneles remotos (`allow_origin_regex=r"https?://.*"`).

---

### 5. 🎧 Integración Discord RPC (Local)
- **Detección Automática de Discord**: Cliente WebSocket local que escanea automáticamente los puertos `6463` a `6472` utilizando la cabecera `Origin: https://streamkit.discord.com`.
- **Participantes en Canal de Voz**: Muestra en tiempo real qué jugadores están conectados al canal de Discord, quién está hablando y vincula automáticamente sus identificadores al Roster de la partida.
- **Captura Dual de Audio (PC Host)**:
  - **Canal 1 (Izquierdo)**: Tu micrófono local.
  - **Canal 2 (Derecho)**: El audio de tus audífonos/altavoces (Discord loopback) a través de la librería `soundcard`.
  - Whisper analiza ambos canales para etiquetar con precisión quién habló en cada momento (`[Tu]` vs `[Discord]`).

---

### 6. 📄 Exportación & Sincronización en la Nube
- **Formatos de Descarga**:
  - **Markdown (`.md`)**: Formato limpio con tablas, bloques de combate y citas narrativas.
  - **Microsoft Word (`.docx`)**: Documento formateado con portada, tipografías personalizadas y tablas estilizadas listo para imprimir o compartir.
- **Sincronización con Google Drive**:
  - Autenticación OAuth 2.0 directa desde la cabecera (`credentials.json`).
  - Sube automáticamente las crónicas y apuntes generados a una carpeta dedicada en tu unidad de Google Drive.

---

## 🛠️ Requisitos Previos

1. **Python 3.10 o superior**:
   ```bash
   python --version
   ```
2. **FFmpeg**:
   Requerido para la decodificación de audio de `faster-whisper` y `yt-dlp`.
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
     sudo apt update && sudo apt install ffmpeg
     ```
3. *(Opcional para túnel móvil)* **Node.js** (para `npx localtunnel`) o **Cloudflare CLI** (`cloudflared`).

---

## 🚀 Instalación y Puesta en Marcha

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

# Puerto y Host
PORT=8080
HOST=127.0.0.1
```

### 5. Iniciar la Aplicación
```bash
python main.py
```
Abre tu navegador en: **`http://localhost:8080`**

---

## 🌐 Conexión desde el Móvil (Túnel HTTPS)

1. Con el servidor corriendo en tu PC, ejecuta el lanzador:
   - **Windows**: Doble clic en `scripts\start_tunnel.bat` o en PowerShell: `.\scripts\tunnel.ps1`.
   - **Manual (Cloudflare)**: `cloudflared tunnel --url http://localhost:8080`.
   - **Manual (Localtunnel)**: `npx -y localtunnel --port 8080`.
2. Abre la URL HTTPS generada en tu teléfono móvil (ej. `https://xxxx.trycloudflare.com`).
3. **Instala la PWA**:
   - En **Android (Chrome)**: Toca `⋮` &rarr; *"Instalar aplicación"*.
   - En **iOS (Safari)**: Toca el botón Compartir `⎋` &rarr; *"Añadir a pantalla de inicio"*.
4. **Graba con tu Teléfono**: Selecciona la fuente **📱 Móvil / Mic Navegador** y pulsa *"Iniciar Grabación"*.

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite integral de 135 pruebas unitarias y de integración que validan endpoints, exportadores, clientes de IA y canalizaciones de audio:

```bash
# Ejecutar toda la suite de pruebas
.\.venv\Scripts\python.exe -m unittest discover -s tests

# Resultado esperado:
# Ran 135 tests in ~25s -> OK
```

---

## 📂 Estructura del Proyecto

```text
WhisperDnD/
├── data/                       # Almacenamiento local de audio y estado de campañas
│   ├── campaigns/              # Ficheros JSON de campañas y crónicas acumulativas
│   ├── input/                  # Archivos de audio subidos o grabados
│   └── output/                 # Documentos .md y .docx generados
├── docs/                       # Guías técnicas y documentación de arquitectura
│   └── mobile_pwa_and_tunnel.md# Manual detallado de PWA y túneles HTTPS
├── scripts/                    # Scripts de utilidad y lanzadores
│   ├── start_tunnel.bat        # Lanzador rápido de túnel para Windows
│   ├── tunnel.ps1              # Script PowerShell interactivo de túneles
│   └── test_transcription.py   # Diagnóstico de audio por consola
├── src/                        # Código fuente modular
│   ├── api/                    # Servidor FastAPI, rutas REST y WebSockets
│   │   ├── server.py           # Endpoints de audio, transcripción, PWA y tareas
│   │   └── templates/          # Plantilla HTML sincronizada
│   ├── exporters/              # Generadores de documentos Markdown y Word (.docx)
│   ├── storage/                # Gestor de campañas vivas y cliente Google Drive
│   ├── summarizer/             # Cliente Google Gemini y arquitecturas de prompts
│   └── transcription/          # Motores Groq Whisper, faster-whisper, Discord RPC
├── static/                     # Activos web estáticos
│   ├── icon-192.png            # Icono PWA (192x192)
│   ├── icon-512.png            # Icono PWA (512x512)
│   ├── manifest.json           # Manifiesto Web PWA
│   ├── sw.js                   # Service Worker PWA (Network-first)
│   └── index.html              # Interfaz interactiva SPA (Dual Workspace)
├── tests/                      # Suite de pruebas unitarias (135 tests)
├── .env.example                # Plantilla de variables de entorno
├── main.py                     # Punto de entrada de la aplicación
└── requirements.txt            # Dependencias de Python
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.