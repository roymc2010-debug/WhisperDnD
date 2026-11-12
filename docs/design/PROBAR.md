# Probar el rediseño con tus datos

Esta rama se creó a partir del Laboratorio local y sus cambios sin commit. La copia del rediseño es independiente: no cambies la rama dentro de WhisperDnD-Lab para esta prueba.

1. Abre esta carpeta en el Explorador y haz doble clic en **probar_redisenio.bat**.
2. El navegador abrirá la **URL que muestre el lanzador**, después de que el servidor del rediseño esté listo. Prefiere 8081; si otra copia lo ocupa, elige 8082 u otro puerto libre. No abre la versión que ya estaba usando el puerto ocupado.
3. Selecciona una campaña y prueba sus menús. Los seis temas están en **Apariencia**.
4. Para cerrar, vuelve a la ventana del lanzador y pulsa **Ctrl+C**.

El lanzador utiliza primero la .venv de esta copia. Si no existe, usa la de %USERPROFILE%\WhisperDnD-Lab. Si se prueba en otro equipo, se necesita Python con requirements.txt instalado; todavía no es un instalador de escritorio.

## Qué datos utiliza

La primera ejecución toma los documentos de %USERPROFILE%\WhisperDnD-Lab y los copia a **.design-preview** dentro de esta rama. Copia campañas JSON/modulares, apuntes, transcripciones de texto y documentos Word. No copia archivos de audio, .env ni credenciales o sesiones de Google/Discord.

La copia ya preparada no se sobrescribe al volver a iniciar. Las modificaciones, migraciones de formato y nuevas sesiones se guardan en esa copia. Esa carpeta está excluida de Git. Para probar una grabación anterior, selecciona manualmente el audio desde Archivo Local.

Por defecto, `probar_redisenio.bat` se ejecuta con `--with-drive` en el puerto **8080**, utilizando tus credenciales locales (`token.json`, `credentials.json` y `.env`) para que Google Drive y las APIs funcionen inmediatamente sin necesidad de registrar nuevos links ni permisos en Google Cloud Console.

Si prefieres ejecutar una prueba completamente aislada en el puerto 8081 sin credenciales ni tokens cloud:

    probar_redisenio.bat --port 8081

Para usar otra carpeta de origen:

    probar_redisenio.bat --source "C:\ruta\WhisperDnD-Lab"

Para verificar sin documentos reales:

    probar_redisenio.bat --empty

Para preparar los documentos sin abrir servidor:

    probar_redisenio.bat --prepare-only

El aislamiento de .env requiere python-dotenv 1.2 o posterior. El lanzador verifica esa capacidad y se detiene antes de iniciar si falta.

## Qué revisar

- **Selector de Motor (Groq Cloud vs. faster-whisper Local)**:
  - Selector compacto en la cabecera de captura (`[ ⚡ Groq | 💻 Local ]`).
  - Al seleccionar Local, se despliega el subselector `[ base | small ]` optimizado para CPU (`int8`, Intel i7-6560U).
  - La opción elegida se persiste automáticamente en `localStorage` y se propaga de forma idéntica a Grabación en Vivo, YouTube y Archivo Local.
  - La transcripción local procesa el audio 100% en tu equipo sin enviar datos a Groq ni requerir `GROQ_API_KEY`.
  - *Nota*: La generación y síntesis posterior de crónicas, fichas y apuntes con Google Gemini continúa realizándose en la nube y requiere `GEMINI_API_KEY`.
- **Informes Locales de Pruebas (`outputs/transcription-tests/`)**:
  - Cada transcripción genera automáticamente un informe `.txt` con metadatos de rendimiento: motor, modelo, origen del audio, duración, tiempo de transcripción, tiempo total, factor de tiempo real (RTF) y configuración (CPU, int8, VAD).
  - *Privacidad estricta*: Los informes nunca contienen audio, transcripciones completas, claves de API, tokens, nombres de campañas, personajes ni jugadores.
  - Los informes son estrictamente locales y nunca se sincronizan a Google Drive ni a servicios cloud externos.
- **Comparación Cuantitativa de Precisión**:
  - En la pestaña de Archivo Local puedes desplegar la sección opcional para pegar una transcripción de referencia corregida.
  - El sistema normaliza el texto (minúsculas, eliminación de signos de puntuación y colapso de espacios) y calcula matemáticamente las tasas de error de palabras (WER) y caracteres (CER) en memoria para el informe. No se asume mayor precisión entre modelos sin dicha referencia objetiva.

- Campaña correcta, party y datos de sus personajes.
- Marcar tu personaje, guardar grupo, recargar y comprobar que se conserva.
- Especies, subclases y multiclases en sus menús flotantes.
- Grabar en vivo, archivo y YouTube; regrabar una sesión existente.
- Wiki, Mi Personaje, apuntes, exportaciones y ajustes.
- Los seis temas, incluyendo los dos claros.

Los resultados de las pruebas y los once fallos previos pendientes están en [VERIFICACION.md](VERIFICACION.md). La dirección visual y las decisiones de integración están en [DESIGN.md](DESIGN.md).
