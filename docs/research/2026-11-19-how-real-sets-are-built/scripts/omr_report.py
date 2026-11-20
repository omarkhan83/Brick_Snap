"""Tables for part B from omr.pkl. argv: omr.pkl out.md"""
import pickle, sys, collections, statistics as st

R = pickle.load(open(sys.argv[1], 'rb'))
out = open(sys.argv[2], 'w')
def P(*a): print(*a, file=out)
def med(x):
    x = [v for v in x if v == v]
    return st.median(x) if x else float('nan')
JOINT = {'hinge', 'turntable', 'clip', 'bar', 'balljoint'}
GROUPJ = [('pin/beam', {'pinbeam'}), ('other Technic', {'technic_other'}), ('brick', {'brick'}), ('plate', {'plate'}),
          ('tile', {'tile'}), ('slope/curve/wedge', {'slope', 'curved_slope', 'wedge'}), ('round', {'round'}),
          ('sideways', {'sideways'}), ('joints', JOINT), ('wheel', {'wheel', 'wheelmount'}),
          ('other special', {'special_other'}), ('plant/panel/other', {'plant', 'panel_window', 'other'})]
for r in R:
    r['ppstep'] = r['nparts'] / max(1, r['nsteps'])
    r['stepped'] = r['nsteps'] >= 10 and r['ppstep'] <= 8
    subs = {k: v for k, v in r['subs'].items() if not v['minifig']}
    r['nsub'] = len(subs)
    r['nsub_reused'] = sum(1 for v in subs.values() if v['refs'] > 1)
    o = r['orient']; tot = sum(o.values()) or 1
    r['side'] = o['side'] / tot; r['down'] = o['down'] / tot; r['angled'] = o['angled'] / tot
P('### B-T1. The sample: one row per model\n')
P('parts = build parts in the OMR file (minifigure and sticker parts left out); RB = Rebrickable part count for the set (includes minifigures and spares rules of its own); steps = steps after unrolling sub-models (a sub-model used twice is counted twice); stepped = has at least 10 steps and at most 8 parts per step, the files used for the order measures; sub-models = non-minifigure sub-models; height rho = rank correlation between build order and height of the part (positive = bottom up); outward rho = rank correlation between build order and horizontal distance from the model centre (positive = inside out); sideways / upside down = share of studded System parts whose top does not point up.\n')
P('| set | name | group | parts | RB | steps | parts/step | stepped | sub-models | used >1 | parts built in sub-models | height rho | outward rho | sideways | angled | upside down |')
P('|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|')
for r in sorted(R, key=lambda r: (r['g'], r['nparts'])):
    P(f"| {r['set']} | {r['name']} | {r['g']} | {r['nparts']} | {r['n_rb']} | {r['nsteps']} | {r['ppstep']:.1f} | {'yes' if r['stepped'] else 'no'} | {r['nsub']} | {r['nsub_reused']} | {100*r['in_sub']:.0f} % | {r['rho_height']:+.2f} | {r['rho_hdist']:+.2f} | {100*r['side']:.0f} % | {100*r['angled']:.0f} % | {100*r['down']:.0f} % |")
S = [r for r in R if r['stepped']]
P(f'\nModels in the sample: {len(R)}; with usable steps: {len(S)}.\n')
fam = lambda r: 'Technic' if r['g'] == 'Technic' else ('non-Technic <500' if r['nparts'] < 500 else 'non-Technic 500+')
for title, key in [('by order of parts placed', 'comp'), ('by share of steps', 'comp_steps')]:
    P(f'\n### B-T2. What the start of the build is made of ({title}): mean % of the parts in each segment, stepped models only\n')
    for F in ['non-Technic <500', 'non-Technic 500+', 'Technic']:
        RR = [r for r in S if fam(r) == F]
        if not RR: continue
        P(f'\n**{F}** ({len(RR)} models)\n')
        P('| segment | ' + ' | '.join(g for g, _ in GROUPJ) + ' |'); P('|---|' + '---:|' * len(GROUPJ))
        for seg in ['first 10%', 'first 20%', 'first third', 'last two thirds']:
            P(f'| {seg} | ' + ' | '.join(f"{100*sum(sum(r[key][seg].get(j, 0) for j in js) for r in RR)/len(RR):.1f}" for _, js in GROUPJ) + ' |')
# per model first-10% leader
P('\n### B-T3. Per model: the two commonest kinds of part in the first 10 % and first third of the parts placed\n')
P('| set | name | group | first 10 % | first third | rest |'); P('|---|---|---|---|---|---|')
def lead(d):
    agg = collections.Counter()
    for g, js in GROUPJ:
        agg[g] = sum(d.get(j, 0) for j in js)
    return ', '.join(f'{g} {100*v:.0f} %' for g, v in agg.most_common(2))
for r in sorted(S, key=lambda r: (r['g'], r['nparts'])):
    P(f"| {r['set']} | {r['name']} | {r['g']} | {lead(r['comp']['first 10%'])} | {lead(r['comp']['first third'])} | {lead(r['comp']['last two thirds'])} |")
# parts per step through the build
P('\n### B-T4. Parts per step through the build (stepped models): median over models of the mean parts per step in each fifth of the steps\n')
P('| family | models | 1st fifth | 2nd | 3rd | 4th | 5th | overall median parts/step |'); P('|---|---:|---:|---:|---:|---:|---:|---:|')
for F in ['non-Technic <500', 'non-Technic 500+', 'Technic', 'all']:
    RR = [r for r in S if F == 'all' or fam(r) == F]
    if not RR: continue
    cells = []
    for k in range(5):
        vals = []
        for r in RR:
            n = len(r['pps']); seg = r['pps'][int(k * n / 5):int((k + 1) * n / 5)]
            if seg: vals.append(sum(seg) / len(seg))
        cells.append(f'{med(vals):.1f}')
    P(f"| {F} | {len(RR)} | " + ' | '.join(cells) + f" | {med([med(r['pps']) for r in RR]):.1f} |")
dist = collections.Counter()
for r in S:
    for v in r['pps']:
        dist[min(v, 10)] += 1
tot = sum(dist.values())
P('\nDistribution of parts per step over all stepped models (' + str(tot) + ' steps): ' + ', '.join(f"{'10+' if k == 10 else k}: {100*v/tot:.0f} %" for k, v in sorted(dist.items())) + '\n')
# orientation by tenth
P('\n### B-T5. Studded System parts placed sideways or upside down, by tenth of the steps (stepped models, non-Technic)\n')
RR = [r for r in S if r['g'] != 'Technic']
P('| tenth | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |'); P('|---|' + '---:|' * 10)
for lab, key in [('sideways (90 degrees) %', 'side'), ('angled %', 'angled'), ('upside down %', 'down')]:
    cells = []
    for k in range(10):
        c = collections.Counter()
        for r in RR: c.update(r['orient_by_tenth'][k])
        t = sum(c.values()) or 1
        cells.append(f'{100*c[key]/t:.0f}')
    P(f'| {lab} (pooled parts) | ' + ' | '.join(cells) + ' |')
P(f'\nModels: {len(RR)}. Median per model over the whole build: sideways {100*med([r["side"] for r in RR]):.0f} %, upside down {100*med([r["down"] for r in RR]):.0f} %.\n')
# when moving parts go on
P('\n### B-T6. When wheels, hinges and other moving parts go on (stepped models): position in the build as a share of parts placed (0 = first part, 1 = last)\n')
P('| kind | models that have it | median first appearance | median of each model\'s median position |'); P('|---|---:|---:|---:|')
for lab, js in [('wheels and tyres', {'wheel'}), ('wheel holders', {'wheelmount'}), ('hinges', {'hinge'}), ('turntables', {'turntable'}),
                ('ball and towball joints', {'balljoint'}), ('clips', {'clip'}), ('bars and handles', {'bar'}),
                ('gears and other Technic', {'technic_other'}), ('pin/beam', {'pinbeam'}), ('sideways-building parts', {'sideways'}),
                ('tiles', {'tile'}), ('slopes, curves, wedges', {'slope', 'curved_slope', 'wedge'}), ('plain bricks', {'brick'}), ('plates', {'plate'})]:
    firsts, meds = [], []
    for r in S:
        ps = [i / r['nparts'] for i, p in enumerate(r['build']) if p['job'] in js]
        if ps:
            firsts.append(min(ps)); meds.append(st.median(ps))
    if firsts:
        P(f'| {lab} | {len(firsts)} | {med(firsts):.2f} | {med(meds):.2f} |')
# growth summary
P('\n### B-T7. How the model grows (stepped models)\n')
for F in ['non-Technic <500', 'non-Technic 500+', 'Technic']:
    RR = [r for r in S if fam(r) == F]
    if not RR: continue
    P(f"- **{F}** ({len(RR)} models): height rho median {med([r['rho_height'] for r in RR]):+.2f} (positive in {sum(r['rho_height'] > 0.2 for r in RR)} of {len(RR)} above +0.2); outward rho median {med([r['rho_hdist'] for r in RR]):+.2f} (above +0.2 in {sum(r['rho_hdist'] > 0.2 for r in RR)}); non-minifigure sub-models per model median {med([r['nsub'] for r in RR]):.0f} (range {min(r['nsub'] for r in RR)}-{max(r['nsub'] for r in RR)}); sub-models used more than once, median {med([r['nsub_reused'] for r in RR]):.0f}; share of parts built inside sub-models median {100*med([r['in_sub'] for r in RR]):.0f} %.")
# submodel sizes
P('\n### B-T8. Sub-model sizes (stepped models, non-minifigure sub-models, own parts only, nested sub-models not included)\n')
for F in ['non-Technic <500', 'non-Technic 500+', 'Technic']:
    RR = [r for r in S if fam(r) == F]
    sizes = [v['own'] for r in RR for v in r['subs'].values() if not v['minifig']]
    refs = [v['refs'] for r in RR for v in r['subs'].values() if not v['minifig']]
    if sizes:
        q = sorted(sizes)
        P(f'- **{F}**: {len(sizes)} sub-models; own parts median {st.median(sizes):.0f}, quartiles {q[len(q)//4]}-{q[3*len(q)//4]}, largest {q[-1]}; used once {sum(1 for x in refs if x == 1)}, twice {sum(1 for x in refs if x == 2)}, three or more times {sum(1 for x in refs if x >= 3)}; never referenced (alternates or leftovers in the file) {sum(1 for x in refs if x == 0)}.')
out.close()
out = open(sys.argv[2], 'a')
P('\n### B-T9. Is there a pin-and-beam core? Share of pin/beam parts in the first 20 % of parts placed against the whole model (stepped, non-Technic models that contain any)\n')
P('| set | name | group | parts | pin/beam in first 20 % | pin/beam overall | ratio |'); P('|---|---|---|---:|---:|---:|---:|')
rows = []
for r in S:
    if r['g'] == 'Technic': continue
    allpb = sum(1 for p in r['build'] if p['job'] == 'pinbeam') / r['nparts']
    if allpb == 0: continue
    first = r['comp']['first 20%'].get('pinbeam', 0)
    rows.append((first / allpb, r, first, allpb))
for ratio, r, first, allpb in sorted(rows, key=lambda x: -x[0]):
    P(f"| {r['set']} | {r['name']} | {r['g']} | {r['nparts']} | {100*first:.0f} % | {100*allpb:.0f} % | {ratio:.1f} |")
P(f"\nModels where pin/beam parts are at least twice as common in the first 20 % as overall: {sum(1 for x in rows if x[0] >= 2)} of {len(rows)}; where they are at most half as common: {sum(1 for x in rows if x[0] <= 0.5)}.\n")
# orientation by thirds per model
P('\n### B-T10. Sideways and angled System parts by third of the build, median over stepped non-Technic models\n')
P('| third | models | sideways (90 degrees) median % | angled median % | upside down median % |'); P('|---|---:|---:|---:|---:|')
RR = [r for r in S if r['g'] != 'Technic']
for k, lab in enumerate(['first', 'middle', 'last']):
    vals = {'side': [], 'angled': [], 'down': []}
    for r in RR:
        c = collections.Counter()
        for t in range(10):
            if (k == 0 and t < 3) or (k == 1 and 3 <= t < 7) or (k == 2 and t >= 7): c.update(r['orient_by_tenth'][t])
        tot = sum(c.values())
        if tot:
            for key in vals: vals[key].append(c[key] / tot)
    P(f"| {lab} | {len(vals['side'])} | {100*med(vals['side']):.0f} | {100*med(vals['angled']):.0f} | {100*med(vals['down']):.0f} |")
out.close()
