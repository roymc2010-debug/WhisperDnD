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

    if (Math.abs(diff) > 0.05) {
      // Easing suave hacia el porcentaje real reportado por el backend
      const step = diff * 0.15;
      currentProgressPercent += step;
    } else {
      currentProgressPercent = targetProgressPercent;
    }

    renderProgressDOM(currentProgressPercent);

    if (currentTaskId || Math.abs(currentProgressPercent - targetProgressPercent) > 0.05) {
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
  const isHidden = el.classList.contains("hidden") || (el.id === "stageAudio" && !isYoutubeStepper);
  const icon = el.querySelector(".stage-icon");
  const baseClasses = "p-2.5 rounded-xl text-left space-y-1 transition-all";

  if (state === "active") {
    el.className = `${baseClasses} border border-amber-500/60 bg-amber-950/30 ring-1 ring-amber-500/50 shadow-md shadow-amber-900/20`;
    if (icon) icon.textContent = "⚡";
  } else if (state === "completed") {
    el.className = `${baseClasses} border border-emerald-500/40 bg-emerald-950/20`;
    if (icon) icon.textContent = "✓";
  } else {
    el.className = `${baseClasses} border border-slate-800 bg-slate-950/60 opacity-60`;
    if (icon) icon.textContent = "⏳";
  }

  if (isHidden) {
    el.classList.add("hidden");
    el.style.display = "none";
  } else {
    el.classList.remove("hidden");
    el.style.display = "";
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
    if (stageAudio) {
      stageAudio.classList.remove("hidden");
      stageAudio.style.display = "";
    }
    if (stageAudioStep) stageAudioStep.textContent = "Paso 1";
    if (stageTranscribeStep) stageTranscribeStep.textContent = "Paso 2";
    if (stageTranscribeDesc) stageTranscribeDesc.textContent = "30% – 75% (Whisper)";
    if (stageGeminiStep) stageGeminiStep.textContent = "Paso 3";
    if (stageDoneStep) stageDoneStep.textContent = "Paso 4";
  } else {
    if (container) {
      container.className = "grid grid-cols-1 md:grid-cols-3 gap-2 pt-1";
    }
    if (stageAudio) {
      stageAudio.classList.add("hidden");
      stageAudio.style.display = "none";
    }
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
  const container = document.getElementById("stepperContainer");

  if (isYoutubeStepper) {
    if (container && !container.className.includes("md:grid-cols-4")) {
      container.className = "grid grid-cols-1 md:grid-cols-4 gap-2 pt-1";
    }
    if (elAudio) {
      elAudio.classList.remove("hidden");
      elAudio.style.display = "";
    }

    if (stage) {
      if (stage === "audio") {
        setStageElementState(elAudio, "active");
        setStageElementState(elTranscribe, "waiting");
        setStageElementState(elGemini, "waiting");
        setStageElementState(elDone, "waiting");
      } else if (stage === "segmenting" || stage === "transcribing") {
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
      setStageElementState(elTranscribe, p >= 80.0 ? "completed" : (p >= 30.0 ? "active" : "waiting"));
      setStageElementState(elGemini, p >= 98.0 ? "completed" : (p >= 80.0 ? "active" : "waiting"));
      setStageElementState(elDone, p >= 100.0 ? "completed" : "waiting");
    }
  } else {
    // Mode Local / En vivo: stageAudio ALWAYS hidden, exactly 3 steps in 1 row
    if (container && !container.className.includes("md:grid-cols-3")) {
      container.className = "grid grid-cols-1 md:grid-cols-3 gap-2 pt-1";
    }
    if (elAudio) {
      elAudio.classList.add("hidden");
      elAudio.style.display = "none";
    }

    if (stage) {
      if (stage === "audio" || stage === "segmenting" || stage === "transcribing") {
        setStageElementState(elTranscribe, "active");
        setStageElementState(elGemini, "waiting");
        setStageElementState(elDone, "waiting");
      } else if (stage === "analyzing") {
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "active");
        setStageElementState(elDone, "waiting");
      } else if (stage === "done" || p >= 100.0) {
        setStageElementState(elTranscribe, "completed");
        setStageElementState(elGemini, "completed");
        setStageElementState(elDone, "completed");
      }
    } else {
      setStageElementState(elTranscribe, p >= 80.0 ? "completed" : (p > 0.0 ? "active" : "waiting"));
      setStageElementState(elGemini, p >= 98.0 ? "completed" : (p >= 80.0 ? "active" : "waiting"));
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
