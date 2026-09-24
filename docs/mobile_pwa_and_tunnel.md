# Guía de Acceso Remoto Móvil, PWA y Túnel HTTPS para WhisperDnD

WhisperDnD soporta acceso multidispositivo completo, instalación nativa como Progressive Web App (PWA) en iOS y Android, y captura de audio directamente desde el micrófono de tu teléfono móvil a través de la API `MediaRecorder` del navegador.

---

## 1. ¿Por qué se requiere un Túnel HTTPS en Móvil?
Los navegadores móviles modernos (Google Chrome, Apple Safari, Samsung Internet) exigen estrictamente **orígenes seguros (HTTPS o localhost)** para:
1. Permitir el acceso al micrófono (`navigator.mediaDevices.getUserMedia`).
2. Permitir el registro del Service Worker (`/sw.js`).
3. Ofrecer la opción "Instalar aplicación" o "Añadir a la pantalla de inicio" (PWA).

Cuando tu PC ejecuta el servidor en `http://localhost:8080`, tu teléfono en la misma red Wi-Fi accedería por `http://192.168.x.x:8080`, lo cual **no** es un origen seguro (HTTP no localhost) y el navegador móvil bloquearía el micrófono y el PWA. Al abrir un túnel HTTPS (Cloudflare o localtunnel), obtienes un dominio con certificado SSL válido y cifrado de extremo a extremo.

---

## 2. Métodos para Iniciar el Túnel

### Método 1: Script Automático Windows (Recomendado)
Haz doble clic en `scripts\start_tunnel.bat` o abre PowerShell en el proyecto y ejecuta:
```powershell
.\scripts\tunnel.ps1
```
El script te permitirá elegir entre Cloudflare Tunnel y Localtunnel con un solo clic.

### Método 2: Cloudflare Quick Tunnel (Sin cuenta ni registro)
Si tienes `cloudflared` instalado:
```bash
cloudflared tunnel --url http://localhost:8080
```
Obtendrás una URL con el formato: `https://[subdominio-aleatorio].trycloudflare.com`.

### Método 3: Localtunnel (Usando Node.js / npx)
Si tienes Node.js en tu PC:
```bash
npx -y localtunnel --port 8080
```
Obtendrás una URL con el formato: `https://[subdominio].loca.lt`.

---

## 3. Instalación como App Nativa (PWA) en tu Móvil

1. Abre la URL HTTPS generada en el navegador de tu teléfono:
   - **Android (Chrome)**: Toca el menú de tres puntos `⋮` &rarr; **Instalar aplicación** o **Añadir a la pantalla de inicio**.
   - **iPhone / iPad (Safari)**: Toca el botón **Compartir** `⎋` &rarr; **Añadir a la pantalla de inicio**.
2. La app se instalará en el escritorio de tu teléfono con su propio icono de alta resolución y se abrirá a pantalla completa (`display: standalone`), sin barras del navegador.

---

## 4. Grabación con el Micrófono del Teléfono Móvil (`MediaRecorder`)

1. En la barra superior, selecciona tu entorno de trabajo:
   - `[ D&D ]` para partidas de rol y diario de campaña.
   - `[ Work & Study ]` para conferencias, clases o reuniones con notas explicativas profundas.
2. En la pestaña **En Vivo (Mic)**, la app detectará automáticamente si estás en un dispositivo móvil y activará la fuente:
   - **📱 Móvil / Mic Navegador**.
   - También puedes alternar manualmente entre `💻 PC Host (Dual-Canal)` y `📱 Móvil / Mic Navegador`.
3. Toca **Iniciar Sesión / Grabar**. El navegador solicitará permiso de micrófono.
4. El medidor VU en vivo reaccionará en tiempo real al volumen de tu voz.
5. Al pulsar **Detener y Procesar**, la grabación se empaqueta en audio Opus/WebM de alta fidelidad, se envía al servidor mediante `/api/transcribe/file` y se procesa automáticamente con Whisper y Gemini.
