const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function view(fetch) {
  const button = {disabled:false, textContent:'Descargar reporte de errores'};
  const status = {textContent:''};
  const links = [], revoked = [];
  const context = vm.createContext({fetch, AbortController, setTimeout:(fn,ms)=>ms===1000?(fn(),0):setTimeout(fn,ms), clearTimeout,
    document: {
      getElementById: id => id === 'btnDownloadSupportReport' ? button : status,
      createElement: () => { const a = {click(){this.clicked=true;},remove(){this.removed=true;}}; links.push(a); return a; },
      body: {appendChild(){}}
    }, URL: {createObjectURL: ()=>'blob:local-report', revokeObjectURL:u=>revoked.push(u)}});
  vm.runInContext(fs.readFileSync('static/js/support-report.js', 'utf8'), context);
  return {context,button,status,links,revoked};
}

test('download uses no keys or session payload and releases its local URL', async()=>{
  const calls=[];
  const v=view(async(...args)=>{calls.push(args);return {ok:true,headers:{get:()=> 'text/plain; charset=utf-8'},blob:async()=>({})};});
  await v.context.downloadSupportReport();
  assert.equal(calls.length,1);
  assert.equal(calls[0][0],'/api/support/report');
  assert.equal(calls[0][1].headers,undefined);
  assert.equal(calls[0][1].body,undefined);
  assert.equal(v.links[0].download,'WhisperDnD-reporte-errores.txt');
  assert.equal(v.links[0].clicked,true);
  assert.equal(v.links[0].removed,true);
  assert.deepEqual(v.revoked,['blob:local-report']);
  assert.equal(v.button.disabled,false);
  assert.match(v.status.textContent,/no se envió/i);
});

test('failed download restores the button and does not print a server response', async()=>{
  const v=view(async()=>({ok:false,status:500,text:async()=> 'secret-token'}));
  await v.context.downloadSupportReport();
  assert.equal(v.links.length,0);
  assert.equal(v.button.disabled,false);
  assert.match(v.status.textContent,/intentar/i);
  assert.doesNotMatch(v.status.textContent,/secret-token/);
});

test('double activation does not start concurrent downloads', async()=>{
  let resolve, calls=0;
  const v=view(()=>{calls++;return new Promise(r=>{resolve=r;});});
  const first=v.context.downloadSupportReport();
  await v.context.downloadSupportReport();
  assert.equal(calls,1);
  resolve({ok:false});
  await first;
  assert.equal(v.button.disabled,false);
});
