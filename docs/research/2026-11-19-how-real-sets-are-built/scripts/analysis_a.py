"""Part A: shares of part jobs by theme group and size band. argv: cache.pkl classify.py out.md"""
import pickle, sys, collections, statistics as st
exec(open(sys.argv[2]).read())
parts, themes, sets, parent, tally = pickle.load(open(sys.argv[1], 'rb'))
def root(p):
    k = 0
    while p in parent and k < 5: p = parent[p]; k += 1
    return p
JOBS = ['pinbeam','technic_other','sideways','hinge','turntable','clip','bar','balljoint','wheel','wheelmount',
        'brick','plate','tile','slope','curved_slope','wedge','round','special_other','plant','panel_window','other']
rows = []  # per set record
for s, lst in tally.items():
    S = sets[s]; n = int(S['num_parts'])
    if n < 10: continue
    g = group_of(S['theme_id'], themes)
    if g is None or 'mosaic' in S['name'].lower(): continue
    jc = collections.Counter(); tot = 0; dparts = set(); dcol = set(); delem = set(); duplo = 0
    for p, col, q in lst:
        rp = root(p); j = job(rp, parts)
        if j == 'duplo': duplo += q; continue
        if j == 'minifig': continue
        jc[j] += q; tot += q; dparts.add(rp); dcol.add(col); delem.add((rp, col))
    if tot < 10 or duplo: continue
    rows.append(dict(set=s, name=S['name'], year=int(S['year']), n=n, g=g, b=band(n), tot=tot,
                     share={j: jc[j]/tot for j in JOBS}, dp=len(dparts), dc=len(dcol), de=len(delem),
                     parts=dparts))
pickle.dump(rows, open(sys.argv[1].replace('cache.pkl', 'rows.pkl'), 'wb'))
out = open(sys.argv[3], 'w')
def P(*a): print(*a, file=out)
def med(xs): return st.median(xs) if xs else float('nan')
def mean(xs): return sum(xs)/len(xs) if xs else float('nan')
groups = [g for g, _ in GROUPS] + ['Other themes']
P(f'Sets kept: {len(rows)}')
# overview by group
P('\n### A1. Mean share of build parts by job, by theme group (sets 2015 onward, all sizes)\n')
cols = [('pinbeam','pin/beam'),('technic_other','other Technic'),('sideways','sideways'),
        ('hinge','hinge'),('turntable','turntable'),('clip','clip'),('bar','bar'),('balljoint','ball/towball'),
        ('wheel','wheel/tyre'),('brick','brick'),('plate','plate'),('tile','tile'),('slope','slope'),('curved_slope','curved slope'),('wedge','wedge'),('round','round'),('special_other','other special'),('plant','plant'),('panel_window','panel/window'),('other','other')]
P('| group | sets | median parts | ' + ' | '.join(c[1] for c in cols) + ' |')
P('|---|---:|---:|' + '---:|'*len(cols))
for g in groups:
    R = [r for r in rows if r['g'] == g]
    if not R: continue
    P(f'| {g} | {len(R)} | {med([r["n"] for r in R]):.0f} | ' + ' | '.join(f'{100*mean([r["share"][c] for r in R]):.1f}' for c, _ in cols) + ' |')
R = rows
P(f'| **all** | {len(R)} | {med([r["n"] for r in R]):.0f} | ' + ' | '.join(f'{100*mean([r["share"][c] for r in R]):.1f}' for c, _ in cols) + ' |')
# by band overall
P('\n### A2. Mean share by job, by size band (all groups except Technic)\n')
P('| band | sets | ' + ' | '.join(c[1] for c in cols) + ' | distinct parts (median) | distinct colours (median) | distinct part+colour (median) |')
P('|---|---:|' + '---:|'*(len(cols)+3))
for b in ['a <150','b 150-500','c 500-1500','d >1500']:
    R = [r for r in rows if r['b'] == b and r['g'] != 'Technic']
    P(f'| {b[2:]} | {len(R)} | ' + ' | '.join(f'{100*mean([r["share"][c] for r in R]):.1f}' for c, _ in cols) +
      f' | {med([r["dp"] for r in R]):.0f} | {med([r["dc"] for r in R]):.0f} | {med([r["de"] for r in R]):.0f} |')
# group x band compact
P('\n### A3. By theme group and size band: shares (%) of the main jobs, and variety\n')
P('Columns: pin/beam = Technic pins, beams, axles, connectors, bushes, Technic bricks/plates; sideways = brackets and bricks/plates with side studs; joints = hinges + turntables + clips + bars + ball/towball joints; basic = plain bricks + plates + tiles + slopes + curved slopes. Distinct = medians.\n')
P('| group | band | sets | pin/beam | sideways | joints | brick | plate | tile | slope | curved slope | distinct parts | distinct colours |')
P('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for g in groups:
    for b in ['a <150','b 150-500','c 500-1500','d >1500']:
        R = [r for r in rows if r['g'] == g and r['b'] == b]
        if len(R) < 3: 
            if R: P(f'| {g} | {b[2:]} | {len(R)} | (too few) |||||||||| ')
            continue
        sh = lambda js: 100*mean([sum(r['share'][j] for j in js) for r in R])
        P(f'| {g} | {b[2:]} | {len(R)} | {sh(["pinbeam"]):.1f} | {sh(["sideways"]):.1f} | {sh(["hinge","turntable","clip","bar","balljoint"]):.1f} | {sh(["brick"]):.1f} | {sh(["plate"]):.1f} | {sh(["tile"]):.1f} | {sh(["slope"]):.1f} | {sh(["curved_slope"]):.1f} | {med([r["dp"] for r in R]):.0f} | {med([r["dc"] for r in R]):.0f} |')
out.close()
# diagnostics: what is in 'other'
oc = collections.Counter()
for s, lst in tally.items():
    for p, col, q in lst:
        rp = root(p)
        if job(rp, parts) == 'other': oc[(parts.get(rp, {}).get('part_cat_id'), rp, parts.get(rp, {}).get('name', '?')[:60])] += q
for k, v in oc.most_common(25): print(v, k)
