#!/usr/bin/env python3
"""Static validation for the "Tuva: The Center of Asia" HOI4 mod.

Run from anywhere:  python3 docs/validate_mod.py
Standard library only. Exits with 1 if any check fails.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOM = b'\xef\xbb\xbf'
TGA_FOOTER = b'\x00' * 8 + b'TRUEVISION-XFILE.\x00'

errors: list[str] = []
checks = 0


def ok(condition: bool, message: str) -> bool:
    global checks
    checks += 1
    if not condition:
        errors.append(message)
    return condition


def script_files() -> list[Path]:
    return sorted([*ROOT.glob('**/*.txt'), *ROOT.glob('**/*.mod')])


def strip_noise(text: str) -> str:
    """Remove quoted strings and # comments so brace counting is reliable."""
    text = re.sub(r'"[^"\n]*"', '""', text)
    return '\n'.join(line.split('#', 1)[0] for line in text.split('\n'))


# --------------------------------------------------- Clausewitz Block AST Parser
CW_TOKEN_RE = re.compile(
    r'#.*|'                        # comments (discarded)
    r'"(?:\\.|[^"\\])*"|'          # quoted strings
    r'[{}]|'                       # block braces
    r'<=|>=|!=|==|[=!<>]|'         # comparison / assignment operators
    r'[^\s#{}<>=!"]+'              # identifiers, numbers, tokens
)


class CWBlock:
    """A parsed Clausewitz syntax block or node tree."""

    def __init__(self, key: str = '', op: str = '='):
        self.key: str = key
        self.op: str = op
        self.assignments: list[tuple[str, str, str]] = []  # (key, op, val)
        self.blocks: list[CWBlock] = []
        self.values: list[str] = []

    def get_assignment(self, key: str) -> str | None:
        """Return the value of the first direct assignment with key, or None."""
        for k, _, v in self.assignments:
            if k == key:
                return v
        return None

    def find_assignments(self, key: str) -> list[tuple[str, str]]:
        """Return all (op, val) pairs for direct assignments with key."""
        return [(op, v) for k, op, v in self.assignments if k == key]

    def has_assignment(self, key: str, val: str | None = None) -> bool:
        """Return True if this block directly has assignment key (and optionally val)."""
        for k, _, v in self.assignments:
            if k == key and (val is None or v == val):
                return True
        return False

    def get_block(self, key: str) -> CWBlock | None:
        """Return the first direct child block with key, or None."""
        for b in self.blocks:
            if b.key == key:
                return b
        return None

    def find_blocks(self, key: str) -> list[CWBlock]:
        """Return all direct child blocks with key."""
        return [b for b in self.blocks if b.key == key]

    def find_all_blocks(self, key: str) -> list[CWBlock]:
        """Recursively find all descendant blocks with key."""
        res: list[CWBlock] = []
        for b in self.blocks:
            if b.key == key:
                res.append(b)
            res.extend(b.find_all_blocks(key))
        return res

    def has_recursive(self, key: str, val: str | None = None) -> bool:
        """Return True if key exists anywhere in tree as an assignment or block."""
        for k, _, v in self.assignments:
            if k == key and (val is None or v == val):
                return True
        for b in self.blocks:
            if b.key == key and val is None:
                return True
            if b.has_recursive(key, val):
                return True
        return False


def parse_clausewitz(text: str) -> CWBlock:
    """Parse Clausewitz script into a tree of CWBlock nodes using brace depth tracking."""
    tokens = [t for t in CW_TOKEN_RE.findall(text) if not t.startswith('#')]
    root = CWBlock('<root>')
    stack: list[CWBlock] = [root]
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok == '}':
            if len(stack) > 1:
                stack.pop()
            i += 1
        elif tok == '{':
            block = CWBlock('', '=')
            stack[-1].blocks.append(block)
            stack.append(block)
            i += 1
        elif i + 2 < n and tokens[i + 1] in ('=', '<', '>', '<=', '>=', '!=') and tokens[i + 2] == '{':
            block = CWBlock(tok, tokens[i + 1])
            stack[-1].blocks.append(block)
            stack.append(block)
            i += 3
        elif i + 2 < n and tokens[i + 1] in ('=', '<', '>', '<=', '>=', '!=') and tokens[i + 2] != '{':
            stack[-1].assignments.append((tok, tokens[i + 1], tokens[i + 2]))
            i += 3
        else:
            stack[-1].values.append(tok)
            i += 1
    return root


# ------------------------------------------------------------------ 1. encodings
def check_encodings() -> None:
    files = script_files()
    ok(len(files) >= 8, f'expected the mod script files, found {len(files)}')
    for p in files:
        b = p.read_bytes()
        rel = p.relative_to(ROOT).as_posix()
        ok(not b.startswith(BOM), f'{rel}: UTF-8 BOM in a .txt/.mod file')
        ok(b'\r\n' not in b and b'\r' not in b, f'{rel}: CRLF/CR line endings')
        try:
            text = b.decode('utf-8')
        except UnicodeDecodeError as e:
            errors.append(f'{rel}: invalid UTF-8 ({e})')
            continue
        clean = strip_noise(text)
        opens, closes = clean.count('{'), clean.count('}')
        ok(opens == closes, f'{rel}: unbalanced braces {{={opens} }}={closes}')
        # A closing brace may never overtake the opening one.
        depth = 0
        for ch in clean:
            depth += (ch == '{') - (ch == '}')
            if depth < 0:
                break
        ok(depth >= 0, f'{rel}: a closing brace appears before its opening brace')


# ------------------------------------------------------------- 2. localisation
LOC_FILES = {
    'EN': ROOT / 'localisation/english/tt_tuva_l_english.yml',
    'RU': ROOT / 'localisation/russian/tt_tuva_l_russian.yml',
}
KEY_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_.]*):\s', re.M)
TOKEN_RE = re.compile(r'\b(?:TT_[A-Za-z0-9_]+|tt_tuva\.[A-Za-z0-9_.]+)\b')
NON_LOCALISABLE = {'TT_khural_open', 'TT_soviet_path', 'TT_national_path'}


def loc_keys(path: Path) -> tuple[list[str], str]:
    b = path.read_bytes()
    text = b[3:].decode('utf-8-sig')
    return KEY_RE.findall(text), text


def expected_keys() -> set[str]:
    """Localisation keys implied by the scripts (ids + _desc/_DEF/_ADJ conventions)."""
    focus = (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(encoding='utf-8')
    ideas = (ROOT / 'common/ideas/tt_tuva_ideas.txt').read_text(encoding='utf-8')
    decs = (ROOT / 'common/decisions/tt_tuva_decisions.txt').read_text(encoding='utf-8')
    cosmetic = (ROOT / 'common/countries/tt_tuva_cosmetic.txt').read_text(encoding='utf-8')
    expected: set[str] = set()

    for fid in re.findall(r'^\tfocus = \{\n\t\tid = (\S+)', focus, re.M):
        expected |= {fid, fid + '_desc'}
    for name in re.findall(r'^\t\t([A-Za-z_][A-Za-z0-9_]*) = \{', ideas, re.M):
        expected |= {name, name + '_desc'}
    for cat in re.findall(r'^([A-Za-z_][A-Za-z0-9_]*) = \{', decs, re.M):
        expected.add(cat)
    for name in re.findall(r'^\t([A-Za-z_][A-Za-z0-9_]*) = \{', decs, re.M):
        expected |= {name, name + '_desc'}
    for tag in re.findall(r'^([A-Za-z_][A-Za-z0-9_]*) = \{', cosmetic, re.M):
        expected |= {tag, tag + '_DEF', tag + '_ADJ'}

    # title / desc / name / tooltip / tech-bonus name / country-flag tokens
    for p in script_files():
        for token in TOKEN_RE.findall(p.read_text(encoding='utf-8')):
            if token in NON_LOCALISABLE or re.fullmatch(r'tt_tuva\.\d+', token):
                continue
            expected.add(token)
    return expected


def check_localisation() -> None:
    data: dict[str, set[str]] = {}
    for lang, path in LOC_FILES.items():
        b = path.read_bytes()
        ok(b.startswith(BOM), f'{lang}: missing UTF-8 BOM')
        ok(b'\r\n' not in b and b'\r' not in b, f'{lang}: CRLF/CR line endings')
        try:
            keys, text = loc_keys(path)
        except UnicodeDecodeError as e:
            errors.append(f'{lang}: invalid UTF-8 ({e})')
            continue
        keys = [k for k in keys if k not in ('l_english', 'l_russian')]
        ok(text.startswith('l_english:' if lang == 'EN' else 'l_russian:'),
           f'{lang}: wrong localisation header')
        ok(len(keys) == 235, f'{lang}: expected 235 keys, found {len(keys)}')
        ok(len(set(keys)) == len(keys),
           f'{lang}: duplicate keys: {sorted({k for k in keys if keys.count(k) > 1})}')
        data[lang] = set(keys)

        # Every §Y must be closed by §!, on the same line and without nesting.
        for n, line in enumerate(text.split('\n'), 1):
            if '§' not in line:
                continue
            markers = re.findall(r'§.', line)
            valid = (len(markers) % 2 == 0 and
                     all(m == ('§Y' if i % 2 == 0 else '§!')
                         for i, m in enumerate(markers)))
            ok(valid, f'{lang}:{n}: unclosed/nested §Y…§! colour code: {line.strip()[:80]}')
        ok(text.count('§Y') == text.count('§!'), f'{lang}: §Y/§! count mismatch')

    if 'EN' in data and 'RU' in data:
        ok(data['EN'] == data['RU'],
           f'EN/RU key mismatch: EN-only={sorted(data["EN"] - data["RU"])}, '
           f'RU-only={sorted(data["RU"] - data["EN"])}')
        exp = expected_keys()
        ok(len(exp) == 235, f'script-implied key set has {len(exp)} keys (expected 235)')
        ok(not (exp - data['EN']), f'missing localisation keys: {sorted(exp - data["EN"])}')
        ok(not (data['EN'] - exp), f'orphan localisation keys: {sorted(data["EN"] - exp)}')


# ------------------------------------------------------------------ 3. focuses
# Vanilla sprites (interface/goals.gfx + interface/goals_shine.gfx), one per focus.
VANILLA_ICONS = {
    'GFX_focus_generic_the_giant_wakes', 'GFX_focus_generic_freedom_council',
    'GFX_focus_generic_soviet_politics', 'GFX_focus_generic_communist_industry',
    'GFX_focus_generic_total_war', 'GFX_focus_generic_workers_and_farmers_rise',
    'GFX_focus_generic_join_comintern', 'GFX_focus_generic_attack_mongolia',
    'GFX_focus_generic_support_the_left_right', 'GFX_focus_generic_monarchy_2',
    'GFX_focus_generic_provoke_border_clashes',
    'GFX_focus_generic_military_dictatorship', 'GFX_focus_generic_industry_1',
    'GFX_focus_generic_agricultural_subsidies', 'GFX_focus_generic_industry_2',
    'GFX_focus_generic_mining_industry', 'GFX_focus_generic_railroad',
    'GFX_focus_generic_hydroelectric_energy', 'GFX_focus_generic_resource_extraction',
    'GFX_focus_generic_military_academy', 'GFX_focus_generic_horse_studs',
    'GFX_focus_generic_military_mission',
    'GFX_focus_generic_commonwealth_build_infantry',
    'GFX_focus_generic_air_bases', 'GFX_focus_generic_manpower',
    'GFX_focus_generic_annex_country', 'GFX_focus_generic_diplomatic_treaty',
    'GFX_focus_generic_annex_country_2', 'GFX_focus_generic_winter_warfare',
    # 1.1.0 doctrine / air / navy focuses use the legacy generic goal sprites.
    # The GFX_focus_generic_* spellings of these seven do not exist in vanilla;
    # the GFX_goal_generic_* sprites (and their _shine counterparts) do.
    'GFX_goal_generic_army_artillery', 'GFX_goal_generic_army_tanks',
    'GFX_goal_generic_CAS', 'GFX_goal_generic_air_bomber',
    'GFX_goal_generic_build_navy', 'GFX_goal_generic_navy_doctrines_tactics',
    'GFX_goal_generic_navy_battleship',
}
# Sprites that are known not to exist in vanilla.
BAD_ICONS = {
    'GFX_focus_generic_asia_liberation', 'GFX_focus_generic_stalinist_industry',
    'GFX_focus_generic_communist_asia', 'GFX_focus_generic_printing_press',
    'GFX_focus_generic_army_attack', 'GFX_focus_generic_modernizing_agriculture',
    'GFX_focus_generic_mineral_prospecting', 'GFX_focus_generic_expand_gold_mining',
    'GFX_focus_generic_advisors', 'GFX_focus_generic_mountain_troops',
    # Invented 1.1.0 spellings replaced by the GFX_goal_generic_* sprites above.
    'GFX_focus_generic_army_artillery', 'GFX_focus_generic_army_tanks',
    'GFX_focus_generic_CAS', 'GFX_focus_generic_air_bomber',
    'GFX_focus_generic_build_navy', 'GFX_focus_generic_navy_doctrines_tactics',
    'GFX_focus_generic_navy_battleship',
}


def check_focuses(custom_focus_text: str | None = None) -> None:
    text = custom_focus_text if custom_focus_text is not None else (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(encoding='utf-8')
    icons = re.findall(r'^\t\ticon = (\S+)', text, re.M)
    ids = re.findall(r'^\tfocus = \{\n\t\tid = (\S+)', text, re.M)
    ok(len(ids) == 36, f'expected 36 focuses, found {len(ids)}')
    ok(len(set(ids)) == len(ids), 'duplicate focus ids')
    ok(len(icons) == 36, f'expected 36 focus icons, found {len(icons)}')
    ok(len(set(icons)) == 36,
       f'focus icons are not unique: {sorted({i for i in icons if icons.count(i) > 1})}')
    ok(set(icons) == VANILLA_ICONS,
       f'focus icons differ from the validated vanilla set: '
       f'unknown={sorted(set(icons) - VANILLA_ICONS)}, '
       f'missing={sorted(VANILLA_ICONS - set(icons))}')
    ok(not (set(icons) & BAD_ICONS), f'known-invalid icons still used: {sorted(set(icons) & BAD_ICONS)}')
    ok(all(i.startswith(('GFX_focus_generic_', 'GFX_goal_generic_')) for i in icons),
       'every icon must be a validated generic focus/goal sprite')
    # Specific regression fixes.
    ok('category = infantry_weapons' in text and 'category = infantry_tech' not in text,
       'TT_mountain_warfare: research category is not infantry_weapons')
    ok('generator = { 563 566 568 570 }' in text,
       'TT_the_siberian_gambit: wargoal generator must include state 563')
    ok('has_dlc = "By Blood Alone"' in text and 'small_plane_airframe_1' in text,
       'TT_the_tuvan_air_force: missing By Blood Alone compatibility')
    ok('picture = "GFX_Portrait_Asia_Generic_land_1"' in text,
       'TT_the_second_khanate: portrait is not the vanilla Asian general portrait')
    ok(re.search(r'country_exists = SOV\s*\n\s*NOT = \{ has_war_with = SOV \}', text) is not None,
       'TT_form_central_asian_ssr: country_exists / peace check is missing')

    # 1.1.0 layout and branch regressions.
    by_id: dict[str, str] = {}
    for chunk in text.split('\n\tfocus = {'):
        m = re.match(r'\n\t\tid = (\S+)', chunk)
        if m:
            by_id[m.group(1)] = chunk
    # Every economic focus (plus the Soviet arsenal chain) grants building slots,
    # so the player always has room left to build manually (329 = Tuva).
    for fid in ('TT_the_soviet_arsenal', 'TT_the_siberian_military_district',
                'TT_first_five_year_plan', 'TT_collective_herds',
                'TT_kyzyl_industries', 'TT_mineral_prospecting',
                'TT_the_kyzyl_railroad', 'TT_the_yenisei_dam', 'TT_the_golden_hoard'):
        ok('add_extra_state_shared_building_slots' in by_id.get(fid, ''),
           f'{fid}: economic focus grants no building slots')
    # The three army doctrines are mutually exclusive ways of war.
    ok('mutually_exclusive = { focus = TT_infantry_and_artillery focus = TT_tanks_of_the_steppe }'
       in by_id.get('TT_cavalry_of_the_steppe', ''),
       'doctrine focuses are not mutually exclusive (cavalry)')
    ok('mutually_exclusive = { focus = TT_cavalry_of_the_steppe focus = TT_tanks_of_the_steppe }'
       in by_id.get('TT_infantry_and_artillery', ''),
       'doctrine focuses are not mutually exclusive (infantry/artillery)')
    ok('mutually_exclusive = { focus = TT_cavalry_of_the_steppe focus = TT_infantry_and_artillery }'
       in by_id.get('TT_tanks_of_the_steppe', ''),
       'doctrine focuses are not mutually exclusive (tanks)')
    # Land/air/navy branch roots accept any of the three doctrines. HoI4 treats
    # several focus entries inside ONE prerequisite block as OR, but several
    # separate prerequisite blocks as AND -- with mutually exclusive doctrines
    # the latter would make the whole military subtree unreachable.
    doctrines = ('TT_cavalry_of_the_steppe', 'TT_infantry_and_artillery',
                 'TT_tanks_of_the_steppe')
    prerequisites: dict[str, list[list[str]]] = {}
    for fid, body in by_id.items():
        prerequisites[fid] = [
            re.findall(r'focus = (\S+)', group)
            for group in re.findall(r'prerequisite = \{([^}]*)\}', body)
        ]
    for root in ('TT_soviet_advisors', 'TT_the_tuvan_air_force',
                 'TT_the_yenisei_flotilla'):
        ok(prerequisites.get(root) == [list(doctrines)],
           f'{root}: doctrines must be alternatives in one prerequisite block, '
           f'got {prerequisites.get(root)}')
    # Logical reachability of the focus graph for every doctrine choice:
    # each prerequisite block (AND) needs one completed focus from it (OR).
    def reachable(blocked: set[str]) -> set[str]:
        done: set[str] = set()
        changed = True
        while changed:
            changed = False
            for fid in ids:
                if fid in done or fid in blocked:
                    continue
                if all(any(req in done for req in group)
                       for group in prerequisites.get(fid, [])):
                    done.add(fid)
                    changed = True
        return done

    for chosen in doctrines:
        blocked = set(doctrines) - {chosen}
        missing = set(ids) - blocked - reachable(blocked)
        ok(not missing,
           f'focuses unreachable with doctrine {chosen}: {sorted(missing)}')
    # No two focuses share an absolute tree position.
    seen: dict[tuple[int, int], str] = {}
    abspos: dict[str, tuple[int, int]] = {}

    def resolve(fid: str) -> tuple[int, int]:
        if fid in abspos:
            return abspos[fid]
        body = by_id.get(fid, '')
        x = int(re.search(r'^\t\tx = (-?\d+)', body, re.M).group(1))
        y = int(re.search(r'^\t\ty = (-?\d+)', body, re.M).group(1))
        rel = re.search(r'relative_position_id = (\S+)', body)
        if rel:
            ax, ay = resolve(rel.group(1))
            x, y = x + ax, y + ay
        abspos[fid] = (x, y)
        return abspos[fid]

    for fid in ids:
        p = resolve(fid)
        ok(p not in seen, f'{fid}: tree position {p} collides with {seen.get(p)}')
        seen[p] = fid
    # Neutrality popularity is built up along the national path (no civil war).
    ok('popularity = 0.30' in by_id.get('TT_tuvan_renaissance', ''),
       'TT_tuvan_renaissance: neutrality popularity boost is missing')
    khanate = by_id.get('TT_the_second_khanate', '')
    ok('set_popularities' in khanate and 'neutrality = 75' in khanate and
       'communism = 25' in khanate and 'popularity = 0.45' not in khanate,
       'TT_the_second_khanate: popularity split must be set to 75/25 exactly')
    ok('leave_faction = yes' in khanate,
       'TT_the_second_khanate: Tuva must leave the Comintern before it can fight SOV')
    ok('custom_effect_tooltip = TT_war_declaration_tt' in khanate,
       'TT_the_second_khanate: war-declaration tooltip is missing')
    # Parse focus file AST for structural block and modifier inspection
    focus_root = parse_clausewitz(text)
    foci_by_id = {f.get_assignment('id'): f for f in focus_root.find_all_blocks('focus')}
    renaissance_focus = foci_by_id.get('TT_tuvan_renaissance')
    renaissance_reward = (renaissance_focus.get_block('completion_reward')
                          if renaissance_focus is not None else None)
    ok(renaissance_reward is not None and
       renaissance_reward.has_assignment('leave_faction', 'yes'),
       'TT_tuvan_renaissance: national independence must leave the faction immediately')

    # Historical AI branch tuning: exact AST parsing of ai_will_do blocks and factors.
    ry_focus = foci_by_id.get('TT_red_yurt')
    ok(ry_focus is not None, 'TT_red_yurt: focus not found in AST')
    if ry_focus:
        ry_ai = ry_focus.get_block('ai_will_do')
        ok(ry_ai is not None, 'TT_red_yurt: missing ai_will_do block')
        if ry_ai:
            ok(ry_ai.get_assignment('factor') == '20',
               f"TT_red_yurt: unexpected ai_will_do base factor: {ry_ai.get_assignment('factor')} (expected 20)")
            ry_mods = ry_ai.find_blocks('modifier')
            ok(len(ry_mods) == 1, f'TT_red_yurt: expected 1 ai_will_do modifier, found {len(ry_mods)}')
            if ry_mods:
                ok(ry_mods[0].get_assignment('factor') == '3',
                   f"TT_red_yurt: expected modifier factor = 3, got {ry_mods[0].get_assignment('factor')}")
                ok(ry_mods[0].get_assignment('is_historical_focus_on') == 'yes',
                   f"TT_red_yurt: expected is_historical_focus_on = yes in modifier, got {ry_mods[0].get_assignment('is_historical_focus_on')}")

    tr_focus = foci_by_id.get('TT_tuvan_renaissance')
    ok(tr_focus is not None, 'TT_tuvan_renaissance: focus not found in AST')
    if tr_focus:
        tr_ai = tr_focus.get_block('ai_will_do')
        ok(tr_ai is not None, 'TT_tuvan_renaissance: missing ai_will_do block')
        if tr_ai:
            ok(tr_ai.get_assignment('factor') == '20',
               f"TT_tuvan_renaissance: unexpected ai_will_do base factor: {tr_ai.get_assignment('factor')} (expected 20)")
            tr_mods = tr_ai.find_blocks('modifier')
            ok(len(tr_mods) == 1, f'TT_tuvan_renaissance: expected 1 ai_will_do modifier, found {len(tr_mods)}')
            if tr_mods:
                ok(tr_mods[0].get_assignment('factor') == '0',
                   f"TT_tuvan_renaissance: expected modifier factor = 0, got {tr_mods[0].get_assignment('factor')}")
                ok(tr_mods[0].get_assignment('is_historical_focus_on') == 'yes',
                   f"TT_tuvan_renaissance: expected is_historical_focus_on = yes in modifier, got {tr_mods[0].get_assignment('is_historical_focus_on')}")

    # Equipment gifts only work if the producer has unlocked the equipment.
    # TAN starts with nothing but basic infantry equipment, so the doctrine
    # and air gifts must prefer a producer that has the kit (SOV, with a GER
    # fallback for legacy CAS I, which the USSR does not start with).
    for fid in ('TT_infantry_and_artillery', 'TT_tanks_of_the_steppe',
                'TT_the_tuvan_air_force', 'TT_wings_of_the_steppe',
                'TT_bombers_over_siberia'):
        ok('producer = SOV' in by_id.get(fid, ''),
           f'{fid}: equipment gift has no producer with the equipment unlocked')
    ok('producer = GER' in by_id.get('TT_wings_of_the_steppe', ''),
       'TT_wings_of_the_steppe: legacy CAS gift lacks its GER producer fallback')
    ok('type = CAS_equipment_1\n' in by_id.get('TT_wings_of_the_steppe', ''),
       'TT_wings_of_the_steppe: legacy gift must use CAS I equipment (case-sensitive CAS_equipment_1)')
    ok('type = cas_equipment_1' not in text,
       'tt_tuva_focus.txt: invalid lowercase cas_equipment_1 found (must be CAS_equipment_1)')
    ok('type = tac_bomber_equipment_1\n' in by_id.get('TT_bombers_over_siberia', ''),
       'TT_bombers_over_siberia: legacy gift must use tactical bomber I equipment')

    # Structural AST verification of TT_wings_of_the_steppe CAS gifts and producer chain
    wings_focus = foci_by_id.get('TT_wings_of_the_steppe')
    ok(wings_focus is not None, 'TT_wings_of_the_steppe: focus not found in AST')
    if wings_focus:
        stockpiles = wings_focus.find_all_blocks('add_equipment_to_stockpile')
        cas_blocks = [eq for eq in stockpiles if eq.get_assignment('type') == 'CAS_equipment_1']
        ok(len(cas_blocks) == 6,
           f'TT_wings_of_the_steppe: expected 6 CAS_equipment_1 stockpile blocks, found {len(cas_blocks)}')
        cas_producers = [b.get_assignment('producer') for b in cas_blocks]
        ok('SOV' in cas_producers, 'TT_wings_of_the_steppe: CAS_equipment_1 lacks SOV producer')
        ok('GER' in cas_producers, 'TT_wings_of_the_steppe: legacy CAS gift lacks its GER producer fallback')
        ok(set(cas_producers) == {'SOV', 'GER', 'USA', 'ENG', 'JAP', 'TAN'},
           f'TT_wings_of_the_steppe: unexpected CAS producer set: {cas_producers}')
        ok(all(b.get_assignment('amount') == '20' for b in cas_blocks),
           'TT_wings_of_the_steppe: all CAS gifts must deliver amount = 20')
        ok(not wings_focus.has_recursive('type', 'cas_equipment_1'),
           'TT_wings_of_the_steppe: invalid lowercase cas_equipment_1 found in AST (must be CAS_equipment_1)')
        bba_blocks = [eq for eq in stockpiles if eq.get_assignment('type') == 'small_plane_airframe_1']
        ok(len(bba_blocks) == 2,
           f'TT_wings_of_the_steppe: expected 2 BBA small plane blocks, found {len(bba_blocks)}')
        ok({b.get_assignment('producer') for b in bba_blocks} == {'SOV', 'TAN'},
           'TT_wings_of_the_steppe: BBA small plane gifts must use SOV and TAN producers')
    # Navy branch endpoint builds dockyards on the coast.
    pac = by_id.get('TT_the_pacific_fleet', '')
    ok('type = dockyard' in pac and 'controls_state = 716' in pac and 'navy_experience' in text,
       'TT_the_pacific_fleet: dockyards in Liaotung / navy XP are missing')


# ------------------------------------------------- 3b. other vanilla graphics
# Exact sprite names verified against the vanilla interface indexes
# (ideas are referenced without the GFX_idea_ prefix in script).
VANILLA_IDEA_PICTURES = {
    'generic_agrarian_society', 'generic_armor', 'generic_army_war_college',
    'generic_build_infrastructure', 'generic_communism_drift_bonus',
    'generic_communist_army', 'generic_economic_increase',
    'generic_exploit_mines', 'generic_fortify_the_borders',
    'generic_infantry_bonus', 'generic_manpower_bonus',
    'generic_monarchist_uprising', 'generic_morale_bonus',
    'generic_political_support', 'generic_production_bonus',
    'generic_reserve_divisions', 'generic_victors_of_ww1',
}
VANILLA_DECISION_ICONS = {
    'GFX_decision_category_generic_political_actions',
    'GFX_decision_eng_propaganda_campaigns',
    'GFX_decision_generic_army_support', 'GFX_decision_generic_cavalry',
    'GFX_decision_generic_civil_support', 'GFX_decision_generic_fundraising',
    'GFX_decision_generic_industry', 'GFX_decision_generic_nationalism',
}
VANILLA_EVENT_PICTURES = {
    'GFX_news_event_generic_army', 'GFX_news_event_generic_parliament',
    'GFX_news_event_generic_rally', 'GFX_news_event_generic_sign_treaty1',
    'GFX_news_event_generic_sign_treaty2',
    'GFX_report_event_generic_communist_congress',
    'GFX_report_event_generic_handshake',
    'GFX_report_event_generic_parliament',
    'GFX_report_event_generic_sign_treaty2',
    'GFX_report_event_generic_stock_traders',
}

# -------------------------------------------------------------- 3c. commanders
EXPECTED_COMMANDERS = {
    'TT_the_peoples_army': {
        'role': 'corps_commander',
        'name': 'Soyan Choodu',
        'skill': 2,
        'attack_skill': 2,
        'defense_skill': 2,
        'planning_skill': 2,
        'logistics_skill': 2,
        'gfx': 'GFX_Portrait_Asia_Generic_land_2',
        'traits': {'career_officer', 'organizer'},
    },
    'TT_cavalry_of_the_steppe': {
        'role': 'corps_commander',
        'name': 'Kyrgys Ezir',
        'skill': 3,
        'attack_skill': 4,
        'defense_skill': 2,
        'planning_skill': 3,
        'logistics_skill': 1,
        'gfx': 'GFX_Portrait_Asia_Generic_land_3',
        'traits': {'cavalry_officer', 'cavalry_leader'},
    },
    'TT_infantry_and_artillery': {
        'role': 'corps_commander',
        'name': 'Mongush Dash',
        'skill': 3,
        'attack_skill': 2,
        'defense_skill': 4,
        'planning_skill': 2,
        'logistics_skill': 3,
        'gfx': 'GFX_Portrait_Asia_Generic_land_4',
        'traits': {'infantry_officer', 'infantry_leader'},
    },
    'TT_tanks_of_the_steppe': {
        'role': 'corps_commander',
        'name': 'Kuzhuget Arslan',
        'skill': 3,
        'attack_skill': 4,
        'defense_skill': 2,
        'planning_skill': 3,
        'logistics_skill': 2,
        'gfx': 'GFX_Portrait_Asia_Generic_land_5',
        'traits': {'armor_officer', 'panzer_leader'},
    },
    'TT_total_mobilization': {
        'role': 'field_marshal',
        'name': 'Sat Mergen',
        'skill': 2,
        'attack_skill': 2,
        'defense_skill': 2,
        'planning_skill': 3,
        'logistics_skill': 3,
        'gfx': 'GFX_Portrait_Asia_Generic_land_1',
        'traits': {'fast_planner', 'logistics_wizard'},
    },
}


def check_commanders() -> None:
    text = (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(encoding='utf-8')
    corps_commanders = re.findall(r'create_corps_commander\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', text)
    field_marshals = re.findall(r'create_field_marshal\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', text)
    ok(len(corps_commanders) == 4, f'expected exactly 4 corps commanders, found {len(corps_commanders)}')
    ok(len(field_marshals) == 1, f'expected exactly 1 field marshal, found {len(field_marshals)}')

    names: list[str] = []
    portraits: list[str] = []

    for fid, exp in EXPECTED_COMMANDERS.items():
        m = re.search(rf'id\s*=\s*{fid}\b.*?(?=focus\s*=\s*\{{|\Z)', text, re.S)
        ok(m is not None, f'{fid}: focus not found')
        if not m:
            continue
        ftext = m.group(0)
        role = exp['role']
        cmd_match = re.search(rf'create_{role}\s*=\s*\{{([^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*)\}}', ftext)
        ok(cmd_match is not None, f'{fid}: create_{role} effect not found in focus')
        if not cmd_match:
            continue
        block = cmd_match.group(1)

        name_m = re.search(r'name\s*=\s*"([^"]+)"', block)
        name = name_m.group(1) if name_m else None
        ok(name == exp['name'], f'{fid}: expected commander name {exp["name"]}, got {name}')
        if name:
            names.append(name)

        gfx_m = re.search(r'gfx\s*=\s*(\S+)', block)
        gfx = gfx_m.group(1) if gfx_m else None
        ok(gfx == exp['gfx'], f'{fid}: expected portrait {exp["gfx"]}, got {gfx}')
        if gfx:
            portraits.append(gfx)

        for s in ['skill', 'attack_skill', 'defense_skill', 'planning_skill', 'logistics_skill']:
            sm = re.search(rf'{s}\s*=\s*(\d+)', block)
            val = int(sm.group(1)) if sm else None
            ok(val == exp[s], f'{fid}: expected {s}={exp[s]}, got {val}')

        tr_m = re.search(r'traits\s*=\s*\{([^}]*)\}', block)
        traits = set(tr_m.group(1).split()) if tr_m else set()
        ok(traits == exp['traits'], f'{fid}: expected traits {exp["traits"]}, got {traits}')

    ok(len(set(names)) == len(names) == 5, f'commander names must be unique without duplicates: {names}')
    ok(len(set(portraits)) == len(portraits) == 5, f'commander portraits must be unique: {portraits}')


def check_graphics() -> None:
    ideas = (ROOT / 'common/ideas/tt_tuva_ideas.txt').read_text(encoding='utf-8')
    found = set(re.findall(r'^\s*picture = (\S+)', ideas, re.M))
    ok(found == VANILLA_IDEA_PICTURES,
       f'idea pictures differ from the validated vanilla set: '
       f'unknown={sorted(found - VANILLA_IDEA_PICTURES)}, '
       f'missing={sorted(VANILLA_IDEA_PICTURES - found)}')
    dec_text = ''.join(
        (ROOT / p).read_text(encoding='utf-8')
        for p in ('common/decisions/tt_tuva_decisions.txt',
                  'common/decisions/categories/tt_tuva_categories.txt'))
    found = set(re.findall(r'^\s*icon = (\S+)', dec_text, re.M))
    ok(found == VANILLA_DECISION_ICONS,
       f'decision icons differ from the validated vanilla set: '
       f'unknown={sorted(found - VANILLA_DECISION_ICONS)}, '
       f'missing={sorted(VANILLA_DECISION_ICONS - found)}')
    events = (ROOT / 'events/tt_tuva_events.txt').read_text(encoding='utf-8')
    found = set(re.findall(r'^\s*picture = (\S+)', events, re.M))
    ok(found == VANILLA_EVENT_PICTURES,
       f'event pictures differ from the validated vanilla set: '
       f'unknown={sorted(found - VANILLA_EVENT_PICTURES)}, '
       f'missing={sorted(VANILLA_EVENT_PICTURES - found)}')


# ------------------------------------------------------------------- 4. events
def check_events(custom_events_text: str | None = None) -> None:
    events_file = ROOT / 'events/tt_tuva_events.txt'
    text = custom_events_text if custom_events_text is not None else events_file.read_text(encoding='utf-8')
    lines = text.split('\n')
    defs: dict[str, str] = {}
    calls: list[tuple[str, str, str]] = []

    def scan(path: Path, lines_in: list[str], definitions_allowed: bool) -> None:
        for i, line in enumerate(lines_in):
            m_def = re.match(r'^(country_event|news_event) = \{', line)
            m_call = re.match(r'^\s+(country_event|news_event) = \{', line)
            if not (m_def or m_call):
                continue
            typ = (m_def or m_call).group(1)
            eid = None
            for j in range(i + 1, min(i + 5, len(lines_in))):
                found = re.search(r'\bid\s*=\s*(tt_tuva\.\d+)\b', lines_in[j])
                if found:
                    eid = found.group(1)
                    break
            if not eid:
                continue
            if m_def and definitions_allowed:
                defs[eid] = typ
            else:
                calls.append((eid, typ, path.relative_to(ROOT).as_posix()))

    scan(events_file, lines, True)
    for p in script_files():
        if p != events_file:
            scan(p, p.read_text(encoding='utf-8').split('\n'), False)

    expected_ids = {f'tt_tuva.{n}' for n in range(1, 17)}
    ok(set(defs) == expected_ids,
       f'event definitions: expected tt_tuva.1..16, got {sorted(defs)}')
    news = sorted((k for k, v in defs.items() if v == 'news_event'),
                  key=lambda s: int(s.split('.')[1]))
    country = sorted((k for k, v in defs.items() if v == 'country_event'),
                     key=lambda s: int(s.split('.')[1]))
    ok(len(news) == 10, f'expected 10 news events, found {len(news)}')
    ok(len(country) == 6, f'expected 6 country events, found {len(country)}')
    ok(news == ['tt_tuva.3', 'tt_tuva.4', 'tt_tuva.6', 'tt_tuva.8', 'tt_tuva.9',
                'tt_tuva.11', 'tt_tuva.13', 'tt_tuva.14', 'tt_tuva.15', 'tt_tuva.16'],
       f'unexpected news event ids: {news}')
    for eid in expected_ids:
        triggered = [c for c in calls if c[0] == eid]
        ok(bool(triggered), f'{eid}: never triggered')
        for _, typ, where in triggered:
            ok(typ == defs.get(eid),
               f'{eid}: triggered as {typ} in {where}, declared as {defs.get(eid)}')
    for eid, typ, where in calls:
        ok(eid in defs, f'{where}: triggers undefined event {eid}')

    ok('GFX_news_event_generic_handshake' not in text,
       'tt_tuva.8: GFX_news_event_generic_handshake does not exist in vanilla')
    # 1.1.4: tt_tuva.7 response-moment safeguards:
    # All game effects in both option A and option B must be inside an outer
    # if = { limit = { country_exists = TAN, TAN = { has_capitulated = no },
    #                  has_capitulated = no, NOT = { has_war_with = TAN } } }.
    ev_root = parse_clausewitz(text)
    ev7_list = [e for e in ev_root.find_blocks('country_event') if e.get_assignment('id') == 'tt_tuva.7']
    ok(len(ev7_list) == 1, 'tt_tuva.7: event definition not found in AST')
    if ev7_list:
        ev7 = ev7_list[0]

        # Verify root trigger of tt_tuva.7
        trig = ev7.get_block('trigger')
        ok(trig is not None, 'tt_tuva.7: root trigger block missing')
        if trig:
            exists_tags = [val for key, op, val in trig.assignments if key == 'country_exists']
            ok('TAN' in exists_tags, 'tt_tuva.7 trigger: missing country_exists = TAN')
            ok('MON' in exists_tags, 'tt_tuva.7 trigger: missing country_exists = MON')
            ok(trig.has_assignment('has_capitulated', 'no'), 'tt_tuva.7 trigger: missing has_capitulated = no')
            tan_t = trig.get_block('TAN')
            ok(tan_t is not None and tan_t.has_assignment('has_capitulated', 'no'),
               'tt_tuva.7 trigger: missing TAN = { has_capitulated = no }')
            not_t = trig.get_block('NOT')
            ok(not_t is not None and not_t.has_assignment('has_war_with', 'TAN'),
               'tt_tuva.7 trigger: missing NOT = { has_war_with = TAN }')

        # Helper to verify full set of response safeguards in limit block
        def verify_option_guard(opt: CWBlock, opt_name: str) -> CWBlock | None:
            if_blocks = opt.find_blocks('if')
            ok(len(if_blocks) == 1, f'{opt_name}: expected exactly 1 outer if guard block, found {len(if_blocks)}')
            if not if_blocks:
                return None
            guard = if_blocks[0]
            lim = guard.get_block('limit')
            ok(lim is not None, f'{opt_name}: missing limit block inside guarded if')
            if lim:
                ok(lim.get_assignment('country_exists') == 'TAN',
                   f'{opt_name}: limit missing country_exists = TAN')
                tan_b = lim.get_block('TAN')
                ok(tan_b is not None and tan_b.get_assignment('has_capitulated') == 'no',
                   f'{opt_name}: limit missing TAN = {{ has_capitulated = no }}')
                ok(lim.get_assignment('has_capitulated') == 'no',
                   f'{opt_name}: limit missing has_capitulated = no')
                not_b = lim.get_block('NOT')
                ok(not_b is not None and not_b.get_assignment('has_war_with') == 'TAN',
                   f'{opt_name}: limit missing NOT = {{ has_war_with = TAN }}')
            return guard

        # Option A checks: leave_faction, annex_country and news_event inside guarded if block
        opt_a_list = [o for o in ev7.find_blocks('option') if o.get_assignment('name') == 'tt_tuva.7.a']
        ok(len(opt_a_list) == 1, 'tt_tuva.7.a: option A not found in AST')
        if opt_a_list:
            opt_a = opt_a_list[0]
            ga = verify_option_guard(opt_a, 'tt_tuva.7.a')
            if ga:
                ok(ga.has_assignment('leave_faction', 'yes'),
                   'tt_tuva.7.a: leave_faction = yes must be nested inside guarded if')
                ok(ga.has_recursive('annex_country'),
                   'tt_tuva.7.a: annex_country must be nested inside guarded if')
                news_a = [b for b in ga.find_all_blocks('news_event') if b.get_assignment('id') == 'tt_tuva.8']
                ok(len(news_a) == 1,
                   'tt_tuva.7.a: news_event tt_tuva.8 must be nested inside guarded if')
                ok(not opt_a.has_assignment('leave_faction'),
                   'tt_tuva.7.a: leave_faction must not appear outside the guard block')
                ok(not any(b.key == 'annex_country' or b.has_recursive('annex_country') for b in opt_a.blocks if b is not ga),
                   'tt_tuva.7.a: annex_country must not appear outside the guard block')
                ok(not any(b.key == 'news_event' or b.has_recursive('news_event') for b in opt_a.blocks if b is not ga) and
                   not opt_a.has_assignment('news_event'),
                   'tt_tuva.7.a: news_event must not appear outside the guard block')

        # Option B checks: leave_faction, create_wargoal and news_event inside guarded if block
        opt_b_list = [o for o in ev7.find_blocks('option') if o.get_assignment('name') == 'tt_tuva.7.b']
        ok(len(opt_b_list) == 1, 'tt_tuva.7.b: option B not found in AST')
        if opt_b_list:
            opt_b = opt_b_list[0]
            gb = verify_option_guard(opt_b, 'tt_tuva.7.b')
            if gb:
                ok(gb.has_assignment('leave_faction', 'yes'),
                   'tt_tuva.7.b: leave_faction = yes must be nested inside guarded if')
                ok(gb.has_recursive('create_wargoal'),
                   'tt_tuva.7.b: create_wargoal must be nested inside guarded if')
                news_b = [b for b in gb.find_all_blocks('news_event') if b.get_assignment('id') == 'tt_tuva.9']
                ok(len(news_b) == 1,
                   'tt_tuva.7.b: news_event tt_tuva.9 must be nested inside guarded if')
                ok(not opt_b.has_assignment('leave_faction'),
                   'tt_tuva.7.b: leave_faction must not appear outside the guard block')
                ok(not any(b.key == 'create_wargoal' or b.has_recursive('create_wargoal') for b in opt_b.blocks if b is not gb),
                   'tt_tuva.7.b: create_wargoal must not appear outside the guard block')
                ok(not any(b.key == 'news_event' or b.has_recursive('news_event') for b in opt_b.blocks if b is not gb) and
                   not opt_b.has_assignment('news_event'),
                   'tt_tuva.7.b: news_event must not appear outside the guard block')
                nested_ifs = gb.find_all_blocks('if')
                ok(len(nested_ifs) == 0,
                   'tt_tuva.7.b: redundant nested if block found inside guard')
    block = text.split('id = tt_tuva.10')[1].split('id = tt_tuva.11')[0]
    ok(block.index('every_state') < block.index('white_peace = TAN'),
       'tt_tuva.10.a: every_state must run before white_peace')
    ok('is_controlled_by = TAN' in block,
       'tt_tuva.10.a: missing is_controlled_by = TAN in every_state limit')
    states12 = [402, 404, 405, 406, 407, 583, 584, 585, 586, 587, 588, 589,
                590, 732, 742, 823, 830, 831, 832, 881, 882]
    block12 = text.split('id = tt_tuva.12')[1].split('id = tt_tuva.13')[0]
    found12 = [int(s) for s in re.findall(r'^\s*state = (\d+)', block12, re.M)]
    ok(found12 == states12, f'tt_tuva.12: Central Asian state list mismatch: {found12}')
    # The Central Asian SSR must not exist before Moscow answers: the focus
    # only self-proclaims it when there is no USSR to ask, and the approval
    # option of tt_tuva.12 grants the same name/spirit/cores on acceptance.
    approve12 = block12.split('# Option B')[0]
    focus_text = (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(
        encoding='utf-8')
    ca_focus = focus_text.split('id = TT_form_central_asian_ssr')[1].split(
        '\n\tfocus = {')[0]
    ok(ca_focus.index('id = tt_tuva.12') < ca_focus.index('set_cosmetic_tag'),
       'TT_form_central_asian_ssr: rewards must not precede the request to Moscow')
    ok('set_cosmetic_tag = TT_central_asian_ssr' in approve12 and
       'add_ideas = TT_central_asian_ssr_spirit' in approve12,
       'tt_tuva.12 approval: Central Asian SSR rewards are missing')
    cores = lambda txt: [int(s) for s in re.findall(r'add_state_core = (\d+)', txt)]
    ok(cores(ca_focus) == states12,
       f'TT_form_central_asian_ssr: core list mismatch: {cores(ca_focus)}')
    ok(cores(approve12) == states12,
       f'tt_tuva.12 approval: core list mismatch: {cores(approve12)}')


# --------------------------------------------------------------------- 5. flags
FLAG_SIZES = {'': (82, 52, 17100), 'medium': (41, 26, 4308), 'small': (10, 7, 324)}
FLAG_STEMS = ('TT_tuvan_khanate', 'TT_tuvan_empire', 'TT_central_asian_ssr')


def check_flags() -> None:
    total = 0
    for folder, (w, h, expected_len) in FLAG_SIZES.items():
        base = ROOT / 'gfx/flags' / folder if folder else ROOT / 'gfx/flags'
        for stem in FLAG_STEMS:
            suffixes = ('_neutrality',) if stem != 'TT_central_asian_ssr' else ('_communism',)
            for suffix in ('', *suffixes):
                p = base / f'{stem}{suffix}.tga'
                rel = p.relative_to(ROOT).as_posix()
                ok(p.exists(), f'{rel}: missing flag')
                if not p.exists():
                    continue
                total += 1
                b = p.read_bytes()
                ok(len(b) == expected_len,
                   f'{rel}: {len(b)} bytes, expected {expected_len}')
                ok(len(b) >= 44, f'{rel}: too short for a TGA header/footer')
                if len(b) < 44:
                    continue
                idlen, cmap, itype = b[0], b[1], b[2]
                cm_spec = b[3:8]
                xorig, yorig, bw, bh, bpp, desc = struct.unpack('<HHHHBB', b[8:18])
                ok((idlen, cmap, itype) == (0, 0, 2),
                   f'{rel}: not an uncompressed type-2 true-colour TGA')
                ok(cm_spec == b'\x00' * 5, f'{rel}: unexpected colour-map specification')
                ok((xorig, yorig) == (0, 0), f'{rel}: unexpected image origin')
                ok((bw, bh) == (w, h), f'{rel}: {bw}x{bh}, expected {w}x{h}')
                ok(bpp == 32, f'{rel}: {bpp} bpp, expected 32-bit BGRA')
                ok(desc == 8, f'{rel}: image descriptor {desc}, expected 8 (8-bit alpha)')
                ok(b[-26:] == TGA_FOOTER, f'{rel}: missing TRUEVISION-XFILE footer')
                ok(len(b) == 18 + w * h * 4 + 26,
                   f'{rel}: pixel data length does not match the header')
    ok(total == 18, f'expected 18 TGA flags, found {total}')


# --------------------------------------------------------- 6. other regressions
def check_misc() -> None:
    cosmetic = (ROOT / 'common/countries/tt_tuva_cosmetic.txt').read_text(encoding='utf-8')
    for tag in FLAG_STEMS:
        ok(re.search(rf'^{tag} = \{{', cosmetic, re.M) is not None,
           f'cosmetic tag {tag} is not declared')
    ok('rgb { 178 34 34 }' in cosmetic, 'TT_central_asian_ssr: wrong colour')

    ideas = (ROOT / 'common/ideas/tt_tuva_ideas.txt').read_text(encoding='utf-8')
    ok('generic_nationalization' not in ideas, 'ideas: generic_nationalization still used')
    ok(ideas.count('picture = generic_morale_bonus') == 2,
       'ideas: expected two generic_morale_bonus icons')
    mm = ideas.split('TT_masters_of_manchuria = {')[1].split('\n\t\t}')[0]
    ok('army_org_factor = 0.05' in mm, 'TT_masters_of_manchuria: army_org_factor missing')
    # 1.1.0: the khanate chain keeps neutrality growing daily and removes the
    # non-aligned 50% world-tension threshold for justifying war goals.
    ok('neutrality_drift = 0.03' in ideas and 'neutrality_drift = 0.08' in ideas,
       'khanate chain: neutrality drift is missing')
    ok(ideas.count('generate_wargoal_tension = -0.5') == 3,
       'khanate chain: expected generate_wargoal_tension = -0.5 on three spirits')
    sc = ideas.split('TT_steppe_cavalry = {')[1].split('\n\t\t}')[0]
    ok('army_org_factor' not in sc,
       'TT_steppe_cavalry: doctrine spirit must not duplicate the army base spirit')
    # Country-scope unit-category modifiers need the army_ prefix (unlike
    # cavalry_*): the bare infantry_/artillery_/armor_ names are not modifiers
    # and would be silently ignored by the game.
    for wrong in ('\n\t\t\t\tinfantry_attack_factor', '\n\t\t\t\tinfantry_defence_factor',
                  '\n\t\t\t\tartillery_attack_factor', '\n\t\t\t\tarmor_attack_factor',
                  '\n\t\t\t\tarmor_defence_factor'):
        ok(wrong not in ideas, f'ideas: invalid modifier name {wrong.strip()}')
    for right in ('army_infantry_attack_factor = 0.10',
                  'army_infantry_defence_factor = 0.10',
                  'army_artillery_attack_factor = 0.15',
                  'army_armor_attack_factor = 0.15',
                  'army_armor_defence_factor = 0.10'):
        ok(right in ideas, f'ideas: missing modifier {right}')
    # The stacking military spirits must reproduce the old cumulative chain:
    # organisation +15% in total (5% army + 5% mission + 5% mountain troops),
    # so the mobilization spirit itself adds no organisation.
    mob = ideas.split('TT_mobilization = {')[1].split('\n\t\t}')[0]
    ok('army_org_factor' not in mob,
       'TT_mobilization: stacking spirits would exceed the old +15% organisation')

    dec = (ROOT / 'common/decisions/tt_tuva_decisions.txt').read_text(encoding='utf-8')
    kh = dec.split('TT_convene_the_khural = {')[1].split('\n\t}')[0]
    ok('cost = 25' in kh and 'add_political_power = 75' in kh and
       'add_war_support = 0.05' in kh and 'generic_skip_one_line_tt' in kh,
       'TT_convene_the_khural: cost/effects are wrong')
    off = dec.split('TT_launch_manchurian_offensive = {')[1].split('\n\t}')[0]
    ok('NOT = { has_idea = TT_masters_of_manchuria }' in off,
       'TT_launch_manchurian_offensive: decision is not hidden after the victory')
    vic = dec.split('TT_proclaim_manchurian_victory = {')[1].split('\n\t}')[0]
    ok('highlight_states' in vic and all(f'state = {s}' in vic for s in (328, 610, 716)),
       'TT_proclaim_manchurian_victory: target states are not highlighted')
    # 1.1.0 decisions: repeatable building slot and repeatable neutrality support.
    zones = dec.split('TT_develop_industrial_zones = {')[1].split('\n\t}')[0]
    ok('add_extra_state_shared_building_slots = 1' in zones and 'days_re_enable = 90' in zones,
       'TT_develop_industrial_zones: repeatable slot effect is missing')
    rally = dec.split('TT_rally_the_clans = {')[1].split('\n\t}')[0]
    ok('has_government = neutrality' in rally and 'ideology = neutrality' in rally,
       'TT_rally_the_clans: neutrality popularity decision is missing')

    # Descriptors live inside the repository: the launcher descriptor at the
    # root (with the mod/ path) and the internal descriptor.mod. Both must
    # carry the current release version.
    ext = ROOT / 'tuva_center_of_asia.mod'
    ok(ext.exists(), 'tuva_center_of_asia.mod: external descriptor missing')
    if ext.exists():
        mod_text = ext.read_text(encoding='utf-8')
        ok('path="mod/tuva_center_of_asia"' in mod_text,
           'tuva_center_of_asia.mod: wrong path')
        ok('version="1.1.4"' in mod_text, 'tuva_center_of_asia.mod: version is not 1.1.4')
    desc = ROOT / 'descriptor.mod'
    ok(desc.exists(), 'descriptor.mod: missing')
    if desc.exists():
        ok('version="1.1.4"' in desc.read_text(encoding='utf-8'), 'descriptor.mod: version is not 1.1.4')
    ok((ROOT / 'docs/focus_tree_preview.png').exists() and
       not (ROOT / 'focus_tree_preview.png').exists(),
       'focus_tree_preview.png must live in docs/')
    ga = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    ok('docs/ export-ignore' in ga, '.gitattributes: docs/ export-ignore missing')


# -------------------------------------------------------- 7. mutation tests
def run_mutation_tests(verbose: bool = True) -> bool:
    """Run in-memory mutation tests verifying that AST checks catch broken structures.

    Performs mutations entirely in memory without modifying any files on disk.
    """
    global errors, checks
    orig_errors = list(errors)
    orig_checks = checks

    results: list[tuple[str, bool, str]] = []

    def test_mutation(name: str, fn, arg, expected_msg_part: str) -> None:
        global errors
        errors = []
        fn(arg)
        caught = any(expected_msg_part in e for e in errors)
        sample_msg = next((e for e in errors if expected_msg_part in e), errors[0] if errors else 'No error captured')
        results.append((name, caught, sample_msg))

    events_txt = (ROOT / 'events/tt_tuva_events.txt').read_text(encoding='utf-8')
    focus_txt = (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(encoding='utf-8')

    # Mutation 1: War check removed from option A guard in tt_tuva.7
    target_1 = (
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\tTAN = { has_capitulated = no }\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t\tNOT = { has_war_with = TAN }\n"
        "\t\t\t}\n"
        "\t\t\tleave_faction = yes\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tannex_country = {"
    )
    mut_1 = (
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\tTAN = { has_capitulated = no }\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t}\n"
        "\t\t\tleave_faction = yes\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tannex_country = {"
    )
    test_mutation(
        "Mutation 1 (War check removed from option A guard in tt_tuva.7)",
        check_events,
        events_txt.replace(target_1, mut_1),
        "tt_tuva.7.a: limit missing NOT = { has_war_with = TAN }"
    )

    # Mutation 2: TAN capitulation check removed from option B guard in tt_tuva.7
    target_2 = (
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\tTAN = { has_capitulated = no }\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t\tNOT = { has_war_with = TAN }\n"
        "\t\t\t}\n"
        "\t\t\tleave_faction = yes\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tcreate_wargoal = {"
    )
    mut_2 = (
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t\tNOT = { has_war_with = TAN }\n"
        "\t\t\t}\n"
        "\t\t\tleave_faction = yes\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tcreate_wargoal = {"
    )
    test_mutation(
        "Mutation 2 (TAN capitulation check removed from option B guard in tt_tuva.7)",
        check_events,
        events_txt.replace(target_2, mut_2),
        "tt_tuva.7.b: limit missing TAN = { has_capitulated = no }"
    )

    # Mutation 3a: news_event moved outside guard in tt_tuva.7.b
    target_3a = (
        "\t\t\tTAN = {\n"
        "\t\t\t\tcreate_wargoal = {\n"
        "\t\t\t\t\ttype = annex_everything\n"
        "\t\t\t\t\ttarget = MON\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t\tnews_event = {\n"
        "\t\t\t\tid = tt_tuva.9\n"
        "\t\t\t\tdays = 1\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\t}"
    )
    mut_3a = (
        "\t\t\tTAN = {\n"
        "\t\t\t\tcreate_wargoal = {\n"
        "\t\t\t\t\ttype = annex_everything\n"
        "\t\t\t\t\ttarget = MON\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t}\n"
        "\t\tnews_event = {\n"
        "\t\t\tid = tt_tuva.9\n"
        "\t\t\tdays = 1\n"
        "\t\t}\n"
        "\t}"
    )
    test_mutation(
        "Mutation 3a (news_event moved outside guard in tt_tuva.7.b)",
        check_events,
        events_txt.replace(target_3a, mut_3a),
        "tt_tuva.7.b: news_event must not appear outside the guard block"
    )

    # Mutation 3b: leave_faction moved outside guard in tt_tuva.7.a
    target_3b = (
        "\t\tif = {\n"
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\tTAN = { has_capitulated = no }\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t\tNOT = { has_war_with = TAN }\n"
        "\t\t\t}\n"
        "\t\t\tleave_faction = yes\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tannex_country = {"
    )
    mut_3b = (
        "\t\tleave_faction = yes\n"
        "\t\tif = {\n"
        "\t\t\tlimit = {\n"
        "\t\t\t\tcountry_exists = TAN\n"
        "\t\t\t\tTAN = { has_capitulated = no }\n"
        "\t\t\t\thas_capitulated = no\n"
        "\t\t\t\tNOT = { has_war_with = TAN }\n"
        "\t\t\t}\n"
        "\t\t\tTAN = {\n"
        "\t\t\t\tannex_country = {"
    )
    test_mutation(
        "Mutation 3b (leave_faction moved outside guard in tt_tuva.7.a)",
        check_events,
        events_txt.replace(target_3b, mut_3b),
        "tt_tuva.7.a: leave_faction must not appear outside the guard block"
    )

    # Mutation C: modifier factor changed in TT_red_yurt ai_will_do
    target_c = "\t\tai_will_do = {\n\t\t\tfactor = 20\n\t\t\tmodifier = {\n\t\t\t\tfactor = 3"
    mut_c = "\t\tai_will_do = {\n\t\t\tfactor = 20\n\t\t\tmodifier = {\n\t\t\t\tfactor = 99"
    test_mutation(
        "Mutation C (modifier factor in TT_red_yurt ai_will_do changed)",
        check_focuses,
        focus_txt.replace(target_c, mut_c),
        "TT_red_yurt: expected modifier factor = 3"
    )

    # Mutation D: TT_wings_of_the_steppe CAS GER producer changed
    target_d = "type = CAS_equipment_1\n\t\t\t\t\t\tamount = 20\n\t\t\t\t\t\tproducer = GER"
    mut_d = "type = CAS_equipment_1\n\t\t\t\t\t\tamount = 20\n\t\t\t\t\t\tproducer = ITA"
    test_mutation(
        "Mutation D (TT_wings_of_the_steppe CAS GER producer missing)",
        check_focuses,
        focus_txt.replace(target_d, mut_d),
        "TT_wings_of_the_steppe: legacy CAS gift lacks its GER producer fallback"
    )

    # Removing the early exit must be caught even though the khanate still exits.
    target_exit = "\t\t\tleave_faction = yes\n\t\t\tset_country_flag = TT_national_path"
    test_mutation(
        "Mutation E (national-path faction exit removed)",
        check_focuses,
        focus_txt.replace(target_exit, "\t\t\tset_country_flag = TT_national_path"),
        "TT_tuvan_renaissance: national independence must leave the faction immediately"
    )

    # Restore globals
    errors = orig_errors
    checks = orig_checks

    all_ok = all(passed for _, passed, _ in results)
    if verbose:
        print("Mutation Testing Suite Results:")
        for name, passed, msg in results:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}")
            print(f"         Caught error: {msg}")
        if all_ok:
            print(f"All {len(results)} mutation tests passed: deliberate syntax corruptions caught by AST checks.")
        else:
            print("Mutation test failures detected!")

    return all_ok


def check_mutations() -> None:
    """Validate that mutation tests pass and AST checks catch corruptions."""
    all_ok = run_mutation_tests(verbose=False)
    ok(all_ok, "mutation testing: all in-memory AST mutations were caught as expected")


def main() -> int:
    if '--mutation-test' in sys.argv or '-m' in sys.argv:
        success = run_mutation_tests(verbose=True)
        return 0 if success else 1

    check_encodings()
    check_localisation()
    check_focuses()
    check_commanders()
    check_graphics()
    check_events()
    check_flags()
    check_misc()
    check_mutations()
    print(f'Ran {checks} checks.')
    if errors:
        print(f'FAILED: {len(errors)} problem(s):')
        for e in errors:
            print(f'  - {e}')
        return 1
    print('OK: all checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
