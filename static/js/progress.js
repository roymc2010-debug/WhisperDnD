// =========================================================================
// WhisperDnD - progress.js
// Barra de progreso fluida con decimales, polling de tareas y fases
// =========================================================================

var progressPollInterval = null;
var currentTaskId = null;
var lastActionCallback = null;
var currentProgressPercent = 0.0;
var targetProgressPercent = 0.0;
var progressAnimationRaf = null;
var progressCurrentStage = null;
var isYoutubeStepper = false;

function generateTaskId() {
  return 'task_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
}

function showProcessingCard(title = "", desc = "") {
  const card = document.getElementById("processingCard");
  if (card) {
    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  if (title) {
    const titleEl = document.getElementById("procStepTitle");
    if (titleEl) {
      const span = titleEl.querySelector("span:last-child");
      if (span) span.textContent = title;
      else titleEl.textContent = title;
    }
  }
  if (desc) {
    const descEl = document.getElementById("procStepDesc");
    if (descEl) descEl.textContent = desc;
  }
}

function hideProcessingCard() {
  const card = document.getElementById("processingCard");
  if (card) card.classList.add("hidden");
}

function showErrorCard(errorMessage, retryCallback = null) {
  finishProgressTracking(false);
  const card = document.getElementById("errorCard");
  const msgEl = document.getElementById("errorCardMessage");
  if (msgEl) msgEl.textContent = errorMessage || "Ocurrió un error inesperado durante el procesamiento.";
  if (retryCallback) {
    lastActionCallback = retryCallback;
  }
  if (card) {
    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function hideErrorCard() {
  const card = document.getElementById("errorCard");
  if (card) card.classList.add("hidden");
}

function retryLastAction() {
  hideErrorCard();
  if (typeof lastActionCallback === 'function') {
    const fn = lastActionCallback;
    lastActionCallback = null;
    fn();
  } else if (typeof showAlert === 'function') {
    showAlert("Por favor reintenta la operación desde el botón correspondiente.");
  }
}

function renderProgressDOM(val) {
  const clamped = Math.max(0.0, Math.min(100.0, val));
  // Muestra siempre el porcentaje con precisión de un decimal (ej: 42.5%)
  const formatted = clamped.toFixed(1) + "%";
  const percentEl = document.getElementById("progressBarPercent");
  const fillEl = document.getElementById("progressBarFill");

  if (percentEl) percentEl.textContent = formatted;
  if (fillEl) fillEl.style.width = formatted;
  updateStageHighlights(clamped, progressCurrentStage);
}

function startProgressAnimationLoop() {
  if (progressAnimationRaf) return;

  const tick = () => {
    let diff = targetProgressPercent - currentProgressPercent;

    if (diff > 0.05) {
      // Easing suave hacia el hito reportado por el backend
      const step = Math.max(0.05, diff * 0.12);
      currentProgressPercent = Math.min(targetProgressPercent, currentProgressPercent + step);
    } else if (currentTaskId && targetProgressPercent > 0.0 && targetProgressPercent < 99.0) {
      // Micro-incremento fluido y vivo mientras el backend procesa entre polls (con decimales)
      let stageCeiling = 98.5;
      if (progressCurrentStage === "audio") stageCeiling = 24.9;
      else if (progressCurrentStage === "segmenting") stageCeiling = 29.9;
      else if (progressCurrentStage === "transcribing") stageCeiling = 79.9;
      else if (progressCurrentStage === "analyzing") stageCeiling = 98.9;

      if (currentProgressPercent < stageCeiling) {
        currentProgressPercent = Math.min(stageCeiling, currentProgressPercent + 0.035);
      }
    } else if (targetProgressPercent >= 100.0) {
      currentProgressPercent = 100.0;
    }

    renderProgressDOM(currentProgressPercent);

    if (currentTaskId || currentProgressPercent < targetProgressPercent) {
      progressAnimationRaf = requestAnimationFrame(tick);
    } else {
      progressAnimationRaf = null;
    }
  };

  progressAnimationRaf = requestAnimationFrame(tick);
}

function stopProgressAnimationLoop() {
  if (progressAnimationRaf) {
    cancelAnimationFrame(progressAnimationRaf);
    progressAnimationRaf = null;
  }
}

function startProgressTracking(taskId, initialTitle, initialDesc) {
  currentTaskId = taskId;
  currentProgressPercent = 0.0;
  targetProgressPercent = 0.0;
  progressCurrentStage = null;
  hideErrorCard();
  if (typeof hideAlert === "function") hideAlert();

  if (progressPollInterval) {
    clearInterval(progressPollInterval);
    progressPollInterval = null;
  }
  stopProgressAnimationLoop();

  showProcessingCard(initialTitle, initialDesc);
  renderProgressDOM(0.0);
  startProgressAnimationLoop();

  progressPollInterval = setInterval(async () => {
    if (!currentTaskId) return;
    try {
      const res = await fetch(`/api/task/status?task_id=${encodeURIComponent(currentTaskId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.status === 'error') {
          if (progressPollInterval) {
            clearInterval(progressPollInterval);
            progressPollInterval = null;
          }
          showErrorCard(data.error_message || data.message || "Error durante el procesamiento.");
          return;
        }
        if (data && typeof data.percent === 'number') {
          updateProgressBar(data.percent, data.step, data.message, data.stage);
        }
      }
    } catch (err) {
      console.warn("Error polling task status:", err);
    }
  }, 1000);
}

function setStageElementState(el, state) {
  if (!el) return;
  const icon = el.querySelector(".stage-icon");
  if (state === "active") {
    el.className = "p-2.5 rounded-xl border border-amber-500/60 bg-amber-950/30 text-left space-y-1 transition-all ring-1 ring-amber-500/50 shadow-md shadow-amber-900/20";
    if (icon) icon.textContent = "⚡";
  } else if (state === "completed") {
    el.className = "p-2.5 rounded-xl border border-emerald-500/40 bg-emerald-950/20 text-left space-y-1 transition-all";
    if (icon) icon.textContent = "✓";
  } else {
    el.className = "p-2.5 rounded-xl border border-slate-800 bg-slate-950/60 text-left space-y-1 transition-all opacity-60";
    if (icon) icon.textContent = "⏳";
  }
}

function updateProgressBar(percent, title, desc, stage = null) {
  const p = Math.max(0.0, Math.min(100.0, parseFloat(percent) || 0.0));
  targetProgressPercent = Math.max(targetProgressPercent, p);
  if (stage) progressCurrentStage = stage;

  const titleEl = document.getElementById("procStepTitle");
  const descEl = document.getElementById("procStepDesc");

  if (title && titleEl) {
    const span = titleEl.querySelector("span:last-child");
    if (span) span.textContent = title;
    else titleEl.textContent = title;
  }
  if (desc && descEl) descEl.textContent = desc;

  startProgressAnimationLoop();
}

function updateStepperMode(isYoutube) {
  isYoutubeStepper = Boolean(isYoutube);
  const container = document.getElementById("stepperContainer");
  const stageAudio = document.getElementById("stageAudio");
  const stageAudioStep = document.getElementById("stageAudioStep");
  const stageTranscribeStep = document.getElementById("stageTranscribeStep");
  const stageTranscribeDesc = document.getElementById("stageTranscribeDesc");
  const stageGeminiStep = document.getElementById("stageGeminiStep");
  const stageDoneStep = document.getElementById("stageDoneStep");

  if (isYoutubeStepper) {
    if (container) {
      container.className = "grid grid-cols-1 md:grid-cols-4 gap-2 pt-1";
    }
    if (stageAudio) stageAudio.classList.remove("hidden");
    if (stageAudioStep) stageAudioStep.textContent = "Paso 1";
    if (stageTranscribeStep) stageTranscribeStep.textContent = "Paso 2";
    if (stageTranscribeDesc) stageTranscribeDesc.textContent = "30% – 75% (Whisper)";
    if (stageGeminiStep) stageGeminiStep.textContent = "Paso 3";
    if (stageDoneStep) stageDoneStep.textContent = "Paso 4";
  } else {
    if (container) {
      container.className = "grid grid-cols-1 md:grid-cols-3 gap-2 pt-1";
    }
    if (stageAudio) stageAudio.classList.add("hidden");
    if (stageTranscribeStep) stageTranscribeStep.textContent = "Paso 1";
    if (stageTranscribeDesc) stageTranscribeDesc.textContent = "0% – 75% (Whisper)";
    if (stageGeminiStep) stageGeminiStep.textContent = "Paso 2";
    if (stageDoneStep) stageDoneStep.textContent = "Paso 3";
  }
}

function updateStageHighlights(p, stage = null) {
  const elAudio = document.getElementById("stageAudio");
  const elTranscribe = document.getElementById("stageTranscribe");
  const elGemini = document.getElementById("stageGemini");
  const elDone = document.getElementById("stageDone");

  if (isYoutubeStepper) {
    if (stage) {
      if (stage === "audio") {
        setStageElementState(elAudio, "active");
        setStageElementState(elTranscribe, "waiting");
        setStageElementState(elGemini, "waiting");
        setStageElementState(elDone, "waiting");
      } else if (stage === "transcribing") {
        setStageElementState(elAudio, "completed");
        setStageElementState(elTranscribe, "active");
        setStageElementState(elGemini, "waiting");
        setStageElementState(elDone, "waiting");
      } else if (stage === "analyzing") {
        setStageElementState(elAudio, "completed");
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "active");
        setStageElementState(elDone, "waiting");
      } else if (stage === "done" || p >= 100.0) {
        setStageElementState(elAudio, "completed");
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "completed");
        setStageElementState(elDone, "completed");
      }
    } else {
      setStageElementState(elAudio, p >= 30.0 ? "completed" : (p > 0.0 ? "active" : "waiting"));
      setStageElementState(elTranscribe, p >= 75.0 ? "completed" : (p >= 30.0 ? "active" : "waiting"));
      setStageElementState(elGemini, p >= 95.0 ? "completed" : (p >= 75.0 ? "active" : "waiting"));
      setStageElementState(elDone, p >= 100.0 ? "completed" : "waiting");
    }
  } else {
    if (stage) {
      if (stage === "audio" || stage === "transcribing") {
        setStageElementState(elAudio, "waiting");
        setStageElementState(elTranscribe, "active");
        setStageElementState(elGemini, "waiting");
        setStageElementState(elDone, "waiting");
      } else if (stage === "analyzing") {
        setStageElementState(elAudio, "waiting");
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "active");
        setStageElementState(elDone, "waiting");
      } else if (stage === "done" || p >= 100.0) {
        setStageElementState(elAudio, "waiting");
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "completed");
        setStageElementState(elDone, "completed");
      }
    } else {
      setStageElementState(elAudio, "waiting");
      setStageElementState(elTranscribe, p >= 75.0 ? "completed" : (p > 0.0 ? "active" : "waiting"));
      setStageElementState(elGemini, p >= 95.0 ? "completed" : (p >= 75.0 ? "active" : "waiting"));
      setStageElementState(elDone, p >= 100.0 ? "completed" : "waiting");
    }
  }
}

function finishProgressTracking(success = true) {
  if (progressPollInterval) {
    clearInterval(progressPollInterval);
    progressPollInterval = null;
  }
  currentTaskId = null;

  if (success) {
    targetProgressPercent = 100.0;
    currentProgressPercent = 100.0;
    progressCurrentStage = "done";
    renderProgressDOM(100.0);

    const titleEl = document.getElementById("procStepTitle");
    const descEl = document.getElementById("procStepDesc");
    if (titleEl) {
      const span = titleEl.querySelector("span:last-child");
      if (span) span.textContent = "¡Finalizado!";
      else titleEl.textContent = "¡Finalizado!";
    }
    if (descEl) descEl.textContent = "Procesamiento completado y Grimorio actualizado.";

    setTimeout(() => {
      stopProgressAnimationLoop();
      hideProcessingCard();
    }, 800);
  } else {
    stopProgressAnimationLoop();
    hideProcessingCard();
  }
}

// Window bindings
window.generateTaskId = generateTaskId;
window.showProcessingCard = showProcessingCard;
window.hideProcessingCard = hideProcessingCard;
window.showErrorCard = showErrorCard;
window.hideErrorCard = hideErrorCard;
window.retryLastAction = retryLastAction;
window.renderProgressDOM = renderProgressDOM;
window.startProgressTracking = startProgressTracking;
window.updateProgressBar = updateProgressBar;
window.updateStepperMode = updateStepperMode;
window.updateStageHighlights = updateStageHighlights;
window.finishProgressTracking = finishProgressTracking;
