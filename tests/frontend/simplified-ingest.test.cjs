const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('engine selection exposes exactly one pressed button and preserves the chosen engine',()=>{
 const nodes=new Map();
 for(const id of ['engineGroqBtn','engineLocalBtn'])nodes.set(id,{className:'',attributes:{},setAttribute(k,v){this.attributes[k]=v;}});
 nodes.set('transcriptionEngine',{value:''});
 const saved=new Map();
 const context=vm.createContext({window:{addEventListener(){}},document:{getElementById:id=>nodes.get(id)||null,addEventListener(){}},localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},console});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),context);
 for(const engine of ['groq','local','groq']){
  context.setEngine(engine);
  assert.equal(nodes.get('transcriptionEngine').value,engine);
  assert.equal(saved.get('whisper_engine'),engine);
  for(const name of ['groq','local']){
   const label=name==='groq'?'Groq':'Local';
   assert.equal(nodes.get('engine'+label+'Btn').attributes['aria-pressed'],String(name===engine));
  }
 }
});

test('changing document format preserves the entered topic and date',()=>{
 const nodes=new Map([['workStudyDocumentFormat',{value:'academic'}],['workStudyFormatDescription',{textContent:''}],['workStudyTopicInput',{value:'Mi tema'}],['workStudyDateInput',{value:'31/10/2026 10:00'}]]);
 const saved=new Map();const context=vm.createContext({window:{addEventListener(){}},document:{getElementById:id=>nodes.get(id)||null,addEventListener(){}},localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},console});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),context);
 vm.runInContext('setWorkStudyDocumentFormat("executive")',context);
 assert.equal(vm.runInContext('getWorkStudyDocumentFormat()',context),'executive');
 assert.equal(nodes.get('workStudyTopicInput').value,'Mi tema');
 assert.equal(nodes.get('workStudyDateInput').value,'31/10/2026 10:00');
});

test('meeting classification uses stored format and supports older titles',()=>{
 const context=vm.createContext({window:{},document:{getElementById(){return null;}}});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/notes.js'),'utf8'),context);
 assert.equal(vm.runInContext('isMeetingNote({filename:"apuntes_reunion_equipo.md",title:"Entrega"})',context),true);
 assert.equal(vm.runInContext('isMeetingNote({document_format:"executive",title:"Entrega"})',context),true);
 assert.equal(vm.runInContext('isMeetingNote({document_format:"academic",title:"Reuniones en sociología"})',context),false);
 assert.equal(vm.runInContext('isMeetingNote({title:"Reunión semanal"})',context),true);
});

test('switching from automatic session numbering to an audio file allows direct number entry',()=>{
 const input={value:'4',readOnly:true,disabled:true,removeAttribute(name){if(name==='readonly')this.readOnly=false;}};
 const nodes=new Map([['sessionNumberInput',input],['overrideSessionNumberCheck',{checked:false}]]);
 const context=vm.createContext({window:{addEventListener(){}},document:{getElementById:id=>nodes.get(id)||null,addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},console});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),context);
 vm.runInContext('updateSessionLockForTab("file")',context);
 assert.equal(input.disabled,false);
 assert.equal(input.readOnly,false);
});

test('results card persists in sessionStorage by workspace and clears on start of session',()=>{
 const sessionStore = new Map();
 const makeNode = () => ({ style: {}, classList: { classes: new Set(['hidden']), add(c){ this.classes.add(c); }, remove(c){ this.classes.delete(c); }, contains(c){ return this.classes.has(c); } }, innerHTML: '', setAttribute(){}, getAttribute(){ return null; }, appendChild(){}, scrollIntoView(){} });
 const nodes = new Map([
  ['resultsCard', makeNode()],
  ['chronicleView', makeNode()],
 ]);
 const context = vm.createContext({
  window: { addEventListener(){} },
  addEventListener: () => {},
  document: { getElementById: id => nodes.get(id) || makeNode(), addEventListener(){}, createElement: makeNode, querySelector: () => makeNode(), querySelectorAll: () => [] },
  localStorage: { getItem(){ return null; }, setItem(){} },
  sessionStorage: {
   getItem: k => sessionStore.get(k) || null,
   setItem: (k, v) => sessionStore.set(k, String(v)),
   removeItem: k => sessionStore.delete(k)
  },
  fetch: async () => ({ ok: true, json: async () => ({ campaigns: [] }) }),
  console,
  escapeHtml: s => String(s),
  formatSeconds: s => String(s),
  WhisperIcons: { set: () => {} },
  renderMarkdownWithKaTeX: s => String(s)
 });
 context.window = context;
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'), context);

 context.currentWorkspace = 'dnd';
 context.displayResults({ chronicle: 'Crónica épica sesión 4' });
 assert.equal(nodes.get('resultsCard').classList.contains('hidden'), false);
 assert.ok(sessionStore.has('whisper_last_result_dnd'));
 assert.equal(sessionStore.has('whisper_last_result_work_and_study'), false);

 context.clearResultsView(true);
 assert.equal(nodes.get('resultsCard').classList.contains('hidden'), true);
 assert.equal(sessionStore.has('whisper_last_result_dnd'), false);

 sessionStore.set('whisper_last_result_dnd', JSON.stringify({ chronicle: 'Crónica restaurada' }));
 const restored = context.restoreLastResultForWorkspace('dnd');
 assert.equal(restored, true);
 assert.equal(nodes.get('resultsCard').classList.contains('hidden'), false);
 assert.equal(context.currentResult.chronicle, 'Crónica restaurada');
});
