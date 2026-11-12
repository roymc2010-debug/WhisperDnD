const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function context() {
  const nodes = new Map();
  const ctx = vm.createContext({window:{addEventListener(){}}, document:{getElementById:id=>nodes.get(id)||null,addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},console});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),ctx);
  return ctx;
}

test('all uploaded parts are retained in order, can move and remove without losing the others',()=>{
  const ctx=context();
  ctx.handleIncomingFiles([{name:'Parte_01.wav',size:10},{name:'Parte_02.wav',size:12}]);
  assert.equal(vm.runInContext('selectedAudioParts.length',ctx),2);
  ctx.moveAudioPart(1,-1);
  assert.equal(vm.runInContext('selectedAudioParts[0].file.name',ctx),'Parte_02.wav');
  ctx.removeAudioPart(0);
  assert.equal(vm.runInContext('selectedAudioParts[0].file.name',ctx),'Parte_01.wav');
});

test('local recordings accumulate instead of replacing the last part',()=>{
  const ctx=context();
  ctx.selectExistingRecording('first.wav',true,1,'recordings');
  ctx.selectExistingRecording('second.wav',true,1,'recordings');
  assert.equal(vm.runInContext('selectedAudioParts.length',ctx),2);
  assert.equal(vm.runInContext('selectedAudioParts[0].filename',ctx),'first.wav');
  ctx.selectExistingRecording('second.wav',true,1,'recordings');
  assert.equal(vm.runInContext('selectedAudioParts.length',ctx),2);
});

test('multipart uploads carry every audio and matching timeline to the API', async()=>{
  const ctx=context();
  assert.equal(typeof ctx.appendSelectedAudioParts,'function');
  ctx.handleIncomingFiles([{name:'first.wav',size:10},{name:'second.wav',size:12},{name:'first.timeline.json',size:2},{name:'second.timeline.json',size:2}]);
  const values=[];
  ctx.appendSelectedAudioParts({append:(name,value)=>values.push([name,value])});
  assert.deepEqual(values.filter(v=>v[0]==='files').map(v=>v[1].name),['first.wav','second.wav']);
  assert.deepEqual(values.filter(v=>v[0]==='timeline_files').map(v=>v[1].name),['first.timeline.json','second.timeline.json']);
});

test('browser recording can send reference text without accessing the desktop request', async()=>{
  const notices=[], sent=[];
  const nodes=new Map([['campaignNameInput',{value:'Mesa'}],['sessionNumberInput',{value:'4'}],['optionalReferenceTextInput',{value:'texto de referencia'}]]);
  const ctx=vm.createContext({window:{innerWidth:1280,currentLiveMode:'roleplay',currentWorkspace:'dnd'},navigator:{userAgent:'Desktop',maxTouchPoints:0},localStorage:{getItem(){return null;}},document:{getElementById:id=>nodes.get(id)||null},console,Blob,FormData,AbortController,generateTaskId:()=> 'fake',showAlert:msg=>notices.push(msg),getUserApiHeaders:()=>({}),checkAuthErrorAndRedirect:()=>false,displayResults(){},fetch:async(url,opts)=>{sent.push(opts.body);return {ok:true,json:async()=>({})};}});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/audio.js'),'utf8'),ctx);
  ctx.stopTimer=()=>{};ctx.setRecordingUI=()=>{};ctx.stopBrowserVuMeter=()=>{};
  ctx.audioSourceMode='browser_mic';ctx.browserAudioChunks=[new Blob(['synthetic audio'])];
  let completion;
  ctx.mediaRecorder={mimeType:'audio/webm',state:'recording',stop(){completion=this.onstop();}};
  await ctx.stopSessionAndProcess();await completion;
  assert.equal(notices.length,0,notices.join('\n'));
  assert.equal(sent.length,1);
  assert.equal(sent[0].get('reference_text'),'texto de referencia');
});

test('campaign filenames with apostrophes remain selectable without inline filename code', async()=>{
  const ctx=context();const list={innerHTML:''};
  ctx.document.getElementById=id=>id==='localRecordingsList'?list:null;
  ctx.escapeHtml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const name="O'Brien_<Mesa>_Sesion_04.wav";
  ctx.fetch=async()=>({ok:true,json:async()=>({files:[{filename:name,created_at:'Desconocida',size_mb:1}]})});
  await ctx.loadLocalRecordingsList();
  assert.ok(!list.innerHTML.includes(name));
  assert.equal(typeof ctx.addCachedRecording,'function');
  ctx.addCachedRecording(0);
  assert.equal(vm.runInContext('selectedAudioParts[0].filename',ctx),name);
});
