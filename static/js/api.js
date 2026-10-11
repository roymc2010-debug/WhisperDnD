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
