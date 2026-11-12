"""Find hand-ins that wait although the route walks past their NPC with the quest already finished.

Usage: python -I tools/late_handins.py [--route all] [--radius 2.5] [--all]

Reads the generated route Lua (so it sees the resolved coordinates). A quest is "ready" once its last C step is
behind you (or right after its A step when the route has no C step for it). For every ready quest it looks for an
earlier step that stands within --radius map units of the hand-in NPC (or whose straight walk to the next step
passes that close), in the same zone, and from which the route
then LEAVES (a later step further than 3 x radius away, or in another zone) before the T step comes.
Default output leaves out quests without a C step (deliveries and "talk to" quests are often meant to wait for a
follow-up level or an NPC next door); --all shows them too.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_route as B  # noqa: E402


def steps_of(lua):
    out = []
    for m in re.finditer(r'^\s*\{t="(\w+)", seg=(\d+),(.*)\},?\s*$', lua, flags=re.M):
        body = m.group(3)
        if 'dg=' in body:
            continue
        q = re.search(r'\bq=\{([\d, ]*)\}', body)
        z = re.search(r'zone="([^"]*)"', body)
        x = re.search(r'\bx=([\d.]+)', body)
        y = re.search(r'\by=([\d.]+)', body)
        names = re.search(r'names=\{([^}]*)\}', body)
        text = re.search(r'text="((?:[^"\\]|\\.)*)"', body)
        out.append({'t': m.group(1), 'seg': int(m.group(2)),
                    'q': [int(v) for v in re.findall(r'\d+', q.group(1))] if q else [],
                    'zone': z.group(1) if z else None,
                    'x': float(x.group(1)) if x else None, 'y': float(y.group(1)) if y else None,
                    'names': re.findall(r'"((?:[^"\\]|\\.)*)"', names.group(1)) if names else [],
                    'text': text.group(1) if text else ''})
    return out


def near(a, b, r):
    return (a['zone'] and a['zone'] == b['zone'] and a['x'] is not None and b['x'] is not None
            and abs(a['x'] - b['x']) <= r and abs(a['y'] - b['y']) <= r)


def passes(S, i, T, r):
    """True when the straight walk from step i to the next positioned step runs within r of T (same zone)."""
    a = S[i]
    if a['x'] is None or a['zone'] != T['zone']:
        return False
    b = next((S[j] for j in range(i + 1, len(S)) if S[j]['x'] is not None), None)
    if b is None or b['zone'] != T['zone'] or b is T:
        return False
    ax, ay, bx, by, px, py = a['x'], a['y'], b['x'], b['y'], T['x'], T['y']
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return False
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 <= r


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    key = args[args.index('--route') + 1] if '--route' in args else 'all'
    radius = float(args[args.index('--radius') + 1]) if '--radius' in args else 2.5
    show_all = '--all' in args
    for rk in (list(B.PROFILES) if key == 'all' else [key]):
        P = B.use_profile(rk)
        lua = (B.ROOT / 'addon' / 'ForeverRoute' / 'Routes' / f"{P['lua']}.lua").read_text(encoding='utf-8')
        head = lua[lua.index('segments = {'):]
        segs = re.findall(r'"((?:[^"\\]|\\.)*)"', head[:head.index('}')])
        S = steps_of(lua)
        acc, lastc, turn = {}, {}, {}
        for i, s in enumerate(S):
            for q in s['q']:
                if s['t'] == 'A':
                    acc.setdefault(q, i)
                elif s['t'] == 'C':
                    lastc[q] = i
                elif s['t'] == 'T':
                    turn.setdefault(q, i)
        found = []
        for q, ti in turn.items():
            if q not in acc or S[ti]['x'] is None:
                continue
            has_c = q in lastc and lastc[q] < ti
            if not has_c and not show_all:
                continue
            ready = lastc[q] if has_c else acc[q]
            T = S[ti]
            hit = None
            for i in range(ready, ti):  # the walk away from the last objective counts too
                if not (i > ready and near(S[i], T, radius)) and not passes(S, i, T, radius):
                    continue
                # does the route leave this place again before the hand-in?
                left = None
                for j in range(i + 1, ti):
                    sj = S[j]
                    if sj['x'] is None:
                        continue
                    if sj['zone'] != T['zone'] or abs(sj['x'] - T['x']) > 3 * radius or abs(sj['y'] - T['y']) > 3 * radius:
                        left = j
                        break
                if left is not None:
                    hit = (i, left)
                    break
            if hit:
                found.append((hit[0], q, ti, hit[1], has_c))
        found.sort()
        print(f"\n===== {rk}: {len(found)} hand-ins that wait past their NPC")
        for i, q, ti, left, has_c in found:
            T = S[ti]
            name = T['names'][T['q'].index(q)] if len(T['names']) == len(T['q']) else ''
            a = S[i]
            print(f"  seg {a['seg']:2d} step {i + 1}: at {a['zone']} {a['x']},{a['y']} ({a['t']} {a['q'] or ''} {a['text'][:50]!r})"
                  f"\n         {q} {name!r} is {'done' if has_c else 'in the log (no C step)'}; handed in at step {ti + 1}"
                  f" (seg {T['seg']}, {ti - i} steps later) after leaving for {S[left]['zone']} {S[left]['x']},{S[left]['y']}")


if __name__ == '__main__':
    main()
