const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('icon names cannot inject arbitrary markup into the interface', () => {
  const icons = require('../../static/js/ui-icons.js');
  const html = icons.markup('<img src=x onerror=alert(1)>');
  assert.match(html, /^<svg /);
  assert.doesNotMatch(html, /<img|onerror|alert\(/);
  assert.match(html, /aria-hidden="true"/);
});

test('headphone warning uses device metadata even when its name has no headphone keyword', () => {
  let hidden = true;
  const speaker = {options:[{textContent:'Altavoces integrados',dataset:{headphone:'false'}},{textContent:'WH-1000XM5',dataset:{headphone:'true'}}],selectedIndex:0};
  const warning = {classList:{remove(){hidden=false;},add(){hidden=true;}}};
  const context = vm.createContext({window:{innerWidth:1280,currentLiveMode:'roleplay'},navigator:{userAgent:'Desktop',maxTouchPoints:0},localStorage:{getItem(){return null;}},document:{getElementById(id){return id==='selectAudioSpeaker'?speaker:id==='speakerWarningHint'?warning:null;}}});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/audio.js'),'utf8'),context);
  vm.runInContext('checkSpeakerSelection()',context);
  assert.equal(hidden,false);
  speaker.selectedIndex=1;
  vm.runInContext('checkSpeakerSelection()',context);
  assert.equal(hidden,true);
});

function quotaView() {
  const nodes = new Map();
  const document = {getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, {textContent:'',className:'',style:{},dataset:{},title:''});
    return nodes.get(id);
  }};
  const context = vm.createContext({window:{},document});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/api.js'),'utf8'), context);
  return {nodes,render:context.window.renderApiQuota};
}

test('unavailable quota never claims full capacity and clears a previous reading', () => {
  const {nodes,render}=quotaView();
  render({gemini:{tokens_limit:1000,tokens_remaining:850}});
  assert.equal(parseFloat(nodes.get('quotaPercentDisplay').textContent),85);
  render(null);
  assert.equal(nodes.get('quotaPercentDisplay').textContent,'Sin datos');
  assert.equal(nodes.get('mobileQuotaPercent').textContent,'Sin datos');
  assert.equal(nodes.get('quotaProgressBar').style.width,'0%');
  assert.equal(nodes.get('apiQuotaContainer').dataset.state,'unknown');
  assert.doesNotMatch(nodes.get('apiQuotaContainer').title,/85%|100%/);
});

test('compact quota distinguishes low capacity and exhausted capacity with text', () => {
  const {nodes,render}=quotaView();
  render({gemini:{tokens_limit:1000,tokens_remaining:100}});
  assert.match(nodes.get('quotaStatusSummary').textContent,/baja/i);
  assert.equal(nodes.get('apiQuotaContainer').dataset.state,'low');
  render({gemini:{tokens_limit:1000,tokens_remaining:0}});
  assert.equal(nodes.get('quotaPercentDisplay').textContent,'0%');
  assert.equal(nodes.get('apiQuotaContainer').dataset.state,'critical');
});

test('API setup warning belongs to Settings and does not require optional Drive', () => {
  const nodes = new Map();
  const document = {getElementById(id) {
    if (id==='apiOnboardingBanner') return null;
    if (!nodes.has(id)) nodes.set(id,{hidden:false,textContent:'',innerHTML:'',dataset:{},setAttribute(k,v){this[k]=v;}});
    return nodes.get(id);
  }};
  document.getElementById('settingsApiWarning');
  const context = vm.createContext({window:{},document,localStorage:{getItem(){return null;}}});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/api.js'),'utf8'),context);
  context.updateSystemStatusIndicator();
  assert.equal(nodes.get('settingsApiWarning').hidden,false);
  assert.match(nodes.get('btnSettingsSidebar').title,/Groq.*Gemini/);
  assert.equal(nodes.get('systemStatusContainer').innerHTML,'');
  vm.runInContext('serverHasGroq=true; serverHasGemini=true; isGoogleDriveConnected=false;',context);
  context.updateSystemStatusIndicator();
  assert.equal(nodes.get('settingsApiWarning').hidden,true);
});

test('quota stays quiet at normal capacity and shows the discounted audio estimate only at twenty percent or below', () => {
 const {nodes,render}=quotaView();
 render({gemini:{tokens_limit:1000,tokens_remaining:850}});
 assert.equal(nodes.get('quotaStatusSummary').hidden,true);
 assert.equal(nodes.get('quotaAudioEstimate').hidden,true);
 render({gemini:{tokens_limit:1000,tokens_remaining:200},audio_capacity:{seconds:7980,safety_margin_percent:5,samples:3}});
 assert.equal(nodes.get('quotaAudioEstimate').hidden,false);
 assert.match(nodes.get('quotaAudioEstimate').textContent,/2 h 13 min/);
 render({gemini:{tokens_limit:1000,tokens_remaining:100},audio_capacity:{seconds:null,samples:0}});
 assert.doesNotMatch(nodes.get('quotaAudioEstimate').textContent,/2 h|NaN|Infinity/);
 assert.match(nodes.get('quotaAudioEstimate').textContent,/historial/i);
});

test('quota requests select the origin, workspace and document format currently in use', async () => {
 const urls=[]; const nodes=new Map();
 const context=vm.createContext({window:{currentWorkspace:'work_and_study',currentActiveMainTab:'file'},localStorage:{getItem(){return null;}},document:{getElementById(id){if(id==='userGroqKeyInput'||id==='userGeminiKeyInput')return null;if(!nodes.has(id))nodes.set(id,{value:id==='workStudyDocumentFormat'?'executive':'',style:{},dataset:{}});return nodes.get(id);}},fetch:async url=>{urls.push(url);return {ok:true,json:async()=>({gemini:{tokens_limit:1000,tokens_remaining:850}})};}});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/api.js'),'utf8'),context);
 await context.window.fetchApiQuota();
 assert.match(urls[0],/source=file/);
 assert.match(urls[0],/workspace=work_and_study/);
 assert.match(urls[0],/document_format=executive/);
 context.window.currentWorkspace='dnd';context.window.currentActiveMainTab='youtube';
 await context.window.fetchApiQuota();
 assert.match(urls[1],/source=youtube/);
 assert.match(urls[1],/workspace=dnd/);
 assert.doesNotMatch(urls[1],/document_format/);
});

test('a delayed quota response cannot overwrite the estimate for a newer selection', async () => {
 const pending=[],nodes=new Map();
 const context=vm.createContext({window:{currentWorkspace:'dnd',currentActiveMainTab:'youtube'},localStorage:{getItem(){return null;}},document:{getElementById(id){if(id==='userGroqKeyInput'||id==='userGeminiKeyInput')return null;if(!nodes.has(id))nodes.set(id,{style:{},dataset:{}});return nodes.get(id);}},fetch:()=>new Promise(resolve=>pending.push(resolve))});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/api.js'),'utf8'),context);
 const first=context.window.fetchApiQuota();
 context.window.currentActiveMainTab='file';
 const second=context.window.fetchApiQuota();
 pending[1]({ok:true,json:async()=>({gemini:{tokens_limit:1000,tokens_remaining:200}})});await second;
 pending[0]({ok:true,json:async()=>({gemini:{tokens_limit:1000,tokens_remaining:800}})});await first;
 assert.equal(parseFloat(nodes.get('quotaPercentDisplay').textContent),20);
});
