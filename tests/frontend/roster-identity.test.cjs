const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const officialRoster = [
  { player_name: 'Directora', character_name: '(DM)', role: 'Dungeon Master (DM)', discord_user_id: 'dm-123' },
  { player_name: 'Jugador', character_name: 'Aldren', role: 'Guerrero', subclass: 'Battle Master',
    species: 'Humano', discord_user_id: 'pc-456', is_user_character: true,
    ui_class_config: {
      primary: { classId: 'fighter', subclassId: 'champ', isCustom: true, customText: 'Clase personal' },
      secondary: { active: true, classId: 'warlock', subclassId: 'hexblade', isCustom: true, customText: 'Pacto personal' },
    } },
];
const state = { campaign_name: 'Mesa sintética', last_session: 5, sessions: [],
  dm_name: 'Directora', dm_discord_user_id: 'dm-123', roster: officialRoster.slice(1) };

function rosterView(campaignState = state) {
  const posts = [], timers = new Map(), storage = new Map();
  let nextTimer = 0;
  const context = vm.createContext({
    document: {
      getElementById: id => id === 'campaignNameInput' ? { value: 'Mesa sintética' } : null,
      querySelector: () => null, addEventListener() {},
    },
    localStorage: { getItem() { return null; }, setItem() {} },
    sessionStorage: { getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    setTimeout: fn => { const id = ++nextTimer; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id),
    addEventListener() {}, console: { warn() {}, error() {} },
    fetch: async (url, options = {}) => {
      if (options.method === 'POST') posts.push(JSON.parse(options.body));
      return { ok: true, json: async () => ({ campaign_state: campaignState }) };
    },
  });
  context.window = context;
  for (const script of ['app', 'roster']) {
    vm.runInContext(fs.readFileSync(require.resolve(`../../static/js/${script}.js`), 'utf8'), context);
  }
  // Result-tab styling and campaign-list refresh are independent from roster writes.
  context.syncResultTabsForWorkspace = () => {};
  context.updateCampaignViewTabs = () => {};
  context.toggleResultTab = () => {};
  context.loadCampaignList = async () => {};
  const read = () => JSON.parse(JSON.stringify(context.getRosterFromTable(true)));
  const flushTimers = async () => {
    for (const [id, fn] of [...timers]) { timers.delete(id); await fn(); }
  };
  return { context, posts, storage, read, flushTimers };
}

test('a roster without a DM preserves its first player as a character', () => {
  const { context, read } = rosterView();
  context.renderRosterTable(officialRoster.slice(1));
  const rows = read();
  assert.equal(rows.length, 2);
  assert.equal(rows[0].character_name, '(DM)');
  assert.notEqual(rows[0].player_name, 'Jugador');
  assert.equal(rows[1].character_name, 'Aldren');
  assert.equal(rows[1].is_user_character, true);
  assert.equal(rows[1].discord_user_id, 'pc-456');
  assert.equal(rows[1].ui_class_config.secondary.customText, 'Pacto personal');
});

test('an explicit DM below a player becomes the only first DM without losing the player', () => {
  const { context, read } = rosterView();
  context.renderRosterTable([officialRoster[1], officialRoster[0]]);
  const rows = read();
  assert.equal(rows.filter(r => r.character_name === '(DM)').length, 1);
  assert.equal(rows[0].player_name, 'Directora');
  assert.equal(rows[1].character_name, 'Aldren');
  assert.equal(rows[1].is_user_character, true);
  assert.equal(rows[1].ui_class_config.primary.customText, 'Clase personal');
});

test('an existing DM-first roster keeps both identities and class configuration', () => {
  const { context, read } = rosterView();
  context.renderRosterTable(officialRoster);
  const rows = read();
  assert.deepEqual(rows.map(r => [r.player_name, r.character_name, r.discord_user_id, r.is_user_character]),
    [['Directora', '(DM)', 'dm-123', false], ['Jugador', 'Aldren', 'pc-456', true]]);
  assert.deepEqual(rows[1].ui_class_config, officialRoster[1].ui_class_config);
});

for (const loader of ['loadCampaignRoster', 'loadCurrentCampaign']) {
  test(`${loader} uses saved DM metadata when the roster contains only PCs`, async () => {
    const { context, read, posts } = rosterView();
    await context[loader]('Mesa sintética');
    assert.deepEqual(read().map(r => [r.player_name, r.character_name, r.discord_user_id]),
      [['Directora', '(DM)', 'dm-123'], ['Jugador', 'Aldren', 'pc-456']]);
    assert.equal(posts.length, 0, 'loading must not save a campaign');
    await context.saveRoster();
    assert.equal(posts[0].dm_name, 'Directora');
    assert.equal(posts[0].roster[1].is_user_character, true);
    assert.equal(posts[0].roster[1].ui_class_config.secondary.customText, 'Pacto personal');
  });
}

test('loading an empty group uses its own saved DM instead of retaining the previous group', async () => {
  const { context, read, posts } = rosterView({ ...state, roster: [] });
  context.renderRosterTable(officialRoster);
  await context.loadCampaignRoster('Mesa sintética');
  assert.deepEqual(read().map(r => [r.player_name, r.character_name, r.discord_user_id]),
    [['Directora', '(DM)', 'dm-123']]);
  assert.equal(posts.length, 0);
});

test('missing DM metadata is filled on the actual DM without mutating saved character rows', async () => {
  const campaign = { ...state, roster: [officialRoster[1],
    { player_name: '', character_name: '(DM)', role: 'Dungeon Master (DM)' }] };
  const original = JSON.stringify(campaign);
  const { context, read } = rosterView(campaign);
  await context.loadCampaignRoster('Mesa sintética');
  assert.deepEqual(read().map(r => [r.player_name, r.character_name, r.discord_user_id]),
    [['Directora', '(DM)', 'dm-123'], ['Jugador', 'Aldren', 'pc-456']]);
  assert.equal(JSON.stringify(campaign), original);
});

for (const field of ['detected_pcs', 'detected_party']) {
  test(`displaying ${field} does not replace or automatically save the official group`, async () => {
    const { context, read, posts, flushTimers } = rosterView();
    context.renderRosterTable(officialRoster);
    const before = read();
    context.displayResults({ campaign_name: 'Mesa sintética', session_number: 5,
      [field]: [{ jugador: 'Jugador', personaje: 'Aldren', clase: 'Guerrero' }] });
    await flushTimers();
    assert.deepEqual(posts, [], 'showing a result must never write a detected group');
    assert.deepEqual(read(), before);
  });
}

test('restoring cached results cannot replace a manually repaired group', async () => {
  const { context, storage, read, posts, flushTimers } = rosterView();
  context.renderRosterTable(officialRoster);
  const before = read();
  storage.set('whisper_last_result_dnd', JSON.stringify({ campaign_name: 'Mesa sintética',
    chronicle: 'Resultado de prueba', detected_pcs: [{ jugador: 'Jugador', personaje: 'Aldren' }] }));
  assert.equal(context.restoreLastResultForWorkspace('dnd'), true);
  await flushTimers();
  assert.deepEqual(posts, []);
  assert.deepEqual(read(), before);
});
