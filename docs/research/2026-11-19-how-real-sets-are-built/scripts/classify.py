"""Shared classifier: themes into groups, parts into jobs. Imported by exec() from analysis scripts."""
import re
MINIFIG_CATS = {'13','58','59','60','61','62','63','64','65','70','71','72','73','27'}
PB_CATS = {'8','12','46','51','53','54','55'}          # pin-and-beam frame
TECH_OTHER = {'17','22','25','26','40','52','44','45'} # gears, panels, steering, specials, electrics
SNOT_RE = re.compile(r'\bbracket\b|\bstuds? on (?:\w+ ){0,2}sides?\b|\bside studs?\b|\bstuds? on (?:1 |2 )?ends?\b|\bstuds on \d sides\b', re.I)
def job(p, parts):
    r = parts.get(p)
    if r is None: return 'other'
    c, n = r['part_cat_id'], r['name']; nl = n.lower()
    if c in MINIFIG_CATS: return 'minifig'
    if c == '4' : return 'duplo'
    if c in PB_CATS or nl.startswith('technic plate') or nl.startswith('technic brick'): return 'pinbeam'
    if c == '29': return 'wheel'
    if re.search(r'wheels? holder|wheel pins|stub axle', nl): return 'wheelmount'
    if c in TECH_OTHER: return 'technic_other'
    if c in ('5','9','23','20','21') and (SNOT_RE.search(n) or (c=='5' and 'with headlight' in nl)) and 'hinge' not in nl:
        return 'sideways'
    if c == '18':
        return 'turntable' if 'turntable' in nl else 'hinge'
    if 'hinge' in nl: return 'hinge'
    if re.search(r'towball|tow ball|ball joint|\bball\b|socket|rotation joint', nl): return 'balljoint'
    if 'clip' in nl or 'bar holder' in nl: return 'clip'
    if 'ingot' in nl: return 'tile'
    if c == '32' and re.match(r'(bar|antenna|lever)', nl) or re.search(r'\bbar\b|handle', nl) and c in ('5','9','15','21','20','32'): return 'bar'
    if c == '11': return 'brick'
    if c == '14': return 'plate'
    if c in ('19','15','67'): return 'tile'
    if c == '3': return 'slope'
    if c == '37': return 'curved_slope'
    if c in ('6','49'): return 'wedge'
    if c in ('20','21'): return 'round'
    if c in ('5','9'): return 'special_other'
    if c == '76': return 'plant'
    if c in ('16','23'): return 'panel_window'
    return 'other'

GROUPS = [  # (group, theme ids whose subtree belongs to it), first match wins walking up the tree
 ('Technic', {'1'}), ('Speed Champions', {'601'}), ('Creator 3-in-1', {'672'}),
 ('Adult display (Icons/Creator Expert/UCS/Modular)', {'721','673','171','155'}),
 ('Botanicals', {'769'}), ('Architecture', {'252'}), ('BrickHeadz', {'610'}),
 ('Ideas', {'576'}), ('City', {'52'}), ('Friends', {'494'}), ('Star Wars (play)', {'158'}),
 ('Ninjago', {'435'}), ('Super Heroes', {'695','696','482','487','697'}), ('Harry Potter', {'246'}),
 ('Minecraft', {'577'}), ('Disney', {'608'}), ('Creator (other)', {'22'}),
 ('Classic', {'621'}), ('Super Mario', {'690'}), ('Jurassic World', {'602'}),
 ('Dreamzzz', {'749'}), ('Monkie Kid', {'693'}),
]
EXCLUDE = {'504','497','501','535','709','688','254','443','507','19','598','408','440','441','480','398','258','719'}  # Duplo, books, gear, CMF, Art, DOTS, bulk, service, education, supplemental, promo, brand store, Primo, Quatro, Znap, FIRST LEGO League, Mindstorms, BrickLink Designer Program (fan designs)
def group_of(tid, themes):
    chain = []; t = tid
    while t:
        chain.append(t); t = themes[t]['parent_id'] if t in themes else ''
    if any(x in EXCLUDE for x in chain): return None
    for t in chain:
        for g, ids in GROUPS:
            if t in ids: return g
    return 'Other themes'
def band(n):
    return 'a <150' if n < 150 else 'b 150-500' if n < 500 else 'c 500-1500' if n < 1500 else 'd >1500'
