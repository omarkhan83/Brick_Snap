"""Part B: measure building order in OMR LDraw models.

argv: omr_data_dir rebrickable_cache.pkl classify.py ldraw_zip out.md out.pkl

Reads each <set>/model.mpd (untrusted text, parsed as data only), unrolls it into the order a
builder follows (a sub-model's steps are emitted where the parent first uses it), and measures
what goes on when. Parts are sorted into jobs with the same classifier as part A, via the
Rebrickable parts table (LDraw and Rebrickable numbers mostly agree), falling back to the LDraw
library's own description.
"""
import sys, os, re, zipfile, pickle, collections, statistics as st, math

DATA, CACHE, CLASSIFY, ZIP, OUT, OUTP = sys.argv[1:7]
exec(open(CLASSIFY).read())
parts, themes, sets, parent, tally = pickle.load(open(CACHE, 'rb'))
Z = zipfile.ZipFile(ZIP)
ZN = {n.lower(): n for n in Z.namelist()}


def ldraw_desc(name):
    for pre in ('ldraw/parts/', 'ldraw/unofficial/parts/'):
        k = pre + name.lower().replace('\\', '/')
        if k in ZN:
            txt = Z.read(ZN[k]).decode('utf-8', 'replace').splitlines()
            first = txt[0][2:].strip() if txt and txt[0].startswith('0') else ''
            m = re.match(r'~?moved to (\S+)', first, re.I)
            if m:
                return first, m.group(1)
            return first, None
    return None, None


def rb_root(p):
    k = 0
    while p in parent and k < 5:
        p = parent[p]; k += 1
    return p


_cache = {}
FALLBACK_CAT = [(r'^technic beam|^technic liftarm', '51'), (r'^technic pin', '53'), (r'^technic axle\b', '46'),
                (r'^technic bush', '54'), (r'^technic (connector|axle joiner|pin joiner)', '12'), (r'^technic brick', '8'),
                (r'^technic', '26'), (r'^hinge', '18'), (r'^(wheel|tyre|tire)', '29'), (r'^minifig|^figure', '13'),
                (r'^sticker', '58'), (r'^bracket', '9'), (r'^brick', '5'), (r'^plate', '9'), (r'^tile', '15'),
                (r'^slope', '3'), (r'^bar\b', '32'), (r'^panel', '23'), (r'^window|^door|^glass', '16'),
                (r'^plant|^flower', '76')]


def part_job(fname):
    """Return (job, rebrickable-like id, name) for an LDraw part file name."""
    if fname in _cache:
        return _cache[fname]
    base = fname.lower().replace('\\', '/').rsplit('/', 1)[-1]
    base = re.sub(r'\.dat$', '', base)
    base = re.sub(r'^\d+(-\d+)?\s*-\s*', '', base)
    cands = [base, re.sub(r'p[a-z0-9]{2,4}$', '', base), re.sub(r'pr\d+$', '', base), re.sub(r'c\d\d$', '', base),
             re.sub(r'(p[a-z0-9]+|pr\d+|c\d\d)+$', '', base), re.sub(r'(d\d\d|p[a-z0-9]+|pr\d+|c\d\d)+$', '', base), re.sub(r'[a-z]+$', '', base)]
    desc, moved = ldraw_desc(base + '.dat')
    if desc is None:
        desc = EMB.get(fname.lower())
    if moved:
        cands.insert(1, re.sub(r'\.dat$', '', moved.lower()))
    res = None
    for c in cands:
        if c in parts:
            rp = rb_root(c)
            res = (job(rp, parts), rp, parts[rp]['name'])
            break
    if res is None:
        d = (desc or '').lstrip('~_=').strip()
        cat = None
        for rx, ccat in FALLBACK_CAT:
            if re.search(rx, d.lower()):
                cat = ccat; break
        if cat:
            fake = {'__x': {'part_cat_id': cat, 'name': d}}
            res = (job('__x', fake), base, d + ' [LDraw]')
        else:
            res = ('unknown', base, d or base)
    _cache[fname] = res
    return res


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def matvec(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


EMB = {}


def parse_mpd(path):
    files = collections.OrderedDict(); kind = {}; cur = None
    for raw in open(path, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if line.upper().startswith('0 FILE '):
            cur = line[7:].strip().lower(); files[cur] = []; kind[cur] = 'model'
            continue
        if cur is None:
            cur = '__main__'; files[cur] = []; kind[cur] = 'model'
        m = re.match(r'0 !LDRAW_ORG\s+(\S+)', line, re.I)
        if m and 'model' not in m.group(1).lower():
            kind[cur] = 'part'
        if len(files[cur]) == 0 and line.startswith('0 ') and cur not in EMB:
            EMB[cur] = line[2:].strip()
        files[cur].append(line)
    return files, kind


def unroll(files, kind):
    """Yield the build as a list of steps. Each step: dict(parts=[(fname, R, t)], sub=[names], depth, file)."""
    models = {n for n in files if kind[n] == 'model'}
    main = next(iter(files))
    steps_of = {}
    for n in models:
        st_ = [[]]
        for line in files[n]:
            u = line.upper()
            if u.startswith('0 STEP') or u.startswith('0 ROTSTEP'):
                st_.append([])
            elif line.startswith('1 '):
                tok = line.split()
                if len(tok) < 15:
                    continue
                x, y, z = map(float, tok[2:5]); m = list(map(float, tok[5:14]))
                R = [m[0:3], m[3:6], m[6:9]]
                ref = ' '.join(tok[14:]).lower()
                st_[-1].append((ref, R, [x, y, z]))
        steps_of[n] = [s for s in st_ if s]
    out = []
    refcount = collections.Counter()
    def walk(n, R0, t0, depth, stack, chain=()):
        for s in steps_of.get(n, []):
            here = []
            subs = []
            for ref, R, t in s:
                Rw = matmul(R0, R); tw = [a + b for a, b in zip(matvec(R0, t), t0)]
                if ref in models and ref not in stack:
                    refcount[ref] += 1
                    subs.append(ref)
                    walk(ref, Rw, tw, depth + 1, stack | {ref}, chain + (ref,))
                else:
                    here.append((ref, Rw, tw))
            out.append(dict(parts=here, sub=subs, depth=depth, file=n, chain=chain))
    I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    walk(main, I, [0, 0, 0], 0, {main})
    return out, refcount, steps_of, models, main


SYSTEM = {'brick', 'plate', 'tile', 'slope', 'curved_slope', 'wedge', 'round', 'sideways', 'special_other'}
JOINTJ = {'hinge', 'turntable', 'clip', 'bar', 'balljoint'}
MOVE = {'wheel', 'hinge', 'turntable', 'balljoint', 'technic_other'}


def spearman(x, y):
    n = len(x)
    if n < 5:
        return float('nan')
    def rank(v):
        o = sorted(range(n), key=lambda i: v[i]); r = [0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float('nan')


results = []
for set_num in sorted(os.listdir(DATA)):
    path = os.path.join(DATA, set_num, 'model.mpd')
    if not os.path.isfile(path):
        continue
    files, kind = parse_mpd(path)
    steps, refcount, steps_of, models, main = unroll(files, kind)
    # flatten placed parts with step index
    placed = []
    for si, s in enumerate(steps):
        for ref, R, t in s['parts']:
            j, pid, nm = part_job(ref)
            placed.append(dict(step=si, job=j, pid=pid, name=nm, R=R, t=t, depth=s['depth'], file=s['file'], chain=s['chain']))
    build = [p for p in placed if p['job'] not in ('minifig', 'unknown') and not p['name'].lower().startswith('sticker')]
    if not build:
        continue
    nsteps = len(steps)
    # effective root: descend while one sub-model holds >= 80 % of the build parts (a wrapper scene)
    root = ()
    while True:
        c = collections.Counter(p['chain'][len(root)] for p in build if len(p['chain']) > len(root) and p['chain'][:len(root)] == root)
        if c and c.most_common(1)[0][1] >= 0.8 * sum(1 for p in build if p['chain'][:len(root)] == root):
            root = root + (c.most_common(1)[0][0],)
        else:
            break
    for p in build:
        p['rel'] = len(p['chain']) - len(root) if p['chain'][:len(root)] == root else -1
    rb = sets.get(set_num, {})
    g = group_of(rb['theme_id'], themes) if rb else '?'
    # submodel classification: minifig-like if most of its own parts are minifig parts
    sub_info = {}
    for n in models:
        if n == main:
            continue
        own = [part_job(r)[0] for s in steps_of.get(n, []) for (r, _, _) in s if r not in models]
        if not own and not any(r in models for s in steps_of.get(n, []) for (r, _, _) in s):
            continue
        mf = sum(1 for x in own if x == 'minifig') / max(1, len(own))
        sub_info[n] = dict(minifig=mf >= 0.5, own=len(own), refs=refcount[n])
    # world up: most common up vector of system parts
    ups = collections.Counter()
    for p in build:
        if p['job'] in SYSTEM:
            u = matvec(p['R'], [0, -1, 0]); ups[tuple(round(c) for c in u)] += 1
    up = [0, -1, 0]  # LDraw convention: -y is up; OMR models stand as displayed
    def orient(p):
        u = matvec(p['R'], [0, -1, 0]); d = sum(a * b for a, b in zip(u, up))
        return 'up' if d > 0.9 else 'down' if d < -0.9 else 'side' if abs(d) < 0.1 else 'angled'
    # heights and horizontal distance in the world frame defined by `up`
    def height(p):
        return sum(a * b for a, b in zip(p['t'], up))
    cx = [sum(p['t'][i] for p in build) / len(build) for i in range(3)]
    def hdist(p):
        v = [a - b for a, b in zip(p['t'], cx)]; h = sum(a * b for a, b in zip(v, up))
        w = [a - h * b for a, b in zip(v, up)]
        return math.sqrt(sum(a * a for a in w))
    order = list(range(len(build)))
    rec = dict(set=set_num, name=rb.get('name', '?'), year=rb.get('year', '?'), n_rb=int(rb.get('num_parts', 0) or 0), g=g,
               nparts=len(build), nsteps=nsteps, steps_nonempty=sum(1 for s in steps if s['parts'] or s['sub']),
               has_steps=any(len(steps_of[n]) > 1 for n in models),
               unknown=sum(1 for p in placed if p['job'] == 'unknown'),
               rho_height=spearman(order, [height(p) for p in build]),
               rho_hdist=spearman(order, [hdist(p) for p in build]),
               subs=sub_info, build=build, steps=steps, up=up, root=root,
               in_sub=sum(1 for p in build if p['rel'] != 0) / len(build), outside_root=sum(1 for p in build if p['rel'] == -1) / len(build))
    # orientation
    sysp = [p for p in build if p['job'] in SYSTEM]
    rec['orient'] = collections.Counter(orient(p) for p in sysp)
    rec['orient_by_tenth'] = [collections.Counter(orient(p) for p in sysp if int(10 * p['step'] / nsteps) == k) for k in range(10)]
    # composition by build fraction (by part order)
    def frac_parts(lo, hi):
        a, b = int(lo * len(build)), int(hi * len(build))
        return build[a:b]
    rec['comp'] = {}
    for lo, hi, lab in [(0, .1, 'first 10%'), (0, .2, 'first 20%'), (0, 1 / 3, 'first third'), (1 / 3, 1, 'last two thirds')]:
        seg = frac_parts(lo, hi); c = collections.Counter(p['job'] for p in seg)
        rec['comp'][lab] = {k: v / max(1, len(seg)) for k, v in c.items()}
    # by step fraction too
    rec['comp_steps'] = {}
    for lo, hi, lab in [(0, .1, 'first 10%'), (0, .2, 'first 20%'), (0, 1 / 3, 'first third'), (1 / 3, 1.01, 'last two thirds')]:
        seg = [p for p in build if lo <= p['step'] / nsteps < hi]; c = collections.Counter(p['job'] for p in seg)
        rec['comp_steps'][lab] = {k: v / max(1, len(seg)) for k, v in c.items()}
    # parts per step through the build (fifths, by step)
    pps = [len([q for q in s['parts'] if part_job(q[0])[0] not in ('minifig', 'unknown')]) for s in steps]
    rec['pps'] = pps
    # when jobs go on: mean normalised position (by part order) of each job
    pos = collections.defaultdict(list)
    for i, p in enumerate(build):
        pos[p['job']].append(i / len(build))
    rec['pos'] = {k: (min(v), st.median(v), len(v)) for k, v in pos.items()}
    results.append(rec)
    print(set_num, g, rec['nparts'], rec['nsteps'], 'unknown', rec['unknown'], 'subs', len(sub_info), 'up', up, file=sys.stderr)

unk = collections.Counter()
for f, v in _cache.items():
    if v[0] == 'unknown': unk[(f, v[2][:50])] += 1
print('UNKNOWN', len(unk), sorted(unk)[:80], file=sys.stderr)
pickle.dump(results, open(OUTP, 'wb'))
print(len(results), 'models', file=sys.stderr)
