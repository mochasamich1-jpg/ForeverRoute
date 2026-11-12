"""Walking paths and cave entrances read from the zone map art.

The zone maps (research/maps/<uiMapID>.webp, 1002x668, the in-game map art as served by
foreverchanges.pro) are turned into a cost grid: smooth ground and roads are cheap, the densely
drawn mountain ridges and water are expensive. A* over that grid gives a walking line between two
points of the same zone; cave entrances are the small cave drawings on the map.

Everything here is read off a drawing, not the game's real terrain, so paths are a best guess.

CLI (debug picture):
    python -I tools/pathmap.py path <mapid> x1 y1 x2 y2 out.png
    python -I tools/pathmap.py caves <mapid> out.png
"""
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / 'research' / 'maps'
SCALE = 2            # path grid = map pixels / SCALE
MIN_BLOCKED = 0.25   # share of the straight line that must be mountain before a path is made
MAX_ROUGH = 0.35     # a path with more than this share of its cells on drawn ridges is thrown away
MAX_DETOUR = 1.6     # longest path accepted, as a multiple of the straight line
_cost_cache = {}
_img_cache = {}


def map_image(mapid):
    if mapid not in _img_cache:
        f = MAPS / f'{mapid}.webp'
        _img_cache[mapid] = Image.open(f).convert('RGB') if f.exists() else None
    return _img_cache[mapid]


def _box(a, r):
    """box blur with radius r (integral image)"""
    p = np.pad(a, ((r + 1, r), (r + 1, r)), mode='edge').cumsum(0).cumsum(1)
    n = 2 * r + 1
    return (p[n:, n:] - p[:-n, n:] - p[n:, :-n] + p[:-n, :-n]) / (n * n)


THIN = 9            # bands narrower than about 2*THIN px are not mountains


def _minmax(a, n, op):
    """n passes of a 3x3 min (erode) or max (dilate) filter"""
    for _ in range(n):
        p = np.pad(a, 1, mode='edge')
        a = op(op(p[:-2], p[1:-1]), p[2:])
        a = op(op(a[:, :-2], a[:, 1:-1]), a[:, 2:])
    return a


def cost_grid(mapid):
    """float grid (h, w): 1 = open ground / road, up to ~40 = mountain wall or water"""
    if mapid in _cost_cache:
        return _cost_cache[mapid]
    im = map_image(mapid)
    if im is None:
        _cost_cache[mapid] = None
        return None
    a = np.asarray(im, dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    rough = _box(gx + gy, 7)                 # how densely drawn the area is (ridges = high)
    water = _box(((b > r + 8) & (b > g)).astype(np.float32), 3)
    lo, hi = 9.0, 22.0                        # tuned on Stonetalon / Barrens / Tirisfal
    t = np.clip((rough - lo) / (hi - lo), 0, 1)
    # roads, rivers and map labels are thin drawn bands; mountains are wide blobs.
    # Opening (erode then dilate) keeps only the wide blobs.
    wide = _minmax(_minmax(t, THIN, np.minimum), THIN, np.maximum)
    thin = np.clip(t - wide, 0, 1)            # what the opening removed: roads, labels, river banks
    cost = 1 + 39 * wide ** 2 + 4 * np.clip(water * 2, 0, 1) - 0.15 * (thin > 0.5)
    h, w = cost.shape
    cost = cost[:h - h % SCALE, :w - w % SCALE].reshape(h // SCALE, SCALE, w // SCALE, SCALE).mean((1, 3))
    _cost_cache[mapid] = cost
    return cost


def _to_cell(cost, x, y):
    h, w = cost.shape
    return (min(h - 1, max(0, int(y / 100 * h))), min(w - 1, max(0, int(x / 100 * w))))


def _to_pct(cost, cy, cx):
    h, w = cost.shape
    return ((cx + 0.5) / w * 100, (cy + 0.5) / h * 100)


NB = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1),
      (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]


def _astar(cost, s, e):
    h, w = cost.shape
    # search only a box around the two points (keeps it fast)
    m = 45
    y0, y1 = max(0, min(s[0], e[0]) - m), min(h, max(s[0], e[0]) + m + 1)
    x0, x1 = max(0, min(s[1], e[1]) - m), min(w, max(s[1], e[1]) + m + 1)
    dist = {s: 0.0}
    prev = {}
    pq = [(math.hypot(s[0] - e[0], s[1] - e[1]), s)]
    done = set()
    while pq:
        _, u = heapq.heappop(pq)
        if u in done:
            continue
        if u == e:
            break
        done.add(u)
        du = dist[u]
        cu = cost[u]
        for dy, dx, step in NB:
            vy, vx = u[0] + dy, u[1] + dx
            if vy < y0 or vy >= y1 or vx < x0 or vx >= x1:
                continue
            v = (vy, vx)
            if v in done:
                continue
            nd = du + step * (cu + cost[v]) / 2
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd + math.hypot(vy - e[0], vx - e[1]), v))
    if e not in prev and e != s:
        return None, None
    path = [e]
    while path[-1] != s:
        path.append(prev[path[-1]])
    path.reverse()
    return path, dist[e]


def _line_cost(cost, s, e):
    n = max(abs(s[0] - e[0]), abs(s[1] - e[1]), 1)
    tot = 0.0
    for i in range(n + 1):
        y = s[0] + (e[0] - s[0]) * i / n
        x = s[1] + (e[1] - s[1]) * i / n
        tot += cost[int(round(y)), int(round(x))]
    return tot / (n + 1) * math.hypot(s[0] - e[0], s[1] - e[1])


def _blocked_share(cost, s, e):
    n = max(abs(s[0] - e[0]), abs(s[1] - e[1]), 1)
    hit = 0
    for i in range(n + 1):
        y = s[0] + (e[0] - s[0]) * i / n
        x = s[1] + (e[1] - s[1]) * i / n
        hit += cost[int(round(y)), int(round(x))] >= 20
    return hit / (n + 1)


def _simplify(pts, eps):
    """Douglas-Peucker on grid cells"""
    if len(pts) < 3:
        return pts
    (y1, x1), (y2, x2) = pts[0], pts[-1]
    L = math.hypot(y2 - y1, x2 - x1) or 1e-9
    best, bi = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs((x2 - x1) * (y1 - pts[i][0]) - (x1 - pts[i][1]) * (y2 - y1)) / L
        if d > best:
            best, bi = d, i
    if best <= eps:
        return [pts[0], pts[-1]]
    return _simplify(pts[:bi + 1], eps)[:-1] + _simplify(pts[bi:], eps)


def walk_path(mapid, a, b, min_len=4.0):
    """Waypoints (zone %, without the two ends) for walking a -> b, or [] when a straight line is fine.

    a, b: (x, y) in zone %.  min_len: shortest trip (in % of map width) worth routing.
    """
    cost = cost_grid(mapid)
    if cost is None:
        return []
    s, e = _to_cell(cost, *a), _to_cell(cost, *b)
    straight = math.hypot(s[0] - e[0], s[1] - e[1])
    if straight < min_len / 100 * cost.shape[1]:
        return []
    line = _line_cost(cost, s, e)
    if line < straight * 3.0:                 # the straight line is over open ground already
        return []
    if _blocked_share(cost, s, e) < MIN_BLOCKED:   # only a little of it is drawn as mountain: not worth a detour
        return []
    path, total = _astar(cost, s, e)
    if not path or total > line * 0.55:        # no clearly better way found: keep the plain arrow
        return []
    body = path[:-10] or path                 # the target itself is often drawn inside the mountains
    if sum(cost[c] > 12 for c in body) > MAX_ROUGH * len(body):   # mostly over ridges: not a real way round
        return []
    walked = sum(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(path, path[1:]))
    if walked > straight * MAX_DETOUR:        # a huge loop is more likely a misread drawing than a real way round
        return []
    simp = _simplify(path, 3.0)
    return [tuple(round(v, 1) for v in _to_pct(cost, cy, cx)) for cy, cx in simp[1:-1]]


# ---------------------------------------------------------------- cave entrances
def load_caves():
    f = MAPS / 'caves.json'
    if not f.exists():
        return {}
    return {int(k): v for k, v in json.loads(f.read_text(encoding='utf-8')).items()}


def nearest_cave(caves, mapid, x, y, max_dist=5.0):
    """closest cave drawing to (x, y) within max_dist (map-width %), or None. y is scaled to the 3:2 map."""
    best, bd = None, max_dist
    for cx, cy in caves.get(mapid, []):
        d = math.hypot(cx - x, (cy - y) * 2 / 3)
        if d < bd:
            best, bd = (cx, cy), d
    return best


# ---------------------------------------------------------------- debug pictures
def _px(im, x, y):
    return (x / 100 * im.width, y / 100 * im.height)


def debug_path(mapid, a, b, out):
    im = map_image(mapid).copy()
    d = ImageDraw.Draw(im)
    pts = [a] + walk_path(mapid, a, b) + [b]
    line = [_px(im, *p) for p in pts]
    d.line(line, fill=(0, 0, 0), width=6)
    d.line(line, fill=(255, 40, 40), width=3)
    for p in line:
        d.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill=(255, 255, 0), outline=(0, 0, 0))
    im.save(out)
    print(pts)


def debug_cost(mapid, out):
    c = cost_grid(mapid)
    g = np.clip((c - 1) / 39 * 255, 0, 255).astype(np.uint8)
    Image.fromarray(g).resize((c.shape[1] * SCALE, c.shape[0] * SCALE)).save(out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'path':
        mid = int(sys.argv[2])
        x1, y1, x2, y2 = map(float, sys.argv[3:7])
        debug_path(mid, (x1, y1), (x2, y2), sys.argv[7])
    elif cmd == 'cost':
        debug_cost(int(sys.argv[2]), sys.argv[3])
    elif cmd == 'caves':
        mid = int(sys.argv[2])
        im = map_image(mid).copy()
        d = ImageDraw.Draw(im)
        for x, y in load_caves().get(mid, []):
            p = _px(im, x, y)
            d.ellipse((p[0] - 12, p[1] - 12, p[0] + 12, p[1] + 12), outline=(255, 0, 0), width=3)
        im.save(sys.argv[3])
