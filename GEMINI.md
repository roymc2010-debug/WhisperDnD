# Directivas de Operación y Arquitectura - WhisperDnD

## 1. HERRAMIENTAS DE OPERACIÓN, LECTURA Y EDICIÓN
- **Uso de herramientas por Codex y agentes**: Se autoriza explícitamente a Codex y a los agentes del entorno a utilizar sus herramientas nativas disponibles (ej. `read_file`, `edit_file`, `write_file`, `view_file`, `replace_file_content` o las herramientas nativas equivalentes de su entorno) para leer, editar y verificar archivos dentro de este repositorio (`C:\Users\HP\WhisperDnD`).
- **Exploración acotada**: Priorizar siempre las herramientas nativas de lectura sobre comandos de terminal. No usar scripts de consola (PowerShell, `python -c ...`, `Select-String`, `grep`, `cat`, etc.) para buscar texto o calcular números de línea cuando se disponga de herramientas nativas de lectura.
- No ampliar permisos a otras carpetas fuera de este repositorio ni eludir controles de seguridad.

## 2. POLÍTICA DE CERO PROCESOS EN SEGUNDO PLANO (ZERO HANGING BACKGROUND TASKS)
- **NUNCA dejar procesos corriendo en segundo plano**: En Windows, lanzar comandos de terminal repetitivos o con timeouts cortos acumula procesos en la cola de tareas ("XX tasks running"), saturando la interfaz del usuario.
- Si en algún momento el usuario pide explícitamente ejecutar una acción de terminal (por ejemplo, instalar un paquete pip o lanzar pruebas unitarias), debe ejecutarse de forma aislada, síncrona y con confirmación.
- Nunca encadenar llamadas de terminal para exploración del código.

## 3. DISEÑO Y CALIDAD DE CÓDIGO
- Respetar los estándares de diseño limpio (`emil-design-eng`, `frontend-ui-engineering`, `impeccable`):
  - Tipografía estable (`tabular-nums` para valores numéricos dinámicos y porcentajes).
  - Cero estéticas genéricas de IA (evitar brillos morados o animaciones innecesarias).
  - Interactividad fluida con `requestAnimationFrame` para animaciones y estados de progreso.
