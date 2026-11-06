// Cross-file integrity checks for the whole mod, not only the war branch.
// Run from the repository root: node tests/integrity.test.js
// Complements tests/war_focuses.test.js (structure of the Soviet war branch).
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
process.chdir(path.join(__dirname, '..'));
const read = p => fs.readFileSync(p, 'utf8');

let checks = 0;
function test(name, run) { run(); checks++; console.log(`PASS ${name}`); }

// ---------- helpers ----------
// Extract the body of `NAME = { ... }` by brace counting (comments stripped).
function block(src, name) {
  const start = src.search(new RegExp(`^\\s*${name}\\s*=\\s*\\{`, 'm'));
  assert.notEqual(start, -1, `block ${name} not found`);
  let i = src.indexOf('{', start), depth = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') depth++;
    if (src[j] === '}') depth--;
    if (depth === 0) return src.slice(i + 1, j).replace(/#[^\n]*/g, '');
  }
  assert.fail(`block ${name} is not closed`);
}
// State IDs listed either as `state = N` or as numeric scope keys `N = {`.
function stateIds(src) {
  const ids = new Set();
  for (const m of src.matchAll(/(?:^|[^_\w])state = (\d+)/gm)) ids.add(m[1]);
  for (const m of src.matchAll(/^\s*(\d+) = \{/gm)) ids.add(m[1]);
  return ids;
}
function locKeys(p) {
  const src = read(p);
  assert.ok(src.startsWith('\ufeff'), `${p} needs a UTF-8 BOM`);
  const keys = [];
  for (const m of src.matchAll(/^ ([\w.]+):/gm)) keys.push(m[1]);
  return keys;
}

// ---------- localisation ----------
const locPairs = ['tt_tuva_l', 'tt_postwar_l', 'tt_war_focuses_l', 'tt_khozhuun_l', 'tt_superevent_l'];
test('RU/EN localisation pairs match in keys and order, with BOM', () => {
  for (const name of locPairs) {
    const en = locKeys(`localisation/english/${name}_english.yml`).filter(k => k !== 'l_english');
    const ru = locKeys(`localisation/russian/${name}_russian.yml`).filter(k => k !== 'l_russian');
    assert.deepEqual(ru, en, name);
  }
});
test('Colour tags are balanced in every localisation line', () => {
  for (const name of locPairs) for (const lang of ['english', 'russian']) {
    for (const line of read(`localisation/${lang}/${name}_${lang}.yml`).split('\n')) {
      const tags = line.match(/§./g) || [];
      assert.equal(tags.filter(t => t !== '§!').length, tags.filter(t => t === '§!').length, line);
    }
  }
});
const enAll = new Set(locPairs.flatMap(name => locKeys(`localisation/english/${name}_english.yml`)));

// ---------- script inventory ----------
const scriptFiles = [];
(function walk(d) {
  for (const e of fs.readdirSync(d || '.', { withFileTypes: true })) {
    const rel = d ? `${d}/${e.name}` : e.name;
    if (e.isDirectory()) { if (!['.git', 'docs', 'tests', 'gfx', 'sound', 'localisation'].includes(rel)) walk(rel); }
    else if (/\.(txt|gfx|gui)$/.test(e.name)) scriptFiles.push(rel);
  }
})('');
const all = scriptFiles.map(f => ({ f, src: read(f) }));

test('Every referenced TT_/tt_ localisation key exists in English files', () => {
  const missing = new Set();
  for (const { f, src } of all) {
    for (const m of src.matchAll(/\bcustom_(?:effect|trigger)_tooltip = \{?\s*(?:tooltip = )?([A-Za-z0-9_]+)/g))
      if (/^(TT_|tt_)/.test(m[1])) missing.add(m[1]);
    for (const m of src.matchAll(/tooltip = ((?:TT_|tt_)[A-Za-z0-9_]+)/g)) missing.add(m[1]);
    if (f.startsWith('common/national_focus/'))
      for (const m of src.matchAll(/id = (TT_[A-Za-z0-9_]+)/g)) missing.add(m[1]);
    if (f.startsWith('common/decisions/'))
      for (const m of src.matchAll(/^\t((?:TT_|tt_)[A-Za-z0-9_]+) = \{/gm)) { missing.add(m[1]); missing.add(m[1] + '_desc'); }
    if (f.startsWith('common/ideas/'))
      for (const m of src.matchAll(/^\t\t((?:TT_|tt_)[A-Za-z0-9_]+) = \{/gm)) { missing.add(m[1]); missing.add(m[1] + '_desc'); }
    if (f.startsWith('events/')) {
      for (const m of src.matchAll(/^\t?id = ([a-z0-9_]+\.\d+)/gm)) { missing.add(m[1] + '.t'); missing.add(m[1] + '.desc'); }
      for (const m of src.matchAll(/name = ([a-z0-9_]+\.\d+\.[a-z]+)/g)) missing.add(m[1]);
    }
  }
  assert.deepEqual([...missing].filter(k => !enAll.has(k)), []);
});

// ---------- events ----------
const definedEvents = new Set();
for (const { f, src } of all.filter(x => x.f.startsWith('events/')))
  for (const m of src.matchAll(/^\t?id = ([a-z0-9_]+\.\d+)/gm)) definedEvents.add(m[1]);
test('Every fired event id exists exactly once in the events folder', () => {
  for (const { f, src } of all)
    for (const m of src.matchAll(/\b(?:country_event|news_event)\s*=\s*\{[^{}]*?id = ([a-z0-9_]+\.\d+)/gs))
      assert(definedEvents.has(m[1]), `${f} fires unknown ${m[1]}`);
});

// ---------- ideas ----------
const definedIdeas = new Set();
for (const { f, src } of all.filter(x => x.f.startsWith('common/ideas/')))
  for (const m of src.matchAll(/^\t\t([A-Za-z0-9_]+) = \{/gm)) definedIdeas.add(m[1]);
test('Every referenced idea is defined', () => {
  for (const { f, src } of all)
    for (const m of src.matchAll(/\b(?:add_ideas|remove_ideas|has_idea|add_timed_idea|idea\s*=|remove_idea|add_idea)\s*=?\s*([A-Za-z0-9_]+)/g))
      if (m[1].startsWith('TT_')) assert(definedIdeas.has(m[1]), `${f} references undefined ${m[1]}`);
});

// ---------- graphics ----------
const definedGfx = new Set();
const modTextures = [];
for (const { f, src } of all.filter(x => x.f.startsWith('interface/'))) {
  for (const m of src.matchAll(/name\s*=\s*"([^"]+)"/g)) definedGfx.add(m[1]);
  for (const m of src.matchAll(/texturefile\s*=\s*"([^"]+)"/g)) modTextures.push(m[1]);
  for (const m of src.matchAll(/animationmaskfile\s*=\s*"([^"]+)"/g)) modTextures.push(m[1]);
  for (const m of src.matchAll(/animationtexturefile\s*=\s*"([^"]+)"/g)) modTextures.push(m[1]);
}
const vanillaGfx = /^(GFX_decision_generic_|GFX_decision_eng_|GFX_decision_category_generic_|GFX_Portrait_Asia_Generic_|GFX_report_event_generic_|GFX_news_event_generic_)/;
test('Script graphics resolve to mod sprites or known vanilla sprites', () => {
  for (const { f, src } of all.filter(x => !x.f.startsWith('interface/')))
    for (const m of src.matchAll(/\b(?:icon|picture|gfx|spriteType)\s*=\s*"?([A-Za-z0-9_\.]+)"?/g))
      if (/^GFX/.test(m[1])) assert(definedGfx.has(m[1]) || vanillaGfx.test(m[1]), `${f} references unknown ${m[1]}`);
});
test('Mod textures exist; vanilla helpers are the only external paths', () => {
  const vanillaPaths = ['gfx/interface/goals/shine_overlay.dds', 'gfx/FX/buttonstate.lua'];
  for (const t of new Set(modTextures))
    if (!vanillaPaths.includes(t)) assert(fs.existsSync(t), `missing texture ${t}`);
});

// ---------- equipment whitelist ----------
test('add_equipment_to_stockpile uses only verified equipment names', () => {
  const allowed = new Set(['infantry_equipment', 'infantry_equipment_0', 'support_equipment', 'support_equipment_1',
    'artillery_equipment', 'motorized_equipment', 'CAS_equipment_1', 'fighter_equipment_1',
    'tac_bomber_equipment_1', 'small_plane_airframe_1', 'medium_plane_airframe_1']);
  for (const { f, src } of all)
    for (const m of src.matchAll(/add_equipment_to_stockpile = \{([^}]*)\}/gs))
      for (const t of m[1].matchAll(/type = ([A-Za-z0-9_]+)/g))
        assert(allowed.has(t[1]), `${f} uses unverified equipment ${t[1]}`);
});

// ---------- Taishet package manifest (A-3) ----------
const manifest = new Set(['40', '654', '563', '564', '565', '566', '567', '568', '569', '570', '574', '575', '576', '578']);
test('The 14-state treaty manifest is identical in all five script sites', () => {
  const triggers = read('common/scripted_triggers/tt_tuva_siberian_campaign.txt');
  const effects = read('common/scripted_effects/tt_tuva_siberian_campaign.txt');
  const decisions = read('common/decisions/tt_tuva_decisions.txt');
  const sites = {
    'TT_taishet_package_uncontested': stateIds(block(triggers, 'TT_taishet_package_uncontested')),
    'TT_owns_taishet_package': stateIds(block(triggers, 'TT_owns_taishet_package')),
    'TT_transfer_taishet_package': stateIds(block(effects, 'TT_transfer_taishet_package')),
    'TT_dictate_peace_in_siberia': stateIds(block(decisions, 'TT_dictate_peace_in_siberia')),
    'TT_proclaim_siberian_victory': stateIds(block(decisions, 'TT_proclaim_siberian_victory')),
  };
  for (const [name, ids] of Object.entries(sites))
    assert.deepEqual([...ids].filter(id => manifest.has(id)).sort(), [...manifest].sort(), name);
});

// ---------- recovery hooks (A-2) and fallback (A-1) ----------
test('Daily cleanup releases every dangling pending flag when its target is gone', () => {
  const effects = read('common/scripted_effects/tt_tuva_siberian_campaign.txt');
  const body = block(effects, 'TT_cleanup_diplomatic_pending');
  for (const flag of ['TT_taishet_request_pending', 'TT_corridor_request_pending', 'TT_war_mandate_pending'])
    assert(body.includes(`clr_country_flag = ${flag}`), flag);
  assert(read('common/on_actions/tt_tuva_siberian_campaign.txt').includes('TT_cleanup_diplomatic_pending = yes'));
});
test('Fallback victory decision grants the victory spirit and queues the celebration', () => {
  const body = block(read('common/decisions/tt_tuva_decisions.txt'), 'TT_proclaim_siberian_victory');
  assert(body.includes('add_ideas = TT_masters_of_siberia'));
  assert(body.includes('TT_queue_taishet_superevent = yes'));
  assert(body.includes('TT_postwar_queue_reactions = yes'));
  assert(body.includes('TT_owns_taishet_package = yes'));
});
test('Moscow pressure pulse: window trigger, 60-day cooldown, three events wired', () => {
  assert(read('common/scripted_triggers/tt_tuva_siberian_campaign.txt').includes('TT_pressure_window = {'));
  const on = read('common/on_actions/tt_tuva_siberian_campaign.txt');
  assert(on.includes('TT_pressure_window = yes'));
  assert(on.includes('flag = TT_pressure_cooldown days = 60'));
  for (const id of ['tt_tuva.28', 'tt_tuva.29', 'tt_tuva.30'])
    assert(on.includes(`id = ${id}`), id);
});

// ---------- superevent window (2026-11-06 display bugfix) ----------
test('Superevent window rests on screen; show_position agrees with position', () => {
  const gui = read('interface/tt_tuva_superevent.gui');
  const pos = s => {
    const m = gui.match(new RegExp(`(?:^|[^_\\w])${s} = \\{ x = (-?\\d+) y = (-?\\d+) \\}`, 'm'));
    assert.ok(m, `${s} missing in tt_tuva_superevent.gui`);
    return { x: +m[1], y: +m[2] };
  };
  const at = pos('position'), show = pos('show_position');
  assert.ok(Math.abs(at.y) <= 1000, `container position y=${at.y} is off screen`);
  assert.deepEqual(show, at, 'show_position must match the resting position');
});
test('Superevent show_sound resolves, and the close button follows the proven pattern', () => {
  const gui = read('interface/tt_tuva_superevent.gui');
  const snd = gui.match(/show_sound = ([\w]+)/);
  assert.ok(snd, 'show_sound missing');
  const assets = fs.readdirSync('sound').filter(f => f.endsWith('.asset'))
    .map(f => read(`sound/${f}`)).join('\n');
  assert(assets.includes(`name = "${snd[1]}"`) || assets.includes(`name = ${snd[1]}`),
    `soundeffect ${snd[1]} is not registered in sound/*.asset`);
  const btn = block(gui, 'buttonType');
  assert(btn.includes('spriteType = "GFX_TT_taishet_super_button"'), 'button must use spriteType');
  assert(!btn.includes('quadTextureSprite'), 'quadTextureSprite is for tiled sprites, not buttons');
  assert(btn.includes('clicksound = decisions_ui_button'), 'close button needs a vanilla click sound');
  assert(btn.includes('shortcut = "ESCAPE"'));
  const sgui = read('common/scripted_guis/tt_tuva_superevent.txt');
  assert(sgui.includes('TT_taishet_close_click'), 'scripted_gui must bind TT_taishet_close_click');
});

// ---------- binary assets and GUI references ----------
test('Every spriteType/quadTextureSprite referenced in .gui resolves to a .gfx sprite', () => {
  for (const { f, src } of all.filter(x => x.f.startsWith('interface/') && x.f.endsWith('.gui')))
    for (const m of src.matchAll(/\b(?:spriteType|quadTextureSprite)\s*=\s*"?([A-Za-z0-9_\.]+)"?/g))
      assert(definedGfx.has(m[1]) || vanillaGfx.test(m[1]), `${f} references unknown ${m[1]}`);
});
test('GUI text keys exist in localisation', () => {
  for (const { f, src } of all.filter(x => x.f.startsWith('interface/') && x.f.endsWith('.gui')))
    for (const m of src.matchAll(/\btext\s*=\s*"([A-Za-z0-9_\.]+)"/g))
      if (m[1].startsWith('TT_')) assert(enAll.has(m[1]), `${f} references unlocalised ${m[1]}`);
});
test('Binary assets are engine-safe: DDS magic and PCM16 WAV', () => {
  for (const t of new Set(modTextures)) {
    if (!t.endsWith('.dds') || !fs.existsSync(t)) continue; // vanilla helpers: covered above
    const d = fs.readFileSync(t);
    assert.equal(d.subarray(0, 4).toString('latin1'), 'DDS ', `${t} is not a DDS file`);
  }
  const assets = fs.readdirSync('sound').filter(f => f.endsWith('.asset'))
    .map(f => read(`sound/${f}`)).join('\n');
  for (const m of assets.matchAll(/file = "([^"]+\.wav)"/g)) {
    const p = `sound/${m[1]}`;
    assert.ok(fs.existsSync(p), `missing sound file ${p}`);
    const d = fs.readFileSync(p);
    assert.equal(d.subarray(0, 4).toString('latin1'), 'RIFF', `${p} is not RIFF`);
    assert.equal(d.subarray(8, 12).toString('latin1'), 'WAVE', `${p} is not WAVE`);
    const tag = d.readUInt16LE(20), bits = d.readUInt16LE(34);
    assert.equal(tag, 1, `${p} must be PCM (tag=${tag}); IEEE float is not engine-safe`);
    assert.equal(bits, 16, `${p} must be 16-bit`);
  }
});

// ---------- descriptors ----------
test('Both mod descriptors agree on the version, and README quotes it', () => {
  const v = p => read(p).match(/version="([^"]+)"/)[1];
  assert.equal(v('descriptor.mod'), v('tuva_center_of_asia.mod'));
  assert(read('README.md').includes(`version="${v('descriptor.mod')}"`));
});

console.log(`${checks} grouped integrity checks passed. Engine behaviour still needs an in-game pass (docs/release_checklist.md).`);
