const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function view(fetch = async () => ({ok:true,json:async()=>({})})) {
  const nodes = new Map();
  for (const id of ['wikiCampaignSelect','wikiDossierEmpty','wikiDossierContent','wikiMutationStatus','wikiEditError','wikiEditSave','wikiSessionExportSelect']) {
    nodes.set(id,{value:id==='wikiCampaignSelect'?'Mesa':'',innerHTML:'',textContent:'',classList:{add(){},remove(){}},focus(){}});
  }
  const fields = [{dataset:{wikiEdit:'name'},value:'Nóra del Mar'}];
  const context = vm.createContext({document:{getElementById:id=>nodes.get(id)||null,
    querySelectorAll:selector=>selector==='[data-wiki-edit]'?fields:[]},
    fetch,console,escapeHtml:s=>(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
    renderMarkdownWithKaTeX:s=>s,WhisperIcons:{markup:()=>''}});
  context.window=context;
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/wiki.js'),'utf8'),context);
  context.currentWikiCampaignState={campaign_name:'Mesa',sessions:[{session_number:2,title:'Duplicada'}],
    universal_pcs:[{personaje:'Lia'}],locations:[],items:[],npcs:[]};
  return {context,nodes,fields};
}

test('character and location dossiers expose an editor while sessions expose individual deletion',()=>{
  const {context,nodes}=view();
  for (const [type,data,label] of [['pc',{personaje:'Lia'},'Editar ficha'],['npc',{name:'Nora'},'Editar PNJ'],['location',{name:'Puerto'},'Editar lugar'],['session',{session_number:2},'Eliminar sesión']]) {
    context.selectedWikiEntity={type,key:'selected',data};
    context.renderWikiDossier();
    assert.match(nodes.get('wikiDossierContent').innerHTML,new RegExp(label));
  }
});

test('saving a character sends an edit, preserves selection and uses returned state',async()=>{
  const requests=[];
  const state={campaign_name:'Mesa',npcs:[{name:'Nóra del Mar'}],sessions:[{session_number:1,title:'Nóra del Mar regresa'}]};
  const {context,nodes}=view(async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({campaign_state:state,entity:state.npcs[0]})};});
  context.selectedWikiEntity={type:'npc',key:'Nora',data:{name:'Nora'}};
  await context.submitWikiEntityEdit({preventDefault(){}});
  assert.equal(requests[0].url,'/api/campaigns/Mesa/entities/npc');
  assert.equal(requests[0].options.method,'PUT');
  assert.deepEqual(JSON.parse(requests[0].options.body),{original_name:'Nora',name:'Nóra del Mar'});
  assert.equal(context.selectedWikiEntity.data.name,'Nóra del Mar');
  assert.match(nodes.get('wikiSessionExportSelect').innerHTML,/Nóra del Mar regresa/);
});

test('failed edit keeps the old character and displays the server error',async()=>{
  const {context,nodes}=view(async()=>({ok:false,json:async()=>({detail:'Nombre ya existente'})}));
  context.selectedWikiEntity={type:'pc',key:'Lia',data:{personaje:'Lia'}};
  await context.submitWikiEntityEdit({preventDefault(){}});
  assert.equal(context.selectedWikiEntity.data.personaje,'Lia');
  assert.equal(nodes.get('wikiEditError').textContent,'Nombre ya existente');
});

test('deleting one session requires confirmation and refreshes the current history',async()=>{
  const requests=[];
  const {context}=view(async(url,options)=>{if (url.endsWith('/deletion-preview')) return {ok:true,json:async()=>({removed:{npcs:['Sombra']},shared:{},unattributed:{},legacy_provenance:true})};if (!options) return {ok:true,json:async()=>[]}; requests.push({url,options});return {ok:true,json:async()=>({campaign_state:{campaign_name:'Mesa',sessions:[],last_session:0},backup_id:'backup.json'})};});
  context.selectedWikiEntity={type:'session',data:{session_number:2}};
  await context.openDeleteWikiSession();
  assert.equal(requests.length,0);
  assert.match(context.document.getElementById('wikiDossierContent').innerHTML,/Confirmar eliminación/);
  assert.match(context.document.getElementById('wikiDossierContent').innerHTML,/Sombra/);
  await context.confirmDeleteWikiSession();
  assert.equal(requests[0].url,'/api/campaigns/Mesa/session/2');
  assert.equal(requests[0].options.method,'DELETE');
  assert.equal(context.currentWikiCampaignState.sessions.length,0);
  assert.equal(context.selectedWikiEntity,null);
});

test('player names are read-only in the wiki editor',()=>{
  const {context,nodes}=view();
  context.selectedWikiEntity={type:'pc',data:{personaje:'Lia',jugador:'Ana'}};
  context.openWikiEntityEditor();
  assert.match(nodes.get('wikiDossierContent').innerHTML,/id="wikiEdit_name"[^>]*readonly/);
  assert.match(nodes.get('wikiDossierContent').innerHTML,/id="wikiEdit_player_name"[^>]*readonly/);
});

test('a failed deletion preview never exposes a confirmation action',async()=>{
  const {context,nodes}=view(async()=>({ok:false,json:async()=>({detail:'Sesión dañada'})}));
  context.selectedWikiEntity={type:'session',data:{session_number:2}};
  await context.openDeleteWikiSession();
  assert.match(nodes.get('wikiDossierContent').innerHTML,/Sesión dañada/);
  assert.doesNotMatch(nodes.get('wikiDossierContent').innerHTML,/Confirmar eliminación/);
});

test('a place explicitly linked by the user is visible for a PC even when it is not a residence',()=>{
  const {context}=view();
  context.currentWikiCampaignState.locations=[{name:'Puerto',associated_characters:['Lia'],manual_associated_characters:['Lia']}];
  assert.equal(context.getAssociatedLocationsForCharacter('Lia').length,1);
});

test('an edited description is visible alongside historical notes',()=>{
  const {context}=view();
  assert.match(context.buildPcDossierHtml({personaje:'Lia',description:'Descripción corregida',hitos_acumulados:['Hecho anterior']}),/Descripción corregida/);
  assert.match(context.buildNpcDossierHtml({name:'Nora',description:'Guía del puerto',notes:['Nota anterior']}),/Guía del puerto/);
});


test('NPC editor exposes every alias for correction and removal, including hidden phonetic variants',()=>{
  const {context,nodes}=view();
  context.selectedWikiEntity={type:'npc',data:{name:'Nora',aliases:['Nori','La \"Guía\"','<Erróneo>']}};
  context.openWikiEntityEditor();
  const html=nodes.get('wikiDossierContent').innerHTML;
  assert.match(html,/<textarea[^>]*data-wiki-edit="aliases"/);
  assert.match(html,/Nori/);
  assert.match(html,/&lt;Erróneo&gt;/);
  assert.match(html,/Variantes de pronunciación/);
  assert.match(html,/borra una línea/);
});

for (const [text,expected] of [[' Nori \n Guía nueva \n\n',['Nori','Guía nueva']],['',[]]]) {
  test('NPC alias edits submit a list, including explicit removal: '+JSON.stringify(text),async()=>{
    const requests=[];
    const {context,fields}=view(async(url,options)=>{requests.push(JSON.parse(options.body));return {ok:true,json:async()=>({entity:{name:'Nora',aliases:expected},campaign_state:{campaign_name:'Mesa',npcs:[],sessions:[]}})};});
    context.selectedWikiEntity={type:'npc',data:{name:'Nora',aliases:['Erróneo']}};
    fields.splice(0,fields.length,{dataset:{wikiEdit:'name'},value:'Nora'},{dataset:{wikiEdit:'aliases'},value:text});
    await context.submitWikiEntityEdit({preventDefault(){}});
    assert.deepEqual(requests[0].aliases,expected);
  });
}

test('alias controls stay out of player and place editors',()=>{
  const {context,nodes}=view();
  for(const type of ['pc','location']) {
    context.selectedWikiEntity={type,data:{name:'Nora',personaje:'Lia',aliases:['Variante']}};
    context.openWikiEntityEditor();
    assert.doesNotMatch(nodes.get('wikiDossierContent').innerHTML,/data-wiki-edit="aliases"/);
  }
});


test('phonetic variants never become invented nicknames in NPC display',()=>{
  const {context}=view();
  const html=context.buildNpcDossierHtml({name:'Nora del Mar',aliases:['Nori','Norita'],nicknames:['La Vigía']});
  assert.match(html,/La Vigía/);
  assert.doesNotMatch(html,/Nora &quot;Nori&quot;/);
  assert.equal(context.formatCharacterDisplayName('Nora del Mar',[]),'Nora del Mar');
});
