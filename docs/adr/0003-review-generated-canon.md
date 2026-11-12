# Revisión de canon antes de guardar una generación

Estado: aceptada e implementada, por autorización del usuario para aplicar las protecciones de la comparación.

## Contexto
Una crónica convirtió un plazo de viaje en una fecha de eclosión y propagó ese dato a PNJs y misiones. Otra confundió el libro entregado e identificó un objeto como propiedad del personaje que lo examinaba. Una cita literal puede existir y seguir estar mal interpretada: un verificador de coincidencias no certifica hechos. Reforzar únicamente el prompt o confiar en una etiqueta de confianza del mismo generador no resuelve ese límite.

## Decisión
Las nuevas generaciones D&D de campaña producen borradores durables bajo output/session-reviews. No llaman a record_session hasta que el usuario revisa el texto y selecciona propuestas. La transcripción y la respuesta de generación se conservan aparte; aprobar o actualizar la comparación no llama a Groq/Gemini. Las variantes de pronunciación permanecen en aliases; los apodos confirmados usan nicknames y ya no se infieren por similitud.

La revisión muestra campaña, sesión de destino, intención de reemplazo/creación, estado anterior, propuestas y citas. Se comprueba la presencia literal de citas, sin declarar válida su interpretación. El usuario puede corregir relato, resumen factual, cierre, guion y reflexión, aprobar propuestas concretas y rechazar las demás. La revisión comprueba una huella del estado de campaña y la coherencia de ambos formatos antes de guardar; un estado distinto exige actualizar la comparación. Esta actualización conserva la generación y el texto revisado, y restablece la selección para que se revise el estado nuevo.

El commit local reutiliza record_session, sus respaldos y el guardado modular/agregado. La ruta de revisión desactiva la expansión implícita de identidades por semejanza y usa IDs para evitar aplicaciones duplicadas. Los resúmenes factuales aprobados alimentan la continuidad; las campañas antiguas conservan el tratamiento conservador de recap/guion heredados.

La generación mantiene exclusivamente el modelo elegido, hasta tres intentos y un presupuesto total configurable (600 s predeterminado), sin reintentos ocultos del SDK. Se conserva Retry-After cuando está disponible y no se duerme después del último intento. Se registran modelo, tiempo por intento y tokens, sin claves ni transcripción en los metadatos.

## Alternativas y consecuencias
- Más instrucciones o citas autoaprobadas: menos intervención, pero no evita una interpretación falsa respaldada por una cita de otro asunto.
- Otro modelo como juez: añade cuota y demora, y tampoco garantiza fidelidad; no se incorpora.
- Revisión humana de propuestas: añade un paso explícito a cada generación. Se elige como primera protección verificable. Las propuestas sin marcar no se guardan; no hay una clasificación semántica infalible de cambios seguros.

No hay migración automática de campañas ni de aliases a apodos. No se reparan datos históricos por inferencia. La sincronización cloud y la exportación siguen separadas del guardado: un fallo de exportación no repite generación. La revisión confirma guardado local; Drive se puede sincronizar desde sus controles existentes.

La exclusión entre revisiones se aplica dentro del proceso actual. No se afirma coordinación entre servidores independientes ni protección absoluta contra escrituras concurrentes ajenas al gestor. Una confirmación humana tampoco sustituye escuchar audio dudoso: la transcripción puede contener errores.
