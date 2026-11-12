const test=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
function fixture({failure=false,inputs=[]}={}){
 const nodes=new Map(['generationInputList','reviewList','reviewDetail','reviewStatus','reviewError','canonReviewForm','confirmCanonReview','applyCanonReview'].map(id=>[id,{innerHTML:'',textContent:'',checked:false,addEventListener(){},scrollIntoView(){}}]));
 const intervals=new Map();let timer=0;const requests=[];const fields=[{dataset:{reviewField:'chronicle_text'},value:'Texto corregido por el usuario.'}];
 const draft={id:'a'.repeat(32),revision:'revision',status:'pending',campaign_name:'Mesa',session_number:4,replaces_session:true,chapter:{chronicle_text:'Borrador.'},transcript:'<fuente>',proposals:[{id:'items:0',collection:'items',key:'Varita',before:null,after:{name:'Varita',holder:'Lia'},evidence:{notice:'Sin citas verificables.',quotes:[]}}]};
 const fetch=async(url,opts)=>{requests.push({url,opts});if(opts)return {ok:!failure,json:async()=>failure?{detail:'La campaña cambió.'}:url.endsWith('/retry')?{review_id:'a'.repeat(32)}:{status:'applied'}};return {ok:true,json:async()=>url==='/api/generation-inputs'?inputs:url==='/api/session-reviews'?[]:draft};};
 const context=vm.createContext({fetch,URLSearchParams,setInterval:fn=>{intervals.set(++timer,fn);return timer;},clearInterval:id=>intervals.delete(id),localStorage:{getItem:()=> 'synthetic-personal-key'},location:{search:''},document:{getElementById:id=>nodes.get(id),querySelectorAll:selector=>selector==='[data-review-field]'?fields:[]},console});
 context.window=context;vm.runInContext(fs.readFileSync(require.resolve('../../static/js/utils.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/canon-review.js'),'utf8'),context);
 return {context,nodes,requests,draft,intervals};
}
test('review exposes replacement intent, escapes source and leaves proposals unselected',async()=>{
 const {context,nodes,draft}=fixture();await context.openCanonReview(draft.id);const html=nodes.get('reviewDetail').innerHTML;
 assert.match(html,/reemplazará la sesión/);assert.match(html,/&lt;fuente&gt;/);assert.doesNotMatch(html,/data-review-proposal[^>]*checked/);assert.match(html,/Portador/);assert.doesNotMatch(html,/&quot;holder&quot;/);
});
test('saving a reviewed draft never requests generation and preserves explicit rejection',async()=>{
 const {context,nodes,requests,draft}=fixture();await context.openCanonReview(draft.id);
 await context.submitCanonReview({preventDefault(){}});assert.equal(requests.filter(r=>r.opts).length,0);
 nodes.get('confirmCanonReview').checked=true;await context.submitCanonReview({preventDefault(){}});
 const writes=requests.filter(r=>r.opts);assert.equal(writes.length,1);assert.equal(writes[0].url,'/api/session-reviews/'+draft.id+'/apply');const body=JSON.parse(writes[0].opts.body);assert.deepEqual(body.selected,[]);assert.equal(body.chapter.chronicle_text,'Texto corregido por el usuario.');
});
test('a conflict preserves the open draft and permits reviewing again',async()=>{
 const {context,nodes,draft}=fixture({failure:true});await context.openCanonReview(draft.id);nodes.get('confirmCanonReview').checked=true;await context.submitCanonReview({preventDefault(){}});assert.equal(nodes.get('reviewError').textContent,'La campaña cambió.');assert.equal(nodes.get('applyCanonReview').disabled,false);assert.match(nodes.get('reviewDetail').innerHTML,/Borrador/);
});

test('saved transcripts are visible without starting any generation',async()=>{
 const {context,nodes,requests}=fixture({inputs:[{id:'b'.repeat(32),campaign_name:'<Mesa>',session_number:6,transcript_characters:120000,can_retry:true,response_saved:false,error_type:'ReadTimeout'}]});
 assert.equal(typeof context.showSavedGenerationInputs,'function');await context.showSavedGenerationInputs();
 const html=nodes.get('generationInputList').innerHTML;assert.match(html,/Generar solo crónica/);assert.match(html,/cuota de Gemini/);assert.match(html,/Descargar transcripción/);assert.match(html,/&lt;Mesa&gt;/);assert.equal(requests.filter(r=>r.opts).length,0);
});
test('recovery sends only the saved job and Gemini key, not audio or Groq',async()=>{
 const {context,requests}=fixture();assert.equal(typeof context.retrySavedChronicle,'function');const button={disabled:false,textContent:'Generar solo crónica'};
 await context.retrySavedChronicle('b'.repeat(32),button);const writes=requests.filter(r=>r.opts);assert.equal(writes.length,1);assert.equal(writes[0].url,'/api/generation-inputs/'+'b'.repeat(32)+'/retry');assert.equal(writes[0].opts.headers['X-Gemini-Api-Key'],'synthetic-personal-key');assert.deepEqual(JSON.parse(writes[0].opts.body),{confirm_generation:true});assert.doesNotMatch(JSON.stringify(writes),/Groq|transcribe|audio_file/);
});
test('failed recovery keeps the saved input available and allows another explicit attempt',async()=>{
 const {context,nodes}=fixture({failure:true});assert.equal(typeof context.retrySavedChronicle,'function');const button={disabled:false,textContent:'Generar solo crónica'};
 await context.retrySavedChronicle('b'.repeat(32),button);assert.equal(button.disabled,false);assert.equal(button.textContent,'Generar solo crónica');assert.match(nodes.get('reviewError').textContent,/La campaña cambió/);
});
test('saved provider responses offer recovery without a new generation',async()=>{
 const {context,nodes}=fixture({inputs:[{id:'b'.repeat(32),campaign_name:'Mesa',session_number:6,transcript_characters:50,can_retry:true,response_saved:true}]});assert.equal(typeof context.showSavedGenerationInputs,'function');await context.showSavedGenerationInputs();assert.match(nodes.get('generationInputList').innerHTML,/Recuperar respuesta guardada/);assert.doesNotMatch(nodes.get('generationInputList').innerHTML,/consume cuota/);
});

test('saved-chronicle recovery polls phases and always stops its timer',async()=>{
 const {context,intervals}=fixture();let finish;const pending=new Promise(resolve=>{finish=resolve;});let statusCalls=0;
 context.fetch=async(url,opts)=>opts?pending:{ok:true,json:async()=>{if(url.endsWith('/status')){statusCalls++;return {generation:{phase:'waiting_response',label:'Esperando respuesta de Gemini',phase_elapsed_seconds:200}};}return [];}};
 const button={disabled:false,textContent:'Generar solo crónica'};const run=context.retrySavedChronicle('b'.repeat(32),button);assert.equal(intervals.size,1);
 await [...intervals.values()][0]();assert.equal(statusCalls,1);
 finish({ok:false,json:async()=>({detail:'Google Gemini devolvió HTTP 504.'})});await run;assert.equal(intervals.size,0);assert.equal(button.disabled,false);
});
