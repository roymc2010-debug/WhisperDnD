const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function node() {
  return {
    value: '', textContent: '', style: {}, options: [],
    classList: { add() {}, remove() {}, contains() { return false; } },
    set innerHTML(value) { this.html = value; this.options = []; },
    get innerHTML() { return this.html || ''; },
    appendChild(child) { this.options.push(child); },
  };
}

function campaignView(fetch) {
  const nodes = new Map(['campaignSelect', 'campaignManagerModal',
    'campaignManagerList', 'campaignManagerCount', 'wikiCampaignSelect',
    'wikiSessionsCounter'].map(id => [id, node()]));
  const context = vm.createContext({
    document: { getElementById: id => nodes.get(id) || null,
      createElement: node, querySelector() { return null; }, addEventListener() {} },
    localStorage: { getItem() { return null; }, setItem() {} },
    addEventListener() {}, console: { warn() {}, error() {} }, fetch,
    escapeHtml: String,
  });
  context.window = context;
  for (const script of ['app', 'wiki']) {
    vm.runInContext(fs.readFileSync(require.resolve(`../../static/js/${script}.js`), 'utf8'), context);
  }
  return { context, nodes };
}

test('recording selector and saved campaigns display the same API campaigns', async () => {
  const { context, nodes } = campaignView(async () => ({ ok: true,
    json: async () => [{ name: 'Candlekeep 2.0', sessions_count: 4 }] }));
  await context.toggleCampaignManagerModal(true);
  assert.ok(nodes.get('campaignSelect').options.some(o => o.value === 'Candlekeep 2.0'));
  assert.equal(nodes.get('campaignManagerCount').textContent, '1 campaña guardada');
  assert.match(nodes.get('campaignManagerList').options[0].innerHTML, /Candlekeep 2.0/);
});

for (const [name, fetch] of [
  ['HTTP failure', async () => ({ ok: false, status: 503 })],
  ['network failure', async () => { throw new Error('offline'); }],
  ['malformed response', async () => ({ ok: true, json: async () => ({ unexpected: true }) })],
]) {
  test(`${name} does not report zero saved campaigns`, async () => {
    const { context, nodes } = campaignView(fetch);
    await context.toggleCampaignManagerModal(true);
    assert.doesNotMatch(nodes.get('campaignManagerCount').textContent, /^0 /);
    assert.match(nodes.get('campaignManagerList').innerHTML, /No se pudieron cargar/);
  });
}

test('processing session 4 reloads the open Wiki content, not just its campaign selector', async () => {
  const fresh = { campaign_name: 'Candlekeep 2.0', last_session: 4,
    sessions: [1, 2, 3, 4].map(session_number => ({ session_number })) };
  const { context, nodes } = campaignView(async url => ({ ok: true, json: async () =>
    url === '/api/campaigns' ? [{ name: 'Candlekeep 2.0', sessions_count: 4 }] : { campaign_state: fresh } }));
  nodes.get('wikiCampaignSelect').value = 'Candlekeep 2.0';
  context.currentWikiCampaignState = { ...fresh, sessions: fresh.sessions.slice(0, 3) };
  // Result-panel renderers are unrelated to the Wiki's independently loaded state.
  context.syncResultTabsForWorkspace = () => {};
  context.updateCampaignViewTabs = () => {};
  context.toggleResultTab = () => {};
  context.displayResults({ campaign_name: 'Candlekeep 2.0', session_number: 4, campaign_state: fresh });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.currentWikiCampaignState.sessions.length, 4);
  assert.equal(nodes.get('wikiSessionsCounter').textContent, 4);
});

test('a saved session with export problems remains visible and shows a warning', () => {
  const { context } = campaignView(async () => ({ ok: true, json: async () => [] }));
  const notices = [];
  context.showFloatingToast = (text, severity) => notices.push({ text, severity });
  context.syncResultTabsForWorkspace = () => {};
  context.updateCampaignViewTabs = () => {};
  context.toggleResultTab = () => {};
  context.displayResults({ campaign_name: 'Mesa', session_number: 1,
    campaign_state: { campaign_name: 'Mesa', last_session: 1, sessions: [{ session_number: 1 }] },
    processing_warnings: ['La sesión se guardó, pero no se pudo generar el archivo DOCX.'] });
  assert.equal(context.currentResult.campaign_state.sessions.length, 1);
  assert.deepEqual(notices, [{ text: 'La sesión se guardó, pero no se pudo generar el archivo DOCX.', severity: 'warning' }]);
});

for (const exists of [true, false]) {
  test(`loading a ${exists ? 'saved' : 'new'} recording campaign preserves the independent Wiki session selection`, async () => {
    const { context, nodes } = campaignView(async () => ({ ok: exists,
      json: async () => ({ campaign_state: { campaign_name: 'Otra mesa', last_session: 1,
        sessions: [{ session_number: 1, title: 'Otra aventura' }] } }) }));
    nodes.set('campaignNameInput', { value: 'Otra mesa' });
    nodes.set('wikiSessionExportSelect', node());
    nodes.get('wikiCampaignSelect').value = 'Candlekeep 2.0';
    context.updateCampaignViewTabs = () => {};
    context.populateWikiSessionExportDropdown([{ session_number: 5, title: 'Mi sesión elegida' }], 5);
    const before = nodes.get('wikiSessionExportSelect').innerHTML;
    await context.loadCurrentCampaign();
    assert.equal(nodes.get('wikiSessionExportSelect').innerHTML, before);
    assert.equal(nodes.get('wikiSessionExportSelect').value, '5');
  });
}
