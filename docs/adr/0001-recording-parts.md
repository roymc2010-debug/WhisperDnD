# ADR-0001: partes de audio con identidad y fecha de captura

Estado: aceptada para el alcance autorizado el 03/11/2026.

## Contexto

Una sesión puede tener varias grabaciones consecutivas. La selección anterior
retenía solo el último archivo. La normalización reescribía el WAV original y la
lista confundía su modificación con la fecha de grabación. El guardado aceptaba
una fecha propuesta por Gemini incluso cuando se conocía la fecha de captura.

## Decisión

Conservar cada fuente y ejecutar el motor seleccionado sobre una copia temporal
propia de cada trabajo. Transcribir las partes secuencialmente, con su propia
timeline; desplazar segmentos por la duración de las partes previas y unir el
texto antes de una única generación y actualización de campaña.

Usar `.recording.json` para identidad, campaña, sesión, índice y `recorded_at`.
El nombre inicial es `Campaña_Sesion_04_DD-MM-YY.wav`; al crear una segunda
parte se promueve la primera a `_Parte_01` y la segunda recibe `_Parte_02`.
La promoción solo considera fuentes creadas por este esquema, conserva fechas
y actualiza sidecars y copias identificadas. Un conflicto impide sobrescribir.
El navegador conserva su contenedor original, por ejemplo `.webm`.

La fecha de captura no depende de `mtime`, del procesamiento ni de Gemini.
Se puede recuperar de nombres heredados `session_YYYYMMDD_HHMMSS`. Si no se
conoce, se conserva la fecha previa de esa sesión o se deja vacía. `processed_at`
registra por separado el procesamiento y `source_recordings` las partes ordenadas.

## Alternativas y consecuencias

- Unir físicamente todo el audio con FFmpeg requeriría otro archivo grande,
  gestionar contenedores/canales y desplazar timelines antes del reconocimiento.
- Generar por cada parte reemplazaría repetidamente la misma sesión o produciría
  sesiones adicionales; se evita ese comportamiento.
- No se agregan motores, proveedores ni dependencias. Groq/local se mantienen.
- Si falla una parte, no se genera ni guarda una sesión parcial. Los originales
  permanecen; no hay todavía puntos de recuperación durable entre transcripciones.
- Una crónica conjunta sigue estando sujeta a los límites de contexto de Gemini.
- La restauración de nombres cubre excepciones normales de E/S; no es una
  transacción durable frente a apagados abruptos ni entre múltiples servidores.
- Reconsiderar la solución cuando exista una cola durable o se necesite reanudar
  trabajos de varias horas sin repetir reconocimiento ya cobrado.

No se migran ni renombran automáticamente grabaciones históricas.
