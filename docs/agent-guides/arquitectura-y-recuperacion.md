# WhisperDnD: arquitectura y recuperación

Consultar al diseñar o revisar el procesamiento de sesiones, reintentos, persistencia y límites entre módulos. Es una guía de desarrollo: los criterios siguientes no describen garantías ya implementadas. No autoriza migraciones, reprocesamientos, correcciones de campañas ni llamadas facturables.

## Modelo y responsabilidades

Antes de cambiar interfaces, distinguir grabación, intento de procesamiento, transcripción, crónica, sesión guardada y revisión de una sesión. No son intercambiables: varios intentos pueden corresponder a una misma sesión y una grabación puede no contener material narrativo. Reutilizar los nombres y campos reales; documentar una ambigüedad antes de resolverla mediante cambios de esquema.

Mantener la terminología funcional separada de la información del juego. Un glosario técnico explica qué significa sesión o revisión en la aplicación; no renombra personajes ni modifica el canon.

Separar responsabilidades observables: captura produce un artefacto de audio; transcripción produce texto y segmentos; generación interpreta la fuente con contexto explícito; persistencia aplica una actualización validada; exportación y sincronización producen derivados o copias. Una etapa no debe ocultar el fallo de otra mediante un resultado anterior.

Diseñar interfaces que concentren las invariantes en su responsable, con entradas, resultados y errores claros. Probarlas desde el comportamiento que usan sus consumidores. Antes de extraer otro módulo o adaptador, comprobar si reduce conocimiento y cambios repartidos entre llamadores; una capa que solo añade delegaciones puede empeorar el mantenimiento.

## Idempotencia e intención de reprocesar

Para una operación con efectos, definir qué identifica la misma intención del usuario. El identificador debe mantenerse al reintentar esa operación; crear uno nuevo en cada intento elimina la protección. Acotar su identidad a la campaña y operación correspondientes para evitar colisiones entre campañas.

Un doble clic o reenvío tras perder la respuesta no equivale a una petición explícita de reprocesar. El reprocesamiento autorizado debe tener su propia identidad y una política clara sobre la revisión de la sesión que actualizará. No deduplicar únicamente por texto, nombre de campaña, número visible de sesión o hash de audio: entradas iguales pueden formar parte de intenciones distintas.

Al revisar un diseño, comprobar:

- Cómo se impide que dos solicitudes concurrentes ejecuten la misma operación; comprobar y escribir en pasos separados no garantiza exclusión.
- Qué devuelve una solicitud repetida mientras la primera está en curso y después de completarse.
- Qué ocurre si se reutiliza una identidad con parámetros diferentes: señalar conflicto, sin devolver silenciosamente el resultado de otra entrada.
- Qué evidencia queda si el servicio externo terminó pero la app perdió la respuesta o falló antes de guardar. Tratar ese resultado como incierto antes de repetir una llamada facturable.
- Cuánto tiempo se conserva el registro y qué ocurre después. No prometer ejecución única fuera de los límites efectivamente cubiertos.

Aplicar estas comprobaciones al almacenamiento actual antes de proponer una base de datos, un servicio de claves o una cola adicional. No copiar automáticamente contratos de APIs públicas o sistemas de pagos.

## Etapas, estado y reintentos

Para cada trabajo largo, precisar su identidad, campaña y sesión de destino, entradas, etapa, resultado y error. Distinguir progreso mostrado en pantalla de un punto de recuperación verificable: un porcentaje en memoria no prueba que un artefacto esté guardado ni permite recuperarlo después de reiniciar.

Al plantear recuperación, registrar un punto de control solo después de verificar el artefacto y su asociación a la entrada correcta. Reanudar desde una etapa válida; si cambió la entrada o la configuración relevante, decidir explícitamente qué resultados se pueden reutilizar. No rescatar automáticamente la última transcripción o crónica disponible.

Reintentar únicamente fallos clasificados como temporales, con límite de intentos y duración total, espera progresiva y respeto de las indicaciones del proveedor cuando existan. No reintentar credenciales inválidas, entradas corruptas, conflictos de persistencia o respuestas que requieren intervención. Revisar también los reintentos internos de SDKs para evitar multiplicarlos.

Antes de reintentar, comprobar los efectos de esa etapa y su posibilidad de repetición segura. No envolver todo el flujo en un reintento genérico: puede volver a cobrar generación o volver a guardar una sesión. La cancelación debe comunicar qué terminó y qué sigue incierto; cancelar una tarea local no deshace una operación externa.

## Persistencia, derivados y fallos parciales

Identificar la fuente de verdad y los escritores existentes antes de intervenir. En el código actual, `src/storage/campaign_ingest.py` valida estados completos, detecta discrepancias entre formatos y contiene un mecanismo de restauración ante excepciones; revisar sus llamadores y cobertura en cada cambio. Una restauración en un `except` no demuestra protección frente a cierre abrupto, concurrencia o fallos del disco.

Tratar la representación modular y el JSON agregado como partes de una misma actualización lógica. Si discrepan, preservar ambos e informar del conflicto antes de reconciliar. Para una modificación autorizada, verificar esquema y respaldo, y comprobar ambos formatos después del guardado. No reconstruir una representación sobre otra solo porque contiene más sesiones.

Separar el éxito del guardado local de una exportación o sincronización fallida. Un fallo posterior no justifica repetir generación ni insertar otra sesión; informar el resultado parcial y ofrecer recuperación de la etapa que falló. Cualquier cambio de ese comportamiento requiere implementación y regresiones propias.

## Decisiones y comprobación

Usar `architecture-decision-records` al resolver una decisión importante con alternativas y consecuencias reales. Registrar contexto, elección, estado y motivos para reconsiderarla. Consultar primero las decisiones existentes; no crear ADRs para cada arreglo ni presentar una propuesta como aceptada o implementada. Los ejemplos de PRs, herramientas y revisión de equipos de esa skill se ajustan al alcance autorizado: no implican commits, mensajes a terceros ni instalaciones adicionales.

Para cambios de comportamiento, partir de las pruebas existentes. Cubrir según el riesgo: repetición y concurrencia de la misma petición, reprocesamiento intencional, misma identidad con entradas distintas, fallo entre escrituras, cierre abrupto, resultado externo incierto y fallo de exportación tras guardar. Usar temporales y mocks; verificar ausencia de nuevas contribuciones o duplicados además del resultado HTTP. No usar campañas reales como destinos de prueba.

## Selección de fuentes y mantenimiento

Síntesis original de criterios; no incorpora bibliotecas, scripts o plantillas de las fuentes adaptadas. Consultarlas solo si hace falta profundizar:

| Fuente | Incorporación y límite |
| --- | --- |
| [architecture-decision-records](https://github.com/wshobson/agents/tree/7e2fb559cf4b824b27f1fec49fe88f7511066d26/plugins/documentation-generation/skills/architecture-decision-records) | Skill completa instalada para decisiones importantes; sin instalar `adr-tools`. |
| [find-skills](https://github.com/vercel-labs/skills/tree/77cfce8221e6e112a70152a230abc848b8b14c19/skills/find-skills) | Skill completa instalada para descubrimiento. Popularidad y reputación ayudan a filtrar; no sustituyen revisión de contenido, licencia, permisos y compatibilidad. Buscar no autoriza instalar ni actualizar todo. |
| [python-resilience](https://github.com/wshobson/agents/blob/7e2fb559cf4b824b27f1fec49fe88f7511066d26/plugins/python-development/skills/python-resilience/SKILL.md) | Clasificación de fallos y reintentos acotados; sin añadir Tenacity por defecto. |
| [python-background-jobs](https://github.com/wshobson/agents/blob/7e2fb559cf4b824b27f1fec49fe88f7511066d26/plugins/python-development/skills/python-background-jobs/SKILL.md) | Estado, identidad y repetición segura; sin añadir Celery, Redis o una segunda cola. |
| [api-idempotency-retry](https://github.com/samber/developer-platform-skills/blob/100ff8aa3088fec3276bcc6a0610884b9a166bb3/skills/api-idempotency-retry/SKILL.md) | Identidad de operación, conflictos y concurrencia; adaptar al almacenamiento local, sin asumir una garantía global de ejecución única. |
| [domain-modeling](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering/domain-modeling/SKILL.md) | Claridad de conceptos y decisiones justificadas; sin crear glosarios o archivos automáticamente por cada conversación. |
| [codebase-design](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering/codebase-design/SKILL.md) y [improve-codebase-architecture](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering/improve-codebase-architecture/SKILL.md) | Interfaces pequeñas, responsabilidades concentradas y pruebas desde consumidores; sin imponer vocabulario, delegación, informes HTML o recorridos generales del repositorio. |
| [workflow-orchestration-patterns](https://github.com/wshobson/agents/blob/7e2fb559cf4b824b27f1fec49fe88f7511066d26/plugins/backend-development/skills/workflow-orchestration-patterns/SKILL.md) | Separación entre coordinación y efectos, y revisión de recuperación; sin incorporar Temporal. |

Para fidelidad narrativa, consultar [crónicas y canon](cronicas-y-canon.md). Para localizar evidencia y controlar contexto, consultar [contexto y diagnóstico](contexto-y-diagnostico.md), sin volver a cargar todas las fuentes anteriores.
