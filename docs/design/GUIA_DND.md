# Qué hace cada pestaña de D&D

Revisión del código de la rama codex/desktop-redesign, 30 de octubre de 2026.

## Menú principal

| Pestaña | Para qué sirve | Controles y límites actuales |
| --- | --- | --- |
| Sesión y grabación | Preparar la partida y aportar el audio que se va a procesar. | Campaña activa, número de sesión, lore previo, party por campaña y fuentes En vivo, YouTube y Archivo local. La party permite vincular Discord, editar identidad, elegir especie/clase/subclase, configurar multiclase, señalar tu personaje, cambiar presencia y eliminar integrantes. |
| Audio y dispositivos | Comprobar qué audio entrará antes de grabar. | Micrófono, captura del sistema/Discord, dispositivos disponibles, ganancias y medidores de nivel. Parte de estos ajustes también sigue accesible en Ajustes. |
| Wiki y campañas | Consultar y administrar la información guardada de una campaña. | Selector de campaña, seis categorías, búsqueda y dossier; administración de campañas, importación ZIP/JSON y exportaciones. Las campañas se administran aquí. |
| Mis personajes | Elegir o crear un personaje vinculado a una campaña y guardar su trasfondo. | Permite marcarlo como tu personaje principal y conservar historias individuales de varios personajes. Ese trasfondo se usa en la generación de coaching narrativo. No es una ficha completa de atributos, combate, equipo o conjuros. |
| Proceso | Seguir el trabajo de transcripción y análisis. | Progreso por etapas, estado de la tarea y revisión ortográfica de nombres de PNJs cuando está disponible. Si no hay una tarea activa, explica cómo iniciarla. No inicia una grabación por sí sola. |
| Resultado | Revisar el último procesamiento y sus documentos. | Crónica, misiones, PNJs, PCs, grimorio y transcripción. Incluye descargas, versión para jugadores, herramientas de revisión/regeneración y Drive según el resultado disponible. Algunas listas usan el estado acumulado de la campaña. |
| Apariencia | Elegir la presentación de la aplicación. | Seis temas: Grafito y cobre, Carbón, Tinta azul, Borgoña, Papel y tinta y Azul claro. Se conserva la elección al cambiar entre D&D y Work & Study. No hay editor de fondos personalizados. |
| Ajustes & APIs | Configurar conexiones y credenciales de los servicios. | Llaves del usuario, comprobación de proveedores, conexión/desconexión y sincronización de Drive, más controles de audio. Los servicios externos requieren configuración y conexión. |

## Dentro de Sesión y grabación

| Pestaña o acción | Qué hace |
| --- | --- |
| Grabar en vivo | Captura una nueva sesión con la fuente de audio seleccionada. Detener y procesar envía el audio al flujo de transcripción/análisis configurado. |
| YouTube | Recibe una URL para descargar el audio y procesarlo. No es una grabación en vivo del navegador. |
| Archivo local | Procesa un audio que ya existe; puede acompañarlo una timeline de Discord para aprovechar la identificación temporal de participantes. También muestra grabaciones locales detectadas. |
| Regrabar | Permite elegir una sesión existente de la campaña para preparar su reemplazo. La selección no reemplaza los archivos inmediatamente: se aplica al procesar el nuevo audio. |

La party está dentro de esta vista, plegable y abierta por defecto. No existe una pestaña independiente de participantes y no se muestra party en Work & Study.

## Dentro de Wiki y campañas

| Categoría | Qué muestra |
| --- | --- |
| Misiones | Objetivos, estado, subobjetivos, notas y evolución de las misiones. |
| PNJs | Personajes no jugadores con su información, categoría, estado y relaciones disponibles; incluye herramientas para editar o fusionar registros. |
| PCs | Protagonistas de los jugadores e hitos acumulados de la campaña. No sustituye la ficha de juego. |
| Lugares | Localizaciones y sus datos, estado y relaciones registradas. |
| Objetos | Objetos y artefactos, con su descripción, relaciones y custodia cuando hay datos. |
| Sesiones | Historial de sesiones guardadas. El detalle permite alternar Crónica y Transcripción, buscar en la transcripción y copiarla o descargarla cuando existe. |

Mis Campañas abre la administración de campañas; Importar incorpora un ZIP/JSON. El selector de sesión de la cabecera decide qué sesión se exporta. Para Jugadores descarga la versión limpia prevista por el flujo existente, sin consejos personales.

## Dentro de Resultado

| Pestaña | Qué muestra |
| --- | --- |
| Crónica | Relato y secciones narrativas generadas para la sesión; puede incluir recapitulación, cierre y coaching según el resultado. |
| Misiones | Registro de objetivos y subobjetivos que maneja el resultado/campaña. |
| PNJs | Directorio de personajes no jugadores, categorías y herramientas de revisión de nombres. |
| PCs | Protagonistas e hitos disponibles en el estado de la campaña. |
| Grimorio (.md) | Documento consolidado en Markdown que el resultado tiene disponible. |
| Transcripción | Texto transcrito y segmentos/marcas temporales cuando están disponibles. |

Puntos Clave y Glosario pertenece a Work & Study y permanece oculto en D&D. Resultado es el espacio de revisión de un procesamiento; Wiki es el lugar habitual para volver a consultar una campaña guardada.

## Cambios de botones e iconos de esta revisión

| Antes | Ahora | Motivo |
| --- | --- | --- |
| Algunas acciones sin estilo común parecían texto | Acciones con superficie, borde, etiqueta legible y estados de interacción | Hacer visible qué se puede pulsar |
| Emojis de estilos distintos en controles y mensajes | SVG locales con un trazo común y texto explícito para los estados | Coherencia visual y nombres accesibles |
| El aviso de audífonos dependía de un emoji en la opción | Información del dispositivo y reconocimiento del nombre | Evitar perder la advertencia al retirar los emojis |
| El estilo base podía hacer visibles acciones con clase hidden | Regla explícita para conservar acciones ocultas | Mantener los flujos condicionales de Drive y otros controles |

Los logos de clase y sus colores no se sustituyen por este sistema de iconos. No se reintroducen contornos, relieves ni fondos. Los textos y archivos personales no se recorren ni se reescriben para retirar emojis. Los lectores conservan el contenido que proporcionan los datos.

## Número de sesión con −/+

Los botones se habilitan donde se permite editar el número. En vivo se calcula automáticamente la siguiente sesión; durante la grabación quedan bloqueados. En Archivo y YouTube se puede ajustar desde 1. Al preparar Regrabar, −/+ recorren las sesiones guardadas y se detienen en sus extremos. Cambiar de número no reemplaza documentos hasta procesar el audio.

Los campos de nombre de personaje ajustan su ancho al texto, igual que los nombres de jugador. La etiqueta Tú permanece junto al campo; los nombres largos se limitan al espacio disponible sin desplazar las otras columnas.
