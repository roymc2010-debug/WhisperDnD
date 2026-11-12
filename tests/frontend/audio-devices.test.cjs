const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function view(){
 const nodes=new Map();
 const makeSelect=()=>({value:'',options:[],_html:'',set innerHTML(s){this._html=s;this.options=[];this.value='';},get innerHTML(){return this._html;},appendChild(o){this.options.push(o);if(this.options.length===1)this.value=o.value;},replaceChildren(...options){this.options=[];options.forEach(o=>this.appendChild(o));}});
 for(const id of ['selectAudioMic','selectAudioSpeaker','deviceMicSettings','deviceSpeakerSettings'])nodes.set(id,makeSelect());
 for(const id of ['audioDevicesStatus','audioDevicesSettingsStatus'])nodes.set(id,{textContent:'',hidden:true,dataset:{}});
 const saved=new Map();
 const context=vm.createContext({window:{innerWidth:1280,addEventListener(){}},navigator:{userAgent:'Desktop',maxTouchPoints:0},console:{warn(){}},localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},document:{getElementById:id=>nodes.get(id)||null,addEventListener(){},createElement(){return {value:'',textContent:'',dataset:{},cloneNode(){return {...this,dataset:{...this.dataset}};}};}}});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/audio.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/app.js'),'utf8'),context);
 context.checkSpeakerSelection=()=>{};
 context.pollAudioLevel=()=>{};
 context.fetch=async()=>({ok:true,json:async()=>({microphones:[{id:'mic-a',name:'Micrófono A'},{id:'mic-b',name:'Micrófono B'}],speakers:[{id:'spk-a',name:'Salida A'}],default_mic_id:'mic-a',default_speaker_id:'spk-a'})});
 return {context,nodes,saved};
}

test('Settings receives the detected devices and shares selections with Audio',async()=>{
 const {context,nodes,saved}=view();
 await context.loadAudioDevices();
 assert.equal(nodes.get('deviceMicSettings').options.length,2);
 assert.equal(nodes.get('deviceSpeakerSettings').options.length,1);
 context.onSettingsMicChange('mic-b');
 assert.equal(nodes.get('selectAudioMic').value,'mic-b');
 assert.equal(saved.get('dnd_selected_mic'),'mic-b');
 nodes.get('selectAudioMic').value='mic-a';
 context.onAudioDeviceChange();
 assert.equal(nodes.get('deviceMicSettings').value,'mic-a');
});

test('a failed refresh preserves usable devices and gives an explicit error',async()=>{
 const {context,nodes}=view();
 await context.loadAudioDevices();
 context.fetch=async()=>{throw new Error('Sin respuesta del servidor');};
 await context.loadAudioDevices(true);
 assert.equal(nodes.get('selectAudioMic').options.length,2);
 assert.equal(nodes.get('deviceMicSettings').options.length,2);
 assert.equal(nodes.get('audioDevicesSettingsStatus').hidden,false);
 assert.match(nodes.get('audioDevicesSettingsStatus').textContent,/Sin respuesta/);
});
