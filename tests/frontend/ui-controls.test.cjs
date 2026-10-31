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
  assert.match(nodes.get('quotaStatusSummary').textContent,/Baja/);
  assert.equal(nodes.get('apiQuotaContainer').dataset.state,'low');
  render({gemini:{tokens_limit:1000,tokens_remaining:0}});
  assert.equal(nodes.get('quotaPercentDisplay').textContent,'0%');
  assert.equal(nodes.get('apiQuotaContainer').dataset.state,'critical');
});
