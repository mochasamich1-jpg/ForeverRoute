"""Draw every walking path a built route has in one zone, to check them by eye.
    python -I tools/path_preview.py UndeadMage 1424 out.png [seg]"""
import re, sys
from pathlib import Path
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parent.parent
name, mid, out = sys.argv[1], sys.argv[2], sys.argv[3]
seg = sys.argv[4] if len(sys.argv) > 4 else None
im = Image.open(ROOT / f'research/maps/{mid}.webp').convert('RGB')
d = ImageDraw.Draw(im)
P = lambda x, y: (float(x) / 100 * im.width, float(y) / 100 * im.height)
n = 0
for l in (ROOT / f'addon/ForeverRoute/Routes/{name}.lua').read_text(encoding='utf-8').split('\n'):
    m = re.search(r'map=%s, x=([\d.]+), y=([\d.]+), path=\{(.*?)\}\}' % mid, l)
    if not m or (seg and f'seg={seg},' not in l):
        continue
    pts = [P(*p.strip('{}').split(',')) for p in m.group(3).split('},{')]
    end = P(m.group(1), m.group(2))
    d.line(pts, fill=(0, 0, 0), width=5); d.line(pts, fill=(255, 60, 60), width=2)
    d.line([pts[-1], end], fill=(255, 220, 0), width=2)
    if 'cave=true' in l:
        c = pts[-1]; d.ellipse((c[0] - 7, c[1] - 7, c[0] + 7, c[1] + 7), outline=(0, 255, 255), width=3)
    d.ellipse((end[0] - 4, end[1] - 4, end[0] + 4, end[1] + 4), fill=(60, 255, 60), outline=(0, 0, 0))
    n += 1
im.save(out); print(n, 'paths drawn')
