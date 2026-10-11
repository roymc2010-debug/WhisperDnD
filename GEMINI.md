# Directivas de Operación y Arquitectura - WhisperDnD

## 1. PROHIBICIÓN ESTRICTA DE COMANDOS DE TERMINAL PARA LECTURA O BÚSQUEDA
- **NUNCA usar `run_command` ni scripts de consola (PowerShell, `python -c ...`, `Select-String`, `grep`, `cat`, etc.)** para buscar cadenas de texto, inspeccionar archivos o calcular números de línea.
- Todas las operaciones de lectura deben realizarse **exclusivamente con la herramienta nativa `view_file`**.
- Todas las modificaciones de archivos deben realizarse **exclusivamente con `replace_file_content` o `write_to_file`**.

## 2. POLÍTICA DE CERO PROCESOS EN SEGUNDO PLANO (ZERO HANGING BACKGROUND TASKS)
- **NUNCA dejar procesos corriendo en segundo plano**: En Windows, lanzar comandos de terminal repetitivos o con timeouts cortos acumula procesos en la cola de tareas ("XX tasks running"), saturando la interfaz del usuario.
- Si en algún momento el usuario pide explícitamente ejecutar una acción de terminal (por ejemplo, instalar un paquete pip o lanzar pruebas unitarias), debe ejecutarse de forma aislada, síncrona y con confirmación.
- Nunca encadenar llamadas de terminal para exploración del código.

## 3. DISEÑO Y CALIDAD DE CÓDIGO
- Respetar los estándares de diseño limpio (`emil-design-eng`, `frontend-ui-engineering`, `impeccable`):
  - Tipografía estable (`tabular-nums` para valores numéricos dinámicos y porcentajes).
  - Cero estéticas genéricas de IA (evitar brillos morados o animaciones innecesarias).
  - Interactividad fluida con `requestAnimationFrame` para animaciones y estados de progreso.
