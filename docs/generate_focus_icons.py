#!/usr/bin/env python3
"""Rebuild the 36 original Tuva focus emblems (not needed by the game).

Optional art-build dependencies: Pillow, resvg-py. The validator remains stdlib-only.
Install: python -m pip install Pillow==13.0.0 resvg-py==0.5.0
Run: python docs/generate_focus_icons.py
All motifs below are original vector artwork; no vanilla textures are copied.
"""
from __future__ import annotations
import io
from pathlib import Path
import re
import resvg_py
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'gfx/interface/goals/tt_tuva'
SIZE = (95, 85)
GOLD = 'url(#gold)'


def path(d, fill='none', stroke='#f3ce79', width=3):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'


def poly(points, fill=GOLD, stroke='#4a3018', width=1.5):
    return f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>'


def rect(x,y,w,h,fill=GOLD,rx=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="#49301d" stroke-width="1.5"/>'


def circle(x,y,r,fill=GOLD,stroke='#4a3018',width=1.5):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def star(x=64,y=35,r=12):
    import math
    points=[]
    for i in range(10):
        a=math.radians(-90+i*36);rad=r if i%2==0 else r*.43
        points.append(f'{x+rad*math.cos(a):.2f},{y+rad*math.sin(a):.2f}')
    return poly(' '.join(points))


def sun(x=64,y=34,r=12):
    import math
    rays=''
    for i in range(12):
        a=math.radians(i*30)
        rays+=path(f'M{x+(r+4)*math.cos(a):.1f} {y+(r+4)*math.sin(a):.1f} L{x+(r+8)*math.cos(a):.1f} {y+(r+8)*math.sin(a):.1f}',width=2)
    return rays+circle(x,y,r)


def mountains():
    return poly('29,72 49,38 63,58 76,30 101,72',fill='url(#steel)')+path('M40 53 L49 38 L57 51 L50 48 Z M65 49 L76 30 L88 50 L76 43 Z',fill='#f3dfac',stroke='#f3dfac',width=1)


def yurt():
    return poly('33,51 64,28 95,51',fill='url(#gold)')+rect(34,51,60,27,'url(#ivory)',3)+path('M35 57 H93 M35 72 H93',stroke='#a3352b',width=3)+rect(56,58,16,20,'#223c3c',3)+path('M48 51 L54 43 M80 51 L74 43',stroke='#7f5a27',width=2)+rect(59,25,10,5,'#bb4f32')


def flag():
    return path('M47 78 V26',stroke='#f3d68b',width=4)+path('M49 28 Q65 20 88 30 L86 53 Q67 43 49 51 Z',fill='url(#red)',stroke='#eed092',width=2)+star(67,37,7)


def crown():
    return poly('37,43 44,70 84,70 91,43 76,54 64,36 52,54',fill=GOLD)+rect(43,67,42,8)+circle(64,57,4,'#258e91')+circle(48,60,2,'#a42e28')+circle(80,60,2,'#a42e28')


def rifle():
    return path('M45 80 L52 63 L57 63 L76 29 L81 32 L64 67 L61 67 L55 84 Z',fill=GOLD,stroke='#53391e',width=2)+path('M74 32 L82 20',stroke='#ead09b',width=3)


def crossed_rifles():
    return rifle()+f'<g transform="translate(128 0) scale(-1 1)">{rifle()}</g>'


def factory():
    return rect(33,54,63,26,'url(#steel)')+poly('33,54 49,43 49,54 65,43 65,54',fill=GOLD)+rect(73,28,10,32,'url(#gold)')+rect(87,36,8,24,'url(#gold)')+path('M77 23 Q68 17 78 13 M91 29 Q85 24 93 20',stroke='#b3c7b4',width=3)+''.join(rect(x,63,7,9,'#edcf7a') for x in (40,54,69,83))


def wheel(x=64,y=54,r=22):
    import math
    s=circle(x,y,r,fill='none',stroke='#d8b35e',width=6)+circle(x,y,7)
    for i in range(8):
        a=i*math.pi/4
        s+=path(f'M{x} {y} L{x+r*math.cos(a):.1f} {y+r*math.sin(a):.1f}',width=3)
    return s


def wings():
    return poly('60,47 24,34 30,45 46,53 29,49 38,60 57,62 64,72 71,62 90,60 99,49 82,53 98,45 104,34 68,47',fill=GOLD)


def plane():
    return poly('62,25 67,25 70,48 100,62 100,68 70,61 69,76 79,81 78,86 64,82 50,86 49,81 59,76 58,61 28,68 28,62 58,48',fill='url(#ivory)')+path('M64 36 V71',stroke='#806735',width=2)


def anchor():
    return circle(64,30,6,fill='none',stroke='#f1cd76',width=4)+path('M64 36 V76 M48 45 H80 M37 61 Q38 79 64 82 Q90 79 91 61 M37 61 L33 69 M37 61 L45 64 M91 61 L95 69 M91 61 L83 64',stroke='#f3ce79',width=5)


def waves():
    return path('M28 76 Q36 68 44 76 T60 76 T76 76 T92 76 M32 84 Q40 76 48 84 T64 84 T80 84 T96 84',stroke='#56b2b3',width=3)


def ship(big=False):
    return poly('28,62 99,62 88,75 40,75',fill=GOLD)+rect(51,49,24,13,'url(#steel)')+rect(59,36,8,14)+path('M63 36 V24 M40 57 H54 M74 57 H91',width=3)+(rect(77,51,11,10,'url(#steel)') if big else '')+waves()


def scroll():
    return rect(44,28,42,49,'url(#ivory)',4)+circle(43,31,5)+circle(84,74,5)+path('M53 42 H76 M53 51 H76 M53 60 H69',stroke='#7b4e27',width=3)


def horse():
    return path('M42 81 Q42 63 56 52 L48 42 L53 27 L62 35 L69 28 L79 41 L92 49 L88 59 L73 58 Q67 69 74 81 Z',fill=GOLD,stroke='#4d351f',width=2)+path('M51 40 Q42 48 44 64 L36 71 M57 34 L59 43 M74 50 L89 54',stroke='#392f24',width=3)+circle(74,44,2,'#193b3b')


def pick():
    return path('M43 80 L76 35',stroke='#b66e35',width=8)+path('M38 36 Q62 22 89 50 L83 55 Q63 39 38 41 Z',fill='url(#steel)',stroke='#e5c57a',width=2)


def crystal():
    return poly('56,53 64,37 73,54 70,78 59,78',fill='#3faaa6')+path('M64 38 V76 M56 53 H73',stroke='#d4e1ad',width=2)


def book():
    return path('M64 78 Q48 69 34 75 V40 Q50 34 64 43 Q78 34 94 40 V75 Q80 69 64 78 Z',fill='url(#ivory)',stroke='#80602d',width=2)+path('M64 44 V76 M40 47 L57 49 M40 56 L57 58 M72 49 L87 47 M72 58 L87 56',stroke='#96743d',width=2)


def cannon():
    return circle(52,68,13,fill='url(#steel)',stroke='#edcb7c',width=3)+circle(52,68,4)+path('M52 68 L83 80',width=5)+poly('48,52 91,33 95,42 55,62',fill=GOLD)+path('M89 31 L96 45',width=4)


def tank():
    return rect(29,62,70,17,'url(#steel)',8)+''.join(circle(x,71,5,'#af9255') for x in (41,55,69,83))+poly('35,62 43,49 83,49 94,62',fill=GOLD)+rect(54,37,25,13)+path('M76 43 H101',stroke='#f1ce7b',width=6)+star(63,44,4)


def map_shape():
    return path('M34 37 L47 31 L55 37 L67 27 L76 35 L94 37 L90 49 L99 58 L86 67 L80 79 L64 75 L52 82 L44 69 L30 64 L36 52 Z',fill='#328f90',stroke='#edcc7f',width=2)+path('M44 42 L55 48 L64 39 L76 49 L87 46 M43 62 L55 59 L67 67 L81 59',stroke='#80beb0',width=1.5)


def helmet():
    return path('M43 61 Q41 32 64 29 Q87 32 85 61 L77 75 H51 Z',fill=GOLD,stroke='#54391f',width=2)+path('M64 29 V73 M43 56 H85 M53 62 L58 65 M70 65 L75 62',stroke='#584425',width=3)+poly('58,28 64,16 70,28',fill='#c14b31')


def soldiers():
    s=''
    for x,y in ((43,48),(85,48),(64,37)):
        s+=circle(x,y,7,'url(#ivory)')+path(f'M{x-9} {y-3} Q{x} {y-15} {x+9} {y-3} Z',fill='#398b80',stroke='#d8bb6e',width=2)+path(f'M{x-10} {y+30} V{y+18} Q{x} {y+7} {x+10} {y+18} V{y+30} Z',fill='url(#gold)',stroke='#4a3922',width=2)
    return s


def motif(kind):
    if kind=='center':return sun(64,33,14)+mountains()+poly('56,79 60,38 68,38 72,79',fill=GOLD)+rect(49,77,30,6)
    if kind=='khural':return '<g transform="translate(0 -8)">'+yurt()+'</g>'+''.join(circle(x,78,5) for x in (45,64,83))+path('M37 88 Q45 76 53 88 M56 88 Q64 76 72 88 M75 88 Q83 76 91 88',width=3)
    if kind=='red_yurt':return yurt()+star(64,43,9)
    if kind=='arsenal':return '<g transform="translate(0 4) scale(1 .9)">'+factory()+'</g>'+path('M32 81 L92 30 M96 81 L36 30',stroke='#f1cd7b',width=4)
    if kind=='district':return mountains()+rect(46,61,36,19)+path('M47 61 V54 H54 V61 H61 V54 H68 V61 H75 V54 H82 V61',width=3)+rect(59,68,10,12,'#244647')
    if kind=='banner':return mountains()+flag()
    if kind=='ssr':return circle(64,51,27,fill='none',stroke='#65bcb2',width=2)+''.join(f'<g transform="translate({dx} {dy}) translate(64 50) scale(.43) translate(-64 -50)">{yurt()}</g>' for dx,dy in [(-20,12),(20,12),(0,-15)])+star(64,22,7)
    if kind=='manchuria':return mountains()+path('M40 83 L87 27',width=6)+poly('82,26 94,20 90,34',fill=GOLD)+star(46,34,10)
    if kind=='renaissance':return sun(64,33,15)+'<g transform="translate(0 12) scale(1 .85)">'+yurt()+'</g>'+path('M30 80 Q64 93 98 80',width=3)
    if kind=='khanate':return sun(64,40,20)+crown()
    if kind=='khan':return helmet()+path('M36 78 Q64 91 92 78',width=4)+circle(64,52,4,'#44aead')
    if kind=='empire':return wings()+crown()+sun(64,24,6)
    if kind=='plan':return wheel(64,53,25)+'<g transform="translate(10 2) scale(.85)">'+scroll()+'</g>'
    if kind=='herds':return path('M35 60 Q32 44 45 41 H76 Q90 43 91 58 L86 73 H42 Z',fill=GOLD,stroke='#4b351e',width=2)+path('M40 65 L38 81 M51 67 L51 81 M76 67 L77 81 M85 64 L88 80',stroke='#e6bf70',width=5)+path('M35 47 Q22 44 25 32 Q27 43 38 39 M80 44 Q98 41 96 31 Q103 43 91 51',stroke='#e8d6a7',width=3)+path('M43 51 L49 66 L56 51 L62 67 L69 51 L76 64',stroke='#8e652f',width=2)+circle(39,51,2,'#203f3b')
    if kind=='industry':return wheel(64,55,26)+factory()
    if kind=='minerals':return pick()+crystal()
    if kind=='rail':return path('M42 86 L54 47 M86 86 L74 47 M44 80 H84 M48 70 H80',stroke='#b9995d',width=4)+rect(46,40,36,35,'url(#steel)',5)+rect(50,44,28,11,'#82bbae')+circle(64,64,6)+rect(59,27,10,13)+path('M62 23 Q49 13 62 12',width=3)
    if kind=='dam':return poly('44,29 81,29 94,75 31,75',fill='url(#steel)')+path('M53 32 L47 72 M64 32 V72 M75 32 L81 72',width=4)+waves()
    if kind=='gold':return ''.join(f'<g transform="translate({x} {y})">'+rect(0,0,22,9)+path('M2 4 H20',stroke='#fff0af',width=1)+'</g>' for x,y in [(37,65),(61,65),(49,54),(49,76),(73,76),(25,76)])+sun(64,36,10)
    if kind=='army':return crossed_rifles()+poly('44,37 64,29 84,37 82,64 64,79 46,64',fill='#308b82')+star(64,51,14)
    if kind=='cavalry':return horse()+path('M35 81 H85',width=3)
    if kind=='advisors':return book()+star(43,32,9)+star(85,32,9)+path('M49 27 Q64 18 79 27',stroke='#62b8ac',width=3)
    if kind=='mountain':return mountains()+'<g transform="translate(11 14) scale(.8)">'+pick()+'</g>'
    if kind=='airforce':return wings()+'<g transform="translate(16 3) scale(.75)">'+plane()+'</g>'
    if kind=='mobilize':return soldiers()+path('M28 83 H100',width=3)
    if kind=='infantry':return '<g transform="translate(-9 -2)">'+rifle()+'</g>'+cannon()
    if kind=='tanks':return tank()
    if kind=='cas':return '<g transform="rotate(24 64 53)">'+plane()+'</g>'+poly('32,60 47,67 39,72 51,87 27,73 35,68',fill='#d86a39')
    if kind=='bombers':return plane()+rect(42,48,7,16,'url(#gold)',3)+rect(79,48,7,16,'url(#gold)',3)+path('M48 76 V86 M82 76 V86',stroke='#e9a957',width=4)
    if kind=='flotilla':return '<g transform="translate(0 -6)">'+mountains()+'</g>'+ship()
    if kind=='school':return '<g transform="translate(0 9)">'+book()+'</g>'+'<g transform="translate(16 -1) scale(.75)">'+anchor()+'</g>'
    if kind=='fleet':return sun(64,29,12)+ship(True)
    if kind=='claims':return map_shape()+path('M39 83 L88 25',width=4)+poly('84,25 95,18 91,33',fill=GOLD)
    if kind=='mongolia':return '<g transform="translate(0 7)">'+yurt()+'</g>'+path('M39 34 L32 23 L48 18 M89 34 L96 23 L80 18',width=3)+circle(64,26,8,'#449e96')
    if kind=='greater':return map_shape()+'<g transform="translate(16 13) scale(.75)">'+crown()+'</g>'
    if kind=='siberia':return mountains()+path('M39 82 L86 28',width=5)+poly('82,28 95,20 90,35',fill=GOLD)+path('M41 28 V46 M32 37 H50 M35 31 L47 43 M35 43 L47 31',stroke='#9ddbd0',width=2.5)
    raise ValueError(kind)


KINDS = ['center','khural','red_yurt','arsenal','district','banner','ssr','manchuria','renaissance','khanate','khan','empire','plan','herds','industry','minerals','rail','dam','gold','army','cavalry','advisors','mountain','airforce','mobilize','infantry','tanks','cas','bombers','flotilla','school','fleet','claims','mongolia','greater','siberia']
# Explicit ordered manifest: stable artwork assignment, independent of tree layout.
FOCUS_IDS = ['center_of_asia','the_great_khural','red_yurt','the_soviet_arsenal','the_siberian_military_district','the_red_banner_over_asia','form_central_asian_ssr','the_battle_for_manchuria','tuvan_renaissance','the_second_khanate','the_great_khan','the_empire_of_the_steppe','first_five_year_plan','collective_herds','kyzyl_industries','mineral_prospecting','the_kyzyl_railroad','the_yenisei_dam','the_golden_hoard','the_peoples_army','cavalry_of_the_steppe','soviet_advisors','mountain_warfare','the_tuvan_air_force','total_mobilization','infantry_and_artillery','tanks_of_the_steppe','wings_of_the_steppe','bombers_over_siberia','the_yenisei_flotilla','kyzyl_naval_school','the_pacific_fleet','claims_on_the_steppe','the_mongolian_question','greater_tuva','the_siberian_gambit']


def emblem(kind,index):
    import math
    red = index in (2,3,4,5,6,7)
    accent='#9b382e' if red else '#246e70'
    defs='''<defs>
      <linearGradient id="gold" x1="0" y1="0" x2=".7" y2="1"><stop stop-color="#fff0b2"/><stop offset=".35" stop-color="#e1b762"/><stop offset=".65" stop-color="#a47734"/><stop offset=".82" stop-color="#f1d181"/><stop offset="1" stop-color="#91632c"/></linearGradient>
      <linearGradient id="steel" x2=".9" y2="1"><stop stop-color="#aac1ac"/><stop offset=".45" stop-color="#506f6a"/><stop offset="1" stop-color="#1d3b3c"/></linearGradient>
      <linearGradient id="ivory" x2=".6" y2="1"><stop stop-color="#fff2c3"/><stop offset="1" stop-color="#b5a36c"/></linearGradient>
      <linearGradient id="red" x2=".4" y2="1"><stop stop-color="#d36a43"/><stop offset="1" stop-color="#7b2726"/></linearGradient>
      <radialGradient id="field"><stop stop-color="#326a65"/><stop offset="1" stop-color="#102d30"/></radialGradient>
    </defs>'''
    # Stylised interlocking angular ornament, not a claimed reproduction of a sacred emblem.
    rim=''
    for i in range(12):
        angle=i*30
        rim+=f'<g transform="rotate({angle} 64 54)">'+path('M59 15 H67 V20 H62 V24 H69',stroke='#c4a255',width=1.6)+'</g>'
    etching=''
    for i in range(16):
        a=i*math.pi/8
        etching+=path(f'M{64+31*math.cos(a):.2f} {54+31*math.sin(a):.2f} L{64+35*math.cos(a):.2f} {54+35*math.sin(a):.2f}',stroke='#a4a46a',width=.6)
    body=circle(64,56,46,'#0b181c','#0b181c',3)+circle(64,54,46,GOLD,'#4a301b',2)+circle(64,54,41,'url(#field)','#fff0aa',1)+circle(64,54,36,'url(#field)',accent,3)+rim+etching
    body+=f'<g transform="translate(0 2)" opacity=".8">{motif(kind)}</g>' # dark offset under the relief
    body+=f'<g>{motif(kind)}</g>'
    body+=path('M22 81 L38 85 L36 100 L20 95 L13 99 L16 88 Z',fill='url(#red)',stroke='#674126',width=1.5)
    body+=path('M106 81 L90 85 L92 100 L108 95 L115 99 L112 88 Z',fill='url(#red)',stroke='#674126',width=1.5)
    body+=path('M35 85 Q64 95 93 85 L89 99 Q64 108 39 99 Z',fill=accent,stroke='#ddb76a',width=2)
    body+=path('M44 93 H51 V98 H57 V93 H64 V98 H71 V93 H78 V98 H84',stroke='#eaca83',width=1.7)
    body+=poly('58,5 64,0 70,5 64,12',fill='#48aaa6')+circle(64,5,1.4,'#f5dc92')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="95" height="85" viewBox="0 -3 128 114">{defs}{body}</svg>'


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


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    focus_path=ROOT/'common/national_focus/tt_tuva_focus.txt'
    text=focus_path.read_text(encoding='utf-8')
    images=[]
    for fid,kind in zip(FOCUS_IDS,KINDS,strict=True):
        raw=resvg_py.svg_to_bytes(svg_string=emblem(kind,FOCUS_IDS.index(fid)),width=380,height=340)
        image=Image.open(io.BytesIO(raw)).convert('RGBA').resize(SIZE,Image.Resampling.LANCZOS)
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
    d.text((30,57),'36 авторских эмблем · орнамент / бирюза / золото',font=font(16),fill='#89b6ad')
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
