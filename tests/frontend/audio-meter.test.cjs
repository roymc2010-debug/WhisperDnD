const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function view(){
 const nodes=new Map();
 const ids=['meterMicBar','meterMicValue','meterSpkBar','meterSpkValue','meterActivityDot','meterStatusHint','meterStatusHintSettings','meterMicBarSettings','meterMicValSettings','meterSpkBarSettings','meterSpkValSettings','discordLiveStatusText'];
 for(const id of ids)nodes.set(id,{style:{},textContent:'En espera',className:''});
 const context=vm.createContext({window:{innerWidth:1280,currentLiveMode:'roleplay'},navigator:{userAgent:'Desktop',maxTouchPoints:0},localStorage:{getItem(){return null;}},document:{getElementById:id=>nodes.get(id)||null}});
 vm.runInContext(fs.readFileSync(require.resolve('../../static/js/audio.js'),'utf8'),context);
 return {context,nodes};
}

test('a valid microphone and Discord reading updates both screens and the overall activity status',()=>{
 const {context,nodes}=view();
 context.updateVuMeter(.03,.04,{discord_status:{discord_detected:true,is_capturing:true,status_message:'Discord activo'}});
 assert.match(nodes.get('meterStatusHint').textContent,/detectada/);
 assert.match(nodes.get('meterStatusHintSettings').textContent,/detectada/);
 assert.equal(nodes.get('meterMicBarSettings').style.width,nodes.get('meterMicBar').style.width);
 assert.equal(nodes.get('meterSpkBarSettings').style.width,nodes.get('meterSpkBar').style.width);
 assert.notEqual(nodes.get('meterMicValSettings').textContent,'En espera');
 assert.match(nodes.get('discordLiveStatusText').textContent,/Discord activo/);
});

test('an overlapping sample is reported as busy instead of clearing both channels to silence',async()=>{
 const {context,nodes}=view();
 nodes.set('tabLiveContent',{classList:{contains(){return false;}}});
 nodes.set('btnStopRecording',{disabled:true});
 context.URLSearchParams=URLSearchParams;
 context.updateVuMeter(.03,.04,{});
 const width=nodes.get('meterMicBar').style.width;
 context.fetch=async()=>({ok:true,json:async()=>({meter_busy:true,mic_rms:0,speaker_rms:0,is_recording:false})});
 await context.pollAudioLevel();
 assert.equal(nodes.get('meterMicBar').style.width,width);
 assert.match(nodes.get('meterStatusHint').textContent,/ocupado|esperando/i);
});
