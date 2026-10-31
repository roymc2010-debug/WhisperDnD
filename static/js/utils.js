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

function showFloatingToast(msg, type = "info", duration = 5000, actionLabel = null, actionCallback = null) {
  if (!msg) return;
  let container = document.getElementById("floatingToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "floatingToastContainer";
    container.className = "fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-sm sm:max-w-md w-full pointer-events-none px-3 sm:px-0";
    container.setAttribute("aria-live", "assertive");
    document.body.appendChild(container);
  }

  // Evitar duplicados exactos si ya está visible
  const existing = Array.from(container.children).find(c => c.getAttribute("data-msg") === msg);
  if (existing) {
    existing.classList.add("ring-2", "ring-white/40");
    setTimeout(() => existing.classList.remove("ring-2", "ring-white/40"), 300);
    return existing;
  }

  const toast = document.createElement("div");
  toast.setAttribute("data-msg", msg);
  toast.className = "pointer-events-auto rounded-2xl p-4 shadow-2xl backdrop-blur-md border text-sm font-sans flex items-start gap-3 transition-all duration-200 transform translate-y-[-10px] opacity-0 select-none";

  let iconHtml = WhisperIcons.markup("info");
  if (type === "error") {
    toast.className += " bg-rose-950/95 border-rose-500/80 text-rose-100 shadow-rose-950/60";
    iconHtml = `<div class="w-6 h-6 rounded-lg bg-rose-900/80 border border-rose-600 flex items-center justify-center text-xs font-bold shrink-0 text-rose-200"><span data-ui-icon=close aria-hidden=true></span></div>`;
  } else if (type === "warning") {
    toast.className += " bg-amber-950/95 border-amber-500/80 text-amber-100 shadow-amber-950/60";
    iconHtml = `<div class="w-6 h-6 rounded-lg bg-amber-900/80 border border-amber-600 flex items-center justify-center text-xs font-bold shrink-0 text-amber-200"><span data-ui-icon=warning aria-hidden=true></span></div>`;
  } else if (type === "success") {
    toast.className += " bg-emerald-950/95 border-emerald-500/80 text-emerald-100 shadow-emerald-950/60";
    iconHtml = `<div class="w-6 h-6 rounded-lg bg-emerald-900/80 border border-emerald-600 flex items-center justify-center text-xs font-bold shrink-0 text-emerald-200"><span data-ui-icon=check aria-hidden=true></span></div>`;
  } else {
    toast.className += " bg-slate-900/95 border-slate-700/80 text-slate-100 shadow-slate-950/60";
    iconHtml = `<div class="w-6 h-6 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold shrink-0 text-sky-300"><span data-ui-icon=info aria-hidden=true></span></div>`;
  }

  const contentCol = document.createElement("div");
  contentCol.className = "flex-1 min-w-0 pr-1";

  const textEl = document.createElement("p");
  textEl.className = "leading-relaxed whitespace-pre-wrap break-words font-medium text-sm";
  textEl.textContent = msg;
  contentCol.appendChild(textEl);

  if (actionLabel && typeof actionCallback === "function") {
    const actionBtn = document.createElement("button");
    actionBtn.type = "button";
    actionBtn.className = "mt-2 px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 active:scale-95 text-xs font-semibold transition cursor-pointer inline-flex items-center gap-1.5";
    actionBtn.textContent = actionLabel;
    actionBtn.onclick = (e) => {
      e.stopPropagation();
      dismissToast();
      actionCallback();
    };
    contentCol.appendChild(actionBtn);
  }

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "text-slate-400 hover:text-white active:scale-90 text-base leading-none transition cursor-pointer p-0.5 shrink-0";
  closeBtn.innerHTML = "&times;";
  closeBtn.title = "Cerrar notificación";

  toast.innerHTML = iconHtml;
  toast.appendChild(contentCol);
  toast.appendChild(closeBtn);

  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-[-10px]", "opacity-0");
    toast.classList.add("translate-y-0", "opacity-100");
  });

  let dismissTimer = null;
  const dismissToast = () => {
    if (dismissTimer) clearTimeout(dismissTimer);
    toast.classList.remove("translate-y-0", "opacity-100");
    toast.classList.add("translate-y-[-10px]", "opacity-0");
    setTimeout(() => {
      try { toast.remove(); } catch (_) {}
    }, 200);
  };

  closeBtn.onclick = dismissToast;

  if (duration && duration > 0) {
    dismissTimer = setTimeout(dismissToast, duration);
    toast.addEventListener("mouseenter", () => {
      if (dismissTimer) clearTimeout(dismissTimer);
    });
    toast.addEventListener("mouseleave", () => {
      dismissTimer = setTimeout(dismissToast, 2000);
    });
  }

  return toast;
}

function showAlert(msg, type = "error") {
  if (!msg) return;

  // Si el mensaje es de éxito o info, enrutar a la función adecuada sin modal ni alerta roja
  const lowerMsg = String(msg).toLowerCase();
  if (type === "success" || lowerMsg.startsWith("✓") || lowerMsg.includes("éxito") || lowerMsg.includes("guardad") || lowerMsg.includes("correctamente")) {
    showSuccessAlert(msg);
    return;
  }
  if (type === "info" || lowerMsg.startsWith("ℹ") || lowerMsg.startsWith("🎧") || lowerMsg.startsWith("🔔")) {
    showInfoAlert(msg);
    return;
  }

  // Notificación flotante no bloqueante
  showFloatingToast(msg, type === "warning" ? "warning" : "error", 6000);

  // Cuadro fijo superior: se muestra solo en advertencias/errores reales y auto-desaparece a los 5 segundos
  const box = document.getElementById("alertBox");
  if (box) {
    const msgEl = document.getElementById("alertMessage");
    const iconEl = document.getElementById("alertIcon");
    if (msgEl) msgEl.textContent = msg;
    if (iconEl) iconEl.innerHTML = `<span class="text-rose-400"><span data-ui-icon=warning aria-hidden=true></span></span>`;
    box.className = "rounded-xl border border-rose-800 bg-rose-950/40 p-4 text-sm flex items-start gap-3 text-rose-200 shadow-lg";
    box.classList.remove("hidden");
    clearTimeout(box._autoHideTimer);
    box._autoHideTimer = setTimeout(() => {
      hideAlert();
    }, 5000);
  }
}

function showInfoAlert(msg) {
  if (!msg) return;
  showFloatingToast(msg, "info", 4500);
}

function showSuccessAlert(msg) {
  if (!msg) return;
  showFloatingToast(msg, "success", 4000);
}

function hideAlert() {
  const box = document.getElementById("alertBox");
  if (box) {
    box.classList.add("hidden");
    if (box._autoHideTimer) {
      clearTimeout(box._autoHideTimer);
      box._autoHideTimer = null;
    }
    const msgEl = document.getElementById("alertMessage");
    if (msgEl) msgEl.textContent = "";
  }
}

function showTransientAlert(msg, type = "info") {
  if (type === "success") showSuccessAlert(msg);
  else if (type === "warning" || type === "error") showAlert(msg, type);
  else showInfoAlert(msg);
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
window.showFloatingToast = showFloatingToast;
window.showAlert = showAlert;
window.showInfoAlert = showInfoAlert;
window.showSuccessAlert = showSuccessAlert;
window.hideAlert = hideAlert;
window.showTransientAlert = showTransientAlert;
window.wipeCacheAndStartOver = wipeCacheAndStartOver;
