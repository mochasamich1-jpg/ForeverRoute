"""Find the small cave drawings on every zone map -> research/maps/caves.json

    python -I tools/find_caves.py [--debug mapid out.png]

Template match (normalised cross-correlation on grey) against the cave drawings cut from the
Stonetalon map. Positions are zone % of the middle of the drawing.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / 'research' / 'maps'
T = 11  # template half size (px)
# cave drawings on the Stonetalon map (1442) used as templates: pixel centres
TEMPLATES = [(1442, 616, 613), (1442, 646, 636), (1420, 274, 387)]
THRESH = 0.55


def grey(mapid):
    return np.asarray(Image.open(MAPS / f'{mapid}.webp').convert('L'), dtype=np.float32)


def templates():
    out = []
    for mid, x, y in TEMPLATES:
        g = grey(mid)[y - T:y + T + 1, x - T:x + T + 1]
        out.append((g - g.mean()) / (g.std() + 1e-6))
    return out


def match(g, tpl):
    """NCC score map (same size as g, 0 at the border)"""
    n = 2 * T + 1
    h, w = g.shape
    out = np.zeros((h, w), dtype=np.float32)
    win = np.lib.stride_tricks.sliding_window_view(g, (n, n))
    for y0 in range(0, win.shape[0], 40):
        blk = win[y0:y0 + 40].astype(np.float32)
        m = blk.mean((2, 3), keepdims=True)
        s = blk.std((2, 3), keepdims=True) + 1e-6
        out[y0 + T:y0 + T + blk.shape[0], T:T + blk.shape[1]] = (((blk - m) / s) * tpl).mean((2, 3))
    return out


def find(mapid, tpls):
    g = grey(mapid)
    score = np.max([match(g, t) for t in tpls], axis=0)
    hits = []
    s = score.copy()
    while True:
        y, x = np.unravel_index(np.argmax(s), s.shape)
        if s[y, x] < THRESH:
            break
        hits.append((round(x / g.shape[1] * 100, 1), round(y / g.shape[0] * 100, 1), round(float(s[y, x]), 2)))
        s[max(0, y - 14):y + 15, max(0, x - 14):x + 15] = 0
    return hits


if __name__ == '__main__':
    tpls = templates()
    if '--debug' in sys.argv:
        mid = int(sys.argv[2]); hits = find(mid, tpls)
        im = Image.open(MAPS / f'{mid}.webp').convert('RGB'); d = ImageDraw.Draw(im)
        for x, y, sc in hits:
            px, py = x / 100 * im.width, y / 100 * im.height
            d.ellipse((px - 14, py - 14, px + 14, py + 14), outline=(255, 0, 0), width=3)
            d.text((px + 16, py - 6), str(sc), fill=(255, 255, 255))
        im.save(sys.argv[3]); print(hits)
    else:
        out = {}
        for f in sorted(MAPS.glob('*.webp')):
            mid = int(f.stem)
            out[mid] = [[x, y] for x, y, _ in find(mid, tpls)]
            print(mid, len(out[mid]), flush=True)
        (MAPS / 'caves.json').write_text(json.dumps(out, indent=0), encoding='utf-8')
