// =========================================================================
// WhisperDnD - api.js
// Gestión de API Keys multi-inquilino (Groq & Gemini) y estado del sistema
// =========================================================================

var serverHasGroq = false;
var serverHasGemini = false;
var apiVerification = null;
var apiVerificationPending = false;
var apiVerificationError = false;
var apiVerificationSequence = 0;
var apiVerificationFailureMessage = "";
var apiVerificationPendingMessage = "Verificando conexión…";

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

function loadUserApiKeys() {
  const groqInput = document.getElementById("userGroqKeyInput");
  const geminiInput = document.getElementById("userGeminiKeyInput");
  const groqKey = (localStorage.getItem("user_groq_key") || "").trim();
  const geminiKey = (localStorage.getItem("user_gemini_key") || "").trim();
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
    feedback.textContent = "Guardando y verificando credenciales con Groq y Gemini...";
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
    feedback.textContent = "Llaves locales eliminadas de este navegador.";
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
    feedback.textContent = "Conectando con las llaves predeterminadas del servidor (.env)...";
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
    if (btnEl) { WhisperIcons.set(btnEl, "eye-off"); btnEl.setAttribute("aria-label", "Ocultar clave"); btnEl.title = "Ocultar clave"; btnEl.setAttribute("aria-pressed", "true"); }
  } else {
    input.type = "password";
    if (btnEl) { WhisperIcons.set(btnEl, "eye"); btnEl.setAttribute("aria-label", "Mostrar clave"); btnEl.title = "Mostrar clave"; btnEl.setAttribute("aria-pressed", "false"); }
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
      groqIndicator.textContent = "No configurada localmente";
      groqIndicator.className = "text-[11px] text-slate-500 font-mono";
    }
  }
  if (geminiIndicator) {
    if (gemini) {
      geminiIndicator.textContent = "Guardada en este navegador";
      geminiIndicator.className = "text-[11px] text-emerald-400 font-mono";
    } else {
      geminiIndicator.textContent = "No configurada localmente";
      geminiIndicator.className = "text-[11px] text-slate-500 font-mono";
    }
  }
}

function checkAuthErrorAndRedirect(status, data) {
  if (status === 401 || (data && (data.error === "API_KEYS_REQUIRED" || data.status === 401))) {
    const msg = (data && data.message) || (data && data.detail && data.detail.message) || (typeof data.detail === "string" ? data.detail : "Por favor ingresa tus API keys de Groq y Gemini en la sección de Ajustes para continuar.");
    if (typeof showAlert === "function") {
      showAlert(`${msg}`);
    } else {
      alert(`${msg}`);
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
  if (apiVerificationPending || apiVerificationError) { banner.classList.add("hidden"); return; }
  const currentEngine = (document.getElementById("transcriptionEngine")?.value || localStorage.getItem("whisper_engine") || "groq");
  const isLocalEngine = (currentEngine === "local");
  const hasLocalGroq = Boolean((localStorage.getItem("user_groq_key") || "").trim());
  const hasLocalGemini = Boolean((localStorage.getItem("user_gemini_key") || "").trim());
  const hasAnyEffectiveGroq = hasLocalGroq || Boolean(serverHasGroq);
  const hasAnyEffectiveGemini = hasLocalGemini || Boolean(serverHasGemini);

  const isSatisfied = isLocalEngine ? hasLocalGemini : (hasLocalGroq && hasLocalGemini);
  const hasMinimum = isLocalEngine ? hasAnyEffectiveGemini : (hasAnyEffectiveGroq && hasAnyEffectiveGemini);

  if (isSatisfied) {
    banner.classList.add("hidden");
  } else if (!hasMinimum) {
    banner.classList.remove("hidden");
    const badge = document.getElementById("apiOnboardingBadge");
    if (badge) {
      badge.textContent = isLocalEngine ? "Falta Gemini" : "Paso requerido";
      badge.className = "px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-rose-500/20 text-rose-200 border border-rose-500/30";
    }
  } else {
    // Server has fallback keys, but this computer has no personal keys stored yet
    banner.classList.remove("hidden");
    const badge = document.getElementById("apiOnboardingBadge");
    if (badge) {
      badge.textContent = "Recomendado en esta PC";
      badge.className = "px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-amber-500/20 text-amber-200 border border-amber-500/30";
    }
  }
}

function updateSystemStatusIndicator() {
  const currentEngine = (document.getElementById("transcriptionEngine")?.value || localStorage.getItem("whisper_engine") || "groq");
  const isLocalEngine = (currentEngine === "local");
  const hasGroq = Boolean((localStorage.getItem('user_groq_key') || '').trim() || serverHasGroq);
  const hasGemini = Boolean((localStorage.getItem('user_gemini_key') || '').trim() || serverHasGemini);
  const issueFor = (key, label, configured) => {
    if (apiVerificationPending) return null;
    if (apiVerificationError) return apiVerificationFailureMessage;
    if (apiVerification && !apiVerification[key]) {
      const raw = String(apiVerification[key + '_message'] || '').trim();
      const detail = raw && !/:$/.test(raw) ? raw : 'No se pudo completar la comprobación de acceso.';
      return `${label}: ${detail} Comprueba tu conexión y la clave configurada; después pulsa «Probar Conexión».`;
    }
    return configured ? null : `${label}: falta configurar una clave en Credenciales de API.`;
  };
  const missing = apiVerificationError ? [apiVerificationFailureMessage] : [!isLocalEngine && issueFor('groq', 'Groq', hasGroq), issueFor('gemini', 'Gemini', hasGemini)].filter(Boolean);
  const needsSetup = missing.length > 0;
  const label = needsSetup ? 'Ajustes y APIs: ' + missing.join(' ') : 'Ajustes y APIs';
  const summary = document.getElementById('settingsApiIssueSummary');
  if (summary) { summary.hidden = !needsSetup; summary.textContent = missing.join(' '); }
  for (const [key, id] of [['groq', 'settingsGroqStatus'], ['gemini', 'settingsGeminiStatus']]) {
    const row = document.getElementById(id), status = document.getElementById(id + 'Text');
    let state = apiVerificationPending ? 'pending' : apiVerificationError ? 'unverified' : apiVerification ? (apiVerification[key] ? 'ready' : 'error') : 'unverified';
    let message = apiVerificationError && !apiVerificationPending ? 'Acceso sin comprobar' : state === 'pending' ? apiVerificationPendingMessage : state === 'ready' ? 'Acceso a la API verificado' : state === 'error' ? (issueFor(key, key === 'groq' ? 'Groq' : 'Gemini', false)) : 'Conexión sin comprobar';
    if (key === 'groq' && isLocalEngine) { state = 'unverified'; message = 'Modelo local seleccionado; disponibilidad sin comprobar'; }
    if (row) { row.dataset.state = state; row.title = message; }
    if (status) status.textContent = message;
  }
  updateOnboardingBannerState();
  const container = document.getElementById('systemStatusContainer');
  if (container) { container.innerHTML = ''; container.hidden = true; }
  for (const id of ['settingsApiWarning', 'mobileSettingsApiWarning']) {
    const badge = document.getElementById(id);
    if (badge) badge.hidden = !needsSetup;
  }
  for (const id of ['btnSettingsSidebar', 'btnMobileSettings']) {
    const button = document.getElementById(id);
    if (button) { button.title = label; button.setAttribute('aria-label', label); button.dataset.needsSetup = String(needsSetup); }
  }
}

function updateKeyBadge(elementId, isReady, label, message) {
  const badge = document.getElementById(elementId);
  if (!badge) return;
  if (isReady === "unverified") {
    badge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30";
    badge.textContent = "Sin comprobar";
    badge.title = message || "Todavía no se ha podido comprobar el acceso.";
    return;
  }
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

function apiVerificationFailure(kind, status = null) {
  const messages = {
    network: 'No se pudo contactar con el servidor de WhisperDnD. Abre la app con su acceso directo y pulsa «Probar Conexión» para reintentar.',
    timeout: 'El servidor de WhisperDnD no respondió a tiempo. Espera unos instantes y pulsa «Probar Conexión».',
    invalid_response: 'El servidor respondió con un diagnóstico inválido. Recarga la app y vuelve a probar.',
    http: 'El servidor de WhisperDnD respondió HTTP ' + status + '. Pulsa «Probar Conexión» para reintentar.',
  };
  const error = new Error(messages[kind]);
  error.verificationKind = kind;
  error.retryable = kind === 'network' || kind === 'timeout' || (kind === 'http' && [502,503,504].includes(status));
  return error;
}

async function requestApiVerification(headers, sequence, force = false) {
  for (let attempt = 0; attempt < 3; attempt++) {
    if (sequence !== apiVerificationSequence) return null;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    let failure;
    try {
      let response;
      try {
        response = await fetch('/api/status/keys?include_drive=false' + (force ? '&force=true' : ''), {headers, signal: controller.signal});
      } catch {
        throw apiVerificationFailure(controller.signal.aborted ? 'timeout' : 'network');
      }
      if (!response.ok) throw apiVerificationFailure('http', response.status);
      let data;
      try { data = await response.json(); }
      catch { throw apiVerificationFailure(controller.signal.aborted ? 'timeout' : 'invalid_response'); }
      if (!data || typeof data.groq !== 'boolean' || typeof data.gemini !== 'boolean') throw apiVerificationFailure('invalid_response');
      return data;
    } catch (error) {
      failure = error;
    } finally {
      clearTimeout(timer);
    }
    if (sequence !== apiVerificationSequence) return null;
    if (!failure.retryable || attempt === 2) throw failure;
    apiVerificationPendingMessage = 'Esperando al servidor de WhisperDnD. Reintentando (' + (attempt + 2) + '/3)…';
    updateSystemStatusIndicator();
    await new Promise(resolve => setTimeout(resolve, (attempt + 1) * 1000));
  }
}

async function checkApiKeysStatus(showToast = false) {
  const checkSequence = ++apiVerificationSequence;
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
  apiVerificationPending = true;
  apiVerificationPendingMessage = "Verificando conexión…";
  const checkButton = document.getElementById('btnCheckApiConnection');
  if (checkButton) checkButton.disabled = true;
  updateSystemStatusIndicator();

  try {
    const data = await requestApiVerification(getUserApiHeaders(), checkSequence, showToast);
    if (checkSequence !== apiVerificationSequence || !data) return;
    {
      apiVerification = data;
      apiVerificationError = false;
      apiVerificationFailureMessage = "";
      const modelLabel = document.getElementById('settingsGeminiModelText');
      if (modelLabel) modelLabel.textContent = data.gemini_model || 'Gemini (modelo sin consultar)';
      serverHasGroq = Boolean(data.groq);
      serverHasGemini = Boolean(data.gemini);
      if (typeof data.drive === "boolean" && typeof window.isGoogleDriveConnected !== "undefined") {
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
        geminiMsgEl.textContent = data.gemini_message || (data.gemini ? "Acceso a Gemini verificado." : "Sin configurar.");
        geminiMsgEl.className = data.gemini ? "text-[10px] text-emerald-400/90 font-mono truncate" : "text-[10px] text-slate-500 font-mono truncate";
      }

      // Update input-level labels: ONLY show green on the input card if the user actually has a personal key saved locally!
      const hasGroqLocal = Boolean((localStorage.getItem("user_groq_key") || "").trim());
      const hasGeminiLocal = Boolean((localStorage.getItem("user_gemini_key") || "").trim());
      const groqIndicator = document.getElementById("groqKeySavedIndicator");
      const geminiIndicator = document.getElementById("geminiKeySavedIndicator");

      if (groqIndicator) {
        if (hasGroqLocal && data.groq) {
          groqIndicator.textContent = "Llave personal verificada";
          groqIndicator.className = "text-[11px] text-emerald-400 font-mono font-semibold";
        } else if (hasGroqLocal && !data.groq) {
          groqIndicator.textContent = "Llave inválida o error";
          groqIndicator.className = "text-[11px] text-rose-400 font-mono font-semibold";
        } else if (!hasGroqLocal && data.groq) {
          groqIndicator.textContent = "Sin llave local (Servidor activo)";
          groqIndicator.className = "text-[11px] text-amber-300/90 font-mono";
        } else {
          groqIndicator.textContent = "No configurada";
          groqIndicator.className = "text-[11px] text-slate-500 font-mono";
        }
      }

      if (geminiIndicator) {
        if (hasGeminiLocal && data.gemini) {
          geminiIndicator.textContent = "Llave personal verificada";
          geminiIndicator.className = "text-[11px] text-emerald-400 font-mono font-semibold";
        } else if (hasGeminiLocal && !data.gemini) {
          geminiIndicator.textContent = "Llave inválida o error";
          geminiIndicator.className = "text-[11px] text-rose-400 font-mono font-semibold";
        } else if (!hasGeminiLocal && data.gemini) {
          geminiIndicator.textContent = "Sin llave local (Servidor activo)";
          geminiIndicator.className = "text-[11px] text-amber-300/90 font-mono";
        } else {
          geminiIndicator.textContent = "No configurada";
          geminiIndicator.className = "text-[11px] text-slate-500 font-mono";
        }
      }

      if (typeof data.drive === "boolean" && typeof updateDriveUIState === "function") {
        updateDriveUIState(Boolean(data.drive), data.drive_email || null);
      }

      const feedback = document.getElementById("apiKeySaveFeedback");
      if (feedback && showToast) {
        feedback.classList.remove("hidden");
        if (data.groq && data.gemini) {
          const msg = (hasGroqLocal && hasGeminiLocal)
            ? "¡Tus llaves personales de Groq y Gemini fueron guardadas y verificadas con éxito!"
            : "Conexión operativa con Groq y Gemini verificada.";
          feedback.textContent = msg;
          feedback.className = "text-xs text-emerald-400 font-semibold";
          if (typeof showSuccessAlert === "function") showSuccessAlert(msg);
        } else if (!data.groq && !data.gemini) {
          const msg = "No se pudo verificar el acceso. Groq: " + (data.groq_message || "sin acceso confirmado") + ". Gemini: " + (data.gemini_message || "sin acceso confirmado") + ".";
          feedback.textContent = msg;
          feedback.className = "text-xs text-rose-400 font-semibold";
          if (typeof showAlert === "function") showAlert(msg);
        } else {
          const msg = `Estado parcial — Groq: ${data.groq ? 'OK' : 'Falla (' + (data.groq_message || 'revisar') + ')'} | Gemini: ${data.gemini ? 'OK' : 'Falla (' + (data.gemini_message || 'revisar') + ')'}`;
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
    if (checkSequence !== apiVerificationSequence) return;
    apiVerification = null;
    apiVerificationError = true;
    serverHasGroq = false;
    serverHasGemini = false;
    apiVerificationFailureMessage = err.verificationKind ? err.message : 'No se pudo actualizar el diagnóstico en la app. Recarga la pantalla y vuelve a probar.';
    console.warn("No se pudo completar el diagnóstico de APIs:", err.verificationKind || 'display');
    updateKeyBadge("badgeGroqStatus", "unverified", "Groq", apiVerificationFailureMessage);
    updateKeyBadge("badgeGeminiStatus", "unverified", "Gemini", apiVerificationFailureMessage);
    const feedback = document.getElementById("apiKeySaveFeedback");
    if (feedback && showToast) {
      feedback.classList.remove("hidden");
      feedback.textContent = apiVerificationFailureMessage;
      feedback.className = "text-xs text-rose-400 font-semibold";
      if (typeof showAlert === "function") {
        showAlert(apiVerificationFailureMessage);
      }
    }
  } finally {
    if (checkSequence === apiVerificationSequence) {
      apiVerificationPending = false;
      if (checkButton) checkButton.disabled = false;
      updateSystemStatusIndicator();
    }
  }
}

// =========================================================================
// API TOKEN & QUOTA MONITORING
// =========================================================================
var currentApiQuotaData = null;

var quotaRequestSerial = 0;

function currentQuotaProfileQuery() {
  const workspace = window.currentWorkspace === "work_and_study" ? "work_and_study" : "dnd";
  const source = window.currentActiveMainTab === "youtube" ? "youtube" : window.currentActiveMainTab === "file" ? "file" : "recording";
  let query = "source=" + source + "&workspace=" + workspace;
  if (workspace === "work_and_study") {
    const format = document.getElementById("workStudyDocumentFormat")?.value === "executive" ? "executive" : "academic";
    query += "&document_format=" + format;
  }
  return query;
}

async function fetchApiQuota() {
  const serial = ++quotaRequestSerial;
  try {
    const res = await fetch("/api/system/quota?" + currentQuotaProfileQuery(), {headers: getUserApiHeaders()});
    if (serial !== quotaRequestSerial) return null;
    if (!res.ok) { currentApiQuotaData = null; renderApiQuota(null); return null; }
    const data = await res.json();
    if (serial !== quotaRequestSerial) return null;
    currentApiQuotaData = data;
    renderApiQuota(data);
    return data;
  } catch (err) {
    if (serial !== quotaRequestSerial) return null;
    console.warn("Could not fetch API quota:", err);
    currentApiQuotaData = null;
    renderApiQuota(null);
    return null;
  }
}

// Selection changes keep the capacity estimate attached to the profile being prepared.
document.addEventListener?.("click", event => {
  if (event.target?.closest?.("#switchWorkspaceDnd,#switchWorkspaceWork,#mobileSwitchDnd,#mobileSwitchWork,#tabLiveBtn,#tabYoutubeBtn,#tabFileBtn")) fetchApiQuota();
});
document.addEventListener?.("change", event => {
  if (event.target?.id === "workStudyDocumentFormat") fetchApiQuota();
});

function renderApiQuota(data) {
  const percentDisplay = document.getElementById("quotaPercentDisplay");
  const progressBar = document.getElementById("quotaProgressBar");
  const statusDot = document.getElementById("quotaStatusDot");
  const statusSummary = document.getElementById("quotaStatusSummary");
  const audioEstimate = document.getElementById("quotaAudioEstimate");
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
    Number.isFinite(tokensLimit) && tokensLimit > 0 &&
    Number.isFinite(tokensRem) && tokensRem >= 0
  );

  // Unknown capacity is not a full quota. Clear old readings on refresh failure.
  if (!hasValidData) {
    if (percentDisplay) {
      percentDisplay.textContent = "Sin datos";
      percentDisplay.className = "font-mono font-bold tabular-nums text-xs text-slate-400";
    }
    if (progressBar) {
      progressBar.style.width = "0%";
      progressBar.className = "h-full rounded-full transition-all duration-300 bg-slate-700";
    }
    if (statusDot) {
      statusDot.className = "w-2 h-2 rounded-full bg-slate-500";
    }
    if (statusSummary) {
      statusSummary.hidden = true;
      statusSummary.textContent = "";
      statusSummary.className = "font-semibold text-slate-400";
    }
    if (tokensSummary) {
      tokensSummary.textContent = "Tokens no disponibles";
    }
    if (mobilePercent) {
      mobilePercent.textContent = "Sin datos";
      mobilePercent.className = "tabular-nums text-slate-400";
    }
    if (mobileDot) {
      mobileDot.className = "w-1.5 h-1.5 rounded-full bg-slate-500";
    }
    if (quotaContainer) {
      quotaContainer.dataset.state = "unknown";
      quotaContainer.title = "No hay datos de cuota disponibles";
    }
    if (audioEstimate) { audioEstimate.hidden = true; audioEstimate.textContent = ""; }
    return;
  }

  // Porcentaje DISPONIBLE real (tokens disponibles / límite total)
  const pctRemaining = Math.max(0.0, Math.min(100.0, (tokensRem / tokensLimit) * 100.0));
  const pctStr = `${Number(pctRemaining.toFixed(1))}%`;

  // Only low capacity needs a label; normal capacity stays visually quiet.
  const isCritical = pctRemaining < 5;
  const isLow = pctRemaining <= 20;
  const colorClass = isCritical ? "rose" : isLow ? "amber" : "emerald";
  const statusText = isCritical ? "Cuota muy baja" : "Cuota baja";

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
    statusSummary.hidden = !isLow;
    statusSummary.textContent = isLow ? statusText : "";
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
    quotaContainer.dataset.state = isCritical ? "critical" : isLow ? "low" : "normal";
    const resetInfo = data.resets_in ? ` (se recarga en ~${data.resets_in} a las 00:00 UTC)` : ' (se recarga a las 00:00 UTC diariamente)';
    quotaContainer.title = `Cuota estimada disponible: ${pctStr} (~${Math.round(tokensRem / 1000)}k tokens restantes)${resetInfo}`;
  }
  if (audioEstimate) {
    audioEstimate.hidden = !isLow;
    audioEstimate.textContent = "";
    if (isLow) {
      const seconds = pctRemaining === 0 ? 0 : data.audio_capacity?.seconds;
      if (!Number.isFinite(seconds) || seconds < 0) {
        audioEstimate.textContent = "Cuota baja. Falta historial para estimar el tiempo de audio.";
      } else if (seconds === 0) {
        audioEstimate.textContent = "No hay capacidad disponible para procesar audio.";
      } else if (seconds < 60) {
        audioEstimate.textContent = "La capacidad estimada es menor a 1 min de audio. Margen del 5 % incluido.";
      } else {
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const duration = hours ? hours + " h" + (minutes % 60 ? " " + minutes % 60 + " min" : "") : minutes + " min";
        audioEstimate.textContent = "Puedes procesar aproximadamente " + duration + " de audio. Margen del 5 % incluido.";
      }
    }
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
        `ADVERTENCIA DE CUOTA DE API CRÍTICA (${remainingPct}% disponible)\n\n` +
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
