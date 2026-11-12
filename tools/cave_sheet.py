"""Contact sheet of every cave found by find_caves.py, to check them by eye.
    python -I tools/cave_sheet.py out.png"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parent.parent
caves = json.loads((ROOT / 'research/maps/caves.json').read_text())
tiles = []
for mid, pts in caves.items():
    im = Image.open(ROOT / f'research/maps/{mid}.webp').convert('RGB')
    for x, y in pts:
        px, py = int(x / 100 * im.width), int(y / 100 * im.height)
        t = im.crop((px - 30, py - 30, px + 30, py + 30)).resize((150, 150), Image.LANCZOS)
        ImageDraw.Draw(t).text((3, 3), f'{mid} {x},{y}', fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        tiles.append(t)
cols = 8
sheet = Image.new('RGB', (cols * 150, ((len(tiles) + cols - 1) // cols) * 150))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 150, (i // cols) * 150))
sheet.save(sys.argv[1]); print(len(tiles), 'caves')
