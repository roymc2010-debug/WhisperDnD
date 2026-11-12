const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const campaign = (name, character) => ({ campaign_name: name, last_session: 2, sessions: [],
  dm_name: `DM ${name}`, roster: [
    { player_name: `DM ${name}`, character_name: '(DM)', role: 'Dungeon Master (DM)' },
    { player_name: `Jugador ${name}`, character_name: character, role: 'Guerrero', is_user_character: true },
  ] });
const response = state => ({ ok: true, status: 200, json: async () => ({ campaign_state: state }) });
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }

function appView() {
  const makeNode = () => ({ value: '', textContent: '', disabled: false, inert: false, attrs: {}, dataset: {},
    classList: { add() {}, remove() {} }, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute() {}, focus() {} });
  const nodes = new Map(['campaignNameInput', 'campaignLastSessionBadge', 'sessionNumberInput',
    'rosterFullCard', 'saveStatusBadge'].map(id => [id, makeNode()]));
  nodes.get('campaignNameInput').value = 'A';
  const requests = [], timers = new Map(), notices = [];
  let fetchGET = async () => response(campaign('A', 'Alba')), timerId = 0;
  const ctx = vm.createContext({
    document: { getElementById: id => nodes.get(id) || null, querySelector: () => null, addEventListener() {} },
    localStorage: { getItem: key => key === 'audio_source_mode' ? 'pc_host' : null, setItem() {} },
    navigator: { userAgent: 'Desktop', maxTouchPoints: 0 },
    addEventListener() {}, console: { warn() {}, error() {} },
    setTimeout: fn => { const id = ++timerId; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id), clearInterval() {}, AbortController,
    fetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || 'GET', body: options.body });
      return options.method === 'POST' ? { ok: true, json: async () => ({}) } : fetchGET(url);
    },
  });
  ctx.window = ctx;
  for (const name of ['app', 'roster', 'audio']) vm.runInContext(
    fs.readFileSync(require.resolve(`../../static/js/${name}.js`), 'utf8'), ctx);
  ctx.updateCampaignViewTabs = () => {};
  ctx.showAlert = text => notices.push(text);
  ctx.showFloatingToast = text => notices.push(text);
  ctx.generateTaskId = () => 'synthetic-task';
  return { ctx, nodes, requests, notices,
    select: name => { nodes.get('campaignNameInput').value = name; },
    respond: fn => { fetchGET = fn; },
    read: () => JSON.parse(JSON.stringify(ctx.gatherRosterData())),
    flush: async () => { for (const [id, fn] of [...timers]) { timers.delete(id); await fn(); } },
  };
}

for (const failure of ['HTTP 503', 'network', 'invalid JSON', 'invalid state']) {
  test(`same-campaign reload preserves the entire group on ${failure} and refuses writes`, async () => {
    const app = appView();
    await app.ctx.loadCurrentCampaign();
    const before = app.read();
    app.respond(async () => {
      if (failure === 'network') throw Error('offline');
      if (failure === 'HTTP 503') return { ok: false, status: 503 };
      return { ok: true, status: 200, json: async () => {
        if (failure === 'invalid JSON') throw SyntaxError('invalid JSON');
        return { unexpected: true };
      } };
    });
    await app.ctx.onCampaignChange();
    assert.deepEqual(app.read(), before);
    assert.match(app.nodes.get('campaignLastSessionBadge').textContent, /No se pudo cargar/);
    assert.doesNotMatch(app.nodes.get('campaignLastSessionBadge').textContent, /Nueva Campaña/);
    assert.equal(app.nodes.get('rosterFullCard').attrs['aria-busy'], 'false');
    assert.equal(await app.ctx.saveRoster(), false);
    assert.equal(app.requests.filter(r => r.method === 'POST').length, 0);
  });
}

test('a campaign change loads once rather than racing two separate roster requests', async () => {
  const app = appView();
  await app.ctx.onCampaignChange();
  assert.equal(app.requests.length, 1);
  assert.deepEqual(app.read().map(r => r.character_name), ['(DM)', 'Alba']);
});

test('a failed switch cannot save the previous group under the new campaign', async () => {
  const app = appView(); await app.ctx.loadCurrentCampaign();
  app.select('B'); app.respond(async () => ({ ok: false, status: 503 }));
  await app.ctx.onCampaignChange();
  assert(!app.read().some(r => r.character_name === 'Alba'));
  assert.equal(await app.ctx.saveRoster(), false);
  assert.equal(app.requests.filter(r => r.method === 'POST').length, 0);
});

test('neither a manual nor a queued save writes while another campaign is loading', async () => {
  const app = appView(); await app.ctx.loadCurrentCampaign();
  app.ctx.saveCurrentRoster();
  app.select('B'); const delayed = deferred(); app.respond(() => delayed.promise);
  const loading = app.ctx.onCampaignChange();
  await app.flush();
  const saved = await app.ctx.saveRoster();
  delayed.resolve(response(campaign('B', 'Brisa'))); await loading;
  assert.equal(saved, false);
  assert.equal(app.requests.filter(r => r.method === 'POST').length, 0);
  assert.deepEqual(app.read().map(r => r.character_name), ['(DM)', 'Brisa']);
});

for (const lateStage of ['HTTP response', 'JSON body']) {
  test(`a stale ${lateStage} cannot overwrite the latest campaign`, async () => {
    const app = appView(), delayed = deferred();
    app.respond(() => lateStage === 'HTTP response' ? delayed.promise :
      Promise.resolve({ ok: true, status: 200, json: () => delayed.promise }));
    const old = app.ctx.loadCurrentCampaign();
    await Promise.resolve(); await Promise.resolve();
    app.select('B'); app.respond(async () => response(campaign('B', 'Brisa')));
    await app.ctx.onCampaignChange();
    delayed.resolve(lateStage === 'HTTP response' ? response(campaign('A', 'Alba')) : { campaign_state: campaign('A', 'Alba') });
    await old;
    assert.deepEqual(app.read().map(r => r.character_name), ['(DM)', 'Brisa']);
    assert.equal(app.ctx.currentCampaignState.campaign_name, 'B');
    assert.equal(app.nodes.get('rosterFullCard').inert, false);
  });
}

test('the standalone roster loader cannot paint a campaign that is no longer selected', async () => {
  const app = appView(), delayed = deferred(); app.respond(() => delayed.promise);
  const old = app.ctx.loadCampaignRoster('A');
  app.select('B'); app.respond(async () => response(campaign('B', 'Brisa')));
  await app.ctx.loadCurrentCampaign();
  delayed.resolve(response(campaign('A', 'Alba'))); await old;
  assert.deepEqual(app.read().map(r => r.character_name), ['(DM)', 'Brisa']);
});

test('retrying after failure restores editing and saves only the recovered group', async () => {
  const app = appView(); app.respond(async () => ({ ok: false, status: 503 }));
  await app.ctx.onCampaignChange();
  assert.equal(await app.ctx.saveRoster(), false);
  app.respond(async () => response(campaign('A', 'Alba')));
  await app.ctx.loadCurrentCampaign();
  assert.equal(app.nodes.get('rosterFullCard').inert, false);
  assert.equal(await app.ctx.saveRoster(), true);
  const post = app.requests.find(r => r.method === 'POST');
  assert.equal(JSON.parse(post.body).campaign_name, 'A');
  assert.equal(JSON.parse(post.body).roster[1].character_name, 'Alba');
});

test('a confirmed 404 for a new campaign permits configuring its blank group', async () => {
  const app = appView(); await app.ctx.loadCurrentCampaign();
  app.select('Nueva'); app.respond(async () => ({ ok: false, status: 404 }));
  await app.ctx.onCampaignChange();
  assert.deepEqual(app.read().map(r => r.character_name), ['(DM)']);
  assert.equal(await app.ctx.saveRoster(), true);
  assert.equal(JSON.parse(app.requests.find(r => r.method === 'POST').body).campaign_name, 'Nueva');
});

test('a 404 for a known campaign is an error rather than permission to overwrite it', async () => {
  const app = appView(); await app.ctx.loadCurrentCampaign();
  const before = app.read(); app.ctx.knownCampaigns = { a: { last_session: 2 } };
  app.respond(async () => ({ ok: false, status: 404 })); await app.ctx.onCampaignChange();
  assert.deepEqual(app.read(), before);
  assert.equal(await app.ctx.saveRoster(), false);
});

test('a newly saved group is not treated as nonexistent on a later 404', async () => {
  const app = appView(); app.respond(async () => ({ ok: false, status: 404 }));
  await app.ctx.loadCurrentCampaign();
  app.ctx.addPlayerRow();
  assert.equal(await app.ctx.saveRoster(), true);
  const before = app.read();
  await app.ctx.loadCurrentCampaign();
  assert.deepEqual(app.read(), before);
  assert.equal(await app.ctx.saveRoster(), false);
  assert.equal(app.requests.filter(r => r.method === 'POST').length, 1);
});

test('a response naming another campaign cannot authorize saving its roster', async () => {
  const app = appView(); await app.ctx.loadCurrentCampaign();
  const before = app.read();
  app.respond(async () => response(campaign('B', 'Brisa')));
  await app.ctx.loadCurrentCampaign();
  assert.deepEqual(app.read(), before);
  assert.equal(await app.ctx.saveRoster(), false);
});

test('a late failed request cannot disable a newer successful load of the same campaign', async () => {
  const app = appView(), delayed = deferred(); app.respond(() => delayed.promise);
  const old = app.ctx.loadCurrentCampaign();
  app.respond(async () => response(campaign('A', 'Alba')));
  await app.ctx.loadCurrentCampaign();
  delayed.resolve({ ok: false, status: 503 }); await old;
  assert.deepEqual(app.read().map(r => r.character_name), ['(DM)', 'Alba']);
  assert.equal(app.nodes.get('rosterFullCard').inert, false);
  assert.equal(await app.ctx.saveRoster(), true);
});

test('a loaded DM with Discord remains usable when the roster table is present', async () => {
  const app = appView(), saved = campaign('A', 'Alba');
  saved.dm_discord_user_id = 'dm-a';
  saved.roster[0].discord_user_id = 'dm-a';
  const input = { value: '' }, select = { value: '', innerHTML: '' };
  app.ctx.document.querySelector = () => ({ querySelector: selector =>
    selector === '.player-name' ? input : select });
  app.respond(async () => response(saved));
  assert.equal(await app.ctx.loadCurrentCampaign(), true);
  assert.equal(await app.ctx.saveRoster(), true);
  const body = JSON.parse(app.requests.find(r => r.method === 'POST').body);
  assert.equal(body.roster[0].discord_user_id, 'dm-a');
});

test('failed campaign loading blocks recording and processing before any action request', async () => {
  const app = appView(); app.respond(async () => ({ ok: false, status: 503 }));
  await app.ctx.onCampaignChange();
  let quotaChecks = 0;
  app.ctx.checkQuotaBeforeAction = async () => { quotaChecks++; return false; };
  app.nodes.set('youtubeUrl', { value: 'https://example.invalid/video' });
  app.ctx.selectedLocalRecordingFilename = 'synthetic.wav';
  const actions = ['startSessionRecording', 'stopSessionAndProcess', 'transcribeYoutube', 'transcribeFile'];
  for (const action of actions) await app.ctx[action]();
  assert.equal(app.requests.filter(r => r.method === 'POST').length, 0);
  assert.equal(quotaChecks, 0);
  assert(app.notices.length > 0);
});
