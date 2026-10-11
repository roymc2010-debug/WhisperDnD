// =========================================================================
// WhisperDnD - utils.js
// Funciones de utilidad general, alertas, formato de texto y render KaTeX
// =========================================================================

function escapeHtml(str) {
  return String(str).replace(/[&<>'"]/g, 
    t => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t)
  );
}

function sanitizeFormulaDelimiters(text) {
  if (!text || typeof text !== 'string') return text || '';
  // Elimina signos de dólar alrededor de factores de aumento o escalas ($40x$ -> 40x, $10x$ -> 10x)
  let clean = text.replace(/\$\s*([0-9]+(?:\.[0-9]+)?\s*[xX])\s*\$/g, '$1');
  // También limpia porcentajes o unidades comunes envueltas en $: "$50%$" -> "50%", "$10 mm$" -> "10 mm"
  clean = clean.replace(/\$\s*([0-9]+(?:\.[0-9]+)?\s*(?:%|mm|cm|m|km|g|kg|mg|ml|mL|L|fps|rpm|Hz|kHz|MHz|GHz))\s*\$/g, '$1');
  return clean;
}

function renderMarkdownWithKaTeX(text) {
  if (!text) return '';
  const sanitized = sanitizeFormulaDelimiters(text);
  
  // 1. Si marked está disponible, convertir Markdown a HTML
  let html = typeof marked !== 'undefined' ? marked.parse(sanitized) : sanitized;
  
  // 2. Renderizar KaTeX si la librería está cargada
  if (typeof renderMathInElement !== 'undefined') {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    try {
      renderMathInElement(tempDiv, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false }
        ],
        throwOnError: false
      });
      return tempDiv.innerHTML;
    } catch (e) {
      console.warn("KaTeX render warning:", e);
      return html;
    }
  }
  
  return html;
}

function formatSeconds(sec) {
  if (!sec || isNaN(sec)) return "00:00";
  const m = Math.floor(sec / 60).toString().padStart(2, "0");
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function formatTime(totalSecs) {
  const s = Math.max(0, Math.floor(totalSecs || 0));
  const hrs = Math.floor(s / 3600).toString().padStart(2, "0");
  const mins = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
  const secs = (s % 60).toString().padStart(2, "0");
  return `${hrs}:${mins}:${secs}`;
}

function capitalize(s) {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function cleanNoteDisplayTitle(titleStr, filename) {
  let t = (titleStr || "").trim();
  if (!t && filename) {
    t = filename.replace(/^apuntes_(?:file_)?/i, '')
                .replace(/_\d{8}_\d{6}\.md$/i, '')
                .replace(/\.md$/i, '')
                .replace(/_(?:es|en)$/i, '')
                .replace(/_/g, ' ')
                .trim();
  }
  if (!t) return "Apuntes de Clase";
  t = t.replace(/^#+\s*/, '')
       .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}]/gu, '')
       .trim();
  let prev = "";
  while (prev !== t) {
    prev = t;
    t = t.replace(/^(?:BRIEFING EJECUTIVO Y GU[ÍI]A DE ESTUDIO PROFUNDA|EXECUTIVE BRIEFING & DEEP STUDY GUIDE|GU[ÍI]A DE ESTUDIO PROFUNDA|DEEP STUDY GUIDE|GU[ÍI]A DE ESTUDIO|STUDY GUIDE|BRIEFING EJECUTIVO|EXECUTIVE BRIEFING|APUNTES DE CLASE|APUNTES|NOTAS DE CLASE|TOPIC|MATERIA|TEMA|RESUMEN EJECUTIVO|EXECUTIVE SUMMARY)[\s:–—\-]+/i, '').trim();
  }
  if (t.includes(':')) {
    const parts = t.split(':').map(p => p.trim()).filter(Boolean);
    if (parts.length === 2 && parts[0].toLowerCase() === parts[1].toLowerCase()) {
      t = parts[0];
    } else if (parts.length >= 2 && ['topic', 'tema', 'materia', 'title', 'título', 'titulo', 'subject'].includes(parts[0].toLowerCase())) {
      t = parts.slice(1).join(': ').trim();
    }
  }
  return t || "Apuntes de Clase";
}

function showAlert(msg) {
  const box = document.getElementById("alertBox");
  if (!box) return;
  const msgEl = document.getElementById("alertMessage");
  const iconEl = document.getElementById("alertIcon");
  if (msgEl) msgEl.textContent = msg;
  if (iconEl) iconEl.innerHTML = `<span class="text-rose-400">⚠️</span>`;
  box.className = "rounded-xl border border-rose-800 bg-rose-950/40 p-4 text-sm flex items-start gap-3 text-rose-200";
  box.classList.remove("hidden");
}

function showInfoAlert(msg) {
  const box = document.getElementById("alertBox");
  if (!box) return;
  const msgEl = document.getElementById("alertMessage");
  const iconEl = document.getElementById("alertIcon");
  if (msgEl) msgEl.textContent = msg;
  if (iconEl) iconEl.innerHTML = `<span class="text-indigo-400">ℹ️</span>`;
  box.className = "rounded-xl border border-indigo-800 bg-indigo-950/40 p-4 text-sm flex items-start gap-3 text-indigo-200";
  box.classList.remove("hidden");
}

function showSuccessAlert(msg) {
  const box = document.getElementById("alertBox");
  if (!box) return;
  const msgEl = document.getElementById("alertMessage");
  const iconEl = document.getElementById("alertIcon");
  if (msgEl) msgEl.textContent = msg;
  if (iconEl) iconEl.innerHTML = `<span class="text-emerald-400">✅</span>`;
  box.className = "rounded-xl border border-emerald-800 bg-emerald-950/40 p-4 text-sm flex items-start gap-3 text-emerald-200";
  box.classList.remove("hidden");
}

function hideAlert() {
  const box = document.getElementById("alertBox");
  if (box) box.classList.add("hidden");
}

function showTransientAlert(msg, type = "info") {
  if (type === "success") showSuccessAlert(msg);
  else if (type === "warning" || type === "error") showAlert(msg);
  else showInfoAlert(msg);

  setTimeout(() => {
    hideAlert();
  }, 3500);
}

function wipeCacheAndStartOver() {
  if (confirm("¿Estás seguro de que deseas limpiar todo el almacenamiento local de campañas y empezar de cero?\n\nEsta acción borrará la caché del navegador y recargará la aplicación limpiamente.")) {
    localStorage.clear();
    sessionStorage.clear();
    window._isPageNavigatingOrReloading = true;
    window.location.reload();
  }
}

// Window bindings
window.escapeHtml = escapeHtml;
window.sanitizeFormulaDelimiters = sanitizeFormulaDelimiters;
window.renderMarkdownWithKaTeX = renderMarkdownWithKaTeX;
window.formatSeconds = formatSeconds;
window.formatTime = formatTime;
window.capitalize = capitalize;
window.cleanNoteDisplayTitle = cleanNoteDisplayTitle;
window.showAlert = showAlert;
window.showInfoAlert = showInfoAlert;
window.showSuccessAlert = showSuccessAlert;
window.hideAlert = hideAlert;
window.showTransientAlert = showTransientAlert;
window.wipeCacheAndStartOver = wipeCacheAndStartOver;
