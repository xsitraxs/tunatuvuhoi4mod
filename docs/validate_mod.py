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
    # 1.1.0 doctrine / air / navy focuses (generic army, air and navy sprites).
    'GFX_focus_generic_army_artillery', 'GFX_focus_generic_army_tanks',
    'GFX_focus_generic_CAS', 'GFX_focus_generic_air_bomber',
    'GFX_focus_generic_build_navy', 'GFX_focus_generic_navy_doctrines_tactics',
    'GFX_focus_generic_navy_battleship',
}
# Sprites that are known not to exist (or to have no _shine counterpart) in vanilla.
BAD_ICONS = {
    'GFX_focus_generic_asia_liberation', 'GFX_focus_generic_stalinist_industry',
    'GFX_focus_generic_communist_asia', 'GFX_focus_generic_printing_press',
    'GFX_focus_generic_army_attack', 'GFX_focus_generic_modernizing_agriculture',
    'GFX_focus_generic_mineral_prospecting', 'GFX_focus_generic_expand_gold_mining',
    'GFX_focus_generic_advisors', 'GFX_focus_generic_mountain_troops',
}


def check_focuses() -> None:
    text = (ROOT / 'common/national_focus/tt_tuva_focus.txt').read_text(encoding='utf-8')
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
    ok(all(i.startswith('GFX_focus_generic_') for i in icons),
       'every icon must be a GFX_focus_generic_* sprite (with a _shine counterpart)')
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
    # Land/air/navy branch roots accept any of the three doctrines (OR prerequisites).
    ok(text.count('prerequisite = { focus = TT_infantry_and_artillery }') == 3,
       'land/air/navy branch roots must each accept any doctrine')
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
    ok('custom_effect_tooltip = TT_war_declaration_tt' in by_id.get('TT_the_second_khanate', ''),
       'TT_the_second_khanate: war-declaration tooltip is missing')
    # Navy branch endpoint builds dockyards on the coast.
    pac = by_id.get('TT_the_pacific_fleet', '')
    ok('type = dockyard' in pac and 'controls_state = 716' in pac and 'navy_experience' in text,
       'TT_the_pacific_fleet: dockyards in Liaotung / navy XP are missing')


# ------------------------------------------------------------------- 4. events
def check_events() -> None:
    events_file = ROOT / 'events/tt_tuva_events.txt'
    lines = events_file.read_text(encoding='utf-8').split('\n')
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

    text = events_file.read_text(encoding='utf-8')
    ok('GFX_news_event_generic_handshake' not in text,
       'tt_tuva.8: GFX_news_event_generic_handshake does not exist in vanilla')
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

    ext = ROOT / 'tuva_center_of_asia.mod'
    ok(ext.exists(), 'tuva_center_of_asia.mod: external descriptor missing')
    if ext.exists():
        ok('path="mod/tuva_center_of_asia"' in ext.read_text(encoding='utf-8'),
           'tuva_center_of_asia.mod: wrong path')
    ok((ROOT / 'docs/focus_tree_preview.png').exists() and
       not (ROOT / 'focus_tree_preview.png').exists(),
       'focus_tree_preview.png must live in docs/')
    ga = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    ok('docs/ export-ignore' in ga, '.gitattributes: docs/ export-ignore missing')


def main() -> int:
    check_encodings()
    check_localisation()
    check_focuses()
    check_events()
    check_flags()
    check_misc()
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
