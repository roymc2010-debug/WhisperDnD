const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function view(fetch){
 const nodes=new Map();
 const make=()=>({value:'',textContent:'',innerHTML:'',hidden:false,className:'',dataset:{},style:{},classList:{add(){},remove(){},contains(){return true;}},setAttribute(k,v){this[k]=v;}});
 const document={getElementById(id){if(id==='apiOnboardingBanner')return null;if(!nodes.has(id))nodes.set(id,make());return nodes.get(id);}};
 const saved=new Map([['user_groq_key','test-groq'],['user_gemini_key','test-gemini']]);
 const context=vm.createContext({window:{},document,localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},fetch,AbortController,setTimeout:(fn,ms)=>ms<10000?(queueMicrotask(fn),0):setTimeout(fn,ms),clearTimeout,console:{warn(){},error(){}}});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/api.js'),'utf8'),context);
 return {context,nodes,document};
}

test('a failed API check lights the corresponding warning even when a personal key exists',async()=>{
 const {context,nodes}=view(async()=>({ok:true,json:async()=>({groq:true,gemini:false,gemini_message:'La clave no permite acceso.',gemini_model:'modelo-configurado'})}));
 await context.checkApiKeysStatus();
 assert.equal(nodes.get('settingsGroqStatus').dataset.state,'ready');
 assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'error');
 assert.equal(nodes.get('settingsApiWarning').hidden,false);
 assert.equal(nodes.get('settingsApiIssueSummary').hidden,false);
 assert.match(nodes.get('settingsApiIssueSummary').textContent,/Gemini.*clave/i);
 assert.equal(nodes.get('settingsGeminiModelText').textContent,'modelo-configurado');
});

test('an HTTP failure clears a previous green state and explains what to check',async()=>{
 let ok=true;
 const {context,nodes}=view(async()=>ok?{ok:true,json:async()=>({groq:true,gemini:true})}:{ok:false,status:503});
 await context.checkApiKeysStatus();
 assert.equal(nodes.get('settingsApiWarning').hidden,true);
 ok=false;
 await context.checkApiKeysStatus();
 assert.equal(nodes.get('settingsGroqStatus').dataset.state,'unverified');
 assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'unverified');
 assert.equal(nodes.get('settingsApiWarning').hidden,false);
 assert.match(nodes.get('settingsApiIssueSummary').textContent,/servidor|conexión/i);
});

test('an empty provider error still gives an actionable settings explanation',async()=>{
 const {context,nodes}=view(async()=>({ok:true,json:async()=>({groq:true,gemini:false,gemini_message:'Error validando Gemini: '})}));
 await context.checkApiKeysStatus();
 assert.match(nodes.get('settingsApiIssueSummary').textContent,/Probar Conexión/);
 assert.match(nodes.get('settingsApiIssueSummary').textContent,/clave/);
});

test('selecting local does not claim that its model was checked and does not require Groq',async()=>{
 const {context,nodes,document}=view(async()=>({ok:true,json:async()=>({groq:false,gemini:true})}));
 document.getElementById('transcriptionEngine').value='local';
 await context.checkApiKeysStatus();
 assert.equal(nodes.get('settingsGroqStatus').dataset.state,'unverified');
 assert.match(nodes.get('settingsGroqStatusText').textContent,/sin comprobar/i);
 assert.equal(nodes.get('settingsApiWarning').hidden,true);
});

test('an unavailable Drive check does not disconnect an already connected account',async()=>{
 const {context}=view(async()=>({ok:true,json:async()=>({groq:true,gemini:true,drive:null})}));
 let driveUpdates=0;
 context.window.isGoogleDriveConnected=true;
 context.updateDriveUIState=()=>{driveUpdates++;};
 await context.checkApiKeysStatus();
 assert.equal(context.window.isGoogleDriveConnected,true);
 assert.equal(driveUpdates,0);
});

test('API key verification explicitly excludes optional Drive work',async()=>{
 let requested;
 const {context}=view(async(url)=>{requested=url;return {ok:true,json:async()=>({groq:true,gemini:true,drive:null})};});
 await context.checkApiKeysStatus();
 assert.equal(requested,'/api/status/keys?include_drive=false');
});

test('a delayed check cannot replace the result of a newer check',async()=>{
 let finishOld;
 let calls=0;
 const old=new Promise(resolve=>{finishOld=resolve;});
 const {context,nodes}=view(()=>++calls===1?old:Promise.resolve({ok:true,json:async()=>({groq:false,gemini:false})}));
 const first=context.checkApiKeysStatus();
 assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'pending');
 await context.checkApiKeysStatus();
 finishOld({ok:true,json:async()=>({groq:true,gemini:true})});
 await first;
 assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'error');
 assert.equal(nodes.get('settingsApiWarning').hidden,false);
});

test('Drive sync buttons restore exactly one icon after a completed request',async()=>{
 const nodes=new Map(['btnSyncDriveHeader','btnSyncDriveSettings','btnSyncDriveModal'].map(id=>[id,{innerHTML:'',disabled:false}]));
 const context=vm.createContext({window:{},document:{getElementById:id=>nodes.get(id)||null},fetch:async()=>({ok:true,json:async()=>({status:'success'})})});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/drive.js'),'utf8'),context);
 await context.syncWithGoogleDrive(true);
 for(const button of nodes.values()){
  assert.equal(button.disabled,false);
  assert.equal((button.innerHTML.match(/<svg\b|data-ui-icon=/g)||[]).length,1);
 }
});

test('a partial Drive sync keeps an attention state and explains conflicts',async()=>{
 const nodes=new Map(['btnSyncDriveHeader','btnSyncDriveSettings','btnSyncDriveModal','driveSyncStatusWidget'].map(id=>[id,{innerHTML:'',disabled:false,className:'',classList:{add(){},remove(){}}}]));
 const alerts=[];
 const context=vm.createContext({window:{},document:{getElementById:id=>nodes.get(id)||null},showAlert:m=>alerts.push(m),fetch:async()=>({ok:true,json:async()=>({status:'partial',conflicts:[{file:'mesa.json',message:'Ambas copias cambiaron'}]})})});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/drive.js'),'utf8'),context);
 await context.syncWithGoogleDrive(true);
 assert.match(nodes.get('driveSyncStatusWidget').innerHTML,/Revisar sincronización/);
 assert.equal(nodes.get('btnSyncDriveSettings').disabled,false);
 assert.equal(alerts.length,1);
 assert.match(alerts[0],/mesa.json/);
});

test('a failed sync does not turn a connected Drive account into disconnected',async()=>{
 const node={innerHTML:'',className:'',classList:{add(){},remove(){}}};
 const context=vm.createContext({window:{},console:{error(){}},document:{getElementById:id=>id==='driveSyncStatusWidget'?node:null},fetch:async()=>({ok:false,json:async()=>({message:'Network unavailable'})})});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/drive.js'),'utf8'),context);
 context._driveConnected=true;
 await context.syncWithGoogleDrive(true);
 assert.equal(context._driveConnected,true);
 assert.match(node.innerHTML,/Revisar sincronización/);
});

test('an explicitly disconnected Drive response is not shown as saved',async()=>{
 const node={innerHTML:'',className:'',classList:{add(){},remove(){}}};
 const context=vm.createContext({window:{},document:{getElementById:id=>id==='driveSyncStatusWidget'?node:null},fetch:async()=>({ok:true,json:async()=>({status:'not_connected',message:'Inicia sesión'})})});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/drive.js'),'utf8'),context);
 context._driveConnected=true;
 await context.syncWithGoogleDrive(true);
 assert.equal(context._driveConnected,false);
 assert.doesNotMatch(node.innerHTML,/Guardado en Drive/);
});

test('startup automatically recovers from transient local server failures',async()=>{
 let attempts=0;const {context,nodes}=view(async()=>{attempts++;if(attempts<3)throw new TypeError('Failed to fetch');return {ok:true,json:async()=>({groq:true,gemini:true})};});
 await context.checkApiKeysStatus();assert.equal(attempts,3);assert.equal(nodes.get('settingsGroqStatus').dataset.state,'ready');assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'ready');assert.equal(nodes.get('settingsApiWarning').hidden,true);
});
test('a server outage is bounded and leaves both providers unverified with one shared explanation',async()=>{
 let attempts=0;const {context,nodes}=view(async()=>{attempts++;throw new TypeError('Failed to fetch');});await context.checkApiKeysStatus();assert.equal(attempts,3);assert.equal(nodes.get('settingsGroqStatus').dataset.state,'unverified');assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'unverified');const text=nodes.get('settingsApiIssueSummary').textContent;assert.match(text,/servidor/i);assert.doesNotMatch(text,/Groq:.*Gemini:|inválida/i);
});
test('an actual credential rejection is not automatically retried',async()=>{
 let attempts=0;const {context,nodes}=view(async()=>{attempts++;return {ok:true,json:async()=>({groq:false,gemini:false,groq_message:'Clave rechazada',gemini_message:'Clave rechazada'})};});await context.checkApiKeysStatus();assert.equal(attempts,1);assert.equal(nodes.get('settingsGeminiStatus').dataset.state,'error');
});
test('an invalid diagnostic response is distinguished from an unreachable server',async()=>{
 let attempts=0;const {context,nodes}=view(async()=>{attempts++;return {ok:true,json:async()=>({groq:'unexpected',gemini:true})};});await context.checkApiKeysStatus();assert.equal(attempts,1);assert.match(nodes.get('settingsApiIssueSummary').textContent,/diagnóstico inválido/i);assert.doesNotMatch(nodes.get('settingsApiIssueSummary').textContent,/no respondió|no se pudo comprobar la conexión/i);
});

test('a shared server failure is explained once rather than repeated inside both provider cards',async()=>{
 const {context,nodes}=view(async()=>{throw new TypeError('Failed to fetch');});await context.checkApiKeysStatus();const summary=nodes.get('settingsApiIssueSummary').textContent;assert.notEqual(nodes.get('settingsGroqStatusText').textContent,summary);assert.notEqual(nodes.get('settingsGeminiStatusText').textContent,summary);assert.match(nodes.get('settingsGeminiStatusText').textContent,/sin comprobar/i);
});

test('the explicit connection button asks for fresh verification instead of cached status',async()=>{
 let requested;const {context}=view(async(url)=>{requested=url;return {ok:true,json:async()=>({groq:true,gemini:true})};});await context.checkApiKeysStatus(true);assert.equal(requested,'/api/status/keys?include_drive=false&force=true');
});
