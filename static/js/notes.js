// =========================================================================
// WhisperDnD - notes.js
// Historial de Apuntes Académicos, Glosario, Tareas y Modal de Términos
// =========================================================================

var academicNotesList = [];
var selectedNoteFilename = null;
var currentActiveNoteDetailTab = 'full'; // 'full' | 'keypoints' | 'tasks'
var currentActiveNoteData = null;

// =========================================================================
// HISTORIAL DE APUNTES & NOTAS ACADÉMICAS
// =========================================================================
async function loadAcademicNotesHistory(showToast = false) {
  const container = document.getElementById("notesListContainer");
  const countBadge = document.getElementById("notesCountBadge");
  if (container) {
    container.innerHTML = `<div class="text-center py-8 text-xs text-slate-500 italic">Cargando apuntes guardados...</div>`;
  }
  try {
    const resp = await fetch("/api/notes");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    academicNotesList = Array.isArray(data) ? data : (data.notes || []);
    if (countBadge) {
      countBadge.textContent = `${academicNotesList.length} nota${academicNotesList.length === 1 ? '' : 's'}`;
    }
    renderAcademicNotesList(academicNotesList);
    if (showToast && typeof showAlert === "function") {
      showAlert(`✓ Se cargaron ${academicNotesList.length} apuntes.`);
    }
  } catch (err) {
    console.error("Error al cargar notas académicas:", err);
    if (container) {
      container.innerHTML = `<div class="text-center py-6 text-xs text-rose-400">Error al cargar notas: ${escapeHtml(err.message)}</div>`;
    }
  }
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

function renderAcademicNotesList(notes) {
  const container = document.getElementById("notesListContainer");
  if (!container) return;
  container.innerHTML = "";

  if (!notes || notes.length === 0) {
    container.innerHTML = `<div class="text-center py-8 text-xs text-slate-500 italic">No hay apuntes registrados aún. Graba una clase o reunión para generar apuntes.</div>`;
    return;
  }

  notes.forEach(note => {
    const isSelected = (selectedNoteFilename === note.filename);
    const card = document.createElement("div");
    card.className = `p-3 rounded-xl border text-xs cursor-pointer transition flex items-start justify-between gap-2.5 ${
      isSelected
        ? "bg-sky-500/15 border-sky-500/40 text-sky-200 shadow-md"
        : "bg-slate-950/70 border-slate-800/80 hover:bg-slate-900 text-slate-300"
    }`;
    card.onclick = () => selectAcademicNote(note.filename);

    const title = cleanNoteDisplayTitle(note.title || note.topic, note.filename);
    const dateStr = note.date || note.created_at || "Sin fecha";
    const wordCount = note.word_count !== undefined ? note.word_count : 0;
    const excerpt = note.excerpt || "Sin extracto.";

    card.innerHTML = `
      <div class="min-w-0 flex-1">
        <div class="font-semibold truncate text-slate-200">${escapeHtml(title)}</div>
        <div class="text-[11px] text-slate-500 font-mono mt-0.5">${escapeHtml(dateStr)} • ${wordCount.toLocaleString()} palabras</div>
        <p class="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">${escapeHtml(excerpt)}</p>
      </div>
      <button type="button" onclick="event.stopPropagation(); deleteAcademicNoteFile('${escapeHtml(note.filename)}')" title="Eliminar apunte"
        class="text-slate-500 hover:text-rose-400 p-1 rounded hover:bg-rose-500/10 transition">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
      </button>
    `;
    container.appendChild(card);
  });
}

function filterAcademicNotes(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) {
    renderAcademicNotesList(academicNotesList);
    return;
  }
  const filtered = (academicNotesList || []).filter(n => {
    const topic = (n.topic || "").toLowerCase();
    const fname = (n.filename || "").toLowerCase();
    const date = (n.date || "").toLowerCase();
    const exc = (n.excerpt || "").toLowerCase();
    return topic.includes(q) || fname.includes(q) || date.includes(q) || exc.includes(q);
  });
  renderAcademicNotesList(filtered);
}

function updateNoteDetailTabUI() {
  const tabFull = document.getElementById("tabNoteViewFull");
  const tabKp = document.getElementById("tabNoteViewKeyPoints");
  const tabTasks = document.getElementById("tabNoteViewTasks");
  const btnCopyText = document.getElementById("btnCopyNoteText");

  const activeClasses = ["bg-sky-600/30", "text-sky-200", "border-sky-500/40", "shadow-sm"];
  const inactiveClasses = ["text-slate-400", "hover:text-slate-200", "hover:bg-slate-800/60", "border-transparent"];

  const applyTabStyle = (el, isActive) => {
    if (!el) return;
    if (isActive) {
      el.classList.remove(...inactiveClasses);
      el.classList.add(...activeClasses);
    } else {
      el.classList.remove(...activeClasses);
      el.classList.add(...inactiveClasses);
    }
  };

  applyTabStyle(tabFull, currentActiveNoteDetailTab === "full");
  applyTabStyle(tabKp, currentActiveNoteDetailTab === "keypoints");
  applyTabStyle(tabTasks, currentActiveNoteDetailTab === "tasks");

  if (btnCopyText) {
    if (currentActiveNoteDetailTab === "keypoints") {
      btnCopyText.textContent = "Copiar Glosario";
    } else if (currentActiveNoteDetailTab === "tasks") {
      btnCopyText.textContent = "Copiar Tareas";
    } else {
      btnCopyText.textContent = "Copiar Apunte";
    }
  }
}

function renderNoteDetailBody() {
  const bodyEl = document.getElementById("noteViewBody");
  if (!bodyEl) return;
  if (!currentActiveNoteData || !currentActiveNoteData.content) {
    bodyEl.innerHTML = `<div class="py-8 text-center text-xs text-slate-500 italic">No hay contenido disponible para este apunte.</div>`;
    return;
  }

  const content = currentActiveNoteData.content;
  if (currentActiveNoteDetailTab === "full") {
    bodyEl.innerHTML = renderMarkdownWithKaTeX(content);
  } else if (currentActiveNoteDetailTab === "keypoints") {
    const keypoints = extractKeyPointsFromMarkdown(content);
    if (keypoints && keypoints.trim()) {
      bodyEl.innerHTML = `
        <div class="space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div class="flex items-center gap-2 text-xs text-slate-300">
              <span class="text-base">📖</span>
              <span class="font-semibold text-sky-300">Glosario & Técnicas Clave</span>
            </div>
            <div class="flex items-center gap-2">
              <input type="text" placeholder="🔍 Buscar concepto..." oninput="filterGlossaryItemsInContainer(this.value, 'noteGlossaryContainer')"
                class="px-2.5 py-1 text-xs rounded-lg bg-slate-950 border border-slate-700 text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none w-44 sm:w-56">
              <button type="button" onclick="openAddGlossaryModal()"
                class="px-3 py-1 rounded-lg bg-sky-600/30 hover:bg-sky-600/50 text-sky-200 border border-sky-500/40 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer">
                <span>➕</span> <span>Agregar Término</span>
              </button>
            </div>
          </div>
          <div id="noteGlossaryContainer" class="prose-dnd text-slate-300 text-xs sm:text-sm leading-relaxed overflow-x-auto space-y-3 font-sans">
            ${renderMarkdownWithKaTeX(keypoints)}
          </div>
        </div>
      `;
    } else {
      bodyEl.innerHTML = `
        <div class="p-8 text-center space-y-3 bg-slate-900/40 rounded-xl border border-dashed border-slate-800">
          <span class="text-3xl">⭐</span>
          <p class="text-xs text-slate-300 font-medium">No se detectaron secciones específicas de glosario o técnicas.</p>
          <p class="text-[11px] text-slate-500">Puedes agregar tus propios conceptos o técnicas a esta nota con el botón a continuación:</p>
          <button type="button" onclick="openAddGlossaryModal()" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-md transition cursor-pointer">
            <span>➕</span> <span>Agregar Término al Glosario</span>
          </button>
        </div>
      `;
    }
  } else if (currentActiveNoteDetailTab === "tasks") {
    const taskItems = extractActionItemsFromMarkdown(content);
    if (taskItems && taskItems.length > 0) {
      bodyEl.innerHTML = `
        <div class="space-y-3">
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <h5 class="text-xs font-semibold text-sky-300 uppercase tracking-wider font-mono">Tareas & Compromisos Asignados</h5>
            <span class="text-[11px] text-slate-400 font-mono">${taskItems.length} tarea${taskItems.length === 1 ? '' : 's'}</span>
          </div>
          <div class="space-y-2">
            ${taskItems.map((item) => `
              <label class="flex items-start gap-3 p-3 rounded-xl bg-slate-900/90 border border-slate-800/80 hover:border-sky-500/40 transition-all cursor-pointer group">
                <input type="checkbox" onchange="
                  const span = this.nextElementSibling;
                  if (this.checked) {
                    span.classList.add('line-through', 'text-slate-500');
                    span.classList.remove('text-slate-200');
                  } else {
                    span.classList.remove('line-through', 'text-slate-500');
                    span.classList.add('text-slate-200');
                  }
                " class="mt-0.5 w-4 h-4 rounded bg-slate-950 border-slate-700 text-sky-500 focus:ring-0 cursor-pointer">
                <span class="text-xs leading-relaxed text-slate-200 transition-all select-none">${escapeHtml(item)}</span>
              </label>
            `).join('')}
          </div>
        </div>
      `;
    } else {
      bodyEl.innerHTML = `
        <div class="p-8 text-center space-y-2 bg-slate-900/40 rounded-xl border border-dashed border-slate-800">
          <span class="text-2xl">📋</span>
          <p class="text-xs text-slate-300 font-medium">No se detectaron tareas ni fechas límite en esta nota.</p>
          <p class="text-[11px] text-slate-500">No se encontraron entregables pendientes en la sección de avisos o compromisos.</p>
        </div>
      `;
    }
  }
}

function switchNoteDetailTab(tab) {
  currentActiveNoteDetailTab = tab;
  updateNoteDetailTabUI();
  renderNoteDetailBody();
}

async function selectAcademicNote(filename) {
  selectedNoteFilename = filename;
  renderAcademicNotesList(academicNotesList);

  const emptyEl = document.getElementById("noteViewerEmpty");
  const contentEl = document.getElementById("noteViewerContent");
  const titleEl = document.getElementById("noteViewTitle");
  const metaEl = document.getElementById("noteViewMeta");
  const bodyEl = document.getElementById("noteViewBody");
  const docxBtn = document.getElementById("btnDownloadNoteDocx");

  if (!emptyEl || !contentEl || !titleEl || !bodyEl) return;

  const note = (academicNotesList || []).find(n => n.filename === filename);
  if (!note) {
    emptyEl.classList.remove("hidden");
    contentEl.classList.add("hidden");
    currentActiveNoteData = null;
    return;
  }

  emptyEl.classList.add("hidden");
  contentEl.classList.remove("hidden");

  currentActiveNoteData = note;
  currentActiveNoteDetailTab = 'full';
  updateNoteDetailTabUI();

  titleEl.textContent = cleanNoteDisplayTitle(note.title || note.topic, note.filename);
  const wordCount = note.word_count !== undefined ? note.word_count : 0;
  if (metaEl) {
    metaEl.textContent = `${note.date || note.created_at || 'Sin fecha'} • ${wordCount.toLocaleString()} palabras • ${note.filename}`;
  }

  const docxFile = note.docx_filename || note.filename.replace(/\.md$/, ".docx");
  if (docxBtn) {
    docxBtn.href = `/api/academic-notes/download/${encodeURIComponent(docxFile)}`;
    docxBtn.classList.remove("hidden");
  }

  const refreshTasksBadge = (mdText) => {
    const tasks = extractActionItemsFromMarkdown(mdText || "");
    const badgeTasks = document.getElementById("badgeNoteTasksCount");
    if (badgeTasks) {
      if (tasks.length > 0) {
        badgeTasks.textContent = tasks.length;
        badgeTasks.classList.remove("hidden");
      } else {
        badgeTasks.classList.add("hidden");
      }
    }
  };

  if (note.content) {
    refreshTasksBadge(note.content);
    renderNoteDetailBody();
  } else {
    bodyEl.innerHTML = `<div class="py-8 text-center text-xs text-slate-500 italic animate-pulse">Cargando contenido del apunte...</div>`;
    try {
      const resp = await fetch(`/api/academic-notes/${encodeURIComponent(filename)}`);
      if (resp.ok) {
        const data = await resp.json();
        note.content = data.content || "";
        note.action_items = data.action_items || [];
        note.key_points = data.key_points || "";
        currentActiveNoteData = note;
        if (data.topic || data.title) {
          note.title = cleanNoteDisplayTitle(data.title || data.topic, data.filename || filename);
          note.topic = note.title;
          titleEl.textContent = note.title;
        }
        if (data.docx_filename && docxBtn) {
          docxBtn.href = `/api/academic-notes/download/${encodeURIComponent(data.docx_filename)}`;
        }
        refreshTasksBadge(note.content);
        renderNoteDetailBody();
      } else {
        bodyEl.innerHTML = `<div class="py-4 text-xs text-rose-400">Error al cargar contenido (${resp.status}).</div>`;
      }
    } catch (err) {
      console.error("Error fetching academic note content:", err);
      bodyEl.innerHTML = `<div class="py-4 text-xs text-rose-400">Error al cargar contenido de la nota.</div>`;
    }
  }
}

function copyCurrentNoteContent() {
  const bodyEl = document.getElementById("noteViewBody");
  const btnText = document.getElementById("btnCopyNoteText");
  if (!bodyEl) return;
  const text = bodyEl.innerText || "";
  if (!text.trim()) return;
  navigator.clipboard.writeText(text).then(() => {
    if (btnText) {
      const old = btnText.textContent;
      btnText.textContent = "✓ ¡Copiado!";
      setTimeout(() => btnText.textContent = old, 2000);
    }
  }).catch(err => {
    console.error("Error copiando:", err);
  });
}

async function deleteAcademicNoteFile(filename) {
  if (!confirm(`¿Eliminar permanentemente "${filename}"?`)) return;
  try {
    const resp = await fetch(`/api/academic-notes/${encodeURIComponent(filename)}`, {
      method: "DELETE"
    });
    if (resp.ok) {
      academicNotesList = academicNotesList.filter(n => n.filename !== filename);
      if (selectedNoteFilename === filename) {
        selectedNoteFilename = null;
        const emptyEl = document.getElementById("noteViewerEmpty");
        const contentEl = document.getElementById("noteViewerContent");
        if (emptyEl) emptyEl.classList.remove("hidden");
        if (contentEl) contentEl.classList.add("hidden");
      }
      renderAcademicNotesList(academicNotesList);
      const countBadge = document.getElementById("notesCountBadge");
      if (countBadge) {
        countBadge.textContent = `${academicNotesList.length} nota${academicNotesList.length === 1 ? '' : 's'}`;
      }
      if (typeof notifyDriveSaveEvent === "function") {
        notifyDriveSaveEvent();
      }
    } else {
      alert("No se pudo eliminar el archivo.");
    }
  } catch (err) {
    console.error("Error eliminando apunte:", err);
  }
}

async function handleAcademicNoteImport(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    if (typeof showAlert === "function") {
      showAlert("Importando apunte y respaldando en Google Drive...");
    }
    const resp = await fetch("/api/academic-notes/import", {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || "Error al importar el apunte.");
    }
    if (typeof showAlert === "function") {
      showAlert(`✓ ${data.message || 'Apunte importado exitosamente.'}`);
    }
    if (typeof notifyDriveSaveEvent === "function") {
      notifyDriveSaveEvent();
    }
    await loadAcademicNotesHistory(false);
  } catch (err) {
    console.error("Error importando apunte:", err);
    alert("Error al importar apunte: " + err.message);
  } finally {
    event.target.value = "";
  }
}

// =========================================================================
// ACTION ITEMS & KEY POINTS EXTRACTION
// =========================================================================
function renderAcademicTasks(tasks) {
  const container = document.getElementById("questsContainer");
  if (!container) return;
  const qBadge = document.getElementById("questCountBadge");

  let taskList = [];
  if (Array.isArray(tasks)) {
    taskList = tasks.map(t => {
      if (typeof t === "string") return { text: t.trim(), completed: false };
      if (t && typeof t === "object") return { text: (t.text || t.title || "").trim(), completed: Boolean(t.completed) };
      return null;
    }).filter(t => t && t.text.length > 0);
  }

  if (qBadge) {
    qBadge.textContent = taskList.length;
  }

  if (taskList.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center space-y-2">
        <span class="text-2xl">📋</span>
        <p class="text-xs text-slate-500 italic">No se detectaron tareas ni fechas límite en esta grabación.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="space-y-2">
      ${taskList.map((task) => `
        <label class="flex items-start gap-3 p-3.5 rounded-xl bg-slate-900/90 border border-slate-800/80 hover:border-sky-500/40 transition-all duration-150 cursor-pointer group">
          <input type="checkbox" ${task.completed ? 'checked' : ''} 
            onchange="
              const span = this.nextElementSibling;
              if (this.checked) {
                span.classList.add('line-through', 'text-slate-500');
                span.classList.remove('text-slate-200');
              } else {
                span.classList.remove('line-through', 'text-slate-500');
                span.classList.add('text-slate-200');
              }
            "
            class="mt-0.5 w-4 h-4 rounded bg-slate-950 border-slate-700 text-sky-500 focus:ring-0 focus:ring-offset-0 cursor-pointer">
          <span class="text-xs leading-relaxed ${task.completed ? 'line-through text-slate-500' : 'text-slate-200'} transition-all duration-150 select-none">${escapeHtml(task.text)}</span>
        </label>
      `).join('')}
    </div>
  `;
}

function extractActionItemsFromMarkdown(md) {
  if (!md || typeof md !== "string") return [];
  const items = [];
  const secTaskMatch = md.match(/(?:^|\n)#+\s*(?:5|6)\.\s*(?!(?:Conclusiones|Key Takeaways|Resumen|Summary))(?:Avisos Relevantes|Avisos|Tareas y Entregables|Tareas y Próximos Pasos|Tareas|Entregables|Pendientes|Announcements|Deadlines|Deliverables).*?\n([\s\S]*?)(?=\n#+\s*\d\.|\Z)/i);
  if (secTaskMatch && secTaskMatch[1]) {
    const lines = secTaskMatch[1].split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      const m = trimmed.match(/^(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+[\.)]\s+)(.+)$/);
      if (m && m[1]) {
        const itemText = m[1].trim();
        if (itemText && !/^(?:no se (?:anunciaron|mencionaron)|no hay|ninguna|ninguno|no assignments|none)/i.test(itemText)) {
          items.push(itemText);
        }
      }
    }
  }

  if (items.length === 0) {
    const taskSubMatch = md.match(/\n\s*(?:Tareas y acuerdos|Acuerdos de acción|Acciones pendientes|Tareas pendientes|Tasks).*?\n([\s\S]*?)(?=\n\s*[-*+]\s*3\s*(?:a|to)\s*5|\n#+|\Z)/i);
    if (taskSubMatch && taskSubMatch[1]) {
      for (const line of taskSubMatch[1].split('\n')) {
        const trimmed = line.trim();
        const m = trimmed.match(/^(?:[-*+]\s*(?:\[[ xX]\]\s*)?|\d+[\.)]\s+)(.+)$/);
        if (m && m[1]) {
          const itemText = m[1].trim();
          if (itemText && !/^(?:no se (?:anunciaron|mencionaron)|no hay|ninguna|ninguno|no assignments|none)/i.test(itemText)) {
            items.push(itemText);
          }
        }
      }
    }
  }
  return items;
}

function extractKeyPointsFromMarkdown(md) {
  if (!md || typeof md !== "string") return "";
  const cleanMd = typeof sanitizeFormulaDelimiters === "function" ? sanitizeFormulaDelimiters(md) : md;
  const sec2Match = cleanMd.match(/(?:^|\n)(?:#{1,2}\s*2\.\s*[^\n]+\n)([\s\S]*?)(?=\n#{1,2}\s*3\.|\Z)/i);
  if (!sec2Match || !sec2Match[1]) return "";

  let sec2Body = sec2Match[1].trim();
  sec2Body = sec2Body.replace(/\n---+/g, "").trim();

  const hasGlossary = /###\s*(?:📖\s*)?Glosario/i.test(sec2Body);
  const hasTech = /###\s*(?:🛠️\s*)?Técnicas/i.test(sec2Body);

  const parts = [];
  if (hasGlossary || hasTech) {
    parts.push(sec2Body);
  } else {
    const bodyClean = sec2Body.replace(/^(?:A continuación[^\n]+\n+|To understand[^\n]+\n+)/i, "").trim();
    parts.push(`### 📖 Glosario Conceptual\n${bodyClean}`);
  }

  if (!hasTech) {
    const techSnippets = [];
    const techRegex = /^(###\s*(?:[^\n]*(?:Estrategia|Técnica|Protocol|Step Strategy|Method|Procedimiento)[^\n]*))\n([\s\S]*?)(?=(?:^#{1,3}\s|\Z))/gmi;
    let match;
    while ((match = techRegex.exec(cleanMd)) !== null) {
      const header = match[1].trim();
      const body = match[2].trim();
      if (body && body.length > 40) {
        techSnippets.push(`${header}\n${body}`);
      }
    }
    if (techSnippets.length > 0) {
      parts.push("### 🛠️ Técnicas y Procedimientos Clave\n" + techSnippets.slice(0, 2).join("\n\n"));
    }
  }

  return parts.join("\n\n---\n\n");
}

// =========================================================================
// GLOSSARY & VOCABULARY MODAL
// =========================================================================
function filterGlossaryItemsInContainer(query, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const q = (query || "").trim().toLowerCase();
  const listItems = container.querySelectorAll("li, p, h3");
  listItems.forEach(el => {
    if (!q) {
      el.style.display = "";
    } else {
      const match = el.textContent.toLowerCase().includes(q);
      el.style.display = match ? "" : "none";
    }
  });
}

function openAddGlossaryModal(prefillWord = "") {
  const modal = document.getElementById("modalAddGlossaryTerm");
  const box = document.getElementById("modalAddGlossaryTermBox");
  const inputTerm = document.getElementById("inputGlossaryTerm");
  const inputDef = document.getElementById("inputGlossaryDefinition");
  if (!modal || !inputTerm) return;

  const selectedText = window.getSelection() ? window.getSelection().toString().trim() : "";
  inputTerm.value = prefillWord || selectedText || "";
  if (inputDef) inputDef.value = "";
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
  setTimeout(() => {
    if (!inputTerm.value) {
      inputTerm.focus();
    } else if (inputDef) {
      inputDef.focus();
    }
  }, 50);
}

function closeAddGlossaryModal() {
  const modal = document.getElementById("modalAddGlossaryTerm");
  const box = document.getElementById("modalAddGlossaryTermBox");
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

async function saveNewGlossaryTerm() {
  const inputTerm = document.getElementById("inputGlossaryTerm");
  const inputDef = document.getElementById("inputGlossaryDefinition");
  const selectType = document.getElementById("selectGlossaryType");
  if (!inputTerm || !inputDef) return;

  const term = inputTerm.value.trim();
  const def = inputDef.value.trim();
  const type = selectType ? selectType.value : "concept";

  if (!term) {
    alert("Por favor ingresa la palabra o concepto.");
    return;
  }
  if (!def) {
    alert("Por favor ingresa la definición o explicación.");
    return;
  }

  const entryLine = `- **${term}**: ${def}`;

  if (currentActiveNoteData && currentActiveNoteData.filename) {
    let md = currentActiveNoteData.content || "";
    const sec2HeaderMatch = md.match(/(#+\s*2\.\s*(?:Conceptos Teóricos|Conceptos|Glosario|Fundamental Theoretical|Theoretical Concepts|Theoretical|Glossary|Key Concepts|Terminology).*?\n)/i);
    if (sec2HeaderMatch) {
      if (type === "technique") {
        const techMatch = md.match(/###\s*(?:🛠️\s*)?(?:Técnicas|Key Techniques|Procedimientos).*?\n/i);
        if (techMatch) {
          const insertIdx = techMatch.index + techMatch[0].length;
          md = md.slice(0, insertIdx) + entryLine + "\n" + md.slice(insertIdx);
        } else {
          const insertIdx = sec2HeaderMatch.index + sec2HeaderMatch[0].length;
          md = md.slice(0, insertIdx) + "### 🛠️ Técnicas, Métodos y Cuándo se Usan\n" + entryLine + "\n\n" + md.slice(insertIdx);
        }
      } else {
        const glossMatch = md.match(/###\s*(?:📖\s*)?(?:Glosario|Conceptual Glossary).*?\n/i);
        if (glossMatch) {
          const insertIdx = glossMatch.index + glossMatch[0].length;
          md = md.slice(0, insertIdx) + entryLine + "\n" + md.slice(insertIdx);
        } else {
          const insertIdx = sec2HeaderMatch.index + sec2HeaderMatch[0].length;
          md = md.slice(0, insertIdx) + "### 📖 Glosario Conceptual\n" + entryLine + "\n" + md.slice(insertIdx);
        }
      }
    } else {
      md += `\n\n# 2. Conceptos Teóricos Fundamentales y Glosario\n### 📖 Glosario Conceptual\n${entryLine}\n`;
    }

    currentActiveNoteData.content = md;

    try {
      await fetch('/api/academic-notes/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: currentActiveNoteData.filename,
          content: md,
          subject: currentActiveNoteData.subject || "Materia",
          topic: currentActiveNoteData.topic || currentActiveNoteData.title || "Apuntes"
        })
      });
    } catch (e) {
      console.warn("Could not save updated note to backend:", e);
    }

    closeAddGlossaryModal();
    renderNoteDetailBody();
    if (typeof showSuccessAlert === "function") {
      showSuccessAlert(`✓ Término "${term}" guardado en el glosario.`);
    } else if (typeof showAlert === "function") {
      showAlert(`✓ Término "${term}" guardado en el glosario.`);
    }
    return;
  }

  if (typeof currentResult !== "undefined" && currentResult && (currentResult.chronicle_markdown || currentResult.chronicle)) {
    let md = currentResult.chronicle_markdown || currentResult.chronicle || "";
    const sec2HeaderMatch = md.match(/(#+\s*2\.\s*(?:Conceptos Teóricos|Conceptos|Glosario|Fundamental Theoretical|Theoretical Concepts|Theoretical|Glossary|Key Concepts|Terminology).*?\n)/i);
    if (sec2HeaderMatch) {
      const insertIdx = sec2HeaderMatch.index + sec2HeaderMatch[0].length;
      md = md.slice(0, insertIdx) + entryLine + "\n" + md.slice(insertIdx);
    } else {
      md += `\n\n# 2. Conceptos Teóricos Fundamentales y Glosario\n### 📖 Glosario Conceptual\n${entryLine}\n`;
    }
    currentResult.chronicle_markdown = md;
    currentResult.chronicle = md;
    closeAddGlossaryModal();
    if (typeof displayResults === "function") {
      displayResults(currentResult);
    }
    if (typeof showSuccessAlert === "function") {
      showSuccessAlert(`✓ Término "${term}" guardado en el glosario.`);
    }
    return;
  }

  closeAddGlossaryModal();
}

// Window Global Exports
window.loadAcademicNotesHistory = loadAcademicNotesHistory;
window.cleanNoteDisplayTitle = cleanNoteDisplayTitle;
window.renderAcademicNotesList = renderAcademicNotesList;
window.filterAcademicNotes = filterAcademicNotes;
window.updateNoteDetailTabUI = updateNoteDetailTabUI;
window.renderNoteDetailBody = renderNoteDetailBody;
window.switchNoteDetailTab = switchNoteDetailTab;
window.selectAcademicNote = selectAcademicNote;
window.copyCurrentNoteContent = copyCurrentNoteContent;
window.deleteAcademicNoteFile = deleteAcademicNoteFile;
window.handleAcademicNoteImport = handleAcademicNoteImport;
window.renderAcademicTasks = renderAcademicTasks;
window.extractActionItemsFromMarkdown = extractActionItemsFromMarkdown;
window.extractKeyPointsFromMarkdown = extractKeyPointsFromMarkdown;
window.filterGlossaryItemsInContainer = filterGlossaryItemsInContainer;
window.openAddGlossaryModal = openAddGlossaryModal;
window.closeAddGlossaryModal = closeAddGlossaryModal;
window.saveNewGlossaryTerm = saveNewGlossaryTerm;
