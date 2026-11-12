# Integración inicial de rutas — 12 de noviembre de 2026

## Alcance y conservación

El usuario autorizó el primer paso hacia la distribución instalable. Esta entrega conecta los proveedores de rutas del servidor y el almacenamiento de campañas/salidas al contrato `src/runtime_paths.py`. No constituye una aplicación empaquetada ni completa toda la etapa de separación de datos.

Se registraron hashes al inicio de 69 archivos pertinentes, incluidos archivos con cambios locales anteriores y 17 JSON de Candlekeep 2.0 (campaña agregada, metadatos modulares, sesiones, entidades y respaldos). No se restauraron, movieron o importaron campañas. No se cambió de rama, se instaló software, se inició/reinició servidor ni se consumieron servicios de pago.

## Cambios de código

- `src/api/server.py`: `get_data_input_dir`, `get_data_output_dir` y `get_data_campaigns_dir` usan el resolvedor común. Conservan la creación de sus carpetas y sus overrides explícitos. El servidor de desarrollo en Linux conserva su regla previa de `/tmp/whisper_input`; no se aplica esa excepción al modo empaquetado.
- `src/storage/campaign_manager.py`: la ubicación predeterminada de campañas y la propiedad de salidas usan el mismo resolvedor. `campaigns_dir` explícito del constructor sigue teniendo prioridad. `WHISPER_OUTPUT_DIR` sigue consultándose al resolver exportaciones, sin caché nueva.
- `src/runtime_paths.py`: únicamente se actualizó la descripción del módulo para reflejar sus consumidores actuales; no se cambió el contrato de cálculo.

En desarrollo se mantienen `data/campaigns`, `data/input` en Windows y la preferencia por `outputs` existente, con fallback a `data/output`. En modo empaquetado, los proveedores conectados utilizan el perfil `%LOCALAPPDATA%/WhisperDnD` para campañas, grabaciones de entrada y exportaciones. Los recursos HTML siguen leyéndose desde los recursos del programa. Los overrides explícitos continúan siendo autoritativos.

No se alteró el esquema, la lógica de guardado de campañas, el frontend, los prompts, motores de transcripción ni modelos de generación.

## Regresiones y resultados

`tests/test_runtime_path_integration.py` añade ocho casos. Una instalación sintética contiene una campaña antigua y recursos HTML; el test rechaza cualquier intento de crear directorios en recursos y compara los archivos al terminar. Los dos casos de destino empaquetado fallaron con el código anterior porque escribía en la instalación; seis controles de comportamiento existente ya pasaban.

Después del cambio se verificaron:

- Coincidencia entre rutas de servidor y gestor, incluso desde otro directorio de trabajo y con nombres con espacios/acentos.
- Guardado y lectura de una campaña sintética en el perfil temporal, con JSON agregado y carpeta modular.
- Ausencia de importación automática de la campaña antigua colocada en recursos.
- Lectura de la interfaz desde recursos, sin copiarla al perfil de datos.
- Overrides de entorno, argumento explícito del gestor y actualización dinámica del destino de salidas.
- Defaults de desarrollo con/sin carpeta `outputs`, entrada de Windows y excepción temporal de Linux. El test de Linux no crea carpetas en el `/tmp` global.

Comprobaciones ejecutadas:

| Verificación | Resultado |
| --- | --- |
| Rutas, integración, aislamiento y gestor de campañas | 57 aprobadas |
| Suite backend offline completa | 634 aprobadas, 2 omitidas, 45 subpruebas aprobadas; 31,77 s |
| Avisos de la suite completa | Cinco avisos de soporte/deprecación de dependencias; sin fallos |
| `git diff --check` de los dos archivos de aplicación modificados | Sin errores de whitespace; Git advierte normalización de finales de línea |
| SHA-256 de los 17 JSON registrados | Conservados |

La suite se ejecutó con red bloqueada, claves ficticias y almacenamiento temporal mediante `scripts/run_offline_tests.py`. Los mensajes de Drive indicaron bloqueo de red; no hubo transferencias. No se reejecutó el frontend porque no se modificó. Las pruebas no son una build real ni una ejecución empaquetada de todo el proceso.

## Pendientes de la etapa de rutas

Continúan pendientes los logs de `main.py` y el lanzador, credenciales y tokens, cuotas, caché de modelos, las rutas de captura/timeline y los demás escritores que todavía derivan carpetas por su cuenta. Deben integrarse por grupos pequeños con sus regresiones antes de construir el EXE.

Las inicializaciones ajenas al almacenamiento de campañas aún pueden depender de la carpeta del programa. No se debe afirmar que la app completa ya funciona desde una instalación de solo lectura basándose en estas pruebas acotadas. No se migran los datos actuales a LocalAppData como efecto de este trabajo.
