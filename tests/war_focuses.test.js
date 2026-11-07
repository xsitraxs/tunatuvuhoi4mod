// Limited static/model tests, NOT a substitute for HOI4 engine/save/UI tests.
// Run from the repository root: node tests/war_focuses.test.js
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
process.chdir(path.join(__dirname, '..'));
const read = p => fs.readFileSync(p, 'utf8');
function parse(source) {
  const tokens = source.match(/#[^\n]*|"(?:\\.|[^"\\])*"|[{}=<>]|[^\s{}=<>#]+/g).filter(t => !t.startsWith('#'));
  let i = 0;
  function block(nested) {
    const nodes = [];
    while (i < tokens.length && tokens[i] !== '}') {
      const key = tokens[i++];
      if (!['=', '<', '>'].includes(tokens[i])) { nodes.push({ key }); continue; }
      const op = tokens[i++];
      let value = tokens[i++];
      if (value === '{') value = block(true);
      assert.notEqual(value, undefined, key);
      nodes.push({ key, op, value });
    }
    if (nested) assert.equal(tokens[i++], '}');
    return nodes;
  }
  const result = block(false);
  assert.equal(i, tokens.length);
  return result;
}
const get = (nodes, key) => nodes.find(n => n.key === key)?.value;
function walk(nodes, key) {
  return nodes.flatMap(n => [ ...(n.key === key ? [n.value] : []), ...(Array.isArray(n.value) ? walk(n.value, key) : []) ]);
}
const tree = get(parse(read('common/national_focus/tt_tuva_focus.txt')), 'focus_tree');
const focuses = tree.filter(n => n.key === 'focus').map(n => n.value);
const all = new Map(focuses.map(f => [get(f, 'id'), f]));
const added = focuses.filter(f => get(f, 'id').startsWith('TT_war_'));
const triggerFiles = ['tt_tuva_war_focuses', 'tt_tuva_siberian_campaign', 'tt_tuva_postwar'];
const triggers = new Map(triggerFiles.flatMap(f => parse(read(`common/scripted_triggers/${f}.txt`))).map(n => [n.key, n.value]));
const newIdeas = get(get(parse(read('common/ideas/tt_tuva_war_focuses.txt')), 'ideas'), 'country');
const effects = parse(read('common/scripted_effects/tt_tuva_war_focuses.txt'));
let checks = 0;
function test(name, run) { run(); checks++; console.log(`PASS ${name}`); }
function evalNodes(nodes, state) {
  return nodes.filter(n => n.key !== 'tooltip').every(n => {
    if (n.key === 'NOT') return !evalNodes(n.value, state);
    if (n.key === 'OR') return n.value.some(v => evalNodes([v], state));
    if (n.key === 'AND' || n.key === 'custom_trigger_tooltip') return evalNodes(n.value, state);
    if (triggers.has(n.key)) return evalNodes(triggers.get(n.key), state) === (n.value === 'yes');
    if (/^\d+$/.test(n.key)) return evalNodes(n.value, { ...state, stateId: n.key });
    if (n.key === 'SOV') return evalNodes(n.value, { ...state, sovScope: true });
    const boolean = b => b === (n.value === 'yes');
    switch (n.key) {
      case 'tag': return n.value === 'TAN';
      case 'has_country_flag': return state.flags.has(n.value);
      case 'has_completed_focus': return state.completed.has(n.value);
      case 'country_exists': return state.sovExists;
      case 'has_war_with': return state.sovWar;
      case 'has_war': return boolean(state.anyWar);
      case 'has_capitulated': return boolean(state.sovScope ? state.sovCapitulated : state.capitulated);
      case 'is_subject': return boolean(state.subject);
      case 'is_in_faction_with': return state.sameFaction;
      case 'has_idea': return state.ideas.has(n.value);
      case 'controls_state': return state.control.has(n.value);
      case 'is_owned_by': return (n.value === 'TAN' ? state.owned : state.sovOwned).has(state.stateId);
      default: throw Error(`Unmodelled trigger: ${n.key}`);
    }
  });
}
const packageIds = ['40','654','563','564','565','566','567','568','569','570','574','575','576','578'];
function state(overrides = {}) {
  return { flags: new Set(['TT_national_path']), completed: new Set(['TT_the_siberian_gambit']), sovExists: true,
    sovWar: true, anyWar: true, capitulated: false, sovCapitulated: false, subject: false, sameFaction: false,
    ideas: new Set(), control: new Set(['329', ...packageIds]),
    owned: overrides.ideas?.has('TT_masters_of_siberia') ? new Set(packageIds) : new Set(), sovOwned: overrides.ideas?.has('TT_masters_of_siberia') ? new Set() : new Set(packageIds), ...overrides };
}
const available = (id, s) => evalNodes(get(all.get(`TT_war_${id}`), 'available'), s);
test('46 unique focuses; ten additions', () => { assert.equal(focuses.length, 46); assert.equal(all.size, 46); assert.equal(added.length, 10); });
const milestoneIds = ['transsib_advance', 'red_army_salvage', 'taishet_junction'];
const preparationIds = ['staff_maps', 'border_depots', 'field_reserve'];
test('Preparation 15 days, complete branch 58 days; no repeatable focuses', () => {
  let days = 0;
  added.forEach(f => {
    const id = get(f, 'id').replace('TT_war_', '');
    assert.equal(get(f, 'cost'), preparationIds.includes(id) || milestoneIds.includes(id) ? '5' : '7');
    days += Number(get(f, 'cost'));
    assert.notEqual(get(f, 'repeatable'), 'yes');
    assert.equal(get(f, 'cancel_if_invalid'), milestoneIds.includes(id) ? 'no' : 'yes');
  });
  assert.equal(days, 58);
  assert.equal(preparationIds.reduce((sum, id) => sum + Number(get(all.get('TT_war_' + id), 'cost')), 0), 15);
});
test('All prerequisites, relative anchors and icons resolve', () => {
  const gfx = new Set([...read('interface/tt_tuva_focus_icons.gfx').matchAll(/name\s*=\s*"([^"]+)"/g)].map(m => m[1]));
  added.forEach(f => { walk(f, 'focus').forEach(id => assert(all.has(id), id)); assert(all.has(get(f, 'relative_position_id'))); assert(gfx.has(get(f, 'icon'))); });
});
test('Soviet war branch owns ten dedicated icons', () => {
  const gfx = new Map([...read('interface/tt_tuva_focus_icons.gfx')
    .matchAll(/name\s*=\s*"([^"]+)"\s*\n\s*texturefile\s*=\s*"([^"]+)"/g)].map(m => [m[1], m[2]]));
  const icons = added.map(f => get(f, 'icon'));
  assert.equal(new Set(icons).size, 10, 'icons are not distinct');
  icons.forEach(name => {
    assert(name.startsWith('GFX_TT_focus_war_'), name);          // own naming for the branch
    assert(gfx.has(name) && gfx.has(name + '_shine'), name);    // normal and shine sprite
    const file = gfx.get(name);
    assert(fs.existsSync(file), file);
    assert.equal(fs.statSync(file).size, 32428, `${file} is not a 95x85 A8R8G8B8 DDS`);
    const borrowed = focuses.filter(f => !get(f, 'id').startsWith('TT_war_') && get(f, 'icon') === name);
    assert.equal(borrowed.length, 0, `${name} is shared with ${borrowed[0] && get(borrowed[0], 'id')}`);
  });
});
test('Soviet war operation stands in its own column block', () => {
  // The nine-focus wartime operation occupies an isolated block. The postwar
  // finale is intentionally parked directly below its sole prerequisite,
  // the Siberian Gambit, so it does not create an orphaned long connector.
  const warIds = new Set(added.map(f => get(f, 'id')).filter(id => id !== 'TT_war_new_siberian_border'));
  const byColumn = new Map();
  focuses.forEach(f => {
    const x = position(get(f, 'id'))[0];
    if (!byColumn.has(x)) byColumn.set(x, []);
    byColumn.get(x).push(get(f, 'id'));
  });
  const warColumns = [...byColumn.keys()].filter(x => byColumn.get(x).some(id => warIds.has(id)));
  assert(warColumns.length >= 2, 'the branch needs its own columns');
  warColumns.forEach(x => assert(byColumn.get(x).every(id => warIds.has(id)), `column ${x} mixes the branch with the rest of the tree`));
  const otherColumns = [...byColumn.keys()].filter(x => !warColumns.includes(x));
  const gap = Math.min(...otherColumns.map(x => Math.min(...warColumns.map(w => Math.abs(w - x)))));
  assert(gap >= 2, `the branch is only ${gap} column(s) away from another branch`);
});
const positions = new Map();
function position(id, seen = new Set()) {
  assert(!seen.has(id), 'relative-position cycle'); seen.add(id);
  const f = all.get(id), anchor = get(f, 'relative_position_id');
  const p = anchor ? position(anchor, seen) : [0, 0];
  return [p[0] + Number(get(f, 'x')), p[1] + Number(get(f, 'y'))];
}
test('No focus-coordinate collisions across the whole tree', () => focuses.forEach(f => {
  const id = get(f, 'id'), p = position(id).join(','); assert(!positions.has(p), `${id} overlaps ${positions.get(p)}`); positions.set(p, id);
}));
test('New prerequisite graph has no cycles', () => {
  function visit(id, ancestors = new Set()) { assert(!ancestors.has(id), id); const next = new Set([...ancestors, id]); walk(all.get(id).filter(n => n.key === 'prerequisite'), 'focus').forEach(p => visit(p, next)); }
  added.forEach(f => visit(get(f, 'id')));
});
test('Gambit does not require new preparation; finale needs only Gambit', () => {
  assert(!walk(all.get('TT_the_siberian_gambit'), 'focus').some(id => id.startsWith('TT_war_')));
  assert.deepEqual(walk(all.get('TT_war_new_siberian_border'), 'focus'), ['TT_the_siberian_gambit']);
});
test('Preparation works before war and during campaign', () => {
  assert(available('staff_maps', state({ sovWar: false, anyWar: false, completed: new Set() })));
  assert(available('staff_maps', state()));
});
test('Preparation blocks subjects, surrender, missing USSR, Soviet alliance, victory and wrong path', () => {
  for (const change of [{ subject: true }, { capitulated: true }, { sovExists: false }, { sameFaction: true },
    { ideas: new Set(['TT_masters_of_siberia']) }, { flags: new Set() }]) assert(!available('staff_maps', state(change)));
});
test('War branch requires an active Soviet campaign', () => {
  assert(available('sayan_offensive', state()));
  for (const change of [{ sovWar: false }, { sovExists: false }, { capitulated: true }, { sovCapitulated: true },
    { completed: new Set() }, { flags: new Set() }, { ideas: new Set(['TT_masters_of_siberia']) }]) assert(!available('sayan_offensive', state(change)));
});
test('Eastern railway reward checks all four required states', () => {
  assert(available('transsib_advance', state()));
  for (const id of ['329', '563', '564', '566']) { const control = state().control; control.delete(id); assert(!available('transsib_advance', state({ control }))); }
});
test('Trophies require Irkutsk control', () => { assert(available('red_army_salvage', state())); const control = state().control; control.delete('566'); assert(!available('red_army_salvage', state({ control }))); });
test('Junction reward requires every peace railway node', () => {
  assert(available('taishet_junction', state()));
  for (const id of ['329','563','564','566','568','569','570','578']) { const control = state().control; control.delete(id); assert(!available('taishet_junction', state({ control }))); }
});
test('Peaceful victory finale works without wartime branch completion', () => {
  assert(available('new_siberian_border', state({ sovWar: false, anyWar: false, ideas: new Set(['TT_masters_of_siberia']) })));
});
test('Finale blocks every missing treaty state, ongoing war and absent victory spirit', () => {
  const victory = { sovWar: false, anyWar: false, ideas: new Set(['TT_masters_of_siberia']) };
  for (const id of packageIds) { const owned = state().owned; owned.delete(id); assert(!available('new_siberian_border', state({ ...victory, owned }))); }
  assert(!available('new_siberian_border', state({ ...victory, anyWar: true })));
  assert(!available('new_siberian_border', state({ sovWar: false, anyWar: false })));
});
test('Rewards recheck availability except proven-at-selection milestones', () => added.forEach(f => {
  const avail = get(f, 'available').flatMap(n => n.key === 'custom_trigger_tooltip' ? n.value.filter(n => n.key !== 'tooltip') : [n]);
  assert.deepEqual(get(get(get(f, 'completion_reward'), 'if'), 'limit'), milestoneIds.includes(get(f, 'id').replace('TT_war_', '')) ? [{ key: 'TT_siberian_campaign_active', op: '=', value: 'yes' }] : avail);
}));
test('Three timed spirits, exactly ninety days; all references resolve', () => {
  const timed = added.flatMap(f => walk(f, 'add_timed_idea')); assert.equal(timed.length, 3);
  timed.forEach(t => { assert.equal(get(t, 'days'), '90'); assert(newIdeas.some(n => n.key === get(t, 'idea'))); });
});
test('Bounded spirit strengths; no new attack or defence multiplier', () => {
  const modifiers = newIdeas.flatMap(n => get(n.value, 'modifier'));
  assert.deepEqual(modifiers.map(n => [n.key, Number(n.value)]), [['max_planning_factor', 0.05], ['supply_consumption_factor', -0.03], ['army_org_factor', 0.03]]);
});
test('Cleanup removes every new spirit and is called daily', () => {
  assert.deepEqual(walk(effects, 'remove_ideas').sort(), newIdeas.map(n => n.key).sort());
  const guard = get(get(get(effects, 'TT_cleanup_war_focus_spirits'), 'if'), 'limit');
  assert.equal(evalNodes(guard, state()), false);
  for (const change of [{ sovWar: false }, { sovExists: false }, { capitulated: true }, { sovCapitulated: true }, { ideas: new Set(['TT_masters_of_siberia']) }]) assert(evalNodes(guard, state(change)));
  assert(read('common/on_actions/tt_tuva_siberian_campaign.txt').includes('TT_cleanup_war_focus_spirits = yes'));
});
test('Supplies total 350 basic rifles and 35 support equipment, not factories', () => {
  const amounts = {};
  added.flatMap(f => walk(f, 'add_equipment_to_stockpile')).forEach(e => { const t = get(e, 'type'); amounts[t] = (amounts[t] || 0) + Number(get(e, 'amount')); });
  assert.deepEqual(amounts, { infantry_equipment_0: 350, support_equipment_1: 35 });
  assert.equal(added.flatMap(f => walk(f, 'add_manpower')).reduce((a,b) => a + Number(b), 0), 500);
});
test('Reward effects use supported names and bounded total XP/PP', () => {
  const allowed = new Set(['army_experience','add_command_power','add_equipment_to_stockpile','add_manpower','add_war_support','add_timed_idea','add_political_power','add_stability']);
  added.forEach(f => get(get(f, 'completion_reward'), 'if').filter(n => n.key !== 'limit').forEach(n => assert(allowed.has(n.key), n.key)));
  assert.equal(added.flatMap(f => walk(f, 'army_experience')).reduce((a,b) => a + Number(b), 0), 40);
  assert.equal(added.flatMap(f => walk(f, 'add_political_power')).reduce((a,b) => a + Number(b), 0), 45);
});
test('No new cores, transfers, war declaration, factories, bypasses or peace gates', () => {
  for (const key of ['add_state_core','transfer_state','transfer_state_to','declare_war_on','create_wargoal','add_building_construction','bypass']) assert.equal(added.flatMap(f => walk(f, key)).length, 0, key);
  for (const file of ['common/scripted_triggers/tt_tuva_siberian_campaign.txt','common/decisions/tt_tuva_decisions.txt','events/tt_tuva_events.txt']) added.forEach(f => assert(!read(file).includes(get(f, 'id')), file));
});
test('RU/EN keys match; all new focuses, spirits and tooltips localised with BOM', () => {
  function keys(lang) { const text = read(`localisation/${lang}/tt_war_focuses_l_${lang}.yml`); assert(text.startsWith('\ufeff')); return [...text.matchAll(/^ ([\w.]+):/gm)].map(m => m[1]); }
  const ru = keys('russian'), en = keys('english'); assert.equal(ru.length, 28); assert.equal(new Set(ru).size, 28); assert.deepEqual(ru, en);
  [...added.map(f => get(f, 'id')), ...newIdeas.map(n => n.key)].forEach(id => { assert(ru.includes(id)); assert(ru.includes(id + '_desc')); });
});

test('Milestones cannot start without control or on non-Soviet-owned objectives', () => {
  const regions = { transsib_advance: ['563','564','566'], red_army_salvage: ['566'], taishet_junction: ['563','564','566','568','569','570','578'] };
  for (const [id, nodes] of Object.entries(regions)) {
    for (const node of nodes) {
      const sovOwned = state().sovOwned; sovOwned.delete(node);
      assert(!available(id, state({ sovOwned })), id + ' ownership ' + node);
    }
    assert(!available(id, state({ control: new Set() })), id);
    assert(!available(id, state({ flags: new Set(['TT_national_path', 'fake_capture']) , control: new Set() })), id);
  }
});
test('Running milestones survive loss but not peace or capitulation', () => {
  for (const id of milestoneIds) {
    const focus = all.get('TT_war_' + id);
    assert(available(id, state())); // Selection is the evidence, no select_effect side effects.
    assert.equal(get(focus, 'continue_if_invalid'), 'yes');
    assert.equal(get(focus, 'select_effect'), undefined); // Keep manual cancellation possible.
    const lost = state({ control: new Set(), sovOwned: new Set() });
    assert(!available(id, lost)); // Cannot start/restart after losing objectives.
    assert(!evalNodes(get(focus, 'cancel'), lost)); // But an already running project survives.
    const rewardGuard = get(get(get(focus, 'completion_reward'), 'if'), 'limit');
    assert(evalNodes(rewardGuard, lost));
    for (const change of [{ sovWar: false }, { sovExists: false }, { capitulated: true }, { sovCapitulated: true }, { ideas: new Set(['TT_masters_of_siberia']) }]) {
      const ended = state(change);
      assert(evalNodes(get(focus, 'cancel'), ended));
      assert(!evalNodes(rewardGuard, ended));
    }
  }
});
test('Front-holding project still cancels on loss of any eastern node', () => {
  const focus = all.get('TT_war_hold_conquests');
  assert.equal(get(focus, 'cancel_if_invalid'), 'yes');
  assert.notEqual(get(focus, 'continue_if_invalid'), 'yes');
  for (const node of ['329','563','564','566']) {
    const control = state().control; control.delete(node);
    const lost = state({ control });
    assert(!available('hold_conquests', lost));
    assert(!evalNodes(get(get(get(focus, 'completion_reward'), 'if'), 'limit'), lost));
  }
});
test('AI weights respond to war and postwar state; filters match supplies/manpower', () => {
  function weight(id, st) {
    const ai = get(all.get('TT_war_' + id), 'ai_will_do');
    return ai.filter(n => n.key === 'modifier').reduce((v, n) => evalNodes(n.value.filter(x => x.key !== 'factor'), st) ? v * Number(get(n.value, 'factor')) : v, Number(get(ai, 'factor')));
  }
  assert.equal(weight('staff_maps', state({ sovWar: false, completed: new Set() })), 10);
  assert.equal(weight('staff_maps', state({ sovWar: false })), 40);
  assert.equal(weight('staff_maps', state()), 40);
  assert.equal(weight('siberian_guides', state()), 60);
  assert.equal(weight('new_siberian_border', state({ sovWar: false, anyWar: false, ideas: new Set(['TT_masters_of_siberia']) })), 40);
  for (const id of ['border_depots','red_army_salvage','field_reserve']) assert(get(all.get('TT_war_' + id), 'search_filters').some(n => n.key === 'FOCUS_FILTER_MANPOWER'));
  assert(get(all.get('TT_war_field_reserve'), 'search_filters').some(n => n.key === 'FOCUS_FILTER_WAR_SUPPORT'));
});

console.log(`${checks} grouped checks passed. Model does not emulate HOI4 timing, saves or UI rendering.`);
