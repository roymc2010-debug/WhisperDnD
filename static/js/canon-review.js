/* Approval uses saved drafts. Generation recovery requires an explicit action. */
let activeCanonReview = null;
function reviewEscape(value) { return String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function reviewRecord(record) {
  if(!record)return '<p>Ficha nueva.</p>';
  const labels={name:'Nombre',title:'Título',holder:'Portador o custodio',status:'Estado',role:'Rol',category:'Categoría',tipo:'Tipo',type:'Tipo',context:'Contexto',description:'Descripción',notes:'Notas',aliases:'Variantes',nicknames:'Apodos confirmados',subobjectives:'Objetivos',associated_characters:'Personajes vinculados',personaje:'Personaje',jugador:'Jugador',rol_en_sesion:'Acciones atribuidas',hitos_acumulados:'Hitos'};
  return '<dl>'+Object.entries(record).filter(([key])=>labels[key]).map(([key,value])=>'<dt><strong>'+labels[key]+'</strong></dt><dd>'+ (Array.isArray(value)?value.map(item=>'<p>'+reviewEscape(typeof item==='object'?(item.completed?'Completado: ':'Pendiente: ')+(item.text||item.note||''):item)+'</p>').join(''):reviewEscape(value))+'</dd>').join('')+'</dl>';
}
async function reviewFetch(url, options) {
  const response=await fetch(url,options); const data=await response.json();
  if(!response.ok) throw new Error(data.detail || 'No se pudo completar la revisión. Vuelve a intentarlo.');
  return data;
}
async function showPendingCanonReviews() {
  try {
    const reviews=await reviewFetch('/api/session-reviews');
    document.getElementById('reviewList').innerHTML='<h2>Revisiones pendientes</h2>'+ (reviews.length ? reviews.map(d=>'<p><button type="button" data-open-review="'+reviewEscape(d.id)+'">'+reviewEscape(d.campaign_name)+' · Sesión '+reviewEscape(d.session_number)+' · '+reviewEscape(d.title)+'</button></p>').join('') : '<p>No hay revisiones pendientes.</p>');
    document.querySelectorAll('[data-open-review]').forEach(button=>button.addEventListener('click',()=>openCanonReview(button.dataset.openReview)));
  } catch(error) { document.getElementById('reviewError').textContent=error.message; }
}
async function openCanonReview(id) {
  const status=document.getElementById('reviewStatus'), errors=document.getElementById('reviewError');
  errors.textContent=''; status.textContent='Cargando borrador…';
  try {
    const d=await reviewFetch('/api/session-reviews/'+encodeURIComponent(id));activeCanonReview=d;
    const root=document.getElementById('reviewDetail');
    if(d.status==='superseded') { root.innerHTML='<p>Hay una revisión más reciente. Ábrela en la lista de pendientes.</p>';status.textContent='';return; }
    if(d.status==='applied') { root.innerHTML='<h2>Revisión ya guardada</h2><p>La sesión ya está incorporada a la campaña. Puedes verla y descargarla desde la Wiki.</p>';status.textContent='';return; }
    const metadata=d.chapter.generation_metadata || {};
    const metrics=metadata.model ? '<p class="muted" style="font-variant-numeric:tabular-nums">Modelo: '+reviewEscape(metadata.model)+(Number.isFinite(metadata.seconds)?' · Generación: '+reviewEscape(metadata.seconds)+' s':'')+' · Intentos: '+reviewEscape((metadata.attempts||[]).length)+'</p>' : '';
    const fields=[['title','Título'],['chronicle_text','Crónica'],['recap_text','Resumen factual para continuidad'],['closing_expectations','Cierre'],['next_session_script','Guion para la próxima sesión'],['user_coaching','Reflexión de rol']];
    root.innerHTML='<hr><h2>'+reviewEscape(d.campaign_name)+' · Sesión '+reviewEscape(d.session_number)+'</h2>'+metrics+'<p class="notice">'+(d.replaces_session?'Al guardar se reemplazará la sesión existente con este número. Se conservará un respaldo.':'Al guardar se creará esta sesión.')+'</p><form id="canonReviewForm">'+fields.map(([key,label])=>'<label for="review_'+key+'">'+label+'</label>'+(key==='title'?'<input type="text" id="review_title" data-review-field="title" maxlength="200" required value="'+reviewEscape(d.chapter.title||'')+'">':'<textarea id="review_'+key+'" data-review-field="'+key+'" class="'+(key==='chronicle_text'?'chronicle':'')+'">'+reviewEscape(d.chapter[key]||'')+'</textarea>')).join('')+'<details><summary>Consultar transcripción original</summary><pre>'+reviewEscape(d.transcript)+'</pre></details><h2>Propuestas para la Wiki</h2><p>Marca únicamente los cambios que hayas verificado. Las propuestas sin marcar se descartarán al guardar. Las citas localizadas permiten encontrar el pasaje; su interpretación también necesita revisión.</p>'+d.proposals.map(p=>'<details><summary>'+reviewEscape(({npcs:'PNJ',quests:'Misión',locations:'Lugar',items:'Objeto',pcs:'Personaje'})[p.collection]||p.collection)+' · '+reviewEscape(p.after.name||p.after.title||p.after.personaje||p.after.character_name||p.key)+'</summary><label class="check"><input type="checkbox" data-review-proposal value="'+reviewEscape(p.id)+'"><span>Incorporar este cambio</span></label><h3>Estado anterior</h3>'+reviewRecord(p.before)+'<h3>Propuesta</h3>'+reviewRecord(p.after)+'<p>'+reviewEscape(p.evidence.notice)+'</p><pre>'+reviewEscape(p.evidence.quotes.join('\n'))+'</pre></details>').join('')+'<label class="check"><input id="confirmCanonReview" type="checkbox" required><span>He revisado el texto y los cambios seleccionados para incorporarlos al canon.</span></label><div class="actions"><button id="applyCanonReview" type="submit">Guardar revisión en campaña</button><button id="refreshCanonReview" type="button" onclick="refreshCanonComparison()">Actualizar comparación con la campaña</button><a class="action" href="/api/session-reviews/'+encodeURIComponent(d.id)+'/download">Descargar borrador</a></div></form>';
    document.getElementById('canonReviewForm').addEventListener('submit',submitCanonReview);
    status.textContent='Borrador cargado. La campaña conserva sus datos hasta que guardes la revisión.';
  } catch(error) { errors.textContent=error.message; status.textContent='No se pudo cargar el borrador.'; }
}
async function submitCanonReview(event) {
  event.preventDefault();
  if(!activeCanonReview || !document.getElementById('confirmCanonReview').checked)return;
  const d=activeCanonReview,button=document.getElementById('applyCanonReview');
  const chapter={};document.querySelectorAll('[data-review-field]').forEach(input=>{chapter[input.dataset.reviewField]=input.value;});
  const selected=Array.from(document.querySelectorAll('[data-review-proposal]:checked')).map(input=>input.value);
  button.disabled=true;button.textContent='Guardando…';document.getElementById('reviewError').textContent='';
  try {
    const result=await reviewFetch('/api/session-reviews/'+encodeURIComponent(d.id)+'/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:d.revision,selected,chapter})});
    activeCanonReview=null;
    document.getElementById('reviewDetail').innerHTML='<h2>Revisión guardada</h2><p>La sesión y los cambios seleccionados están en la campaña. Vuelve a la Wiki y recarga la campaña para verlos.</p>';
    document.getElementById('reviewStatus').textContent=(result.processing_warnings||[]).join(' ') || 'Guardado en JSON y carpeta modular.';
    await showPendingCanonReviews();
  } catch(error) { document.getElementById('reviewError').textContent=error.message;button.disabled=false;button.textContent='Guardar revisión en campaña'; }
}
showPendingCanonReviews();
const initialReview=new URLSearchParams(location.search).get('id');
if(initialReview)openCanonReview(initialReview);

async function refreshCanonComparison() {
  if(!activeCanonReview)return;
  const chapter={};document.querySelectorAll('[data-review-field]').forEach(input=>{chapter[input.dataset.reviewField]=input.value;});
  const button=document.getElementById('refreshCanonReview');button.disabled=true;
  try {
    const d=activeCanonReview;
    const result=await reviewFetch('/api/session-reviews/'+encodeURIComponent(d.id)+'/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:d.revision,chapter})});
    await showPendingCanonReviews();await openCanonReview(result.id);
  } catch(error){document.getElementById('reviewError').textContent=error.message;button.disabled=false;}
}

async function showSavedGenerationInputs() {
  const root=document.getElementById('generationInputList');
  if(!root)return;
  try {
    const inputs=await reviewFetch('/api/generation-inputs');
    root.innerHTML='<h2>Transcripciones guardadas</h2>'+(inputs.length ? '<p>Si la generación falló, puedes continuar con el texto guardado. La campaña se actualizará únicamente después de revisar el borrador.</p>'+inputs.map(input=>{
      const action=input.response_saved?'Recuperar respuesta guardada':'Generar solo crónica';
      const explanation=input.response_saved?'La respuesta ya está guardada; recuperarla no requiere otra llamada a Gemini.':'Reutiliza la transcripción y consume cuota de Gemini. No vuelve a transcribir el audio.';
      const state=!input.can_retry?'No se ha confirmado el final del intento anterior. Espera o revisa su estado antes de repetirlo.':input.error_type==='ReadTimeout'?'En el intento anterior se agotó la espera de Gemini. La transcripción está conservada.':'';
      return '<article class="saved-input"><h3>'+reviewEscape(input.campaign_name)+' · Sesión '+reviewEscape(input.session_number)+'</h3><p>'+explanation+'</p><p class="muted">'+reviewEscape(input.transcript_characters)+' caracteres de transcripción guardados.</p>'+(state?'<p>'+state+'</p>':'')+'<div class="actions"><button type="button" data-retry-generation="'+reviewEscape(input.id)+'"'+(input.can_retry?'':' disabled')+'>'+action+'</button><a class="action" href="/api/generation-inputs/'+encodeURIComponent(input.id)+'/transcript">Descargar transcripción</a></div></article>';
    }).join(''):'<p>No hay generaciones interrumpidas pendientes de recuperar.</p>');
    root.querySelectorAll?.('[data-retry-generation]').forEach(button=>button.addEventListener('click',()=>retrySavedChronicle(button.dataset.retryGeneration,button)));
  } catch(error) { root.textContent='No se pudieron consultar las transcripciones guardadas: '+error.message; }
}
async function retrySavedChronicle(id,button) {
  if(button.disabled)return;
  const label=button.textContent,status=document.getElementById('reviewStatus'),errors=document.getElementById('reviewError');
  button.disabled=true;button.textContent='Recuperando crónica…';errors.textContent='';
  status.textContent='Usando la transcripción guardada. Si hace falta generar la crónica, Gemini puede tardar varios minutos.';
  const headers={'Content-Type':'application/json'};
  let stopped=false,polling=false;
  const poller=setInterval(async()=>{
    if(stopped || polling)return;
    polling=true;
    try {
      const data=await reviewFetch('/api/generation-inputs/'+encodeURIComponent(id)+'/status');
      if(!stopped && data.generation)status.textContent=data.generation.label+' · '+formatSeconds(data.generation.phase_elapsed_seconds);
    } catch {
      if(!stopped)status.textContent='No se pudo actualizar el estado. La generación puede seguir activa.';
    } finally {polling=false;}
  },1000);
  try {
    try {const key=localStorage.getItem('user_gemini_key');if(key)headers['X-Gemini-Api-Key']=key;} catch { /* Server-configured key remains available. */ }
    const result=await reviewFetch('/api/generation-inputs/'+encodeURIComponent(id)+'/retry',{method:'POST',headers,body:JSON.stringify({confirm_generation:true})});
    await showPendingCanonReviews();await showSavedGenerationInputs();await openCanonReview(result.review_id);
  } catch(error) {
    errors.textContent=error.message;status.textContent='La transcripción sigue guardada. Puedes volver a intentarlo sin repetir la transcripción.';
    button.disabled=false;button.textContent=label;
  } finally {
    stopped=true;clearInterval(poller);
  }
}
showSavedGenerationInputs();
