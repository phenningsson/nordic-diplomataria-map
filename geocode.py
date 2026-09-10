#!/usr/bin/env python3
"""Resolve every charter's issue place to coordinates.

Resolver chain, most precise first; every row records geo_source + confidence so
the provenance stays auditable and unresolved places stay visible.

  1 curated/Wikidata on the raw string
  2 curated/Wikidata on the cleaned string ([Næstved] -> Næstved)
  3 curated/Wikidata on the head of an institutional compound
    ('Ribe byting' -> 'Ribe', 'Foran Helsingborg' -> 'Helsingborg')
  4 DigDag on that head, preferring place-like layers  ('Houlbjerg herredsting'
    -> Houlbjerg Herred centroid) -- the Danish long tail
  5 DigDag on the cleaned string
  else unresolved (kept, flagged)
"""
import csv, json, os, re, sys, collections
import numpy as np

ROOT = '/home/pontus/dd_geo_map'
NULL_TOKENS = {'', 'empty', 'nil', 'ukendt', 'unknown', '-'}

# assembly / residence compounds: the head noun carries the location
INST_SUFFIX = re.compile(
    r'\s+(by-?ting|byting|herredsting|herreds\s+ting|landsting|sysselting|ting|'
    r'slot|kloster|domkirke|kirke|gård|gaard|hus|birketing)$', re.I)
INST_PREFIX = re.compile(r'^(foran|ved|uden\s+for|udenfor|nær|paa|på|i)\s+', re.I)
# DigDag layers that denote settlements/territories rather than modern admin units
PLACE_LAYERS = ['Koebstad', 'Stadt_Koebstad', 'Sogn', 'Herred', 'Geografisk_Herred',
                'Birk', 'Ejerlav', 'Len', 'Pastorat', 'Provsti', 'Flecke_Flaekke']

FOLD = str.maketrans({'å': 'aa', 'Å': 'aa', 'ä': 'ae', 'Ä': 'ae', 'ø': 'oe', 'Ø': 'oe',
                      'ö': 'oe', 'Ö': 'oe', 'æ': 'ae', 'Æ': 'ae', 'ü': 'ue', 'Ü': 'ue'})

def norm(s):
    import unicodedata
    s = s.translate(FOLD).lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in s)
    return ' '.join(s.split())

def clean(raw):
    s = re.sub(r'^\[(.*)\]$', r'\1', raw.strip()).strip()
    return re.sub(r'\s+', ' ', s)

def head_of(s):
    """'Ribe byting' -> 'Ribe'; 'Foran Helsingborg' -> 'Helsingborg'."""
    prev = None
    while prev != s:
        prev = s
        s = INST_PREFIX.sub('', s).strip()
        s = INST_SUFFIX.sub('', s).strip()
        s = re.sub(r"[’']s$", '', s).strip()
        s = re.sub(r's$', '', s).strip() if re.search(
            r'(?<=\w)s$', s) and len(s) > 4 else s
    return s

def main():
    # ---- curated / Wikidata table, keyed on raw and on query name -------
    cur_raw, cur_name = {}, {}
    with open(os.path.join(ROOT, 'gazetteer', 'curated_places.csv'),
              encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['lat']:
                rec = {'name': r['modern_name'], 'lat': float(r['lat']),
                       'lon': float(r['lon']), 'country': r['country'],
                       'qid': r['qid'], 'conf': r['confidence']}
                cur_raw[r['issue_place_raw']] = rec
                cur_name.setdefault(norm(r['query_name']), rec)
                cur_name.setdefault(norm(r['issue_place_raw']), rec)

    # ---- DigDag index, unambiguous names only ---------------------------
    dig = collections.defaultdict(list)
    with open(os.path.join(ROOT, 'data', 'gazetteer_digdag_units.jsonl'),
              encoding='utf-8') as f:
        for line in f:
            u = json.loads(line)
            dig[u['name_norm']].append(u)

    def digdag_lookup(name):
        us = dig.get(norm(name))
        if not us:
            return None
        pref = [u for u in us if u['layer'] in PLACE_LAYERS] or us
        # only accept if the candidates agree on where they are
        lats = [u['lat'] for u in pref]; lons = [u['lon'] for u in pref]
        mlat, mlon = float(np.median(lats)), float(np.median(lons))
        spread = max((float(np.hypot((la - mlat) * 111.0,
                                     (lo - mlon) * 111.0 * np.cos(np.radians(mlat))))
                      for la, lo in zip(lats, lons)), default=0.0)
        if spread > 25.0:
            return {'ambiguous': True, 'n': len(pref)}
        order = {l: i for i, l in enumerate(PLACE_LAYERS)}
        best = sorted(pref, key=lambda u: order.get(u['layer'], 99))[0]
        return {'ambiguous': False, 'name': best['navn'], 'lat': best['lat'],
                'lon': best['lon'], 'layer': best['layer'], 'art': best['art'],
                'n': len(pref)}

    def resolve(raw):
        if raw is None or raw.strip().lower() in NULL_TOKENS:
            return None, 'null_placeholder', 'none'
        c = clean(raw)
        uncertain = bool(re.match(r'^\[.*\]$', raw.strip()))
        for key, src in ((raw, 'curated'), (c, 'curated')):
            if key in cur_raw:
                h = cur_raw[key]
                return h, src, ('medium' if uncertain else h['conf'])
        if norm(c) in cur_name:
            h = cur_name[norm(c)]
            return h, 'curated', ('medium' if uncertain else 'high')
        h2 = head_of(c)
        if h2 and h2 != c:
            if h2 in cur_raw or norm(h2) in cur_name:
                h = cur_raw.get(h2) or cur_name[norm(h2)]
                return h, 'curated_head', 'medium'
            d = digdag_lookup(h2)
            if d and not d['ambiguous']:
                return ({'name': d['name'], 'lat': d['lat'], 'lon': d['lon'],
                         'country': 'Denmark', 'qid': '', 'conf': 'medium'},
                        f'digdag:{d["layer"]}', 'medium')
        d = digdag_lookup(c)
        if d and not d['ambiguous']:
            return ({'name': d['name'], 'lat': d['lat'], 'lon': d['lon'],
                     'country': 'Denmark', 'qid': '', 'conf': 'medium'},
                    f'digdag:{d["layer"]}', 'medium')
        if d and d['ambiguous']:
            return None, 'digdag_ambiguous', 'none'
        return None, 'unresolved', 'none'

    # ---- apply ----------------------------------------------------------
    inp = os.path.join(ROOT, 'data', 'charters.jsonl')
    outp = os.path.join(ROOT, 'data', 'charters_geocoded.jsonl')
    src_counts = collections.Counter()
    unresolved = collections.Counter()
    n = n_geo = 0
    with open(inp, encoding='utf-8') as f, open(outp, 'w', encoding='utf-8') as g:
        for line in f:
            rec = json.loads(line)
            n += 1
            hit, src, conf = resolve(rec['issue_place_raw'])
            rec['place_name'] = hit['name'] if hit else None
            rec['lat'] = hit['lat'] if hit else None
            rec['lon'] = hit['lon'] if hit else None
            rec['country'] = hit['country'] if hit else None
            rec['wikidata_qid'] = hit['qid'] if hit else None
            rec['geo_source'] = src
            rec['confidence'] = conf
            src_counts[src] += 1
            if hit:
                n_geo += 1
            elif src not in ('null_placeholder',):
                unresolved[rec['issue_place_raw']] += 1
            g.write(json.dumps(rec, ensure_ascii=False) + '\n')

    tagged = sum(v for k, v in src_counts.items() if k != 'null_placeholder')
    print(f'charters            : {n}')
    print(f'tagged issue place  : {tagged}')
    print(f'geocoded            : {n_geo}  ({100*n_geo/tagged:.1f}% of tagged)')
    print('\nby geo_source:')
    for k, v in src_counts.most_common():
        if k.startswith('digdag:'):
            continue
        print(f'  {k:<24} {v:>6}')
    dg = {k: v for k, v in src_counts.items() if k.startswith('digdag:')}
    if dg:
        print(f'  {"digdag (all layers)":<24} {sum(dg.values()):>6}')
        for k, v in sorted(dg.items(), key=lambda kv: -kv[1]):
            print(f'      {k:<20} {v:>6}')

    up = os.path.join(ROOT, 'data', 'unresolved_places.csv')
    with open(up, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['issue_place_raw', 'n_charters'])
        for k, v in unresolved.most_common():
            w.writerow([k, v])
    print(f'\nunresolved strings  : {len(unresolved)}  '
          f'({sum(unresolved.values())} charters)')
    print(f'wrote {outp}')
    print(f'wrote {up}')

if __name__ == '__main__':
    main()
