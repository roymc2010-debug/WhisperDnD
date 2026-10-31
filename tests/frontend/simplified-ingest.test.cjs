const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const core=require('../../static/js/desktop-core.js');

test('session step controls obey the recording lock and the minimum',()=>{
 assert.equal(core.stepSessionNumber({value:1,delta:-1}),1);
 assert.equal(core.stepSessionNumber({value:4,delta:1}),5);
 assert.equal(core.stepSessionNumber({value:'',delta:1}),1);
 assert.equal(core.stepSessionNumber({value:4,delta:1,locked:true}),4);
 assert.equal(core.stepSessionNumber({value:4,delta:1,recording:true}),4);
});
test('re-record stepping can select only saved sessions, including gaps',()=>{
 assert.equal(core.stepSessionNumber({value:1,delta:1,sessions:[1,3]}),3);
 assert.equal(core.stepSessionNumber({value:3,delta:1,sessions:[1,3]}),3);
 assert.equal(core.stepSessionNumber({value:3,delta:-1,sessions:[1,3]}),1);
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
