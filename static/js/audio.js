// =========================================================================
// WhisperDnD - audio.js
// Dispositivos de audio, calibración VU en vivo, grabación dual PC y móvil
// =========================================================================

function isMobileUser() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
    (window.innerWidth <= 768 && ('ontouchstart' in window || navigator.maxTouchPoints > 0));
}

var audioSourceMode = localStorage.getItem("audio_source_mode") || (isMobileUser() ? "browser_mic" : "pc_host");
var mediaRecorder = null;
var browserRecordingStartedAt = null;
var mediaStream = null;
var browserAudioChunks = [];
var browserAudioContext = null;
var browserAnalyser = null;
var browserAnimFrame = null;

var liveMeterInterval = null;
var isMeterPolling = false;
var isLiveMeterEnabled = true;
var gainMic = parseFloat(localStorage.getItem("dnd_gain_mic") || "1.0");
var gainSpeaker = parseFloat(localStorage.getItem("dnd_gain_speaker") || "2.0");
if (isNaN(gainMic) || gainMic < 0.1 || gainMic > 5.0) gainMic = 1.0;
if (isNaN(gainSpeaker) || gainSpeaker < 0.1 || gainSpeaker > 10.0) gainSpeaker = 2.0;

var timerInterval = null;
var secondsElapsed = 0;
var heartbeatInterval = null;

function setAudioSourceMode(mode) {
  audioSourceMode = mode || "pc_host";
  localStorage.setItem("audio_source_mode", audioSourceMode);

  const btnPc = document.getElementById("btnSourcePcHost");
  const btnBrowser = document.getElementById("btnSourceBrowserMic");
  const badgeCurrent = document.getElementById("badgeCurrentSource");
  const pcDevicesContainer = document.getElementById("pcHostDevicesContainer");
  const browserNotice = document.getElementById("browserMicNotice");
  const ch1Label = document.getElementById("meterCh1Label");
  const speakerRow = document.getElementById("meterSpeakerRow");

  if (audioSourceMode === "browser_mic") {
    if (btnPc) {
      btnPc.className = "min-h-[44px] px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all duration-150 text-slate-400 hover:text-slate-200 cursor-pointer active:scale-[0.98]";
    }
    if (btnBrowser) {
      btnBrowser.className = "min-h-[44px] px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all duration-150 bg-sky-600 text-white shadow-sm cursor-pointer active:scale-[0.98]";
    }
    if (badgeCurrent) {
      badgeCurrent.textContent = "Mic Móvil / Navegador";
      badgeCurrent.className = "px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-sky-500/20 text-sky-300 border border-sky-500/30";
    }
    if (pcDevicesContainer) pcDevicesContainer.classList.add("opacity-40", "pointer-events-none");
    if (browserNotice) browserNotice.classList.remove("hidden");
    if (ch1Label) ch1Label.textContent = "Micrófono Móvil / Dispositivo";
    if (speakerRow) speakerRow.classList.add("hidden");
    stopLiveMeterPolling();
  } else {
    if (btnPc) {
      btnPc.className = "min-h-[44px] px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all duration-150 bg-indigo-600 text-white shadow-sm cursor-pointer active:scale-[0.98]";
    }
    if (btnBrowser) {
      btnBrowser.className = "min-h-[44px] px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all duration-150 text-slate-400 hover:text-slate-200 cursor-pointer active:scale-[0.98]";
    }
    if (badgeCurrent) {
      badgeCurrent.textContent = "PC Host (Dual)";
      badgeCurrent.className = "px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30";
    }
    if (pcDevicesContainer) pcDevicesContainer.classList.remove("opacity-40", "pointer-events-none");
    if (browserNotice) browserNotice.classList.add("hidden");
    if (ch1Label) ch1Label.textContent = "CH 1 (Mic Local)";
    if (speakerRow && (window.currentLiveMode === "roleplay" || !window.currentLiveMode)) speakerRow.classList.remove("hidden");
    if (isLiveMeterEnabled) startLiveMeterPolling();
  }
}

function startBrowserVuMeter() {
  if (!browserAnalyser) return;
  const dataArray = new Uint8Array(browserAnalyser.frequencyBinCount);

  function update() {
    if (!browserAnalyser) return;
    browserAnalyser.getByteFrequencyData(dataArray);
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    const level = Math.min(100, Math.round((avg / 128) * 100));

    const meterBar = document.getElementById("meterMicBar");
    const meterVal = document.getElementById("meterMicValue");
    const dot = document.getElementById("meterActivityDot");
    const hint = document.getElementById("meterStatusHint");

    if (meterBar) meterBar.style.width = level + "%";
    if (meterVal) {
      meterVal.textContent = level > 0 ? `${level}% (Captura Móvil)` : "0% (Silencio)";
      meterVal.className = level > 5 ? "text-emerald-400 font-bold" : "text-slate-500";
    }
    if (dot) {
      dot.className = level > 5 ? "w-2 h-2 rounded-full bg-emerald-400 animate-ping" : "w-2 h-2 rounded-full bg-slate-600";
    }
    if (hint) {
      if (level > 5) {
        hint.textContent = "Señal de micrófono móvil detectada";
        hint.className = "text-[10px] text-emerald-400 font-mono font-semibold";
      } else {
        hint.textContent = "Habla al micrófono de tu dispositivo";
        hint.className = "text-[10px] text-slate-500 font-mono";
      }
    }
    browserAnimFrame = requestAnimationFrame(update);
  }
  update();
}

function stopBrowserVuMeter() {
  if (browserAnimFrame) {
    cancelAnimationFrame(browserAnimFrame);
    browserAnimFrame = null;
  }
  if (browserAudioContext && browserAudioContext.state !== 'closed') {
    browserAudioContext.close().catch(() => {});
    browserAudioContext = null;
  }
  browserAnalyser = null;
}

function refreshAudioDevices() {
  loadAudioDevices(true);
}

function onSettingsMicChange(val) {
  const selectAudioMic = document.getElementById("selectAudioMic");
  if (selectAudioMic) {
    selectAudioMic.value = val;
    onAudioDeviceChange();
  }
  localStorage.setItem("dnd_selected_mic", val);
}

function onSettingsSpeakerChange(val) {
  const selectAudioSpeaker = document.getElementById("selectAudioSpeaker");
  if (selectAudioSpeaker) {
    selectAudioSpeaker.value = val;
    onAudioDeviceChange();
  }
  localStorage.setItem("dnd_selected_speaker", val);
}

async function loadAudioDevices(forceRefresh = false) {
  const micSelect = document.getElementById("selectAudioMic");
  const spkSelect = document.getElementById("selectAudioSpeaker");
  if (!micSelect || !spkSelect) return;

  // Keep previously discovered devices usable while a refresh is pending.
  setAudioDevicesStatus(forceRefresh ? "Actualizando dispositivos…" : "Buscando dispositivos…", "pending");

  try {
    const res = await fetch("/api/audio/devices");
    if (!res.ok) throw new Error("No se pudo obtener la lista de dispositivos de audio.");
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const savedMic = localStorage.getItem("dnd_selected_mic") || "";
    const savedSpk = localStorage.getItem("dnd_selected_speaker") || "";

    // 1. Cargar Micrófonos
    micSelect.innerHTML = "";
    if (!data.microphones || data.microphones.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Micrófono predeterminado";
      micSelect.appendChild(opt);
    } else {
      data.microphones.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        const isSuggested = (data.suggested_mic_id && m.id === data.suggested_mic_id);
        const isDefault = (data.default_mic_id && m.id === data.default_mic_id);
        const tag = isSuggested ? " (Recomendado - Conexant)" : (isDefault ? " (Predeterminado)" : "");
        opt.textContent = `${m.name}${tag}`;
        micSelect.appendChild(opt);
      });
    }

    if (savedMic && Array.from(micSelect.options).some(o => o.value === savedMic)) {
      micSelect.value = savedMic;
    } else if (data.suggested_mic_id) {
      micSelect.value = data.suggested_mic_id;
    } else if (data.default_mic_id) {
      micSelect.value = data.default_mic_id;
    }

    // 2. Cargar Altavoces / Audífonos
    spkSelect.innerHTML = "";
    if (!data.speakers || data.speakers.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "Altavoces predeterminados";
      spkSelect.appendChild(opt);
    } else {
      data.speakers.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s.id;
        const isDefault = (data.default_speaker_id && s.id === data.default_speaker_id);
        const isHeadphone = s.is_headphone;
        opt.dataset.headphone = String(Boolean(isHeadphone));
        opt.textContent = `${s.name}${isDefault ? " (Predeterminado)" : ""}`;
        spkSelect.appendChild(opt);
      });
    }

    if (savedSpk && Array.from(spkSelect.options).some(o => o.value === savedSpk)) {
      spkSelect.value = savedSpk;
    } else if (data.suggested_speaker_id) {
      spkSelect.value = data.suggested_speaker_id;
    } else if (data.default_speaker_id) {
      spkSelect.value = data.default_speaker_id;
    }

    if (micSelect.value) localStorage.setItem("dnd_selected_mic", micSelect.value);
    if (spkSelect.value) localStorage.setItem("dnd_selected_speaker", spkSelect.value);

    syncAudioSettingsSelectors();
    setAudioDevicesStatus("Dispositivos actualizados.", "ready");
    checkSpeakerSelection();
    pollAudioLevel();
  } catch (err) {
    setAudioDevicesStatus(`No se pudieron actualizar los dispositivos: ${err.message}. Vuelve a pulsar «Escanear dispositivos».`, "error");
    console.warn("[Audio Devices] Error cargando dispositivos:", err);
  }
}

function setAudioDevicesStatus(message, state) {
  for (const id of ["audioDevicesStatus", "audioDevicesSettingsStatus"]) {
    const status = document.getElementById(id);
    if (status) { status.textContent = message; status.hidden = !message; status.dataset.state = state; }
  }
}

function syncAudioSettingsSelectors() {
  for (const [sourceId, targetId] of [["selectAudioMic", "deviceMicSettings"], ["selectAudioSpeaker", "deviceSpeakerSettings"]]) {
    const source = document.getElementById(sourceId), target = document.getElementById(targetId);
    if (source && target) {
      target.replaceChildren(...Array.from(source.options, option => option.cloneNode(true)));
      target.value = source.value;
    }
  }
}

function onAudioDeviceChange() {
  syncAudioSettingsSelectors();
  const micSelect = document.getElementById("selectAudioMic");
  const spkSelect = document.getElementById("selectAudioSpeaker");
  if (micSelect && micSelect.value) {
    localStorage.setItem("dnd_selected_mic", micSelect.value);
  }
  if (spkSelect && spkSelect.value) {
    localStorage.setItem("dnd_selected_speaker", spkSelect.value);
  }
  checkSpeakerSelection();
  pollAudioLevel();
}

function checkSpeakerSelection() {
  const spkSelect = document.getElementById("selectAudioSpeaker");
  const warningHint = document.getElementById("speakerWarningHint");
  if (!spkSelect || !warningHint) return;

  const selectedOpt = spkSelect.options[spkSelect.selectedIndex];
  const text = (selectedOpt ? selectedOpt.textContent : "").toLowerCase();
  const isAltavoz = text.includes("altavoz") || text.includes("altavoc") || text.includes("speaker");
  const hasHeadphonesInOptions = Array.from(spkSelect.options).some(o =>
    o.dataset?.headphone === "true" || o.textContent.toLowerCase().includes("auricular") || o.textContent.toLowerCase().includes("headphone")
  );

  if (isAltavoz && hasHeadphonesInOptions && window.currentLiveMode === "roleplay") {
    warningHint.classList.remove("hidden");
  } else {
    warningHint.classList.add("hidden");
  }
}

function initGainSliders() {
  const sMic = document.getElementById("sliderGainMic");
  const sSpk = document.getElementById("sliderGainSpk");
  const dMic = document.getElementById("gainMicDisplay");
  const dSpk = document.getElementById("gainSpkDisplay");

  if (sMic) sMic.value = gainMic;
  if (sSpk) sSpk.value = gainSpeaker;
  if (dMic) dMic.textContent = `${gainMic.toFixed(2)}x`;
  if (dSpk) {
    const db = Math.round(20 * Math.log10(gainSpeaker));
    const dbStr = db >= 0 ? `+${db} dB` : `${db} dB`;
    dSpk.textContent = `${gainSpeaker.toFixed(1)}x (${dbStr})`;
  }
}

function onGainSliderChange(channel, val) {
  const num = parseFloat(val);
  if (isNaN(num)) return;
  if (channel === "mic") {
    gainMic = Math.max(0.1, Math.min(5.0, num));
    localStorage.setItem("dnd_gain_mic", gainMic.toFixed(2));
    const dMic = document.getElementById("gainMicDisplay");
    if (dMic) dMic.textContent = `${gainMic.toFixed(2)}x`;
  } else if (channel === "speaker") {
    gainSpeaker = Math.max(0.1, Math.min(10.0, num));
    localStorage.setItem("dnd_gain_speaker", gainSpeaker.toFixed(2));
    const dSpk = document.getElementById("gainSpkDisplay");
    if (dSpk) {
      const db = Math.round(20 * Math.log10(gainSpeaker));
      const dbStr = db >= 0 ? `+${db} dB` : `${db} dB`;
      dSpk.textContent = `${gainSpeaker.toFixed(1)}x (${dbStr})`;
    }
  }
  pollAudioLevel();
}

function resetAudioGains() {
  gainMic = 1.0;
  gainSpeaker = 2.0;
  localStorage.setItem("dnd_gain_mic", "1.00");
  localStorage.setItem("dnd_gain_speaker", "2.00");
  initGainSliders();
  pollAudioLevel();
}

function toggleLiveMeter(enabled) {
  isLiveMeterEnabled = !!enabled;
  if (isLiveMeterEnabled) {
    startLiveMeterPolling();
  } else {
    stopLiveMeterPolling();
    updateVuMeter(0, 0);
  }
}

function startLiveMeterPolling() {
  if (liveMeterInterval) return;
  liveMeterInterval = setInterval(pollAudioLevel, 600);
  pollAudioLevel();
}

function stopLiveMeterPolling() {
  if (liveMeterInterval) {
    clearInterval(liveMeterInterval);
    liveMeterInterval = null;
  }
}

async function pollAudioLevel() {
  if (isMeterPolling || !isLiveMeterEnabled || audioSourceMode === "browser_mic") return;

  const liveTab = document.getElementById("tabLiveContent");
  const isLiveTabVisible = liveTab && !liveTab.classList.contains("hidden");
  const isRecordingActive = !document.getElementById("btnStopRecording")?.disabled;

  if (!isLiveTabVisible && !isRecordingActive) {
    return;
  }

  isMeterPolling = true;
  try {
    const micId = document.getElementById("selectAudioMic")?.value || "";
    const spkId = (window.currentLiveMode === "roleplay") ? (document.getElementById("selectAudioSpeaker")?.value || "") : "";

    const params = new URLSearchParams();
    if (micId) params.append("mic_id", micId);
    if (spkId) params.append("speaker_id", spkId);
    params.append("gain_mic", gainMic);
    params.append("gain_spk", gainSpeaker);

    const options = (typeof AbortSignal !== "undefined" && AbortSignal.timeout) ? {signal: AbortSignal.timeout(8000)} : {};
    const res = await fetch(`/api/audio/test-level?${params.toString()}`, options);
    if (res.ok) {
      const data = await res.json();
      if (data.meter_busy) {
        for (const id of ["meterStatusHint", "meterStatusHintSettings"]) {
          const hint = document.getElementById(id);
          if (hint) hint.textContent = "Medidor ocupado; esperando una lectura nueva…";
        }
        return;
      }
      updateVuMeter(data.mic_rms || 0, data.speaker_rms || 0, data);

      // Watchdog: monitor recording active status from backend
      if (isRecordingActive) {
        if (data.is_recording === false) {
          onRecordingInterrupted(data.duration_seconds || secondsElapsed);
        } else if (data.is_recording === true) {
          if (data.duration_seconds && Math.abs(secondsElapsed - Math.floor(data.duration_seconds)) > 2) {
            secondsElapsed = Math.floor(data.duration_seconds);
            updateTimerDisplay();
          }
        }
      }
    }
  } catch (err) {
    for (const id of ["meterStatusHint", "meterStatusHintSettings"]) {
      const hint = document.getElementById(id);
      if (hint) hint.textContent = "No se pudo leer la señal; reintentando…";
    }
  } finally {
    isMeterPolling = false;
  }
}

function updateVuMeter(micRms, spkRms, extraData = null) {
  const micBar = document.getElementById("meterMicBar");
  const micVal = document.getElementById("meterMicValue");
  const spkBar = document.getElementById("meterSpkBar");
  const spkVal = document.getElementById("meterSpkValue");
  const dot = document.getElementById("meterActivityDot");
  const hint = document.getElementById("meterStatusHint");

  const calcPct = (rms) => {
    if (!rms || rms < 0.0003) return 0;
    return Math.min(100, Math.round(Math.sqrt(rms / 0.15) * 100));
  };

  const micPct = calcPct(micRms);
  const spkPct = (window.currentLiveMode === "roleplay") ? calcPct(spkRms) : 0;

  if (micBar) micBar.style.width = `${micPct}%`;
  if (micVal) {
    micVal.textContent = micPct > 0 ? `${micPct}% (RMS ${micRms.toFixed(4)})` : "0% (Silencio)";
    micVal.className = micPct > 0 ? "text-indigo-300 font-bold" : "text-slate-500";
  }

  if (spkBar) spkBar.style.width = `${spkPct}%`;
  if (spkVal) {
    if (window.currentLiveMode === "roleplay") {
      if (spkPct > 0) {
        spkVal.textContent = `${spkPct}% (Discord)`;
        spkVal.className = "text-amber-300 font-bold";
      } else {
        const isDetect = extraData?.discord_detected || extraData?.discord_status?.discord_detected;
        const dMsg = extraData?.discord_status?.status_message || extraData?.discord_message || (isDetect ? "Discord listo (en espera de voz)" : "Esperando a Discord...");
        spkVal.textContent = dMsg;
        spkVal.className = isDetect ? "text-emerald-400 font-medium text-[10px]" : "text-amber-400 font-medium text-[10px]";
      }
    } else {
      spkVal.textContent = spkPct > 0 ? `${spkPct}% (RMS ${spkRms.toFixed(4)})` : "0% (Silencio)";
      spkVal.className = spkPct > 0 ? "text-amber-300 font-bold" : "text-slate-500";
    }
  }

  for (const [barId, valueId, pct] of [["meterMicBarSettings", "meterMicValSettings", micPct], ["meterSpkBarSettings", "meterSpkValSettings", spkPct]]) {
    const bar = document.getElementById(barId), value = document.getElementById(valueId);
    if (bar) bar.style.width = `${pct}%`;
    if (value) value.textContent = `${pct}%`;
  }
  const discordText = document.getElementById("discordLiveStatusText");
  if (discordText) discordText.textContent = extraData?.discord_status?.status_message || extraData?.discord_message || "Estado de Discord pendiente de lectura";

  const hasActivity = (micPct > 0 || spkPct > 0);
  const settingsHint = document.getElementById("meterStatusHintSettings");
  if (settingsHint) settingsHint.textContent = hasActivity ? "Señal de audio detectada" : "Habla o reproduce audio para probar señal";
  if (dot) {
    dot.className = hasActivity ? "w-2 h-2 rounded-full bg-emerald-400 animate-ping" : "w-2 h-2 rounded-full bg-slate-600";
  }
  if (hint) {
    if (hasActivity) {
      hint.textContent = "Señal de audio detectada";
      hint.className = "text-[10px] text-emerald-400 font-mono font-semibold";
    } else {
      hint.textContent = "Habla o reproduce audio para probar señal";
      hint.className = "text-[10px] text-slate-500 font-mono";
    }
  }
}

function onRecordingInterrupted(durationSec) {
  stopTimer();
  stopHeartbeat();
  if (durationSec) {
    secondsElapsed = Math.floor(durationSec);
    updateTimerDisplay();
  }

  const btnStart = document.getElementById("btnStartRecording");
  const btnStop = document.getElementById("btnStopRecording");
  const btnStopOnly = document.getElementById("btnStopOnly");
  const statusText = document.getElementById("liveRecordingStatus");
  const watchdogAlert = document.getElementById("recordingWatchdogAlert");
  const watchdogMsg = document.getElementById("recordingWatchdogMsg");

  if (btnStart) {
    btnStart.disabled = false;
    btnStart.classList.remove("opacity-40", "cursor-not-allowed");
  }
  if (btnStop) {
    btnStop.disabled = false;
  }

  if (statusText) {
    statusText.textContent = `Grabación detenida en el servidor (${formatTime(secondsElapsed)} grabados)`;
    statusText.className = "text-xs text-amber-400 font-semibold";
  }

  if (watchdogAlert && watchdogMsg) {
    watchdogMsg.textContent = `La captura de audio en el servidor se detuvo tras ${formatTime(secondsElapsed)}. El audio grabado está seguro en el servidor. Presiona "Detener y Procesar" para transcribirlo con Gemini y Groq, o pulsa "Iniciar Grabación" para comenzar una nueva.`;
    watchdogAlert.classList.remove("hidden");
  }
}

async function checkActiveRecording() {
  try {
    const res = await fetch("/api/record/status");
    if (res.ok) {
      const data = await res.json();
      if (data.is_recording) {
        if (data.mode && typeof window.setLiveMode === "function") {
          window.setLiveMode(data.mode);
        }
        secondsElapsed = Math.floor(data.duration_seconds || 0);
        startTimer();
        setRecordingUI(true);
        const watchdogAlert = document.getElementById("recordingWatchdogAlert");
        if (watchdogAlert) watchdogAlert.classList.add("hidden");
      }
    }
  } catch (err) {
    console.warn("Could not check recording status:", err);
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

function startHeartbeat() {
  stopHeartbeat();
  heartbeatInterval = setInterval(async () => {
    try {
      await fetch('/api/ping');
      console.log('[Keep-Alive] Heartbeat ping sent to Render');
    } catch (e) {
      console.warn('[Keep-Alive] Heartbeat ping failed:', e);
    }
  }, 5 * 60 * 1000);
  console.log('[Keep-Alive] Heartbeat started (interval: 5m)');
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
    console.log('[Keep-Alive] Heartbeat stopped');
  }
}

function setRecordingUI(isRecording) {
  const btnStart = document.getElementById("btnStartRecording");
  const btnStop = document.getElementById("btnStopRecording");
  const btnStopOnly = document.getElementById("btnStopOnly");
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
    if (btnStopOnly) btnStopOnly.disabled = false;
    if (badge) badge.classList.remove("hidden");
    if (statusText) {
      if (audioSourceMode === "browser_mic") {
        statusText.textContent = "Grabación en curso con Micrófono del Móvil / Navegador";
      } else if (window.currentLiveMode === "class") {
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
    if (btnStopOnly) btnStopOnly.disabled = true;
    if (badge) badge.classList.add("hidden");
    if (statusText) {
      if (audioSourceMode === "browser_mic") {
        statusText.textContent = "Listo para grabar desde el micrófono de este dispositivo";
      } else if (window.currentLiveMode === "class") {
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

async function startSessionRecording() {
  if (typeof hideAlert === "function") hideAlert();
  const watchdogAlert = document.getElementById("recordingWatchdogAlert");
  if (watchdogAlert) watchdogAlert.classList.add("hidden");

  // Validación estricta: en modo D&D / rol no se puede grabar sin seleccionar o crear una campaña
  if (window.currentLiveMode === "roleplay" || window.currentWorkspace === "dnd") {
    const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
    if (!campName) {
      if (typeof showAlert === "function") {
        showAlert("Debes seleccionar o crear una campaña antes de iniciar la grabación.");
      }
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
  }

  if (window.currentLiveMode !== "class" && window.currentWorkspace !== "work_and_study" &&
      typeof ensureCampaignRosterReady === "function" && !ensureCampaignRosterReady()) return;
  if (typeof checkQuotaBeforeAction === "function") {
    const quotaOk = await checkQuotaBeforeAction("una nueva grabación de sesión");
    if (typeof window.clearResultsView === "function") {
      window.clearResultsView(true);
    }
    if (!quotaOk) return;
  }

  // MODO 1: GRABACIÓN DIRECTA EN NAVEGADOR / MÓVIL (MediaRecorder API)
  if (audioSourceMode === "browser_mic") {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Tu navegador no permite captura de micrófono o la conexión no es segura (se requiere HTTPS en móvil).");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      mediaStream = stream;
      browserAudioChunks = [];

      let mimeType = "audio/webm;codecs=opus";
      if (!window.MediaRecorder || !MediaRecorder.isTypeSupported(mimeType)) {
        if (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        } else if (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm")) {
          mimeType = "audio/webm";
        } else {
          mimeType = "";
        }
      }

      const options = mimeType ? { mimeType } : {};
      mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          browserAudioChunks.push(event.data);
        }
      };

      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          browserAudioContext = new AudioCtx();
          const sourceNode = browserAudioContext.createMediaStreamSource(stream);
          browserAnalyser = browserAudioContext.createAnalyser();
          browserAnalyser.fftSize = 256;
          sourceNode.connect(browserAnalyser);
          startBrowserVuMeter();
        }
      } catch (e) {
        console.warn("No se pudo iniciar AudioContext para medidor visual:", e);
      }

      const captureStart = new Date();
      browserRecordingStartedAt = new Date(captureStart.getTime() - captureStart.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
      mediaRecorder.start(1000);
      secondsElapsed = 0;
      startTimer();
      setRecordingUI(true);
      return;
    } catch (err) {
      if (typeof showAlert === "function") {
        showAlert("Error al acceder al micrófono del dispositivo: " + err.message + ". Asegúrate de estar usando un túnel HTTPS y permitir el permiso de micrófono.");
      }
      return;
    }
  }

  // MODO 2: GRABACIÓN DEL SERVIDOR PC HOST (soundcard dual-canal)
  try {
    const micSelect = document.getElementById("selectAudioMic");
    const spkSelect = document.getElementById("selectAudioSpeaker");
    const micId = micSelect ? micSelect.value || null : null;
    const spkId = (window.currentLiveMode === "roleplay" && spkSelect) ? spkSelect.value || null : null;

    const campName = (window.currentLiveMode === "roleplay" || window.currentWorkspace === "dnd")
      ? (document.getElementById("campaignNameInput")?.value || "").trim()
      : null;

    const res = await fetch("/api/record/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: window.currentLiveMode || "roleplay",
        mic_id: micId,
        speaker_id: spkId,
        gain_mic: gainMic,
        gain_spk: gainSpeaker,
        campaign_name: campName,
        session_number: campName ? (parseInt(document.getElementById('sessionNumberInput')?.value, 10) || null) : null
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al iniciar grabación en el servidor.");

    secondsElapsed = 0;
    startTimer();
    setRecordingUI(true);
  } catch (err) {
    if (typeof showAlert === "function") showAlert(err.message);
  }
}

async function stopSessionAndProcess() {
  if (window.currentLiveMode !== "class" && window.currentWorkspace !== "work_and_study" &&
      typeof ensureCampaignRosterReady === "function" && !ensureCampaignRosterReady()) return;
  if (typeof hideAlert === "function") hideAlert();
  if (typeof hideErrorCard === "function") hideErrorCard();
  window.lastActionCallback = () => stopSessionAndProcess();
  stopTimer();
  setRecordingUI(false);
  const modelSize = document.getElementById("globalModelSize") ? document.getElementById("globalModelSize").value : "base";
  const engine = (document.getElementById("transcriptionEngine") ? document.getElementById("transcriptionEngine").value : "") || "groq";
  const taskId = generateTaskId();
  const engineName = (engine === "groq") ? "Groq Whisper Large-v3" : "faster-whisper local";

  // MODO 1: DETENER GRABACIÓN MÓVIL / MEDIARECORDER Y ENVIAR AL SERVIDOR
  if (audioSourceMode === "browser_mic" && mediaRecorder) {
    stopBrowserVuMeter();
    if (typeof updateStepperMode === "function") updateStepperMode(false);
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Finalizando captura del dispositivo móvil...",
        `Empaquetando audio local y transmitiendo al backend para transcripción con ${engineName}.`
      );
    }

    mediaRecorder.onstop = async () => {
      try {
        const actualMime = mediaRecorder.mimeType || "audio/webm";
        const ext = actualMime.includes("mp4") ? "mp4" : "webm";
        const audioBlob = new Blob(browserAudioChunks, { type: actualMime });

        if (mediaStream) {
          mediaStream.getTracks().forEach(t => t.stop());
          mediaStream = null;
        }

        const formData = new FormData();
        formData.append("file", audioBlob, `mobile_recording_${Date.now()}.${ext}`);
        if (browserRecordingStartedAt) formData.append("recorded_at", browserRecordingStartedAt);
        formData.append("model_size", modelSize);
        formData.append("engine", engine);
        formData.append("task_id", taskId);
        formData.append("target_language", window.currentTargetLanguage || "es");

        if (window.currentLiveMode === "class" || window.currentWorkspace === "work_and_study") {
          const topic = (document.getElementById("workStudyTopicInput") ? document.getElementById("workStudyTopicInput").value.trim() : "") ||
                        (document.getElementById("lectureTopicInput") ? document.getElementById("lectureTopicInput").value.trim() : "") ||
                        "Reunión / Clase";
          const subject = (document.getElementById("lectureSubjectInput") ? document.getElementById("lectureSubjectInput").value.trim() : "") ||
                          topic;
          const dateEl = document.getElementById("workStudyDateInput");
          const customDate = (dateEl && dateEl.value.trim()) ? dateEl.value.trim() : (typeof getLocalFormattedDateTime === "function" ? getLocalFormattedDateTime() : "");
          formData.append("recording_mode", "class");
          formData.append("document_format", getWorkStudyDocumentFormat());
    formData.append("subject", subject);
          formData.append("topic", topic);
          if (customDate) formData.append("custom_date", customDate);
          formData.append("client_timezone_offset", String(new Date().getTimezoneOffset()));
        } else {
          formData.append("client_timezone_offset", String(new Date().getTimezoneOffset()));
          const campaignName = (document.getElementById("campaignNameInput")?.value || "").trim();
          if (!campaignName) {
            if (typeof showAlert === "function") showAlert("Debes seleccionar o crear una campaña para procesar la sesión.");
            const campInput = document.getElementById("campaignNameInput");
            if (campInput) {
              campInput.focus();
              campInput.classList.add("ring-2", "ring-rose-500", "border-rose-500");
              setTimeout(() => {
                campInput.classList.remove("ring-2", "ring-rose-500", "border-rose-500");
              }, 3500);
            }
            setRecordingUI(true);
            return;
          }
          const roster = typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [];
          const sessionNumber = parseInt(document.getElementById("sessionNumberInput").value) || "";
          formData.append("recording_mode", "roleplay");
          formData.append("campaign_name", campaignName);
          if (sessionNumber) formData.append("session_number", sessionNumber);
          formData.append("roster_json", JSON.stringify(roster));
        }

  if (window.currentActiveAbortController) {
          try { window.currentActiveAbortController.abort(); } catch (_) {}
        }
        window.currentActiveAbortController = new AbortController();

        const refTextLive = (document.getElementById("optionalReferenceTextInput")?.value || "").trim();
        if (refTextLive) formData.append("reference_text", refTextLive);
        formData.append("processing_source", "recording");
        const res = await fetch("/api/transcribe/file", {
          method: "POST",
          headers: typeof getUserApiHeaders === "function" ? getUserApiHeaders() : {},
          body: formData,
          signal: window.currentActiveAbortController.signal
        });

        const data = await res.json();
        if (typeof checkAuthErrorAndRedirect === "function" && checkAuthErrorAndRedirect(res.status, data)) {
          throw new Error("Credenciales de API requeridas.");
        }
        if (!res.ok) throw new Error(data.detail || "Error al procesar el audio del dispositivo.");

        if (typeof displayResults === "function") {
          displayResults(data, { source: "live" });
        }
        if (typeof finishProgressTracking === "function") {
          finishProgressTracking(true);
        }
      } catch (err) {
        if (err.name === "AbortError") {
          console.log("[stopSessionAndProcess:browser_mic] Proceso detenido por el usuario.");
          return;
        }
        if (typeof finishProgressTracking === "function") finishProgressTracking(false);
        if (typeof showErrorCard === "function") {
          showErrorCard(err.message, () => stopSessionAndProcess());
        }
      }
    };

    try {
      if (mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
    } catch (e) {
      console.warn("MediaRecorder already inactive:", e);
    }
    return;
  }

  // MODO 2: DETENER GRABACIÓN PC HOST
  let bodyPayload = {};
  if (window.currentLiveMode === "class" || window.currentWorkspace === "work_and_study") {
    const topic = (document.getElementById("workStudyTopicInput") ? document.getElementById("workStudyTopicInput").value.trim() : "") ||
                  (document.getElementById("lectureTopicInput") ? document.getElementById("lectureTopicInput").value.trim() : "") ||
                  "Reunión / Clase";
    const subject = (document.getElementById("lectureSubjectInput") ? document.getElementById("lectureSubjectInput").value.trim() : "") ||
                    topic;
    const dateEl = document.getElementById("workStudyDateInput");
    const customDate = (dateEl && dateEl.value.trim()) ? dateEl.value.trim() : (typeof getLocalFormattedDateTime === "function" ? getLocalFormattedDateTime() : "");
    bodyPayload = {
      task_id: taskId,
      recording_mode: "class",
      document_format: getWorkStudyDocumentFormat(),
      subject: subject,
      topic: topic,
      custom_date: customDate || null,
      client_timezone_offset: new Date().getTimezoneOffset(),
      model_size: modelSize,
      engine: engine,
      target_language: window.currentTargetLanguage || "es"
    };
    if (typeof updateStepperMode === "function") updateStepperMode(false);
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Deteniendo grabación y generando el documento...",
        `Transcribiendo con ${engineName} y generando el documento con Gemini para "${topic}".`
      );
    }
  } else {
    const campaignName = (document.getElementById("campaignNameInput")?.value || "").trim();
    if (!campaignName) {
      if (typeof showAlert === "function") showAlert("Debes seleccionar o crear una campaña para procesar la sesión.");
      const campInput = document.getElementById("campaignNameInput");
      if (campInput) {
        campInput.focus();
        campInput.classList.add("ring-2", "ring-rose-500", "border-rose-500");
        setTimeout(() => {
          campInput.classList.remove("ring-2", "ring-rose-500", "border-rose-500");
        }, 3500);
      }
      setRecordingUI(true);
      return;
    }
    const roster = typeof getRosterFromTable === "function" ? getRosterFromTable(true) : [];
    const sessionNumber = parseInt(document.getElementById("sessionNumberInput").value) || null;
    bodyPayload = {
      task_id: taskId,
      recording_mode: "roleplay",
      roster: roster,
      model_size: modelSize,
      engine: engine,
      campaign_name: campaignName,
      session_number: sessionNumber,
      client_timezone_offset: new Date().getTimezoneOffset(),
      target_language: window.currentTargetLanguage || "es"
    };
    if (typeof updateStepperMode === "function") updateStepperMode(false);
    if (typeof startProgressTracking === "function") {
      startProgressTracking(
        taskId,
        "Deteniendo grabación y enriqueciendo el Diario de Campaña...",
        `Transcribiendo con ${engineName}, identificando misiones/PNJs y generando crónica continua con Gemini.`
      );
    }
  }

  const refTextLive2 = (document.getElementById("optionalReferenceTextInput")?.value || "").trim();
  if (refTextLive2 && bodyPayload) {
    bodyPayload.reference_text = refTextLive2;
  }

  if (window.currentActiveAbortController) {
    try { window.currentActiveAbortController.abort(); } catch (_) {}
  }
  window.currentActiveAbortController = new AbortController();

  try {
    const res = await fetch("/api/record/stop-and-process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(typeof getUserApiHeaders === "function" ? getUserApiHeaders() : {})
      },
      body: JSON.stringify(bodyPayload),
      signal: window.currentActiveAbortController.signal
    });

    const data = await res.json();
    if (typeof checkAuthErrorAndRedirect === "function" && checkAuthErrorAndRedirect(res.status, data)) {
      throw new Error("Credenciales de API requeridas.");
    }
    if (!res.ok) throw new Error(data.detail || "Error al procesar la sesión.");

    if (typeof displayResults === "function") {
      displayResults(data, { source: "live" });
    }
    if (typeof finishProgressTracking === "function") {
      finishProgressTracking(true);
    }
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("[stopSessionAndProcess:pcHost] Proceso detenido por el usuario.");
      return;
    }
    if (typeof finishProgressTracking === "function") finishProgressTracking(false);
    if (typeof showErrorCard === "function") {
      showErrorCard(err.message, () => stopSessionAndProcess());
    }
  }
}

async function deleteOriginalAudio() {
  if (!window.currentResult || !window.currentResult.wav_filename) {
    if (typeof showAlert === "function") showAlert("No hay audio original asociado a esta sesión.");
    return;
  }
  const filename = window.currentResult.wav_filename;
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

    if (typeof showAlert === "function") showAlert(data.message || "Audio original eliminado con éxito.");
    window.currentResult.wav_filename = null;
    const btnDlAudio = document.getElementById("btnDownloadAudio");
    if (btnDlAudio) btnDlAudio.classList.add("hidden");
    if (btn) {
      if (btnText) btnText.textContent = "Audio eliminado";
      setTimeout(() => {
        btn.classList.add("hidden");
      }, 2000);
    }
  } catch (err) {
    if (typeof showAlert === "function") showAlert("Error al eliminar audio: " + err.message);
    if (btn) {
      btn.disabled = false;
      if (btnText) btnText.textContent = "Eliminar audio original";
    }
  }
}

function downloadAudioFile() {
  if (window.currentResult && window.currentResult.wav_filename) {
    const url = `/api/download/audio/${encodeURIComponent(window.currentResult.wav_filename)}`;
    if (typeof navigateToDownload === "function") {
      navigateToDownload(url);
    } else {
      window.location.href = url;
    }
    return;
  }
  if (typeof showAlert === "function") showAlert("No hay archivo de audio original disponible para descargar.");
}

function openBackupFallbackModal() {
  const modal = document.getElementById("backupFallbackModal");
  const box = document.getElementById("backupFallbackModalBox");
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  modal.style.pointerEvents = "auto";
  if (box) box.style.pointerEvents = "auto";
  requestAnimationFrame(() => {
    modal.classList.remove("opacity-0", "pointer-events-none");
    modal.classList.add("opacity-100", "pointer-events-auto");
    if (box) {
      box.classList.remove("scale-95");
      box.classList.add("scale-100");
    }
  });
}

function closeBackupFallbackModal() {
  const modal = document.getElementById("backupFallbackModal");
  const box = document.getElementById("backupFallbackModalBox");
  if (!modal) return;
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

function retryUploadSavedAudio() {
  closeBackupFallbackModal();
  stopSessionAndProcess();
}

function reDownloadBackupAudio() {
  if (browserAudioChunks && browserAudioChunks.length > 0) {
    const blob = new Blob(browserAudioChunks, { type: "audio/webm" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `grabacion_respaldo_${Date.now()}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  } else if (typeof showAlert === "function") {
    showAlert("No hay audio en memoria para descargar.");
  }
}

function switchToManualUploadFromBackup() {
  closeBackupFallbackModal();
  if (typeof switchMainTab === "function") switchMainTab("file");
}

function confirmAndClearBackupMemory() {
  closeBackupFallbackModal();
  browserAudioChunks = [];
}

// Window bindings
window.openBackupFallbackModal = openBackupFallbackModal;
window.closeBackupFallbackModal = closeBackupFallbackModal;
window.retryUploadSavedAudio = retryUploadSavedAudio;
window.reDownloadBackupAudio = reDownloadBackupAudio;
window.switchToManualUploadFromBackup = switchToManualUploadFromBackup;
window.confirmAndClearBackupMemory = confirmAndClearBackupMemory;
window.isMobileUser = isMobileUser;
window.setAudioSourceMode = setAudioSourceMode;
window.startBrowserVuMeter = startBrowserVuMeter;
window.stopBrowserVuMeter = stopBrowserVuMeter;
window.refreshAudioDevices = refreshAudioDevices;
window.onSettingsMicChange = onSettingsMicChange;
window.onSettingsSpeakerChange = onSettingsSpeakerChange;
window.loadAudioDevices = loadAudioDevices;
window.onAudioDeviceChange = onAudioDeviceChange;
window.checkSpeakerSelection = checkSpeakerSelection;
window.initGainSliders = initGainSliders;
window.onGainSliderChange = onGainSliderChange;
window.resetAudioGains = resetAudioGains;
window.toggleLiveMeter = toggleLiveMeter;
window.startLiveMeterPolling = startLiveMeterPolling;
window.stopLiveMeterPolling = stopLiveMeterPolling;
window.pollAudioLevel = pollAudioLevel;
window.updateVuMeter = updateVuMeter;
window.onRecordingInterrupted = onRecordingInterrupted;
window.checkActiveRecording = checkActiveRecording;
window.startTimer = startTimer;
window.stopTimer = stopTimer;
window.updateTimerDisplay = updateTimerDisplay;
window.startHeartbeat = startHeartbeat;
window.stopHeartbeat = stopHeartbeat;
window.setRecordingUI = setRecordingUI;
window.startSessionRecording = startSessionRecording;
async function stopRecordingOnly() {
  if (typeof hideAlert === "function") hideAlert();
  if (typeof hideErrorCard === "function") hideErrorCard();
  stopTimer();
  setRecordingUI(false);
  try {
    const res = await fetch("/api/record/stop", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      const savedPath = data.full_path || data.file_path || "data/input/";
      if (typeof showSuccessAlert === "function") {
        showSuccessAlert(`Grabación WAV guardada con éxito (sin procesar con IA) en: ${savedPath}`);
      } else if (typeof showAlert === "function") {
        showAlert(`Grabación WAV guardada con éxito en: ${savedPath}`);
      }
      console.log("[AudioRecorder] Grabación guardada sin IA en:", savedPath);
    } else {
      throw new Error(data.detail || "Error al detener grabación");
    }
  } catch (err) {
    if (typeof showAlert === "function") showAlert(err.message);
  }
}

window.stopRecordingOnly = stopRecordingOnly;
window.stopSessionAndProcess = stopSessionAndProcess;
window.deleteOriginalAudio = deleteOriginalAudio;
window.downloadAudioFile = downloadAudioFile;
