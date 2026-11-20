"""Most-used parts per job per theme group, wheel mountings by lift, variety vs size. argv: cache.pkl classify.py out.md"""
import pickle, sys, collections, statistics as st
exec(open(sys.argv[2]).read())
parts, themes, sets, parent, tally = pickle.load(open(sys.argv[1], 'rb'))
rows = pickle.load(open(sys.argv[1].replace('cache.pkl', 'rows2.pkl'), 'rb'))
out = open(sys.argv[3], 'w')
def P(*a): print(*a, file=out)
nm = lambda p: parts[p]['name'] if p in parts else p
JOINT = {'hinge','turntable','clip','bar','balljoint'}
def top(R, jobs, k):
    c = collections.Counter()
    for r in R:
        for p in r['parts']:
            if job(p, parts) in jobs: c[p] += 1
    return c.most_common(k)
for title, jobs in [('sideways-building parts (brackets, bricks and plates with side studs)', {'sideways'}),
                    ('hinge and joint parts (hinges, turntables, clips, bars, ball and towball joints)', JOINT)]:
    P(f'\n### C. The twenty commonest {title}, all groups except Technic (by number of sets using the part, any colour, prints folded into the plain part)\n')
    R = [r for r in rows if r['g'] != 'Technic']
    P(f'Sets: {len(R)}\n'); P('| rank | part (Rebrickable number) | name | job | sets | % of sets |'); P('|---:|---|---|---|---:|---:|')
    for i, (p, n) in enumerate(top(R, jobs, 20), 1):
        P(f'| {i} | {p} | {nm(p)} | {job(p, parts)} | {n} | {100*n/len(R):.0f} |')
    P(f'\nBy theme group, top 8 (number of sets using it / sets in the group):\n')
    for g in [g for g, _ in GROUPS] + ['Other themes']:
        R = [r for r in rows if r['g'] == g]
        if len(R) < 15: continue
        P(f'- **{g}** ({len(R)} sets): ' + '; '.join(f'{nm(p)} [{p}] {n}' for p, n in top(R, jobs, 8)))
# wheel mountings by lift
P('\n### C3. Wheel mountings: parts that go with wheels\n')
P('Method: among non-Technic sets, compare sets that contain a wheel or tyre (Rebrickable category "Wheels and Tyres") with sets that do not. A part counts as a wheel mounting if its name mentions a wheel holder, stub axle, axle or pin and it is at least three times as common in wheeled sets. Ranked by number of wheeled sets using it.\n')
R = [r for r in rows if r['g'] != 'Technic']
W = [r for r in R if any(job(p, parts) == 'wheel' for p in r['parts'])]
N = [r for r in R if r not in W]
Wset = set(r['set'] for r in W)
cw = collections.Counter(p for r in W for p in r['parts']); cn = collections.Counter(p for r in N for p in r['parts'])
import re
cand = []
for p, n in cw.items():
    if not re.search(r'wheel|axle|pin\b|pins\b', nm(p).lower()) or job(p, parts) == 'wheel': continue
    fw = n/len(W); fn = (cn[p]+1)/len(N)
    if fw/fn >= 3 and n >= 15: cand.append((n, p, fw/fn))
cand.sort(reverse=True)
P(f'Wheeled sets: {len(W)}; sets without wheels: {len(N)}.\n')
P('| rank | part | name | wheeled sets using it | % of wheeled sets | times more common than in wheel-less sets |'); P('|---:|---|---|---:|---:|---:|')
for i, (n, p, lift) in enumerate(cand[:20], 1): P(f'| {i} | {p} | {nm(p)} | {n} | {100*n/len(W):.0f} | {lift:.1f} |')
P('\nCommonest wheels and tyres by group (top 5):\n')
for g in ['City','Speed Champions','Creator 3-in-1','Friends','Super Heroes','Adult display (Icons/Creator Expert/UCS/Modular)','Other themes']:
    RG = [r for r in W if r['g'] == g]
    if len(RG) < 10: continue
    P(f'- **{g}** ({len(RG)} wheeled sets): ' + '; '.join(f'{nm(p)} [{p}] {n}' for p, n in top(RG, {'wheel'}, 5)))
# variety vs size
P('\n### D1. Variety against size (all groups except Technic and Classic)\n')
BINS = [(0,50),(50,100),(100,150),(150,250),(250,400),(400,600),(600,1000),(1000,1500),(1500,2500),(2500,99999)]
P('| parts | sets | distinct parts median (IQR) | distinct colours median | distinct part+colour median | parts per distinct part+colour (median) |'); P('|---|---:|---|---:|---:|---:|')
R = [r for r in rows if r['g'] not in ('Technic','Classic')]
def q(x, f): x = sorted(x); return x[int(f*(len(x)-1))]
for a, b in BINS:
    RR = [r for r in R if a <= r['n'] < b]
    if not RR: continue
    dp = [r['dp'] for r in RR]
    P(f'| {a}-{b if b<99999 else "+"} | {len(RR)} | {st.median(dp):.0f} ({q(dp,.25)}-{q(dp,.75)}) | {st.median([r["dc"] for r in RR]):.0f} | {st.median([r["de"] for r in RR]):.0f} | {st.median([r["tot"]/r["de"] for r in RR]):.1f} |')
# tiles/slopes by size
P('\n### D2. Finish parts against size (all groups except Technic, Classic, BrickHeadz): mean % of build parts\n')
cols = ['tile','slope','curved_slope','wedge','round','plate','brick','sideways','pinbeam']
P('| parts | sets | ' + ' | '.join(cols) + ' | joints (hinge+turntable+clip+bar+ball) |'); P('|---|---:|' + '---:|'*(len(cols)+1))
R = [r for r in rows if r['g'] not in ('Technic','Classic','BrickHeadz')]
for a, b in BINS:
    RR = [r for r in R if a <= r['n'] < b]
    if not RR: continue
    P(f'| {a}-{b if b<99999 else "+"} | {len(RR)} | ' + ' | '.join(f'{100*sum(r["share"][c] for r in RR)/len(RR):.1f}' for c in cols) + f' | {100*sum(sum(r["share"][j] for j in JOINT) for r in RR)/len(RR):.1f} |')
# the commonest parts overall in 100-ish sets
P('\n### D3. The parts found in the most sets of 80 to 150 parts (all groups except Technic)\n')
R = [r for r in rows if r['g'] != 'Technic' and 80 <= r['n'] < 150]
c = collections.Counter(p for r in R for p in r['parts'] if job(p, parts) not in ('minifig',))
P(f'Sets: {len(R)}\n'); P('| part | name | job | % of sets |'); P('|---|---|---|---:|')
for p, n in c.most_common(25): P(f'| {p} | {nm(p)} | {job(p, parts)} | {100*n/len(R):.0f} |')
out.close()
