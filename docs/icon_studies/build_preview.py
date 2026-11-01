#!/usr/bin/env python3
"""Preview completed heraldic icons at 2x and actual game resolution."""
from pathlib import Path
import re
import sys
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'docs'))
from generate_focus_icons import PAINTED_SOURCES, FOCUS_IDS


def font(size):
    for name in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 'C:/Windows/Fonts/arial.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    items = [fid for fid in FOCUS_IDS if fid in PAINTED_SOURCES]
    rows = (len(items)+4)//5
    height = 145+rows*340
    sheet = Image.new('RGB', (1320,height), '#19201f')
    draw = ImageDraw.Draw(sheet)
    draw.text((30,24), 'ТУВА / ЭМБЛЕМЫ ФОКУСОВ',font=font(29),fill='#dfd3b8')
    draw.text((30,70), f'Готово {len(items)} из 36 · сталь, бронза и знамёна',
              font=font(19),fill='#a5aaa0')
    loc = (ROOT/'localisation/russian/tt_tuva_l_russian.yml').read_text(encoding='utf-8-sig')
    for i,fid in enumerate(items):
        x = 16+(i%5)*260
        y = 120+(i//5)*340
        draw.rounded_rectangle((x,y,x+248,y+326),radius=6,fill='#28302c',outline='#485044')
        with Image.open(ROOT/'gfx/interface/goals/tt_tuva'/f'{fid}.dds') as source:
            image = source.convert('RGBA')
        large = image.resize((190,170),Image.Resampling.LANCZOS)
        sheet.paste(large,(x+29,y+7),large)
        match = re.search(rf'^ TT_{fid}: "([^"]+)"',loc,re.M)
        title = match.group(1) if match else fid
        for j,line in enumerate(textwrap.wrap(title,23)[:2]):
            box = draw.textbbox((0,0),line,font=font(15))
            draw.text((x+(248-box[2]+box[0])//2,y+182+j*19),line,font=font(15),fill='#e5d9bf')
        sheet.paste(image,(x+76,y+230),image)
    sheet.save(ROOT/'docs/focus_icon_style_study.png')
    print(f'Preview: {len(items)} painted icons, enlarged 2x above and native 95x85 below.')


if __name__ == '__main__':
    main()
