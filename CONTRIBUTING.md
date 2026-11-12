# Cambios y reportes durante la evaluación

Participar en pruebas no concede permiso general de redistribución o modificación del software; consulta [LICENSE](LICENSE). Acuerda las contribuciones de código con quien mantiene el proyecto antes de enviarlas.

## Reportes

Describe el paso realizado, resultado esperado, resultado observado y hora aproximada. Adjunta únicamente el reporte descargado desde Ajustes y capturas revisadas. No incluyas claves, tokens, `.env`, audios, campañas o respaldos como diagnóstico general. La recepción pública de archivos todavía no está habilitada.

## Conservación de datos

- Identifica los módulos afectados y conserva los cambios locales. No mezcles copias de laboratorio ni reconstruyas campañas sin autorización.
- Registra el estado y una referencia de los archivos antes de editar. Compara contra el inicio del trabajo, además de Git HEAD.
- Usa perfiles temporales, campañas inventadas y proveedores simulados en pruebas automáticas; no escribas sobre campañas reales.
- Un fallo de generación o exportación no autoriza a duplicar sesiones, sobrescribir el grupo o sustituir fuentes.
- No instales herramientas, descargues modelos ni hagas llamadas de pago como efecto secundario de una prueba sin coordinarlo.

## Verificación

Empieza por las pruebas pertinentes y cubre la regresión antes de cambiar comportamiento. Utiliza el [harness offline](scripts/run_offline_tests.py) para backend y las pruebas de `tests/frontend` para interfaz. Revisa accesibilidad y ventanas estrechas al cambiar controles.

La [guía manual](docs/prueba-manual-antes-del-exe.md) cubre los dispositivos y cuentas reales. Distingue entre código probado, proceso ejecutándose y build instalable.

## Publicación

Revisa los archivos exactos del commit. No añadas indiscriminadamente datos, copias internas o credenciales. Ignorar un archivo no elimina las versiones que ya entraron en el historial. No publiques binarios sin revisar dependencias, recursos y licencias.
