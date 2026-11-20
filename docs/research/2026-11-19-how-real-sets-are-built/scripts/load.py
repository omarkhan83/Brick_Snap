"""Load Rebrickable CSVs into per-set part tallies for sets 2015+. Data dir is argv-given."""
import csv, collections, pickle, sys
def load(D, year_min=2015):
    parts = {r['part_num']: r for r in csv.DictReader(open(D + '/parts.csv'))}
    themes = {r['id']: r for r in csv.DictReader(open(D + '/themes.csv'))}
    sets = {r['set_num']: r for r in csv.DictReader(open(D + '/sets.csv')) if int(r['year']) >= year_min}
    # parent map for prints / patterns
    parent = {}
    for r in csv.DictReader(open(D + '/part_relationships.csv')):
        if r['rel_type'] in ('P', 'T'):
            parent[r['child_part_num']] = r['parent_part_num']
    inv = {}
    for r in csv.DictReader(open(D + '/inventories.csv')):
        if r['set_num'] in sets:
            v = int(r['version'])
            if r['set_num'] not in inv or v < inv[r['set_num']][1]:
                inv[r['set_num']] = (r['id'], v)
    invid = {i: s for s, (i, v) in inv.items()}
    tally = collections.defaultdict(list)  # set -> [(part, color, qty)]
    for r in csv.DictReader(open(D + '/inventory_parts.csv')):
        s = invid.get(r['inventory_id'])
        if s and r['is_spare'] == 'False':
            tally[s].append((r['part_num'], r['color_id'], int(r['quantity'])))
    return parts, themes, sets, parent, dict(tally)
if __name__ == '__main__':
    out = load(sys.argv[1])
    pickle.dump(out, open(sys.argv[2], 'wb'))
    print(len(out[2]), 'sets', len(out[4]), 'with parts')
