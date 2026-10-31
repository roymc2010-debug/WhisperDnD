/* Desktop presentation. Recording, storage and provider handlers stay in their modules. */
(() => {
 'use strict';
 const core=window.WhisperDesktopCore, $=id=>document.getElementById(id);
 const svg=(path)=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+path+'</svg>';
 const icons={audio:svg('<path d="M12 3v18M7 7v10M17 6v12M3 10v4M21 9v6"/>'),process:svg('<path d="M4 7h16M4 12h16M4 17h10"/><circle cx="18" cy="17" r="2"/>'),chronicle:svg('<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4zM13 7a3 3 0 0 1 3-3h4v14h-3a4 4 0 0 0-4 3"/>'),appearance:svg('<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 3v18"/>'),repeat:svg('<path d="m4 8 3-3-3-3M4 5h11a6 6 0 0 1 0 12H7"/>'),chevron:svg('<path d="m9 5 7 7-7 7"/>')};
 const text=(el,value)=>{if(el&&el.textContent!==value)el.textContent=value;};
 const setHidden=(el,hidden)=>{if(el&&el.classList.contains('hidden')!==hidden)el.classList.toggle('hidden',hidden);};
 const visible=el=>el&&!el.classList.contains('hidden')&&getComputedStyle(el).display!=='none';
 function section(id,title,description){
  const el=document.createElement('section');el.id=id;el.className='desktop-view hidden';
  el.innerHTML='<div class="desktop-page-heading"><h2>'+title+'</h2><p>'+description+'</p></div>';
  $('viewIngest').before(el);return el;
 }
 const sourceToolbar=$('tabLiveBtn')?.closest('nav')?.parentElement;
 if(sourceToolbar){sourceToolbar.id='desktopSourceToolbar';sourceToolbar.parentElement.id='desktopRecorderPanel';}
 const heading=document.createElement('div');heading.className='desktop-page-heading';
 heading.innerHTML='<h2 id="desktopPageTitle">Sesión y grabación</h2><p id="desktopPageDescription">Prepara la campaña, reúne a tu party y conserva la sesión.</p>';
 $('viewIngest').prepend(heading);
 const audio=section('viewAudio','Audio y dispositivos','Elige tus canales y calibra los niveles antes de grabar.');
 const audioDetails=$('audioDeviceSection');
 if(audioDetails){audio.append(audioDetails);audioDetails.open=true;}
 if($('vuMeterContainer'))audio.append($('vuMeterContainer'));
 text($('campaignHeaderCard')?.querySelector('h2'),'Campaña activa');
 text($('campaignHeaderCard')?.querySelector('p'),'El contexto y la party se guardan por campaña.');
 const processView=section('viewProcess','Proceso','Sigue la transcripción, el análisis y las revisiones pendientes.');
 processView.insertAdjacentHTML('beforeend','<div id="desktopProcessEmpty" class="desktop-empty">No hay un proceso activo. Inicia una grabación o importa un audio desde Sesión y grabación.</div>');
 for(const id of ['processingCard','npcSpellcheckCard'])if($(id))processView.append($(id));
 // Errors remain global overlays, visible from every page.
 if($('errorCard'))document.body.append($('errorCard'));
 const chronicle=section('viewChronicle','Resultado de la sesión','Consulta, revisa y exporta el último documento generado.');
 chronicle.insertAdjacentHTML('beforeend','<div id="desktopResultEmpty" class="desktop-empty">Aquí aparecerá el resultado de tu próxima grabación. Los documentos guardados siguen disponibles en la Wiki o en Apuntes.</div>');
 if($('resultsCard'))chronicle.append($('resultsCard'));
 const appearance=section('viewAppearance','Apariencia','Un mismo espacio, seis formas de verlo. El tema se conserva al cambiar de modo.');
 appearance.insertAdjacentHTML('beforeend','<div id="desktopThemeGrid" class="desktop-theme-grid" role="group" aria-label="Elegir tema"></div><p id="desktopThemeStatus" class="desktop-status" role="status"></p><div class="desktop-appearance-note"><h3>Colores de las clases</h3><p>Los logos conservan su color original en todos los temas, sin fondos ni contornos añadidos.</p></div>');
 for(const theme of core.themes){
  const button=document.createElement('button');button.type='button';button.className='desktop-theme-option';button.dataset.themeOption=theme.id;
  button.innerHTML='<span class="desktop-theme-preview" aria-hidden="true" style="--preview-canvas:'+theme.canvas+';--preview-surface:'+theme.surface+';--preview-raised:'+theme.raised+';--preview-accent:'+theme.accent+'"><i></i><span><b></b><em></em><small></small></span></span><span class="desktop-theme-name">'+theme.name+'<span class="desktop-theme-check" aria-hidden="true"><span data-ui-icon=check aria-hidden=true></span></span></span><span class="desktop-theme-kind">'+(theme.mode==='light'?'Claro':'Oscuro')+'</span>';
  button.addEventListener('click',()=>applyTheme(theme.id,true));$('desktopThemeGrid').append(button);
 }
 function applyTheme(value,persist=false){
  const id=core.normalizeTheme(value),theme=core.themes.find(t=>t.id===id);
  document.documentElement.dataset.theme=id;document.documentElement.classList.toggle('dark',theme.mode==='dark');
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme.canvas);
  for(const b of document.querySelectorAll('[data-theme-option]'))b.setAttribute('aria-pressed',String(b.dataset.themeOption===id));
  text($('desktopThemeStatus'),'Tema actual: '+theme.name+'.');
  if(persist){try{localStorage.setItem('whisper_desktop_theme',id);}catch{ text($('desktopThemeStatus'),'Tema aplicado. El navegador no permitió guardar esta preferencia.');}}
 }
 applyTheme(document.documentElement.dataset.theme);
 const nav=$('navBtnIngest').parentElement;
 for(const [key,label] of [['audio','Audio y dispositivos'],['process','Proceso'],['chronicle','Resultado']]){
  const b=document.createElement('button');b.type='button';b.className='desktop-nav';b.dataset.desktopView=key;
  b.innerHTML=icons[key]+'<span>'+label+'</span>';b.addEventListener('click',()=>setActiveView(key));
  if(key==='audio')$('navBtnIngest').after(b);else nav.append(b);
 }
 const appearanceButton=document.createElement('button');appearanceButton.type='button';appearanceButton.className='desktop-nav';appearanceButton.dataset.desktopView='appearance';appearanceButton.innerHTML=icons.appearance+'<span>Apariencia</span>';
 appearanceButton.addEventListener('click',()=>setActiveView('appearance'));$('btnSettingsSidebar').parentElement.before(appearanceButton);
 // Mobile has the same reachable pages without adding more bottom-navigation tabs.
 const shortcuts=document.createElement('div');shortcuts.className='desktop-mobile-shortcuts';
 for(const [key,label] of [['audio','Audio'],['process','Proceso'],['chronicle','Resultado'],['appearance','Apariencia']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',()=>setActiveView(key));shortcuts.append(b);}
 $('viewIngest').insertBefore(shortcuts,heading.nextSibling);
 const roster=$('rosterFullCard');
 if(roster){
  const details=document.createElement('details');details.id='desktopParty';details.className='desktop-party';details.open=true;
  details.innerHTML='<summary><span class="desktop-party-label">Party <span id="desktopPartyCount"></span></span><span class="desktop-disclosure-icon">'+icons.chevron+'</span></summary>';
  $('campaignHeaderCard').after(details);details.append(roster);
  text(roster.querySelector('h3 span'),'Personajes y vinculación con Discord');
 }
 // Campaign administration lives in Wiki, next to its campaign selector.
 const campaignTools=document.createElement('div');campaignTools.className='desktop-library-actions';
 for(const id of ['btnMyCampaigns','btnImportCampaign','campaignImportFileInput'])if($(id))campaignTools.append($(id));
 $('viewWiki').prepend(campaignTools);
 // Keep source behavior intact; the recorder offers an explicit route to calibration.
 const audioLink=document.createElement('button');audioLink.type='button';audioLink.className='desktop-audio-link';audioLink.innerHTML=icons.audio+'<span>Revisar audio y dispositivos</span>';audioLink.addEventListener('click',()=>setActiveView('audio'));
 $('recordingStationCard')?.append(audioLink);
 for(const el of document.querySelectorAll('[onclick*="openTunnelModal"],[onclick*="toggleTunnelModal"]')){el.hidden=true;el.setAttribute('data-retired-tunnel','');}
 const override=$('overrideSessionNumberCheck');
 $('campaignNameInput')?.addEventListener('input',()=>{if(override)override.checked=false;});
 if(override){
  override.parentElement.hidden=true;
  const repeat=document.createElement('button');repeat.id='desktopRerecord';repeat.type='button';repeat.dataset.buttonRole='review';repeat.innerHTML=icons.repeat+'<span>Regrabar</span>';repeat.addEventListener('click',openRerecord);
  $('sessionNumberInput').closest('.relative').parentElement.after(repeat);
 }
 const notice=document.createElement('div');notice.id='desktopRerecordNotice';notice.className='desktop-rerecord-notice hidden';notice.setAttribute('role','status');notice.innerHTML='<span id="desktopRerecordNoticeText"></span><button type="button" id="desktopCancelRerecord">Cancelar reemplazo</button>';
 $('priorLoreDetails')?.before(notice);
 $('desktopCancelRerecord')?.addEventListener('click',()=>{override.checked=false;toggleSessionOverride();syncDesktopNavigation();});
 const dialog=document.createElement('dialog');dialog.id='desktopRerecordDialog';dialog.setAttribute('aria-labelledby','desktopRerecordTitle');
 dialog.innerHTML='<form method="dialog"><h2 id="desktopRerecordTitle">Regrabar una sesión</h2><p>Elige la sesión que quieres reemplazar. Al procesar el audio se utilizará el flujo de reemplazo existente de la campaña.</p><label for="desktopRerecordSession">Sesión guardada</label><select id="desktopRerecordSession" required></select><p class="desktop-review-copy">Se reemplazará el contenido de esa sesión. Esta selección todavía no modifica sus archivos.</p><p id="desktopRerecordError" role="alert"></p><div class="desktop-dialog-actions"><button value="cancel">Cancelar</button><button type="button" id="desktopConfirmRerecord" data-button-role="review">Preparar regrabación</button></div></form>';
 document.body.append(dialog);
 let chosenCampaign='';
 const recording=()=>Boolean(window.isRecording||window.isSessionRecording||window.serverRecordingActive||($('btnStartRecording')?.disabled&&!$('btnStopRecording')?.disabled));
 function openRerecord(){
  chosenCampaign=($('campaignNameInput')?.value||'').trim();
  const sessions=core.sessionNumbers(window.currentCampaignState);
  const error=core.validateRerecord({campaign:chosenCampaign,selectedCampaign:chosenCampaign,sessions,session:sessions[0],recording:recording()});
  if(error){if(typeof showFloatingToast==='function')showFloatingToast(error,'info');return;}
  const select=$('desktopRerecordSession');select.replaceChildren();
  for(const n of sessions){const o=document.createElement('option');o.value=String(n);o.textContent='Sesión '+n;select.append(o);}
  text($('desktopRerecordError'),'');dialog.showModal();
 }
 $('desktopConfirmRerecord').addEventListener('click',()=>{
  const session=Number($('desktopRerecordSession').value);
  const error=core.validateRerecord({campaign:chosenCampaign,selectedCampaign:($('campaignNameInput')?.value||'').trim(),sessions:core.sessionNumbers(window.currentCampaignState),session,recording:recording()});
  if(error){text($('desktopRerecordError'),error);return;}
  override.checked=true;toggleSessionOverride();$('sessionNumberInput').value=String(session);dialog.close();syncDesktopNavigation();
 });
 const roleFor=button=>{
  if(button.closest('#roster-table')||button.closest('nav')||button.closest('#desktopThemeGrid')||button.dataset.desktopView)return null;
  const action=(button.getAttribute('onclick')||'')+' '+button.id;
  if(/toggleQuestStatus|toggleWikiQuestStatus|^(select|applySpecies|applySubclass|setNpcCategory|setNotesCategory|setWikiCategory|setLiveMode|setTargetLanguage|setWorkspace|setWorkStudySubMode|switchClassModalTab|switchNoteDetailTab|switchWikiSessionSubtab|switchSummaryLanguage|toggleResultTab|selectCampaignFromManager)/.test(action.trim()))return null;
  if(/btnStartRecording|btnUploadFile|btnProcessYoutube|btnFile|btnYoutube/.test(action))return 'primary';
  if(/delete|remove|clearBackup|clearAll|clearUserApiKeys|disconnect|logout|resetDiscordAuth|btnStopRecording|stopSessionAndProcess|cancelCurrentTask/i.test(action))return 'danger';
  if(/reprocess|regenerate|retry|deduplicate|merge|translate|Reprocess/i.test(action))return 'review';
  if(/download|export|import|sync|refresh|copy|Drive|print/i.test(action))return 'transfer';
  if(/save|create|addRoster|addPlayer|addGlossary|addNew|manualSave|submitEditNpc|toggleNewCharacterMode|enableMulticlass/i.test(action))return 'save';
  return 'neutral';
 };
 function enhanceButtons(){
  WhisperIcons.mount(document);
  for(const b of document.querySelectorAll('button')){
   if(!b.hasAttribute('data-button-role')){const role=roleFor(b);if(role)b.dataset.buttonRole=role;}
   const iconOnly=!b.textContent.trim()&&Boolean(b.querySelector('svg'));
   b.classList.toggle('desktop-icon-button',iconOnly);
   if(iconOnly&&!b.getAttribute('aria-label')){
    const action=b.getAttribute('onclick')||'';
    const label=b.title||(/close|hide|Modal\(false\)/i.test(action)?'Cerrar diálogo':'');
    if(label)b.setAttribute('aria-label',label);
   }
  }
  for(const b of document.querySelectorAll('#roster-table button[onclick*="toggleUserChar"]')){
   b.setAttribute('aria-label','Marcar como mi personaje');b.setAttribute('aria-pressed',String(Boolean(b.querySelector('svg[fill="currentColor"]'))));
  }
  for(const b of document.querySelectorAll('#roster-table button[onclick*="deletePlayer"]'))b.setAttribute('aria-label','Eliminar personaje de la party');
 }
 window.syncDesktopNavigation=()=>{
  const dnd=window.currentWorkspace!=='work_and_study',view=window.currentActiveView||'ingest';
  text($('desktopPageTitle'),dnd?'Sesión y grabación':'Grabación y apuntes');
  text($('desktopPageDescription'),dnd?'Prepara la campaña, reúne a tu party y conserva la sesión.':'Graba una clase o reunión y organiza sus ideas en apuntes.');
  text($('navBtnIngestText'),dnd?'Sesión y grabación':'Grabar');text($('navBtnWikiText'),'Wiki y campañas');text($('navBtnHistoryText'),'Apuntes');
  text($('brandSubtitle'),dnd?'Tu mesa, sesión a sesión':'Work & Study');
  for(const [id,key] of [['navBtnIngest','ingest'],['navBtnWiki','wiki'],['navBtnCharacter','character'],['navBtnHistory','history'],['btnSettingsSidebar','settings'],['mobileNavBtnIngest','ingest'],['mobileNavBtnWiki','wiki'],['mobileNavBtnCharacter','character'],['mobileNavBtnHistory','history']]){
   const b=$(id);if(b){if(key===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
  }
  for(const b of document.querySelectorAll('[data-desktop-view]')){if(b.dataset.desktopView===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
  for(const [id,on]of [['switchWorkspaceDnd',dnd],['switchWorkspaceWork',!dnd],['mobileSwitchDnd',dnd],['mobileSwitchWork',!dnd]])$(id)?.setAttribute('aria-pressed',String(on));
  for(const [id,key]of [['tabLiveBtn','live'],['tabYoutubeBtn','youtube'],['tabFileBtn','file']])$(id)?.setAttribute('aria-pressed',String(window.currentActiveMainTab===key));
  const rows=$('rosterTableBody')?.querySelectorAll('tr').length||0;text($('desktopPartyCount'),rows?'· '+rows+' integrantes':'');
  const rerecord=$('desktopRerecord');if(rerecord){const disabled=!core.sessionNumbers(window.currentCampaignState).length||recording();if(rerecord.disabled!==disabled)rerecord.disabled=disabled;}
  const replacing=Boolean(override?.checked);setHidden(notice,!replacing);if(replacing)text($('desktopRerecordNoticeText'),'Reemplazo preparado · Sesión '+$('sessionNumberInput').value+'. Se aplicará al procesar el nuevo audio.');
  setHidden($('desktopProcessEmpty'),visible($('processingCard'))||visible($('npcSpellcheckCard')));setHidden($('desktopResultEmpty'),visible($('resultsCard')));
  for(const [selector,value] of [['#resultsCard [onclick*="toggleResultTab"]',window.currentActiveResultTab],['#viewWiki [onclick*="setWikiCategory"]',window.activeWikiCategory],['#viewWiki [onclick*="switchWikiSessionSubtab"]',window.currentWikiSessionSubtab]]){
   for(const b of document.querySelectorAll(selector)){const match=b.getAttribute('onclick')?.match(/\('([^']+)'/);b.setAttribute('aria-pressed',String(Boolean(match&&match[1]===value)));}
  }
  enhanceButtons();syncModals();
 };
 // Existing custom pickers get keyboard focus containment and return focus to their opener.
 const modalIds=['campaignManagerModal','mergeEntityModal','editNpcModal','speciesModal','classModal','backupFallbackModal','modalAddGlossaryTerm','errorCard'];
 const modalState=new Map();let latestOpener=null,scheduled=false;
 const focusable=root=>[...root.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled):not([type="hidden"]),select:not(:disabled),textarea:not(:disabled),summary,[tabindex="0"]')].filter(el=>el.getClientRects().length);
 function syncModals(){
  for(const id of modalIds){const m=$(id);if(!m)continue;const open=visible(m);
   if(open&&!modalState.has(id)){m.setAttribute('role','dialog');m.setAttribute('aria-modal','true');m.tabIndex=-1;const h=m.querySelector('h2,h3');if(h){h.id||=id+'Title';m.setAttribute('aria-labelledby',h.id);}modalState.set(id,{opener:latestOpener||document.activeElement});requestAnimationFrame(()=>{if(visible(m))(focusable(m)[0]||m).focus({preventScroll:true});});}
   else if(!open&&modalState.has(id)){const opener=modalState.get(id).opener;modalState.delete(id);if(opener?.isConnected&&opener.getClientRects().length)opener.focus({preventScroll:true});}
  }
 }
 function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;syncDesktopNavigation();});}
 document.addEventListener('pointerdown',e=>{latestOpener=e.target.closest('button,summary')||latestOpener;},true);
 document.addEventListener('keydown',e=>{
  if(e.key==='Enter'||e.key===' ')latestOpener=document.activeElement;
  const open=modalIds.map($).filter(visible).at(-1);if(!open||dialog.open)return;
  if(e.key==='Escape'){const close=open.querySelector('button[onclick*="false"],button[onclick*="close"],button[onclick*="Close"]');if(close){e.preventDefault();e.stopImmediatePropagation();close.click();}}
  if(e.key==='Tab'){const f=focusable(open),i=f.indexOf(document.activeElement);if(!f.length){e.preventDefault();open.focus();}else if(e.shiftKey&&i<=0){e.preventDefault();f.at(-1).focus();}else if(!e.shiftKey&&(i===f.length-1||i<0)){e.preventDefault();f[0].focus();}}
 },true);
 document.addEventListener('DOMContentLoaded',()=>{
  const original=window.switchMainTab;if(typeof original==='function')window.switchMainTab=function(...args){const result=original.apply(this,args);schedule();return result;};
  new MutationObserver(schedule).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class','disabled']});syncDesktopNavigation();
 });
})();
