const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../static/js/desktop-core.js');
test('all six accepted themes are available, with a safe persisted fallback', () => {
 assert.deepEqual(core.themes.map(t => t.id), ['copper','graphite','midnight','wine','paper','sky']);
 assert.equal(core.normalizeTheme('paper'), 'paper');
 assert.equal(core.normalizeTheme('<script>'), 'copper');
 assert.equal(core.normalizeTheme(null), 'copper');
});
test('re-record offers only actual unique positive session numbers', () => {
 assert.deepEqual(core.sessionNumbers({sessions:[{session_number:4},{session_number:'2'},{session_number:4},{session_number:0},{session_number:'oops'},{}]}),[2,4]);
 assert.deepEqual(core.sessionNumbers({last_session:9}),[]);
});
test('re-record rejects stale campaign, missing session and active recording', () => {
 const context={campaign:'Mesa A',selectedCampaign:'Mesa A',sessions:[2,4],session:2,recording:false};
 assert.equal(core.validateRerecord(context),'');
 assert.match(core.validateRerecord({...context,selectedCampaign:'Mesa B'}),/campaña/);
 assert.match(core.validateRerecord({...context,session:3}),/sesión/);
 assert.match(core.validateRerecord({...context,recording:true}),/grabación/);
});
