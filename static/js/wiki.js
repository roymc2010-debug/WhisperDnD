// =========================================================================
// WhisperDnD - wiki.js
// Explorador de Campaña, Fichas de Personajes, Quests, PNJs, PCs y Fusión
// =========================================================================

var activeWikiCategory = "quests"; // "quests" | "npcs" | "pcs" | "locations" | "items" | "sessions"
var selectedWikiEntity = null;     // { type: string, key: string, data: any }
var currentWikiCampaignState = null;
var wikiFilterQuery = "";
var currentWikiSessionData = null;
var currentWikiSessionSubtab = 'chronicle'; // 'chronicle' or 'transcript'
var detectedNpcNamesList = [];

// =========================================================================
// MI PERSONAJE — Character Backstory View
// =========================================================================
var currentCampaignRosterCache = [];
var isNewCharacterMode = false;

function syncWikiCampaignSelector(campName) {
  const select = document.getElementById("wikiCampaignSelect");
  if (!select) return;
  if (!campName || !campName.trim()) {
    select.value = "";
    return;
  }
  const target = campName.trim().toLowerCase();
  let found = false;
  for (let i = 0; i < select.options.length; i++) {
    if (select.options[i].value.toLowerCase() === target) {
      select.selectedIndex = i;
      found = true;
      break;
    }
  }
  if (!found) {
    const opt = document.createElement("option");
    opt.value = campName.trim();
    opt.textContent = campName.trim();
    select.appendChild(opt);
    select.value = campName.trim();
  }
}

async function loadCharacterView() {
  const badge = document.getElementById("characterBackstorySavedBadge");
  if (badge) badge.classList.add("hidden");

  const campaignSelect = document.getElementById("characterProfileCampaign");
  if (!campaignSelect) return;

  const prevCampaign = campaignSelect.value;
  campaignSelect.innerHTML = '<option value="">— Selecciona una campaña —</option>';

  try {
    const res = await fetch("/api/campaigns");
    if (res.ok) {
      const data = await res.json();
      const campaigns = data.campaigns || data || [];
      let targetCampaign = prevCampaign;
      campaigns.forEach(c => {
        const name = typeof c === "string" ? c : (c.campaign_name || c.name || "");
        if (!name) return;
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        campaignSelect.appendChild(opt);
        if (!targetCampaign && (name.toLowerCase() === "candlekeep 2.0" || name.toLowerCase().includes("candlekeep"))) {
          targetCampaign = name;
        }
      });

      if (!targetCampaign && campaigns.length > 0) {
        const first = campaigns[0];
        targetCampaign = typeof first === "string" ? first : (first.campaign_name || first.name || "");
      }

      if (targetCampaign) {
        campaignSelect.value = targetCampaign;
        await loadCharactersForCampaign(targetCampaign);
      }
    }
  } catch (e) {
    console.warn("[Mi Personaje] Error cargando campañas:", e);
  }
}

async function loadCharactersForCampaign(campaignName, selectCharName = null) {
  if (!campaignName) {
    currentCampaignRosterCache = [];
    renderCharacterSelectDropdown([], null);
    const textarea = document.getElementById("characterBackstoryInput");
    if (textarea) textarea.value = "";
    return;
  }

  const textarea = document.getElementById("characterBackstoryInput");

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}`);
    if (res.ok) {
      const data = await res.json();
      const state = data.campaign_state || data || {};
      const roster = state.roster || [];
      const universalPcs = state.universal_pcs || [];
      const charBackstories = state.character_backstories || {};
      const userBackstory = state.user_character_backstory || "";

      // Extraer PCs distintos (excluyendo DM)
      const charsMap = new Map();
      roster.forEach(m => {
        if (!m || typeof m !== "object") return;
        const cname = (m.character_name || "").trim();
        if (!cname || cname.toLowerCase() === "(dm)" || cname.toLowerCase() === "dm" || cname.toLowerCase() === "dungeon master") return;
        const isUser = Boolean(m.is_user_character || m.is_user);
        const specificBackstory = m.backstory || charBackstories[cname] || (isUser ? userBackstory : "");
        charsMap.set(cname.toLowerCase(), {
          name: cname,
          player: m.player_name || "",
          role: m.role || "",
          species: m.species || "",
          is_user: isUser,
          backstory: specificBackstory,
        });
      });

      universalPcs.forEach(u => {
        if (!u || typeof u !== "object") return;
        const cname = (u.personaje || u.character_name || "").trim();
        if (!cname || cname.toLowerCase() === "(dm)" || cname.toLowerCase() === "dm" || cname.toLowerCase() === "dungeon master") return;
        const key = cname.toLowerCase();
        if (!charsMap.has(key)) {
          charsMap.set(key, {
            name: cname,
            player: u.jugador || u.player_name || "",
            role: u.clase || u.role || "",
            species: u.raza || u.species || "",
            is_user: false,
            backstory: u.trasfondo || charBackstories[cname] || "",
          });
        }
      });

      Object.keys(charBackstories).forEach(cname => {
        const key = cname.trim().toLowerCase();
        if (key && !charsMap.has(key)) {
          charsMap.set(key, {
            name: cname.trim(),
            player: "",
            role: "",
            species: "",
            is_user: false,
            backstory: charBackstories[cname] || "",
          });
        }
      });

      currentCampaignRosterCache = Array.from(charsMap.values());
      currentCampaignRosterCache.sort((a, b) => {
        if (a.is_user !== b.is_user) return a.is_user ? -1 : 1;
        return a.name.localeCompare(b.name);
      });

      let chosenChar = null;
      if (selectCharName) {
        chosenChar = currentCampaignRosterCache.find(c => c.name.toLowerCase() === selectCharName.toLowerCase());
      }
      if (!chosenChar) {
        chosenChar = currentCampaignRosterCache.find(c => c.is_user) || (currentCampaignRosterCache.length > 0 ? currentCampaignRosterCache[0] : null);
      }

      renderCharacterSelectDropdown(currentCampaignRosterCache, chosenChar ? chosenChar.name : null);

      if (chosenChar) {
        onUserCharacterSelected(chosenChar.name);
      } else {
        if (textarea) textarea.value = "";
      }
    }
  } catch (e) {
    console.warn("[Mi Personaje] Error cargando personajes de campaña:", e);
  }
}

function renderCharacterSelectDropdown(charList, selectedName) {
  const charSelect = document.getElementById("userCharacterSelect");
  if (!charSelect) return;

  charSelect.innerHTML = "";
  if (!charList || charList.length === 0) {
    charSelect.innerHTML = '<option value="">— Ningún personaje registrado en esta campaña —</option>';
    return;
  }

  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = "— Selecciona un personaje de la campaña —";
  charSelect.appendChild(defaultOpt);

  charList.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.name;
    const star = c.is_user ? "Mi personaje · " : "";
    const roleInfo = [c.role, c.species].filter(Boolean).join(", ");
    const playerInfo = c.player ? ` [${c.player}]` : "";
    const details = roleInfo ? ` (${roleInfo}${playerInfo})` : (playerInfo ? ` (${playerInfo.trim()})` : "");
    opt.textContent = `${star}${c.name}${details}`;
    charSelect.appendChild(opt);
  });

  if (selectedName) {
    charSelect.value = selectedName;
  }
}

function onCampaignDropdownChanged(campName) {
  if (isNewCharacterMode) {
    const textarea = document.getElementById("characterBackstoryInput");
    if (textarea) textarea.value = "";
  } else {
    loadCharactersForCampaign(campName);
  }
}

function onUserCharacterSelected(charName) {
  const textarea = document.getElementById("characterBackstoryInput");
  const chkIsUser = document.getElementById("chkIsUserCharacter");
  const nameInput = document.getElementById("characterProfileName");

  if (nameInput) nameInput.value = charName || "";

  if (!charName) {
    if (textarea) textarea.value = "";
    return;
  }

  const found = currentCampaignRosterCache.find(c => c.name.toLowerCase() === charName.toLowerCase());
  if (found) {
    if (textarea) textarea.value = found.backstory || "";
    if (chkIsUser) chkIsUser.checked = Boolean(found.is_user);
  } else {
    if (textarea) textarea.value = "";
  }
}

function toggleNewCharacterMode(forceMode) {
  const selectContainer = document.getElementById("characterSelectContainer");
  const inputContainer = document.getElementById("newCharacterInputContainer");
  const labelToggle = document.getElementById("labelToggleNewChar");
  const nameInput = document.getElementById("characterProfileName");
  const textarea = document.getElementById("characterBackstoryInput");
  const chkIsUser = document.getElementById("chkIsUserCharacter");

  if (typeof forceMode === "boolean") {
    isNewCharacterMode = forceMode;
  } else {
    isNewCharacterMode = !isNewCharacterMode;
  }

  if (isNewCharacterMode) {
    if (selectContainer) selectContainer.classList.add("hidden");
    if (inputContainer) inputContainer.classList.remove("hidden");
    if (labelToggle) labelToggle.textContent = "Seleccionar Existente";
    if (nameInput) {
      nameInput.value = "";
      nameInput.focus();
    }
    if (textarea) textarea.value = "";
    if (chkIsUser) chkIsUser.checked = true;
  } else {
    if (selectContainer) selectContainer.classList.remove("hidden");
    if (inputContainer) inputContainer.classList.add("hidden");
    if (labelToggle) labelToggle.textContent = "Crear Nuevo Personaje";
    const charSelect = document.getElementById("userCharacterSelect");
    if (charSelect && charSelect.value) {
      onUserCharacterSelected(charSelect.value);
    }
  }
}

async function saveCharacterBackstory() {
  const campaignSelect = document.getElementById("characterProfileCampaign");
  const nameInput  = document.getElementById("characterProfileName");
  const charSelect = document.getElementById("userCharacterSelect");
  const textarea   = document.getElementById("characterBackstoryInput");
  const chkIsUser  = document.getElementById("chkIsUserCharacter");
  const badge      = document.getElementById("characterBackstorySavedBadge");
  const btn        = document.getElementById("btnSaveCharacterBackstory");

  const campaignName = campaignSelect?.value?.trim();
  let charName = "";

  if (isNewCharacterMode) {
    charName = nameInput?.value?.trim();
  } else {
    charName = charSelect?.value?.trim();
    if (!charName && nameInput?.value?.trim()) {
      charName = nameInput.value.trim();
    }
  }

  if (!campaignName) { alert("Selecciona una campaña primero."); return; }
  if (!charName)     { alert("Escribe o selecciona el nombre de un personaje."); return; }
  if (!textarea)     return;

  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}/character-backstory`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        backstory: textarea.value,
        character_name: charName,
        is_user_character: chkIsUser ? chkIsUser.checked : true
      }),
    });
    if (res.ok) {
      if (badge) {
        badge.classList.remove("hidden");
        setTimeout(() => badge.classList.add("hidden"), 3000);
      }
      if (isNewCharacterMode) {
        toggleNewCharacterMode(false);
      }
      await loadCharactersForCampaign(campaignName, charName);
    } else {
      alert("Error guardando el trasfondo. Intenta de nuevo.");
    }
  } catch (e) {
    alert("Error de red al guardar. Revisa que el servidor esté corriendo.");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// =========================================================================
// CAMPAIGN WIKI EXPLORER
// =========================================================================
async function refreshWikiCampaigns() {
  const select = document.getElementById("wikiCampaignSelect");
  if (!select) return;
  const currentVal = (select.value || "").trim();
  try {
    const res = await fetch("/api/campaigns");
    if (res.ok) {
      const list = await res.json();
      select.innerHTML = '<option value="">-- Seleccionar Campaña --</option>';
      let valFound = false;
      list.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.name;
        opt.textContent = `${c.name} (${c.sessions_count || c.total_sessions || 0} sesiones)`;
        select.appendChild(opt);
        if (currentVal && c.name.toLowerCase() === currentVal.toLowerCase()) {
          valFound = true;
        }
      });
      if (currentVal && valFound) {
        select.value = currentVal;
      }
    }
  } catch (err) {
    console.warn("Error refreshing wiki campaigns:", err);
  }
}

async function onWikiCampaignSelected(campName) {
  const emptyState = document.getElementById("wikiEmptyCampaignState");
  const explorerLayout = document.getElementById("wikiExplorerLayout");
  const select = document.getElementById("wikiCampaignSelect");

  if (!campName || !campName.trim()) {
    currentWikiCampaignState = null;
    selectedWikiEntity = null;
    if (select) select.value = "";
    if (emptyState) emptyState.classList.remove("hidden");
    if (explorerLayout) explorerLayout.classList.add("hidden");
    return;
  }

  const cleanName = campName.trim();
  if (select && select.value !== cleanName) {
    syncWikiCampaignSelector(cleanName);
  }

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(cleanName)}`);
    if (res.ok) {
      const data = await res.json();
      currentWikiCampaignState = data.campaign_state || { quests: [], npcs: [], universal_pcs: [] };
      if (!currentWikiCampaignState.campaign_name) {
        currentWikiCampaignState.campaign_name = cleanName;
      }
      selectedWikiEntity = null;
      if (emptyState) emptyState.classList.add("hidden");
      if (explorerLayout) explorerLayout.classList.remove("hidden");
      renderWikiCategoryPills();
      renderWikiEntityList();
      renderWikiDossier();
      updateWikiSessionExportSelect(currentWikiCampaignState);
    } else {
      currentWikiCampaignState = null;
      if (emptyState) emptyState.classList.remove("hidden");
      if (explorerLayout) explorerLayout.classList.add("hidden");
    }
  } catch (err) {
    console.error("Error loading wiki campaign data:", err);
    currentWikiCampaignState = null;
    if (emptyState) emptyState.classList.remove("hidden");
    if (explorerLayout) explorerLayout.classList.add("hidden");
  }
}

async function refreshWikiView() {
  await refreshWikiCampaigns();
  const select = document.getElementById("wikiCampaignSelect");
  const mainCampInput = document.getElementById("campaignNameInput") || document.getElementById("campaignSelect");
  const currentMain = (mainCampInput && mainCampInput.value) ? mainCampInput.value.trim() : "";
  const currentSelect = (select && select.value) ? select.value.trim() : "";

  const targetCamp = currentSelect || currentMain;

  if (targetCamp) {
    syncWikiCampaignSelector(targetCamp);
    await onWikiCampaignSelected(targetCamp);
    return;
  }

  if (select) select.value = "";
  currentWikiCampaignState = null;
  selectedWikiEntity = null;
  const emptyState = document.getElementById("wikiEmptyCampaignState");
  const explorerLayout = document.getElementById("wikiExplorerLayout");
  if (emptyState) emptyState.classList.remove("hidden");
  if (explorerLayout) explorerLayout.classList.add("hidden");
}

function setWikiCategory(cat) {
  activeWikiCategory = cat;
  selectedWikiEntity = null;
  renderWikiCategoryPills();
  renderWikiEntityList();
  renderWikiDossier();
}

function renderWikiCategoryPills() {
  const pillQuests = document.getElementById("wikiPillQuests");
  const pillNpcs = document.getElementById("wikiPillNpcs");
  const pillPcs = document.getElementById("wikiPillPcs");
  const pillLocations = document.getElementById("wikiPillLocations");
  const pillItems = document.getElementById("wikiPillItems");
  const pillSessions = document.getElementById("wikiPillSessions");

  const state = currentWikiCampaignState || {};
  const quests = state.quests || [];
  const npcs = state.npcs || [];
  const pcs = state.universal_pcs || [];
  const locations = state.locations || [];
  const items = state.items || [];
  const sessionCount = (state.chronicles?.length || state.sessions?.length || Object.keys(state.history || {}).length || 0);

  const qCounter = document.getElementById("wikiQuestsCounter");
  if (qCounter) qCounter.textContent = quests.length;
  const nCounter = document.getElementById("wikiNpcsCounter");
  if (nCounter) nCounter.textContent = npcs.length;
  const pCounter = document.getElementById("wikiPcsCounter");
  if (pCounter) pCounter.textContent = pcs.length;
  const lCounter = document.getElementById("wikiLocationsCounter");
  if (lCounter) lCounter.textContent = locations.length;
  const iCounter = document.getElementById("wikiItemsCounter");
  if (iCounter) iCounter.textContent = items.length;
  const sCounter = document.getElementById("wikiSessionsCounter");
  if (sCounter) sCounter.textContent = sessionCount;

  const activeClass = "min-h-[46px] px-3 py-2.5 rounded-xl text-sm font-bold transition flex items-center justify-between gap-2 bg-[#1c1c24] text-white border border-white/20 cursor-pointer shadow-sm active:scale-95";
  const inactiveClass = "min-h-[46px] px-3 py-2.5 rounded-xl text-sm font-semibold transition flex items-center justify-between gap-2 text-neutral-400 hover:text-white hover:bg-[#14141a] border border-[#222228] cursor-pointer active:scale-95";

  if (pillQuests) pillQuests.className = (activeWikiCategory === "quests") ? activeClass : inactiveClass;
  if (pillNpcs) pillNpcs.className = (activeWikiCategory === "npcs") ? activeClass : inactiveClass;
  if (pillPcs) pillPcs.className = (activeWikiCategory === "pcs") ? activeClass : inactiveClass;
  if (pillLocations) pillLocations.className = (activeWikiCategory === "locations") ? activeClass : inactiveClass;
  if (pillItems) pillItems.className = (activeWikiCategory === "items") ? activeClass : inactiveClass;
  if (pillSessions) pillSessions.className = (activeWikiCategory === "sessions") ? activeClass : inactiveClass;

  const pillCounters = [
    { el: qCounter, cat: "quests" },
    { el: nCounter, cat: "npcs" },
    { el: pCounter, cat: "pcs" },
    { el: lCounter, cat: "locations" },
    { el: iCounter, cat: "items" },
    { el: sCounter, cat: "sessions" }
  ];
  pillCounters.forEach(c => {
    if (!c.el) return;
    if (activeWikiCategory === c.cat) {
      c.el.className = "text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-white/15 text-white border border-white/20 shrink-0";
    } else {
      c.el.className = "text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-[#14141a] text-neutral-400 border border-white/10 shrink-0";
    }
  });
}

function onWikiSearchInput() {
  const input = document.getElementById("wikiSearchInput");
  wikiFilterQuery = (input && input.value) ? input.value.trim().toLowerCase() : "";
  renderWikiEntityList();
}

function renderWikiEntityList() {
  const listEl = document.getElementById("wikiEntityList");
  if (!listEl) return;
  listEl.innerHTML = "";

  const state = currentWikiCampaignState || {};
  const query = (wikiFilterQuery || "").toLowerCase();

  if (activeWikiCategory === "quests") {
    const quests = (state.quests || []).filter(q => {
      if (!query) return true;
      const t = (q.title || "").toLowerCase();
      const c = (q.context || "").toLowerCase();
      const tp = (q.tipo || "").toLowerCase();
      return t.includes(query) || c.includes(query) || tp.includes(query);
    });

    if (quests.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No se encontraron misiones.</p>`;
      return;
    }

    quests.forEach(q => {
      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "quest" && selectedWikiEntity.key === q.id;
      const isCompleted = q.status === "completed";
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("quest", q.id, q);

      const badge = isCompleted
        ? '<span class="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"><span data-ui-icon=check aria-hidden=true></span> Hecha</span>'
        : '<span class="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-white/10 text-white border border-white/20">● Activa</span>';

      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(q.title || "Misión sin título")}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(q.tipo || "Principal")}</div>
        </div>
        ${badge}
      `;
      listEl.appendChild(card);
    });
  } else if (activeWikiCategory === "npcs") {
    const npcs = (state.npcs || []).filter(n => {
      if (!query) return true;
      const nm = (n.name || n.nombre || n.personaje || n.character_name || "").toLowerCase();
      const desc = (n.description || n.descripcion || n.detalles || n.rol_en_sesion || n.role || "").toLowerCase();
      return nm.includes(query) || desc.includes(query);
    });

    if (npcs.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No se encontraron PNJs.</p>`;
      return;
    }

    npcs.forEach(n => {
      const npcName = n.name || n.nombre || n.personaje || n.character_name || "Sin nombre";
      const npcDesc = n.description || n.descripcion || n.detalles || n.rol_en_sesion || n.role || n.session_role || (Array.isArray(n.notes) && n.notes[0]) || "Sin descripción disponible";
      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "npc" && selectedWikiEntity.key === (n.name || npcName);
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("npc", n.name || npcName, n);

      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(npcName)}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(npcDesc)}</div>
        </div>
      `;
      listEl.appendChild(card);
    });
  } else if (activeWikiCategory === "pcs") {
    const pcs = (state.universal_pcs || []).filter(p => {
      if (!query) return true;
      const nm = (p.name || p.nombre || p.personaje || p.character_name || "").toLowerCase();
      const pl = (p.player_name || p.jugador || p.player || "").toLowerCase();
      const cl = (p.character_class || p.clase || p.class || p.role || "").toLowerCase();
      return nm.includes(query) || pl.includes(query) || cl.includes(query);
    });

    if (pcs.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No se encontraron protagonistas (PCs).</p>`;
      return;
    }

    pcs.forEach(p => {
      const pcName = p.name || p.nombre || p.personaje || p.character_name || "Sin nombre";
      const pcPlayer = p.player_name || p.jugador || p.player || "";
      const pcClass = p.character_class || p.clase || p.class || p.role || "Aventurero";
      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "pc" && selectedWikiEntity.key === (p.name || pcName);
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("pc", p.name || pcName, p);

      const subText = pcPlayer ? `${pcClass} • ${pcPlayer}` : pcClass;
      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(pcName)}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(subText)}</div>
        </div>
      `;
      listEl.appendChild(card);
    });
  } else if (activeWikiCategory === "locations") {
    const locs = (state.locations || []).filter(l => {
      if (!query) return true;
      const nm = (l.name || "").toLowerCase();
      const desc = (l.description || "").toLowerCase();
      return nm.includes(query) || desc.includes(query);
    });

    if (locs.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No hay lugares registrados todavía en esta campaña.</p>`;
      return;
    }

    locs.forEach(l => {
      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "location" && selectedWikiEntity.key === l.name;
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("location", l.name, l);

      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(l.name || "Lugar")}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(l.type || "Ubicación")}</div>
        </div>
      `;
      listEl.appendChild(card);
    });
  } else if (activeWikiCategory === "items") {
    const items = (state.items || []).filter(it => {
      if (!query) return true;
      const nm = (it.name || "").toLowerCase();
      const desc = (it.description || "").toLowerCase();
      return nm.includes(query) || desc.includes(query);
    });

    if (items.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No hay objetos o facciones registrados todavía en esta campaña.</p>`;
      return;
    }

    items.forEach(it => {
      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "item" && selectedWikiEntity.key === it.name;
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("item", it.name, it);

      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(it.name || "Objeto")}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(it.type || "Artefacto / Facción")}</div>
        </div>
      `;
      listEl.appendChild(card);
    });
  } else if (activeWikiCategory === "sessions") {
    const rawSessions = state.sessions || state.chronicles || [];
    const sessionList = Array.isArray(rawSessions) ? rawSessions : Object.values(rawSessions);
    const sessions = sessionList.filter(s => {
      if (!query) return true;
      const num = String(s.session_number || s.number || "");
      const sm = (s.summary || s.chronicle_text || s.title || "").toLowerCase();
      const dt = (s.date || "").toLowerCase();
      return num.includes(query) || sm.includes(query) || dt.includes(query);
    });

    if (sessions.length === 0) {
      listEl.innerHTML = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No hay sesiones registradas todavía en esta campaña.</p>`;
      return;
    }

    sessions.forEach(s => {
      const num = s.session_number || s.number || "1";
      const rawTitle = (s.session_title || s.title || "").trim();
      const cleanTitle = rawTitle.replace(/^(?:sesi[oó]n|session)\s*#?\d+\s*[:\-]\s*/i, "").trim();
      const displayTitle = cleanTitle ? `Sesión #${num}: ${cleanTitle}` : `Sesión #${num}`;

      const isSelected = selectedWikiEntity && selectedWikiEntity.type === "session" && selectedWikiEntity.key === (s.session_number || num);
      const card = document.createElement("div");
      card.className = `p-3.5 rounded-xl border text-xs cursor-pointer transition-all duration-150 flex items-center justify-between gap-3 ${
        isSelected
          ? "bg-white/10 border-white/25 text-white shadow-sm"
          : "bg-[#0d0d0d] border-[#222222] hover:border-[#333333] hover:bg-[#141414] text-neutral-300"
      }`;
      card.onclick = () => selectWikiEntity("session", s.session_number || num, s);

      card.innerHTML = `
        <div class="min-w-0 flex-1">
          <div class="text-sm font-semibold truncate text-neutral-100">${escapeHtml(displayTitle)}</div>
          <div class="text-xs sm:text-[13px] text-neutral-300 font-medium truncate mt-1">${escapeHtml(s.date || "Sin fecha")} • ${escapeHtml(s.summary || "Capítulo de campaña")}</div>
        </div>
      `;
      listEl.appendChild(card);
    });
  }
}

async function selectWikiEntity(type, key, data) {
  selectedWikiEntity = { type, key, data };
  renderWikiEntityList();

  if (type === "session" && (!data.chronicle_markdown || !data.raw_transcript)) {
    const sel = document.getElementById("wikiCampaignSelect");
    const campName = (sel && sel.value) ? sel.value.trim() : "";
    if (campName && data.session_number) {
      try {
        const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/session/${data.session_number}`);
        if (res.ok) {
          const detail = await res.json();
          selectedWikiEntity.data.chronicle_markdown = detail.chronicle_markdown || selectedWikiEntity.data.chronicle_markdown;
          selectedWikiEntity.data.raw_transcript = detail.raw_transcript || selectedWikiEntity.data.raw_transcript;
        }
      } catch (err) {
        console.warn("Could not load full session transcript/chronicle:", err);
      }
    }
  }

  renderWikiDossier();
}

function findAndSelectWikiEntity(type, entityName) {
  if (!entityName) return;
  const state = currentWikiCampaignState || {};
  const targetLower = String(entityName).toLowerCase().trim();

  if (type === 'pc') {
    const found = (state.universal_pcs || []).find(p => (p.name || p.nombre || p.personaje || "").toLowerCase().trim() === targetLower);
    if (found) {
      activeWikiCategory = "pcs";
      renderWikiCategoryPills();
      selectWikiEntity('pc', found.name || found.personaje || entityName, found);
      return;
    }
  } else if (type === 'npc') {
    const found = (state.npcs || []).find(n => (n.name || n.nombre || "").toLowerCase().trim() === targetLower);
    if (found) {
      activeWikiCategory = "npcs";
      renderWikiCategoryPills();
      selectWikiEntity('npc', found.name || entityName, found);
      return;
    }
  } else if (type === 'location') {
    const found = (state.locations || []).find(l => (l.name || "").toLowerCase().trim() === targetLower);
    if (found) {
      activeWikiCategory = "locations";
      renderWikiCategoryPills();
      selectWikiEntity('location', found.name || entityName, found);
      return;
    }
  } else if (type === 'item') {
    const found = (state.items || []).find(it => (it.name || "").toLowerCase().trim() === targetLower);
    if (found) {
      activeWikiCategory = "items";
      renderWikiCategoryPills();
      selectWikiEntity('item', found.name || entityName, found);
      return;
    }
  }
}

function formatCharacterDisplayName(fullName, aliases) {
  if (!fullName) return fullName || "";
  let name = String(fullName).trim();
  if (name.includes('"') || name.includes("'")) {
    return name;
  }
  if (!aliases || !Array.isArray(aliases) || aliases.length === 0) {
    return name;
  }

  const words = name.split(/\s+/);
  const firstName = words[0];

  for (const rawAlias of aliases) {
    const alias = String(rawAlias).trim();
    if (!alias) continue;
    const lowerAlias = alias.toLowerCase();
    const lowerFirst = firstName.toLowerCase();
    if (
      lowerAlias.length >= 3 &&
      (lowerFirst.startsWith(lowerAlias) || lowerAlias.startsWith(lowerFirst.replace(/[^a-z0-9]/g, ""))) &&
      lowerAlias !== lowerFirst
    ) {
      const rest = words.slice(1).join(" ");
      return rest ? `${firstName} "${alias}" ${rest}` : `${firstName} "${alias}"`;
    }
  }
  return name;
}

function getCleanNarrativeAliases(fullName, aliases) {
  if (!aliases || !Array.isArray(aliases)) return [];
  const name = String(fullName || "").toLowerCase().trim();
  const nameWords = name.split(/\s+/).map(w => w.replace(/[^\w]/g, "")).filter(Boolean);
  const firstName = nameWords[0] || "";

  return aliases.map(a => String(a).trim()).filter(alias => {
    if (!alias) return false;
    const lowerAlias = alias.toLowerCase();
    if (lowerAlias === name) return false;
    if (nameWords.includes(lowerAlias.replace(/[^\w]/g, ""))) return false;

    // Short-form callsign already in display name (e.g. "John" in Johngalli)
    if (
      lowerAlias.length >= 3 &&
      (firstName.startsWith(lowerAlias) || lowerAlias.startsWith(firstName))
    ) {
      return false;
    }

    // Exclude single-word phonetic variations and Whisper misheard syllables
    const aliasWords = lowerAlias.split(/\s+/);
    if (aliasWords.length === 1) {
      const w = aliasWords[0];
      const isPhonetic = nameWords.some(nw => {
        if (Math.abs(nw.length - w.length) <= 3) {
          let common = 0;
          for (let i = 0; i < Math.min(nw.length, w.length); i++) {
            if (nw[i] === w[i]) common++;
          }
          if (common >= 3) return true;
        }
        return false;
      });
      if (isPhonetic) return false;
    }

    return true;
  });
}

function getAssociatedLocationsForCharacter(charName) {
  if (!charName) return [];
  const state = currentWikiCampaignState || {};
  const target = charName.toLowerCase().trim();

  // Check if character is a Player Character (PC)
  const isPc = (state.universal_pcs || []).some(p => {
    const pName = (p.name || p.nombre || p.personaje || "").toLowerCase().trim();
    if (pName === target) return true;
    return (p.aliases || []).some(a => (a || "").toLowerCase().trim() === target);
  }) || (state.roster || []).some(r => {
    const rName = (r.character_name || "").toLowerCase().trim();
    return rName && rName !== "(dm)" && rName === target;
  });

  return (state.locations || []).filter(loc => {
    const assoc = Array.isArray(loc.associated_characters) ? loc.associated_characters : [];
    const inAssoc = assoc.some(a => (a || "").toLowerCase().trim() === target);
    const locType = String(loc.type || "").toLowerCase();
    const locDesc = String(loc.description || "").toLowerCase();
    const isResidence = /hogar|residencia|base|cuartel|sede|refugio/i.test(`${locType} ${locDesc}`);

    // If PC: ONLY associate if this place is explicitly their home base or residence!
    // Transient visits to dungeons, caves or battlefields NEVER link to PC dossiers!
    if (isPc) {
      return isResidence && (inAssoc || (target.length >= 3 && locDesc.includes(target)));
    }

    // For NPCs: ONLY link if listed as inhabitant/custodian/ruler in associated_characters
    return inAssoc;
  });
}

function getHeldItemsForCharacter(charName) {
  if (!charName) return [];
  const state = currentWikiCampaignState || {};
  const target = charName.toLowerCase().trim();
  return (state.items || []).filter(it => {
    const holder = (it.holder || "").toLowerCase().trim();
    return holder === target || (target.length >= 4 && holder.includes(target));
  });
}

function buildAllPcsGridHtml() {
  const state = currentWikiCampaignState || {};
  const pcs = state.universal_pcs || [];
  if (pcs.length === 0) {
    return `
      <div class="h-full min-h-[350px] flex flex-col items-center justify-center text-center p-8 space-y-3">
        <div class="w-12 h-12 rounded-2xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-500">
          <span class="text-2xl"><span data-ui-icon=shield aria-hidden=true></span></span>
        </div>
        <h4 class="text-sm font-bold text-slate-300">Directorio de Protagonistas (PCs)</h4>
        <p class="text-xs text-slate-500 max-w-sm leading-relaxed">
          No hay protagonistas registrados aún en esta campaña. Se registrarán automáticamente con cada sesión.
        </p>
      </div>
    `;
  }

  return `
    <div class="space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 class="text-base font-bold text-slate-100 font-fantasy flex items-center gap-2">
            <span><span data-ui-icon=shield aria-hidden=true></span></span> Protagonistas de la Campaña (${pcs.length})
          </h3>
          <p class="text-xs text-slate-400">Cuadrícula maestra de personajes jugadores activos</p>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        ${pcs.map(p => {
          const charName = p.name || p.nombre || p.personaje || p.character_name || 'Sin nombre';
          const player = p.player_name || p.jugador || p.player || '';
          const species = p.species || p.especie || p.raza || 'Desconocida';
          const cls = p.character_class || p.clase || p.class || p.role || 'Aventurero';
          const subcls = p.subclass || p.subclase || '';
          const debut = p.debut_sesion ? `Sesión #${p.debut_sesion}` : (p.primera_aparicion_sesion ? `Sesión #${p.primera_aparicion_sesion}` : "Sesión #1");
          const rawHitos = (Array.isArray(p.hitos_acumulados) && p.hitos_acumulados.length > 0) ? p.hitos_acumulados : [];
          const latestHito = rawHitos.length > 0 ? rawHitos[rawHitos.length - 1] : (p.rol_en_sesion || '');

          return `
            <div class="bg-slate-950/80 border border-slate-800/90 hover:border-amber-500/40 rounded-xl p-3.5 space-y-2.5 transition flex flex-col justify-between shadow-sm">
              <div class="space-y-1.5">
                <div class="flex items-center justify-between gap-2">
                  <h4 class="font-bold text-slate-100 font-fantasy text-sm truncate">${escapeHtml(charName)}</h4>
                  <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400 font-mono shrink-0">
                    ${escapeHtml(debut)}
                  </span>
                </div>
                ${player ? `<p class="text-[11px] text-slate-400 truncate">Jugador: <strong class="text-amber-300 font-medium">${escapeHtml(player)}</strong></p>` : ''}
                <div class="flex flex-wrap gap-1 text-[10px] font-mono">
                  <span class="px-1.5 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800">${escapeHtml(species)}</span>
                  <span class="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">${escapeHtml(cls)}${subcls && subcls !== '-' ? ` (${escapeHtml(subcls)})` : ''}</span>
                </div>
                ${latestHito ? `
                  <p class="text-[11px] text-slate-400 line-clamp-2 leading-relaxed pt-1 border-t border-slate-900">
                    ${escapeHtml(typeof latestHito === 'string' ? latestHito : (latestHito.text || latestHito.hito || ''))}
                  </p>
                ` : ''}
              </div>
              <div class="flex items-center justify-end gap-1.5 pt-2 border-t border-slate-900">
                <button type="button" onclick="openMergeEntityModal('pc', '${escapeHtml(charName)}')" class="px-2 py-1 rounded-lg text-[11px] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-amber-300 border border-slate-800 transition active:scale-95 cursor-pointer" title="Fusionar con otro personaje">
                  <span data-ui-icon=link aria-hidden=true></span>
                </button>
                <button type="button" onclick="findAndSelectWikiEntity('pc', '${escapeHtml(charName)}')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 transition active:scale-95 cursor-pointer">
                  Ver Ficha
                </button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderWikiDossier() {
  const emptyEl = document.getElementById("wikiDossierEmpty");
  const contentEl = document.getElementById("wikiDossierContent");
  if (!emptyEl || !contentEl) return;

  if (!selectedWikiEntity || !selectedWikiEntity.data) {
    if (activeWikiCategory === "pcs") {
      emptyEl.classList.add("hidden");
      contentEl.classList.remove("hidden");
      contentEl.innerHTML = buildAllPcsGridHtml();
      return;
    }
    emptyEl.classList.remove("hidden");
    contentEl.classList.add("hidden");
    return;
  }

  emptyEl.classList.add("hidden");
  contentEl.classList.remove("hidden");

  const { type, data } = selectedWikiEntity;
  if (type === "quest") {
    contentEl.innerHTML = buildQuestDossierHtml(data);
  } else if (type === "npc") {
    contentEl.innerHTML = buildNpcDossierHtml(data);
  } else if (type === "pc") {
    contentEl.innerHTML = buildPcDossierHtml(data);
  } else if (type === "location") {
    contentEl.innerHTML = buildLocationDossierHtml(data);
  } else if (type === "item") {
    contentEl.innerHTML = buildItemDossierHtml(data);
  } else if (type === "session") {
    contentEl.innerHTML = buildSessionDossierHtml(data);
  }
}

function buildLocationDossierHtml(loc) {
  const state = currentWikiCampaignState || {};
  const rawAssoc = Array.isArray(loc.associated_characters) ? loc.associated_characters : [];
  const locType = String(loc.type || "").toLowerCase();
  const locDesc = String(loc.description || "").toLowerCase();
  const isResidence = /hogar|residencia|base|cuartel|sede|refugio/i.test(`${locType} ${locDesc}`);

  // Exclude visiting PCs unless the place is explicitly their home / permanent base
  const assoc = rawAssoc.filter(charName => {
    const isPc = (state.universal_pcs || []).some(p => {
      const pName = (p.name || p.nombre || p.personaje || "").toLowerCase().trim();
      if (pName === charName.toLowerCase().trim()) return true;
      return (p.aliases || []).some(a => (a || "").toLowerCase().trim() === charName.toLowerCase().trim());
    }) || (state.roster || []).some(r => {
      const rName = (r.character_name || "").toLowerCase().trim();
      return rName && rName !== "(dm)" && rName === charName.toLowerCase().trim();
    });
    if (isPc && !isResidence) return false;
    return true;
  });

  let assocChipsHtml = "";
  if (assoc.length > 0) {
    assocChipsHtml = `
      <div class="space-y-2 pt-2 border-t border-[#222222]">
        <span class="text-[11px] font-semibold text-neutral-400 block uppercase font-mono">Habitantes, Gobernantes o Custodios Permanentes:</span>
        <div class="flex flex-wrap gap-2">
          ${assoc.map(charName => {
            const isPc = (state.universal_pcs || []).some(p => (p.name || p.nombre || p.personaje || "").toLowerCase().trim() === charName.toLowerCase().trim());
            const type = isPc ? 'pc' : 'npc';
            const icon = WhisperIcons.markup(isPc ? 'shield' : 'message');
            return `<button type="button" onclick="findAndSelectWikiEntity('${type}', '${escapeHtml(charName)}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs bg-[#121212] hover:bg-[#1a1a1a] text-amber-300 border border-[#262626] hover:border-amber-500/50 transition cursor-pointer active:scale-95 shadow-sm">
              <span>${icon}</span>
              <span class="font-medium">${escapeHtml(charName)}</span>
            </button>`;
          }).join("")}
        </div>
      </div>
    `;
  }

  const statusBadges = {
    explorado: '<span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=check aria-hidden=true></span> Explorado</span>',
    en_progreso: '<span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">● En Progreso</span>',
    destruido: '<span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30"><span data-ui-icon=close aria-hidden=true></span> Destruido</span>',
    no_visitado: '<span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#121212] text-neutral-400 border border-[#262626]"><span data-ui-icon=compass aria-hidden=true></span> No Visitado</span>',
  };
  const badge = statusBadges[loc.status] || `<span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#121212] text-neutral-300 border border-[#262626]">${escapeHtml(loc.status || 'Ubicación')}</span>`;

  return `
    <div class="space-y-4">
      <div class="flex items-center justify-between border-b border-[#222222] pb-3">
        <div>
          <h3 class="text-xl font-bold text-amber-300 font-fantasy">${escapeHtml(loc.name || 'Lugar')}</h3>
          <p class="text-sm text-neutral-400 mt-0.5">${escapeHtml(loc.type || 'Región / Punto de Interés')}</p>
        </div>
        <div>${badge}</div>
      </div>
      <div class="bg-[#0a0a0d] p-5 rounded-xl border border-[#222222] text-[15px] text-neutral-200 leading-relaxed font-sans">
        ${renderMarkdownWithKaTeX(loc.description || loc.context || 'Sin descripción detallada.')}
      </div>
      ${assocChipsHtml}
    </div>
  `;
}

function buildItemDossierHtml(item) {
  const state = currentWikiCampaignState || {};
  const holder = (item.holder || "-").trim();
  let holderChipHtml = "";
  if (holder && holder !== "-") {
    const isPc = (state.universal_pcs || []).some(p => (p.name || p.nombre || p.personaje || "").toLowerCase().trim() === holder.toLowerCase());
    const type = isPc ? 'pc' : 'npc';
    const icon = WhisperIcons.markup(isPc ? 'shield' : 'message');
    holderChipHtml = `
      <div class="pt-2 border-t border-[#222222] space-y-1.5">
        <span class="text-[11px] font-semibold text-neutral-400 block uppercase font-mono">Portador Actual / Custodio:</span>
        <button type="button" onclick="findAndSelectWikiEntity('${type}', '${escapeHtml(holder)}')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs bg-[#121212] hover:bg-[#1a1a1a] text-amber-300 border border-[#262626] hover:border-amber-500/50 transition cursor-pointer active:scale-95 shadow-sm">
          <span>${icon}</span>
          <strong class="font-semibold">${escapeHtml(holder)}</strong>
          <span class="text-[10px] text-neutral-400">(${isPc ? 'Protagonista' : 'PNJ'})</span>
        </button>
      </div>
    `;
  }

  return `
    <div class="space-y-4">
      <div class="flex items-center justify-between border-b border-[#222222] pb-3">
        <div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30 uppercase">
              ${escapeHtml(item.type || 'Artefacto')}
            </span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
              ${escapeHtml(item.status || 'En posesión')}
            </span>
          </div>
          <h3 class="text-xl font-bold text-amber-300 font-fantasy mt-1">${escapeHtml(item.name || 'Objeto / Reliquia')}</h3>
        </div>
      </div>
      <div class="bg-[#0a0a0d] p-5 rounded-xl border border-[#222222] text-[15px] text-neutral-200 leading-relaxed font-sans">
        ${renderMarkdownWithKaTeX(item.description || item.context || 'Sin descripción.')}
      </div>
      ${holderChipHtml}
    </div>
  `;
}

function switchWikiSessionSubtab(subtab) {
  currentWikiSessionSubtab = subtab;
  const btnChron = document.getElementById("btnWikiSessionChronicle");
  const btnTrans = document.getElementById("btnWikiSessionTranscript");
  const tabChron = document.getElementById("wikiSessionChronicleTab");
  const tabTrans = document.getElementById("wikiSessionTranscriptTab");

  if (subtab === 'chronicle') {
    if (btnChron) btnChron.className = "flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 cursor-pointer shadow-sm";
    if (btnTrans) btnTrans.className = "flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-400 hover:text-neutral-200 hover:bg-[#141414] border border-transparent cursor-pointer";
    if (tabChron) tabChron.classList.remove("hidden");
    if (tabTrans) tabTrans.classList.add("hidden");
  } else {
    if (btnChron) btnChron.className = "flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-400 hover:text-neutral-200 hover:bg-[#141414] border border-transparent cursor-pointer";
    if (btnTrans) btnTrans.className = "flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 cursor-pointer shadow-sm";
    if (tabChron) tabChron.classList.add("hidden");
    if (tabTrans) tabTrans.classList.remove("hidden");
  }
}

function filterWikiSessionTranscript(query) {
  const q = (query || "").trim().toLowerCase();
  const rows = document.querySelectorAll(".wiki-transcript-line");
  rows.forEach(row => {
    if (!q || row.textContent.toLowerCase().includes(q)) {
      row.classList.remove("hidden");
    } else {
      row.classList.add("hidden");
    }
  });
}

function copyWikiSessionTranscript() {
  if (!currentWikiSessionData) return;
  const text = currentWikiSessionData.raw_transcript || currentWikiSessionData.transcript || "";
  if (!text) {
    if (typeof showTransientAlert === "function") showTransientAlert("No hay transcripción disponible para copiar", "warning");
    else alert("No hay transcripción disponible para copiar");
    return;
  }
  navigator.clipboard.writeText(text).then(() => {
    if (typeof showTransientAlert === "function") showTransientAlert("Transcripción completa copiada al portapapeles", "success");
    else alert("Transcripción copiada al portapapeles");
  }).catch(() => {
    if (typeof showTransientAlert === "function") showTransientAlert("Error al copiar transcripción", "error");
  });
}

function downloadWikiSessionTranscript() {
  if (!currentWikiSessionData) return;
  const text = currentWikiSessionData.raw_transcript || currentWikiSessionData.transcript || "";
  if (!text) {
    if (typeof showTransientAlert === "function") showTransientAlert("No hay transcripción disponible para descargar", "warning");
    else alert("No hay transcripción disponible para descargar");
    return;
  }
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sesion_${currentWikiSessionData.session_number || 'historial'}_transcripcion.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildSessionDossierHtml(s) {
  currentWikiSessionData = s;
  const num = s.session_number || "1";
  const dateStr = s.date || "Fecha no registrada";
  const summaryStr = s.summary || "";
  const chronicleMd = s.chronicle_markdown || s.summary || "Sin crónica narrativa registrada.";
  const transcriptText = s.raw_transcript || s.transcript || "";

  const transcriptLines = transcriptText ? transcriptText.split("\n").filter(l => l.trim().length > 0) : [];

  let transcriptHtml = "";
  if (transcriptLines.length === 0) {
    transcriptHtml = `<p class="italic text-neutral-400 text-sm font-medium p-4 text-center">No hay transcripción en texto sin procesar para esta sesión.</p>`;
  } else {
    transcriptHtml = transcriptLines.map((line, idx) => {
      return `<div class="wiki-transcript-line py-2 px-3 rounded-lg hover:bg-[#141414] font-mono text-[13px] text-neutral-200 leading-relaxed border-b border-[#18181b]">
        <span class="text-neutral-500 text-xs select-none mr-2.5 font-mono">${(idx + 1).toString().padStart(3, '0')}</span>
        <span>${escapeHtml(line)}</span>
      </div>`;
    }).join("");
  }

  return `
    <div class="space-y-4">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#222222] pb-3">
        <div>
          <div class="flex items-center gap-2">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">Sesión #${num}</span>
            <span class="text-xs text-neutral-400 font-mono">${escapeHtml(dateStr)}</span>
          </div>
          <h3 class="text-xl font-bold text-neutral-100 mt-1">${escapeHtml((() => {
            const rawTitle = (s.session_title || s.title || "").trim();
            const cleanTitle = rawTitle.replace(/^(?:sesi[oó]n|session)\s*#?\d+\s*[:\-]\s*/i, "").trim();
            return cleanTitle ? `Sesión #${num}: ${cleanTitle}` : `Sesión #${num}`;
          })())}</h3>
          ${summaryStr ? `<p class="text-sm text-neutral-300 mt-1.5 max-w-2xl leading-relaxed">${escapeHtml(summaryStr)}</p>` : ''}
        </div>
      </div>

      <div class="flex items-center gap-2 p-1 rounded-xl bg-black border border-[#222222]">
        <button type="button" id="btnWikiSessionChronicle" onclick="switchWikiSessionSubtab('chronicle')"
          class="flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-2 ${currentWikiSessionSubtab === 'chronicle' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm' : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#141414] border border-transparent'} cursor-pointer">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>
          <span>Crónica Narrativa</span>
        </button>
        <button type="button" id="btnWikiSessionTranscript" onclick="switchWikiSessionSubtab('transcript')"
          class="flex-1 min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center justify-center gap-2 ${currentWikiSessionSubtab === 'transcript' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm' : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#141414] border border-transparent'} cursor-pointer">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span>Transcripción Completa</span>
        </button>
      </div>

      <div id="wikiSessionChronicleTab" class="${currentWikiSessionSubtab === 'chronicle' ? '' : 'hidden'} prose-dnd text-neutral-200 text-base leading-relaxed overflow-x-auto space-y-4 font-sans max-w-3xl">
        ${renderMarkdownWithKaTeX(chronicleMd)}
      </div>

      <div id="wikiSessionTranscriptTab" class="${currentWikiSessionSubtab === 'transcript' ? '' : 'hidden'} space-y-3">
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 bg-[#0a0a0d] p-2.5 rounded-xl border border-[#222222]">
          <div class="relative flex-1">
            <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-neutral-500">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            </span>
            <input type="text" id="wikiTranscriptSearch" oninput="filterWikiSessionTranscript(this.value)" placeholder="Filtrar diálogo o palabras clave..."
              class="w-full min-h-[38px] bg-[#0d0d0d] border border-[#262626] focus:border-amber-500/70 rounded-lg pl-8 pr-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 outline-none">
          </div>
          <div class="flex items-center gap-2">
            <button type="button" onclick="copyWikiSessionTranscript()" title="Copiar transcripción al portapapeles"
              class="min-h-[38px] px-3 py-1.5 rounded-xl bg-[#121212] hover:bg-[#1a1a1a] text-neutral-200 hover:text-white border border-[#262626] text-xs font-semibold flex items-center gap-1.5 cursor-pointer active:scale-95 transition shadow-sm">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
              <span>Copiar Transcripción</span>
            </button>
            <button type="button" onclick="downloadWikiSessionTranscript()" title="Descargar transcripción como .txt"
              class="min-h-[38px] px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs font-semibold flex items-center gap-1.5 cursor-pointer active:scale-95 transition shadow-sm">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
              <span>Descargar (.txt)</span>
            </button>
          </div>
        </div>

        <div id="wikiSessionTranscriptContainer" class="bg-[#08080a] p-3 rounded-xl border border-[#222222] max-h-[500px] overflow-y-auto space-y-1">
          ${transcriptHtml}
        </div>
      </div>
    </div>
  `;
}

function buildQuestDossierHtml(q) {
  const isCompleted = q.status === "completed";
  const isFailed = q.status === "failed";
  const tipo = (q.tipo || "principal").toLowerCase();
  
  let tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"><span data-ui-icon=star aria-hidden=true></span> Misión Principal</span>';
  if (tipo === "secundaria") {
    tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"><span data-ui-icon=swords aria-hidden=true></span> Misión Secundaria</span>';
  } else if (tipo === "opcional") {
    tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=compass aria-hidden=true></span> Tarea Opcional</span>';
  } else if (tipo === "misterios_abiertos" || tipo === "misterio") {
    tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30"><span data-ui-icon=compass aria-hidden=true></span> Misterios Abiertos</span>';
  }

  let statusBadge = "";
  if (isCompleted) {
    statusBadge = `<button type="button" onclick="toggleWikiQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-80 active:scale-95 transition px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=check aria-hidden=true></span> COMPLETADA</button>`;
  } else if (isFailed) {
    statusBadge = `<button type="button" onclick="toggleWikiQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-80 active:scale-95 transition px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30"><span data-ui-icon=record aria-hidden=true></span> FRACASADA</button>`;
  } else {
    statusBadge = `<button type="button" onclick="toggleWikiQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-80 active:scale-95 transition px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">EN PROGRESO</button>`;
  }

  let subobjectivesHtml = "";
  if (q.subobjectives && q.subobjectives.length > 0) {
    subobjectivesHtml = `
      <div class="space-y-2 pt-3 border-t border-[#222222]">
        <h5 class="text-xs font-bold text-neutral-300 uppercase tracking-wider flex items-center gap-2 font-mono">
          <span><span data-ui-icon=target aria-hidden=true></span></span> Sub-objetivos & Hitos Concretos
        </h5>
        <div class="space-y-1.5 bg-[#0a0a0d] p-3.5 rounded-xl border border-[#222222]">
          ${q.subobjectives.map((sub, sIdx) => `
            <label class="flex items-start gap-3 text-sm text-neutral-200 cursor-pointer hover:text-white transition py-0.5">
              <input type="checkbox" ${sub.completed ? 'checked' : ''}
                onchange="toggleWikiSubobjective('${escapeHtml(q.id)}', ${sIdx}, this.checked)"
                class="mt-0.5 w-4 h-4 rounded bg-[#0d0d0d] border-[#262626] text-amber-500 focus:ring-0 cursor-pointer accent-amber-500">
              <span class="${sub.completed ? 'line-through text-neutral-500' : 'text-neutral-200'} leading-relaxed">${escapeHtml(sub.text)}</span>
            </label>
          `).join('')}
        </div>
      </div>
    `;
  }

  return `
    <div class="space-y-4">
      <div class="border-b border-[#222222] pb-3 space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          ${tipoBadge}
          ${statusBadge}
          <span class="text-xs font-mono text-neutral-500">[ID: ${escapeHtml(q.id || '-')}]</span>
        </div>
        <h3 class="text-xl font-bold text-neutral-100 mt-1">${escapeHtml(q.title || 'Misión')}</h3>
      </div>

      <div class="space-y-2">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider font-mono">Contexto & Apuestas</h5>
        <p class="text-sm text-neutral-200 leading-relaxed bg-[#0a0a0d] p-4 rounded-xl border border-[#222222]">
          ${escapeHtml(q.context || 'Sin contexto registrado.')}
        </p>
      </div>

      ${subobjectivesHtml}

      ${q.lifecycle_notes ? `
      <div class="space-y-1.5 pt-2 border-t border-[#222222]">
        <h5 class="text-xs font-bold text-amber-400/90 uppercase tracking-wider flex items-center gap-1.5 font-mono">
          <span><span data-ui-icon=file aria-hidden=true></span></span> Registro Cronológico / Notas de Sesión
        </h5>
        <div class="bg-amber-950/20 border border-amber-500/20 p-3.5 rounded-xl text-sm text-amber-200/90 font-mono leading-relaxed">
          ${escapeHtml(q.lifecycle_notes)}
        </div>
      </div>` : ''}
    </div>
  `;
}

async function toggleWikiSubobjective(questId, subIdx, completed) {
  if (currentWikiCampaignState && currentWikiCampaignState.quests) {
    const q = currentWikiCampaignState.quests.find(x => x.id === questId);
    if (q && q.subobjectives && q.subobjectives[subIdx]) {
      q.subobjectives[subIdx].completed = completed;
      renderWikiDossier();
      renderWikiEntityList();
    }
  }
  const select = document.getElementById("wikiCampaignSelect");
  const campName = (select && select.value) ? select.value.trim() : (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) return;

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/quests/${encodeURIComponent(questId)}/subobjective`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subobjective_idx: subIdx, completed: completed })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.campaign_state) {
        currentWikiCampaignState = data.campaign_state;
        if (campName.toLowerCase() === (document.getElementById("campaignNameInput")?.value || "").trim().toLowerCase()) {
          if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
          if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);
        }
      }
    }
  } catch (err) {
    console.error("Error toggling wiki subobjective:", err);
  }
}

async function toggleWikiQuestStatus(questId, currentStatus) {
  const select = document.getElementById("wikiCampaignSelect");
  const campName = (select && select.value) ? select.value.trim() : (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) return;

  const newStatus = (currentStatus === "completed" || currentStatus === "failed") ? "in_progress" : "completed";
  if (currentWikiCampaignState && currentWikiCampaignState.quests) {
    const q = currentWikiCampaignState.quests.find(x => x.id === questId);
    if (q) {
      q.status = newStatus;
      renderWikiDossier();
      renderWikiEntityList();
    }
  }

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/quests/${encodeURIComponent(questId)}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.campaign_state) {
        currentWikiCampaignState = data.campaign_state;
        if (campName.toLowerCase() === (document.getElementById("campaignNameInput")?.value || "").trim().toLowerCase()) {
          if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
          if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);
        }
        renderWikiDossier();
        renderWikiEntityList();
      }
    }
  } catch (err) {
    console.error("Error toggling wiki quest status:", err);
  }
}

let mergeEntityContext = { type: 'pc', entityName: '' };

function toggleMergeEntityModal(show) {
  const modal = document.getElementById("mergeEntityModal");
  const box = document.getElementById("mergeEntityModalBox");
  if (!modal || !box) return;
  if (show) {
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
  } else {
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
}

function openMergeEntityModal(type, entityName) {
  mergeEntityContext = { type, entityName };
  const sourceEl = document.getElementById("mergeSourceDisplayName");
  const targetSelect = document.getElementById("mergeTargetSelect");
  const errEl = document.getElementById("mergeEntityError");
  if (errEl) errEl.classList.add("hidden");
  if (sourceEl) {
    const badge = type === 'pc' ? 'Protagonista (PC)' : 'PNJ';
    sourceEl.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-bold text-amber-300 text-sm font-fantasy">${escapeHtml(entityName)}</span>
        <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400 font-mono">${badge}</span>
      </div>
    `;
  }

  if (targetSelect) {
    targetSelect.innerHTML = `<option value="">-- Selecciona el personaje principal que lo absorberá --</option>`;
    const state = currentWikiCampaignState || {};
    const pcs = (state.universal_pcs || []).filter(p => {
      const nm = (p.name || p.nombre || p.personaje || p.character_name || "").trim();
      return nm && nm.toLowerCase() !== entityName.trim().toLowerCase();
    });
    const npcs = (state.npcs || []).filter(n => {
      const nm = (n.name || n.nombre || n.personaje || n.character_name || "").trim();
      return nm && nm.toLowerCase() !== entityName.trim().toLowerCase();
    });

    let recommendedValue = "";
    const cleanSource = entityName.toLowerCase().replace(/[^\w\s]/g, "");

    if (pcs.length > 0) {
      const optGroupPcs = document.createElement("optgroup");
      optGroupPcs.label = "Protagonistas (PCs)";
      pcs.forEach(p => {
        const nm = (p.name || p.nombre || p.personaje || p.character_name || "").trim();
        const opt = document.createElement("option");
        opt.value = nm;
        opt.dataset.type = "pc";
        const pl = p.player_name || p.jugador || "";
        opt.textContent = pl ? `${nm} (Jugador: ${pl})` : nm;
        const cleanTarget = nm.toLowerCase().replace(/[^\w\s]/g, "");
        if (cleanTarget.includes(cleanSource) || cleanSource.includes(cleanTarget)) {
          recommendedValue = nm;
        }
        optGroupPcs.appendChild(opt);
      });
      targetSelect.appendChild(optGroupPcs);
    }

    if (npcs.length > 0) {
      const optGroupNpcs = document.createElement("optgroup");
      optGroupNpcs.label = "Personajes No Jugadores (PNJs)";
      npcs.forEach(n => {
        const nm = (n.name || n.nombre || n.personaje || n.character_name || "").trim();
        const opt = document.createElement("option");
        opt.value = nm;
        opt.dataset.type = "npc";
        const rl = n.role || n.rol_en_sesion || "";
        opt.textContent = rl ? `${nm} (${rl})` : nm;
        const cleanTarget = nm.toLowerCase().replace(/[^\w\s]/g, "");
        if (!recommendedValue && (cleanTarget.includes(cleanSource) || cleanSource.includes(cleanTarget))) {
          recommendedValue = nm;
        }
        optGroupNpcs.appendChild(opt);
      });
      targetSelect.appendChild(optGroupNpcs);
    }

    if (recommendedValue) {
      targetSelect.value = recommendedValue;
    }
  }

  toggleMergeEntityModal(true);
}

async function submitMergeEntity() {
  const targetSelect = document.getElementById("mergeTargetSelect");
  const errEl = document.getElementById("mergeEntityError");
  const btn = document.getElementById("confirmMergeBtn");
  const targetName = targetSelect ? targetSelect.value.trim() : "";

  if (!targetName) {
    if (errEl) {
      errEl.textContent = "Por favor selecciona el personaje principal con el que deseas fusionarlo.";
      errEl.classList.remove("hidden");
    }
    return;
  }

  const campSelect = document.getElementById("wikiCampaignSelect");
  const campName = (campSelect && campSelect.value) ? campSelect.value.trim() : "";
  if (!campName) {
    if (errEl) {
      errEl.textContent = "No se ha seleccionado ninguna campaña activa en la Wiki.";
      errEl.classList.remove("hidden");
    }
    return;
  }

  const origBtnHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span><span data-ui-icon=clock aria-hidden=true></span></span><span>Fusionando...</span>`;
  }
  if (errEl) errEl.classList.add("hidden");

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/merge-entities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_name: mergeEntityContext.entityName,
        target_name: targetName,
        entity_type: mergeEntityContext.type
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Error al procesar la fusión en el servidor.");
    }

    toggleMergeEntityModal(false);

    if (data.campaign_state) {
      currentWikiCampaignState = data.campaign_state;
      if (campName.toLowerCase() === (document.getElementById("campaignNameInput")?.value || "").trim().toLowerCase()) {
        if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
        if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);
      }
    }

    renderWikiEntityList();
    const mergedType = (data.merged && data.merged.type) || mergeEntityContext.type;
    const targetData = (mergedType === "pc")
      ? (currentWikiCampaignState.universal_pcs || []).find(p => (p.personaje || p.name) === targetName)
      : (currentWikiCampaignState.npcs || []).find(n => n.name === targetName);

    if (targetData) {
      selectWikiEntity(mergedType, targetName, targetData);
    } else {
      renderWikiDossier();
    }

    if (typeof showAlert === 'function') {
      showAlert(`¡Personajes fusionados con éxito en '${targetName}'!`);
    }
  } catch (err) {
    console.error("Error merging entities:", err);
    if (errEl) {
      errEl.textContent = err.message || "Error al fusionar personajes.";
      errEl.classList.remove("hidden");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origBtnHtml;
    }
  }
}

function buildNpcDossierHtml(n) {
  const tipo = (n.tipo || n.type || "interaccion_contexto").toLowerCase();
  let tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"><span data-ui-icon=message aria-hidden=true></span> Interacción Directa & Contexto</span>';
  if (tipo === "importantes" || tipo === "importante") {
    tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30"><span data-ui-icon=star aria-hidden=true></span> Clave / Importante</span>';
  } else if (tipo === "mencionados" || tipo === "mencionado") {
    tipoBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700"><span data-ui-icon=file aria-hidden=true></span> Mencionado en la historia</span>';
  }

  const rawNpcName = n.name || n.nombre || n.personaje || n.character_name || 'Sin nombre';
  const npcName = formatCharacterDisplayName(rawNpcName, n.aliases);
  const cleanNpcAliases = getCleanNarrativeAliases(rawNpcName, n.aliases);
  const npcRole = n.role || n.rol_en_sesion || n.session_role || 'Personaje No Jugador';
  const npcDesc = n.description || n.descripcion || n.detalles || n.rol_en_sesion || n.role || n.session_role || (Array.isArray(n.notes) && n.notes[0]) || 'Sin descripción disponible';
  const rawNotes = (Array.isArray(n.notes) && n.notes.length > 0) ? n.notes : (n.description ? [n.description] : (n.descripcion ? [n.descripcion] : []));
  const notes = rawNotes.length > 0 ? rawNotes : [npcDesc];

  const assocLocs = getAssociatedLocationsForCharacter(rawNpcName);
  let locsHtml = "";
  if (assocLocs.length > 0) {
    locsHtml = `
      <div class="space-y-2 pt-2 border-t border-slate-800/80">
        <h5 class="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
          <span><span data-ui-icon=pin aria-hidden=true></span></span> Lugares Vinculados
        </h5>
        <div class="flex flex-wrap gap-2">
          ${assocLocs.map(l => `
            <button type="button" onclick="findAndSelectWikiEntity('location', '${escapeHtml(l.name)}')" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-slate-900 hover:bg-slate-800 text-amber-300 border border-slate-700 hover:border-amber-500/40 transition cursor-pointer active:scale-95 shadow-sm">
              <span><span data-ui-icon=pin aria-hidden=true></span></span>
              <span class="font-medium">${escapeHtml(l.name)}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  const heldItems = getHeldItemsForCharacter(rawNpcName);
  let itemsHtml = "";
  if (heldItems.length > 0) {
    itemsHtml = `
      <div class="space-y-2 pt-2 border-t border-[#222222]">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
          <span><span data-ui-icon=swords aria-hidden=true></span></span> Objetos y Artefactos en Custodia
        </h5>
        <div class="flex flex-wrap gap-2">
          ${heldItems.map(it => `
            <button type="button" onclick="findAndSelectWikiEntity('item', '${escapeHtml(it.name)}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs bg-[#121212] hover:bg-[#1a1a1a] text-purple-300 border border-purple-500/30 hover:border-purple-500/50 transition cursor-pointer active:scale-95 shadow-sm">
              <span><span data-ui-icon=gem aria-hidden=true></span></span>
              <span class="font-medium">${escapeHtml(it.name)}</span>
              <span class="text-[10px] text-neutral-400">(${escapeHtml(it.type || 'Artefacto')})</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  return `
    <div class="space-y-4">
      <div class="border-b border-[#222222] pb-3 space-y-2">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            ${tipoBadge}
            <span class="text-xs px-2 py-0.5 rounded-lg bg-[#0d0d0d] border border-[#222222] text-neutral-400 font-mono">
              Visto por primera vez en Sesión #${n.first_seen_session || 1}
            </span>
          </div>
          <button type="button" onclick="openMergeEntityModal('npc', '${escapeHtml(rawNpcName)}')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#121212] hover:bg-[#1a1a1a] text-amber-300 border border-[#262626] hover:border-amber-500/50 shadow-sm transition active:scale-95 cursor-pointer" title="Fusionar con otro personaje de la campaña">
            <span><span data-ui-icon=link aria-hidden=true></span></span>
            <span>Fusionar con otro personaje</span>
          </button>
        </div>
        <h3 class="text-xl font-bold text-neutral-100 font-fantasy mt-1">${escapeHtml(npcName)}</h3>
        <p class="text-sm text-amber-300 font-semibold mt-0.5">${escapeHtml(npcRole)}</p>
        ${cleanNpcAliases.length > 0 ? `
          <div class="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
            <span class="text-[10px] uppercase font-mono text-neutral-400">Apodo / Sobrenombre:</span>
            ${cleanNpcAliases.map(a => `<span class="px-2 py-0.5 rounded-full bg-[#0d0d0d] border border-[#262626] text-amber-300 font-mono text-[11px]">${escapeHtml(a)}</span>`).join("")}
          </div>
        ` : ''}
      </div>

      <div class="space-y-2">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider flex items-center gap-2 font-mono">
          <span><span data-ui-icon=clipboard aria-hidden=true></span></span> Registro Cronológico de Inteligencia & Pistas
        </h5>
        <div class="space-y-2">
          ${notes.map(note => `
            <div class="p-3.5 rounded-xl bg-[#0a0a0d] border border-[#222222] text-sm text-neutral-200 leading-relaxed">
              ${escapeHtml(typeof note === 'string' ? note : (note.note || note.text || JSON.stringify(note)))}
            </div>
          `).join("")}
        </div>
      </div>
      ${locsHtml}
      ${itemsHtml}
    </div>
  `;
}

function buildPcDossierHtml(p) {
  const rawCharName = p.name || p.nombre || p.personaje || p.character_name || 'Sin nombre';
  const charName = formatCharacterDisplayName(rawCharName, p.aliases);
  const cleanPcAliases = getCleanNarrativeAliases(rawCharName, p.aliases);
  const player = p.player_name || p.jugador || p.player || '';
  const species = p.species || p.especie || p.raza || 'Desconocida';
  const cls = p.character_class || p.clase || p.class || p.role || 'Aventurero';
  const subcls = p.subclass || p.subclase || '-';
  const debut = p.debut_sesion ? `Debut en Sesión #${p.debut_sesion}` : (p.primera_aparicion_sesion ? `Debut en Sesión #${p.primera_aparicion_sesion}` : "Debut en Sesión #1");
  const rawHitos = (Array.isArray(p.hitos_acumulados) && p.hitos_acumulados.length > 0) ? p.hitos_acumulados : [];
  const pcDesc = p.description || p.descripcion || p.detalles || p.rol_en_sesion || (rawHitos.length > 0 ? rawHitos[0] : 'Sin descripción disponible');
  const hitos = rawHitos.length > 0 ? rawHitos : [pcDesc];

  const assocLocs = getAssociatedLocationsForCharacter(rawCharName);
  let locsHtml = "";
  if (assocLocs.length > 0) {
    locsHtml = `
      <div class="space-y-2 pt-2 border-t border-[#222222]">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
          <span><span data-ui-icon=pin aria-hidden=true></span></span> Lugares Vinculados
        </h5>
        <div class="flex flex-wrap gap-2">
          ${assocLocs.map(l => `
            <button type="button" onclick="findAndSelectWikiEntity('location', '${escapeHtml(l.name)}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs bg-[#121212] hover:bg-[#1a1a1a] text-amber-300 border border-[#262626] hover:border-amber-500/50 transition cursor-pointer active:scale-95 shadow-sm">
              <span><span data-ui-icon=pin aria-hidden=true></span></span>
              <span class="font-medium">${escapeHtml(l.name)}</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  const heldItems = getHeldItemsForCharacter(rawCharName);
  let itemsHtml = "";
  if (heldItems.length > 0) {
    itemsHtml = `
      <div class="space-y-2 pt-2 border-t border-[#222222]">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
          <span><span data-ui-icon=swords aria-hidden=true></span></span> Objetos y Artefactos en Posesión
        </h5>
        <div class="flex flex-wrap gap-2">
          ${heldItems.map(it => `
            <button type="button" onclick="findAndSelectWikiEntity('item', '${escapeHtml(it.name)}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs bg-[#121212] hover:bg-[#1a1a1a] text-purple-300 border border-purple-500/30 hover:border-purple-500/50 transition cursor-pointer active:scale-95 shadow-sm">
              <span><span data-ui-icon=gem aria-hidden=true></span></span>
              <span class="font-medium">${escapeHtml(it.name)}</span>
              <span class="text-[10px] text-neutral-400">(${escapeHtml(it.type || 'Artefacto')})</span>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  return `
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <button type="button" onclick="selectWikiEntity(null, null, null)" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-semibold bg-[#121212] hover:bg-[#1a1a1a] text-neutral-300 hover:text-white border border-[#262626] transition active:scale-95 cursor-pointer">
          <span><span data-ui-icon=back aria-hidden=true></span></span>
          <span>Ver Todos los Protagonistas</span>
        </button>
        <button type="button" onclick="openMergeEntityModal('pc', '${escapeHtml(rawCharName)}')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#121212] hover:bg-[#1a1a1a] text-amber-300 border border-[#262626] hover:border-amber-500/50 shadow-sm transition active:scale-95 cursor-pointer" title="Fusionar con otro personaje de la campaña">
          <span><span data-ui-icon=link aria-hidden=true></span></span>
          <span>Fusionar con otro personaje</span>
        </button>
      </div>
      <div class="border-b border-[#222222] pb-3 space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
             Protagonista (PC)
          </span>
          <span class="text-xs px-2 py-0.5 rounded-lg bg-[#0d0d0d] border border-[#222222] text-neutral-400 font-mono">
            ${escapeHtml(debut)}
          </span>
        </div>
        <h3 class="text-xl font-bold text-neutral-100 font-fantasy mt-1">${escapeHtml(charName)}</h3>
        ${player ? `<p class="text-sm text-neutral-300 mt-0.5">Jugador: <strong class="text-amber-300">${escapeHtml(player)}</strong></p>` : ''}
        ${cleanPcAliases.length > 0 ? `
          <div class="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
            <span class="text-[10px] uppercase font-mono text-neutral-400">Apodo / Sobrenombre:</span>
            ${cleanPcAliases.map(a => `<span class="px-2 py-0.5 rounded-full bg-[#0d0d0d] border border-[#262626] text-amber-300 font-mono text-[11px]">${escapeHtml(a)}</span>`).join("")}
          </div>
        ` : ''}
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
        <div class="bg-[#0a0a0d] border border-[#222222] rounded-xl p-2.5">
          <span class="text-[10px] text-neutral-500 block uppercase font-mono">Especie</span>
          <strong class="text-neutral-200">${escapeHtml(species)}</strong>
        </div>
        <div class="bg-[#0a0a0d] border border-[#222222] rounded-xl p-2.5">
          <span class="text-[10px] text-neutral-500 block uppercase font-mono">Clase</span>
          <strong class="text-neutral-200">${escapeHtml(cls)}</strong>
        </div>
        <div class="bg-[#0a0a0d] border border-[#222222] rounded-xl p-2.5">
          <span class="text-[10px] text-neutral-500 block uppercase font-mono">Subclase</span>
          <strong class="text-neutral-200">${escapeHtml(subcls)}</strong>
        </div>
      </div>

      <div class="space-y-2">
        <h5 class="text-xs font-bold text-neutral-400 uppercase tracking-wider flex items-center gap-2 font-mono">
          <span><span data-ui-icon=swords aria-hidden=true></span></span> Hitos & Hechos Destacados Acumulados
        </h5>
        <div class="space-y-2">
          ${hitos.map(h => `
            <div class="p-3.5 rounded-xl bg-[#0a0a0d] border border-[#222222] text-sm text-neutral-200 leading-relaxed">
              ${escapeHtml(typeof h === 'string' ? h : (h.hito || h.text || JSON.stringify(h)))}
            </div>
          `).join("")}
        </div>
      </div>
      ${locsHtml}
      ${itemsHtml}
    </div>
  `;
}

// =========================================================================
// UNIVERSAL NPC & PC DIRECTORIES
// =========================================================================
let activeNpcCategoryFilter = 'all';

function setNpcCategoryFilter(filter) {
  activeNpcCategoryFilter = filter;
  const chips = document.querySelectorAll(".npc-filter-chip");
  chips.forEach(chip => {
    const f = chip.getAttribute("data-npc-filter");
    if (f === filter) {
      chip.classList.add("active", "bg-amber-500/20", "border-amber-500/40", "text-amber-200");
      chip.classList.remove("bg-slate-900/80", "border-slate-800", "text-slate-400");
    } else {
      chip.classList.remove("active", "bg-amber-500/20", "border-amber-500/40", "text-amber-200");
      chip.classList.add("bg-slate-900/80", "border-slate-800", "text-slate-400");
    }
  });
  filterNpcs();
}

function getNpcCategoryBadge(n) {
  const cat = String(n.category || "").toLowerCase();
  const tipo = String(n.tipo || "").toLowerCase();

  if (cat === "clave" || tipo === "importantes" || tipo === "importante") {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30"><span data-ui-icon=crown aria-hidden=true></span> Clave / Importante</span>`;
  } else if (cat === "aliado") {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-sky-500/15 text-cyan-300 border border-sky-500/30"><span data-ui-icon=shield aria-hidden=true></span> Aliado / Compañero</span>`;
  } else if (cat === "invocacion") {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30"><span data-ui-icon=paw aria-hidden=true></span> Invocación / Familiar</span>`;
  } else if (cat === "amenaza") {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-rose-500/15 text-rose-300 border border-rose-500/30"><span data-ui-icon=warning aria-hidden=true></span> Amenaza / Enemigo</span>`;
  } else {
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=swords aria-hidden=true></span> Interacción / Contexto</span>`;
  }
}

function getNpcStatusBadge(n) {
  const status = String(n.status || "activo").toLowerCase();
  if (status === "herido") {
    return `<span class="px-1.5 py-0.5 rounded-md text-[10px] font-medium font-mono bg-amber-950/60 text-amber-300 border border-amber-800/40" title="Estado al final de la sesión: Herido o Revivido"><span data-ui-icon=warning aria-hidden=true></span> Herido</span>`;
  } else if (status === "abatido") {
    return `<span class="px-1.5 py-0.5 rounded-md text-[10px] font-medium font-mono bg-rose-950/60 text-rose-300 border border-rose-800/40" title="Estado al final de la sesión: Abatido o Muerto"><span data-ui-icon=record aria-hidden=true></span> Abatido</span>`;
  } else if (status === "desvanecido") {
    return `<span class="px-1.5 py-0.5 rounded-md text-[10px] font-medium font-mono bg-purple-950/60 text-purple-300 border border-purple-800/40" title="Estado al final de la sesión: Desvanecido"><span data-ui-icon=info aria-hidden=true></span> Desvanecido</span>`;
  } else {
    return `<span class="px-1.5 py-0.5 rounded-md text-[10px] font-medium font-mono bg-emerald-950/60 text-emerald-300 border border-emerald-800/40" title="Estado al final de la sesión: Activo"><span data-ui-icon=check aria-hidden=true></span> Activo</span>`;
  }
}

function renderNpcs(npcs) {
  const container = document.getElementById("npcsContainer");
  if (!container) return;

  const list = npcs || [];

  // Update dynamic counters for category filter chips
  const countAll = list.length;
  let countClave = 0, countAliado = 0, countInvocacion = 0, countAmenaza = 0, countInteraccion = 0;

  list.forEach(n => {
    const c = String(n.category || "").toLowerCase();
    const t = String(n.tipo || "").toLowerCase();
    if (c === "clave" || t === "importantes" || t === "importante") countClave++;
    else if (c === "aliado") countAliado++;
    else if (c === "invocacion") countInvocacion++;
    else if (c === "amenaza") countAmenaza++;
    else countInteraccion++;
  });

  const elAll = document.getElementById("npcCountAll");
  const elClave = document.getElementById("npcCountClave");
  const elAliado = document.getElementById("npcCountAliado");
  const elInvocacion = document.getElementById("npcCountInvocacion");
  const elAmenaza = document.getElementById("npcCountAmenaza");
  const elInteraccion = document.getElementById("npcCountInteraccion");

  if (elAll) elAll.textContent = countAll;
  if (elClave) elClave.textContent = countClave;
  if (elAliado) elAliado.textContent = countAliado;
  if (elInvocacion) elInvocacion.textContent = countInvocacion;
  if (elAmenaza) elAmenaza.textContent = countAmenaza;
  if (elInteraccion) elInteraccion.textContent = countInteraccion;

  if (list.length === 0) {
    container.innerHTML = `<p class="italic text-slate-500 text-xs col-span-2 p-4 text-center">No hay PNJs registrados en la campaña.</p>`;
    return;
  }

  container.innerHTML = "";
  list.forEach(n => {
    const card = document.createElement("div");
    card.className = "npc-card group relative p-4 rounded-xl bg-[#0d0d0d] border border-[#222222] hover:border-amber-500/40 shadow-xl transition-all duration-150 flex flex-col justify-between h-full";

    const cat = String(n.category || "").toLowerCase();
    const t = String(n.tipo || "").toLowerCase();
    let normCat = "interaccion_contexto";
    if (cat === "clave" || t === "importantes" || t === "importante") normCat = "clave";
    else if (cat === "aliado") normCat = "aliado";
    else if (cat === "invocacion") normCat = "invocacion";
    else if (cat === "amenaza") normCat = "amenaza";

    card.setAttribute("data-name", (n.name || "").toLowerCase());
    card.setAttribute("data-role", (n.role || "").toLowerCase());
    card.setAttribute("data-category", normCat);

    const tipoBadge = getNpcCategoryBadge(n);
    const statusBadge = getNpcStatusBadge(n);

    const notesHtml = (n.notes && n.notes.length > 0)
      ? `<ul class="text-[11px] text-neutral-300 space-y-1 list-disc list-inside mt-2 pt-2 border-t border-[#222222]">${n.notes.map(note => `<li>${escapeHtml(note)}</li>`).join('')}</ul>`
      : '';

    card.innerHTML = `
      <div class="flex flex-col flex-1">
        <div class="flex items-start justify-between gap-2 min-h-[52px]">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-1.5">
              <h4 class="text-sm font-bold text-neutral-100 truncate">${escapeHtml(formatCharacterDisplayName(n.name, n.aliases))}</h4>
              ${tipoBadge}
              ${statusBadge}
            </div>
            <p class="text-xs text-amber-300 font-medium mt-1 truncate" title="${escapeHtml(n.role || 'PNJ')}">${escapeHtml(n.role || 'PNJ')}</p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <!-- Botones de Acción Rápida en Hover -->
            <div class="opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center gap-1 mr-1">
              <button type="button" onclick="openEditNpcModal('${escapeHtml(n.name)}')" title="Editar PNJ" class="p-1.5 rounded-xl bg-[#121212] hover:bg-[#1a1a1a] text-neutral-400 hover:text-amber-300 border border-[#262626] hover:border-amber-500/40 active:scale-95 transition cursor-pointer shadow-sm">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
              </button>
              <button type="button" onclick="openMergeEntityModal('npc', '${escapeHtml(n.name)}')" title="Fusionar con otro personaje" class="p-1.5 rounded-xl bg-[#121212] hover:bg-[#1a1a1a] text-neutral-400 hover:text-sky-300 border border-[#262626] hover:border-sky-500/40 active:scale-95 transition cursor-pointer shadow-sm">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
              </button>
            </div>
            <span class="px-2 py-0.5 rounded-lg text-[10px] bg-[#121212] text-neutral-400 border border-[#262626] font-mono shrink-0">
              Sesión #${n.first_seen_session || 1}
            </span>
          </div>
        </div>
        <div class="border-t border-[#222222] mt-2.5 pt-2 flex-1">
          ${notesHtml}
        </div>
      </div>
    `;
    container.appendChild(card);
  });
  filterNpcs();
}

function filterNpcs() {
  const query = (document.getElementById("npcSearchInput")?.value || "").toLowerCase().trim();
  const cards = document.querySelectorAll(".npc-card");
  cards.forEach(card => {
    const name = card.getAttribute("data-name") || "";
    const role = card.getAttribute("data-role") || "";
    const cat = card.getAttribute("data-category") || "";

    const matchesQuery = !query || name.includes(query) || role.includes(query);
    const matchesCategory = (activeNpcCategoryFilter === 'all') || (cat === activeNpcCategoryFilter);

    if (matchesQuery && matchesCategory) {
      card.classList.remove("hidden");
    } else {
      card.classList.add("hidden");
    }
  });
}

function toggleEditNpcModal(show) {
  const modal = document.getElementById("editNpcModal");
  const box = document.getElementById("editNpcModalBox");
  if (!modal || !box) return;
  if (show) {
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
  } else {
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
}

function openEditNpcModal(npcName) {
  const state = currentWikiCampaignState || currentCampaignState || {};
  const npcs = state.npcs || [];
  const target = npcs.find(n => (n.name || "").trim().toLowerCase() === npcName.trim().toLowerCase());

  const origNameInput = document.getElementById("editNpcOriginalName");
  const nameInput = document.getElementById("editNpcNameInput");
  const roleInput = document.getElementById("editNpcRoleInput");
  const catSelect = document.getElementById("editNpcCategorySelect");
  const statusSelect = document.getElementById("editNpcStatusSelect");
  const errEl = document.getElementById("editNpcError");

  if (errEl) errEl.classList.add("hidden");

  if (origNameInput) origNameInput.value = target ? (target.name || npcName) : npcName;
  if (nameInput) nameInput.value = target ? (target.name || npcName) : npcName;
  if (roleInput) roleInput.value = target ? (target.role || "") : "";

  if (catSelect) {
    let catVal = "interaccion_contexto";
    if (target) {
      if (target.category) catVal = target.category.toLowerCase();
      else if (target.tipo === "importantes" || target.tipo === "importante") catVal = "clave";
    }
    catSelect.value = catVal;
  }

  if (statusSelect) {
    statusSelect.value = target ? (target.status || "activo").toLowerCase() : "activo";
  }

  toggleEditNpcModal(true);
}

async function submitEditNpc() {
  const origNameInput = document.getElementById("editNpcOriginalName");
  const nameInput = document.getElementById("editNpcNameInput");
  const roleInput = document.getElementById("editNpcRoleInput");
  const catSelect = document.getElementById("editNpcCategorySelect");
  const statusSelect = document.getElementById("editNpcStatusSelect");
  const errEl = document.getElementById("editNpcError");
  const btn = document.getElementById("saveNpcBtn");

  const origName = (origNameInput ? origNameInput.value : "").trim();
  const newName = (nameInput ? nameInput.value : "").trim();
  const role = (roleInput ? roleInput.value : "").trim();
  const category = (catSelect ? catSelect.value : "interaccion_contexto").trim();
  const status = (statusSelect ? statusSelect.value : "activo").trim();

  if (!newName) {
    if (errEl) {
      errEl.textContent = "El nombre del personaje no puede estar vacío.";
      errEl.classList.remove("hidden");
    }
    return;
  }

  const campSelect = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (campSelect && campSelect.value && campSelect.value.trim()) ||
                   (campInput && campInput.value && campInput.value.trim()) ||
                   (currentWikiCampaignState && currentWikiCampaignState.campaign_name) ||
                   (currentCampaignState && currentCampaignState.campaign_name) || "";

  if (!campName) {
    if (errEl) {
      errEl.textContent = "No hay ninguna campaña seleccionada.";
      errEl.classList.remove("hidden");
    }
    return;
  }

  const origBtnText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span><span data-ui-icon=clock aria-hidden=true></span></span><span>Guardando...</span>`;
  }
  if (errEl) errEl.classList.add("hidden");

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/npcs/${encodeURIComponent(origName)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        new_name: newName,
        role: role,
        category: category,
        status: status,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Error al actualizar el PNJ.");
    }

    const data = await res.json();
    if (data.campaign_state) {
      currentWikiCampaignState = data.campaign_state;
      currentCampaignState = data.campaign_state;
    } else {
      const npcs = (currentWikiCampaignState && currentWikiCampaignState.npcs) || [];
      const target = npcs.find(n => (n.name || "").trim().toLowerCase() === origName.toLowerCase());
      if (target) {
        target.name = newName;
        target.role = role;
        target.category = category;
        target.status = status;
        if (category === "clave") target.tipo = "importantes";
        else target.tipo = "interaccion_contexto";
      }
    }

    toggleEditNpcModal(false);
    renderNpcs((currentWikiCampaignState && currentWikiCampaignState.npcs) || []);
    if (typeof showTransientAlert === "function") {
      showTransientAlert(`PNJ '${newName}' actualizado correctamente`, "success");
    } else if (typeof showAlert === "function") {
      showSuccessAlert(`PNJ '${newName}' actualizado correctamente.`);
    }
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || "Error al conectar con el servidor.";
      errEl.classList.remove("hidden");
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origBtnText;
    }
  }
}

function renderUniversalPcs(pcs) {
  const container = document.getElementById("pcsContainer");
  const badge = document.getElementById("universalPcTotalBadge");
  const list = pcs || [];
  if (badge) {
    badge.textContent = `${list.length} ${list.length === 1 ? 'Personaje' : 'Personajes'}`;
  }
  if (!container) return;

  if (list.length === 0) {
    container.innerHTML = `
      <div class="col-span-2 text-center py-8 text-slate-500 space-y-1">
        <p class="text-2xl"><span data-ui-icon=shield aria-hidden=true></span></p>
        <p class="text-xs">No hay aventureros registrados en el Directorio de PCs todavía.</p>
        <p class="text-[11px] text-slate-600">Se registrarán automáticamente conforme se procesen las sesiones de la campaña.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = "";
  list.forEach(pc => {
    const charName = pc.personaje || pc.character_name || "Aventurero";
    const charDisplayName = typeof formatCharacterDisplayName === "function" ? formatCharacterDisplayName(charName, pc.aliases || []) : charName;
    const player = pc.jugador || pc.player_name || "-";
    const species = pc.especie || pc.species || "-";
    const cls = pc.clase || pc.role || "-";
    const subcls = pc.subclase || pc.subclass || "-";
    const debut = pc.debut_sesion ? `Debut: Sesión #${pc.debut_sesion}` : "Debut: Sesión #1";
    const hitos = pc.hitos_acumulados || [];

    const card = document.createElement("div");
    card.className = "p-4 rounded-xl bg-slate-900/90 border border-slate-800/80 hover:border-amber-500/40 backdrop-blur-sm shadow-md transition-all duration-150 space-y-3";

    let hitosHtml = "";
    if (hitos.length > 0) {
      hitosHtml = `
        <div class="pt-2.5 border-t border-slate-800/80 space-y-1.5">
          <span class="text-[11px] font-semibold text-amber-400 flex items-center gap-1.5">
            <span><span data-ui-icon=star aria-hidden=true></span></span> Hitos y Logros Acumulados:
          </span>
          <ul class="text-[11px] text-slate-300 space-y-1 pl-4 list-disc">
            ${hitos.map(h => `<li>${escapeHtml(h)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div>
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-bold text-slate-100">${escapeHtml(charDisplayName)}</h4>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30">
              ${escapeHtml(debut)}
            </span>
          </div>
          <p class="text-xs text-slate-400 font-medium mt-0.5">Jugador: <strong class="text-slate-200">${escapeHtml(player)}</strong></p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="px-2 py-0.5 rounded-md bg-slate-950/70 text-slate-300 border border-slate-800/80 font-mono text-[11px]">
          Especie: <strong class="text-slate-100">${escapeHtml(species)}</strong>
        </span>
        <span class="px-2 py-0.5 rounded-md bg-slate-950/70 text-amber-300/90 border border-amber-900/40 font-mono text-[11px]">
          Clase: <strong class="text-amber-200">${escapeHtml(cls)}</strong>
        </span>
        ${subcls && subcls !== '-' ? `
        <span class="px-2 py-0.5 rounded-md bg-slate-950/70 text-sky-300/90 border border-sky-900/40 font-mono text-[11px]">
          Subclase: <strong class="text-sky-200">${escapeHtml(subcls)}</strong>
        </span>` : ''}
      </div>
      ${hitosHtml}
    `;
    container.appendChild(card);
  });
}

// =========================================================================
// QUEST TRACKER (D&D INGEST VIEW)
// =========================================================================
function renderQuests(quests) {
  if (typeof currentWorkspace !== "undefined" && currentWorkspace === "work_and_study") {
    return;
  }
  const container = document.getElementById("questsContainer");
  if (!container) return;
  if (!quests || quests.length === 0) {
    container.innerHTML = `<p class="italic text-slate-500 text-xs">No hay misiones activas en el diario de campaña.</p>`;
    return;
  }

  const tipoBadges = {
    principal: `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30"><span data-ui-icon=star aria-hidden=true></span> Principal</span>`,
    secundaria: `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30"><span data-ui-icon=swords aria-hidden=true></span> Secundaria</span>`,
    opcional: `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=compass aria-hidden=true></span> Opcional</span>`,
    misterios_abiertos: `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30"><span data-ui-icon=compass aria-hidden=true></span> Misterios Abiertos</span>`,
    misterio: `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30"><span data-ui-icon=compass aria-hidden=true></span> Misterios Abiertos</span>`,
  };

  container.innerHTML = "";
  quests.forEach(q => {
    const isCompleted = q.status === "completed";
    const isFailed = q.status === "failed";
    const qCard = document.createElement("div");
    qCard.className = `p-4 rounded-xl border backdrop-blur-sm shadow-md transition-all duration-150 space-y-2.5 ${
      isCompleted 
        ? "bg-slate-950/70 border-emerald-800/40" 
        : (isFailed ? "bg-rose-950/20 border-rose-800/40" : "bg-slate-900/90 border-slate-800/80 hover:border-slate-700/80")
    }`;

    let statusBadge = "";
    if (isCompleted) {
      statusBadge = `<button type="button" onclick="toggleQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-90 active:scale-[0.98] transition px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"><span data-ui-icon=check aria-hidden=true></span> COMPLETADA</button>`;
    } else if (isFailed) {
      statusBadge = `<button type="button" onclick="toggleQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-90 active:scale-[0.98] transition px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30"><span data-ui-icon=record aria-hidden=true></span> FRACASADA</button>`;
    } else {
      statusBadge = `<button type="button" onclick="toggleQuestStatus('${escapeHtml(q.id)}', '${q.status}')" title="Clic para alternar estado" class="cursor-pointer hover:opacity-90 active:scale-[0.98] transition px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono bg-sky-500/20 text-sky-300 border border-sky-500/30">EN PROGRESO</button>`;
    }

    const qTipo = (q.tipo || "principal").toLowerCase();
    const tipoBadge = tipoBadges[qTipo] || tipoBadges.principal;

    let subsHtml = "";
    if (q.subobjectives && q.subobjectives.length > 0) {
      subsHtml = `
        <div class="mt-3 space-y-1.5 pt-2.5 border-t border-slate-800/80">
          <span class="text-[11px] font-semibold text-slate-400">Objetivos:</span>
          <div class="space-y-1">
            ${q.subobjectives.map((sub, sIdx) => `
              <label class="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer hover:text-white transition duration-150 group">
                <input type="checkbox" ${sub.completed ? 'checked' : ''} 
                  onchange="toggleSubobjective('${escapeHtml(q.id)}', ${sIdx}, this.checked)"
                  class="w-4 h-4 rounded bg-slate-950 border-slate-700 text-sky-600 focus:ring-0 focus:ring-offset-0 cursor-pointer">
                <span class="${sub.completed ? 'line-through text-slate-500' : 'text-slate-200'} transition-all duration-150">${escapeHtml(sub.text)}</span>
              </label>
            `).join('')}
          </div>
        </div>
      `;
    }

    qCard.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h4 class="text-sm font-bold ${isCompleted ? 'text-slate-400 line-through' : (isFailed ? 'text-rose-200' : 'text-slate-100')}">${escapeHtml(q.title)}</h4>
            ${tipoBadge}
            ${statusBadge}
          </div>
          ${q.context ? `<p class="text-xs text-slate-300 mt-1 leading-relaxed">${escapeHtml(q.context)}</p>` : ''}
          ${q.lifecycle_notes ? `<p class="text-[10px] text-slate-400 mt-1 italic font-mono">${escapeHtml(q.lifecycle_notes)}</p>` : ''}
          ${subsHtml}
        </div>
      </div>
    `;
    container.appendChild(qCard);
  });
}

async function toggleSubobjective(questId, subIdx, completed) {
  if (typeof currentCampaignState !== "undefined" && currentCampaignState && currentCampaignState.quests) {
    const q = currentCampaignState.quests.find(x => x.id === questId);
    if (q && q.subobjectives && q.subobjectives[subIdx]) {
      q.subobjectives[subIdx].completed = completed;
      if (q.subobjectives.every(s => s.completed)) {
        q.status = "completed";
      }
      if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(currentCampaignState);
    }
  }
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) return;
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/quests/${encodeURIComponent(questId)}/subobjective`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subobjective_idx: subIdx, completed: completed })
    });
    const data = await res.json();
    if (res.ok && data.campaign_state) {
      if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
      if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);
    }
  } catch (err) {
    console.error("Error toggling subobjective:", err);
  }
}

async function toggleQuestStatus(questId, currentStatus) {
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) return;

  const newStatus = (currentStatus === "completed" || currentStatus === "failed") ? "in_progress" : "completed";
  if (typeof currentCampaignState !== "undefined" && currentCampaignState && currentCampaignState.quests) {
    const q = currentCampaignState.quests.find(x => x.id === questId);
    if (q) {
      q.status = newStatus;
      if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(currentCampaignState);
    }
  }

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/quests/${encodeURIComponent(questId)}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (res.ok && data.campaign_state) {
      if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
      if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);
    }
  } catch (err) {
    console.error("Error toggling quest status:", err);
  }
}

// =========================================================================
// NPC SPELLCHECK MODAL
// =========================================================================
function showNpcSpellcheck(detectedNames) {
  detectedNpcNamesList = detectedNames || [];
  if (detectedNpcNamesList.length === 0) return;

  const modal = document.getElementById("npcSpellcheckCard");
  const listEl = document.getElementById("npcSpellcheckList");
  if (!modal || !listEl) return;

  listEl.innerHTML = "";
  detectedNpcNamesList.forEach(name => {
    const div = document.createElement("div");
    div.className = "bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1.5";
    div.innerHTML = `
      <label class="text-[11px] text-slate-400 font-mono">Nombre detectado:</label>
      <input type="text" data-original-name="${escapeHtml(name)}" value="${escapeHtml(name)}"
        class="npc-spell-input w-full bg-slate-900 border border-slate-700 focus:border-amber-500 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 outline-none transition duration-150">
    `;
    listEl.appendChild(div);
  });

  modal.classList.remove("hidden");
  void modal.offsetWidth; // Force reflow
  modal.classList.remove("opacity-0", "scale-95");
  modal.classList.add("opacity-100", "scale-100");
}

function hideNpcSpellcheck() {
  const modal = document.getElementById("npcSpellcheckCard");
  if (modal) {
    modal.classList.remove("opacity-100", "scale-100");
    modal.classList.add("opacity-0", "scale-95");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 150);
  }
}

async function confirmNpcSpellcheck() {
  const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
  if (!campName) {
    if (typeof showAlert === "function") showAlert("Debes seleccionar o crear una campaña antes de confirmar nombres de PNJs.");
    return;
  }
  const inputs = document.querySelectorAll(".npc-spell-input");
  const corrections = {};

  inputs.forEach(inp => {
    const original = inp.getAttribute("data-original-name");
    const corrected = inp.value.trim();
    if (original && corrected && original !== corrected) {
      corrections[original] = corrected;
    }
  });

  hideNpcSpellcheck();

  if (Object.keys(corrections).length > 0) {
    try {
      const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/finalize-npcs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name_corrections: corrections })
      });
      const data = await res.json();
      if (res.ok && data.campaign_state) {
        if (typeof currentCampaignState !== "undefined") currentCampaignState = data.campaign_state;
        if (typeof updateCampaignViewTabs === "function") updateCampaignViewTabs(data.campaign_state);

        if (typeof currentResult !== "undefined" && currentResult) {
          currentResult.campaign_state = data.campaign_state;
          for (const [oldName, newName] of Object.entries(corrections)) {
            const tokens = [oldName];
            if (oldName.includes("/")) {
              oldName.split("/").forEach(p => {
                const pt = p.trim();
                if (pt.length >= 3 && !tokens.includes(pt)) tokens.push(pt);
              });
            }
            tokens.sort((a, b) => b.length - a.length);

            for (const tok of tokens) {
              const regex = new RegExp(`\\b${tok.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}\\b`, 'gi');
              if (currentResult.chronicle) currentResult.chronicle = currentResult.chronicle.replace(regex, newName);
              if (currentResult.chronicle_markdown) currentResult.chronicle_markdown = currentResult.chronicle_markdown.replace(regex, newName);
              if (currentResult.session_chapter) {
                if (typeof currentResult.session_chapter === "object") {
                  ["chronicle_text", "closing_expectations", "user_coaching", "markus_coaching", "next_session_script", "recap_text", "episode_synopsis", "title"].forEach(prop => {
                    if (typeof currentResult.session_chapter[prop] === "string") {
                      currentResult.session_chapter[prop] = currentResult.session_chapter[prop].replace(regex, newName);
                    }
                  });
                } else if (typeof currentResult.session_chapter === "string") {
                  currentResult.session_chapter = currentResult.session_chapter.replace(regex, newName);
                }
              }
              if (currentResult.recap_text) currentResult.recap_text = currentResult.recap_text.replace(regex, newName);
              if (currentResult.next_session_script) currentResult.next_session_script = currentResult.next_session_script.replace(regex, newName);
              if (Array.isArray(currentResult.detected_pcs)) {
                currentResult.detected_pcs.forEach(p => {
                  if (p.rol_en_sesion) p.rol_en_sesion = p.rol_en_sesion.replace(regex, newName);
                  if (Array.isArray(p.hitos_acumulados)) {
                    p.hitos_acumulados = p.hitos_acumulados.map(h => typeof h === 'string' ? h.replace(regex, newName) : h);
                  }
                });
              }
              if (Array.isArray(currentResult.universal_pcs)) {
                currentResult.universal_pcs.forEach(p => {
                  if (p.session_role) p.session_role = p.session_role.replace(regex, newName);
                  if (Array.isArray(p.hitos_acumulados)) {
                    p.hitos_acumulados = p.hitos_acumulados.map(h => typeof h === 'string' ? h.replace(regex, newName) : h);
                  }
                });
              }
              if (Array.isArray(currentResult.detected_npc_names)) {
                currentResult.detected_npc_names = currentResult.detected_npc_names.map(n => (n.toLowerCase() === tok.toLowerCase() || n.toLowerCase() === oldName.toLowerCase()) ? newName : n);
              }
              if (Array.isArray(currentResult.npcs)) {
                currentResult.npcs.forEach(n => {
                  if (n.name && (n.name.toLowerCase() === tok.toLowerCase() || n.name.toLowerCase() === oldName.toLowerCase())) n.name = newName;
                  if (n.notes) n.notes = typeof n.notes === 'string' ? n.notes.replace(regex, newName) : (Array.isArray(n.notes) ? n.notes.map(nt => typeof nt === 'string' ? nt.replace(regex, newName) : nt) : n.notes);
                  if (n.role) n.role = n.role.replace(regex, newName);
                  if (n.description) n.description = n.description.replace(regex, newName);
                });
              }
              if (Array.isArray(currentResult.updated_npcs)) {
                currentResult.updated_npcs.forEach(n => {
                  if (n.name && (n.name.toLowerCase() === tok.toLowerCase() || n.name.toLowerCase() === oldName.toLowerCase())) n.name = newName;
                  if (n.notes) n.notes = typeof n.notes === 'string' ? n.notes.replace(regex, newName) : (Array.isArray(n.notes) ? n.notes.map(nt => typeof nt === 'string' ? nt.replace(regex, newName) : nt) : n.notes);
                  if (n.role) n.role = n.role.replace(regex, newName);
                  if (n.description) n.description = n.description.replace(regex, newName);
                });
              }
            }
          }
          if (typeof displayResults === "function") {
            displayResults(currentResult);
          }
        }
        if (typeof showAlert === "function") showSuccessAlert("Nombres de PNJs corregidos y actualizados en el documento y campaña.");
      }
    } catch (err) {
      console.error("Error finalizing NPCs:", err);
    }
  }
}

function triggerManualNpcSpellcheck() {
  const currentNpcs = (typeof currentCampaignState !== "undefined" && currentCampaignState && currentCampaignState.npcs) ||
                      (typeof currentResult !== "undefined" && currentResult && currentResult.npcs) || [];
  let names = currentNpcs.map(n => n.name).filter(Boolean);
  if (names.length === 0 && typeof currentResult !== "undefined" && currentResult && Array.isArray(currentResult.updated_npcs)) {
    names = currentResult.updated_npcs.map(n => n.name).filter(Boolean);
  }
  if (names.length === 0) {
    if (typeof showAlert === "function") showAlert("No hay PNJs registrados en esta campaña para revisar ortografía.");
    return;
  }
  showNpcSpellcheck(names);
}

// =========================================================================
// GRIMORIO COMPLETO (.MD) RENDERER
// =========================================================================
function renderJournal(state) {
  const journalEl = document.getElementById("journalView");
  if (!state) return;
  let mdLines = [];
  mdLines.push(`#  Grimorio de Campaña: ${state.campaign_name || 'Campaña'}`);
  mdLines.push(`*Última sesión registrada: #${state.last_session || 0} &bull; Actualizado: ${state.updated_at ? state.updated_at.substring(0, 10) : ''}*\n`);

  const sessions = state.sessions || [];
  if (sessions.length > 0) {
    mdLines.push(`##  Capítulos de Campaña`);
    sessions.forEach(s => {
      mdLines.push(`### Capítulo ${s.session_number}: ${s.title || ''}`);
      let secNum = 1;
      if (s.chronicle_text) {
        mdLines.push(`**${secNum}. Crónica Narrativa y Combates:**\n${s.chronicle_text}\n`);
        secNum++;
      }
      if (s.closing_expectations) {
        mdLines.push(`**${secNum}. Cierre de Mesa, Decisiones y Expectativas:**\n${s.closing_expectations}\n`);
        secNum++;
      }
      const coaching = s.user_coaching || s.markus_coaching;
      if (coaching && coaching.trim()) {
        const charName = (s.user_character && s.user_character.character_name) || 'Markus Veyl';
        mdLines.push(`**${secNum}. Reflexión de Rol y Compañerismo: ${charName}:**\n${coaching}\n`);
        secNum++;
      }
      const synopsis = s.episode_synopsis;
      if (synopsis && synopsis.trim()) {
        mdLines.push(`** Sinopsis Ejecutiva del Episodio:**\n${synopsis}\n`);
      } else {
        const scriptText = s.next_session_script || s.recap_text;
        if (scriptText && scriptText.trim()) {
          const nextNum = (s.session_number || 1) + 1;
          mdLines.push(`**${secNum}.  Guion para abrir la Sesión #${nextNum} (Para leer en voz alta):**\n> ${scriptText}\n`);
        }
      }
      mdLines.push(`---\n`);
    });
  }
  const grimorioEl = document.getElementById("grimorio-content");
  if (grimorioEl) {
    grimorioEl.innerHTML = renderMarkdownWithKaTeX(mdLines.join("\n\n"));
  } else if (journalEl) {
    journalEl.innerHTML = `<div id="grimorio-content">${renderMarkdownWithKaTeX(mdLines.join("\n\n"))}</div>`;
  }
}

// Window Global Exports
window.syncWikiCampaignSelector = syncWikiCampaignSelector;
window.refreshWikiCampaigns = refreshWikiCampaigns;
window.onWikiCampaignSelected = onWikiCampaignSelected;
window.refreshWikiView = refreshWikiView;
window.setWikiCategory = setWikiCategory;
window.renderWikiCategoryPills = renderWikiCategoryPills;
window.onWikiSearchInput = onWikiSearchInput;
window.renderWikiEntityList = renderWikiEntityList;
window.selectWikiEntity = selectWikiEntity;
window.findAndSelectWikiEntity = findAndSelectWikiEntity;
window.getAssociatedLocationsForCharacter = getAssociatedLocationsForCharacter;
window.getHeldItemsForCharacter = getHeldItemsForCharacter;
window.buildAllPcsGridHtml = buildAllPcsGridHtml;
window.renderWikiDossier = renderWikiDossier;
window.buildLocationDossierHtml = buildLocationDossierHtml;
window.buildItemDossierHtml = buildItemDossierHtml;
window.switchWikiSessionSubtab = switchWikiSessionSubtab;
window.filterWikiSessionTranscript = filterWikiSessionTranscript;
window.copyWikiSessionTranscript = copyWikiSessionTranscript;
window.downloadWikiSessionTranscript = downloadWikiSessionTranscript;
window.buildSessionDossierHtml = buildSessionDossierHtml;
window.buildQuestDossierHtml = buildQuestDossierHtml;
window.toggleWikiSubobjective = toggleWikiSubobjective;
window.toggleWikiQuestStatus = toggleWikiQuestStatus;
window.toggleMergeEntityModal = toggleMergeEntityModal;
window.openMergeEntityModal = openMergeEntityModal;
window.submitMergeEntity = submitMergeEntity;
window.toggleEditNpcModal = toggleEditNpcModal;
window.openEditNpcModal = openEditNpcModal;
window.submitEditNpc = submitEditNpc;
window.setNpcCategoryFilter = setNpcCategoryFilter;
window.buildNpcDossierHtml = buildNpcDossierHtml;
window.buildPcDossierHtml = buildPcDossierHtml;
window.renderNpcs = renderNpcs;
window.filterNpcs = filterNpcs;
window.renderUniversalPcs = renderUniversalPcs;
window.renderQuests = renderQuests;
window.toggleSubobjective = toggleSubobjective;
window.toggleQuestStatus = toggleQuestStatus;
window.showNpcSpellcheck = showNpcSpellcheck;
window.hideNpcSpellcheck = hideNpcSpellcheck;
window.confirmNpcSpellcheck = confirmNpcSpellcheck;
window.triggerManualNpcSpellcheck = triggerManualNpcSpellcheck;
window.renderJournal = renderJournal;
window.loadCharacterView = loadCharacterView;
window.loadCharactersForCampaign = loadCharactersForCampaign;
window.renderCharacterSelectDropdown = renderCharacterSelectDropdown;
window.onCampaignDropdownChanged = onCampaignDropdownChanged;
window.onUserCharacterSelected = onUserCharacterSelected;
window.toggleNewCharacterMode = toggleNewCharacterMode;
window.saveCharacterBackstory = saveCharacterBackstory;

// =========================================================================
// WIKI SESSION WORD EXPORT (.DOCX)
// =========================================================================
function populateWikiSessionExportDropdown(rawSessions, selectedNum = null) {
  const selectEl = document.getElementById("wikiSessionExportSelect");
  const containerEl = document.getElementById("wikiSessionExportContainer");
  if (!selectEl) return;

  const sessionsList = Array.isArray(rawSessions) ? rawSessions : Object.values(rawSessions || {});
  if (!sessionsList || sessionsList.length === 0) {
    if (containerEl) containerEl.classList.add("hidden");
    selectEl.innerHTML = '<option value="">Sin sesiones</option>';
    return;
  }

  if (containerEl) containerEl.classList.remove("hidden");

  const sorted = [...sessionsList].sort((a, b) => {
    const numA = parseInt(a.session_number || a.number || 0, 10);
    const numB = parseInt(b.session_number || b.number || 0, 10);
    return numB - numA;
  });

  const maxNum = sorted.length > 0 ? (sorted[0].session_number || sorted[0].number || "1") : "1";
  const targetVal = selectedNum ? String(selectedNum) : String(maxNum);

  selectEl.innerHTML = sorted.map((s, idx) => {
    const num = String(s.session_number || s.number || (sorted.length - idx));
    const rawTitle = (s.session_title || s.title || "").trim();
    const cleanTitle = rawTitle.replace(/^(?:sesi[oó]n|session)\s*#?\d+\s*[:\-]\s*/i, "").trim();
    const isLatest = idx === 0;
    const label = isLatest
      ? `Sesión #${num} (Última)${cleanTitle ? `: ${cleanTitle}` : ""}`
      : `Sesión #${num}${cleanTitle ? `: ${cleanTitle}` : ""}`;
    return `<option value="${escapeHtml(num)}">${escapeHtml(label)}</option>`;
  }).join("");

  selectEl.value = targetVal;
}

function updateWikiSessionExportSelect(state) {
  const rawSessions = (state && (state.sessions || state.chronicles)) || [];
  populateWikiSessionExportDropdown(rawSessions);
}

function onWikiSessionExportSelectChanged(val) {
  const num = parseInt(val);
  if (num && currentWikiCampaignState) {
    const rawSessions = currentWikiCampaignState.sessions || currentWikiCampaignState.chronicles || [];
    const sessions = Array.isArray(rawSessions) ? rawSessions : Object.values(rawSessions);
    const s = sessions.find(x => parseInt(x.session_number || x.number || 0) === num);
    if (s && activeWikiCategory === "sessions") {
      selectWikiEntity("session", num, s);
    }
  }
}

function downloadSelectedWikiSessionDocx(cleanMode = false) {
  const select = document.getElementById("wikiCampaignSelect");
  const campInput = document.getElementById("campaignNameInput");
  const campName = (select && select.value && select.value.trim()) || (campInput && campInput.value && campInput.value.trim());
  if (!campName) {
    if (typeof showAlert === "function") showAlert("Selecciona una campaña primero para descargar la sesión.");
    else alert("Selecciona una campaña primero para descargar la sesión.");
    return;
  }
  const sessionSelect = document.getElementById("wikiSessionExportSelect");
  let num = sessionSelect ? parseInt(sessionSelect.value) : null;
  if (!num && currentWikiSessionData) {
    num = currentWikiSessionData.session_number;
  }
  if (!num && currentWikiCampaignState) {
    const rawSessions = currentWikiCampaignState.sessions || currentWikiCampaignState.chronicles || [];
    const sessions = Array.isArray(rawSessions) ? rawSessions : Object.values(rawSessions);
    if (sessions.length > 0) {
      num = sessions[sessions.length - 1].session_number || sessions[sessions.length - 1].number;
    }
  }
  if (!num) num = 1;

  const includeCoaching = !cleanMode;
  const targetUrl = `/api/campaigns/${encodeURIComponent(campName)}/session/${encodeURIComponent(num)}/download-docx?include_coaching=${includeCoaching}`;
  if (typeof navigateToDownload === "function") {
    navigateToDownload(targetUrl);
  } else {
    window.location.href = targetUrl;
  }
}

window.populateWikiSessionExportDropdown = populateWikiSessionExportDropdown;
window.updateWikiSessionExportSelect = updateWikiSessionExportSelect;
window.onWikiSessionExportSelectChanged = onWikiSessionExportSelectChanged;
window.downloadSelectedWikiSessionDocx = downloadSelectedWikiSessionDocx;
