# Componentes y servicios de terceros

Inventario preliminar para la evaluación de WhisperDnD, actualizado el 12 de noviembre de 2026. La [licencia privada del proyecto](LICENSE) se aplica únicamente a su software original; no cambia los permisos de los componentes de terceros.

## Dependencias

Las dependencias Python se declaran en [requirements.txt](requirements.txt). Incluyen faster-whisper y su motor CTranslate2, Groq, Google Gen AI, FastAPI, Uvicorn, python-docx, python-dotenv, python-multipart, yt-dlp, SoundCard, SoundFile, NumPy, bibliotecas de autenticación/API de Google, pydub, json-repair, tqdm y websockets, además de sus dependencias transitivas. Consulta los archivos de licencia de la versión instalada de cada distribución; las versiones mínimas del archivo no constituyen un inventario bloqueado de una build.

La interfaz contiene recursos locales de Tailwind CSS, KaTeX y la fuente Inter en `static/vendor`. Antes de distribuir el ejecutable deben inventariarse las versiones y conservarse los avisos y textos de licencia correspondientes a los archivos que efectivamente se incluyan.

Los modelos de transcripción tienen sus propios términos. La descarga de un modelo no cambia la licencia de la app ni implica que sus pesos estén incluidos en una distribución.

## FFmpeg y ffprobe

La ejecución desde código utiliza los binarios disponibles en el equipo. No se incorporaron binarios a un instalador en esta entrega. Sus obligaciones dependen de la compilación concreta y de sus componentes; antes de empaquetar deben registrarse procedencia, versión, configuración, hashes, textos y obligaciones de licencia aplicables. Consulta la [información legal oficial de FFmpeg](https://ffmpeg.org/legal.html).

## Servicios conectados

Groq, Gemini, Google Drive y Discord son servicios de sus respectivos proveedores; no quedan cubiertos por la licencia de WhisperDnD. Utilizarlos puede requerir cuentas, permisos y condiciones adicionales. Dungeons & Dragons y otras marcas mencionadas pertenecen a sus titulares; el proyecto no afirma afiliación ni patrocinio.

Este archivo no certifica que se hayan cumplido ya todas las obligaciones de una futura distribución binaria. La revisión de licencias y la inclusión de los avisos completos son requisitos pendientes del empaquetado.
