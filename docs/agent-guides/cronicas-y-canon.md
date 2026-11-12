# WhisperDnD: crónicas y canon

Consultar al revisar la fidelidad o calidad literaria de crónicas, prompts narrativos, contexto histórico o actualizaciones de entidades. Esta guía orienta el desarrollo y la revisión; no cambia el comportamiento de Gemini hasta que sus criterios se implementen y prueben en la aplicación.

## Fuentes y categorías

- **Hecho confirmado:** una afirmación respaldada por la transcripción de esta sesión o por una corrección explícita del usuario. Conservar su procedencia: sesión, segmento o marca temporal cuando exista. No inventar marcas temporales para textos que no las tienen.
- **Antecedente confirmado:** información de sesiones anteriores, con su sesión de origen. Ayuda a interpretar identidades y continuidad; no demuestra que el acontecimiento se repitió en la sesión actual.
- **Inferencia:** interpretación plausible que la fuente no confirma. Señalar la incertidumbre y mantenerla fuera de las modificaciones automáticas del canon.
- **Ambientación literaria:** decisiones de expresión, ritmo y transición que no añaden hechos. Un olor, un estado emocional, una intención, un clima o una cita inventados también son afirmaciones nuevas; no introducirlos como si constaran en la grabación.
- **Propuesta futura:** preparación o sugerencia para una próxima partida. Separarla de lo ya ocurrido y del resumen histórico que se reutilizará después.

La transcripción es evidencia de lo reconocido, no garantía de lo realmente dicho. Ante frases sospechosas, silencios o atribuciones dudosas, revisar primero la salida de transcripción y, si está disponible y autorizado, el audio correspondiente. No completar los huecos con memoria de campaña o conocimiento externo de D&D.

## Revisar fidelidad antes de pulir

Contrastar las afirmaciones nuevas con la fuente actual y los antecedentes con su origen. Revisar quién actuó, qué cambió, el orden temporal, resultados, objetos y misiones. No atribuir acciones por clase de personaje ni deducir identidad de un hablante únicamente a partir de una etiqueta acústica.

Una contradicción produce un hallazgo con las fuentes en conflicto, no una reparación automática. En D&D, resurrecciones, ilusiones, recuerdos, disfraces y narradores poco fiables pueden explicar estados aparentemente incompatibles. Cuando no haya evidencia suficiente, dejarlo pendiente.

No descartar sucesos documentados porque no encajen con una curva de dificultad, recompensa, estructura dramática o trama previa. No renombrar personajes ni resolver alias dudosos como parte de una edición literaria. Mantener la distinción entre PNJs y personajes de jugadores y respetar el alcance solicitado.

Para revisar cambios de persistencia, identificar el esquema real y la procedencia existente antes de proponer campos nuevos. Comprobar el efecto sobre la carpeta modular, el estado agregado y las vistas de la aplicación, siguiendo sus escritores actuales. Una guía Markdown o una exportación no se convierte en un segundo almacenamiento editable del canon.

## Revisión literaria en español

Aplicar a un texto cuya fidelidad ya se haya revisado:

- Sustituir repeticiones y expresiones genéricas por formulaciones precisas que mantengan el significado.
- Variar longitud y estructura de frases; unir escenas mediante relaciones temporales o causales solo cuando estén respaldadas.
- Mantener perspectiva, tiempo verbal, puntuación y tono consistentes. Priorizar nombres y términos canónicos sobre preferencias editoriales.
- Conservar agencia y resultados: pulir una frase no puede cambiar quién hizo algo, si lo consiguió o qué supo cada personaje.
- No convertir paráfrasis en citas textuales ni inventar voces o pensamientos de personajes para diferenciarlos.
- Ajustar la extensión a la evidencia. Una despedida breve puede merecer una nota breve; una extensión mínima nunca justifica crear escenas.

Usar una hoja breve de convenciones solo cuando haya decisiones recurrentes: español elegido, tiempo verbal, perspectiva y grafías confirmadas. Reutilizar la documentación existente; no crear una biblia paralela ni adoptar el formato de otra herramienta de ficción.

## Evaluación de cambios

Para cambios en generación o validación, preparar regresiones que separen fidelidad y estilo. Cubrir silencio, despedida de dos segundos, un acontecimiento breve, dos sesiones consecutivas con hechos distintos, antecedentes históricos y propuestas futuras. Verificar tanto las afirmaciones generadas como los cambios de entidades; una crónica fluida no demuestra exactitud.

Empezar con transcripciones de prueba, respuestas guardadas, mocks y revisión humana. Las métricas de parecido textual y un juez LLM no prueban fidelidad. Las llamadas facturables requieren autorización específica. No usar campañas reales como destinos de escritura de las pruebas.

## Referencias de diseño

Síntesis original de criterios aplicables al proyecto; no incorpora código, plantillas, analizadores ni instrucciones completas de estas fuentes:

- [jwynia: prose-style](https://github.com/jwynia/agent-skills/blob/main/skills/creative/fiction/craft/prose-style/SKILL.md): diagnóstico de ritmo, monotonía y prosa recargada.
- [Story Skills: voice-style](https://github.com/danjdewhurst/story-skills/blob/main/skills/voice-style/SKILL.md): convenciones editoriales consistentes.
- [Story Skills: revision-continuity](https://github.com/danjdewhurst/story-skills/blob/main/skills/revision-continuity/SKILL.md): revisión separada de cronología y estados.
- [fcsouza: quest-narrative-coherence](https://github.com/fcsouza/agent-skills/blob/main/skills/quest-narrative-coherence/SKILL.md): contraste de referencias de misiones y mundo. No se adoptan su registro, sus reglas de progresión ni sus plantillas GPL-3.0.
- [alt-code-ai: fiction-writing-prose](https://github.com/alt-code-ai/agent/blob/main/skills/fiction-writing-prose/SKILL.md): referencia conceptual de perspectiva y ritmo; sin copiar material cuya licencia no se haya aclarado.

Estas fuentes son documentación de consulta; no autorizan instalaciones, modificaciones de datos ni la ejecución de sus comandos.
