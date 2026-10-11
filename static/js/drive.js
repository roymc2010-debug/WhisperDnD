// =========================================================================
// WhisperDnD - drive.js
// Integración con Google Drive: Autenticación persistente (30+ días),
// sincronización en segundo plano e indicadores de respaldo
// =========================================================================

var _driveConnected = false;
var _driveSyncTimer = null;
var _driveConnectedEmail = null;
var isGoogleDriveConnected = false;
var hasAutoSyncedDriveThisSession = false;

function updateDriveSyncIndicator(status) {
  // status: 'saved' | 'syncing' | 'disconnected'
  const campaignIndicator = document.getElementById("campaignDriveSyncIndicator");
  const widgetStatus = document.getElementById("driveSyncStatusWidget");
  const mobileIndicator = document.getElementById("mobileDriveSyncIndicator");

  if (status === "syncing") {
    if (campaignIndicator) {
      campaignIndicator.className = "inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-amber-500/10 border border-amber-500/25 text-amber-300 transition-colors select-none";
      campaignIndicator.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span><span>☁️ Sincronizando con Drive...</span>`;
      campaignIndicator.title = "Sincronizando y guardando cambios en segundo plano con Google Drive ('WhisperDnD')";
    }
    if (widgetStatus) {
      widgetStatus.className = "inline-flex items-center gap-1 text-[11px] font-medium text-amber-300";
      widgetStatus.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span><span>☁️ Sincronizando...</span>`;
      widgetStatus.classList.remove("hidden");
    }
    if (mobileIndicator) {
      mobileIndicator.className = "min-h-[36px] inline-flex items-center justify-center px-2 py-1 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20";
      mobileIndicator.innerHTML = `<span class="animate-spin inline-block">🔄</span>`;
      mobileIndicator.classList.remove("hidden");
      mobileIndicator.title = "Sincronizando con Google Drive...";
    }
  } else if (status === "saved") {
    _driveConnected = true;
    if (campaignIndicator) {
      campaignIndicator.className = "inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400/90 transition-colors select-none";
      campaignIndicator.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>☁️ Guardado en Drive</span>`;
      campaignIndicator.title = "Todos los cambios locales están respaldados en Google Drive ('WhisperDnD')";
    }
    if (widgetStatus) {
      widgetStatus.className = "inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400/90";
      widgetStatus.innerHTML = `<span>☁️ Guardado en Drive</span>`;
      widgetStatus.classList.remove("hidden");
    }
    if (mobileIndicator) {
      mobileIndicator.className = "min-h-[36px] inline-flex items-center justify-center px-2 py-1 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20";
      mobileIndicator.innerHTML = `<span>☁️</span>`;
      mobileIndicator.classList.remove("hidden");
      mobileIndicator.title = "Guardado en Google Drive";
    }
  } else { // 'disconnected'
    _driveConnected = false;
    if (campaignIndicator) {
      campaignIndicator.className = "inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-slate-950 border border-slate-800 text-slate-500 transition-colors select-none";
      campaignIndicator.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-600"></span><span>⚠️ Sin conexión a Drive</span>`;
      campaignIndicator.title = "Google Drive no está conectado. Los datos se guardan de forma local en el servidor.";
    }
    if (widgetStatus) {
      widgetStatus.classList.add("hidden");
    }
    if (mobileIndicator) {
      mobileIndicator.classList.add("hidden");
    }
  }
}

function notifyDriveSaveEvent() {
  if (!_driveConnected) return;
  updateDriveSyncIndicator("syncing");
  clearTimeout(_driveSyncTimer);
  _driveSyncTimer = setTimeout(() => {
    updateDriveSyncIndicator("saved");
  }, 1600);
}

function updateDriveUIState(isConnected, userEmail = null, userName = null) {
  if (userEmail) _driveConnectedEmail = userEmail;
  else if (!isConnected) _driveConnectedEmail = null;

  const btn = document.getElementById("btnConnectDriveHeader");
  const badge = document.getElementById("badgeConnectedDriveHeader");
  const btnSyncHeader = document.getElementById("btnSyncDriveHeader");
  const btnSyncSettings = document.getElementById("btnSyncDriveSettings");
  const btnSyncModal = document.getElementById("btnSyncDriveModal");
  const btnConnectSettings = document.getElementById("btnConnectDriveSettings");
  const btnDisconnectSettings = document.getElementById("btnDisconnectDriveSettings");
  const settingsBadge = document.getElementById("settingsDriveBadge");
  const settingsBadgeText = document.getElementById("settingsDriveBadgeText");
  const settingsAccountInfo = document.getElementById("settingsDriveAccountInfo");
  const settingsEmailEl = document.getElementById("settingsDriveEmail");

  _driveConnected = Boolean(isConnected);
  isGoogleDriveConnected = Boolean(isConnected);
  window.isGoogleDriveConnected = Boolean(isConnected);
  updateDriveSyncIndicator(isConnected ? "saved" : "disconnected");
  if (typeof updateSystemStatusIndicator === "function") {
    updateSystemStatusIndicator();
  }

  if (isConnected) {
    if (btn) btn.classList.add("hidden");
    if (badge) {
      badge.classList.remove("hidden");
      badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400"></span> 🟢 Google Drive Conectado`;
    }
    if (btnSyncHeader) btnSyncHeader.classList.remove("hidden");
    if (btnSyncSettings) btnSyncSettings.classList.remove("hidden");
    if (btnSyncModal) btnSyncModal.classList.remove("hidden");

    // Settings view controls
    if (btnConnectSettings) btnConnectSettings.classList.add("hidden");
    if (btnDisconnectSettings) btnDisconnectSettings.classList.remove("hidden");
    if (settingsBadge) {
      settingsBadge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30";
    }
    if (settingsBadgeText) settingsBadgeText.textContent = "Conectado";
    if (settingsAccountInfo) settingsAccountInfo.classList.remove("hidden");
    if (settingsEmailEl) {
      const displayLabel = _driveConnectedEmail || userEmail || "Cuenta vinculada";
      settingsEmailEl.textContent = displayLabel;
      settingsEmailEl.title = userName ? `${userName} (${displayLabel})` : displayLabel;
    }
  } else {
    if (btn) {
      btn.classList.remove("hidden");
      btn.disabled = false;
      btn.innerHTML = `<span>🔗</span> Conectar Google Drive`;
    }
    if (badge) badge.classList.add("hidden");
    if (btnSyncHeader) btnSyncHeader.classList.add("hidden");
    if (btnSyncSettings) btnSyncSettings.classList.add("hidden");
    if (btnSyncModal) btnSyncModal.classList.add("hidden");

    // Settings view controls
    if (btnConnectSettings) {
      btnConnectSettings.classList.remove("hidden");
      btnConnectSettings.disabled = false;
      const textSpan = document.getElementById("btnConnectDriveSettingsText");
      if (textSpan) textSpan.textContent = "Conectar Google Drive";
    }
    if (btnDisconnectSettings) btnDisconnectSettings.classList.add("hidden");
    if (settingsBadge) {
      settingsBadge.className = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700";
    }
    if (settingsBadgeText) settingsBadgeText.textContent = "No conectado";
    if (settingsAccountInfo) settingsAccountInfo.classList.add("hidden");
    if (settingsEmailEl) settingsEmailEl.textContent = "";
  }
}

async function restoreDriveSessionFromClient() {
  const cachedToken = localStorage.getItem("gdrive_auth_token");
  if (!cachedToken) return false;
  try {
    const tokenObj = JSON.parse(cachedToken);
    const res = await fetch("/api/auth/gdrive/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token_data: tokenObj })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.connected) {
        updateDriveUIState(true);
        return true;
      }
    }
  } catch (e) {
    console.warn("[restoreDriveSessionFromClient] Could not restore Drive session from localStorage:", e);
  }
  return false;
}

async function checkDriveStatus() {
  const urlParams = new URLSearchParams(window.location.search);
  const isJustConnected = urlParams.get("drive_connected") === "true";
  if (isJustConnected) {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
  try {
    let isConnected = false;
    let userEmail = null;
    let userName = null;
    let serverToken = null;
    const res = await fetch("/api/drive/status");
    if (res.ok) {
      const data = await res.json();
      isConnected = Boolean(data.connected);
      userEmail = data.email || null;
      userName = data.name || null;
      serverToken = data.token || null;
      // Sincronizar token fresco en localStorage
      if (serverToken) {
        localStorage.setItem("gdrive_auth_token", JSON.stringify(serverToken));
      }
    }

    // Si el backend no tiene sesión activa, intentar restaurar usando localStorage
    if (!isConnected && localStorage.getItem("gdrive_auth_token")) {
      const restored = await restoreDriveSessionFromClient();
      if (restored) {
        isConnected = true;
        try {
          const rRes = await fetch("/api/drive/status");
          if (rRes.ok) {
            const rData = await rRes.json();
            userEmail = rData.email || null;
            userName = rData.name || null;
            if (rData.token) {
              localStorage.setItem("gdrive_auth_token", JSON.stringify(rData.token));
            }
          }
        } catch (_) {}
      }
    }

    updateDriveUIState(isConnected, userEmail, userName);

    if (isConnected) {
      // Guardar token en localStorage si no estaba guardado
      if (!localStorage.getItem("gdrive_auth_token")) {
        try {
          const tRes = await fetch("/api/drive/token");
          if (tRes.ok) {
            const tData = await tRes.json();
            if (tData.token) {
              localStorage.setItem("gdrive_auth_token", JSON.stringify(tData.token));
            }
          }
        } catch (te) {
          console.warn("Could not cache drive token:", te);
        }
      }

      // Auto-sync al conectarse o al iniciar la app
      if (isJustConnected || !hasAutoSyncedDriveThisSession) {
        hasAutoSyncedDriveThisSession = true;
        await syncWithGoogleDrive(!isJustConnected, isJustConnected);
      }
    }
  } catch (err) {
    console.warn("Could not check Google Drive status:", err);
  }
}

async function connectGoogleDriveUpfront() {
  const btn = document.getElementById("btnConnectDriveHeader");
  const btnSettings = document.getElementById("btnConnectDriveSettings");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="inline-block animate-spin">⏳</span> Abriendo...`;
  }
  if (btnSettings) {
    btnSettings.disabled = true;
    const textSpan = document.getElementById("btnConnectDriveSettingsText");
    if (textSpan) textSpan.textContent = "Conectando...";
  }
  try {
    const res = await fetch("/api/auth/drive/login");
    const data = await res.json();
    if (res.ok && data.auth_url) {
      window._isPageNavigatingOrReloading = true;
      window.location.href = data.auth_url;
    } else {
      throw new Error(data.detail || "No se pudo generar la URL de autenticación.");
    }
  } catch (err) {
    if (typeof showAlert === "function") {
      showAlert("Error conectando Google Drive: " + err.message);
    }
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🔗</span> Conectar Google Drive`;
    }
    if (btnSettings) {
      btnSettings.disabled = false;
      const textSpan = document.getElementById("btnConnectDriveSettingsText");
      if (textSpan) textSpan.textContent = "Conectar Google Drive";
    }
  }
}

async function disconnectGoogleDrive() {
  const confirmed = confirm("¿Deseas cerrar la sesión de Google Drive en este dispositivo?\n\nTus archivos y campañas guardadas localmente se mantendrán intactos.");
  if (!confirmed) return;

  const btn = document.getElementById("btnDisconnectDriveSettings");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="inline-block animate-spin">⏳</span> Cerrando...`;
  }

  try {
    const res = await fetch("/api/drive/disconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    localStorage.removeItem("gdrive_auth_token");
    _driveConnectedEmail = null;
    updateDriveUIState(false);
    if (typeof showSuccessAlert === "function") {
      showSuccessAlert("Google Drive desconectado exitosamente.");
    }
  } catch (err) {
    console.error("Error desconectando Google Drive:", err);
    localStorage.removeItem("gdrive_auth_token");
    _driveConnectedEmail = null;
    updateDriveUIState(false);
    if (typeof showAlert === "function") {
      showAlert("Error en el servidor al desconectar, pero la sesión local fue cerrada.");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg><span>Cerrar Sesión</span>`;
    }
  }
}

async function syncWithGoogleDrive(isSilent = false, isJustConnected = false) {
  const btnHeader = document.getElementById("btnSyncDriveHeader");
  const btnSettings = document.getElementById("btnSyncDriveSettings");
  const btnModal = document.getElementById("btnSyncDriveModal");

  const setButtonsLoading = (loading) => {
    if (btnHeader) {
      btnHeader.disabled = loading;
      btnHeader.innerHTML = loading
        ? `<span class="inline-block animate-spin">⏳</span>`
        : `<svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><span>Sincronizar</span>`;
    }
    if (btnSettings) {
      btnSettings.disabled = loading;
      btnSettings.innerHTML = loading
        ? `<span class="inline-block animate-spin">⏳</span> Buscando en Drive...`
        : `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><span>🔄 Sincronizar Campañas con Drive</span>`;
    }
    if (btnModal) {
      btnModal.disabled = loading;
      btnModal.innerHTML = loading
        ? `<span class="inline-block animate-spin">⏳</span> Buscando...`
        : `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><span>Sincronizar con Drive</span>`;
    }
  };

  setButtonsLoading(true);
  updateDriveSyncIndicator("syncing");
  if (!isSilent) {
    if (isJustConnected && typeof showInfoAlert === "function") {
      showInfoAlert("Google Drive conectado con éxito. Sincronizando campañas desde la carpeta 'WhisperDnD'...");
    } else if (typeof showInfoAlert === "function") {
      showInfoAlert("Buscando campañas y notas en Google Drive ('WhisperDnD')...");
    }
  }

  try {
    const res = await fetch("/api/drive/sync", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    });

    const data = await res.json();
    if (!res.ok || data.status === "error") {
      throw new Error(data.message || data.detail || "Error al sincronizar con Google Drive");
    }

    const downloaded = data.downloaded_campaigns || 0;
    const uploaded = data.uploaded_campaigns || 0;
    const notes = data.downloaded_notes || 0;
    const synced = data.synced_campaigns || 0;

    // Refrescar automáticamente la lista de campañas en el selector y las notas académicas
    let campaigns = [];
    if (typeof loadCampaignList === "function") {
      campaigns = await loadCampaignList();
    }
    if (typeof refreshWikiCampaigns === "function") {
      refreshWikiCampaigns();
    }

    const modal = document.getElementById("campaignManagerModal");
    if (modal && !modal.classList.contains("hidden") && typeof renderCampaignManagerList === "function") {
      renderCampaignManagerList(campaigns);
    }
    if (typeof loadCurrentCampaign === "function") {
      await loadCurrentCampaign();
    }
    if (typeof loadAcademicNotesHistory === "function") {
      await loadAcademicNotesHistory(false);
    }

    updateDriveSyncIndicator("saved");

    if (isJustConnected) {
      if (typeof showSuccessAlert === "function") {
        showSuccessAlert(`Google Drive conectado y sincronizado: ${synced} campaña(s) cargadas en el selector.`);
      }
    } else if (!isSilent) {
      let msg = `Sincronización completada con éxito. `;
      if (downloaded > 0 || uploaded > 0 || notes > 0) {
        msg += `(📥 ${downloaded} campañas descargadas, 📤 ${uploaded} campañas respaldadas, 📝 ${notes} notas restauradas)`;
      } else {
        msg += `Tus campañas y notas locales están al día con Google Drive.`;
      }
      if (typeof showSuccessAlert === "function") showSuccessAlert(msg);
    } else if (downloaded > 0 && typeof showSuccessAlert === "function") {
      showSuccessAlert(`Google Drive: ${downloaded} campaña(s) descargada(s) desde 'WhisperDnD' y cargadas en el selector.`);
    }
  } catch (err) {
    console.error("Sync Drive error:", err);
    if (!isSilent && typeof showAlert === "function") {
      showAlert("Error en la sincronización con Drive: " + err.message);
    }
  } finally {
    setButtonsLoading(false);
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
  const isWorkStudy = (window.currentWorkspace === "work_and_study" || (window.currentResult && window.currentResult.recording_mode === "class"));
  if (!isWorkStudy && !campName) {
    if (typeof showAlert === "function") showAlert("⚠️ Selecciona o abre una campaña antes de subir a Google Drive.");
    return;
  }
  const btn = document.getElementById("btnExportDrive");
  const btnText = document.getElementById("btnDriveText");
  const banner = document.getElementById("driveResultBanner");
  const link = document.getElementById("driveViewLink");
  const fileNameEl = document.getElementById("driveUploadedFileName");

  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = isWorkStudy ? "Subiendo Briefing..." : "Subiendo Grimorio...";
  if (banner) banner.classList.add("hidden");

  try {
    let res;
    if (isWorkStudy && window.currentResult && window.currentResult.docx_filename) {
      res = await fetch("/api/export/drive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: window.currentResult.docx_filename })
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
    if (btnText) btnText.textContent = isWorkStudy ? "✓ Briefing en Drive" : "✓ Grimorio en Drive";
    setTimeout(() => {
      if (btnText) btnText.textContent = "Subir a Drive";
      if (btn) btn.disabled = false;
    }, 3000);
  } catch (err) {
    if (typeof showAlert === "function") showAlert(err.message);
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = "Subir a Drive";
  }
}

// Window bindings
window.updateDriveSyncIndicator = updateDriveSyncIndicator;
window.notifyDriveSaveEvent = notifyDriveSaveEvent;
window.updateDriveUIState = updateDriveUIState;
window.restoreDriveSessionFromClient = restoreDriveSessionFromClient;
window.checkDriveStatus = checkDriveStatus;
window.connectGoogleDriveUpfront = connectGoogleDriveUpfront;
window.disconnectGoogleDrive = disconnectGoogleDrive;
window.syncWithGoogleDrive = syncWithGoogleDrive;
window.exportLivingCampaignToDrive = exportLivingCampaignToDrive;
window.uploadCampaignToDrive = uploadCampaignToDrive;
