const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function context(){
 const nodes=new Map();
 for(const id of ['modalTabPrimaryIcon','modalTabSecondaryIcon']) nodes.set(id,{style:{},innerHTML:''});
 nodes.set('modalTabSecondary',{classList:{add(){},remove(){}}});
 const ctx=vm.createContext({window:{},document:{getElementById:id=>nodes.get(id)||null},console});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/roster.js'),'utf8'),ctx);
 vm.runInContext('activeParty=[{id:7,primaryClass:{classId:"cleric"},secondaryClass:{active:true,classId:"fighter"}}];renderClassCategories=()=>{};renderSubclassItems=()=>{};',ctx);
 return {ctx,nodes};
}
test('opening a multiclass picker selects the requested current class',()=>{
 const {ctx}=context();
 vm.runInContext('openClassModal(7,"primary")',ctx);
 assert.equal(vm.runInContext('DND_DATABASE.classes[activeClassCatIndex].id',ctx),'cleric');
 vm.runInContext('openClassModal(7,"secondary")',ctx);
 assert.equal(vm.runInContext('DND_DATABASE.classes[activeClassCatIndex].id',ctx),'fighter');
});
test('both picker tabs retain their class colors',()=>{
 const {ctx,nodes}=context();vm.runInContext('updateClassModalHeaderTabs(activeParty[0])',ctx);
 assert.equal(nodes.get('modalTabPrimaryIcon').style.color,'#A2B5C9');
 assert.equal(nodes.get('modalTabSecondaryIcon').style.color,'#7F513E');
});

test('an empty campaign starts with a blank DM, without personal example players',()=>{
 const {ctx}=context();
 const result=vm.runInContext('parseRawRosterToParty([])',ctx);
 assert.equal(result.length,1);assert.equal(result[0].isDM,true);assert.equal(result[0].player,'');
});

test('party save uses the live campaign endpoint and includes the complete roster',async()=>{
 const {ctx,nodes}=context();nodes.set('campaignNameInput',{value:'Mesa QA'});
 let request;ctx.fetch=async(url,options)=>{request={url,payload:JSON.parse(options.body)};return {ok:true,json:async()=>({})};};
 const saved=await vm.runInContext('saveRoster()',ctx);
 assert.equal(saved,true);assert.equal(request.url,'/api/campaigns');
 assert.equal(request.payload.roster[0].character_name,'Aventurero');
 assert.equal(request.payload.campaign_name,'Mesa QA');
});
test('a failed server response never produces a saved-success message',async()=>{
 const {ctx,nodes}=context();nodes.set('campaignNameInput',{value:'Mesa QA'});
 ctx.clearTimeout=()=>{};ctx.fetch=async()=>({ok:false,status:500});const alerts=[];ctx.showAlert=(...args)=>alerts.push(args);ctx.console={warn(){}};
 assert.equal(await vm.runInContext('manualSaveRoster()',ctx),false);
 assert.equal(alerts.some(args=>args[1]==='success'),false);
});
test('multiclass subclasses and homebrew survive storage round trips',()=>{
 const {ctx}=context();
 const data=vm.runInContext('const example=JSON.parse(JSON.stringify(DEFAULT_ROSTER));example.push({id:1,isDM:false,player:"Dani",char:"Iria",speciesText:"Humano",isUserChar:true,primaryClass:{classId:"cleric",subclassId:"life",isCustom:true,customText:"Dominio de la Bruma"},secondaryClass:{active:true,classId:"fighter",subclassId:"champ",isCustom:true,customText:"Guardia de la Costa"}});parseRawRosterToParty(partyToStorageList(example))[1]',ctx);
 assert.equal(data.primaryClass.customText,'Dominio de la Bruma');assert.equal(data.primaryClass.isCustom,true);
 assert.equal(data.secondaryClass.customText,'Guardia de la Costa');assert.equal(data.secondaryClass.isCustom,true);assert.equal(data.secondaryClass.classId,'fighter');
});
