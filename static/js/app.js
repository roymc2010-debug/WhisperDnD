// =========================================================================
// WhisperDnD - app.js
// Coordinador Principal de la Aplicación, Espacios de Trabajo y Ciclo de Vida
// =========================================================================

// Variables de Estado Globales (Uso de var para compatibilidad global entre scripts)
var currentActiveView = 'ingest'; // 'ingest', 'wiki', 'character', 'roster', 'history', 'settings'
var currentWorkspace = localStorage.getItem("whisper_workspace") || "dnd"; // 'dnd' or 'work_and_study'
var currentActiveMainTab = 'live'; // 'live', 'youtube', 'file', 'wiki'
var currentLiveMode = 'roleplay'; // 'roleplay' or 'class'
var currentResult = null;
var currentCampaignState = null;
var currentAcademicTasks = [];
var currentActiveResultTab = 'chronicle';
var currentTargetLanguage = 'es'; // 'es' or 'en'
var knownCampaigns = {};
var deferredInstallPrompt = null;
var _isPageNavigatingOrReloading = false;

function navigateToDownload(url) {
  _isPageNavigatingOrReloading = true;
  setTimeout(() => { _isPageNavigatingOrReloading = false; }, 5000);
  window.location.href = url;
}
window.navigateToDownload = navigateToDownload;

function getLocalFormattedDateTime(d = new Date()) {
  const dateObj = (d instanceof Date) ? d : new Date(d);
  if (isNaN(dateObj.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  const day = pad(dateObj.getDate());
  const month = pad(dateObj.getMonth() + 1);
  const year = dateObj.getFullYear();
  const hours = pad(dateObj.getHours());
  const minutes = pad(dateObj.getMinutes());
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}
window.getLocalFormattedDateTime = getLocalFormattedDateTime;

var youtubeAbortController = null;
var isYoutubeTranscribing = false;
var selectedLocalRecordingFilename = null;

// =========================================================================
// VIEW CONTROLLER & NAVIGATION (Dual Workspace + Decoupled Views)
// =========================================================================
function setActiveView(viewId) {
  if (viewId === "roster") viewId = "ingest";
  currentActiveView = viewId;
  const views = {
    ingest: document.getElementById("viewIngest"),
    wiki: document.getElementById("viewWiki"),
    character: document.getElementById("viewCharacter"),
    roster: document.getElementById("viewRoster"),
    history: document.getElementById("viewHistory"),
    settings: document.getElementById("viewSettings"),
    audio: document.getElementById("viewAudio"),
    process: document.getElementById("viewProcess"),
    chronicle: document.getElementById("viewChronicle"),
    appearance: document.getElementById("viewAppearance"),
  };

  Object.entries(views).forEach(([id, el]) => {
    if (!el) return;
    if (id === viewId) {
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  });

  // Desktop sidebar navigation button styles
  const navBtns = {
    ingest: document.getElementById("navBtnIngest"),
    wiki: document.getElementById("navBtnWiki"),
    character: document.getElementById("navBtnCharacter"),
    roster: document.getElementById("navBtnRoster"),
    history: document.getElementById("navBtnHistory"),
    settings: document.getElementById("navBtnSettings"),
  };

  const isDnd = (currentWorkspace !== "work_and_study");
  const activeColor = isDnd ? "amber" : "sky";
  const activeClasses = `w-full min-h-[44px] px-3 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-3 transition-all duration-150 cursor-pointer active:scale-[0.98] bg-${activeColor}-500/15 text-${activeColor}-300 border border-${activeColor}-500/30 shadow-sm`;
  const inactiveClasses = "w-full min-h-[44px] px-3 py-2.5 rounded-xl text-xs font-medium flex items-center gap-3 transition-all duration-150 cursor-pointer active:scale-[0.98] text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent";

  Object.entries(navBtns).forEach(([id, btn]) => {
    if (!btn) return;
    btn.className = (id === viewId) ? activeClasses : inactiveClasses;
  });

  // Mobile bottom navigation button styles
  const mobileNavBtns = {
    ingest: document.getElementById("mobileNavBtnIngest"),
    wiki: document.getElementById("mobileNavBtnWiki"),
    character: document.getElementById("mobileNavBtnCharacter"),
    roster: document.getElementById("mobileNavBtnRoster"),
    history: document.getElementById("mobileNavBtnHistory"),
    settings: document.getElementById("mobileNavBtnSettings"),
  };

  const mobileActiveText = isDnd ? "text-amber-300 font-semibold" : "text-sky-300 font-semibold";
  const mobileInactiveText = "text-slate-400 font-medium";

  Object.entries(mobileNavBtns).forEach(([id, btn]) => {
    if (!btn) return;
    const isAct = (id === viewId);
    btn.className = `flex-1 min-h-[48px] py-1 flex flex-col items-center justify-center gap-1 text-[11px] active:scale-95 transition cursor-pointer ${isAct ? mobileActiveText : mobileInactiveText}`;
  });

  // Strict visibility enforcement: DnD shows wiki + character; Work shows history
  if (isDnd) {
    if (navBtns.wiki) navBtns.wiki.classList.remove("hidden");
    if (navBtns.character) navBtns.character.classList.remove("hidden");
    if (navBtns.history) navBtns.history.classList.add("hidden");
    if (mobileNavBtns.wiki) mobileNavBtns.wiki.classList.remove("hidden");
    if (mobileNavBtns.character) mobileNavBtns.character.classList.remove("hidden");
    if (mobileNavBtns.history) mobileNavBtns.history.classList.add("hidden");
  } else {
    if (navBtns.wiki) navBtns.wiki.classList.add("hidden");
    if (navBtns.character) navBtns.character.classList.add("hidden");
    if (navBtns.history) navBtns.history.classList.remove("hidden");
    if (mobileNavBtns.wiki) mobileNavBtns.wiki.classList.add("hidden");
    if (mobileNavBtns.character) mobileNavBtns.character.classList.add("hidden");
    if (mobileNavBtns.history) mobileNavBtns.history.classList.remove("hidden");
  }
  if (navBtns.roster) navBtns.roster.classList.add("hidden");
  if (navBtns.settings) navBtns.settings.classList.add("hidden");
  if (mobileNavBtns.roster) mobileNavBtns.roster.classList.add("hidden");
  if (mobileNavBtns.settings) mobileNavBtns.settings.classList.add("hidden");

  // View-specific initialization triggers
  if (viewId === 'wiki') {
    if (typeof refreshWikiView === "function") {
      refreshWikiView();
    } else if (typeof refreshWikiCampaigns === "function") {
      refreshWikiCampaigns();
    }
  } else if (viewId === 'character') {
    if (typeof loadCharacterView === "function") {
      loadCharacterView();
    }
  } else if (viewId === 'roster') {
    const sel = document.getElementById("campaignNameInput") || document.getElementById("campaignSelect");
    const badge = document.getElementById("rosterViewCampaignBadge");
    if (badge) {
      badge.textContent = (sel && sel.value && sel.value.trim()) ? sel.value.trim() : "Sin Campaña";
    }
    if (typeof renderRosterTable === "function") {
      renderRosterTable();
    }
  } else if (viewId === 'history') {
    if (typeof loadAcademicNotesHistory === "function") {
      loadAcademicNotesHistory();
    }
  } else if (viewId === 'settings') {
    if (typeof loadUserApiKeys === "function") {
      loadUserApiKeys();
    }
    if (typeof refreshAudioDevices === "function") {
      refreshAudioDevices();
    }
  }

  if (typeof syncDesktopNavigation === "function") syncDesktopNavigation();
  if (viewId === "audio" && typeof refreshAudioDevices === "function") refreshAudioDevices();
  const mainEl = document.querySelector("main");
  if (mainEl) mainEl.scrollTop = 0;
}

function switchView(viewId) {
  setActiveView(viewId);
}

function isMobileUser() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
    (window.innerWidth <= 768 && ('ontouchstart' in window || navigator.maxTouchPoints > 0));
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function isPrivateCampaign(name) {
  const clean = (name || "").trim().toLowerCase();
  return clean === "campaña principal" || clean === "campana principal";
}

function getCampaignRosterKey(name) {
  const clean = (name || "").trim();
  return clean ? "roster_" + clean.toLowerCase() : "";
}

function getSelectedCampaignName() {
  const el = document.getElementById("campaignNameInput");
  return el && el.value ? el.value.trim() : "";
}

// =========================================================================
// ENGINE & LANGUAGE SELECTORS
// =========================================================================
function initEngineSelector() {
  setEngine("groq");
}

function setEngine(engine) {
  const engineInput = document.getElementById("transcriptionEngine");
  if (engineInput) engineInput.value = "groq";
  localStorage.setItem("whisper_engine", "groq");
}

function initLanguageSelector() {
  const savedLang = localStorage.getItem("whisper_target_lang") || "es";
  setTargetLanguage(savedLang);
}

function setTargetLanguage(lang) {
  setLanguage(lang);
}

function setLanguage(lang) {
  const isEs = (lang !== "en");
  currentTargetLanguage = isEs ? "es" : "en";
  const langInput = document.getElementById("targetLanguage");
  if (langInput) langInput.value = currentTargetLanguage;

  const esBtn = document.getElementById("langEsBtn");
  const enBtn = document.getElementById("langEnBtn");
  if (isEs) {
    if (esBtn) {
      esBtn.className = "px-2.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1 bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm";
    }
    if (enBtn) {
      enBtn.className = "px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 text-slate-400 hover:text-slate-200 border border-transparent";
    }
  } else {
    if (enBtn) {
      enBtn.className = "px-2.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1 bg-slate-800 text-slate-200 border border-white/10 shadow-sm";
    }
    if (esBtn) {
      esBtn.className = "px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 text-slate-400 hover:text-slate-200 border border-transparent";
    }
  }
  localStorage.setItem("whisper_target_lang", currentTargetLanguage);
}

function toggleSessionOverride() {
  const check = document.getElementById("overrideSessionNumberCheck");
  const input = document.getElementById("sessionNumberInput");
  const lockBadge = document.getElementById("sessionLockBadge");
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) {
    if (check) check.checked = false;
    if (input) {
      input.disabled = true;
      input.value = "";
      input.placeholder = "-";
    }
    if (lockBadge) lockBadge.classList.add("hidden");
    return;
  }
  if (check && check.checked) {
    input.disabled = false;
    input.removeAttribute("readonly");
    input.className = "w-16 bg-slate-950 border border-amber-500 rounded-xl px-2.5 py-1.5 text-xs text-amber-300 text-center font-bold focus:ring-2 focus:ring-amber-500 outline-none";
    if (lockBadge) lockBadge.classList.add("hidden");
  } else {
    input.setAttribute("readonly", "readonly");
    input.className = "w-16 bg-slate-900 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-400 text-center font-bold cursor-not-allowed outline-none select-none";
    if (lockBadge && currentActiveMainTab === "live") lockBadge.classList.remove("hidden");
    loadCurrentCampaign();
  }
}

function updateSessionLockForTab(tab) {
  currentActiveMainTab = tab || "live";
  const sessionInput = document.getElementById("sessionNumberInput");
  const lockBadge = document.getElementById("sessionLockBadge");
  const overrideCheck = document.getElementById("overrideSessionNumberCheck");
  if (!sessionInput) return;

  if (tab === "live") {
    const isOverridden = overrideCheck ? overrideCheck.checked : false;
    sessionInput.disabled = !isOverridden;
    if (lockBadge) {
      if (!isOverridden && (document.getElementById("campaignNameInput")?.value || "").trim()) {
        lockBadge.classList.remove("hidden");
      } else {
        lockBadge.classList.add("hidden");
      }
    }
  } else {
    sessionInput.disabled = false;
    if (lockBadge) lockBadge.classList.add("hidden");
  }
}

// =========================================================================
// WORKSPACE SWITCHER
// =========================================================================
function setWorkspace(workspace) {
  currentWorkspace = workspace || "dnd";
  localStorage.setItem("whisper_workspace", currentWorkspace);

  const isDnd = (currentWorkspace === "dnd");
  const body = document.body;
  const btnDnd = document.getElementById("switchWorkspaceDnd");
  const btnWork = document.getElementById("switchWorkspaceWork");
  const mobileSwitchDnd = document.getElementById("mobileSwitchDnd");
  const mobileSwitchWork = document.getElementById("mobileSwitchWork");

  const navBtnIngestText = document.getElementById("navBtnIngestText");
  const navBtnWikiText = document.getElementById("navBtnWikiText");
  const navBtnHistoryText = document.getElementById("navBtnHistoryText");
  const mobileNavBtnIngestText = document.getElementById("mobileNavBtnIngestText");
  const mobileNavBtnWikiText = document.getElementById("mobileNavBtnWikiText");
  const mobileNavBtnHistoryText = document.getElementById("mobileNavBtnHistoryText");

  const dndContainer = document.getElementById("dndWorkspaceContainer");
  const workContainer = document.getElementById("workStudyWorkspaceContainer");
  const brandIcon = document.getElementById("brandIcon");
  const brandTitle = document.getElementById("brandTitle");
  const brandSubtitle = document.getElementById("brandSubtitle");
  const mobileBrandTitle = document.getElementById("mobileBrandTitle");

  const tabLiveBtnText = document.getElementById("tabLiveBtnText");
  const tabYoutubeBtnText = document.getElementById("tabYoutubeBtnText");
  const tabFileBtnText = document.getElementById("tabFileBtnText");

  if (isDnd) {
    body.classList.remove("theme-work-study");
    body.classList.add("theme-dnd");

    if (btnDnd) {
      btnDnd.className = "flex-1 min-h-[44px] px-2 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 flex items-center justify-center gap-2 bg-amber-500/15 text-amber-300 border border-amber-500/30 cursor-pointer active:scale-[0.98]";
    }
    if (btnWork) {
      btnWork.className = "flex-1 min-h-[44px] px-2 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 flex items-center justify-center gap-2 text-slate-400 hover:text-slate-200 border border-transparent cursor-pointer active:scale-[0.98]";
    }
    if (mobileSwitchDnd) {
      mobileSwitchDnd.className = "min-h-[36px] px-2.5 py-1 rounded text-xs font-semibold bg-amber-500/20 text-amber-300";
    }
    if (mobileSwitchWork) {
      mobileSwitchWork.className = "min-h-[36px] px-2.5 py-1 rounded text-xs font-medium text-slate-400";
    }

    if (navBtnIngestText) navBtnIngestText.textContent = "Sesión & Grabación";
    if (navBtnWikiText) navBtnWikiText.textContent = "Wiki & Crónicas";
    if (mobileNavBtnIngestText) mobileNavBtnIngestText.textContent = "Sesión";
    if (mobileNavBtnWikiText) mobileNavBtnWikiText.textContent = "Wiki";

    if (dndContainer) dndContainer.classList.remove("hidden");
    if (workContainer) workContainer.classList.add("hidden");

    if (brandIcon) {
      brandIcon.innerHTML = `<img src="/static/icon-192.png" alt="WhisperDnD" class="w-8 h-8 rounded-lg object-contain">`;
    }
    const mobileBrandIconDnd = document.getElementById("mobileBrandIcon");
    if (mobileBrandIconDnd) {
      mobileBrandIconDnd.innerHTML = `<img src="/static/icon-192.png" alt="WhisperDnD" class="w-6 h-6 rounded object-contain">`;
    }
    if (brandTitle) {
      brandTitle.textContent = "WhisperDnD";
      brandTitle.className = "text-base font-bold tracking-tight text-white font-fantasy transition-all duration-200 truncate";
    }
    if (brandSubtitle) brandSubtitle.textContent = "Diario Vivo de Campaña";
    if (mobileBrandTitle) mobileBrandTitle.textContent = "WhisperDnD";

    if (tabLiveBtnText) tabLiveBtnText.textContent = "Grabar en Vivo";
    if (tabYoutubeBtnText) tabYoutubeBtnText.textContent = "YouTube";
    if (tabFileBtnText) tabFileBtnText.textContent = "Archivo Local";

    setActiveView('ingest');
    setLiveMode("roleplay");
  } else {
    body.classList.remove("theme-dnd");
    body.classList.add("theme-work-study");

    if (btnDnd) {
      btnDnd.className = "flex-1 min-h-[44px] px-2 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 flex items-center justify-center gap-2 text-slate-400 hover:text-slate-200 border border-transparent cursor-pointer active:scale-[0.98]";
    }
    if (btnWork) {
      btnWork.className = "flex-1 min-h-[44px] px-2 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 flex items-center justify-center gap-2 bg-sky-500/15 text-sky-300 border border-sky-500/30 cursor-pointer active:scale-[0.98]";
    }
    if (mobileSwitchDnd) {
      mobileSwitchDnd.className = "min-h-[36px] px-2.5 py-1 rounded text-xs font-medium text-slate-400";
    }
    if (mobileSwitchWork) {
      mobileSwitchWork.className = "min-h-[36px] px-2.5 py-1 rounded text-xs font-semibold bg-sky-500/20 text-sky-300";
    }

    if (navBtnIngestText) navBtnIngestText.textContent = "Grabar / Ingesta";
    if (navBtnHistoryText) navBtnHistoryText.textContent = "Historial de Apuntes";
    if (mobileNavBtnIngestText) mobileNavBtnIngestText.textContent = "Grabar";
    if (mobileNavBtnHistoryText) mobileNavBtnHistoryText.textContent = "Historial";

    if (dndContainer) dndContainer.classList.add("hidden");
    if (workContainer) workContainer.classList.remove("hidden");

    if (brandIcon) {
      brandIcon.innerHTML = `<svg class="w-6 h-6 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`;
    }
    const mobileBrandIconWork = document.getElementById("mobileBrandIcon");
    if (mobileBrandIconWork) {
      mobileBrandIconWork.innerHTML = `<svg class="w-4 h-4 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`;
    }
    if (brandTitle) {
      brandTitle.textContent = "Work & Study";
      brandTitle.className = "text-base font-bold tracking-tight text-white font-sans transition-all duration-200 truncate";
    }
    if (brandSubtitle) brandSubtitle.textContent = "Apuntes & Sesiones Inteligentes";
    if (mobileBrandTitle) mobileBrandTitle.textContent = "Work & Study";

    if (tabLiveBtnText) tabLiveBtnText.textContent = "Grabar Reunión / Clase";
    if (tabYoutubeBtnText) tabYoutubeBtnText.textContent = "Video / YouTube";
    if (tabFileBtnText) tabFileBtnText.textContent = "Subir Audio";

    const dateInput = document.getElementById("workStudyDateInput");
    if (dateInput && (!dateInput.value || !dateInput.value.trim())) {
      dateInput.value = getLocalFormattedDateTime(new Date());
    }

    setActiveView('ingest');
    setLiveMode("class");
  }

  const btnDownloadDocxText = document.getElementById("btnDownloadDocxText");
  const btnDownloadMd = document.getElementById("btnDownloadMd");
  const btnSwitchLanguage = document.getElementById("btnSwitchLanguage");
  const btnReprocessCampaignText = document.getElementById("btnReprocessCampaignText");

  if (isDnd && !currentCampaignState && (document.getElementById("campaignNameInput")?.value || "").trim()) {
    loadCurrentCampaign();
  }
  syncResultTabsForWorkspace(isDnd ? "roleplay" : "class");

  if (isDnd) {
    if (btnDownloadDocxText) btnDownloadDocxText.textContent = "Grimorio .docx";
    if (btnDownloadMd) btnDownloadMd.classList.add("hidden");
    if (btnSwitchLanguage) btnSwitchLanguage.classList.remove("hidden");
    if (btnReprocessCampaignText) btnReprocessCampaignText.textContent = "Regenerar Crónica (Gemini)";
  } else {
    if (btnDownloadDocxText) btnDownloadDocxText.textContent = "Documento .docx";
    if (btnDownloadMd) btnDownloadMd.classList.remove("hidden");
    if (btnSwitchLanguage) btnSwitchLanguage.classList.add("hidden");
    if (btnReprocessCampaignText) btnReprocessCampaignText.textContent = "Regenerar Apuntes (Gemini)";
  }
}

function setLiveMode(mode) {
  currentLiveMode = mode;
  const btnRoleplay = document.getElementById("btnModeRoleplay");
  const btnClass = document.getElementById("btnModeClass");
  const dualBanner = document.getElementById("dualChannelBanner");
  const singleBanner = document.getElementById("singleMicBanner");
  const rosterSection = document.getElementById("rosterSection");
  const lectureSection = document.getElementById("lectureSection");
  const startBtnText = document.getElementById("btnStartRecordingText");
  const stopBtnText = document.getElementById("btnStopRecordingText");
  const statusText = document.getElementById("liveRecordingStatus");
  const campaignCard = document.getElementById("campaignHeaderCard");
  const deviceSpeakerContainer = document.getElementById("deviceSpeakerContainer");
  const meterSpeakerRow = document.getElementById("meterSpeakerRow");

  if (mode === "class") {
    if (btnClass) btnClass.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-gradient-to-r from-indigo-600/30 to-purple-600/30 text-indigo-300 border border-indigo-500/40 shadow-sm";
    if (btnRoleplay) btnRoleplay.className = "px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-2 text-slate-400 hover:text-slate-200 border border-transparent";
    if (dualBanner) dualBanner.classList.add("hidden");
    if (singleBanner) singleBanner.classList.remove("hidden");
    if (rosterSection) rosterSection.classList.add("hidden");
    if (lectureSection) lectureSection.classList.remove("hidden");
    if (campaignCard) campaignCard.classList.add("hidden");
    if (deviceSpeakerContainer) deviceSpeakerContainer.classList.add("hidden");
    if (meterSpeakerRow) meterSpeakerRow.classList.add("hidden");
    if (startBtnText) startBtnText.textContent = "Iniciar Grabación de Clase";
    if (stopBtnText) stopBtnText.textContent = "Detener y Generar Apuntes";
    if (statusText && !document.getElementById("btnStopRecording")?.disabled) {
      statusText.textContent = "Grabación de clase en curso (Micrófono Mono)";
    } else if (statusText) {
      statusText.textContent = "Listo para grabar la clase universitaria";
    }
  } else {
    if (btnRoleplay) btnRoleplay.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-gradient-to-r from-rose-600/20 to-indigo-600/20 text-rose-300 border border-rose-500/40 shadow-sm";
    if (btnClass) btnClass.className = "px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-2 text-slate-400 hover:text-slate-200 border border-transparent";
    if (dualBanner) dualBanner.classList.remove("hidden");
    if (singleBanner) singleBanner.classList.add("hidden");
    if (rosterSection) rosterSection.classList.remove("hidden");
    if (lectureSection) lectureSection.classList.add("hidden");
    if (campaignCard) campaignCard.classList.remove("hidden");
    if (deviceSpeakerContainer) deviceSpeakerContainer.classList.remove("hidden");
    if (meterSpeakerRow) meterSpeakerRow.classList.remove("hidden");
    if (startBtnText) startBtnText.textContent = "Iniciar Sesión de D&D";
    if (stopBtnText) stopBtnText.textContent = "Detener y Procesar al Grimorio";
    if (statusText && !document.getElementById("btnStopRecording")?.disabled) {
      statusText.textContent = "Grabación en curso (Canal Izq: Mic | Canal Der: Discord)";
    } else if (statusText) {
      const campVal = (document.getElementById("campaignNameInput")?.value || "").trim();
      statusText.textContent = campVal ? "Listo para iniciar la sesión de juego" : "Selecciona o crea una campaña arriba para poder grabar";
    }
  }
}

function switchMainTab(tab) {
  if (typeof updateStepperMode === "function") updateStepperMode(tab === "youtube");
  const tabs = ["live", "youtube", "file", "wiki"];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab${capitalize(t)}Btn`);
    const content = document.getElementById(`tab${capitalize(t)}Content`);
    if (!btn || !content) return;
    if (t === tab) {
      content.classList.remove("hidden");
      if (t === "live") {
        btn.className = "min-h-[44px] px-3.5 pb-2 text-xs sm:text-sm font-semibold border-b-2 border-rose-500 text-rose-400 transition-all duration-150 active:scale-[0.98] flex items-center gap-2 cursor-pointer";
      } else if (t === "wiki") {
        btn.className = "min-h-[44px] px-3.5 pb-2 text-xs sm:text-sm font-semibold border-b-2 border-amber-500 text-amber-400 transition-all duration-150 active:scale-[0.98] flex items-center gap-2 cursor-pointer";
      } else {
        btn.className = "min-h-[44px] px-3.5 pb-2 text-xs sm:text-sm font-semibold border-b-2 border-indigo-500 text-indigo-400 transition-all duration-150 active:scale-[0.98] flex items-center gap-2 cursor-pointer";
      }
    } else {
      content.classList.add("hidden");
      btn.className = "min-h-[44px] px-3.5 pb-2 text-xs sm:text-sm font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all duration-150 active:scale-[0.98] flex items-center gap-2 cursor-pointer";
    }
  });
  updateSessionLockForTab(tab);
  if (tab === "wiki" && typeof refreshWikiView === "function") {
    refreshWikiView();
  }
  if (tab === "file" && typeof loadLocalRecordingsList === "function") {
    loadLocalRecordingsList();
  }
  if (tab === "live") {
    if (typeof startLiveMeterPolling === "function") startLiveMeterPolling();
  } else {
    const isRecordingActive = !document.getElementById("btnStopRecording")?.disabled;
    if (!isRecordingActive && typeof stopLiveMeterPolling === "function") stopLiveMeterPolling();
  }
}

// =========================================================================
// CAMPAIGN LOADING & LIFECYCLE
// =========================================================================
async function loadCampaignList() {
  try {
    const res = await fetch("/api/campaigns");
    if (res.ok) {
      const campaigns = await res.json();
      knownCampaigns = {};
      const datalist = document.getElementById("campaignListOptions");
      if (datalist) datalist.innerHTML = "";
      campaigns.forEach(c => {
        const cName = c.name || c.campaign_name;
        if (cName) {
          knownCampaigns[cName.trim().toLowerCase()] = c;
          if (datalist) {
            const opt = document.createElement("option");
            opt.value = cName;
            datalist.appendChild(opt);
          }
        }
      });
      const campInput = document.getElementById("campaignNameInput");
      const savedActive = localStorage.getItem("last_active_campaign");
      if (campInput) {
        const currentVal = campInput.value.trim();
        if (currentVal && knownCampaigns[currentVal.toLowerCase()]) {
          loadCampaignRoster(currentVal);
        } else if (savedActive && knownCampaigns[savedActive.trim().toLowerCase()]) {
          campInput.value = savedActive;
          onCampaignChange();
        } else if (!currentVal && campaigns.length > 0) {
          const firstCamp = campaigns[0].name || campaigns[0].campaign_name;
          campInput.value = firstCamp;
          onCampaignChange();
        }
      }
      return campaigns;
    }
  } catch (err) {
    console.warn("Could not load campaigns list:", err);
  }
  return [];
}

async function toggleCampaignManagerModal(show) {
  const modal = document.getElementById("campaignManagerModal");
  const box = document.getElementById("campaignManagerModalBox");
  if (!modal) return;
  if (show) {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    modal.style.pointerEvents = "auto";
    if (box) box.style.pointerEvents = "auto";
    void modal.offsetWidth;
    modal.classList.remove("opacity-0", "pointer-events-none");
    modal.classList.add("opacity-100", "pointer-events-auto");
    if (box) {
      box.classList.remove("scale-95");
      box.classList.add("scale-100");
    }
    const listEl = document.getElementById("campaignManagerList");
    if (listEl) listEl.innerHTML = `<p class="text-slate-400 text-center py-6">Cargando campañas...</p>`;
    const campaigns = await loadCampaignList();
    renderCampaignManagerList(campaigns);
  } else {
    modal.style.pointerEvents = "none";
    modal.classList.remove("opacity-100", "pointer-events-auto");
    modal.classList.add("opacity-0", "pointer-events-none");
    if (box) {
      box.classList.remove("scale-100");
      box.classList.add("scale-95");
    }
    setTimeout(() => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }, 150);
  }
}

function renderCampaignManagerList(campaigns) {
  const listEl = document.getElementById("campaignManagerList");
  const countEl = document.getElementById("campaignManagerCount");
  if (!listEl) return;
  const list = campaigns || [];
  if (countEl) {
    countEl.textContent = `${list.length} ${list.length === 1 ? 'campaña guardada' : 'campañas guardadas'}`;
  }
  if (list.length === 0) {
    listEl.innerHTML = `
      <div class="text-center py-8 text-slate-400 space-y-2">
        <p class="text-2xl"><span data-ui-icon=folder aria-hidden=true></span></p>
        <p class="font-medium">No hay campañas guardadas todavía.</p>
        <p class="text-[11px] text-slate-500">Escribe un nombre en el campo de Campaña para comenzar una nueva aventura.</p>
      </div>
    `;
    return;
  }

  listEl.innerHTML = "";
  list.forEach(c => {
    const cName = c.name || c.campaign_name;
    const sessCount = c.sessions_count !== undefined ? c.sessions_count : (c.total_sessions || 0);
    const lastUpdated = c.last_updated ? c.last_updated.substring(0, 10) : "";
    const sessLabel = `${sessCount} ${sessCount === 1 ? 'sesión' : 'sesiones'}`;

    const row = document.createElement("div");
    row.className = "flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition gap-3";
    row.innerHTML = `
      <button type="button" onclick="selectCampaignFromManager('${escapeHtml(cName)}')" 
        class="flex items-center gap-2.5 text-left flex-1 hover:text-amber-300 transition group cursor-pointer">
        <span class="text-base group-hover:scale-110 transition shrink-0"><span data-ui-icon=file aria-hidden=true></span></span>
        <div class="truncate">
          <span class="font-semibold text-slate-200 group-hover:text-amber-300 text-xs block truncate">${escapeHtml(cName)}</span>
          ${lastUpdated ? `<span class="text-[10px] text-slate-500">Actualizada: ${escapeHtml(lastUpdated)}</span>` : ""}
        </div>
      </button>
      <div class="flex items-center gap-1.5 shrink-0">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/25 whitespace-nowrap">
          ${sessLabel}
        </span>
        <button type="button" onclick="exportCampaignByName('${escapeHtml(cName)}')" title="Exportar paquete ZIP de la campaña (${escapeHtml(cName)})"
          class="w-7 h-7 flex items-center justify-center rounded-lg bg-indigo-950/40 hover:bg-indigo-900/80 text-indigo-300 hover:text-white border border-indigo-800/40 transition cursor-pointer text-xs active:scale-95">
          <span data-ui-icon=upload aria-hidden=true></span>
        </button>
        <button type="button" onclick="confirmDeleteCampaign('${escapeHtml(cName)}')" title="Eliminar campaña y todo su historial"
          class="w-7 h-7 flex items-center justify-center rounded-lg bg-rose-950/40 hover:bg-rose-900/80 text-rose-300 hover:text-white border border-rose-800/40 transition cursor-pointer text-xs active:scale-95">
          <span data-ui-icon=trash aria-hidden=true></span>
        </button>
      </div>
    `;
    listEl.appendChild(row);
  });
}

function selectCampaignFromManager(cName) {
  const campInput = document.getElementById("campaignNameInput");
  if (campInput) {
    campInput.value = cName;
  }
  toggleCampaignManagerModal(false);
  onCampaignChange();
}

async function confirmDeleteCampaign(cName) {
  if (!confirm(`¿Eliminar la campaña '${cName}' y todo su historial?`)) {
    return;
  }
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(cName)}`, {
      method: "DELETE",
    });
    if (res.ok) {
      const activeCamp = (document.getElementById("campaignNameInput")?.value || "").trim().toLowerCase();
      if (activeCamp === cName.trim().toLowerCase()) {
        document.getElementById("campaignNameInput").value = "";
        onCampaignChange();
      }
      const updatedCampaigns = await loadCampaignList();
      renderCampaignManagerList(updatedCampaigns);
    } else {
      const err = await res.json().catch(() => ({}));
      showAlert("Error al eliminar la campaña: " + (err.detail || res.statusText));
    }
  } catch (err) {
    showAlert("Error al eliminar la campaña: " + err.message);
  }
}

async function loadCurrentCampaign() {
  if (currentWorkspace === "work_and_study") return;
  const rawCampName = (document.getElementById("campaignNameInput")?.value || "").trim();
  const sessionInput = document.getElementById("sessionNumberInput");
  const badge = document.getElementById("campaignLastSessionBadge");
  const overrideCheck = document.getElementById("overrideSessionNumberCheck");
  const isOverridden = overrideCheck?.checked;

  if (!rawCampName) {
    if (badge) {
      badge.className = "px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700";
      badge.textContent = "Sin Campaña Seleccionada";
    }
    if (sessionInput) {
      sessionInput.value = "";
      sessionInput.disabled = true;
      sessionInput.placeholder = "-";
    }
    if (overrideCheck) {
      overrideCheck.checked = false;
      overrideCheck.disabled = true;
    }
    if (typeof renderRosterTable === "function") renderRosterTable([]);
    currentCampaignState = null;
    const priorLoreInput = document.getElementById("priorLoreInput");
    const priorBadge = document.getElementById("priorLoreConfiguredBadge");
    if (priorLoreInput) priorLoreInput.value = "";
    if (priorBadge) priorBadge.classList.add("hidden");
    updateCampaignViewTabs({ quests: [], npcs: [], universal_pcs: [], sessions: [] });
    const statusText = document.getElementById("liveRecordingStatus");
    const stopBtn = document.getElementById("btnStopRecording");
    if (statusText && (!stopBtn || stopBtn.disabled) && currentLiveMode !== "class") {
      statusText.textContent = "Selecciona o crea una campaña arriba para poder grabar";
    }
    return;
  }

  const statusText = document.getElementById("liveRecordingStatus");
  const stopBtn = document.getElementById("btnStopRecording");
  if (statusText && (!stopBtn || stopBtn.disabled) && currentLiveMode !== "class") {
    statusText.textContent = "Listo para iniciar la sesión";
  }

  if (overrideCheck) overrideCheck.disabled = false;
  if (sessionInput) {
    sessionInput.disabled = isOverridden ? false : true;
    sessionInput.placeholder = "";
  }
  if (badge) {
    badge.className = "px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30";
  }

  const lowerName = rawCampName.toLowerCase();
  if (knownCampaigns && knownCampaigns[lowerName]) {
    const known = knownCampaigns[lowerName];
    const nextSess = (known.last_session || 0) + 1;
    if (badge) badge.textContent = `Próx. Sesión #${nextSess} (Historial: ${known.last_session})`;
    if (sessionInput && !isOverridden) sessionInput.value = nextSess;
  } else {
    if (badge) badge.textContent = "Nueva Campaña (Sesión #1)";
    if (sessionInput && !isOverridden) sessionInput.value = 1;
  }

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(rawCampName)}`);
    if (res.ok) {
      const data = await res.json();
      currentCampaignState = data.campaign_state;
      const nextSess = data.active_context ? data.active_context.session_number : (currentCampaignState.last_session + 1);
      if (sessionInput && !isOverridden) sessionInput.value = nextSess;
      if (badge) badge.textContent = `Próx. Sesión #${nextSess} (Historial: ${currentCampaignState.last_session})`;

      const priorLoreInput = document.getElementById("priorLoreInput");
      const priorBadge = document.getElementById("priorLoreConfiguredBadge");
      const pLore = (currentCampaignState && currentCampaignState.prior_lore) || "";
      if (priorLoreInput) priorLoreInput.value = pLore;
      if (priorBadge) {
        if (pLore.trim()) priorBadge.classList.remove("hidden");
        else priorBadge.classList.add("hidden");
      }

      const campRoster = (currentCampaignState && (currentCampaignState.roster || currentCampaignState.participants || currentCampaignState.party || currentCampaignState.players)) || [];
      if (typeof renderRosterTable === "function") renderRosterTable(campRoster);
      if (typeof renderPartyChips === "function") renderPartyChips(campRoster);

      const dmRow = document.querySelector("#rosterTableBody tr:first-child");
      if (dmRow) {
        const savedDmName = (currentCampaignState && (currentCampaignState.dm_name || currentCampaignState.dm || currentCampaignState.dungeon_master)) || "";
        const savedDmDiscord = (currentCampaignState && (currentCampaignState.dm_discord_id || currentCampaignState.dm_discord || currentCampaignState.dm_discord_user_id)) || "";
        const dmInput = dmRow.querySelector(".player-name");
        const dmSelect = dmRow.querySelector(".discord-user-select");
        if (dmInput) {
          dmInput.value = savedDmName;
          dmInput.placeholder = "Nombre del DM...";
        }
        if (dmSelect) {
          if (savedDmDiscord) {
            dmSelect.innerHTML = buildDiscordSelectOptions(savedDmDiscord, savedDmName);
            dmSelect.value = savedDmDiscord;
          } else {
            dmSelect.value = "";
          }
        }
      }

      updateCampaignViewTabs(currentCampaignState);

      const histSelect = document.getElementById("historySessionSelect");
      if (histSelect) {
        histSelect.innerHTML = `<option value="">[ Seleccionar Sesión ▾ ]</option>`;
        const sessions = (currentCampaignState && currentCampaignState.sessions) || [];
        if (sessions.length > 0) {
          histSelect.disabled = false;
          sessions.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.session_number;
            opt.textContent = `Sesión #${s.session_number}: ${s.title || 'Sin Título'}`;
            histSelect.appendChild(opt);
          });
        } else {
          histSelect.disabled = true;
        }
      }
      if (typeof populateWikiSessionExportDropdown === "function") {
        populateWikiSessionExportDropdown((currentCampaignState && currentCampaignState.sessions) || []);
      }
    } else {
      if (badge) badge.textContent = "Nueva Campaña (Sesión #1)";
      if (sessionInput && !isOverridden) sessionInput.value = 1;
      const priorLoreInput = document.getElementById("priorLoreInput");
      const priorBadge = document.getElementById("priorLoreConfiguredBadge");
      if (priorLoreInput) priorLoreInput.value = "";
      if (priorBadge) priorBadge.classList.add("hidden");
      const histSelect = document.getElementById("historySessionSelect");
      if (histSelect) {
        histSelect.innerHTML = `<option value="">[ Seleccionar Sesión ▾ ]</option>`;
        histSelect.disabled = true;
      }
      if (typeof populateWikiSessionExportDropdown === "function") {
        populateWikiSessionExportDropdown([]);
      }
    }
  } catch (err) {
    console.warn("Error loading campaign:", err);
  }
}

var campaignRosterLoadVersion = 0;
async function onCampaignChange() {
  if (currentWorkspace === "work_and_study") return;
  const version = ++campaignRosterLoadVersion;
  const rosterCard = document.getElementById("rosterFullCard");
  if (rosterCard) { rosterCard.inert = true; rosterCard.setAttribute("aria-busy", "true"); }
  try {

  if (typeof _rosterDebounceTimer !== "undefined" && _rosterDebounceTimer) {
    clearTimeout(_rosterDebounceTimer);
    _rosterDebounceTimer = null;
  }

  currentCampaignState = null;

  const dmRow = document.querySelector("#rosterTableBody tr:first-child");
  if (dmRow) {
    const dmInput = dmRow.querySelector(".player-name") || dmRow.querySelector('[data-field="player_name"]');
    const dmDiscordSelect = dmRow.querySelector(".discord-user-select") || dmRow.querySelector('[data-field="discord_user_id"]');
    if (dmInput) {
      dmInput.value = "";
      dmInput.placeholder = "Nombre del DM...";
    }
    if (dmDiscordSelect) {
      dmDiscordSelect.value = "";
    }
  }
  if (typeof renderRosterTable === "function") renderRosterTable([]);

  const rawCampName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (rawCampName) {
    localStorage.setItem("last_active_campaign", rawCampName);
  }
  if (typeof loadCampaignRoster === "function") {
    await loadCampaignRoster(rawCampName);
  }
  if (version !== campaignRosterLoadVersion) return;
  await loadCurrentCampaign();
  if (typeof syncWikiCampaignSelector === "function") {
    syncWikiCampaignSelector(rawCampName);
  }
  } finally {
    if (version === campaignRosterLoadVersion && rosterCard) {
      rosterCard.inert = false; rosterCard.setAttribute("aria-busy", "false");
    }
  }
}

async function saveCurrentCampaignLore(showMessage = false) {
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) {
    if (showMessage) showAlert("Debes escribir o seleccionar una campaña antes de guardar el lore.");
    return;
  }
  const priorLore = (document.getElementById("priorLoreInput")?.value || "").trim();
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/prior-lore`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prior_lore: priorLore })
    });
    if (res.ok) {
      const badge = document.getElementById("priorLoreConfiguredBadge");
      if (badge) {
        if (priorLore) badge.classList.remove("hidden");
        else badge.classList.add("hidden");
      }
      if (showMessage) {
        const msg = document.getElementById("priorLoreStatusMsg");
        if (msg) {
          msg.classList.remove("hidden");
          setTimeout(() => msg.classList.add("hidden"), 2500);
        }
      }
      if (currentCampaignState) {
        currentCampaignState.prior_lore = priorLore;
      }
      if (typeof notifyDriveSaveEvent === "function") {
        notifyDriveSaveEvent();
      }
    }
  } catch (err) {
    console.warn("Error saving prior lore:", err);
  }
}

async function onSelectHistoricalSession(sessionNum) {
  if (!sessionNum) return;
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim() || (currentCampaignState && currentCampaignState.campaign_name) || "";
  if (!campName) {
    showAlert("Selecciona o abre una campaña primero.");
    return;
  }
  const num = parseInt(sessionNum, 10);
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/session/${num}`);
    if (!res.ok) {
      throw new Error(`Error ${res.status}: no se pudo cargar la sesión #${num}`);
    }
    const sessionData = await res.json();

    if (sessionData.campaign_state) {
      currentCampaignState = sessionData.campaign_state;
    }

    const fullData = {
      campaign_name: sessionData.campaign_name || campName,
      session_number: sessionData.session_number || num,
      chronicle: sessionData.chronicle_markdown || (sessionData.session_chapter && sessionData.session_chapter.chronicle_text) || "",
      chronicle_markdown: sessionData.chronicle_markdown || "",
      session_chapter: sessionData.session_chapter || {},
      detected_pcs: sessionData.pcs || (sessionData.session_chapter && sessionData.session_chapter.detected_pcs) || [],
      detected_party: (sessionData.session_chapter && sessionData.session_chapter.detected_party) || [],
      detected_npc_names: (sessionData.session_chapter && sessionData.session_chapter.detected_npc_names) || [],
      campaign_state: sessionData.campaign_state || currentCampaignState,
      quests: sessionData.quests || (currentCampaignState && currentCampaignState.quests) || [],
      npcs: sessionData.npcs || (currentCampaignState && currentCampaignState.npcs) || [],
      pcs: sessionData.pcs || (currentCampaignState && currentCampaignState.roster) || [],
      recap: sessionData.recap || "",
      next_session_script: sessionData.recap || "",
      user_coaching: (sessionData.session_chapter && (sessionData.session_chapter.user_coaching || sessionData.session_chapter.markus_coaching)) || "",
      episode_synopsis: sessionData.session_chapter && sessionData.session_chapter.episode_synopsis,
      transcript: sessionData.raw_transcript || "",
      raw_transcript: sessionData.raw_transcript || "",
      txt_filename: sessionData.txt_filename || null,
      wav_filename: sessionData.wav_filename || null,
      segments: [],
    };

    displayResults(fullData);
  } catch (err) {
    console.error("Error fetching historical session:", err);
    showAlert(`Error al cargar la sesión #${num}: ${err.message}`);
  }
}

// =========================================================================
// RECORDING SESSION CONTROL
// =========================================================================
function setRecordingUI(isRecording) {
  const btnStart = document.getElementById("btnStartRecording");
  const btnStop = document.getElementById("btnStopRecording");
  const badge = document.getElementById("headerRecordingBadge");
  const statusText = document.getElementById("liveRecordingStatus");
  const timerEl = document.getElementById("liveTimer");

  if (isRecording) {
    startHeartbeat();
    if (btnStart) {
      btnStart.disabled = true;
      btnStart.classList.add("opacity-40", "cursor-not-allowed");
    }
    if (btnStop) btnStop.disabled = false;
    if (badge) badge.classList.remove("hidden");
    if (statusText) {
      if (typeof audioSourceMode !== "undefined" && audioSourceMode === "browser_mic") {
        statusText.textContent = "Grabación en curso con Micrófono del Móvil / Navegador";
      } else if (currentLiveMode === "class") {
        statusText.textContent = "Grabación de clase en curso (Micrófono Mono 16 kHz)";
      } else {
        statusText.textContent = "Grabación en curso (Canal Izq: Mic | Canal Der: Discord)";
      }
      statusText.className = "text-xs text-rose-400 font-semibold animate-pulse";
    }
    if (timerEl) {
      timerEl.classList.remove("text-slate-400");
      timerEl.classList.add("text-rose-400");
    }
  } else {
    stopHeartbeat();
    if (btnStart) {
      btnStart.disabled = false;
      btnStart.classList.remove("opacity-40", "cursor-not-allowed");
    }
    if (btnStop) btnStop.disabled = true;
    if (badge) badge.classList.add("hidden");
    if (statusText) {
      if (typeof audioSourceMode !== "undefined" && audioSourceMode === "browser_mic") {
        statusText.textContent = "Listo para grabar desde el micrófono de este dispositivo";
      } else if (currentLiveMode === "class") {
        statusText.textContent = "Listo para grabar la clase universitaria o reunión";
      } else {
        statusText.textContent = "Listo para iniciar la sesión de juego";
      }
      statusText.className = "text-xs text-slate-500 font-medium";
    }
    if (timerEl) {
      timerEl.classList.add("text-slate-400");
      timerEl.classList.remove("text-rose-400");
    }
  }
}

function startTimer() {
  stopTimer();
  updateTimerDisplay();
  timerInterval = setInterval(() => {
    secondsElapsed++;
    updateTimerDisplay();
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function updateTimerDisplay() {
  const hrs = Math.floor(secondsElapsed / 3600).toString().padStart(2, "0");
  const mins = Math.floor((secondsElapsed % 3600) / 60).toString().padStart(2, "0");
  const secs = (secondsElapsed % 60).toString().padStart(2, "0");
  const el = document.getElementById("liveTimer");
  if (el) el.textContent = `${hrs}:${mins}:${secs}`;
}

// =========================================================================
// YOUTUBE & FILE TRANSCRIPTION HANDLERS
// =========================================================================
async function transcribeYoutube() {
  const url = document.getElementById("youtubeUrl")?.value.trim();
  const modelSize = document.getElementById("globalModelSize")?.value || "base";
  const engine = document.getElementById("transcriptionEngine")?.value || "groq";
  const isClass = (currentWorkspace === "work_and_study" || currentLiveMode === "class");
  const campaignName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!isClass && !campaignName) {
    showAlert("Debes seleccionar o crear una campaña antes de transcribir.");
    const campInput = document.getElementById("campaignNameInput");
    if (campInput) {
      campInput.focus();
      campInput.classList.add("ring-2", "ring-rose-500", "border-rose-500");
      setTimeout(() => {
        campInput.classList.remove("ring-2", "ring-rose-500", "border-rose-500");
      }, 3500);
    }
    return;
  }
  const sessionNumber = parseInt(document.getElementById("sessionNumberInput")?.value) || null;
  const roster = typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [];

  if (!url) return showAlert("Introduce una URL de YouTube válida.");

  if (typeof checkQuotaBeforeAction === "function") {
    const quotaOk = await checkQuotaBeforeAction("el procesamiento del video de YouTube");
    if (!quotaOk) return;
  }

  if (isYoutubeTranscribing && youtubeAbortController) {
    try {
      youtubeAbortController.abort();
    } catch (_) {}
    if (typeof finishProgressTracking === "function") finishProgressTracking(false);
  }

  youtubeAbortController = new AbortController();
  window.currentActiveAbortController = youtubeAbortController;
  isYoutubeTranscribing = true;

  const btnYt = document.getElementById("btnYoutube");
  const origBtnHtml = btnYt ? btnYt.innerHTML : "Descargar y Procesar";
  if (btnYt) {
    btnYt.innerHTML = `<span class="inline-block animate-spin"><span data-ui-icon=clock aria-hidden=true></span></span> Procesando...`;
  }

  if (typeof lastActionCallback !== "undefined") lastActionCallback = () => transcribeYoutube();
  const taskId = generateTaskId();
  const engineName = (engine === "groq") ? "Groq Whisper Large-v3" : "faster-whisper local";

  const customDateInput = document.getElementById("workStudyDateInput");
  const customDateVal = customDateInput ? customDateInput.value.trim() : "";

  let bodyPayload = {
    task_id: taskId,
    url: url,
    model_size: modelSize,
    engine: engine,
    workspace: currentWorkspace,
    recording_mode: isClass ? "class" : "roleplay",
    target_language: currentTargetLanguage,
    custom_date: customDateVal || null,
    client_timezone_offset: new Date().getTimezoneOffset(),
  };

  if (typeof updateStepperMode === "function") updateStepperMode(true);
  if (isClass) {
    const topic = (document.getElementById("workStudyTopicInput") ? document.getElementById("workStudyTopicInput").value.trim() : "") ||
                  (document.getElementById("lectureTopicInput") ? document.getElementById("lectureTopicInput").value.trim() : "") ||
                  "Reunión / Clase";
    const subject = (document.getElementById("lectureSubjectInput") ? document.getElementById("lectureSubjectInput").value.trim() : "") ||
                    topic;
    bodyPayload.subject = subject;
    bodyPayload.topic = topic;
    bodyPayload.campaign_name = null;
    bodyPayload.session_number = null;
    bodyPayload.roster = [];
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Descargando audio de YouTube y generando síntesis...",
        `Extrayendo audio en alta calidad, transcribiendo con ${engineName} y sintetizando conceptos para "${topic}".`
      );
    }
  } else {
    bodyPayload.campaign_name = campaignName;
    bodyPayload.session_number = sessionNumber;
    bodyPayload.roster = roster;
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Descargando audio de YouTube y procesando...",
        `Extrayendo audio en alta calidad, transcribiendo con ${engineName} y actualizando el Diario de Campaña.`
      );
    }
  }

  try {
    const res = await fetch("/api/transcribe/youtube", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getUserApiHeaders()
      },
      body: JSON.stringify(bodyPayload),
      signal: youtubeAbortController.signal
    });
    const data = await res.json();
    if (checkAuthErrorAndRedirect(res.status, data)) {
      throw new Error("Credenciales de API requeridas.");
    }
    if (!res.ok) throw new Error(data.detail || "Error al transcribir YouTube.");
    displayResults(data, { source: "youtube" });
    if (typeof finishProgressTracking === "function") finishProgressTracking(true);
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("[transcribeYoutube] Petición cancelada.");
      return;
    }
    if (typeof finishProgressTracking === "function") finishProgressTracking(false);
    showErrorCard(err.message, () => transcribeYoutube());
  } finally {
    isYoutubeTranscribing = false;
    if (btnYt) {
      btnYt.innerHTML = origBtnHtml;
    }
  }
}

var selectedAudioFile = null;
var selectedTimelineFile = null;
var selectedLocalRecordingMeta = null;
var selectedLocalRecordingHasTimeline = false;

function handleDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  const zone = document.getElementById("dropZone");
  if (zone) zone.classList.add("border-indigo-500", "bg-indigo-950/20");
}

function handleDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  const zone = document.getElementById("dropZone");
  if (zone) zone.classList.remove("border-indigo-500", "bg-indigo-950/20");
}

function handleDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  const zone = document.getElementById("dropZone");
  if (zone) zone.classList.remove("border-indigo-500", "bg-indigo-950/20");
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    handleIncomingFiles(e.dataTransfer.files);
  }
}

function handleIncomingFiles(fileListOrInput) {
  if (!fileListOrInput) return;
  const rawFiles = fileListOrInput.files ? fileListOrInput.files : fileListOrInput;
  if (!rawFiles || rawFiles.length === 0) return;
  const files = Array.from(rawFiles);

  for (const f of files) {
    const lower = f.name.toLowerCase();
    if (lower.endsWith(".json")) {
      selectedTimelineFile = f;
    } else if (
      lower.endsWith(".wav") ||
      lower.endsWith(".mp3") ||
      lower.endsWith(".m4a") ||
      lower.endsWith(".aac") ||
      lower.endsWith(".ogg") ||
      lower.endsWith(".flac") ||
      lower.endsWith(".webm") ||
      (f.type && f.type.startsWith("audio/"))
    ) {
      selectedAudioFile = f;
      selectedLocalRecordingFilename = null;
      selectedLocalRecordingMeta = null;
      selectedLocalRecordingHasTimeline = false;
    }
  }

  // Si sólo se pasó 1 archivo y no es json, asignarlo como audio
  if (files.length === 1 && !files[0].name.toLowerCase().endsWith(".json")) {
    selectedAudioFile = files[0];
    selectedLocalRecordingFilename = null;
    selectedLocalRecordingMeta = null;
    selectedLocalRecordingHasTimeline = false;
  }

  // Si sólo se seleccionó un .timeline.json y no hay audio, buscar si coincide con una grabación local
  if (!selectedAudioFile && !selectedLocalRecordingFilename && selectedTimelineFile) {
    const stem = selectedTimelineFile.name.replace(/\.timeline\.json$/i, "").replace(/\.json$/i, "").toLowerCase();
    if (window.localRecordingsCache && window.localRecordingsCache.length > 0) {
      const matched = window.localRecordingsCache.find(r => {
        const rStem = r.filename.replace(/\.[^.]+$/, "").toLowerCase();
        return rStem === stem || r.filename.toLowerCase().startsWith(stem);
      });
      if (matched) {
        selectedLocalRecordingFilename = matched.filename;
        selectedLocalRecordingHasTimeline = Boolean(matched.has_timeline);
        selectedLocalRecordingMeta = { size_mb: matched.size_mb, folder: matched.folder };
      }
    }
  }

  if (fileListOrInput && fileListOrInput.value !== undefined) {
    try { fileListOrInput.value = ''; } catch(e){}
  }

  updateSelectedFilesUI();
}

function handleAudioOnlySelect(input) {
  if (input && input.files && input.files[0]) {
    selectedAudioFile = input.files[0];
    selectedLocalRecordingFilename = null;
    selectedLocalRecordingMeta = null;
    selectedLocalRecordingHasTimeline = false;
    try { input.value = ''; } catch(e){}
    updateSelectedFilesUI();
  }
}

function handleTimelineOnlySelect(input) {
  if (input && input.files && input.files[0]) {
    selectedTimelineFile = input.files[0];
    try { input.value = ''; } catch(e){}
    updateSelectedFilesUI();
  }
}

function clearSelectedAudio(e) {
  if (e) e.stopPropagation();
  selectedAudioFile = null;
  selectedLocalRecordingFilename = null;
  selectedLocalRecordingMeta = null;
  selectedLocalRecordingHasTimeline = false;
  const audioInput = document.getElementById("audioFileInput");
  if (audioInput) audioInput.value = "";
  const multiInput = document.getElementById("multiFileInput");
  if (multiInput) multiInput.value = "";
  updateSelectedFilesUI();
}

function clearSelectedTimeline(e) {
  if (e) e.stopPropagation();
  selectedTimelineFile = null;
  selectedLocalRecordingHasTimeline = false;
  const timelineInput = document.getElementById("timelineFileInput");
  if (timelineInput) timelineInput.value = "";
  const multiInput = document.getElementById("multiFileInput");
  if (multiInput) multiInput.value = "";
  updateSelectedFilesUI();
}

function updateSelectedFilesUI() {
  const btn = document.getElementById("btnFile");
  const dropZone = document.getElementById("dropZone");

  // Audio Slot Elements
  const slotAudioCard = document.getElementById("slotAudioCard");
  const btnClearAudio = document.getElementById("btnClearAudio");
  const slotAudioEmpty = document.getElementById("slotAudioEmpty");
  const slotAudioFilled = document.getElementById("slotAudioFilled");
  const slotAudioName = document.getElementById("slotAudioName");
  const slotAudioMeta = document.getElementById("slotAudioMeta");

  // Timeline Slot Elements
  const slotTimelineCard = document.getElementById("slotTimelineCard");
  const btnClearTimeline = document.getElementById("btnClearTimeline");
  const slotTimelineEmpty = document.getElementById("slotTimelineEmpty");
  const slotTimelineFilled = document.getElementById("slotTimelineFilled");
  const slotTimelineName = document.getElementById("slotTimelineName");
  const slotTimelineMeta = document.getElementById("slotTimelineMeta");

  // 1. Audio Slot State
  const hasAudio = Boolean(selectedAudioFile || selectedLocalRecordingFilename);
  if (selectedAudioFile) {
    if (slotAudioEmpty) slotAudioEmpty.classList.add("hidden");
    if (slotAudioFilled) slotAudioFilled.classList.remove("hidden");
    if (slotAudioName) slotAudioName.textContent = selectedAudioFile.name;
    if (slotAudioMeta) slotAudioMeta.textContent = `Archivo de audio (${(selectedAudioFile.size / (1024 * 1024)).toFixed(1)} MB)`;
    if (btnClearAudio) btnClearAudio.classList.remove("hidden");
    if (slotAudioCard) {
      slotAudioCard.classList.add("border-emerald-500/50", "bg-emerald-950/20");
      slotAudioCard.classList.remove("border-slate-800", "bg-slate-900/60");
    }
  } else if (selectedLocalRecordingFilename) {
    if (slotAudioEmpty) slotAudioEmpty.classList.add("hidden");
    if (slotAudioFilled) slotAudioFilled.classList.remove("hidden");
    if (slotAudioName) slotAudioName.textContent = selectedLocalRecordingFilename;
    const mb = selectedLocalRecordingMeta?.size_mb ? ` (${selectedLocalRecordingMeta.size_mb} MB)` : "";
    const folder = selectedLocalRecordingMeta?.folder ? ` en ${selectedLocalRecordingMeta.folder}` : " en data/input";
    if (slotAudioMeta) slotAudioMeta.textContent = `Grabación local guardada${folder}${mb}`;
    if (btnClearAudio) btnClearAudio.classList.remove("hidden");
    if (slotAudioCard) {
      slotAudioCard.classList.add("border-emerald-500/50", "bg-emerald-950/20");
      slotAudioCard.classList.remove("border-slate-800", "bg-slate-900/60");
    }
  } else {
    if (slotAudioEmpty) slotAudioEmpty.classList.remove("hidden");
    if (slotAudioFilled) slotAudioFilled.classList.add("hidden");
    if (btnClearAudio) btnClearAudio.classList.add("hidden");
    if (slotAudioCard) {
      slotAudioCard.classList.remove("border-emerald-500/50", "bg-emerald-950/20");
      slotAudioCard.classList.add("border-slate-800", "bg-slate-900/60");
    }
  }

  // 2. Timeline Slot State
  const hasAutoTimeline = Boolean(selectedLocalRecordingFilename && selectedLocalRecordingHasTimeline);
  if (selectedTimelineFile) {
    if (slotTimelineEmpty) slotTimelineEmpty.classList.add("hidden");
    if (slotTimelineFilled) slotTimelineFilled.classList.remove("hidden");
    if (slotTimelineName) slotTimelineName.textContent = selectedTimelineFile.name;
    if (slotTimelineMeta) slotTimelineMeta.textContent = `Archivo timeline subido (${(selectedTimelineFile.size / 1024).toFixed(1)} KB)`;
    if (btnClearTimeline) btnClearTimeline.classList.remove("hidden");
    if (slotTimelineCard) {
      slotTimelineCard.classList.add("border-indigo-500/50", "bg-indigo-950/20");
      slotTimelineCard.classList.remove("border-slate-800", "bg-slate-900/60");
    }
  } else if (hasAutoTimeline) {
    const stem = selectedLocalRecordingFilename.replace(/\.[^.]+$/, "");
    if (slotTimelineEmpty) slotTimelineEmpty.classList.add("hidden");
    if (slotTimelineFilled) slotTimelineFilled.classList.remove("hidden");
    if (slotTimelineName) slotTimelineName.textContent = `${stem}.timeline.json`;
    if (slotTimelineMeta) slotTimelineMeta.textContent = "Timeline de Discord detectado en tu PC junto al audio";
    if (btnClearTimeline) btnClearTimeline.classList.remove("hidden");
    if (slotTimelineCard) {
      slotTimelineCard.classList.add("border-indigo-500/50", "bg-indigo-950/20");
      slotTimelineCard.classList.remove("border-slate-800", "bg-slate-900/60");
    }
  } else {
    if (slotTimelineEmpty) slotTimelineEmpty.classList.remove("hidden");
    if (slotTimelineFilled) slotTimelineFilled.classList.add("hidden");
    if (btnClearTimeline) btnClearTimeline.classList.add("hidden");
    if (slotTimelineCard) {
      slotTimelineCard.classList.remove("border-indigo-500/50", "bg-indigo-950/20");
      slotTimelineCard.classList.add("border-slate-800", "bg-slate-900/60");
    }
  }

  // 3. DropZone visual state
  if (dropZone) {
    if (hasAudio && (selectedTimelineFile || hasAutoTimeline)) {
      dropZone.classList.add("border-emerald-500/50", "bg-emerald-950/10");
    } else if (hasAudio) {
      dropZone.classList.add("border-indigo-500/40", "bg-slate-950");
      dropZone.classList.remove("border-emerald-500/50", "bg-emerald-950/10");
    } else {
      dropZone.classList.remove("border-emerald-500/50", "bg-emerald-950/10", "border-indigo-500/40");
    }
  }

  // 4. Submit button state
  if (btn) {
    btn.disabled = !hasAudio;
  }
}

function selectExistingRecording(filename, hasTimeline = false, sizeMb = null, folder = null) {
  selectedLocalRecordingFilename = filename;
  selectedLocalRecordingHasTimeline = Boolean(hasTimeline);
  selectedLocalRecordingMeta = { size_mb: sizeMb, folder: folder };
  selectedAudioFile = null;
  const audioInput = document.getElementById("audioFileInput");
  if (audioInput) audioInput.value = "";
  const multiInput = document.getElementById("multiFileInput");
  if (multiInput) multiInput.value = "";
  updateSelectedFilesUI();
}

async function loadLocalRecordingsList() {
  const container = document.getElementById("localRecordingsList");
  if (!container) return;
  try {
    const res = await fetch("/api/audio/local-recordings");
    if (!res.ok) throw new Error("No se pudieron cargar las grabaciones.");
    const data = await res.json();
    const files = data.files || [];
    window.localRecordingsCache = files;
    if (files.length === 0) {
      container.innerHTML = `<p class="text-slate-500 italic text-[11px]">No hay grabaciones en data/input ni en campañas aún.</p>`;
      return;
    }
    let html = '<div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">';
    files.forEach((f, idx) => {
      const isLatest = idx === 0;
      let displayDate = f.created_at;
      if (f.timestamp) {
        const ms = f.timestamp < 1e11 ? f.timestamp * 1000 : f.timestamp;
        const formatted = getLocalFormattedDateTime(new Date(ms));
        if (formatted) displayDate = formatted;
      }
      html += `
        <div class="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 transition text-left cursor-pointer group"
             onclick="selectExistingRecording('${f.filename}', ${f.has_timeline ? 'true' : 'false'}, ${f.size_mb}, '${f.folder || 'data/input'}')">
          <div class="min-w-0 pr-2">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="font-mono text-xs text-slate-200 group-hover:text-amber-400 font-medium truncate">${f.filename}</span>
              ${isLatest ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">MÁS RECIENTE</span>' : ''}
              ${f.has_timeline ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30"><span data-ui-icon=headphones aria-hidden=true></span> Con Timeline</span>' : ''}
            </div>
            <div class="text-[10px] text-slate-500 flex items-center gap-2 mt-0.5">
              <span><span data-ui-icon=calendar aria-hidden=true></span> ${displayDate}</span>
              <span><span data-ui-icon=save aria-hidden=true></span> ${f.size_mb} MB</span>
              ${f.folder ? `<span class="text-indigo-400/80"><span data-ui-icon=folder aria-hidden=true></span> ${f.folder}</span>` : ''}
            </div>
          </div>
          <button type="button" class="shrink-0 text-xs px-2.5 py-1 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white font-medium border border-indigo-500/30 transition cursor-pointer">
            Usar
          </button>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="text-rose-400 text-[11px]">Error cargando grabaciones: ${e.message}</p>`;
  }
}

async function transcribeFile() {
  const hasAudio = Boolean(selectedLocalRecordingFilename || selectedAudioFile);
  if (!hasAudio) {
    if (selectedTimelineFile) {
      if (typeof showAlert === "function") {
        showAlert("Has seleccionado el archivo de timeline (.timeline.json), pero falta el archivo de audio (.wav o .mp3). Por favor selecciona o arrastra el archivo de audio correspondiente, o elige una grabación local de la lista.");
      } else {
        alert("Has seleccionado el archivo de timeline (.timeline.json), pero falta el archivo de audio (.wav o .mp3). Por favor selecciona o arrastra el archivo de audio correspondiente, o elige una grabación local de la lista.");
      }
    } else {
      if (typeof showAlert === "function") {
        showAlert("Por favor selecciona o arrastra un archivo de audio, o elige una grabación local de la lista.");
      } else {
        alert("Por favor selecciona o arrastra un archivo de audio, o elige una grabación local de la lista.");
      }
    }
    return;
  }

  const modelSize = (document.getElementById("globalModelSize") ? document.getElementById("globalModelSize").value : "") || "base";
  const engine = (document.getElementById("transcriptionEngine") ? document.getElementById("transcriptionEngine").value : "") || "groq";
  const isClass = (currentWorkspace === "work_and_study" || currentLiveMode === "class");
  const campaignName = (document.getElementById("campaignNameInput") ? document.getElementById("campaignNameInput").value.trim() : "");
  if (!isClass && !campaignName) {
    if (typeof showAlert === "function") showAlert("Debes seleccionar o crear una campaña antes de transcribir un archivo.");
    const campInput = document.getElementById("campaignNameInput");
    if (campInput) {
      campInput.focus();
      campInput.classList.add("ring-2", "ring-rose-500", "border-rose-500");
      setTimeout(() => {
        campInput.classList.remove("ring-2", "ring-rose-500", "border-rose-500");
      }, 3500);
    }
    return;
  }
  const sessionNumber = (document.getElementById("sessionNumberInput") && parseInt(document.getElementById("sessionNumberInput").value)) || null;
  const roster = typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [];

  if (typeof checkQuotaBeforeAction === "function") {
    const quotaOk = await checkQuotaBeforeAction("el procesamiento del archivo de audio");
    if (!quotaOk) return;
  }

  const taskId = generateTaskId();
  const engineName = (engine === "groq") ? "Groq Whisper Large-v3" : "faster-whisper local";
  if (typeof lastActionCallback !== "undefined") lastActionCallback = () => transcribeFile();

  if (typeof updateStepperMode === "function") updateStepperMode(false);
  if (isClass) {
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Transcribiendo archivo local y generando síntesis...",
        `Cargando audio, ejecutando inferencia con ${engineName} y sintetizando conceptos.`
      );
    }
  } else {
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Transcribiendo archivo local y procesando campaña...",
        `Cargando audio, ejecutando inferencia con ${engineName} y actualizando el Diario de Campaña con Gemini.`
      );
    }
  }

  const btnF = document.getElementById("btnFile");
  const origBtnFHtml = btnF ? btnF.innerHTML : "Procesar Grabación";
  if (btnF) {
    btnF.disabled = true;
    btnF.innerHTML = `<span class="inline-block animate-spin"><span data-ui-icon=clock aria-hidden=true></span></span> Procesando...`;
  }

  if (window.currentActiveAbortController) {
    try { window.currentActiveAbortController.abort(); } catch (_) {}
  }
  window.currentActiveAbortController = new AbortController();

  try {
    const formData = new FormData();
    formData.append("task_id", taskId);
    if (selectedLocalRecordingFilename) {
      formData.append("existing_filename", selectedLocalRecordingFilename);
    } else if (selectedAudioFile) {
      formData.append("file", selectedAudioFile);
    }

    if (selectedTimelineFile) {
      formData.append("timeline_file", selectedTimelineFile);
    }
    formData.append("model_size", modelSize);
    formData.append("engine", engine);
    formData.append("workspace", currentWorkspace);
    formData.append("recording_mode", isClass ? "class" : "roleplay");
    formData.append("target_language", currentTargetLanguage);
    const customDateInput = document.getElementById("workStudyDateInput");
    const customDateVal = customDateInput ? customDateInput.value.trim() : "";
    if (customDateVal) {
      formData.append("custom_date", customDateVal);
    }
    formData.append("client_timezone_offset", String(new Date().getTimezoneOffset()));

    if (isClass) {
      const topic = (document.getElementById("workStudyTopicInput") ? document.getElementById("workStudyTopicInput").value.trim() : "") ||
                    (document.getElementById("lectureTopicInput") ? document.getElementById("lectureTopicInput").value.trim() : "") ||
                    "Reunión / Clase";
      const subject = (document.getElementById("lectureSubjectInput") ? document.getElementById("lectureSubjectInput").value.trim() : "") ||
                      topic;
      formData.append("subject", subject);
      formData.append("topic", topic);
    } else {
      formData.append("campaign_name", campaignName);
      if (sessionNumber) formData.append("session_number", sessionNumber);
      formData.append("roster_json", JSON.stringify(roster));
    }

    const res = await fetch("/api/transcribe/file", {
      method: "POST",
      headers: getUserApiHeaders(),
      body: formData,
      signal: window.currentActiveAbortController.signal
    });
    const data = await res.json();
    if (checkAuthErrorAndRedirect(res.status, data)) {
      throw new Error("Credenciales de API requeridas.");
    }
    if (!res.ok) throw new Error(data.detail || "Error al transcribir archivo.");
    displayResults(data, { source: "file" });
    if (typeof finishProgressTracking === "function") finishProgressTracking(true);
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("[transcribeFile] Petición cancelada por el usuario.");
      return;
    }
    if (typeof finishProgressTracking === "function") finishProgressTracking(false);
    showErrorCard(err.message, () => transcribeFile());
  } finally {
    if (btnF) {
      btnF.disabled = false;
      btnF.innerHTML = origBtnFHtml;
    }
  }
}

// Global window bindings
window.handleDragOver = handleDragOver;
window.handleDragLeave = handleDragLeave;
window.handleDrop = handleDrop;
window.handleIncomingFiles = handleIncomingFiles;
window.handleAudioOnlySelect = handleAudioOnlySelect;
window.handleTimelineOnlySelect = handleTimelineOnlySelect;
window.clearSelectedAudio = clearSelectedAudio;
window.clearSelectedTimeline = clearSelectedTimeline;
window.updateSelectedFilesUI = updateSelectedFilesUI;
window.selectExistingRecording = selectExistingRecording;
window.loadLocalRecordingsList = loadLocalRecordingsList;
window.transcribeFile = transcribeFile;

// =========================================================================
// RESULTS DISPLAY & TABS
// =========================================================================
function displayResults(data, options = {}) {
  currentResult = data;
  if (typeof notifyDriveSaveEvent === "function") notifyDriveSaveEvent();
  const isClassMode = (data.recording_mode === "class" || currentLiveMode === "class" || currentWorkspace === "work_and_study");

  const retentionPrompt = document.getElementById("transcriptRetentionPrompt");
  if (retentionPrompt) {
    if (options && (options.source === "youtube" || options.source === "file")) {
      retentionPrompt.classList.remove("hidden");
    } else {
      retentionPrompt.classList.add("hidden");
    }
  }

  if (isClassMode) {
    const campLabel = document.getElementById("resCampaignLabel");
    if (campLabel) campLabel.textContent = "Tema / Evento";
    const topicVal = data.topic || data.subject || 
                     (document.getElementById("workStudyTopicInput") ? document.getElementById("workStudyTopicInput").value.trim() : "") ||
                     (document.getElementById("lectureSubjectInput") ? document.getElementById("lectureSubjectInput").value.trim() : "") || 
                     "Reunión / Clase";
    const nameEl = document.getElementById("resCampaignName");
    if (nameEl) nameEl.textContent = topicVal;
  } else {
    const campName = data.campaign_name || (document.getElementById("campaignNameInput")?.value || "").trim();
    const nameEl = document.getElementById("resCampaignName");
    if (nameEl) nameEl.textContent = campName || "Sin Campaña";
  }

  const engineUsed = data.engine_used || document.getElementById("transcriptionEngine")?.value || "groq";
  const engineBadgeEl = document.getElementById("resEngineUsed");
  if (engineBadgeEl) {
    engineBadgeEl.textContent = (engineUsed === "groq") ? "Groq Large-v3" : "Local (faster-whisper)";
  }

  const activeLang = (data.target_language || data.language || currentTargetLanguage || "es").toUpperCase();
  const langEl = document.getElementById("resLanguage");
  if (langEl) langEl.textContent = activeLang;

  const switchBtnText = document.getElementById("btnSwitchLanguageText");
  const btnSwitchLang = document.getElementById("btnSwitchLanguage");
  if (btnSwitchLang) btnSwitchLang.classList.remove("hidden");
  if (switchBtnText) {
    switchBtnText.textContent = activeLang.startsWith("EN") ? "Traducir a Español (ES)" : "Traducir a Inglés (EN)";
  }
  const reprocessBtnText = document.getElementById("btnReprocessCampaignText");
  if (reprocessBtnText) {
    reprocessBtnText.textContent = isClassMode ? "Regenerar Apuntes con Gemini" : "Regenerar con Crónica Profunda (Español)";
  }
  const durEl = document.getElementById("resDuration");
  if (durEl) durEl.textContent = formatSeconds(data.duration);
  const timeEl = document.getElementById("resTime");
  if (timeEl) timeEl.textContent = `${data.elapsed_time || 0}s`;

  const btnDocx = document.getElementById("btnDownloadDocx");
  const btnMd = document.getElementById("btnDownloadMd");
  const docxText = document.getElementById("btnDownloadDocxText");
  const mdText = document.getElementById("btnDownloadMdText");

  syncResultTabsForWorkspace(isClassMode ? "class" : "roleplay");

  if (isClassMode) {
    if (docxText) docxText.textContent = "Documento .docx";
    if (mdText) mdText.textContent = "Notas .md";

    if (data.docx_filename && btnDocx) {
      btnDocx.onclick = () => navigateToDownload(`/api/record/download-docx?filename=${encodeURIComponent(data.docx_filename)}`);
    }
    if (data.md_filename && btnMd) {
      btnMd.onclick = () => navigateToDownload(`/api/record/download-md?filename=${encodeURIComponent(data.md_filename)}`);
    }
  } else {
    if (docxText) docxText.textContent = "Grimorio .docx";
    if (mdText) mdText.textContent = "Grimorio .md";

    if (btnDocx) btnDocx.onclick = downloadCampaignDocx;
    if (btnMd) btnMd.onclick = downloadCampaignMd;
  }

  if (!isClassMode) {
    let stateToUse = data.campaign_state || currentCampaignState || {};
    stateToUse.campaign_name = stateToUse.campaign_name || data.campaign_name || (document.getElementById("campaignNameInput")?.value || "").trim();
    stateToUse.last_session = stateToUse.last_session || data.session_number || 1;

    if (data.quests && data.quests.length > 0) {
      stateToUse.quests = data.quests;
    } else if (data.updated_quests && data.updated_quests.length > 0) {
      stateToUse.quests = data.updated_quests;
    } else if (!stateToUse.quests) {
      stateToUse.quests = [];
    }

    if (data.npcs && data.npcs.length > 0) {
      stateToUse.npcs = data.npcs;
    } else if (data.updated_npcs && data.updated_npcs.length > 0) {
      stateToUse.npcs = data.updated_npcs;
    } else if (!stateToUse.npcs) {
      stateToUse.npcs = [];
    }

    if (data.pcs && data.pcs.length > 0) {
      stateToUse.pcs = data.pcs;
      if (!stateToUse.universal_pcs || stateToUse.universal_pcs.length === 0) {
        stateToUse.universal_pcs = data.pcs;
      }
    }

    currentCampaignState = stateToUse;
    updateCampaignViewTabs(stateToUse);
    if (typeof populateWikiSessionExportDropdown === "function") {
      populateWikiSessionExportDropdown(stateToUse.sessions || [], data.session_number || stateToUse.last_session);
    }

    const badgeEl = document.getElementById("campaignLastSessionBadge");
    if (badgeEl) badgeEl.textContent = `Sesión #${stateToUse.last_session || data.session_number || 1}`;
    const sessInput = document.getElementById("sessionNumberInput");
    if (sessInput) sessInput.value = (stateToUse.last_session || 0) + 1;

    const detectedPcsOrParty = (data.detected_pcs && data.detected_pcs.length > 0) 
      ? data.detected_pcs 
      : (data.detected_party && data.detected_party.length > 0 ? data.detected_party : null);

    if (detectedPcsOrParty && detectedPcsOrParty.length > 0 && typeof renderRosterTable === "function") {
      const formattedPcs = detectedPcsOrParty.map(p => ({
        player_name: p.jugador || p.player_name || "-",
        character_name: p.personaje || p.character_name || "-",
        species: p.especie || p.species || "-",
        role: p.clase || p.role || "Aventurero",
        subclass: p.subclase || p.subclass || "-",
        rol_en_sesion: p.rol_en_sesion || p.session_role || "-",
        is_user_character: Boolean(p.is_user_character),
      }));
      renderRosterTable(formattedPcs);
      if (typeof saveCurrentRoster === "function") saveCurrentRoster();
    }
  } else {
    const npcsEl = document.getElementById("npcsContainer");
    if (npcsEl) npcsEl.innerHTML = "";
    const pcsEl = document.getElementById("pcsContainer");
    if (pcsEl) pcsEl.innerHTML = "";
    const grimorioEl = document.getElementById("grimorio-content");
    if (grimorioEl) grimorioEl.innerHTML = "";
    const nBadge = document.getElementById("npcCountBadge");
    if (nBadge) nBadge.textContent = "0";
    const pBadge = document.getElementById("pcCountBadge");
    if (pBadge) pBadge.textContent = "0";
  }

  let npcNamesToCheck = data.detected_npc_names || [];
  if ((!npcNamesToCheck || npcNamesToCheck.length === 0) && Array.isArray(data.updated_npcs)) {
    npcNamesToCheck = data.updated_npcs.map(n => n.name).filter(Boolean);
  }
  if (!isClassMode && npcNamesToCheck.length > 0 && typeof showNpcSpellcheck === "function") {
    showNpcSpellcheck(npcNamesToCheck);
  }

  const chronicleEl = document.getElementById("chronicleView");
  let chronicleContent = (data.chronicle || "").trim();
  if (!chronicleContent && data.session_chapter && data.session_chapter.chronicle_text) {
    chronicleContent = data.session_chapter.chronicle_text;
  }
  if (!isClassMode && (data.detected_pcs?.length > 0 || data.detected_party?.length > 0)) {
    const hasProto = chronicleContent.includes("Compañía de Aventureros") || chronicleContent.includes("Adventuring Company");
    if (!hasProto) {
      const pcs = data.detected_pcs || data.detected_party || [];
      let protoMd = "###  Compañía de Aventureros (Protagonistas Detectados)\n\n| Personaje | Jugador / Rol | Clase / Especie | Rol en la Sesión |\n|---|---|---|---|\n";
      pcs.forEach(p => {
        const char = p.personaje || p.character_name || "-";
        const jug = p.jugador || p.player_name || "-";
        const cls = p.clase || p.role || "-";
        const esp = p.especie || p.species || "-";
        const cls_esp = (cls !== "-" && esp !== "-") ? `${cls} / ${esp}` : (cls !== "-" ? cls : esp);
        const rol = p.rol_en_sesion || p.session_role || "-";
        protoMd += `| **${char}** | ${jug} | ${cls_esp} | ${rol} |\n`;
      });
      protoMd += "\n---\n\n";
      chronicleContent = protoMd + chronicleContent;
    }
  }
  if (chronicleEl) {
    if (chronicleContent) {
      chronicleEl.innerHTML = renderMarkdownWithKaTeX(chronicleContent);
    } else {
      chronicleEl.innerHTML = `
        <div class="py-10 text-center space-y-4">
          <div class="text-3xl"><span data-ui-icon=warning aria-hidden=true></span></div>
          <p class="text-slate-300 font-medium">${isClassMode ? 'No se generaron apuntes para esta clase.' : 'La crónica y el análisis de la sesión no se pudieron procesar.'}</p>
          <p class="text-slate-500 text-xs max-w-md mx-auto">La transcripción está disponible en memoria. Puedes reintentar la generación con Gemini en pocos segundos sin volver a procesar el audio.</p>
          <button onclick="reprocessCampaignChronicle()" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition">
            <span><span data-ui-icon=refresh aria-hidden=true></span></span> <span>Regenerar con Crónica Profunda (Español)</span>
          </button>
        </div>
      `;
    }
  }

  if (!isClassMode) {
    const grimorioEl = document.getElementById("grimorio-content");
    const mdContent = data.chronicle_markdown || data.grimorio_markdown || data.chronicle || chronicleContent || "";
    if (grimorioEl && mdContent) {
      grimorioEl.innerHTML = renderMarkdownWithKaTeX(mdContent);
    } else if (document.getElementById("journalView") && mdContent) {
      document.getElementById("journalView").innerHTML = `<div id="grimorio-content">${renderMarkdownWithKaTeX(mdContent)}</div>`;
    }
  }

  if (isClassMode) {
    let actionItems = [];
    if (Array.isArray(data.action_items) && data.action_items.length > 0) {
      actionItems = data.action_items;
    } else if (Array.isArray(data.tasks) && data.tasks.length > 0) {
      actionItems = data.tasks;
    } else if (chronicleContent && typeof extractActionItemsFromMarkdown === "function") {
      actionItems = extractActionItemsFromMarkdown(chronicleContent);
    }
    currentAcademicTasks = actionItems;
    if (typeof renderAcademicTasks === "function") {
      renderAcademicTasks(actionItems);
    }

    let keyPointsContent = data.key_points || "";
    if (!keyPointsContent && chronicleContent && typeof extractKeyPointsFromMarkdown === "function") {
      keyPointsContent = extractKeyPointsFromMarkdown(chronicleContent);
    }
    const keyPointsEl = document.getElementById("keyPointsView");
    if (keyPointsEl) {
      if (keyPointsContent) {
        keyPointsEl.innerHTML = `
          <div class="space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div class="flex items-center gap-2 text-xs text-slate-300">
                <span class="text-base"><span data-ui-icon=book aria-hidden=true></span></span>
                <span class="font-semibold text-sky-300">Glosario & Técnicas Clave</span>
              </div>
              <div class="flex items-center gap-2">
                <input type="text" placeholder=" Buscar término..." oninput="filterGlossaryItemsInContainer(this.value, 'keyPointsItemsContainer')"
                  class="px-2.5 py-1 text-xs rounded-lg bg-slate-950 border border-slate-700 text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none w-44 sm:w-56">
                <button type="button" onclick="openAddGlossaryModal()"
                  class="px-3 py-1 rounded-lg bg-sky-600/30 hover:bg-sky-600/50 text-sky-200 border border-sky-500/40 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer">
                  <span><span data-ui-icon=plus aria-hidden=true></span></span> <span>Agregar Término</span>
                </button>
              </div>
            </div>
            <div id="keyPointsItemsContainer" class="prose-dnd text-slate-300 text-xs sm:text-sm leading-relaxed overflow-x-auto space-y-3 font-sans">
              ${renderMarkdownWithKaTeX(keyPointsContent)}
            </div>
          </div>
        `;
      } else {
        keyPointsEl.innerHTML = `<p class="italic text-slate-500 text-xs p-6 text-center">No hay glosario ni puntos clave disponibles para esta sesión.</p>`;
      }
    }
  }

  toggleResultTab("chronicle");

  const transcriptEl = document.getElementById("transcriptView");
  let transcriptContent = document.getElementById("transcript-content");
  if (!transcriptContent && transcriptEl) {
    transcriptEl.innerHTML = '<div id="transcript-content" class="space-y-2"></div>';
    transcriptContent = document.getElementById("transcript-content");
  } else if (transcriptContent) {
    transcriptContent.innerHTML = "";
  }

  if (transcriptContent) {
    if (data.segments && data.segments.length > 0) {
      data.segments.forEach(seg => {
        const div = document.createElement("div");
        div.className = "flex items-start gap-3 py-1.5 border-b border-slate-900/60";
        let speakerBadge = "";
        if (seg.speaker) {
          const isUser = seg.speaker.includes("[TÚ");
          const badgeClass = isUser 
            ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold" 
            : "bg-slate-800 text-slate-400 border border-slate-700 font-medium";
          speakerBadge = `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] ${badgeClass} shrink-0 font-mono">${escapeHtml(seg.speaker)}</span>`;
        }
        div.innerHTML = `
          <span class="text-indigo-400 select-none shrink-0 font-mono text-xs">[${formatSeconds(seg.start)} - ${formatSeconds(seg.end)}]</span>
          ${speakerBadge}
          <span class="text-slate-300 leading-relaxed text-xs font-mono">${escapeHtml(seg.text)}</span>
        `;
        transcriptContent.appendChild(div);
      });
    } else if (data.raw_transcript || data.transcript || data.text) {
      transcriptContent.innerHTML = renderTranscriptText(data.raw_transcript || data.transcript || data.text);
    }
  }

  const driveBanner = document.getElementById("driveResultBanner");
  if (driveBanner) driveBanner.classList.add("hidden");

  const btnDownloadAudio = document.getElementById("btnDownloadAudio");
  if (btnDownloadAudio) {
    if (data.wav_filename) {
      btnDownloadAudio.classList.remove("hidden");
    } else {
      btnDownloadAudio.classList.add("hidden");
    }
  }

  const btnDeleteAudio = document.getElementById("btnDeleteOriginalAudio");
  const btnDeleteAudioText = document.getElementById("btnDeleteOriginalAudioText");
  if (btnDeleteAudio) {
    if (data.wav_filename) {
      btnDeleteAudio.classList.remove("hidden");
      btnDeleteAudio.disabled = false;
      if (btnDeleteAudioText) btnDeleteAudioText.textContent = "Eliminar audio original";
    } else {
      btnDeleteAudio.classList.add("hidden");
    }
  }

  const resultsCard = document.getElementById("resultsCard");
  if (resultsCard) {
    resultsCard.classList.remove("hidden");
    if (document.getElementById("viewChronicle")) setActiveView("chronicle");
    resultsCard.scrollIntoView({ behavior: "smooth" });
  }
  if (typeof fetchApiQuota === "function") fetchApiQuota();
  if (isClassMode && typeof loadAcademicNotesHistory === "function") {
    loadAcademicNotesHistory(false);
  }
}

function showResults(data) {
  return displayResults(data);
}

function syncResultTabsForWorkspace(mode = null) {
  const isWork = mode ? (mode === "class" || mode === "work_and_study") : (currentWorkspace === "work_and_study");

  const btnChronicle = document.getElementById("viewChronicleBtn");
  const txtChronicle = document.getElementById("viewChronicleText");
  const iconChronicle = document.getElementById("viewChronicleIcon");

  const btnKeyPoints = document.getElementById("viewKeyPointsBtn");
  const txtKeyPoints = document.getElementById("viewKeyPointsText");
  const iconKeyPoints = document.getElementById("viewKeyPointsIcon");

  const btnQuests = document.getElementById("viewQuestsBtn");
  const txtQuests = document.getElementById("viewQuestsText");
  const iconQuests = document.getElementById("viewQuestsIcon");

  const btnNpcs = document.getElementById("viewNpcsBtn");
  const btnPcs = document.getElementById("viewPcsBtn");
  const btnJournal = document.getElementById("viewJournalBtn");
  const btnTranscript = document.getElementById("viewTranscriptBtn");

  const questsViewTitle = document.getElementById("questsViewTitle");
  const questsViewIcon = document.getElementById("questsViewIcon");
  const questsViewHeading = document.getElementById("questsViewHeading");
  const questsViewSubtitle = document.getElementById("questsViewSubtitle");

  if (isWork) {
    if (btnChronicle) { btnChronicle.classList.remove("hidden"); btnChronicle.style.display = ""; }
    if (txtChronicle) txtChronicle.textContent = "Resumen y apuntes";
    if (iconChronicle) WhisperIcons.set(iconChronicle, "file");

    if (btnKeyPoints) { btnKeyPoints.classList.remove("hidden"); btnKeyPoints.style.display = ""; }
    if (txtKeyPoints) txtKeyPoints.textContent = "Puntos Clave y Glosario";
    if (iconKeyPoints) WhisperIcons.set(iconKeyPoints, "star");

    if (btnQuests) { btnQuests.classList.remove("hidden"); btnQuests.style.display = ""; }
    if (txtQuests) txtQuests.textContent = "Tareas y Encargos";
    if (iconQuests) WhisperIcons.set(iconQuests, "check");

    if (btnTranscript) { btnTranscript.classList.remove("hidden"); btnTranscript.style.display = ""; }

    if (btnNpcs) { btnNpcs.classList.add("hidden"); btnNpcs.style.display = "none"; }
    if (btnPcs) { btnPcs.classList.add("hidden"); btnPcs.style.display = "none"; }
    if (btnJournal) { btnJournal.classList.add("hidden"); btnJournal.style.display = "none"; }

    if (questsViewHeading) questsViewHeading.textContent = "Tareas y Encargos";
    if (questsViewIcon) WhisperIcons.set(questsViewIcon, "check");
    if (questsViewSubtitle) questsViewSubtitle.textContent = "Action items y pendientes extraídos de la sesión";
    if (questsViewTitle) questsViewTitle.className = "text-sm font-bold text-sky-300 font-sans flex items-center gap-2";

    if (["npcs", "pcs", "journal"].includes(currentActiveResultTab)) {
      toggleResultTab("chronicle");
    }
  } else {
    if (btnChronicle) { btnChronicle.classList.remove("hidden"); btnChronicle.style.display = ""; }
    if (txtChronicle) txtChronicle.textContent = "Crónica";
    if (iconChronicle) WhisperIcons.set(iconChronicle, "book");

    if (btnQuests) { btnQuests.classList.remove("hidden"); btnQuests.style.display = ""; }
    if (txtQuests) txtQuests.textContent = "Misiones";
    if (iconQuests) WhisperIcons.set(iconQuests, "map");

    if (btnNpcs) { btnNpcs.classList.remove("hidden"); btnNpcs.style.display = ""; }
    if (btnPcs) { btnPcs.classList.remove("hidden"); btnPcs.style.display = ""; }
    if (btnJournal) { btnJournal.classList.remove("hidden"); btnJournal.style.display = ""; }
    if (btnTranscript) { btnTranscript.classList.remove("hidden"); btnTranscript.style.display = ""; }

    if (btnKeyPoints) { btnKeyPoints.classList.add("hidden"); btnKeyPoints.style.display = "none"; }

    if (questsViewHeading) questsViewHeading.textContent = "Registro Maestro de Misiones (Master Quest Log)";
    if (questsViewIcon) WhisperIcons.set(questsViewIcon, "map");
    if (questsViewSubtitle) questsViewSubtitle.textContent = "Marca los sub-objetivos conforme la mesa avance";
    if (questsViewTitle) questsViewTitle.className = "text-sm font-bold text-amber-300 font-fantasy flex items-center gap-2";

    if (currentActiveResultTab === "keypoints") {
      toggleResultTab("chronicle");
    }
  }
}

function toggleResultTab(tab) {
  const isWork = (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class"));
  if (isWork && ["npcs", "pcs", "journal"].includes(tab)) {
    tab = "chronicle";
  } else if (!isWork && tab === "keypoints") {
    tab = "chronicle";
  }

  currentActiveResultTab = tab;
  const views = {
    chronicle: document.getElementById("chronicleView"),
    keypoints: document.getElementById("keyPointsView"),
    quests: document.getElementById("questsView"),
    npcs: document.getElementById("npcsView"),
    pcs: document.getElementById("pcsView"),
    journal: document.getElementById("journalView"),
    transcript: document.getElementById("transcriptView"),
  };
  const buttons = {
    chronicle: document.getElementById("viewChronicleBtn"),
    keypoints: document.getElementById("viewKeyPointsBtn"),
    quests: document.getElementById("viewQuestsBtn"),
    npcs: document.getElementById("viewNpcsBtn"),
    pcs: document.getElementById("viewPcsBtn"),
    journal: document.getElementById("viewJournalBtn"),
    transcript: document.getElementById("viewTranscriptBtn"),
  };

  const activeClass = "px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white font-semibold transition flex items-center gap-1.5";
  const inactiveClass = "px-3.5 py-1.5 rounded-lg bg-slate-950 text-slate-400 hover:text-slate-200 font-medium transition flex items-center gap-1.5 border border-slate-800";

  Object.keys(views).forEach(k => {
    const v = views[k];
    const b = buttons[k];
    const isForbidden = isWork ? ["npcs", "pcs", "journal"].includes(k) : (k === "keypoints");

    if (isForbidden) {
      if (b) {
        b.classList.add("hidden");
        b.style.display = "none";
      }
      if (v) {
        v.classList.add("hidden");
        v.style.display = "none";
      }
      return;
    }

    if (b) {
      b.classList.remove("hidden");
      b.style.display = "";
    }
    if (v) {
      v.style.display = "";
    }

    if (k === tab) {
      if (v) v.classList.remove("hidden");
      if (b) b.className = activeClass;
      if (isWork && k === "quests" && typeof renderAcademicTasks === "function") {
        renderAcademicTasks(currentAcademicTasks || []);
      }
    } else {
      if (v) v.classList.add("hidden");
      if (b) b.className = inactiveClass;
    }
  });
}

function updateCampaignViewTabs(state) {
  if (!state) return;
  if (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class")) {
    return;
  }
  const quests = state.quests || [];
  const npcs = state.npcs || [];
  const universalPcs = (state.universal_pcs && state.universal_pcs.length > 0)
    ? state.universal_pcs
    : (state.pcs && state.pcs.length > 0 ? state.pcs : (state.detected_pcs || state.roster || []));

  const qBadge = document.getElementById("questCountBadge");
  if (qBadge) qBadge.textContent = quests.filter(q => q.status !== "completed").length;
  const nBadge = document.getElementById("npcCountBadge");
  if (nBadge) nBadge.textContent = npcs.length;
  const pBadge = document.getElementById("pcCountBadge");
  if (pBadge) pBadge.textContent = universalPcs.length;

  if (typeof renderQuests === "function") renderQuests(quests);
  if (typeof renderNpcs === "function") renderNpcs(npcs);
  if (typeof renderUniversalPcs === "function") renderUniversalPcs(universalPcs);
  if (typeof renderJournal === "function") renderJournal(state);
}

// =========================================================================
// EXPORTS & DOWNLOADS
// =========================================================================
function downloadSessionDocx(sessionNum = null, cleanMode = false) {
  if (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class")) {
    downloadCampaignDocx();
    return;
  }
  const wikiSel = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (currentResult && currentResult.campaign_name) ||
                   (wikiSel && wikiSel.value && wikiSel.value.trim()) ||
                   (campInput && campInput.value && campInput.value.trim());

  if (!campName) {
    showAlert("No hay campaña seleccionada para descargar la sesión.");
    return;
  }

  let num = sessionNum;
  if (!num) {
    if (currentResult && currentResult.session_number) {
      num = currentResult.session_number;
    } else {
      const sessInput = document.getElementById("sessionNumberInput");
      num = (sessInput && sessInput.value) ? parseInt(sessInput.value) : 1;
    }
  }

  const includeCoaching = !cleanMode;
  navigateToDownload(`/api/campaigns/${encodeURIComponent(campName)}/session/${encodeURIComponent(num)}/download-docx?include_coaching=${includeCoaching}`);
}

function downloadSessionMd(sessionNum = null, cleanMode = false) {
  if (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class")) {
    downloadCampaignMd();
    return;
  }
  const wikiSel = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (currentResult && currentResult.campaign_name) ||
                   (wikiSel && wikiSel.value && wikiSel.value.trim()) ||
                   (campInput && campInput.value && campInput.value.trim());

  if (!campName) {
    showAlert("No hay campaña seleccionada para descargar la sesión.");
    return;
  }

  let num = sessionNum;
  if (!num) {
    if (currentResult && currentResult.session_number) {
      num = currentResult.session_number;
    } else {
      const sessInput = document.getElementById("sessionNumberInput");
      num = (sessInput && sessInput.value) ? parseInt(sessInput.value) : 1;
    }
  }

  const includeCoaching = !cleanMode;
  navigateToDownload(`/api/campaigns/${encodeURIComponent(campName)}/session/${encodeURIComponent(num)}/download-md?include_coaching=${includeCoaching}`);
}

function toggleAiToolsMenu() {
  const menu = document.getElementById("aiToolsDropdown");
  if (!menu) return;
  menu.classList.toggle("hidden");
}

function closeAiToolsMenu() {
  const menu = document.getElementById("aiToolsDropdown");
  if (menu) menu.classList.add("hidden");
}

document.addEventListener("click", (e) => {
  const container = document.getElementById("aiToolsMenuContainer");
  if (container && !container.contains(e.target)) {
    closeAiToolsMenu();
  }
});

window.downloadSessionDocx = downloadSessionDocx;
window.downloadSessionMd = downloadSessionMd;
window.toggleAiToolsMenu = toggleAiToolsMenu;
window.closeAiToolsMenu = closeAiToolsMenu;

function downloadCampaignDocx() {
  if (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class")) {
    const file = (currentResult && (currentResult.docx_filename || currentResult.md_filename)) || "apuntes.docx";
    const docxName = file.endsWith(".docx") ? file : file.replace(/\.md$/, ".docx");
    navigateToDownload(`/api/academic-notes/download/${encodeURIComponent(docxName)}`);
    return;
  }
  const wikiSel = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (wikiSel && wikiSel.value && wikiSel.value.trim()) || (campInput && campInput.value && campInput.value.trim());
  if (!campName) {
    showAlert("Selecciona o abre una campaña para descargar el documento.");
    return;
  }
  navigateToDownload(`/api/campaigns/${encodeURIComponent(campName)}/download-docx`);
}

function downloadCampaignMd() {
  const wikiSel = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (wikiSel && wikiSel.value && wikiSel.value.trim()) || (campInput && campInput.value && campInput.value.trim());
  if (!campName) {
    showAlert("Selecciona o abre una campaña para descargar el documento.");
    return;
  }
  navigateToDownload(`/api/campaigns/${encodeURIComponent(campName)}/download-md`);
}

function exportCampaignByName(campName) {
  const name = (campName || "").trim();
  if (!name) {
    showAlert("Por favor especifica el nombre de la campaña a exportar.");
    return;
  }
  showInfoAlert(`Generando paquete ZIP para '${name}' con todas sus sesiones, wiki y roster...`);
  const link = document.createElement("a");
  link.href = `/api/campaigns/${encodeURIComponent(name)}/export`;
  link.setAttribute("download", "");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => {
    showSuccessAlert(`Descarga de la campaña '${name}' iniciada.`);
  }, 1000);
}

function exportCurrentCampaign() {
  const campInput = document.getElementById("campaignNameInput");
  const name = campInput ? campInput.value.trim() : "";
  if (!name) {
    showAlert("Selecciona o escribe el nombre de una campaña antes de exportar.");
    if (campInput) campInput.focus();
    return;
  }
  exportCampaignByName(name);
}

function exportCurrentCampaignFromWiki() {
  const select = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const name = (select && select.value.trim()) || (campInput && campInput.value.trim());
  if (!name) {
    showAlert("Selecciona una campaña en el selector superior para exportarla.");
    return;
  }
  exportCampaignByName(name);
}

function triggerImportCampaign() {
  const fileInput = document.getElementById("campaignImportFileInput");
  if (fileInput) {
    fileInput.value = "";
    fileInput.click();
  }
}

async function handleCampaignImportFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".zip") && !lowerName.endsWith(".json")) {
    showAlert("Formato no compatible. Por favor sube un archivo .zip o .json de campaña.");
    return;
  }

  showInfoAlert(`Importando campaña desde '${file.name}' al servidor...`);
  const importBtn = document.getElementById("btnImportCampaign");
  const origText = importBtn ? importBtn.innerHTML : "";
  if (importBtn) {
    importBtn.disabled = true;
    importBtn.innerHTML = `<span class="inline-block animate-spin"><span data-ui-icon=clock aria-hidden=true></span></span><span>Importando...</span>`;
  }

  try {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/campaigns/import", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok || data.status === "error") {
      throw new Error(data.message || data.detail || "Error al importar la campaña.");
    }

    showSuccessAlert(data.message || `Campaña '${data.campaign_name}' importada con éxito.`);

    const campInput = document.getElementById("campaignNameInput");
    if (campInput && data.campaign_name) {
      campInput.value = data.campaign_name;
    }

    const campaigns = await loadCampaignList();

    const modal = document.getElementById("campaignManagerModal");
    if (modal && !modal.classList.contains("hidden") && typeof renderCampaignManagerList === "function") {
      renderCampaignManagerList(campaigns);
    }

    await onCampaignChange();
    await loadCurrentCampaign();
    if (typeof refreshWikiCampaigns === "function") {
      await refreshWikiCampaigns();
      const wikiSelect = document.getElementById("wikiCampaignSelect");
      if (wikiSelect && data.campaign_name) {
        wikiSelect.value = data.campaign_name;
        if (typeof onWikiCampaignSelected === "function") {
          onWikiCampaignSelected(data.campaign_name);
        }
      }
    }
  } catch (err) {
    console.error("Import campaign error:", err);
    showAlert("Error al importar la campaña: " + err.message);
  } finally {
    if (importBtn) {
      importBtn.disabled = false;
      importBtn.innerHTML = origText;
    }
    event.target.value = "";
  }
}

function downloadTranscriptTxt() {
  if (currentResult && currentResult.txt_filename) {
    navigateToDownload(`/api/download/transcript/${encodeURIComponent(currentResult.txt_filename)}`);
    return;
  }
  const campName = (currentResult && currentResult.campaign_name) || (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) {
    showAlert("No hay campaña seleccionada para descargar la transcripción.");
    return;
  }
  const sessNum = (currentResult && currentResult.session_number) ? currentResult.session_number : (parseInt(document.getElementById("sessionNumberInput")?.value) || 1);
  const safeCamp = campName.toLowerCase().replace(/[^a-z0-9_]/g, "_");
  const defaultName = `${safeCamp}_sesion_${sessNum}_transcripcion.txt`;
  navigateToDownload(`/api/download/transcript/${encodeURIComponent(defaultName)}`);
}

function downloadAudioFile() {
  if (currentResult && currentResult.wav_filename) {
    navigateToDownload(`/api/download/audio/${encodeURIComponent(currentResult.wav_filename)}`);
    return;
  }
  showAlert("No hay archivo de audio original disponible para descargar.");
}

async function deleteOriginalAudio() {
  if (!currentResult || !currentResult.wav_filename) {
    showAlert("No hay audio original asociado a esta sesión.");
    return;
  }
  const filename = currentResult.wav_filename;
  if (!confirm(`¿Estás seguro de que deseas eliminar el archivo de audio original en disco ("${filename}") para liberar espacio? Esta acción no se puede deshacer.`)) {
    return;
  }

  const btn = document.getElementById("btnDeleteOriginalAudio");
  const btnText = document.getElementById("btnDeleteOriginalAudioText");
  if (btn) {
    btn.disabled = true;
    if (btnText) btnText.textContent = "Eliminando...";
  }

  try {
    const res = await fetch("/api/record/delete-audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: filename })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al eliminar el audio.");

    showAlert(data.message || "Audio original eliminado con éxito.");
    currentResult.wav_filename = null;
    const btnDlAudio = document.getElementById("btnDownloadAudio");
    if (btnDlAudio) btnDlAudio.classList.add("hidden");
    if (btn) {
      if (btnText) btnText.textContent = "Audio eliminado";
      setTimeout(() => {
        btn.classList.add("hidden");
      }, 2000);
    }
  } catch (err) {
    showAlert("Error al eliminar audio: " + err.message);
    if (btn) {
      btn.disabled = false;
      if (btnText) btnText.textContent = "Eliminar audio original";
    }
  }
}

function renderTranscriptText(text) {
  if (!text || !text.trim()) {
    return '<p class="text-slate-500 italic p-3 text-xs">No hay texto de transcripción registrado para esta sesión.</p>';
  }
  const lines = text.split("\n");
  return lines.map(line => {
    if (!line.trim()) return '<div class="py-1"></div>';
    let formattedLine = escapeHtml(line);
    formattedLine = formattedLine.replace(
      /(\[\d{2}:\d{2}:\d{2}\s*(?:->|-)\s*\d{2}:\d{2}:\d{2}\])/g,
      '<span class="text-slate-400 font-mono select-none text-xs shrink-0">$1</span>'
    );
    formattedLine = formattedLine.replace(
      /(\[T[uú](?:\s*\/\s*[^\]]+)?\])/gi,
      '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">$1</span>'
    );
    formattedLine = formattedLine.replace(
      /(\[(?:Discord(?:\s*\/\s*Mesa)?|[A-Za-z0-9_.\- ()áéíóúÁÉÍÓÚñÑ]+)\])(?!\s*<\/span>)/g,
      (match) => {
        if (match.includes("font-mono") || match.includes("px-1.5")) return match;
        return `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono">${match}</span>`;
      }
    );
    return `<div class="py-1 border-b border-slate-900/60 text-slate-300 leading-relaxed text-xs font-mono flex flex-wrap items-center gap-2">${formattedLine}</div>`;
  }).join("");
}

function confirmKeepTranscript() {
  const promptEl = document.getElementById("transcriptRetentionPrompt");
  if (promptEl) promptEl.classList.add("hidden");
}

async function confirmDiscardTranscript() {
  const promptEl = document.getElementById("transcriptRetentionPrompt");
  if (!currentResult) return;
  try {
    const payload = {
      filename: currentResult.txt_filename || currentResult.transcript_filename || (currentResult.file_path ? currentResult.file_path.replace(/\.[^/.]+$/, ".txt") : null),
      campaign_name: currentResult.campaign_name,
      session_number: currentResult.session_number,
      note_filename: currentResult.md_filename
    };
    const res = await fetch("/api/transcription/discard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showSuccessAlert("Transcripción en bruto descartada correctamente. Los apuntes estructurados se mantienen intactos.");
      if (promptEl) promptEl.classList.add("hidden");
      const txtBtn = document.getElementById("btnDownloadTxt");
      if (txtBtn) txtBtn.classList.add("hidden");
    } else {
      const errData = await res.json();
      showAlert("Error al descartar la transcripción: " + (errData.detail || "Error desconocido"));
    }
  } catch (e) {
    console.error("Error discarding transcription:", e);
    showAlert("Error al descartar la transcripción.");
  }
}

function copyCurrentContent() {
  let textToCopy = "";
  if (currentActiveResultTab === "chronicle") {
    const chronicleEl = document.getElementById("chronicleView");
    textToCopy = chronicleEl ? chronicleEl.innerText : (currentResult ? (currentResult.chronicle || "") : "");
  } else if (currentActiveResultTab === "keypoints") {
    const keyPointsEl = document.getElementById("keyPointsView");
    textToCopy = keyPointsEl ? keyPointsEl.innerText : "";
  } else if (currentActiveResultTab === "quests") {
    const questsEl = document.getElementById("questsContainer");
    textToCopy = questsEl ? questsEl.innerText : "";
  } else if (currentActiveResultTab === "journal") {
    const grimorioEl = document.getElementById("grimorio-content");
    textToCopy = grimorioEl ? grimorioEl.innerText : document.getElementById("journalView")?.innerText || "";
  } else if (currentActiveResultTab === "transcript") {
    const transContent = document.getElementById("transcript-content");
    textToCopy = currentResult ? (currentResult.raw_transcript || currentResult.transcript || currentResult.text || (transContent ? transContent.innerText : "")) : (transContent ? transContent.innerText : "");
  } else {
    textToCopy = (currentResult && currentResult.chronicle) ? currentResult.chronicle : "";
  }

  navigator.clipboard.writeText(textToCopy).then(() => {
    const label = document.getElementById("copyBtnText");
    if (label) {
      label.textContent = "¡Copiado!";
      setTimeout(() => { label.textContent = "Copiar"; }, 2000);
    }
  });
}

async function switchSummaryLanguage() {
  if (!currentResult) {
    showAlert("No hay ningún resumen activo para cambiar de idioma.");
    return;
  }
  const transcriptText = currentResult.transcript || currentResult.text || "";
  if (!transcriptText) {
    showAlert("No se encontró el texto de la transcripción para traducir.");
    return;
  }

  const activeLang = (currentResult.target_language || currentTargetLanguage || "es").toLowerCase();
  const newLang = activeLang.startsWith("en") ? "es" : "en";

  const btn = document.getElementById("btnSwitchLanguage");
  const btnText = document.getElementById("btnSwitchLanguageText");
  if (btn) btn.disabled = true;
  if (btnText) btnText.innerHTML = `<span class="inline-block animate-spin"><span data-ui-icon=clock aria-hidden=true></span></span> Cambiando idioma...`;

  try {
    const isClass = (currentResult.recording_mode === "class" || currentLiveMode === "class");
    const campName = isClass ? null : ((currentResult.campaign_name || document.getElementById("campaignNameInput")?.value || "").trim());
    if (!isClass && !campName) {
      showAlert("Debes seleccionar o crear una campaña antes de cambiar el idioma.");
      return;
    }
    const payload = {
      transcript_text: transcriptText,
      target_language: newLang,
      recording_mode: isClass ? "class" : "roleplay",
      campaign_name: campName,
      session_number: isClass ? null : (currentResult.session_number || parseInt(document.getElementById("sessionNumberInput")?.value) || null),
      roster: isClass ? [] : (currentResult.roster || (typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [])),
      subject: isClass ? (currentResult.subject || document.getElementById("lectureSubjectInput")?.value.trim() || "") : "",
      topic: isClass ? (currentResult.topic || document.getElementById("lectureTopicInput")?.value.trim() || "") : "",
      custom_date: (document.getElementById("workStudyDateInput") ? document.getElementById("workStudyDateInput").value.trim() : "") || null,
      client_timezone_offset: new Date().getTimezoneOffset(),
    };

    const res = await fetch("/api/summarize/switch-language", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getUserApiHeaders()
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (checkAuthErrorAndRedirect(res.status, data)) {
      throw new Error("Credenciales de API requeridas.");
    }
    if (!res.ok) throw new Error(data.detail || "Error al cambiar el idioma del resumen.");

    currentTargetLanguage = newLang;
    setTargetLanguage(newLang);
    currentResult.chronicle = data.chronicle;
    currentResult.target_language = newLang;
    if (data.docx_filename) currentResult.docx_filename = data.docx_filename;
    if (data.md_filename) currentResult.md_filename = data.md_filename;
    if (data.campaign_state) currentResult.campaign_state = data.campaign_state;
    if (data.action_items) currentResult.action_items = data.action_items;
    if (data.key_points) currentResult.key_points = data.key_points;
    if (data.recording_mode) currentResult.recording_mode = data.recording_mode;

    displayResults(currentResult);
  } catch (err) {
    showAlert("Error al cambiar idioma: " + err.message);
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) {
      const langUpper = currentTargetLanguage.toUpperCase();
      btnText.textContent = langUpper.startsWith("EN") ? "Cambiar a Español (ES)" : "Cambiar a Inglés (EN)";
    }
  }
}

async function reprocessCampaignChronicle() {
  if (!currentResult) {
    showAlert("No hay resultados cargados para procesar.");
    return;
  }
  const transcriptText = currentResult.text || currentResult.transcript;
  if (!transcriptText || !transcriptText.trim()) {
    showAlert("No hay transcripción disponible para regenerar la crónica.");
    return;
  }

  if (typeof checkQuotaBeforeAction === "function") {
    const quotaOk = await checkQuotaBeforeAction("la regeneración de la crónica con Gemini");
    if (!quotaOk) return;
  }

  const isClass = (currentResult.recording_mode === "class" || currentLiveMode === "class" || currentWorkspace === "work_and_study");
  if (typeof updateStepperMode === "function") updateStepperMode(false);
  const btn = document.getElementById("btnReprocessCampaign");
  const btnText = document.getElementById("btnReprocessCampaignText");
  if (btn) btn.disabled = true;
  if (btnText) btnText.innerHTML = `<span class="inline-block animate-spin"><span data-ui-icon=clock aria-hidden=true></span></span> Regenerando con Gemini...`;

  try {
    const activeLang = currentResult.target_language || currentTargetLanguage || "es";
    const campName = isClass ? null : ((currentResult.campaign_name || document.getElementById("campaignNameInput")?.value || "").trim());
    if (!isClass && !campName) {
      showAlert("Debes seleccionar o crear una campaña antes de regenerar la crónica.");
      return;
    }
    const payload = {
      transcript_text: transcriptText,
      target_language: activeLang,
      recording_mode: isClass ? "class" : "roleplay",
      workspace: isClass ? "work_and_study" : "dnd",
      is_youtube: currentActiveMainTab === "youtube" || !!currentResult.is_youtube,
      campaign_name: campName,
      session_number: isClass ? null : (currentResult.session_number || parseInt(document.getElementById("sessionNumberInput")?.value) || null),
      roster: isClass ? [] : (currentResult.roster || (typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [])),
      subject: isClass ? (currentResult.subject || document.getElementById("lectureSubjectInput")?.value.trim() || "") : "",
      topic: isClass ? (currentResult.topic || document.getElementById("lectureTopicInput")?.value.trim() || "") : "",
      custom_date: (document.getElementById("workStudyDateInput") ? document.getElementById("workStudyDateInput").value.trim() : "") || null,
      client_timezone_offset: new Date().getTimezoneOffset(),
    };

    if (window.currentActiveAbortController) {
      try { window.currentActiveAbortController.abort(); } catch (_) {}
    }
    window.currentActiveAbortController = new AbortController();

    const res = await fetch("/api/campaign/reprocess", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getUserApiHeaders()
      },
      body: JSON.stringify(payload),
      signal: window.currentActiveAbortController.signal
    });
    const data = await res.json();
    if (checkAuthErrorAndRedirect(res.status, data)) {
      throw new Error("Credenciales de API requeridas.");
    }
    if (!res.ok) throw new Error(data.detail || "Error al regenerar la crónica con Gemini.");

    currentResult.chronicle = data.chronicle;
    if (data.docx_filename) currentResult.docx_filename = data.docx_filename;
    if (data.md_filename) currentResult.md_filename = data.md_filename;
    if (data.file_path) currentResult.file_path = data.file_path;
    if (data.campaign_state) currentResult.campaign_state = data.campaign_state;
    if (data.session_chapter) currentResult.session_chapter = data.session_chapter;
    if (data.detected_pcs) currentResult.detected_pcs = data.detected_pcs;
    if (data.detected_party) currentResult.detected_party = data.detected_party;
    if (data.updated_quests) currentResult.updated_quests = data.updated_quests;
    if (data.updated_npcs) currentResult.updated_npcs = data.updated_npcs;
    if (data.detected_npc_names) currentResult.detected_npc_names = data.detected_npc_names;
    if (data.action_items) currentResult.action_items = data.action_items;
    if (data.key_points) currentResult.key_points = data.key_points;
    if (data.recording_mode) currentResult.recording_mode = data.recording_mode;

    displayResults(currentResult);
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("[reprocessCampaignChronicle] Proceso detenido por el usuario.");
      return;
    }
    showAlert("Error al regenerar crónica: " + err.message);
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) {
      btnText.textContent = isClass ? "Regenerar con Gemini" : "Regenerar con Crónica Profunda (Español)";
    }
  }
}

function exportLivingCampaignToDrive() {
  if (typeof uploadCampaignToDrive === "function") {
    uploadCampaignToDrive();
  }
}

async function uploadCampaignToDrive() {
  const wikiSel = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (wikiSel && wikiSel.value && wikiSel.value.trim()) || (campInput && campInput.value && campInput.value.trim());
  const isWorkStudy = (currentWorkspace === "work_and_study" || (currentResult && currentResult.recording_mode === "class"));
  if (!isWorkStudy && !campName) {
    showAlert("Selecciona o abre una campaña antes de subir a Google Drive.");
    return;
  }
  const btn = document.getElementById("btnExportDrive");
  const btnText = document.getElementById("btnDriveText");
  const banner = document.getElementById("driveResultBanner");
  const link = document.getElementById("driveViewLink");
  const fileNameEl = document.getElementById("driveUploadedFileName");

  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = isWorkStudy ? "Subiendo documento..." : "Subiendo Grimorio...";
  if (banner) banner.classList.add("hidden");

  try {
    let res;
    if (isWorkStudy && currentResult && currentResult.docx_filename) {
      res = await fetch("/api/export/drive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: currentResult.docx_filename })
      });
    } else {
      res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/export-drive`, {
        method: "POST"
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al subir a Google Drive.");

    if (fileNameEl) fileNameEl.textContent = data.file_name;
    if (link) link.href = data.web_view_link;
    if (banner) banner.classList.remove("hidden");
    if (btnText) btnText.textContent = isWorkStudy ? "Documento en Drive" : "Grimorio en Drive";
    setTimeout(() => {
      if (btnText) btnText.textContent = "Subir a Drive";
      if (btn) btn.disabled = false;
    }, 3000);
  } catch (err) {
    showAlert(err.message);
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = "Subir a Drive";
  }
}

// =========================================================================
// PWA & TUNNEL MODALS
// =========================================================================
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const btnInstall = document.getElementById("btnInstallApp");
  if (btnInstall) btnInstall.classList.remove("hidden");
});

window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  const btnInstall = document.getElementById("btnInstallApp");
  if (btnInstall) btnInstall.classList.add("hidden");
  console.log("AudioWorkspace instalado exitosamente como PWA");
});

async function triggerPWAInstall() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    console.log("PWA install outcome:", outcome);
    deferredInstallPrompt = null;
  } else {
    openTunnelModal("pwa");
  }
}

function openTunnelModal(section = 'tunnel') {
  const modal = document.getElementById("tunnelModal");
  const box = document.getElementById("tunnelModalBox");
  if (!modal || !box) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  modal.style.pointerEvents = "auto";
  box.style.pointerEvents = "auto";
  requestAnimationFrame(() => {
    modal.classList.remove("opacity-0", "pointer-events-none");
    modal.classList.add("opacity-100", "pointer-events-auto");
    box.classList.remove("scale-95");
    box.classList.add("scale-100");
  });
  if (section === 'pwa') {
    setTimeout(() => {
      const pwaSection = document.getElementById("tunnelModalPwaSection");
      if (pwaSection) pwaSection.scrollIntoView({ behavior: 'smooth' });
    }, 160);
  }
}

function closeTunnelModal() {
  const modal = document.getElementById("tunnelModal");
  const box = document.getElementById("tunnelModalBox");
  if (!modal || !box) return;
  modal.style.pointerEvents = "none";
  modal.classList.remove("opacity-100", "pointer-events-auto");
  modal.classList.add("opacity-0", "pointer-events-none");
  box.classList.remove("scale-100");
  box.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }, 150);
}

function copyTunnelCmd(elementId, btnElement) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    const originalContent = btnElement.innerHTML;
    btnElement.innerHTML = `<svg class="w-3.5 h-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> <span class="text-emerald-400 font-bold">¡Copiado!</span>`;
    setTimeout(() => {
      btnElement.innerHTML = originalContent;
    }, 2000);
  }).catch(() => {
    prompt("Copia este comando:", text);
  });
}

function toggleSystemStatusPopover() {
  setActiveView('settings');
}

function openDiscordBridgeModal() {
  const campInput = document.getElementById("campaignSelect") || document.getElementById("campaignNameInput");
  const cName = (campInput && campInput.value && campInput.value.trim()) ? campInput.value.trim() : "NombreDeTuCampaña";
  const codeEl = document.getElementById("bridgeCmdCode");
  if (codeEl) {
    codeEl.textContent = `python -m client_bridge.discord_bridge --campaign "${cName}"`;
  }
  const modal = document.getElementById("discordBridgeModal");
  const box = document.getElementById("discordBridgeModalBox");
  if (!modal || !box) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  requestAnimationFrame(() => {
    modal.classList.remove("opacity-0", "pointer-events-none");
    modal.classList.add("opacity-100", "pointer-events-auto");
    box.classList.remove("scale-95");
    box.classList.add("scale-100");
  });
}

function closeDiscordBridgeModal() {
  const modal = document.getElementById("discordBridgeModal");
  const box = document.getElementById("discordBridgeModalBox");
  if (!modal || !box) return;
  modal.classList.remove("opacity-100", "pointer-events-auto");
  modal.classList.add("opacity-0", "pointer-events-none");
  box.classList.remove("scale-100");
  box.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }, 150);
}

// =========================================================================
// LISTENER GLOBAL DE ESCAPE: Cierra cualquier modal abierto
// =========================================================================
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" || e.key === "Esc") {
    const errorCard = document.getElementById("errorCard");
    if (errorCard && !errorCard.classList.contains("hidden")) {
      if (typeof hideErrorCard === "function") {
        hideErrorCard();
      } else {
        errorCard.classList.add("hidden");
        errorCard.classList.remove("flex");
      }
    }
    const campaignModal = document.getElementById("campaignManagerModal");
    if (campaignModal && !campaignModal.classList.contains("hidden")) {
      toggleCampaignManagerModal(false);
    }
    const mergeModal = document.getElementById("mergeEntityModal");
    if (mergeModal && !mergeModal.classList.contains("hidden")) {
      toggleMergeEntityModal(false);
    }
    const tunnelModal = document.getElementById("tunnelModal");
    if (tunnelModal && !tunnelModal.classList.contains("hidden")) {
      closeTunnelModal();
    }
    const backupModal = document.getElementById("backupFallbackModal");
    if (backupModal && !backupModal.classList.contains("hidden")) {
      if (typeof closeBackupFallbackModal === "function") closeBackupFallbackModal();
    }
    const glossaryModal = document.getElementById("modalAddGlossaryTerm");
    if (glossaryModal && !glossaryModal.classList.contains("hidden")) {
      if (typeof closeAddGlossaryModal === "function") closeAddGlossaryModal();
    }
    const bridgeModal = document.getElementById("discordBridgeModal");
    if (bridgeModal && !bridgeModal.classList.contains("hidden")) {
      closeDiscordBridgeModal();
    }
  }
});

function copyBridgeCmd() {
  const el = document.getElementById("bridgeCmdCode");
  const btnText = document.getElementById("bridgeCopyBtnText");
  if (!el) return;
  const text = el.textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    if (btnText) {
      const original = btnText.textContent;
      btnText.textContent = "¡Copiado!";
      setTimeout(() => { btnText.textContent = original; }, 2000);
    }
  }).catch(() => {
    prompt("Copia este comando:", text);
  });
}

function onSettingsMicChange(val) {
  const selectAudioMic = document.getElementById("selectAudioMic");
  if (selectAudioMic) {
    selectAudioMic.value = val;
    if (typeof onAudioDeviceChange === "function") {
      onAudioDeviceChange();
    }
  }
  localStorage.setItem("dnd_selected_mic", val);
}

function onSettingsSpeakerChange(val) {
  const selectAudioSpeaker = document.getElementById("selectAudioSpeaker");
  if (selectAudioSpeaker) {
    selectAudioSpeaker.value = val;
    if (typeof onAudioDeviceChange === "function") {
      onAudioDeviceChange();
    }
  }
  localStorage.setItem("dnd_selected_speaker", val);
}

// =========================================================================
// SHUTDOWN BEACON & LIFECYCLE
// =========================================================================
window.addEventListener("keydown", (e) => {
  if (e.key === "F5" || (e.ctrlKey && (e.key === "r" || e.key === "R"))) {
    _isPageNavigatingOrReloading = true;
    setTimeout(() => { _isPageNavigatingOrReloading = false; }, 4000);
  }
});

window.addEventListener("click", (e) => {
  const target = e.target.closest("a, button");
  if (target) {
    const text = (target.innerText || target.textContent || "").toLowerCase();
    if (text.includes("descargar") || text.includes("export") || text.includes("conectar") || target.tagName === "A") {
      _isPageNavigatingOrReloading = true;
      setTimeout(() => { _isPageNavigatingOrReloading = false; }, 5000);
    }
  }
}, true);

function triggerServerShutdownBeacon() {
  // Deshabilitado por defecto para evitar que recargas de página, redirecciones OAuth
  // o cierres de pestaña en otras computadoras maten el proceso del servidor web.
  return;
}

window.addEventListener("beforeunload", (e) => {
  const isRecordingActive = !document.getElementById("btnStopRecording")?.disabled;
  if (isRecordingActive) {
    e.preventDefault();
    e.returnValue = "Hay una sesión grabándose actualmente. ¿Seguro que deseas salir?";
    return e.returnValue;
  }
});

// =========================================================================
// BOOTSTRAP INITIALIZATION
// =========================================================================
document.addEventListener("DOMContentLoaded", () => {
  if (typeof initCustomSpeciesList === "function") {
    initCustomSpeciesList();
  }
  initEngineSelector();
  initLanguageSelector();
  if (typeof updateStepperMode === "function") updateStepperMode(false);
  if (typeof loadUserApiKeys === "function") loadUserApiKeys();
  if (typeof checkApiKeysStatus === "function") checkApiKeysStatus();
  if (typeof fetchApiQuota === "function") fetchApiQuota();
  if (typeof checkDriveStatus === "function") checkDriveStatus();
  loadCampaignList();
  if (typeof refreshWikiCampaigns === "function") refreshWikiCampaigns();
  if (typeof initGainSliders === "function") {
    initGainSliders();
  }
  if (typeof loadAcademicNotesHistory === "function") {
    loadAcademicNotesHistory(false);
  }

  const dateInput = document.getElementById("workStudyDateInput");
  if (dateInput && !dateInput.value) {
    dateInput.value = getLocalFormattedDateTime(new Date());
  }

  const topicInput = document.getElementById("workStudyTopicInput");
  if (topicInput) {
    topicInput.addEventListener("input", (e) => {
      const val = e.target.value;
      const subEl = document.getElementById("lectureSubjectInput");
      const topEl = document.getElementById("lectureTopicInput");
      if (subEl) subEl.value = val;
      if (topEl) topEl.value = val;
    });
  }

  setWorkspace(currentWorkspace);

  const campInput = document.getElementById("campaignNameInput");
  const dmInput = document.getElementById("campaignDmInput");
  const savedActiveCamp = localStorage.getItem("last_active_campaign");
  if (currentWorkspace === "dnd") {
    if (savedActiveCamp && campInput) {
      campInput.value = savedActiveCamp;
      onCampaignChange();
    } else if (campInput && campInput.value.trim()) {
      onCampaignChange();
    } else {
      if (campInput) campInput.value = "";
      if (dmInput) dmInput.value = "";
      const sessionInput = document.getElementById("sessionNumberInput");
      if (sessionInput) {
        sessionInput.value = "";
        sessionInput.disabled = true;
        sessionInput.placeholder = "-";
      }
      const overrideCheck = document.getElementById("overrideSessionNumberCheck");
      if (overrideCheck) {
        overrideCheck.checked = false;
        overrideCheck.disabled = true;
      }
      const priorLoreInput = document.getElementById("priorLoreInput");
      if (priorLoreInput) priorLoreInput.value = "";
      const priorBadge = document.getElementById("priorLoreConfiguredBadge");
      if (priorBadge) priorBadge.classList.add("hidden");
      const badge = document.getElementById("campaignLastSessionBadge");
      if (badge) {
        badge.className = "px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700";
        badge.textContent = "Sin Campaña Seleccionada";
      }
    }
  }

  // campaignNameInput already declares input/change handlers in the HTML.

  if (typeof loadAudioDevices === "function") loadAudioDevices();
  if (typeof setAudioSourceMode === "function" && typeof audioSourceMode !== "undefined") setAudioSourceMode(audioSourceMode);
  if (typeof startLiveMeterPolling === "function") startLiveMeterPolling();
  if (typeof checkActiveRecording === "function") checkActiveRecording();
  if (typeof refreshDiscordParticipants === "function") refreshDiscordParticipants(false);
  updateSessionLockForTab("live");

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(reg => console.log('ServiceWorker PWA registrado con éxito en scope:', reg.scope))
        .catch(err => console.warn('Aviso: Registro de ServiceWorker:', err));
    });
  }
});

// Window Global Exports
window.setActiveView = setActiveView;
window.switchView = switchView;
window.setWorkspace = setWorkspace;
window.switchMainTab = switchMainTab;
window.setLiveMode = setLiveMode;
window.initEngineSelector = initEngineSelector;
window.setEngine = setEngine;
window.initLanguageSelector = initLanguageSelector;
window.setTargetLanguage = setTargetLanguage;
window.setLanguage = setLanguage;
window.toggleSessionOverride = toggleSessionOverride;
window.updateSessionLockForTab = updateSessionLockForTab;
window.loadCampaignList = loadCampaignList;
window.toggleCampaignManagerModal = toggleCampaignManagerModal;
window.renderCampaignManagerList = renderCampaignManagerList;
window.selectCampaignFromManager = selectCampaignFromManager;
window.confirmDeleteCampaign = confirmDeleteCampaign;
window.loadCurrentCampaign = loadCurrentCampaign;
window.loadCampaign = loadCurrentCampaign;
window.onSelectHistoricalSession = onSelectHistoricalSession;
window.onCampaignChange = onCampaignChange;
window.saveCurrentCampaignLore = saveCurrentCampaignLore;
window.setRecordingUI = setRecordingUI;
window.startTimer = startTimer;
window.stopTimer = stopTimer;
window.updateTimerDisplay = updateTimerDisplay;
window.transcribeYoutube = transcribeYoutube;
window.handleDragOver = handleDragOver;
window.handleDragLeave = handleDragLeave;
window.handleDrop = handleDrop;
window.handleIncomingFiles = handleIncomingFiles;
window.handleFileSelect = handleIncomingFiles;
window.selectExistingRecording = selectExistingRecording;
window.loadLocalRecordingsList = loadLocalRecordingsList;
window.transcribeFile = transcribeFile;
window.displayResults = displayResults;
window.showResults = showResults;
window.syncResultTabsForWorkspace = syncResultTabsForWorkspace;
window.toggleResultTab = toggleResultTab;
window.updateCampaignViewTabs = updateCampaignViewTabs;
window.downloadCampaignDocx = downloadCampaignDocx;
window.downloadCampaignMd = downloadCampaignMd;
window.exportCampaignByName = exportCampaignByName;
window.exportCurrentCampaign = exportCurrentCampaign;
window.exportCurrentCampaignFromWiki = exportCurrentCampaignFromWiki;
window.triggerImportCampaign = triggerImportCampaign;
window.handleCampaignImportFile = handleCampaignImportFile;
window.downloadTranscriptTxt = downloadTranscriptTxt;
window.downloadAudioFile = downloadAudioFile;
window.deleteOriginalAudio = deleteOriginalAudio;
window.renderTranscriptText = renderTranscriptText;
window.confirmKeepTranscript = confirmKeepTranscript;
window.confirmDiscardTranscript = confirmDiscardTranscript;
window.copyCurrentContent = copyCurrentContent;
window.switchSummaryLanguage = switchSummaryLanguage;
window.reprocessCampaignChronicle = reprocessCampaignChronicle;
window.exportLivingCampaignToDrive = exportLivingCampaignToDrive;
window.uploadCampaignToDrive = uploadCampaignToDrive;
window.triggerPWAInstall = triggerPWAInstall;
window.openTunnelModal = openTunnelModal;
window.closeTunnelModal = closeTunnelModal;
window.copyTunnelCmd = copyTunnelCmd;
window.toggleSystemStatusPopover = toggleSystemStatusPopover;
window.openDiscordBridgeModal = openDiscordBridgeModal;
window.closeDiscordBridgeModal = closeDiscordBridgeModal;
window.copyBridgeCmd = copyBridgeCmd;
window.onSettingsMicChange = onSettingsMicChange;
window.onSettingsSpeakerChange = onSettingsSpeakerChange;
window.triggerServerShutdownBeacon = triggerServerShutdownBeacon;
window.isMobileUser = isMobileUser;
window.isPrivateCampaign = isPrivateCampaign;
window.getCampaignRosterKey = getCampaignRosterKey;
window.getSelectedCampaignName = getSelectedCampaignName;


// =========================================================================
// WORK & STUDY WORKSPACE ENHANCED CONTROLLERS (Crafted UI Suite)
// =========================================================================

function setWorkStudySubMode(mode) {
  const btnAcademic = document.getElementById("btnWorkModeAcademic");
  const btnExecutive = document.getElementById("btnWorkModeExecutive");
  const subModeInput = document.getElementById("workStudySubModeInput");
  const modeDesc = document.getElementById("workStudyModeDesc");
  const labelTopic = document.getElementById("labelWorkStudyTopic");
  const labelSession = document.getElementById("labelWorkStudySession");

  const isAcademic = (mode === 'academic');
  if (subModeInput) subModeInput.value = isAcademic ? 'academic' : 'executive';

  if (isAcademic) {
    if (btnAcademic) {
      btnAcademic.className = "min-h-[34px] px-3 py-1 rounded-lg font-semibold transition-all duration-150 flex items-center gap-1.5 bg-sky-500/20 text-sky-300 border border-sky-500/30 shadow-sm cursor-pointer active:scale-[0.98]";
    }
    if (btnExecutive) {
      btnExecutive.className = "min-h-[34px] px-3 py-1 rounded-lg font-medium transition-all duration-150 flex items-center gap-1.5 text-slate-400 hover:text-slate-200 border border-transparent cursor-pointer active:scale-[0.98]";
    }
    if (modeDesc) {
      modeDesc.innerHTML = `<span class="text-sky-400"><span data-ui-icon=lightbulb aria-hidden=true></span></span> <span>Gemini generará: <strong>Glosario conceptual, fórmulas KaTeX y guía estructurada</strong>.</span>`;
    }
    if (labelTopic) labelTopic.textContent = "Materia o Tema de Estudio:";
    if (labelSession) labelSession.textContent = "Clase / Módulo #:";
  } else {
    if (btnExecutive) {
      btnExecutive.className = "min-h-[34px] px-3 py-1 rounded-lg font-semibold transition-all duration-150 flex items-center gap-1.5 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm cursor-pointer active:scale-[0.98]";
    }
    if (btnAcademic) {
      btnAcademic.className = "min-h-[34px] px-3 py-1 rounded-lg font-medium transition-all duration-150 flex items-center gap-1.5 text-slate-400 hover:text-slate-200 border border-transparent cursor-pointer active:scale-[0.98]";
    }
    if (modeDesc) {
      modeDesc.innerHTML = `<span class="text-indigo-400"><span data-ui-icon=briefcase aria-hidden=true></span></span> <span>Acuerdos, decisiones y tareas.</span>`;
    }
    if (labelTopic) labelTopic.textContent = "Nombre de la Reunión / Sprint:";
    if (labelSession) labelSession.textContent = "Sesión / Sprint #:";
  }
}

function applyWorkStudyPreset(presetKey) {
  const topicInput = document.getElementById("workStudyTopicInput");
  const subjectDisplay = document.getElementById("workStudySubjectDisplay");
  const subjectInput = document.getElementById("lectureSubjectInput");
  const topicLegacy = document.getElementById("lectureTopicInput");

  const presets = {
    university: {
      subMode: 'academic',
      topic: 'Sistemas de Control y Dinámica',
      subject: 'Ingeniería',
      desc: 'Clase Universitaria'
    },
    meeting: {
      subMode: 'executive',
      topic: 'Reunión Semanal de Alineación Operativa',
      subject: 'Operaciones',
      desc: 'Reunión de Equipo'
    },
    research: {
      subMode: 'academic',
      topic: 'Metodología de Investigación y Estado del Arte',
      subject: 'Tesis Doctoral',
      desc: 'Tesis & Investigación'
    },
    keynote: {
      subMode: 'academic',
      topic: 'Conferencia Principal: Inteligencia Artificial Multimodal',
      subject: 'Tecnología',
      desc: 'Conferencia / Keynote'
    },
    sprint: {
      subMode: 'executive',
      topic: 'Sprint Planning & Priorización de Backlog',
      subject: 'Desarrollo de Producto',
      desc: 'Sprint Planning'
    }
  };

  const p = presets[presetKey];
  if (!p) return;

  setWorkStudySubMode(p.subMode);

  if (topicInput) {
    topicInput.value = p.topic;
    topicInput.focus();
  }
  if (subjectDisplay) subjectDisplay.value = p.subject;
  if (subjectInput) subjectInput.value = p.subject;
  if (topicLegacy) topicLegacy.value = p.topic;

  setWorkStudyNowDate();

  if (typeof showAlert === "function") {
    showSuccessAlert(`Plantilla "${p.desc}" aplicada.`);
  }
}

function stepWorkStudySession(delta) {
  const sessionInput = document.getElementById("workStudySessionInput");
  if (!sessionInput) return;
  let val = parseInt(sessionInput.value, 10);
  if (isNaN(val)) val = 1;
  val = Math.max(1, val + delta);
  sessionInput.value = val;
}

function setWorkStudyNowDate() {
  const dateInput = document.getElementById("workStudyDateInput");
  if (!dateInput) return;
  dateInput.value = getLocalFormattedDateTime(new Date());
}

function syncWorkStudySubject(val) {
  const subEl = document.getElementById("lectureSubjectInput");
  if (subEl) subEl.value = val || "";
}

function clearWorkStudyTopic() {
  const topicInput = document.getElementById("workStudyTopicInput");
  const topicLegacy = document.getElementById("lectureTopicInput");
  if (topicInput) topicInput.value = "";
  if (topicLegacy) topicLegacy.value = "";
}

window.setWorkStudySubMode = setWorkStudySubMode;
window.applyWorkStudyPreset = applyWorkStudyPreset;
window.stepWorkStudySession = stepWorkStudySession;
window.setWorkStudyNowDate = setWorkStudyNowDate;
window.syncWorkStudySubject = syncWorkStudySubject;
window.clearWorkStudyTopic = clearWorkStudyTopic;
