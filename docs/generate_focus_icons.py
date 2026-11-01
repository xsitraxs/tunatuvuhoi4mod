#!/usr/bin/env python3
"""Rebuild all 36 heraldic Tuva focus icons (not needed by the game).

Optional art-build dependency: Pillow 13.0.0. The validator remains stdlib-only.
Install: python -m pip install Pillow==13.0.0
Run: python docs/generate_focus_icons.py
AI-assisted illustration sources and provenance: docs/icon_studies/README.md.
No vanilla textures are copied. No image generation or network access is needed to rebuild.
"""
from __future__ import annotations
from pathlib import Path
import re
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'gfx/interface/goals/tt_tuva'
SIZE = (95, 85)

# Explicit ordered manifest: stable artwork assignment, independent of tree layout.
FOCUS_IDS = ['center_of_asia','the_great_khural','red_yurt','the_soviet_arsenal','the_siberian_military_district','the_red_banner_over_asia','form_central_asian_ssr','the_battle_for_manchuria','tuvan_renaissance','the_second_khanate','the_great_khan','the_empire_of_the_steppe','first_five_year_plan','collective_herds','kyzyl_industries','mineral_prospecting','the_kyzyl_railroad','the_yenisei_dam','the_golden_hoard','the_peoples_army','cavalry_of_the_steppe','soviet_advisors','mountain_warfare','the_tuvan_air_force','total_mobilization','infantry_and_artillery','tanks_of_the_steppe','wings_of_the_steppe','bombers_over_siberia','the_yenisei_flotilla','kyzyl_naval_school','the_pacific_fleet','claims_on_the_steppe','the_mongolian_question','greater_tuva','the_siberian_gambit']


def gfx_entry(fid):
    name='GFX_TT_focus_'+fid
    texture='gfx/interface/goals/tt_tuva/'+fid+'.dds'
    result=f'\tspriteType = {{\n\t\tname = "{name}"\n\t\ttexturefile = "{texture}"\n\t}}\n'
    result+=f'\tspriteType = {{\n\t\tname = "{name}_shine"\n\t\ttexturefile = "{texture}"\n\t\teffectFile = "gfx/FX/buttonstate.lua"\n\t\tlegacy_lazy_load = no\n'
    for rotation in (-90,90):
        result+=f'''\t\tanimation = {{
			animationmaskfile = "{texture}"
			animationtexturefile = "gfx/interface/goals/shine_overlay.dds"
			animationrotation = {rotation}.0
			animationlooping = no
			animationtime = 0.75
			animationdelay = 0
			animationblendmode = "add"
			animationtype = "scrolling"
			animationrotationoffset = {{ x = 0.0 y = 0.0 }}
			animationtexturescale = {{ x = 1.0 y = 1.0 }}
		}}
'''
    return result+'\t}\n'


# Every focus has a source; rebuilding cannot fall back to old medallions.
PAINTED_SOURCES = {
    'red_yurt': 'red_yurt_gemini_source.png',
    'kyzyl_industries': 'industry_source.png',
    'cavalry_of_the_steppe': 'cavalry_source.png',
    'center_of_asia': 'center_of_asia_source.png',
    'form_central_asian_ssr': 'form_central_asian_ssr_source.png',
    'the_battle_for_manchuria': 'the_battle_for_manchuria_source.png',
    'the_great_khan': 'the_great_khan_source.png',
    'the_great_khural': 'the_great_khural_source.png',
    'the_red_banner_over_asia': 'the_red_banner_over_asia_source.png',
    'the_second_khanate': 'the_second_khanate_source.png',
    'the_siberian_military_district': 'the_siberian_military_district_source.png',
    'the_soviet_arsenal': 'the_soviet_arsenal_source.png',
    'tuvan_renaissance': 'tuvan_renaissance_source.png',
    'collective_herds': 'collective_herds_source.png',
    'first_five_year_plan': 'first_five_year_plan_source.png',
    'mineral_prospecting': 'mineral_prospecting_source.png',
    'mountain_warfare': 'mountain_warfare_source.png',
    'soviet_advisors': 'soviet_advisors_source.png',
    'the_empire_of_the_steppe': 'the_empire_of_the_steppe_source.png',
    'the_golden_hoard': 'the_golden_hoard_source.png',
    'the_kyzyl_railroad': 'the_kyzyl_railroad_source.png',
    'the_peoples_army': 'the_peoples_army_source.png',
    'the_yenisei_dam': 'the_yenisei_dam_source.png',
    'bombers_over_siberia': 'bombers_over_siberia_source.png',
    'claims_on_the_steppe': 'claims_on_the_steppe_source.png',
    'infantry_and_artillery': 'infantry_and_artillery_source.png',
    'kyzyl_naval_school': 'kyzyl_naval_school_source.png',
    'tanks_of_the_steppe': 'tanks_of_the_steppe_source.png',
    'the_pacific_fleet': 'the_pacific_fleet_source.png',
    'the_tuvan_air_force': 'the_tuvan_air_force_source.png',
    'the_yenisei_flotilla': 'the_yenisei_flotilla_source.png',
    'total_mobilization': 'total_mobilization_source.png',
    'wings_of_the_steppe': 'wings_of_the_steppe_source.png',
    'greater_tuva': 'greater_tuva_source.png',
    'the_mongolian_question': 'the_mongolian_question_source.png',
    'the_siberian_gambit': 'the_siberian_gambit_source.png',
}


# Six original heraldic structures, composed with a different subject per focus.
EMBLEM_GROUPS = {
    'political': ['center_of_asia','the_great_khural','red_yurt','tuvan_renaissance',
                  'the_second_khanate','the_great_khan','the_empire_of_the_steppe'],
    'industry': ['the_soviet_arsenal','first_five_year_plan','collective_herds','kyzyl_industries',
                 'mineral_prospecting','the_kyzyl_railroad','the_yenisei_dam','the_golden_hoard'],
    'army': ['the_siberian_military_district','the_red_banner_over_asia',
             'the_battle_for_manchuria','the_peoples_army','cavalry_of_the_steppe','soviet_advisors',
             'mountain_warfare','total_mobilization','infantry_and_artillery','tanks_of_the_steppe'],
    'air': ['the_tuvan_air_force','wings_of_the_steppe','bombers_over_siberia'],
    'naval': ['the_yenisei_flotilla','kyzyl_naval_school','the_pacific_fleet'],
    'territory': ['form_central_asian_ssr','claims_on_the_steppe','the_mongolian_question',
                  'greater_tuva','the_siberian_gambit'],
}


def heraldic_icon(fid):
    """Build a compact metal emblem rather than a miniature landscape painting."""
    scale = 4
    w,h = SIZE[0]*scale,SIZE[1]*scale
    group = next(name for name,ids in EMBLEM_GROUPS.items() if fid in ids)
    frame = keyed_art(f'emblems/{group}.png').copy()
    frame.thumbnail((89*scale,79*scale),Image.Resampling.LANCZOS)
    image = Image.new('RGBA',(w,h))
    image.alpha_composite(frame,((w-frame.width)//2,(h-frame.height)//2))
    subject = keyed_art(PAINTED_SOURCES[fid]).copy()
    subject = ImageEnhance.Color(subject).enhance(.88)
    subject = ImageEnhance.Contrast(subject).enhance(1.14)
    subject.thumbnail((70*scale,58*scale),Image.Resampling.LANCZOS)
    subject = subject.filter(ImageFilter.UnsharpMask(radius=1.4,percent=125,threshold=3))
    px = (w-subject.width)//2
    py = (h-subject.height)//2-scale
    # A narrow dark raised-relief edge keeps unlike materials readable on the plate.
    silhouette = Image.new('L',(w,h))
    silhouette.paste(subject.getchannel('A'),(px,py))
    shadow = Image.new('RGBA',(w,h),(4,8,10,0))
    shadow.putalpha(silhouette.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.8)))
    image.alpha_composite(shadow)
    image.alpha_composite(subject,(px,py))
    image = image.resize(SIZE,Image.Resampling.LANCZOS)
    for x in range(SIZE[0]):
        image.putpixel((x,0),(0,0,0,0));image.putpixel((x,SIZE[1]-1),(0,0,0,0))
    for y in range(SIZE[1]):
        image.putpixel((0,y),(0,0,0,0));image.putpixel((SIZE[0]-1,y),(0,0,0,0))
    return image


@lru_cache(maxsize=48)
def keyed_art(filename):
    """Extract a reusable high-resolution subject or emblem from magenta."""
    with Image.open(ROOT/'docs/icon_studies'/filename) as source:
        source = source.convert('RGB')
    pixels = []
    for r,g,b in source.get_flattened_data():
        chroma = min(r,b)-g
        alpha = max(0., min(1., (150-chroma)/100))
        if alpha == 0:
            pixels.append((0,0,0,0))
        elif alpha == 1:
            pixels.append((r,g,b,255))
        else:
            # Unmix the solid magenta backing instead of leaving a purple halo.
            unkey = lambda value,key: max(0,min(255,round((value-key*(1-alpha))/alpha)))
            pixels.append((unkey(r,255),unkey(g,0),unkey(b,255),round(alpha*255)))
    rgba = Image.new('RGBA', source.size)
    rgba.putdata(pixels)
    bounds = rgba.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()
    if bounds is None:
        raise ValueError(f'{filename}: no foreground after colour-key extraction')
    return rgba.crop(bounds)


def main():
    if len(FOCUS_IDS) != 36 or set(PAINTED_SOURCES) != set(FOCUS_IDS):
        raise ValueError('Expected an exact painted source mapping for all 36 focuses')
    missing = [name for name in PAINTED_SOURCES.values()
               if not (ROOT/'docs/icon_studies'/name).is_file()]
    if missing:
        raise FileNotFoundError(f'Missing painted sources: {missing}')
    grouped = [fid for ids in EMBLEM_GROUPS.values() for fid in ids]
    if len(grouped) != 36 or set(grouped) != set(FOCUS_IDS):
        raise ValueError('Emblem assignments must cover all focuses exactly once')
    for group in EMBLEM_GROUPS:
        if not (ROOT/'docs/icon_studies/emblems'/f'{group}.png').is_file():
            raise FileNotFoundError(f'Missing emblem: {group}')
    OUT.mkdir(parents=True,exist_ok=True)
    focus_path=ROOT/'common/national_focus/tt_tuva_focus.txt'
    text=focus_path.read_text(encoding='utf-8')
    images=[]
    for fid in FOCUS_IDS:
        image=heraldic_icon(fid)
        image.save(OUT/(fid+'.dds'))  # uncompressed DDS, explicit 32-bit alpha
        images.append(image)
        pattern=rf'(id = TT_{fid}\n\t\ticon = )\S+'
        text,count=re.subn(pattern,rf'\g<1>GFX_TT_focus_{fid}',text)
        if count!=1:raise ValueError(f'{fid}: expected one focus, got {count}')
    focus_path.write_text(text,encoding='utf-8',newline='\n')
    (ROOT/'interface').mkdir(exist_ok=True)
    (ROOT/'interface/tt_tuva_focus_icons.gfx').write_text('spriteTypes = {\n'+''.join(gfx_entry(fid) for fid in FOCUS_IDS)+'}\n',encoding='utf-8',newline='\n')
    # A review sheet, exported from the actual game-resolution textures.
    sheet=Image.new('RGB',(1200,1200),'#0d2228');d=ImageDraw.Draw(sheet)
    fonts=Path('/usr/share/fonts/truetype/dejavu')
    # Windows builders may override by installing DejaVu Sans; fall back gracefully.
    def font(size):
        for candidate in (str(fonts/'DejaVuSans.ttf'), 'C:/Windows/Fonts/arial.ttf', 'DejaVuSans.ttf'):
            try:return ImageFont.truetype(candidate,size)
            except OSError:pass
        return ImageFont.load_default()
    d.text((30,20),'ТУВА · ЦЕНТР АЗИИ',font=font(28),fill='#edd393')
    d.text((30,57),'36 эмблем · сталь / бронза / знамёна · тувинский характер',font=font(16),fill='#89b6ad')
    loc=(ROOT/'localisation/russian/tt_tuva_l_russian.yml').read_text(encoding='utf-8-sig')
    import textwrap
    for i,(fid,img) in enumerate(zip(FOCUS_IDS,images,strict=True)):
        x=20+(i%6)*196;y=100+(i//6)*180
        d.rounded_rectangle((x,y,x+184,y+168),radius=10,fill='#173239',outline='#36504a')
        sheet.paste(img.resize((142,127),Image.Resampling.LANCZOS),(x+21,y+1),img.resize((142,127),Image.Resampling.LANCZOS))
        m=re.search(rf'^ TT_{fid}: "([^"]+)"',loc,re.M);title=m.group(1) if m else fid
        for j,line in enumerate(textwrap.wrap(title,23)[:2]):
            box=d.textbbox((0,0),line,font=font(12));d.text((x+(184-(box[2]-box[0]))/2,y+128+j*16),line,font=font(12),fill='#e6d7ad')
    sheet.save(ROOT/'docs/focus_icons_preview.png')
    print(f'Built {len(images)} DDS textures, normal/shine sprites, and preview.')


if __name__=='__main__':main()
