#!/usr/bin/env python3
"""Stdlib-only checks for the completed heraldic DDS assets and source manifest."""
import ast
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]


def main():
    tree = ast.parse((ROOT/'docs/generate_focus_icons.py').read_text(encoding='utf-8'))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FOCUS_IDS', 'PAINTED_SOURCES', 'EMBLEM_GROUPS'):
                    constants[target.id] = ast.literal_eval(node.value)
    sources = constants['PAINTED_SOURCES']
    assert len(sources) == 36 and set(sources) == set(constants['FOCUS_IDS']), 'Expected all 36 painted focuses'
    assert len(set(sources.values())) == len(sources), 'Painted sources must be distinct'
    groups = constants['EMBLEM_GROUPS']
    grouped = [fid for ids in groups.values() for fid in ids]
    assert len(groups) == 6 and len(grouped) == 36 and set(grouped) == set(sources), 'Emblem assignments'
    for group in groups:
        assert Path(group).name == group, 'Invalid emblem name'
        source = ROOT/'docs/icon_studies/emblems'/f'{group}.png'
        data = source.read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n', f'{group}: expected PNG source'
        width, height = struct.unpack_from('>II', data, 16)
        assert 0 < width <= 640 and 0 < height <= 640, f'{group}: emblem source size'

    for fid, filename in sources.items():
        assert Path(filename).name == filename, f'{fid}: source must be a plain filename'
        assert (ROOT/'docs/icon_studies'/filename).is_file(), f'{fid}: source missing'
        data = (ROOT/'gfx/interface/goals/tt_tuva'/f'{fid}.dds').read_bytes()
        assert data[:4] == b'DDS ', f'{fid}: DDS magic'
        height, width, pitch = struct.unpack_from('<III', data, 12)
        assert (width, height, pitch) == (95, 85, 380), f'{fid}: dimensions/pitch'
        assert len(data) == 128+95*85*4, f'{fid}: expected uncompressed pixels'
        assert struct.unpack_from('<IIIII', data, 88) == (
            32, 0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000), f'{fid}: expected BGRA32'
        pixels = list(struct.iter_unpack('BBBB', data[128:]))
        border = pixels[:95]+pixels[-95:]+pixels[::95]+pixels[94::95]
        assert all(a == 0 for b,g,r,a in border), f'{fid}: silhouette clipped at border'
        assert any(a == 255 for b,g,r,a in pixels), f'{fid}: no opaque foreground'
        assert not any(a > 32 and min(r,b)-g > 80 for b,g,r,a in pixels), f'{fid}: magenta residue'
    print(f'OK: {len(sources)} painted icons + 6 heraldic structures: manifests, BGRA32 DDS, transparent borders, no strong magenta residue.')


if __name__ == '__main__':
    main()
