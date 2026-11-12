# Cuotas y modelos en el perfil del usuario — 12 de noviembre de 2026

## Cambio

Se modificaron únicamente dos módulos de producción:

- `src/storage/quota_tracker.py`: el destino del contador diario pasa por el resolvedor existente. En desarrollo mantiene `data/system_quota.json`; empaquetado utiliza `%LOCALAPPDATA%/WhisperDnD/quota/system_quota.json`. Se conserva `WHISPER_QUOTA_DIR` y el comportamiento de contadores, límites y guardado.
- `src/transcription/local_whisper.py`: en modo empaquetado la caché predeterminada se resuelve a `%LOCALAPPDATA%/WhisperDnD/models`. Se mantiene la prioridad del argumento explícito `download_root` y el override de entorno `WHISPER_DOWNLOAD_ROOT`. Desarrollo conserva literalmente el default relativo `models` y sus semánticas anteriores. No se fuerza ese default al directorio del proyecto porque alteraría el comportamiento existente.

Construir el transcriptor sigue sin cargar el modelo ni crear su caché. El directorio se crea al solicitar el modelo, como antes. Las rutas explícitas del consumidor siguen bajo su control. En modo empaquetado predeterminado, la ausencia de un perfil válido produce un error en vez de escribir silenciosamente junto al programa. No hay migración, descubrimiento ni descarga de modelos añadida.

## Verificación

Siete casos nuevos con perfiles, carpetas y archivos sintéticos: contador separado entre dos usuarios; recursos sin modificaciones; ejecución desde otro directorio con espacios; caché por usuario y carga diferida; constructor de modelo simulado sin red; overrides; defaults de desarrollo; ausencia de perfil para ambas funciones. Antes de implementar fallaron cuatro casos que identificaban el comportamiento faltante y pasaron tres que protegían contratos existentes. Después pasaron los siete.

Las pruebas relacionadas con cuotas, Whisper local, aislamiento y contrato de rutas dieron **39 aprobadas**, con cinco avisos de dependencias. La suite backend offline completa terminó con **669 aprobadas, 2 omitidas y 46 subpruebas aprobadas**, con seis avisos, en 35,43 s. Además de los cinco avisos de dependencias, una prueba existente de niveles de audio emitió una advertencia de discontinuidad de Soundcard; no hubo fallos.

Se comparó el contenido de los dos módulos contra el inicio de este paso y coincidió exactamente con las sustituciones previstas, normalizando solo finales de línea. Los cambios locales anteriores de ambos archivos se conservaron. Los cuatro archivos privados y los siete JSON directamente en `data/campaigns` incluidos en la referencia conservaron sus hashes; esta referencia no es un inventario recursivo de campañas.

`git diff --check` de los dos módulos terminó sin errores, con aviso de conversión futura de finales de línea para Whisper local. No se modificó interfaz ni se reejecutó su suite. No se inició o reinició la app ni una grabación de sesión, cambió Google Cloud, instaló dependencias, descargó modelos o consumió servicios. No se produjo todavía un EXE ni se certificó funcionamiento en otro PC.

## Próximo bloque

Revisar los escritores restantes de grabaciones/fragmentos y el token de Discord antes de completar la separación de datos. Después, adaptar y verificar el arranque empaquetado independiente de `.venv`; la compilación y el instalador requieren sus propias verificaciones y herramientas.
