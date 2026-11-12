# WhisperDnD: contexto y diagnóstico

Consultar al investigar contaminación entre sesiones, fallos de procesamiento o persistencia, o consumo innecesario de contexto y herramientas. Complementa AGENTS.md y GEMINI.md; no sustituye las restricciones del usuario ni autoriza servicios, delegación o modificaciones adicionales.

## Contexto necesario y recuperable

Partir del mapa funcional de AGENTS.md y localizar el punto de entrada del flujo afectado. Leer rangos concretos; ampliar solo cuando una dependencia lo justifique. No cargar colecciones completas de skills, campañas, modelos o logs para una pregunta localizada.

Separar dos contextos distintos:

- **Contexto del agente de desarrollo:** tarea actual, restricciones, archivos relevantes, hallazgos y pendientes.
- **Contexto de generación de la app:** transcripción actual, antecedentes confirmados y propuestas futuras, cada uno con procedencia y función explícitas. Consultar [crónicas y canon](cronicas-y-canon.md) cuando el problema afecte a narrativa o entidades.

Para resumir trabajo, conservar decisiones, evidencia, rutas o identificadores que permitan recuperar la fuente, incertidumbres y el siguiente paso. Reducir salidas duplicadas antes que evidencia aún necesaria. No eliminar fuentes ni modificar grabaciones, historial o canon para ahorrar tokens.

Medir el tamaño y la relevancia del contexto antes de optimizarlo. No adoptar porcentajes universales de compresión ni prometer ahorros de tokens o caché. La caché del proveedor y los controles internos del agente dependen de capacidades verificadas; no introducir otro sistema de memoria, base de datos o arquitectura de agentes por defecto.

## Diagnóstico por evidencia

Registrar comportamiento esperado, observado, entrada concreta y etapa donde divergen. Distinguir un fallo confirmado de una hipótesis y de una condición que todavía no se pudo reproducir. Tratar con el mismo escepticismo el código propio y el heredado.

Seguir la entrada actual a través de sus etapas, identificadores y artefactos. Comprobar selección de archivos, estado compartido, reintentos y rutas temporales antes de atribuir el fallo al modelo. Registrar el motor y modelo efectivos, no solo la selección del frontend.

Cuando un texto breve produce una crónica extensa, inspeccionar primero qué audio se eligió y qué transcripción se obtuvo; después, qué antecedentes y prompt se enviaron a generación. La buena redacción no prueba que exista evidencia en la grabación.

Ante cambios externos durante la investigación, volver a comprobar el estado de los archivos afectados. No sobrescribirlos para recuperar la situación inicialmente observada. Si hay conflicto, informar antes de integrar.

Cuando se autorice un arreglo de código, preparar la regresión que reproduzca el fallo, aplicar el cambio mínimo y ejecutar las comprobaciones pertinentes. Usar mocks para fallos de red, reintentos y respuestas de servicios. No confundir aprobación de una instalación de skills con autorización para reparar campañas o realizar llamadas facturables.

## Audio y hablantes

- Separar captura de audio, transcripción, segmentación de hablantes y vinculación a identidades. Un evento RPC, una voz detectada y un personaje no son equivalentes.
- Diferenciar captura aislada por proceso de limpieza de una mezcla ya grabada. Ningún filtro recupera una voz ausente del archivo fuente.
- En investigaciones de recuperación, conservar el original y examinar el cierre del contenedor, duración real y asociación entre grabación y sesión. Una cabecera incompleta y una grabación silenciosa son problemas distintos.
- Si se autoriza una transformación, generar un derivado trazable y comparar con el original. No añadir un proveedor de transcripción por adoptar un formato de segmentos o una idea de validación.

## Rendimiento, privacidad y herramientas

Perfilar un cuello de botella observado antes de introducir concurrencia, cachés o dependencias. Mantener fuera de logs y reportes claves, tokens y contenido privado innecesario. Usar datos sintéticos o muestras mínimas para pruebas; no subir grabaciones o campañas a servicios nuevos sin autorización.

Los análisis estáticos complementan la revisión de acceso a archivos, secretos y datos personales; no verifican fidelidad narrativa ni consentimiento de grabación. Elegir reglas pertinentes y revisar sus hallazgos antes de proponer correcciones.

Cerrar procesos temporales iniciados por una verificación. Diferenciar comprobaciones offline, pruebas con dispositivos reales y llamadas externas; indicar qué se ejecutó y qué sigue sin verificarse.

## Referencias de diseño

Síntesis original de ideas; no incorpora scripts, SDKs ni bibliotecas de estas fuentes:

- [Context Engineering: context-optimization](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/main/skills/context-optimization/SKILL.md): selección de contexto y reducción de salidas redundantes.
- [Context Engineering: context-degradation](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/main/skills/context-degradation/SKILL.md): procedencia y conflictos entre fuentes.
- [alt-code-ai: debug-like-expert](https://github.com/alt-code-ai/agent/blob/main/skills/debug-like-expert/SKILL.md): separación de diagnóstico y modificación; referencia conceptual sin copiar contenido de licencia no aclarada.
- [wshobson: sast-configuration](https://github.com/wshobson/agents/blob/main/plugins/security-scanning/skills/sast-configuration/SKILL.md): selección de análisis estático y revisión de falsos positivos.
- [ElevenLabs: speech-to-text](https://github.com/elevenlabs/skills/blob/main/speech-to-text/SKILL.md) y [Deepgram: speech-to-text](https://github.com/deepgram/skills/blob/main/skills/speech-to-text/SKILL.md): distinción entre segmentos, tiempos, etiquetas de hablantes y turnos.
- [ElevenLabs: voice-isolator](https://github.com/elevenlabs/skills/blob/main/voice-isolator/SKILL.md): limpieza como transformación separada de la captura.

Las referencias a proveedores no indican que se hayan integrado ni autorizan sus llamadas, instaladores o manejo de credenciales.
