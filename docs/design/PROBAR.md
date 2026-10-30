# Probar el rediseño con tus datos

Esta rama se creó a partir del Laboratorio local y sus cambios sin commit. La copia del rediseño es independiente: no cambies la rama dentro de WhisperDnD-Lab para esta prueba.

1. Abre esta carpeta en el Explorador y haz doble clic en **probar_redisenio.bat**.
2. El navegador abrirá **http://127.0.0.1:8081/**. Es una dirección distinta a la versión habitual de 8080.
3. Selecciona una campaña y prueba sus menús. Los seis temas están en **Apariencia**.
4. Para cerrar, vuelve a la ventana del lanzador y pulsa **Ctrl+C**.

El lanzador utiliza primero la .venv de esta copia. Si no existe, usa la de %USERPROFILE%\WhisperDnD-Lab. Si se prueba en otro equipo, se necesita Python con requirements.txt instalado; todavía no es un instalador de escritorio.

## Qué datos utiliza

La primera ejecución toma los documentos de %USERPROFILE%\WhisperDnD-Lab y los copia a **.design-preview** dentro de esta rama. Copia campañas JSON/modulares, apuntes, transcripciones de texto y documentos Word. No copia archivos de audio, .env ni credenciales o sesiones de Google/Discord.

La copia ya preparada no se sobrescribe al volver a iniciar. Las modificaciones, migraciones de formato y nuevas sesiones se guardan en esa copia. Esa carpeta está excluida de Git. Para probar una grabación anterior, selecciona manualmente el audio desde Archivo Local.

Las claves guardadas por el navegador en 8080 no se comparten con 8081. Configura tus claves en Ajustes si quieres probar una transcripción real. Si decides conectar Drive en esta copia, esa conexión sí utilizará tu cuenta y sus archivos remotos: el lanzador no copia ni activa esa conexión por su cuenta.

Para usar otra carpeta de origen:

    probar_redisenio.bat --source "C:\ruta\WhisperDnD-Lab"

Para verificar sin documentos reales:

    probar_redisenio.bat --empty

Para preparar los documentos sin abrir servidor:

    probar_redisenio.bat --prepare-only

El aislamiento de .env requiere python-dotenv 1.2 o posterior. El lanzador verifica esa capacidad y se detiene antes de iniciar si falta.

## Qué revisar

- Campaña correcta, party y datos de sus personajes.
- Marcar tu personaje, guardar grupo, recargar y comprobar que se conserva.
- Especies, subclases y multiclases en sus menús flotantes.
- Grabar en vivo, archivo y YouTube; regrabar una sesión existente.
- Wiki, Mi Personaje, apuntes, exportaciones y ajustes.
- Los seis temas, incluyendo los dos claros.

Los resultados de las pruebas y los once fallos previos pendientes están en [VERIFICACION.md](VERIFICACION.md). La dirección visual y las decisiones de integración están en [DESIGN.md](DESIGN.md).
