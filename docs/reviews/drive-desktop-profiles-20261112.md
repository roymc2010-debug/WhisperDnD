# Drive: configuración de escritorio y aislamiento de perfiles

Fecha: 12 de noviembre de 2026.

## Alcance y hallazgo

El usuario autorizó comprobar el cliente OAuth y preparar el siguiente paso para Drive desde el EXE. El cliente local ya es de tipo Aplicación de escritorio. La inspección no mostró identificadores, secretos o tokens y no inició conexión alguna.

Se integraron las rutas de configuración y tokens por perfil en modo empaquetado y se documentó la configuración distribuible. No se crearon clientes Cloud, se cambiaron permisos, se publicó la aplicación, se copió la configuración real a un paquete ni se ejecutó sincronización real.

## Cambios

- `src/storage/drive_client.py`: las fuentes predeterminadas empaquetadas utilizan el `config_dir` del resolvedor. La configuración común proviene solo de la ruta dedicada `oauth/drive-desktop.json` o del entorno explícito, y se filtra a campos de metadatos OAuth de escritorio. La configuración existente en el perfil se valida sin reescribirla. Los tokens/respaldo pertenecen al perfil; no se leen tokens junto al programa.
- Las operaciones de intercambio, restauración y desconexión dejan de escribir/eliminar `/app/token.json` en modo empaquetado. El comportamiento de desarrollo y contenedores no empaquetados se conserva.
- `main.py` y `src/api/server.py`: la preparación de configuración desde el entorno usa el perfil en modo empaquetado. Un fallo de la configuración opcional de Drive no impide preparar el resto de la app ni provoca una escritura raw de fallback. Los diagnósticos de arranque no imprimen el contenido de la configuración.
- `src/api/routers/drive.py`: el callback y el endpoint de token no consultan `/app/token.json` como fallback de una ejecución empaquetada. Los flujos existentes no empaquetados conservan sus rutas.

No se cambió la interfaz, modelo, scope `drive.file`, lógica de sincronización, flujo OAuth ni vinculación actual de desarrollo. Esta entrega no implementa cifrado de tokens ni certifica el callback de una build real.

## Regresiones y verificación

`tests/test_drive_profile_paths.py` añade 13 casos: fuente común presente/ausente, tokens de recursos ignorados, dos perfiles, entorno explícito, rechazo de cliente web, exclusión de campos personales de los metadatos, conservación de configuración del perfil, restauración de respaldo propio, rutas explícitas y operaciones que no alteran un token de contenedor ajeno. El endpoint empaquetado sin token devuelve no conectado en lugar de usar ese token ajeno.

`tests/test_startup_logging_paths.py` añade dos casos: bootstrap OAuth del punto de entrada en el perfil y conservación del arranque sin Drive válido. Se observaron los fallos esperados antes de aplicar las correcciones. Un error inicial de colección por importar un router antes del servidor se corrigió únicamente en el orden de importación del test.

| Comprobación nueva | Resultado |
| --- | --- |
| Drive por perfil y suite existente del cliente | 28 aprobadas |
| Integración de Drive, arranque, independencia e incremental, antes del último guard opcional | 64 aprobadas |
| Perfiles, arranque e independencia tras el guard opcional | 33 aprobadas |
| Suite backend offline final | 657 aprobadas, 2 omitidas, 45 subpruebas aprobadas; 32,61 s |
| Avisos de dependencias de la suite final | Cinco, sin fallos |
| `git diff --check` de código y test existente modificados | Sin errores de whitespace; avisos de finales de línea |

No se reejecutó el frontend: no se modificó. Los datos eran ficticios y las conexiones estaban bloqueadas por `scripts/run_offline_tests.py`. Las pruebas OAuth utilizaron un proveedor simulado; no se autentificó una cuenta real ni se arrancó un backend o navegador real.

## Conservación

Se registraron hashes de 79 archivos al comenzar. `credentials.json`, `token.json`, `token_backup.json` y `.env` reales permanecen idénticos, al igual que los 17 JSON de campañas registrados. No se imprimieron sus hashes ni contenidos. El alcance final comprende cuatro archivos de aplicación, dos de pruebas y tres documentos; se preservaron los cambios locales anteriores.

## Siguiente paso

Usar [la preparación de distribución](../drive-desktop-distribution.md) para revisar el proyecto Cloud y aprobar el cliente común cuando corresponda. La prueba real del EXE y la protección completa del almacenamiento de tokens siguen pendientes. La separación de rutas aún requiere cuotas, modelos y otros tokens/escritores de grabación. No se activaron estos cambios en un proceso verificado de la app.
