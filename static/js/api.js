// =========================================================================
// WhisperDnD - api.js
// Gestión de API Keys multi-inquilino (Groq & Gemini) y estado del sistema
// =========================================================================

var serverHasGroq = false;
var serverHasGemini = false;

function getUserApiHeaders() {
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  const groq = (localStorage.getItem("user_groq_key") || (groqInput ? groqInput.value : "") || "").trim();
  const gemini = (localStorage.getItem("user_gemini_key") || (geminiInput ? geminiInput.value : "") || "").trim();
  const headers = {};
  if (groq) headers["X-Groq-Api-Key"] = groq;
  if (gemini) headers["X-Gemini-Api-Key"] = gemini;
  return headers;
}

async function loadUserApiKeys() {
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  let groqKey = (localStorage.getItem("user_groq_key") || "").trim();
  let geminiKey = (localStorage.getItem("user_gemini_key") || "").trim();

  // Si no están en localStorage de este navegador, cargarlas automáticamente desde el servidor (.env)
  if (!groqKey || !geminiKey) {
    try {
      const res = await fetch("/api/config/keys");
      if (res.ok) {
        const data = await res.json();
        if (!groqKey && data.groq_key) {
          groqKey = data.groq_key;
          localStorage.setItem("user_groq_key", groqKey);
        }
        if (!geminiKey && data.gemini_key) {
          geminiKey = data.gemini_key;
          localStorage.setItem("user_gemini_key", geminiKey);
        }
      }
    } catch (e) {
      console.warn("Could not fetch server configured keys:", e);
    }
  }

  if (groqInput) groqInput.value = groqKey;
  if (geminiInput) geminiInput.value = geminiKey;
  updateApiKeyStatusIndicators(groqKey, geminiKey);
  updateOnboardingBannerState();
}

async function saveUserApiKeys() {
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

  // Persistir permanentemente en el servidor (.env) para que nunca se borren ni se desincronicen
  try {
    await fetch("/api/config/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groq_key: groqVal, gemini_key: geminiVal })
    });
  } catch (e) {
    console.warn("Error guardando llaves en el servidor:", e);
  }

  updateApiKeyStatusIndicators(groqVal, geminiVal);
  updateOnboardingBannerState();

  const feedback = document.getElementById("apiKeySaveFeedback");
  if (feedback) {
    feedback.textContent = "⏳ Guardando y verificando credenciales...";
    feedback.className = "text-xs text-amber-400 font-medium";
    feedback.classList.remove("hidden");
  }

  checkApiKeysStatus(true);
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
    feedback.textContent = "🗑️ Llaves locales eliminadas de este navegador.";
    feedback.className = "text-xs text-amber-400 font-medium";
    feedback.classList.remove("hidden");
    setTimeout(() => {
      feedback.classList.add("hidden");
    }, 3500);
  }

  checkApiKeysStatus(false);
}

function resetToServerDefaultKeys() {
  localStorage.removeItem("user_groq_key");
  localStorage.removeItem("user_gemini_key");
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  if (groqInput) groqInput.value = "";
  if (geminiInput) geminiInput.value = "";
  updateApiKeyStatusIndicators("", "");

  const feedback = document.getElementById("apiKeySaveFeedback");
  if (feedback) {
    feedback.textContent = "⚡ Conectando con las llaves predeterminadas del servidor (.env)...";
    feedback.className = "text-xs text-amber-300 font-semibold";
    feedback.classList.remove("hidden");
  }

  checkApiKeysStatus(true);
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
      groqIndicator.textContent = "Guardada en este navegador";
      groqIndicator.className = "text-[11px] text-emerald-400 font-mono";
    } else {
      groqIndicator.textContent = "⚪ No configurada localmente";
      groqIndicator.className = "text-[11px] text-slate-500 font-mono";
    }
  }
  if (geminiIndicator) {
    if (gemini) {
      geminiIndicator.textContent = "Guardada en este navegador";
      geminiIndicator.className = "text-[11px] text-emerald-400 font-mono";
    } else {
      geminiIndicator.textContent = "⚪ No configurada localmente";
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

function updateOnboardingBannerState() {
  const banner = document.getElementById("apiOnboardingBanner");
  if (!banner) return;
  const hasLocalGroq = Boolean((localStorage.getItem("user_groq_key") || "").trim());
  const hasLocalGemini = Boolean((localStorage.getItem("user_gemini_key") || "").trim());
  const hasAnyEffectiveGroq = hasLocalGroq || Boolean(serverHasGroq);
  const hasAnyEffectiveGemini = hasLocalGemini || Boolean(serverHasGemini);

  if (hasAnyEffectiveGroq && hasAnyEffectiveGemini) {
    banner.classList.add("hidden");
  } else {
    banner.classList.remove("hidden");
    const badge = document.getElementById("apiOnboardingBadge");
    if (badge) {
      badge.textContent = "Paso requerido";
      badge.className = "px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-rose-500/20 text-rose-200 border border-rose-500/30";
    }
  }
}

function updateSystemStatusIndicator() {
  const hasGroq = !!(localStorage.getItem('user_groq_key') || serverHasGroq);
  const hasGemini = !!(localStorage.getItem('user_gemini_key') || serverHasGemini);
  const isFullyReady = hasGroq && hasGemini;

  updateOnboardingBannerState();

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
  if (isReady === "pending") {
    badge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30";
    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span> <span>Verificando...</span>`;
    badge.title = `Comprobando conexión con ${label}...`;
    return;
  }
  if (isReady) {
    badge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30";
    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> <span>Operativa</span>`;
    badge.title = message || `${label} API operativa`;
  } else {
    badge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30";
    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> <span>Desconectada</span>`;
    badge.title = message || `${label} no configurada o inaccesible`;
  }
}

async function checkApiKeysStatus(showToast = false) {
  // If user clicked "Probar Conexión" after typing keys in inputs without clicking Guardar yet, persist them first
  if (showToast) {
    const groqInput = document.getElementById("userGroqKeyInput");
    const geminiInput = document.getElementById("userGeminiKeyInput");
    if (groqInput && groqInput.value.trim()) {
      localStorage.setItem("user_groq_key", groqInput.value.trim());
    }
    if (geminiInput && geminiInput.value.trim()) {
      localStorage.setItem("user_gemini_key", geminiInput.value.trim());
    }
  }

  updateKeyBadge("badgeGroqStatus", "pending", "Groq");
  updateKeyBadge("badgeGeminiStatus", "pending", "Gemini");

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
      if (data.oauth_redirect_uri) {
        const redirectEl = document.getElementById("currentOAuthRedirectUriDisplay");
        if (redirectEl) redirectEl.textContent = data.oauth_redirect_uri;
      }

      updateKeyBadge("badgeGroqStatus", data.groq, "Groq", data.groq_message);
      updateKeyBadge("badgeGeminiStatus", data.gemini, "Gemini", data.gemini_message);

      const groqMsgEl = document.getElementById("groqStatusMsg");
      if (groqMsgEl) {
        groqMsgEl.textContent = data.groq_message || (data.groq ? "Groq Whisper Large-v3 listo." : "Sin configurar.");
        groqMsgEl.className = data.groq ? "text-[10px] text-emerald-400/90 font-mono truncate" : "text-[10px] text-slate-500 font-mono truncate";
      }

      const geminiMsgEl = document.getElementById("geminiStatusMsg");
      if (geminiMsgEl) {
        geminiMsgEl.textContent = data.gemini_message || (data.gemini ? "Gemini 2.5 Flash listo." : "Sin configurar.");
        geminiMsgEl.className = data.gemini ? "text-[10px] text-emerald-400/90 font-mono truncate" : "text-[10px] text-slate-500 font-mono truncate";
      }

      // Update input-level labels: ONLY show green on the input card if the user actually has a personal key saved locally!
      const hasGroqLocal = Boolean((localStorage.getItem("user_groq_key") || "").trim());
      const hasGeminiLocal = Boolean((localStorage.getItem("user_gemini_key") || "").trim());
      const groqIndicator = document.getElementById("groqKeySavedIndicator");
      const geminiIndicator = document.getElementById("geminiKeySavedIndicator");

      if (groqIndicator) {
        if (hasGroqLocal && data.groq) {
          groqIndicator.textContent = "🟢 Llave personal verificada";
          groqIndicator.className = "text-[11px] text-emerald-400 font-mono font-semibold";
        } else if (hasGroqLocal && !data.groq) {
          groqIndicator.textContent = "🔴 Llave inválida o error";
          groqIndicator.className = "text-[11px] text-rose-400 font-mono font-semibold";
        } else if (!hasGroqLocal && data.groq) {
          groqIndicator.textContent = "⚪ Sin llave local (Servidor activo)";
          groqIndicator.className = "text-[11px] text-amber-300/90 font-mono";
        } else {
          groqIndicator.textContent = "⚪ No configurada";
          groqIndicator.className = "text-[11px] text-slate-500 font-mono";
        }
      }

      if (geminiIndicator) {
        if (hasGeminiLocal && data.gemini) {
          geminiIndicator.textContent = "🟢 Llave personal verificada";
          geminiIndicator.className = "text-[11px] text-emerald-400 font-mono font-semibold";
        } else if (hasGeminiLocal && !data.gemini) {
          geminiIndicator.textContent = "🔴 Llave inválida o error";
          geminiIndicator.className = "text-[11px] text-rose-400 font-mono font-semibold";
        } else if (!hasGeminiLocal && data.gemini) {
          geminiIndicator.textContent = "⚪ Sin llave local (Servidor activo)";
          geminiIndicator.className = "text-[11px] text-amber-300/90 font-mono";
        } else {
          geminiIndicator.textContent = "⚪ No configurada";
          geminiIndicator.className = "text-[11px] text-slate-500 font-mono";
        }
      }

      if (typeof updateDriveUIState === "function") {
        if (data.drive) {
          updateDriveUIState(true, data.drive_email || null);
        } else if (!window.isGoogleDriveConnected) {
          updateDriveUIState(false);
        }
      }

      const feedback = document.getElementById("apiKeySaveFeedback");
      if (feedback && showToast) {
        feedback.classList.remove("hidden");
        if (data.groq && data.gemini) {
          const msg = (hasGroqLocal && hasGeminiLocal)
            ? "✅ ¡Tus llaves personales de Groq y Gemini fueron guardadas y verificadas con éxito!"
            : "✅ Conexión operativa con Groq y Gemini verificada.";
          feedback.textContent = msg;
          feedback.className = "text-xs text-emerald-400 font-semibold";
          if (typeof showSuccessAlert === "function") showSuccessAlert(msg);
        } else if (!data.groq && !data.gemini) {
          const msg = "⚠️ Ninguna de las llaves pudo autenticarse. Verifica que hayas copiado la llave completa (gsk_... y AIzaSy...).";
          feedback.textContent = msg;
          feedback.className = "text-xs text-rose-400 font-semibold";
          if (typeof showAlert === "function") showAlert(msg);
        } else {
          const msg = `⚠️ Estado parcial — Groq: ${data.groq ? '🟢 OK' : '🔴 Falla (' + (data.groq_message || 'revisar') + ')'} | Gemini: ${data.gemini ? '🟢 OK' : '🔴 Falla (' + (data.gemini_message || 'revisar') + ')'}`;
          feedback.textContent = msg;
          feedback.className = "text-xs text-amber-400 font-semibold";
          if (typeof showAlert === "function") showAlert(msg);
        }
        setTimeout(() => {
          feedback.classList.add("hidden");
        }, 7000);
      }
    }
  } catch (err) {
    console.warn("Could not check API keys status:", err);
    updateKeyBadge("badgeGroqStatus", false, "Groq", "Servidor no responde");
    updateKeyBadge("badgeGeminiStatus", false, "Gemini", "Servidor no responde");
    const feedback = document.getElementById("apiKeySaveFeedback");
    if (feedback && showToast) {
      feedback.classList.remove("hidden");
      feedback.textContent = "⚠️ Servidor no disponible (Failed to fetch). Inicia el servidor ejecutando 'start.bat' o 'python main.py' en http://localhost:8080.";
      feedback.className = "text-xs text-rose-400 font-semibold";
      if (typeof showAlert === "function") {
        showAlert("⚠️ Error de conexión: El servidor WhisperDnD no está respondiendo en http://localhost:8080. Inícialo con 'start.bat' o 'python main.py'.");
      }
    }
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
  const percentDisplay = document.getElementById("quotaPercentDisplay");
  const progressBar = document.getElementById("quotaProgressBar");
  const statusDot = document.getElementById("quotaStatusDot");
  const statusSummary = document.getElementById("quotaStatusSummary");
  const tokensSummary = document.getElementById("quotaTokensSummary");
  const mobilePercent = document.getElementById("mobileQuotaPercent");
  const mobileDot = document.getElementById("mobileQuotaDot");
  const quotaContainer = document.getElementById("apiQuotaContainer");

  const tokensUsed = (data && data.gemini && typeof data.gemini.tokens_used === "number")
    ? data.gemini.tokens_used
    : (data && typeof data.tokens_used === "number" ? data.tokens_used : 0);

  const tokensLimit = (data && data.gemini && typeof data.gemini.tokens_limit === "number")
    ? data.gemini.tokens_limit
    : (data && typeof data.tokens_limit === "number" ? data.tokens_limit : null);

  const tokensRem = (data && data.gemini && typeof data.gemini.tokens_remaining === "number")
    ? data.gemini.tokens_remaining
    : (tokensLimit !== null ? Math.max(0, tokensLimit - tokensUsed) : null);

  const hasValidData = Boolean(
    data &&
    tokensLimit !== null &&
    tokensLimit > 0 &&
    tokensRem !== null &&
    tokensRem >= 0
  );

  // Si el límite o cuota no está disponible, mostrar estado neutral disponible (sin falsas alarmas)
  if (!hasValidData) {
    if (percentDisplay) {
      percentDisplay.textContent = "100.0%";
      percentDisplay.className = "font-mono font-bold tabular-nums text-xs text-slate-400";
    }
    if (progressBar) {
      progressBar.style.width = "100%";
      progressBar.className = "h-full rounded-full transition-all duration-300 bg-slate-700";
    }
    if (statusDot) {
      statusDot.className = "w-2 h-2 rounded-full bg-slate-500";
    }
    if (statusSummary) {
      statusSummary.textContent = "Disponible";
      statusSummary.className = "font-semibold text-slate-400";
    }
    if (tokensSummary) {
      tokensSummary.textContent = "Gemini Tokens";
    }
    if (mobilePercent) {
      mobilePercent.textContent = "100%";
      mobilePercent.className = "tabular-nums text-slate-400";
    }
    if (mobileDot) {
      mobileDot.className = "w-1.5 h-1.5 rounded-full bg-slate-500";
    }
    return;
  }

  // Porcentaje DISPONIBLE real (tokens disponibles / límite total)
  const pctRemaining = Math.max(0.0, Math.min(100.0, (tokensRem / tokensLimit) * 100.0));
  const pctStr = `${pctRemaining.toFixed(1)}%`;

  // Escala de estado según disponibilidad (100% es óptima/llena, <5% es crítica):
  let colorClass = "emerald";
  let statusText = "Óptima";
  let isCritical = false;

  if (pctRemaining < 5.0) {
    colorClass = "rose";
    statusText = "Crítica (<5%)";
    isCritical = true;
  } else if (pctRemaining < 15.0) {
    colorClass = "amber";
    statusText = "Baja (<15%)";
  } else if (pctRemaining < 50.0) {
    colorClass = "yellow";
    statusText = "Moderada";
  } else {
    colorClass = "emerald";
    statusText = "Óptima";
  }

  if (percentDisplay) {
    percentDisplay.textContent = pctStr;
    percentDisplay.className = `font-mono font-bold tabular-nums text-xs text-${colorClass}-400`;
  }
  if (progressBar) {
    progressBar.style.width = `${pctRemaining.toFixed(1)}%`;
    progressBar.className = `h-full rounded-full transition-all duration-300 bg-${colorClass}-500`;
  }
  if (statusDot) {
    statusDot.className = `w-2 h-2 rounded-full bg-${colorClass}-400 ${isCritical ? 'animate-pulse' : ''}`;
  }
  if (statusSummary) {
    statusSummary.textContent = statusText;
    statusSummary.className = `font-semibold text-${colorClass}-400`;
  }
  if (tokensSummary) {
    const geminiK = Math.round(tokensRem / 1000);
    tokensSummary.textContent = `~${geminiK}k tok disp.`;
  }

  if (mobilePercent) {
    mobilePercent.textContent = pctStr;
    mobilePercent.className = `tabular-nums text-${colorClass}-400`;
  }
  if (mobileDot) {
    mobileDot.className = `w-1.5 h-1.5 rounded-full bg-${colorClass}-400 ${isCritical ? 'animate-pulse' : ''}`;
  }

  if (quotaContainer) {
    const resetInfo = data.resets_in ? ` (se recarga en ~${data.resets_in} a las 00:00 UTC)` : ' (se recarga a las 00:00 UTC diariamente)';
    quotaContainer.title = `Cuota disponible: ${pctStr} (~${Math.round(tokensRem / 1000)}k tokens restantes)${resetInfo}`;
  }
}

async function checkQuotaBeforeAction(actionName = "este proceso") {
  try {
    const quota = await fetchApiQuota();
    if (!quota) return true;

    const tokensUsed = quota.gemini?.tokens_used ?? quota.tokens_used ?? 0;
    const tokensLimit = quota.gemini?.tokens_limit ?? quota.tokens_limit;
    const tokensRem = quota.gemini?.tokens_remaining ?? (tokensLimit ? Math.max(0, tokensLimit - tokensUsed) : null);

    const pctRemaining = (tokensLimit && tokensLimit > 0 && typeof tokensRem === "number")
      ? (tokensRem / tokensLimit) * 100.0
      : (typeof quota.percent_remaining === "number" ? quota.percent_remaining : null);

    const isCritical = pctRemaining !== null && pctRemaining < 5.0;

    if (isCritical) {
      const remainingPct = pctRemaining.toFixed(1);
      const userWantsToProceed = confirm(
        `⚠️ ADVERTENCIA DE CUOTA DE API CRÍTICA (${remainingPct}% disponible)\n\n` +
        `Te queda menos del 5% de tu cuota diaria de tokens de Gemini. Si inicias ${actionName}, existe riesgo de que los tokens se agoten y el proceso se interrumpa.\n\n` +
        `¿Deseas continuar de todas formas bajo tu propio riesgo?`
      );
      if (!userWantsToProceed) {
        if (typeof showFloatingToast === "function") {
          showFloatingToast(`Operación cancelada para preservar tu cuota de tokens disponible (${remainingPct}%).`, "warning", 6000);
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
