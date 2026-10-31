---
name: WhisperDnD escritorio
status: implemented-for-testing
reference: mockups v6.1
---

# Dirección visual

Aplicación de escritorio moderna y sobria, con Inter local, separación clara entre preparación y grabación, superficies planas, bordes suaves y espaciado estable. Los modos D&D y Work & Study comparten la estructura y el tema visual es independiente del modo.

## Temas

- **Grafito y cobre** (copper): fondo #171717, superficie #202020, texto #f3f0eb, acento #d6aa7a.
- **Carbón** (graphite): fondo #171819, superficie #202224, texto #f1f2f3, acento #c9cdd3.
- **Tinta azul** (midnight): fondo #171c25, superficie #202835, texto #eff2f7, acento #a4bee7.
- **Borgoña** (wine): fondo #20191c, superficie #2a2226, texto #f4edf0, acento #dfafb9.
- **Papel y tinta** (paper): fondo #f4f2ed, superficie #ffffff, texto #262521, acento #383633.
- **Azul claro** (sky): fondo #f0f3f8, superficie #ffffff, texto #232d3b, acento #35567f.

Los tokens implementados están en static/desktop.css y el catálogo en static/js/desktop-core.js. La elección persiste como whisper_desktop_theme. No hay un tema verde ni controles de personalización que todavía no funcionen.

## Acciones

- Acción principal: acento del tema; iniciar, procesar archivo o YouTube.
- Guardar y crear: acento en superficie discreta.
- Transferir, copiar, importar y sincronizar: azul compatible con cada tema.
- Revisar, regenerar, reintentar y regrabar: ocre compatible con cada tema.
- Detener, borrar y desconectar: rojo discreto.
- Navegar, cerrar o cancelar: neutral.

La clasificación usa data-button-role y sobrevive a los cambios de className de los módulos originales. Los botones de las clases no reciben esta clasificación.

## Party y navegación

Party por campaña entre contexto/lore y grabador. Disclosure abierto por defecto. Identidad del personaje, jugador y Discord en una misma celda; dos clases dentro de la misma celda; selección de mi personaje, presencia y borrar. Los colores de los SVG son los de DND_BEYOND_COLORS. Se descartaron relieve, placas de color y ajustes automáticos del contraste de los logos.

Campañas se administran en Wiki y proyectos en Apuntes; no se añaden destinos independientes para participantes, campañas o proyectos. El acceso por túnel no se presenta en la navegación. Audio, proceso, resultado y apariencia tienen vistas propias, con los elementos y handlers reales existentes.

## Integración

La capa de presentación mueve los nodos existentes, conservando IDs, menús, inputs y handlers de grabación/archivo/YouTube/Drive. app.js incorpora las nuevas vistas y dirige los resultados a Resultado; progress.js dirige el procesado a Proceso. Los errores permanecen como diálogos globales.

Los recursos de interfaz se sirven localmente: Tailwind compilado, Inter, Marked y KaTeX. Las licencias se incluyen junto a los recursos. La aplicación aún requiere conexión para los proveedores externos que el usuario elija.

## Correcciones necesarias encontradas al integrar

- Guardar Grupo usaba una ruta inexistente y anunciaba éxito sin revisar HTTP. Usa POST /api/campaigns con el roster completo y solo confirma éxito con una respuesta correcta.
- Metadatos ui_class_config mantienen por separado las subclases y los textos homebrew; se siguen leyendo campañas antiguas sin esos metadatos.
- El selector abre la clase elegida y sus dos pestañas conservan el color original del logo.
- Una campaña nueva comienza con un DM vacío, sin insertar jugadores personales de ejemplo.
- Los controles de la party esperan a que termine su carga inicial. Se retiran los listeners duplicados de campaña.

Consulta VERIFICACION.md para resultados y límites de la prueba.

## Escala y distribución equilibradas

La escala anterior de 20px se moderó: raíz de 18px desde 1600px de ancho y 16px por debajo. El contenido conserva un máximo independiente de 1480px, para aprovechar la pantalla sin ampliar todos los controles al mismo tiempo. Las medidas de componentes continúan en rem y los breakpoints en px.

| Antes | Después | Motivo |
| --- | --- | --- |
| Raíz de 20px desde 1440px | 18px desde 1600px; 16px en ventanas menores | Escala intermedia con margen para ventanas ampliadas |
| Ancho máximo ligado a la escala tipográfica | Máximo de 1480px independiente | Conservar el contenido amplio sin agrandar los controles |
| Título de Wiki junto a todos los selectores y exportaciones | Título, campaña y exportaciones en filas propias | Impedir que el título quede comprimido en una columna estrecha |
| Sesión con ancho intrínseco según su título | Selector flexible con ancho mínimo cero | Admitir títulos largos sin desbordar ni perder el valor completo |
| Seis filtros en tres columnas estrechas | Dos columnas con espacio para icono, nombre y contador | Impedir solapamientos |
| Columnas de lectura con anchos rígidos | Columnas acotadas y apiladas por debajo de 1100px | Mantener legibilidad de Wiki y Apuntes |

El botón de recarga queda junto al selector de campaña. En ventanas estrechas los controles de sesión pasan a varias filas. Los seis filtros y todas las exportaciones permanecen accesibles. Los colores, datos y handlers no cambian.

## Botones reconocibles e iconos locales

La revisión del 30 de octubre conserva Inter y la escala general existente. Los botones de acción usan texto de .875rem, superficie y borde visibles, colores por función y estados hover, pulsado, deshabilitado y foco. Las acciones neutrales también tienen aspecto de botón. Los selectores de especies/clases, la navegación y las pestañas conservan su jerarquía específica.

Los emojis decorativos del frontend se sustituyen por SVG locales de ui-icons.js. Los estados escritos siguen describiendo su significado; los botones de solo icono reciben nombres accesibles. No se recorren datos personales para eliminar símbolos, y los lectores siguen mostrando su contenido. Las expresiones que reconocen documentos y avisos antiguos conservan compatibilidad con emojis antiguos. Los SVG de clase y sus colores permanecen iguales.

La guía funcional está en [GUIA_DND.md](GUIA_DND.md). La verificación comprueba también que las acciones con clase hidden no aparezcan por el estilo común de botón.
