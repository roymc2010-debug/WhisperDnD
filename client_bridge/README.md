# 🎙️ WhisperDnD Local Discord Voice Activity Bridge

Puente ligero de cliente para capturar audio estéreo (micrófono + salida de Discord) y telemetría de eventos de voz en tu PC local, enviándolo directamente a tu servidor en Render (`https://whisperdnd.onrender.com`).

---

## 🚀 Ventajas
- **Atribución de voz al 100%:** Sin bots invasivos en la llamada y sin adivinanzas heurísticas.
- **Diarización nativa de Discord:** Registra los intervalos de habla por `user_id` con precisión de milisegundos directamente desde el cliente oficial de Discord (vía Named Pipe IPC o WebSocket RPC).
- **Audio Estéreo Separado (WASAPI Loopback):**
  - **Canal 1 (Izquierdo):** Tu micrófono local.
  - **Canal 2 (Derecho):** Audio de Discord (audífonos / otros jugadores y DM).
- **Fusión en la Nube:** El servidor en Render alinea cada segmento de Whisper con el `discord_id` y el Roster de la campaña, entregando a Gemini la transcripción con nombres reales de personajes y jugadores.

---

## 📦 Instalación Rápida en tu PC

```bash
cd client_bridge
pip install -r requirements.txt
```

---

## 🎮 Uso

### 1. Iniciar con diálogo interactivo:
```bash
python -m client_bridge.discord_bridge --campaign "Caoz con todo"
```

### 2. Opciones avanzadas:
```bash
python -m client_bridge.discord_bridge \
  --campaign "Candlekeep" \
  --server-url "https://whisperdnd.onrender.com" \
  --lang es \
  --engine groq \
  --gemini-key "TU_GEMINI_API_KEY" \
  --groq-key "TU_GROQ_API_KEY"
```

### 3. Listar dispositivos de audio:
```bash
python -m client_bridge.discord_bridge --list-devices
```

### 4. Probar conexión con Discord:
```bash
python -m client_bridge.discord_bridge --test-discord
```

---

## 📡 Endpoint en el Servidor
El puente empaqueta el archivo de audio `.wav` y el archivo `discord_events.json` y realiza un `POST` multipart a:
`POST /api/sessions/upload-with-telemetry`
