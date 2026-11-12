const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('legacy coaching without a character never invents a personal identity in the Wiki',()=>{
  const output={innerHTML:''};
  const context=vm.createContext({window:{},document:{getElementById:id=>id==='grimorio-content'?output:null},renderMarkdownWithKaTeX:text=>text});
  vm.runInContext(fs.readFileSync(require.resolve('../../static/js/wiki.js'),'utf8'),context);
  const state={campaign_name:'Mesa',sessions:[{session_number:1,title:'Puerta',markus_coaching:'Reflexión pendiente de identificar.'}]};
  context.renderJournal(state);
  assert.ok(!output.innerHTML.includes('Markus'));
  assert.match(output.innerHTML,/Personaje sin identificar/);
  assert.match(output.innerHTML,/Reflexión pendiente/);
  state.sessions[0].user_character={character_name:'Arin'};
  context.renderJournal(state);
  assert.match(output.innerHTML,/Reflexión de Rol y Compañerismo: Arin/);
});
