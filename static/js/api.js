// =========================================================================
// WhisperDnD - api.js
// Gestión de API Keys multi-inquilino (Groq & Gemini) y estado del sistema
// =========================================================================

var serverHasGroq = false;
var serverHasGemini = false;

function getUserApiHeaders() {
  const groq = (localStorage.getItem("user_groq_key") || "").trim();
  const gemini = (localStorage.getItem("user_gemini_key") || "").trim();
  const headers = {};
  if (groq) headers["X-Groq-Api-Key"] = groq;
  if (gemini) headers["X-Gemini-Api-Key"] = gemini;
  return headers;
}

function loadUserApiKeys() {
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  const groqKey = localStorage.getItem("user_groq_key") || "";
  const geminiKey = localStorage.getItem("user_gemini_key") || "";
  if (groqInput) groqInput.value = groqKey;
  if (geminiInput) geminiInput.value = geminiKey;
  updateApiKeyStatusIndicators(groqKey, geminiKey);
}

function saveUserApiKeys() {
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  const groqVal = groqInput ? groqInput.value.trim() : "";
  const geminiVal = geminiInput ? geminiInput.value.trim() : "";

  if (groqVal) {
    localStorage.setItem("user_groq_key", groqVal);
  } else {
    localStorage.removeItem("user_groq_key");
  }

  if (geminiVal) {
    localStorage.setItem("user_gemini_key", geminiVal);
  } else {
    localStorage.removeItem("user_gemini_key");
  }

  updateApiKeyStatusIndicators(groqVal, geminiVal);

  const feedback = document.getElementById("apiKeySaveFeedback");
  if (feedback) {
    feedback.textContent = "✅ ¡Llaves guardadas correctamente en tu navegador!";
    feedback.className = "text-xs text-emerald-400 font-medium";
    feedback.classList.remove("hidden");
    setTimeout(() => {
      feedback.classList.add("hidden");
    }, 4000);
  }

  checkApiKeysStatus();
}

function clearUserApiKeys() {
  localStorage.removeItem("user_groq_key");
  localStorage.removeItem("user_gemini_key");
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  if (groqInput) groqInput.value = "";
  if (geminiInput) geminiInput.value = "";
  updateApiKeyStatusIndicators("", "");

  const feedback = document.getElementById("apiKeySaveFeedback");
  if (feedback) {
    feedback.textContent = "🗑️ Llaves locales eliminadas.";
    feedback.className = "text-xs text-amber-400 font-medium";
    feedback.classList.remove("hidden");
    setTimeout(() => {
      feedback.classList.add("hidden");
    }, 3000);
  }

  checkApiKeysStatus();
}

function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    if (btnEl) btnEl.textContent = "🙈";
  } else {
    input.type = "password";
    if (btnEl) btnEl.textContent = "👁️";
  }
}

function updateApiKeyStatusIndicators(groq, gemini) {
  const groqIndicator = document.getElementById("groqKeySavedIndicator");
  const geminiIndicator = document.getElementById("geminiKeySavedIndicator");
  if (groqIndicator) {
    if (groq) {
      groqIndicator.textContent = "Guardada localmente";
      groqIndicator.className = "text-[11px] text-emerald-400 font-mono";
    } else {
      groqIndicator.textContent = "No configurada";
      groqIndicator.className = "text-[11px] text-slate-500 font-mono";
    }
  }
  if (geminiIndicator) {
    if (gemini) {
      geminiIndicator.textContent = "Guardada localmente";
      geminiIndicator.className = "text-[11px] text-emerald-400 font-mono";
    } else {
      geminiIndicator.textContent = "No configurada";
      geminiIndicator.className = "text-[11px] text-slate-500 font-mono";
    }
  }
}

function checkAuthErrorAndRedirect(status, data) {
  if (status === 401 || (data && (data.error === "API_KEYS_REQUIRED" || data.status === 401))) {
    const msg = (data && data.message) || (data && data.detail && data.detail.message) || (typeof data.detail === "string" ? data.detail : "Por favor ingresa tus API keys de Groq y Gemini en la sección de Ajustes para continuar.");
    if (typeof showAlert === "function") {
      showAlert(`⚠️ ${msg}`);
    } else {
      alert(`⚠️ ${msg}`);
    }
    if (typeof setActiveView === "function") {
      setActiveView('settings');
    }
    const groqInput = document.getElementById("userGroqKeyInput");
    if (groqInput) groqInput.focus();
    return true;
  }
  return false;
}

function updateSystemStatusIndicator() {
  const hasGroq = !!(localStorage.getItem('user_groq_key') || serverHasGroq);
  const hasGemini = !!(localStorage.getItem('user_gemini_key') || serverHasGemini);
  const hasDrive = typeof isGoogleDriveConnected !== "undefined" ? !!isGoogleDriveConnected : false;
  const isFullyReady = hasGroq && hasGemini && hasDrive;

  const container = document.getElementById("systemStatusContainer");
  if (!container) return;

  if (isFullyReady) {
    container.innerHTML = `<div class="px-3 py-2 text-xs text-emerald-400 font-medium">● Systems Ready</div>`;
  } else {
    container.innerHTML = `<button onclick="setActiveView('settings')" class="w-full text-left px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium hover:bg-amber-500/20">⚠️ Configuración Requerida</button>`;
  }
}

function updateKeyBadge(elementId, isReady, label, message) {
  const badge = document.getElementById(elementId);
  if (!badge) return;
  if (isReady) {
    badge.className = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30";
    badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400"></span> 🟢 ${label} Listo`;
    badge.title = message || `${label} API operativa`;
  } else {
    badge.className = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30";
    badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-400"></span> 🔴 ${label} Desconectado`;
    badge.title = message || `${label} API no configurada o inaccesible`;
  }
}

async function checkApiKeysStatus() {
  try {
    const res = await fetch("/api/status/keys", {
      headers: getUserApiHeaders()
    });
    if (res.ok) {
      const data = await res.json();
      serverHasGroq = Boolean(data.groq);
      serverHasGemini = Boolean(data.gemini);
      if (data.drive !== undefined && typeof window.isGoogleDriveConnected !== "undefined") {
        window.isGoogleDriveConnected = Boolean(data.drive);
      }
      updateKeyBadge("badgeGroqStatus", data.groq, "Groq", data.groq_message);
      updateKeyBadge("badgeGeminiStatus", data.gemini, "Gemini", data.gemini_message);

      if (typeof updateDriveUIState === "function") {
        updateDriveUIState(Boolean(data.drive), data.drive_email || null);
      }
    }
  } catch (err) {
    console.warn("Could not check API keys status:", err);
  } finally {
    updateSystemStatusIndicator();
  }
}

// =========================================================================
// API TOKEN & QUOTA MONITORING
// =========================================================================
var currentApiQuotaData = null;

async function fetchApiQuota() {
  try {
    const res = await fetch("/api/system/quota", {
      headers: getUserApiHeaders()
    });
    if (!res.ok) return null;
    const data = await res.json();
    currentApiQuotaData = data;
    renderApiQuota(data);
    return data;
  } catch (err) {
    console.warn("Could not fetch API quota:", err);
    return null;
  }
}

function renderApiQuota(data) {
  if (!data) return;
  const pct = typeof data.percent_remaining === "number" ? data.percent_remaining : 100.0;
  const pctStr = `${pct.toFixed(1)}%`;

  const percentDisplay = document.getElementById("quotaPercentDisplay");
  const progressBar = document.getElementById("quotaProgressBar");
  const statusDot = document.getElementById("quotaStatusDot");
  const statusSummary = document.getElementById("quotaStatusSummary");
  const tokensSummary = document.getElementById("quotaTokensSummary");
  const mobilePercent = document.getElementById("mobileQuotaPercent");
  const mobileDot = document.getElementById("mobileQuotaDot");

  let colorClass = "emerald";
  let statusText = "Óptima";
  if (pct < 5.0) {
    colorClass = "rose";
    statusText = "Crítica (<5%)";
  } else if (pct < 15.0) {
    colorClass = "amber";
    statusText = "Baja (<15%)";
  } else if (pct < 50.0) {
    colorClass = "yellow";
    statusText = "Moderada";
  }

  if (percentDisplay) {
    percentDisplay.textContent = pctStr;
    percentDisplay.className = `font-mono font-bold tabular-nums text-xs text-${colorClass}-400`;
  }
  if (progressBar) {
    progressBar.style.width = `${Math.max(3, Math.min(100, pct))}%`;
    progressBar.className = `h-full rounded-full transition-all duration-300 bg-${colorClass}-500`;
  }
  if (statusDot) {
    statusDot.className = `w-2 h-2 rounded-full bg-${colorClass}-400 ${pct < 5.0 ? 'animate-pulse' : ''}`;
  }
  if (statusSummary) {
    statusSummary.textContent = statusText;
    statusSummary.className = `font-semibold text-${colorClass}-400`;
  }
  if (tokensSummary && data.gemini) {
    const geminiK = Math.round((data.gemini.tokens_remaining || 0) / 1000);
    tokensSummary.textContent = `~${geminiK}k tok disp.`;
  }

  if (mobilePercent) {
    mobilePercent.textContent = pctStr;
    mobilePercent.className = `tabular-nums text-${colorClass}-400`;
  }
  if (mobileDot) {
    mobileDot.className = `w-1.5 h-1.5 rounded-full bg-${colorClass}-400 ${pct < 5.0 ? 'animate-pulse' : ''}`;
  }
}

async function checkQuotaBeforeAction(actionName = "este proceso") {
  try {
    const quota = await fetchApiQuota();
    if (quota && quota.danger) {
      const userWantsToProceed = confirm(
        `⚠️ ADVERTENCIA DE CUOTA DE API CRÍTICA (${quota.percent_remaining}% restante)\n\n` +
        `Te queda menos del 5% de tu cuota de tokens disponibles hoy. Si inicias ${actionName}, existe alto riesgo de que los tokens se agoten y el proceso se quede a la mitad.\n\n` +
        `¿Deseas continuar de todas formas bajo tu propio riesgo?`
      );
      if (!userWantsToProceed) {
        if (typeof showFloatingToast === "function") {
          showFloatingToast(`Operación cancelada para preservar tu cuota de tokens restante (${quota.percent_remaining}%).`, "warning", 6000);
        }
        return false;
      }
    }
  } catch (e) {
    console.warn("Could not check quota guard:", e);
  }
  return true;
}

// Window bindings
window.getUserApiHeaders = getUserApiHeaders;
window.loadUserApiKeys = loadUserApiKeys;
window.saveUserApiKeys = saveUserApiKeys;
window.clearUserApiKeys = clearUserApiKeys;
window.togglePasswordVisibility = togglePasswordVisibility;
window.updateApiKeyStatusIndicators = updateApiKeyStatusIndicators;
window.checkAuthErrorAndRedirect = checkAuthErrorAndRedirect;
window.updateSystemStatusIndicator = updateSystemStatusIndicator;
window.updateKeyBadge = updateKeyBadge;
window.checkApiKeysStatus = checkApiKeysStatus;
window.fetchApiQuota = fetchApiQuota;
window.renderApiQuota = renderApiQuota;
window.checkQuotaBeforeAction = checkQuotaBeforeAction;
