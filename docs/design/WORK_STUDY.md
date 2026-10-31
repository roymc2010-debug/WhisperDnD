# Work & Study: captura simplificada

La pantalla inicial muestra Tipo de documento, Título o tema opcional, fuente de audio y la acción para empezar. Más opciones contiene fecha y hora, número de sesión e idioma; queda cerrado inicialmente.

## Tipos de documento

- **Apuntes de estudio:** conserva la generación académica existente, con explicaciones, conceptos, ejemplos, técnicas y material de repaso cuando estén sustentados por la transcripción.
- **Resumen de reunión:** resumen, decisiones y acuerdos, tareas y responsables, pendientes y bloqueos. Una próxima reunión aparece solo si se mencionó. No se añaden glosarios ni preguntas de repaso. Las instrucciones prohíben inventar responsables, fechas o compromisos.

Se conserva el tema y la fecha al cambiar de formato. Se eliminó el código de las cinco plantillas porque solo precargaban ejemplos. La elección persiste localmente y se transmite como document_format (academic/executive) mediante JSON o formularios según el flujo. La API rechaza valores ajenos a esas dos opciones. Las peticiones anteriores, sin ese campo, mantienen academic por defecto.

El formato cruza grabación del equipo, audio subido desde el navegador, archivos, YouTube, regeneración y cambio de idioma. Las respuestas lo devuelven para que una regeneración use el formato del resultado original, aunque el selector de la próxima captura haya cambiado.

## Guardado y lectura

Los nombres de nuevos resúmenes usan apuntes_reunion_ y conservan el directorio de documentos existente. El prefijo permite reconocerlos al volver a abrirlos; se mantienen también los criterios de reconocimiento de documentos antiguos. La biblioteca admite resúmenes breves sin exigir las 100 palabras de una guía académica. Los documentos Word usan las etiquetas de reunión.

En Resultado, los resúmenes muestran Resumen de reunión, Decisiones y acuerdos, Tareas y Transcripción. La vista de acuerdos no presenta herramientas de glosario.

## Sesión de D&D

El número tiene botones −/+. El mínimo es 1 y no se cambia durante una captura. La numeración en vivo sigue siendo automática. Archivo y YouTube permiten ajuste manual; Regrabar prepara una sesión guardada y sus botones recorren únicamente sesiones existentes, incluso si hay huecos entre sus números. Cambiar el número no procesa audio ni modifica archivos por sí mismo.

## Pruebas

Las pruebas de formatos sustituyen únicamente las llamadas a proveedores y la captura física. Verifican el parámetro en las seis entradas, la validación, la extracción de tareas y acuerdos, la biblioteca de resúmenes breves y el documento Word. No miden la calidad de una transcripción o respuesta real de Gemini.
