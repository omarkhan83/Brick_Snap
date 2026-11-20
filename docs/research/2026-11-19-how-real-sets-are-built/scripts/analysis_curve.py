"""Pin-and-beam share versus set size outside Technic. argv: cache.pkl classify.py out.md"""
import pickle, sys, collections, statistics as st
exec(open(sys.argv[2]).read())
parts, themes, sets, parent, tally = pickle.load(open(sys.argv[1], 'rb'))
rows = pickle.load(open(sys.argv[1].replace('cache.pkl', 'rows.pkl'), 'rb'))
def root(p):
    k = 0
    while p in parent and k < 5: p = parent[p]; k += 1
    return p
def sub(rp):
    r = parts.get(rp); c = r['part_cat_id'] if r else ''; nl = r['name'].lower() if r else ''
    if c in ('51','55'): return 'beam'
    if c == '53': return 'pin'
    if c in ('46','12','54'): return 'axle_conn'
    if c == '8' or nl.startswith('technic brick') or nl.startswith('technic plate'): return 'tbrick'
    return None
for r in rows:
    c = collections.Counter()
    for p, col, q in tally[r['set']]:
        rp = root(p)
        if job(rp, parts) == 'pinbeam': c[sub(rp)] += q
    r['sub'] = {k: c[k]/r['tot'] for k in ('beam','pin','axle_conn','tbrick')}
    r['nbeam'] = c['beam']
pickle.dump(rows, open(sys.argv[1].replace('cache.pkl', 'rows2.pkl'), 'wb'))
BINS = [(0,100),(100,200),(200,350),(350,500),(500,750),(750,1000),(1000,1500),(1500,2500),(2500,99999)]
lab = lambda a,b: f'{a}-{b}' if b < 99999 else f'{a}+'
out = open(sys.argv[3], 'w')
def P(*a): print(*a, file=out)
def med(x): return st.median(x) if x else float('nan')
nt = [r for r in rows if r['g'] != 'Technic']
P('### B1. All themes except Technic: pin-and-beam parts by set size\n')
P('pb = all pin/beam parts (Technic beams, pins, axles, connectors, bushes, Technic bricks and plates); beam = liftarm beams only; "frame" = set has at least 10 liftarm beams.\n')
P('| parts | sets | pb median % | pb mean % | beams median % | pins median % | axles+connectors median % | Technic bricks/plates median % | sets with pb >= 10 % | sets with a frame (>= 10 liftarms) |')
P('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for a, b in BINS:
    R = [r for r in nt if a <= r['n'] < b]
    if not R: continue
    P(f'| {lab(a,b)} | {len(R)} | {100*med([r["share"]["pinbeam"] for r in R]):.1f} | {100*sum(r["share"]["pinbeam"] for r in R)/len(R):.1f} | {100*med([r["sub"]["beam"] for r in R]):.1f} | {100*med([r["sub"]["pin"] for r in R]):.1f} | {100*med([r["sub"]["axle_conn"] for r in R]):.1f} | {100*med([r["sub"]["tbrick"] for r in R]):.1f} | {100*sum(r["share"]["pinbeam"]>=0.10 for r in R)/len(R):.0f} % | {100*sum(r["nbeam"]>=10 for r in R)/len(R):.0f} % |')
P('\n### B2. By theme group: median pin/beam share (%) and share of sets with a liftarm frame (>= 10 liftarms), by size\n')
P('Cells: median pb % / % of sets with >= 10 liftarms (number of sets). Empty = fewer than 3 sets.\n')
groups = [g for g, _ in GROUPS] + ['Other themes']
P('| group | ' + ' | '.join(lab(a,b) for a,b in BINS) + ' |')
P('|---|' + '---|'*len(BINS))
for g in groups:
    if g == 'Technic': continue
    cells = []
    for a, b in BINS:
        R = [r for r in nt if r['g'] == g and a <= r['n'] < b]
        cells.append('' if len(R) < 3 else f'{100*med([r["share"]["pinbeam"] for r in R]):.0f} / {100*sum(r["nbeam"]>=10 for r in R)/len(R):.0f}% ({len(R)})')
    P(f'| {g} | ' + ' | '.join(cells) + ' |')
P('\n### B2b. What the pin/beam parts are, by group (sets of 500 parts and more): medians and means, % of build parts\n')
P('| group | sets | beams (liftarms) median / mean | pins median / mean | axles+connectors+bushes median / mean | Technic bricks/plates median / mean |')
P('|---|---:|---:|---:|---:|---:|')
for g in groups:
    R = [r for r in rows if r['g'] == g and r['n'] >= 500]
    if len(R) < 3: continue
    f = lambda k: f'{100*med([r["sub"][k] for r in R]):.1f} / {100*sum(r["sub"][k] for r in R)/len(R):.1f}'
    P(f'| {g} | {len(R)} | {f("beam")} | {f("pin")} | {f("axle_conn")} | {f("tbrick")} |')
# typical sets each side: for chosen groups, sets just below and above the crossing
P('\n### B3. Typical sets on each side of the change (median-ish examples)\n')
P('For each group: three sets of 150-400 parts closest to the group median pb share in that band, and three of 700-2000 parts. Shows set number, name, year, parts, pb %, liftarms.\n')
for g in ['City','Friends','Speed Champions','Creator 3-in-1','Star Wars (play)','Ninjago','Super Heroes','Harry Potter','Ideas','Adult display (Icons/Creator Expert/UCS/Modular)','Botanicals','Architecture','BrickHeadz','Disney']:
    line = []
    for a, b in [(150,400),(700,2000)]:
        R = [r for r in nt if r['g'] == g and a <= r['n'] < b]
        if not R: line.append(f'{a}-{b}: none'); continue
        m = med([r['share']['pinbeam'] for r in R])
        R.sort(key=lambda r: abs(r['share']['pinbeam'] - m))
        line.append(f'{a}-{b} (median {100*m:.0f} %, {len(R)} sets): ' + '; '.join(f'{r["set"]} {r["name"]} ({r["year"]}, {r["n"]} parts, {100*r["share"]["pinbeam"]:.0f} %, {r["nbeam"]} liftarms)' for r in R[:3]))
    P(f'- **{g}**: ' + ' / '.join(line))
# highest pb non-technic big sets
P('\n### B4. Non-Technic sets over 500 parts with the highest pin/beam share (top 15) and the lowest (bottom 10 among sets over 1,500 parts)\n')
big = sorted([r for r in nt if r['n'] >= 500], key=lambda r: -r['share']['pinbeam'])
for r in big[:15]: P(f'- {r["set"]} {r["name"]} ({r["g"]}, {r["year"]}, {r["n"]} parts): pb {100*r["share"]["pinbeam"]:.0f} %, {r["nbeam"]} liftarms')
P('')
vb = sorted([r for r in nt if r['n'] >= 1500], key=lambda r: r['share']['pinbeam'])
for r in vb[:10]: P(f'- {r["set"]} {r["name"]} ({r["g"]}, {r["year"]}, {r["n"]} parts): pb {100*r["share"]["pinbeam"]:.1f} %, {r["nbeam"]} liftarms')
# correlation with year
P('\n### B5. Pin/beam share over time, sets of 500+ parts outside Technic\n')
P('| year | sets | pb median % | sets with >= 10 liftarms |'); P('|---|---:|---:|---:|')
for y in range(2015, 2027):
    R = [r for r in nt if r['year'] == y and r['n'] >= 500]
    if R: P(f'| {y} | {len(R)} | {100*med([r["share"]["pinbeam"] for r in R]):.1f} | {100*sum(r["nbeam"]>=10 for r in R)/len(R):.0f} % |')
out.close()
