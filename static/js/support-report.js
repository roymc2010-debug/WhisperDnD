/* Download only structured support metadata; do not send API keys or session data. */
async function downloadSupportReport() {
  const button = document.getElementById('btnDownloadSupportReport');
  const status = document.getElementById('supportReportStatus');
  if (!button || button.disabled) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = 'Preparando reporte…';
  status.textContent = 'Preparando el archivo de texto.';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let url, link;
  try {
    const response = await fetch('/api/support/report', {cache: 'no-store', signal: controller.signal});
    if (!response.ok || !response.headers.get('content-type')?.startsWith('text/plain')) {
      throw new Error('Report unavailable');
    }
    const blob = await response.blob();
    url = URL.createObjectURL(blob);
    link = document.createElement('a');
    link.href = url;
    link.download = 'WhisperDnD-reporte-errores.txt';
    document.body.appendChild(link);
    link.click();
    status.textContent = 'Descarga iniciada. El reporte no se envió a nadie; puedes revisarlo antes de compartirlo.';
  } catch (_) {
    status.textContent = 'No se pudo descargar el reporte. Comprueba que la app siga abierta y vuelve a intentar.';
  } finally {
    clearTimeout(timeout);
    if (link) link.remove();
    // Give the browser time to consume the download before releasing its URL.
    if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
    button.disabled = false;
    button.textContent = label;
  }
}
