"""Parse saved OMR list pages into a CSV. argv: pages_dir out.csv"""
import re, sys, html, glob, csv, os
recs = {}
for f in glob.glob(os.path.join(sys.argv[1], 'p*.html')):
    t = open(f, errors='replace').read()
    for r in re.findall(r'(?s)<tr[^>]*>(.*?)</tr>', t):
        cells = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip() for c in re.findall(r'(?s)<td[^>]*>(.*?)</td>', r)]
        link = re.findall(r'omr/sets/(\d+)', r)
        if len(cells) >= 6 and link: recs[cells[1]] = cells[1:6] + [link[0]]
w = csv.writer(open(sys.argv[2], 'w', newline=''))
w.writerow(['set_num', 'name', 'theme', 'year', 'models', 'omr_id'])
for k in sorted(recs): w.writerow(recs[k])
print(len(recs))
