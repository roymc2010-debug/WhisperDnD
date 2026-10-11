// =========================================================================
// WhisperDnD - roster.js
// Roster de campaña, selección de participantes, especies D&D y Discord RPC
// =========================================================================

// Opciones oficiales D&D 5e y 5.5e
const CLASS_OPTIONS = [
  "Dungeon Master (DM)",
  "Bárbaro (Barbarian)",
  "Bardo (Bard)",
  "Clérigo (Cleric)",
  "Druida (Druid)",
  "Guerrero (Fighter)",
  "Monje (Monk)",
  "Paladín (Paladin)",
  "Explorador (Ranger)",
  "Pícaro (Rogue)",
  "Hechicero (Sorcerer)",
  "Brujo (Warlock)",
  "Mago (Wizard)",
  "Artífice (Artificer)",
  "Otro / Personalizado"
];

// Roster por defecto: El grupo oficial de campaña
const DEFAULT_ROSTER = [
  {
    player_name: "Beta",
    character_name: "(DM)",
    species: "(N/A - DM)",
    role: "Dungeon Master (DM)",
    subclass: "N/A",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "Roymc89",
    character_name: "Markus Veyl",
    species: "Humano",
    role: "Guerrero (Fighter)",
    subclass: "Battle Master",
    discord_user_id: "",
    is_user: true,
    is_user_character: true
  },
  {
    player_name: "IDarkLink",
    character_name: "Atou Shadowgrace",
    species: "Elfo",
    role: "Monje (Monk)",
    subclass: "Warrior of Shadow",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "Drowser45",
    character_name: "Meg'lax",
    species: "Lizardfolk (Hombre Lagarto)",
    role: "Hechicero (Sorcerer)",
    subclass: "Wild Magic",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "Acher08",
    character_name: "Selen",
    species: "Shifter (Cambiante)",
    role: "Pícaro (Rogue)",
    subclass: "Phantom",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "moonixb",
    character_name: "Velith",
    species: "Tiefling",
    role: "Bardo (Bard)",
    subclass: "College of Lore",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  }
];

// Roster limpio por defecto para campañas externas / nuevas
const CLEAN_ROSTER = [
  {
    player_name: "",
    character_name: "(DM)",
    species: "(N/A - DM)",
    role: "Dungeon Master (DM)",
    subclass: "N/A",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "",
    character_name: "",
    species: "",
    role: "",
    subclass: "",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "",
    character_name: "",
    species: "",
    role: "",
    subclass: "",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  },
  {
    player_name: "",
    character_name: "",
    species: "",
    role: "",
    subclass: "",
    discord_user_id: "",
    is_user: false,
    is_user_character: false
  }
];

let cachedDiscordParticipants = [];
let _rosterDebounceTimer = null;

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

function registerDynamicSpecies(val) {
  if (!val) return;
  const clean = val.trim();
  if (!clean || clean.length < 2 || clean === "(N/A - DM)" || clean === "-") return;
  const datalist = document.getElementById("species-options");
  if (!datalist) return;
  const existing = Array.from(datalist.options).map(o => o.value.trim().toLowerCase());
  if (!existing.includes(clean.toLowerCase())) {
    const opt = document.createElement("option");
    opt.value = clean;
    datalist.appendChild(opt);
    try {
      const stored = JSON.parse(localStorage.getItem("custom_species_list") || "[]");
      if (!stored.map(s => s.toLowerCase()).includes(clean.toLowerCase())) {
        stored.push(clean);
        localStorage.setItem("custom_species_list", JSON.stringify(stored));
      }
    } catch (e) {
      console.warn("Error storing custom species in localStorage:", e);
    }
  }
}

function initCustomSpeciesList() {
  try {
    const stored = JSON.parse(localStorage.getItem("custom_species_list") || "[]");
    if (Array.isArray(stored)) {
      stored.forEach(s => registerDynamicSpecies(s));
    }
  } catch (e) {
    console.warn("Error initializing custom species list:", e);
  }
}

function isClassMatch(savedVal, optVal) {
  if (!savedVal || !optVal) return false;
  const s = savedVal.trim().toLowerCase();
  const o = optVal.trim().toLowerCase();
  if (s === o || o.includes(s) || s.includes(o)) return true;
  const sNorm = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const oNorm = o.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  return sNorm === oNorm || oNorm.includes(sNorm) || sNorm.includes(oNorm);
}

function setSelectValueFlexible(selectEl, savedVal) {
  if (!selectEl || !savedVal) return;
  const options = Array.from(selectEl.options);
  const match = options.find(opt => isClassMatch(savedVal, opt.value) || isClassMatch(savedVal, opt.textContent));
  if (match) {
    selectEl.value = match.value;
  } else {
    const newOpt = document.createElement("option");
    newOpt.value = savedVal;
    newOpt.textContent = savedVal;
    selectEl.appendChild(newOpt);
    selectEl.value = savedVal;
  }
}

function getDiscordDisplayHandle(selectedId, playerName = "") {
  if (!selectedId) return "";
  selectedId = selectedId.toString().trim();
  if (Array.isArray(cachedDiscordParticipants) && cachedDiscordParticipants.length > 0) {
    const found = cachedDiscordParticipants.find(p => (p.user_id || "").toString().trim() === selectedId);
    if (found) {
      const name = found.username || found.display_name;
      return `@${name.replace(/^@/, '')}`;
    }
  }
  if (/[a-zA-Z_]/.test(selectedId)) {
    return `@${selectedId.replace(/^@/, '')}`;
  }
  if (playerName && playerName.trim() && !["jugador", "dungeon master", "dm"].includes(playerName.trim().toLowerCase())) {
    return `@${playerName.trim().replace(/^@/, '')}`;
  }
  return `@${selectedId.length > 8 ? selectedId.slice(0, 6) + '…' : selectedId}`;
}

function buildDiscordSelectOptions(selectedId = "", playerName = "") {
  selectedId = (selectedId || "").toString().trim();
  let html = '<option value="">-- Sin Vincular --</option>';
  let foundSelected = false;

  (cachedDiscordParticipants || []).forEach(p => {
    const uid = (p.user_id || "").toString().trim();
    const uname = p.username || "Usuario";
    const dname = p.display_name && p.display_name !== uname ? ` (${p.display_name})` : "";
    const label = `@${uname.replace(/^@/, '')}${dname}`;
    const isSel = (uid && uid === selectedId);
    if (isSel) foundSelected = true;
    html += `<option value="${escapeHtml(uid)}"${isSel ? ' selected' : ''}>${escapeHtml(label)}</option>`;
  });

  if (selectedId && !foundSelected) {
    const displayHandle = getDiscordDisplayHandle(selectedId, playerName);
    html += `<option value="${escapeHtml(selectedId)}" selected>${escapeHtml(displayHandle)}</option>`;
  }

  return html;
}

function updateAllDiscordDropdowns() {
  const selects = document.querySelectorAll(".discord-user-select");
  selects.forEach(select => {
    const tr = select.closest("tr");
    const playerInput = tr ? tr.querySelector(".player-name") : null;
    const playerName = playerInput ? playerInput.value.trim() : "";
    const currentVal = (select.value || select.getAttribute("data-saved-value") || "").trim();
    select.innerHTML = buildDiscordSelectOptions(currentVal, playerName);
    select.value = currentVal;
    select.setAttribute("data-saved-value", currentVal);
  });
}

async function resetDiscordAuth() {
  try {
    const res = await fetch("/api/discord/reset-auth", { method: "POST" });
    if (res.ok) {
      if (typeof showAlert === "function") {
        showAlert("🔔 Token de Discord reiniciado. Por favor abre la ventana de tu aplicación de Discord para hacer clic en 'Autorizar' cuando aparezca el diálogo emergente.");
      }
      await refreshDiscordParticipants(true);
    } else {
      if (typeof showAlert === "function") showAlert("No se pudo reiniciar la autorización de Discord.");
    }
  } catch (err) {
    if (typeof showAlert === "function") showAlert("Error al reiniciar autorización de Discord: " + err.message);
  }
}

async function refreshDiscordParticipants(manual = false) {
  const refreshBtn = document.getElementById("btn-refresh-discord");
  const statusText = document.getElementById("discordLiveStatusText");
  if (refreshBtn) refreshBtn.classList.add("opacity-50", "pointer-events-none");
  try {
    const res = await fetch("/api/discord/participants");
    if (res.ok) {
      const data = await res.json();
      cachedDiscordParticipants = Array.isArray(data.participants) ? data.participants : [];
      updateAllDiscordDropdowns();
      if (typeof renderPartyChips === "function") {
        renderPartyChips();
      }

      if (statusText) {
        if (data.connected && cachedDiscordParticipants.length > 0) {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block"></span> <span class="text-emerald-300 font-semibold">Discord: Conectado a #${data.channel_name || 'Voz'} (${cachedDiscordParticipants.length} jugadores)</span>`;
        } else if (data.connected) {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span> <span class="text-emerald-300 font-medium">Discord: Conectado a #${data.channel_name || 'Voz'} (solo tú en la sala)</span>`;
        } else if (data.auth_state === "authorizing") {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-ping inline-block"></span> <span class="text-amber-300 font-medium">Discord: Esperando que hagas clic en 'Autorizar' en tu app de Discord...</span>`;
        } else if (data.auth_state === "denied") {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-400 inline-block"></span> <span class="text-rose-300 font-medium">Discord: Autorización requerida (haz clic en Reautorizar)</span>`;
        } else if (data.rpc_connected) {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 inline-block"></span> <span class="text-amber-300">Discord: Conectado (no estás en un canal de voz)</span>`;
        } else {
          statusText.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500 inline-block"></span> <span class="text-slate-400">Discord: Desconectado (inicia sesión en la app para diarización)</span>`;
        }
      }

      if (manual) {
        const count = cachedDiscordParticipants.length;
        const ch = data.channel_name ? ` en "${data.channel_name}"` : "";
        if (data.connected && count > 0) {
          const badge = document.getElementById("saveStatusBadge");
          if (badge) {
            badge.textContent = `🎧 ${count} usuario(s) detectado(s)${ch}`;
            badge.className = "text-sky-400 text-xs font-semibold";
            badge.classList.remove("hidden");
            setTimeout(() => {
              badge.classList.add("hidden");
              badge.className = "hidden text-emerald-400 text-xs font-semibold animate-pulse";
              badge.textContent = "✓ Guardado";
            }, 3500);
          }
        } else if (data.auth_state === "authorizing") {
          if (typeof showAlert === "function") showAlert("🔔 Abre la app de Discord en tu PC. Aparecerá una ventana emergente pidiéndote autorización; haz clic en 'Autorizar' para vincular las voces al Roster.");
        } else if (data.connected) {
          if (typeof showAlert === "function") showAlert(`🎧 Discord conectado al canal de voz${ch}, pero no hay otros participantes en la llamada.`);
        } else {
          if (typeof showAlert === "function") showAlert("🎧 Discord local no detectado o no estás conectado a un canal de voz activo.");
        }
      }
    }
  } catch (err) {
    console.warn("Error refreshing Discord participants:", err);
    if (manual && typeof showAlert === "function") showAlert("⚠️ No se pudo consultar el cliente local de Discord: " + err.message);
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("opacity-50", "pointer-events-none");
  }
}

function renderDMRow(dmName = "", dmDiscordId = "") {
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return null;
  const tr = document.createElement("tr");
  tr.className = "hover:bg-slate-900/60 transition-colors duration-150 bg-slate-950/60 border-b border-slate-800/80";
  tr.dataset.isUser = "false";
  const discordOptionsHtml = buildDiscordSelectOptions(dmDiscordId, dmName);
  tr.innerHTML = `
    <td class="py-2.5 px-1 text-center align-middle">
      <span class="text-slate-700 text-xs cursor-not-allowed select-none font-mono" title="El DM no puede ser el personaje del jugador">-</span>
      <input type="hidden" data-field="is_user_character" value="false">
    </td>
    <td class="py-2.5 px-3">
      <input type="text" data-field="player_name" value="${escapeHtml(dmName || '')}" oninput="saveCurrentRoster()" placeholder="Nombre del DM..." class="player-name w-full bg-slate-950/80 border border-amber-900/50 hover:border-amber-700/60 focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-500 outline-none transition duration-150 font-medium">
    </td>
    <td class="py-2.5 px-3">
      <input type="text" data-field="character_name" disabled readonly value="(DM)" class="char-name w-full bg-slate-950 border border-amber-900/30 rounded-lg px-2.5 py-1.5 text-xs text-amber-300 font-bold font-mono outline-none cursor-not-allowed">
    </td>
    <td class="py-2.5 px-2.5">
      <input type="text" data-field="species" disabled readonly value="(N/A - DM)" class="species-select w-full bg-slate-950 border border-amber-900/30 rounded-lg px-2.5 py-1.5 text-xs text-amber-300/70 font-mono outline-none cursor-not-allowed">
    </td>
    <td class="py-2.5 px-2.5">
      <select data-field="role" disabled class="class-select w-full bg-slate-950 border border-amber-900/30 rounded-lg px-2 py-1.5 text-xs font-semibold text-amber-300 font-mono outline-none cursor-not-allowed">
        <option value="Dungeon Master (DM)" selected>Dungeon Master (DM)</option>
      </select>
    </td>
    <td class="py-2.5 px-2.5">
      <input type="text" data-field="subclass" disabled readonly value="N/A" class="subclass-input w-full bg-slate-950 border border-amber-900/30 rounded-lg px-2.5 py-1.5 text-xs text-amber-300/70 font-mono outline-none cursor-not-allowed">
    </td>
    <td class="py-2.5 px-2.5">
      <select data-field="discord_user_id" data-saved-value="${escapeHtml(dmDiscordId || '')}" onchange="this.setAttribute('data-saved-value', this.value); saveCurrentRoster()" class="discord-user-select w-full bg-slate-900/90 border border-amber-900/50 hover:border-amber-700/60 focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 rounded-lg px-2 py-1.5 text-xs text-amber-200 outline-none transition duration-150" title="Vincular cuenta de Discord del DM">
        ${discordOptionsHtml}
      </select>
    </td>
    <td class="py-2.5 px-2 text-center">
      <div class="flex items-center justify-center gap-1.5">
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" title="El Dungeon Master siempre está presente">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Presente
        </span>
      </div>
    </td>
  `;
  tbody.appendChild(tr);

  const nameInput = tr.querySelector('.player-name');
  if (nameInput) {
    nameInput.value = dmName || "";
    nameInput.placeholder = "Nombre del DM...";
  }
  const discordSelect = tr.querySelector('.discord-user-select');
  if (discordSelect) {
    discordSelect.setAttribute("data-saved-value", dmDiscordId || "");
    if (dmDiscordId) {
      discordSelect.value = dmDiscordId;
    }
  }

  return tr;
}

function addPlayerRow(playerData = null) {
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return null;
  if (!tbody.querySelector("tr")) {
    renderDMRow("", "");
  }

  const p = playerData || { player_name: "", character_name: "", species: "", role: "", subclass: "", is_user: false, is_user_character: false, discord_user_id: "", is_absent: false };
  if (p && p.species) {
    registerDynamicSpecies(p.species);
  }
  const isUserChar = Boolean(p.is_user || p.is_user_character);
  const isAbsent = Boolean(p.is_absent);
  const discordUserId = (p.discord_user_id || p.discord_id || p.discord || "").toString().trim();
  const tr = document.createElement("tr");
  let rowClasses = isUserChar 
    ? "bg-amber-500/10 border-l-4 border-l-amber-400 border-y border-amber-500/30 shadow-[inset_0_0_24px_rgba(245,158,11,0.12)] transition-all duration-150" 
    : "hover:bg-slate-900/70 transition-colors duration-150 border-b border-slate-900/80";
  if (isAbsent) {
    rowClasses += " opacity-50 bg-amber-950/20";
  }
  tr.className = rowClasses;
  tr.dataset.isUser = isUserChar ? "true" : "false";
  tr.dataset.isAbsent = isAbsent ? "true" : "false";

  const classOptionsHtml = CLASS_OPTIONS.filter(c => c !== "Dungeon Master (DM)").map(opt => `
    <option value="${escapeHtml(opt)}">${escapeHtml(opt)}</option>
  `).join("");
  const discordOptionsHtml = buildDiscordSelectOptions(discordUserId, p.player_name);

  tr.innerHTML = `
    <td class="py-2.5 px-1 text-center align-middle">
      <button type="button" onclick="toggleUserCharacterRow(this)" 
        title="${isUserChar ? '⭐ Tu personaje en esta campaña (Clic para deseleccionar)' : 'Clic para seleccionar/deseleccionar como tu personaje'}" 
        class="star-btn p-1 rounded transition text-sm leading-none flex flex-col items-center justify-center mx-auto group active:scale-90 duration-150 cursor-pointer">
        <span class="${isUserChar ? 'text-amber-400 drop-shadow-[0_0_10px_rgba(251,191,36,0.7)] scale-110' : 'text-slate-600 group-hover:text-amber-300'} text-base transition duration-150">
          ${isUserChar ? '⭐' : '☆'}
        </span>
        ${isUserChar ? '<span class="text-[9px] font-bold font-mono text-amber-300 bg-amber-500/20 px-1 py-0.5 rounded mt-0.5 border border-amber-500/30 whitespace-nowrap leading-tight">[ Tu PJ ]</span>' : ''}
      </button>
      <input type="hidden" data-field="is_user_character" value="${isUserChar ? 'true' : 'false'}">
    </td>
    <td class="py-2.5 px-3">
      <input type="text" data-field="player_name" value="${escapeHtml(p.player_name || '')}" oninput="saveCurrentRoster()" placeholder="Ej. Rodrigo" class="player-name w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-500 outline-none transition duration-150">
    </td>
    <td class="py-2.5 px-3">
      <input type="text" data-field="character_name" value="${escapeHtml(p.character_name || '')}" oninput="saveCurrentRoster()" placeholder="Ej. Kaelen" class="char-name w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-100 placeholder-slate-500 outline-none transition duration-150">
    </td>
    <td class="py-2.5 px-2.5">
      <input list="species-options" data-field="species" value="${escapeHtml(p.species || '')}" oninput="saveCurrentRoster(); registerDynamicSpecies(this.value);" onchange="registerDynamicSpecies(this.value); saveCurrentRoster();" placeholder="Ej. Elfo o escribe especie..." class="species-select w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 outline-none transition duration-150">
    </td>
    <td class="py-2.5 px-2.5">
      <select data-field="role" onchange="saveCurrentRoster()" class="class-select w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none transition duration-150 cursor-pointer">
        <option value="">-- Seleccionar Clase --</option>
        ${classOptionsHtml}
      </select>
    </td>
    <td class="py-2.5 px-2.5">
      <input type="text" data-field="subclass" value="${escapeHtml(p.subclass || '')}" oninput="saveCurrentRoster()" placeholder="Ej. Battle Master" class="subclass-input w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none placeholder-slate-500 transition duration-150">
    </td>
    <td class="py-2.5 px-2.5">
      <select data-field="discord_user_id" data-saved-value="${escapeHtml(discordUserId)}" onchange="this.setAttribute('data-saved-value', this.value); saveCurrentRoster()" class="discord-user-select w-full bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/30 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none transition duration-150 cursor-pointer" title="Vincular a participante de Discord">
        ${discordOptionsHtml}
      </select>
    </td>
    <td class="py-2.5 px-2 text-center">
      <div class="flex items-center justify-center gap-1.5">
        <button type="button" onclick="togglePlayerAbsenceRow(this)" 
          title="${isAbsent ? '🚫 Jugador AUSENTE (Clic para marcar como Presente)' : '🟢 Jugador PRESENTE (Clic para marcar como Ausente)'}" 
          class="absence-btn inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition duration-150 active:scale-95 cursor-pointer ${isAbsent ? 'bg-slate-800/80 text-slate-400 border border-slate-700 hover:text-slate-200' : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25'}">
          <span class="w-1.5 h-1.5 rounded-full ${isAbsent ? 'bg-slate-500' : 'bg-emerald-400'}"></span>
          <span>${isAbsent ? 'Ausente' : 'Presente'}</span>
        </button>
        <button onclick="removeRosterRowEl(this)" title="Eliminar jugador" class="delete-row-btn text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 p-1 rounded-lg active:scale-90 transition duration-150 cursor-pointer">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
        </button>
      </div>
      <input type="hidden" data-field="is_absent" value="${isAbsent ? 'true' : 'false'}">
    </td>
  `;

  tbody.appendChild(tr);

  if (p.role) {
    const selectEl = tr.querySelector(".class-select");
    setSelectValueFlexible(selectEl, p.role);
  }

  const discordSelect = tr.querySelector('.discord-user-select');
  if (discordSelect) {
    discordSelect.setAttribute("data-saved-value", discordUserId);
    if (discordUserId) {
      discordSelect.value = discordUserId;
    }
  }

  return tr;
}

function renderRosterTable(roster) {
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  let dmName = "";
  let dmDiscordId = "";
  let players = [];

  if (Array.isArray(roster) && roster.length > 0) {
    if (roster[0].character_name === "(DM)" || roster[0].role === "Dungeon Master (DM)") {
      dmName = roster[0].player_name || roster[0].dm_name || roster[0].dm || "";
      dmDiscordId = roster[0].discord_user_id || roster[0].discord_id || roster[0].dm_discord_id || roster[0].dm_discord || "";
      players = roster.slice(1);
    } else {
      players = roster;
    }
  } else if (roster && typeof roster === "object" && !Array.isArray(roster)) {
    dmName = roster.dm_name || roster.dm || roster.dungeon_master || "";
    dmDiscordId = roster.dm_discord_id || roster.dm_discord || roster.dm_discord_user_id || "";
    players = roster.players || roster.roster || [];
  }

  const activeCampInput = (document.getElementById("campaignNameInput")?.value || "").trim().toLowerCase();
  if (!dmName && window.currentCampaignState && (window.currentCampaignState.campaign_name || "").toLowerCase() === activeCampInput) {
    dmName = window.currentCampaignState.dm_name || window.currentCampaignState.dm || window.currentCampaignState.dungeon_master || "";
  }
  if (!dmDiscordId && window.currentCampaignState && (window.currentCampaignState.campaign_name || "").toLowerCase() === activeCampInput) {
    dmDiscordId = window.currentCampaignState.dm_discord_id || window.currentCampaignState.dm_discord || window.currentCampaignState.dm_discord_user_id || "";
  }

  renderDMRow(dmName, dmDiscordId);

  if (Array.isArray(players)) {
    players.forEach(p => {
      if (p && p.character_name !== "(DM)" && p.role !== "Dungeon Master (DM)") {
        if (p.species) registerDynamicSpecies(p.species);
        addPlayerRow(p);
      }
    });
  }

  if (window.currentCampaignState && Array.isArray(window.currentCampaignState.universal_pcs)) {
    window.currentCampaignState.universal_pcs.forEach(upc => {
      const esp = upc.especie || upc.species;
      if (esp) registerDynamicSpecies(esp);
    });
  }

  const dmRow = tbody.querySelector("tr:first-child");
  if (dmRow) {
    const dmInput = dmRow.querySelector(".player-name") || dmRow.querySelector('[data-field="player_name"]');
    if (dmInput) {
      dmInput.value = dmName || "";
      dmInput.placeholder = "Nombre del DM...";
    }
    const dmSelect = dmRow.querySelector(".discord-user-select") || dmRow.querySelector('[data-field="discord_user_id"]');
    if (dmSelect) {
      if (dmDiscordId && dmSelect.value !== dmDiscordId) {
        dmSelect.innerHTML = buildDiscordSelectOptions(dmDiscordId, dmName);
      }
      dmSelect.value = dmDiscordId || "";
    }
  }

  renderPartyChips();
}

function renderPartyChips(rosterData = null) {
  const chipsList = document.getElementById("rosterChipsList");
  const countBadge = document.getElementById("rosterChipsCountBadge");
  if (!chipsList) return;

  let roster = rosterData;
  if (!roster) {
    roster = (typeof getRosterFromTable === "function") ? getRosterFromTable(false) : [];
  } else if (!Array.isArray(roster) && typeof roster === "object") {
    const dmName = roster.dm_name || "";
    const dmDiscord = roster.dm_discord_user_id || "";
    const players = Array.isArray(roster.players) ? roster.players : (Array.isArray(roster.roster) ? roster.roster : []);
    roster = [
      { player_name: dmName, character_name: "(DM)", role: "Dungeon Master (DM)", species: "(N/A - DM)", subclass: "N/A", is_user_character: false, discord_user_id: dmDiscord },
      ...players
    ];
  }

  roster = Array.isArray(roster) ? roster : [];
  chipsList.innerHTML = "";

  if (roster.length === 0) {
    chipsList.innerHTML = `<span class="text-xs text-slate-500 italic py-1">Sin miembros en el grupo. Agrega jugadores usando el botón &ldquo;+ Añadir&rdquo; o &ldquo;Editar Roster Completo&rdquo;.</span>`;
    if (countBadge) countBadge.textContent = "0 participantes";
    return;
  }

  if (countBadge) {
    countBadge.textContent = `${roster.length} participante${roster.length === 1 ? '' : 's'}`;
  }

  roster.forEach((member, index) => {
    if (!member || typeof member !== "object") return;
    const isDM = (index === 0) || (member.character_name === "(DM)") || (member.role === "Dungeon Master (DM)");
    const isUserChar = Boolean(member.is_user || member.is_user_character);
    const chip = document.createElement("div");
    chip.className = "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs transition-all duration-150 shadow-sm " + 
      (isDM 
        ? "bg-amber-500/10 border-amber-500/30 text-amber-200" 
        : (isUserChar 
          ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-200 ring-1 ring-indigo-400/20" 
          : "bg-slate-900/90 border-slate-700/80 text-slate-200 hover:border-slate-600"));

    const charName = member.character_name ? escapeHtml(member.character_name) : (isDM ? "(DM)" : "Sin PJ");
    const playerName = member.player_name ? escapeHtml(member.player_name) : (isDM ? "Dungeon Master" : "Jugador");
    const roleClass = member.role ? escapeHtml(member.role) : "";

    const uid = (member.discord_user_id || "").toString().trim();
    let discordLabel = "";
    if (uid) {
      if (Array.isArray(cachedDiscordParticipants) && cachedDiscordParticipants.length > 0) {
        const found = cachedDiscordParticipants.find(p => (p.user_id || "").toString() === uid);
        if (found) {
          discordLabel = `@${(found.username || found.display_name || "").replace(/^@/, '')}`;
        }
      }
      if (!discordLabel) {
        if (member.player_name && member.player_name !== "Jugador" && member.player_name !== "Dungeon Master") {
          discordLabel = `@${member.player_name.replace(/^@/, '')}`;
        } else if (/[a-zA-Z_]/.test(uid)) {
          discordLabel = `@${uid.replace(/^@/, '')}`;
        } else {
          discordLabel = `@${uid.length > 8 ? uid.slice(0, 6) + '…' : uid}`;
        }
      }
    } else if (member.player_name && member.player_name !== "Jugador" && member.player_name !== "Dungeon Master") {
      if (Array.isArray(cachedDiscordParticipants) && cachedDiscordParticipants.length > 0) {
        const found = cachedDiscordParticipants.find(p => 
          (p.username && p.username.toLowerCase() === member.player_name.toLowerCase()) || 
          (p.display_name && p.display_name.toLowerCase() === member.player_name.toLowerCase())
        );
        if (found) {
          discordLabel = `@${(found.username || found.display_name).replace(/^@/, '')}`;
        }
      }
    }

    const discordBtnHtml = discordLabel
      ? `<button type="button" onclick="editMemberDiscord(${index})" title="Discord vinculado: ${escapeHtml(uid || discordLabel)}. Clic para editar en la tabla" class="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-md bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/30 transition cursor-pointer active:scale-95">
          <svg class="w-3 h-3 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
          <span>${escapeHtml(discordLabel)}</span>
        </button>`
      : `<button type="button" onclick="editMemberDiscord(${index})" title="Sin Discord vinculado. Clic para vincular en la tabla" class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-slate-800/80 hover:bg-slate-700/80 text-slate-400 hover:text-sky-300 border border-slate-700/70 hover:border-sky-500/40 transition cursor-pointer active:scale-95">
          <svg class="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>
          <span>+Discord</span>
        </button>`;

    const userCharBadge = isUserChar ? `<span title="Tu personaje principal" class="text-amber-400 font-bold">⭐</span> ` : "";
    const rolePill = (!isDM && roleClass) ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">${roleClass}</span>` : "";

    if (isDM) {
      chip.innerHTML = `
        <div class="flex items-center gap-1.5">
          <span class="text-amber-400 font-bold">👑</span>
          <span class="font-semibold text-amber-200">(DM)</span>
          <span class="text-[11px] text-slate-300 font-normal">(${playerName})</span>
          ${discordBtnHtml}
        </div>
      `;
    } else {
      chip.innerHTML = `
        <div class="flex items-center gap-1.5">
          ${userCharBadge}
          <span class="font-semibold text-slate-100">${charName}</span>
          <span class="text-[11px] text-slate-400 font-normal">(${playerName})</span>
          ${rolePill}
          ${discordBtnHtml}
        </div>
        <button type="button" onclick="removeRosterRow(${index})" title="Eliminar participante del grupo"
          class="w-4 h-4 rounded hover:bg-rose-500/20 hover:text-rose-400 text-slate-400 flex items-center justify-center transition active:scale-90 ml-0.5 text-xs font-bold leading-none cursor-pointer">
          &times;
        </button>
      `;
    }
    chipsList.appendChild(chip);
  });
}

const renderRosterChips = renderPartyChips;

function gatherRosterData() {
  const tbody = document.getElementById("rosterTableBody");
  let dmRow = tbody ? tbody.querySelector("tr:first-child") : null;
  if (!dmRow) {
    dmRow = renderDMRow("", "");
  }

  const dmNameInput = dmRow ? (dmRow.querySelector('.player-name') || dmRow.querySelector('[data-field="player_name"]')) : null;
  const dmDiscordSelect = dmRow ? (dmRow.querySelector('.discord-user-select') || dmRow.querySelector('[data-field="discord_user_id"]')) : null;

  const dmName = dmNameInput ? dmNameInput.value.trim() : '';
  const dmDiscordId = dmDiscordSelect ? dmDiscordSelect.value.trim() : '';

  const dmItem = {
    player_name: dmName,
    character_name: "(DM)",
    species: "(N/A - DM)",
    role: "Dungeon Master (DM)",
    subclass: "N/A",
    discord_user_id: dmDiscordId,
    discord_id: dmDiscordId,
    is_user: false,
    is_user_character: false
  };

  const playerRows = tbody ? Array.from(tbody.querySelectorAll("tr")).slice(1) : [];
  const players = [];
  playerRows.forEach(row => {
    const pInput = row.querySelector('.player-name') || row.querySelector('[data-field="player_name"]');
    const cInput = row.querySelector('.char-name') || row.querySelector('[data-field="character_name"]');
    const sInput = row.querySelector('.species-select') || row.querySelector('[data-field="species"]');
    const rSelect = row.querySelector('.class-select') || row.querySelector('[data-field="role"]');
    const scInput = row.querySelector('.subclass-input') || row.querySelector('[data-field="subclass"]');
    const dSelect = row.querySelector('.discord-user-select') || row.querySelector('[data-field="discord_user_id"]');
    const isUserCharInput = row.querySelector('[data-field="is_user_character"]');
    const isUser = row.dataset.isUser === 'true' || (isUserCharInput && isUserCharInput.value === 'true');

    const playerName = pInput ? pInput.value.trim() : '';
    const charName = cInput ? cInput.value.trim() : '';
    const species = sInput ? sInput.value.trim() : '';
    const role = rSelect ? rSelect.value : '';
    const subclass = scInput ? scInput.value.trim() : '';
    const discordUserId = dSelect ? dSelect.value.trim() : '';

    if (playerName || charName) {
      players.push({
        player_name: playerName,
        character_name: charName,
        species: species,
        role: role,
        subclass: subclass,
        discord_user_id: discordUserId,
        discord_id: discordUserId,
        is_user: isUser,
        is_user_character: isUser
      });
    }
  });

  const gatheredRosterArray = [dmItem, ...players];
  const currentCampaignName = getSelectedCampaignName();

  const payload = {
    campaign_name: currentCampaignName,
    dm_name: dmName,
    dm: dmName,
    dungeon_master: dmName,
    dm_discord_id: dmDiscordId,
    dm_discord: dmDiscordId,
    dm_discord_user_id: dmDiscordId,
    roster: gatheredRosterArray
  };

  return {
    dmName,
    dmDiscordId,
    dmNameInput,
    dmDiscordSelect,
    players,
    gatheredRosterArray,
    payload
  };
}

function saveRoster() {
  const data = gatherRosterData();
  localStorage.setItem('dnd_roster_data', JSON.stringify({
    players: data.players,
    roster: data.gatheredRosterArray.filter(m => m.character_name !== "(DM)" && m.role !== "Dungeon Master (DM)")
  }));
  return data;
}

function scheduleRosterBackendSync() {
  const campName = getSelectedCampaignName();
  if (!campName) return;
  clearTimeout(_rosterDebounceTimer);
  _rosterDebounceTimer = setTimeout(async () => {
    const data = gatherRosterData();
    try {
      await fetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data.payload)
      });
      if (typeof notifyDriveSaveEvent === "function") notifyDriveSaveEvent();
    } catch (err) {
      console.warn("Debounced roster backend sync error:", err);
    }
  }, 1200);
}

async function saveCurrentRoster(showBadge = false, syncBackend = false) {
  const data = saveRoster();
  const campName = getSelectedCampaignName();
  const storageKey = getCampaignRosterKey(campName);
  if (storageKey) {
    localStorage.setItem(storageKey, JSON.stringify(data.gatheredRosterArray));
  }
  renderRosterChips(data.gatheredRosterArray);

  if (syncBackend && campName) {
    clearTimeout(_rosterDebounceTimer);
    try {
      const res = await fetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data.payload)
      });
      if (res.ok) {
        const savedState = await res.json();
        window.currentCampaignState = savedState.campaign_state || savedState;
        if (typeof notifyDriveSaveEvent === "function") notifyDriveSaveEvent();
      }
    } catch (err) {
      console.warn("Error auto-saving campaign roster to backend:", err);
    }
  } else if (!syncBackend && campName) {
    scheduleRosterBackendSync();
  }

  if (showBadge) {
    const badge = document.getElementById("saveStatusBadge");
    if (badge) {
      badge.classList.remove("hidden");
      setTimeout(() => badge.classList.add("hidden"), 2500);
    }
  }
}

async function manualSaveRoster() {
  await saveCurrentRoster(true, true);
}

async function loadCampaignRoster(campaignName) {
  const campName = (campaignName !== undefined ? campaignName : (document.getElementById("campaignNameInput")?.value || "")).trim();
  if (!campName) {
    renderRosterTable([]);
    renderPartyChips([]);
    return [];
  }

  let dmName = "";
  let dmDiscordId = "";
  let players = [];
  let loaded = false;
  let rawMembers = null;

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}`);
    if (res.ok) {
      const data = await res.json();
      const state = data.campaign_state || data;
      if (state) {
        dmName = state.dm_name || state.dm || state.dungeon_master || "";
        dmDiscordId = state.dm_discord_id || state.dm_discord || state.dm_discord_user_id || "";
        const backendMembers = (state.roster || state.participants || state.party || state.players) || null;
        if (Array.isArray(backendMembers) && backendMembers.length > 0) {
          rawMembers = backendMembers;
          loaded = true;
        } else if (dmName || dmDiscordId) {
          loaded = true;
        }
      }
    }
  } catch (err) {
    console.warn("loadCampaignRoster backend fetch error:", err);
  }

  if (!loaded) {
    const storageKey = getCampaignRosterKey(campName);
    const stored = storageKey ? localStorage.getItem(storageKey) : null;
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          rawMembers = parsed;
          loaded = true;
        } else if (parsed && typeof parsed === "object") {
          const arr = parsed.roster || parsed.participants || parsed.party || parsed.players;
          if (Array.isArray(arr) && arr.length > 0) {
            rawMembers = arr;
            loaded = true;
          } else if (parsed.players && Array.isArray(parsed.players)) {
            dmName = parsed.dm_name || "";
            dmDiscordId = parsed.dm_discord_id || parsed.dm_discord_user_id || parsed.dm_discord || "";
            players = parsed.players;
            loaded = true;
          }
        }
      } catch (e) {
        console.warn("Error reading campaign roster from localStorage:", e);
      }
    }
  }

  if (!loaded) {
    rawMembers = [];
    dmName = "";
    dmDiscordId = "";
  }

  let fullRoster = [];
  if (rawMembers && Array.isArray(rawMembers)) {
    if (rawMembers.length > 0 && (rawMembers[0].character_name === "(DM)" || rawMembers[0].role === "Dungeon Master (DM)")) {
      if (!dmName && rawMembers[0].player_name) dmName = rawMembers[0].player_name;
      if (!dmDiscordId) dmDiscordId = rawMembers[0].discord_user_id || rawMembers[0].discord_id || rawMembers[0].dm_discord_id || "";
      players = rawMembers.slice(1);
    } else {
      players = rawMembers;
    }
  }
  fullRoster = [
    {
      player_name: dmName,
      character_name: "(DM)",
      species: "(N/A - DM)",
      role: "Dungeon Master (DM)",
      subclass: "N/A",
      is_user_character: false,
      discord_user_id: dmDiscordId,
      discord_id: dmDiscordId
    },
    ...players
  ];

  renderRosterTable(fullRoster);
  renderPartyChips(fullRoster);

  return fullRoster;
}

function loadRoster(campaignName) {
  return loadCampaignRoster(campaignName);
}

function toggleUserCharacterRow(btn) {
  const tr = btn.closest("tr");
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;
  const allRows = Array.from(tbody.querySelectorAll("tr"));
  const index = allRows.indexOf(tr);
  if (index <= 0) return;
  toggleUserCharacter(index);
}

async function toggleUserCharacter(index) {
  if (index === 0) return;
  const current = getRosterFromTable(false);
  const wasUserChar = Boolean(current[index] && (current[index].is_user || current[index].is_user_character));
  current.forEach((m, idx) => {
    const isThis = (!wasUserChar && idx === index);
    m.is_user = isThis;
    m.is_user_character = isThis;
  });
  renderRosterTable(current);
  await saveCurrentRoster(true, true);
}

function togglePlayerAbsenceRow(btn) {
  const tr = btn.closest("tr");
  if (!tr) return;
  const wasAbsent = tr.dataset.isAbsent === "true";
  const isAbsent = !wasAbsent;
  tr.dataset.isAbsent = isAbsent ? "true" : "false";

  const absentInput = tr.querySelector('[data-field="is_absent"]');
  if (absentInput) {
    absentInput.value = isAbsent ? "true" : "false";
  }

  if (isAbsent) {
    tr.classList.add("opacity-50", "bg-amber-950/20");
    btn.className = "absence-btn inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition duration-150 active:scale-95 cursor-pointer bg-slate-800/80 text-slate-400 border border-slate-700 hover:text-slate-200";
    btn.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span><span>Ausente</span>`;
    btn.title = "🚫 Jugador AUSENTE (Clic para marcar como Presente)";
  } else {
    tr.classList.remove("opacity-50", "bg-amber-950/20");
    btn.className = "absence-btn inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition duration-150 active:scale-95 cursor-pointer bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25";
    btn.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>Presente</span>`;
    btn.title = "🟢 Jugador PRESENTE (Clic para marcar como Ausente)";
  }
}

function addRosterRow() {
  const tr = addPlayerRow();
  saveCurrentRoster();
  if (tr) {
    const playerInput = tr.querySelector(".player-name");
    if (playerInput) playerInput.focus();
  }
}

function removeRosterRowEl(btn) {
  const tr = btn.closest("tr");
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;
  const allRows = Array.from(tbody.querySelectorAll("tr"));
  const index = allRows.indexOf(tr);
  if (index <= 0) {
    if (typeof showAlert === "function") showAlert("La fila del Dungeon Master es fija y no puede ser eliminada.");
    return;
  }
  removeRosterRow(index);
}

function removeRosterRow(index) {
  if (index === 0) {
    if (typeof showAlert === "function") showAlert("La fila del Dungeon Master es fija y no puede ser eliminada.");
    return;
  }
  const current = getRosterFromTable(false);
  current.splice(index, 1);
  renderRosterTable(current);
  saveCurrentRoster();
}

function resetRosterToDefault() {
  const campName = getSelectedCampaignName();
  const isPrivate = isPrivateCampaign(campName);
  const storageKey = getCampaignRosterKey(campName);
  const targetRoster = isPrivate ? DEFAULT_ROSTER : CLEAN_ROSTER;
  const promptMsg = isPrivate
    ? "¿Deseas reiniciar el grupo al equipo oficial de campaña?"
    : "¿Deseas reiniciar el roster de esta campaña a campos vacíos?";

  if (confirm(promptMsg)) {
    if (storageKey) localStorage.removeItem(storageKey);
    localStorage.removeItem("dnd_roster_data");
    renderRosterTable(targetRoster);
    saveCurrentRoster(true);
  }
}

function getRosterFromTable(filterEmpty = false) {
  const rows = document.querySelectorAll("#rosterTableBody tr");
  const roster = [];
  rows.forEach((tr, index) => {
    const isDM = (index === 0);
    const isUserCharInput = tr.querySelector('[data-field="is_user_character"]');
    const isUser = isDM ? false : (tr.dataset.isUser === "true" || (isUserCharInput && isUserCharInput.value === "true"));
    const isAbsentInput = tr.querySelector('[data-field="is_absent"]');
    const isAbsent = !isDM && (tr.dataset.isAbsent === "true" || (isAbsentInput && isAbsentInput.value === "true"));

    const playerInput = tr.querySelector('.player-name') || tr.querySelector('[data-field="player_name"]');
    const charInput = tr.querySelector('.char-name') || tr.querySelector('[data-field="character_name"]');
    const speciesInput = tr.querySelector('.species-select') || tr.querySelector('[data-field="species"]');
    const roleSelect = tr.querySelector('.class-select') || tr.querySelector('[data-field="role"]');
    const subclassInput = tr.querySelector('.subclass-input') || tr.querySelector('[data-field="subclass"]');
    const discordSelect = tr.querySelector('.discord-user-select') || tr.querySelector('[data-field="discord_user_id"]');

    const playerName = playerInput ? playerInput.value.trim() : "";
    const charName = isDM ? "(DM)" : (charInput ? charInput.value.trim() : "");
    const speciesVal = isDM ? "(N/A - DM)" : (speciesInput ? speciesInput.value.trim() : "");
    const roleVal = isDM ? "Dungeon Master (DM)" : (roleSelect ? roleSelect.value : "");
    const subclassVal = isDM ? "N/A" : (subclassInput ? subclassInput.value.trim() : "");
    const discordVal = discordSelect ? discordSelect.value.trim() : "";

    if (!isDM && filterEmpty) {
      const hasPlayer = Boolean(playerName);
      const hasChar = Boolean(charName && charName !== "(DM)" && charName !== "-");
      if (!hasPlayer && !hasChar) {
        return;
      }
    }

    roster.push({
      player_name: playerName,
      character_name: charName,
      species: speciesVal,
      role: roleVal,
      subclass: subclassVal,
      discord_user_id: discordVal,
      is_user: isUser,
      is_user_character: isUser,
      is_absent: isAbsent
    });
  });

  if (filterEmpty && roster.length === 1 && roster[0].character_name === "(DM)" && !roster[0].player_name) {
    return [];
  }

  return roster;
}

function toggleFullRosterTable(forceShow = null) {
  const card = document.getElementById("rosterFullCard");
  const btnText = document.getElementById("btnToggleFullRosterText");
  if (!card) return;
  const shouldShow = forceShow !== null ? Boolean(forceShow) : card.classList.contains("hidden");
  if (shouldShow) {
    card.classList.remove("hidden");
    if (btnText) btnText.textContent = "Ocultar Roster Completo";
    const rows = document.querySelectorAll("#rosterTableBody tr");
    if (rows.length === 0) {
      const campName = (document.getElementById("campaignNameInput")?.value || "").trim();
      if (campName) {
        loadCampaignRoster(campName);
      }
    }
  } else {
    card.classList.add("hidden");
    if (btnText) btnText.textContent = "Editar Roster Completo";
  }
}

function editMemberDiscord(index) {
  toggleFullRosterTable(true);
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;
  const rows = tbody.querySelectorAll("tr");
  const row = rows[index];
  if (row) {
    const discordSelect = row.querySelector(".discord-user-select");
    if (discordSelect) {
      discordSelect.focus();
      discordSelect.classList.add("ring-2", "ring-sky-400");
      setTimeout(() => discordSelect.classList.remove("ring-2", "ring-sky-400"), 2000);
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function quickAddPartyMemberPrompt() {
  const card = document.getElementById("rosterFullCard");
  const btnText = document.getElementById("btnToggleFullRosterText");
  if (card && card.classList.contains("hidden")) {
    card.classList.remove("hidden");
    if (btnText) btnText.textContent = "Ocultar Roster Completo";
  }
  addRosterRow();
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
  requestAnimationFrame(() => {
    modal.classList.remove("opacity-0");
    box.classList.remove("scale-95");
    box.classList.add("scale-100");
  });
}

function closeDiscordBridgeModal() {
  const modal = document.getElementById("discordBridgeModal");
  const box = document.getElementById("discordBridgeModalBox");
  if (!modal || !box) return;
  modal.classList.add("opacity-0");
  box.classList.remove("scale-100");
  box.classList.add("scale-95");
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 150);
}

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

// Window bindings
window.CLASS_OPTIONS = CLASS_OPTIONS;
window.DEFAULT_ROSTER = DEFAULT_ROSTER;
window.CLEAN_ROSTER = CLEAN_ROSTER;
window.registerDynamicSpecies = registerDynamicSpecies;
window.initCustomSpeciesList = initCustomSpeciesList;
window.renderDMRow = renderDMRow;
window.addPlayerRow = addPlayerRow;
window.renderRosterTable = renderRosterTable;
window.renderPartyChips = renderPartyChips;
window.renderRosterChips = renderRosterChips;
window.gatherRosterData = gatherRosterData;
window.saveRoster = saveRoster;
window.saveCurrentRoster = saveCurrentRoster;
window.manualSaveRoster = manualSaveRoster;
window.loadCampaignRoster = loadCampaignRoster;
window.loadRoster = loadRoster;
window.toggleUserCharacterRow = toggleUserCharacterRow;
window.toggleUserCharacter = toggleUserCharacter;
window.togglePlayerAbsenceRow = togglePlayerAbsenceRow;
window.addRosterRow = addRosterRow;
window.removeRosterRowEl = removeRosterRowEl;
window.removeRosterRow = removeRosterRow;
window.resetRosterToDefault = resetRosterToDefault;
window.getRosterFromTable = getRosterFromTable;
window.toggleFullRosterTable = toggleFullRosterTable;
window.editMemberDiscord = editMemberDiscord;
window.quickAddPartyMemberPrompt = quickAddPartyMemberPrompt;
window.refreshDiscordParticipants = refreshDiscordParticipants;
window.resetDiscordAuth = resetDiscordAuth;
window.openDiscordBridgeModal = openDiscordBridgeModal;
window.closeDiscordBridgeModal = closeDiscordBridgeModal;
window.copyBridgeCmd = copyBridgeCmd;
