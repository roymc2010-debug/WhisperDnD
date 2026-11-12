const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
function fixture(){
 const nodes=new Map();const classes=new Set();let clock=0;const frames=new Map();let frameId=0;
 function node(id){if(!nodes.has(id))nodes.set(id,{id,value:'',textContent:'',hidden:false,style:{},className:'',attributes:{},setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];},classList:{add(){},remove(){},contains(){return false;}},querySelector(){return null;},scrollIntoView(){}});return nodes.get(id);}
 const intervals=new Map();let timer=0;let data={status:'running',percent:65,step:'Esperando respuesta de Gemini',message:'Esperando respuesta de Gemini',stage:'analyzing',generation:{phase:'waiting_response',label:'Esperando respuesta de Gemini',phase_elapsed_seconds:200,elapsed_seconds:210}};
 const context=vm.createContext({document:{getElementById:node,addEventListener(){},querySelector(){return null;}},console,encodeURIComponent,AbortController,localStorage:{getItem(){return null;},setItem(){}},addEventListener(){},setInterval:fn=>{intervals.set(++timer,fn);return timer;},clearInterval:id=>intervals.delete(id),setTimeout:()=>1,clearTimeout(){},performance:{now:()=>clock},requestAnimationFrame:fn=>{frames.set(++frameId,fn);return frameId;},cancelAnimationFrame:id=>frames.delete(id),WhisperIcons:{set(){}},setActiveView(){},fetch:async()=>({ok:true,json:async()=>data})});context.window=context;
 for(const file of ['utils','progress'])vm.runInContext(fs.readFileSync(require.resolve('../../static/js/'+file+'.js'),'utf8'),context);
 context.showFloatingToast=()=>{};
 return {context,nodes,intervals,frame:time=>{clock=time;const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(time));},setData:value=>{data=value;}};
}
test('waiting shows actual stage time while the reported percentage stays unchanged',async()=>{
 const {context,nodes,intervals,setData}=fixture();context.startProgressTracking('job','Preparando','Texto');await [...intervals.values()][0]();
 assert.match(nodes.get('procGenerationElapsed').textContent,/03:20/);assert.equal(nodes.get('procGenerationElapsed').hidden,false);assert.equal(context.targetProgressPercent,65);
 setData({status:'running',percent:65,step:'Esperando respuesta de Gemini',stage:'analyzing',generation:{phase:'waiting_response',label:'Esperando respuesta de Gemini',phase_elapsed_seconds:201}});await [...intervals.values()][0]();
 assert.match(nodes.get('procGenerationElapsed').textContent,/03:21/);assert.equal(context.targetProgressPercent,65);context.finishProgressTracking(false);assert.equal(intervals.size,0);
});
test('structured provider errors keep their stage instead of becoming generic processing failures',async()=>{
 const {context,nodes,intervals,setData}=fixture();setData({status:'error',error_type:'GeminiProviderTimeout',error_message:'Google Gemini devolvió HTTP 504.',stage:'Comunicación con Gemini'});context.startProgressTracking('job','Preparando','Texto');await [...intervals.values()][0]();assert.equal(nodes.get('errorCardStageText').textContent,'Comunicación con Gemini');assert.match(nodes.get('errorCardMessage').textContent,/HTTP 504/);assert.equal(intervals.size,0);
});

test('regenerating from results attaches its live progress identity to the request',async()=>{
 const {context,intervals}=fixture();vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),context);
 context.currentResult={text:'Nora abre el cofre.',campaign_name:'Mesa',session_number:6};context.currentLiveMode='roleplay';context.currentTargetLanguage='es';context.currentWorkspace='dnd';context.getUserApiHeaders=()=>({});context.checkAuthErrorAndRedirect=()=>false;context.displayResults=()=>{};
 let payload,tracked;
 context.fetch=async(url,opts)=>{assert.equal(url,'/api/campaign/reprocess');payload=JSON.parse(opts.body);tracked=context.currentTaskId;assert.equal(intervals.size,1);return {ok:true,json:async()=>({chronicle:'Texto nuevo.'})};};
 await context.reprocessCampaignChronicle();assert.ok(payload);assert.ok(payload.task_id);assert.equal(payload.task_id,tracked);assert.equal(intervals.size,0);
});

test('confirmed percentages interpolate by time and settle exactly without overshooting',()=>{
 const {context,nodes,frame}=fixture();context.updateProgressBar(47.3,'Transcribiendo','','transcribing');frame(0);frame(500);
 const halfway=parseFloat(nodes.get('progressBarPercent').textContent);assert.ok(halfway>0 && halfway<47.3);
 frame(1000);assert.equal(nodes.get('progressBarPercent').textContent,'47.3%');assert.equal(nodes.get('progressBarFill').style.width,'47.3%');
 context.updateProgressBar(20,'Respuesta antigua','','transcribing');frame(2000);assert.equal(nodes.get('progressBarPercent').textContent,'47.3%');
});
test('Gemini has an indeterminate accessible bar instead of a pretend completion percentage',()=>{
 const {context,nodes}=fixture();context.renderGenerationProgress({phase:'waiting_response',phase_elapsed_seconds:200});context.renderProgressDOM(65);
 assert.equal(nodes.get('progressBarPercent').textContent,'En curso');assert.equal(nodes.get('progressBarTrack').attributes['aria-valuenow'],undefined);assert.equal(nodes.get('progressBarTrack').attributes['aria-valuetext'],'Esperando respuesta de Gemini');
 context.finishProgressTracking(true);assert.equal(nodes.get('progressBarPercent').textContent,'100.0%');
});

test('only the provider wait explains external timing and connection requirements',()=>{
 const {context,nodes}=fixture();context.renderGenerationProgress({phase:'waiting_response',phase_elapsed_seconds:2});
 assert.match(nodes.get('procStepDesc').textContent,/servicio de Google/);
 assert.match(nodes.get('procStepDesc').textContent,/conexión a internet/);
 context.renderGenerationProgress({phase:'saving_review',phase_elapsed_seconds:1});
 assert.equal(nodes.get('procStepDesc').textContent,'');
 context.renderGenerationProgress(null);assert.equal(nodes.get('procStepDesc').textContent,'');
});
