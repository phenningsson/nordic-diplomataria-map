#!/usr/bin/env python3
"""Resolve the SDHK place strings that no existing gazetteer covered.

Same SPARQL endpoint as the DD pass, but ranked with a Nordic prior: SDHK is a
Swedish corpus, so a same-named Nordic place beats a more famous one elsewhere.
Writes gazetteer/sdhk_wikidata.csv (cached).
"""
import collections, csv, os, sys, time

ROOT = '/home/pontus/dd_geo_map'
sys.path.insert(0, ROOT)
from resolve_wikidata import sparql, build_query, CC
from geocode_sdhk import variants, clean

NORDIC = {'Sweden', 'Finland', 'Norway', 'Denmark', 'Estonia', 'Iceland'}

def main():
    topn = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    unres = list(csv.DictReader(open(os.path.join(ROOT, 'data',
                                                  'sdhk_unresolved_places.csv'),
                                     encoding='utf-8')))
    ov = {}
    p = os.path.join(ROOT, 'gazetteer', 'sdhk_overrides.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            ov[r['raw']] = r

    # query the most specific variant of each string, plus override targets
    targets = {}
    for r in unres[:topn]:
        raw = r['issue_place_raw']
        vs = variants(raw)
        qn = vs[-1] if vs else clean(raw)          # the most reduced form
        if qn:
            targets.setdefault(qn, {'cty': None, 'n': 0})
            targets[qn]['n'] += int(r['n_charters'])
    for raw, o in ov.items():
        targets.setdefault(o['query_name'], {'cty': CC.get(o['country'].upper()), 'n': 0})
        if o.get('country'):
            targets[o['query_name']]['cty'] = CC.get(o['country'].upper())

    cache_p = os.path.join(ROOT, 'gazetteer', 'sdhk_wikidata.csv')
    cache = {}
    if os.path.exists(cache_p):
        for r in csv.DictReader(open(cache_p, encoding='utf-8')):
            cache[r['query_name']] = r

    todo = [q for q in targets if q not in cache]
    print(f'{len(targets)} query names, {len(todo)} not cached', flush=True)

    BATCH = 12
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            res = sparql(build_query(chunk))
        except Exception as e:
            print(f'  batch {i//BATCH+1} FAILED: {str(e)[:70]}', flush=True)
            continue
        cands = collections.defaultdict(list)
        for b in res['results']['bindings']:
            cands[b['nm']['value']].append({
                'sl': int(b['sl']['value']),
                'qid': b['item']['value'].split('/')[-1],
                'label': b['itemLabel']['value'],
                'lat': round(float(b['lat']['value']), 6),
                'lon': round(float(b['lon']['value']), 6),
                'country': b.get('ctyLabel', {}).get('value', '')})
        for q in chunk:
            cs = cands.get(q) or []
            want = targets[q]['cty']
            if want:
                cs = [c for c in cs if c['country'] == want]
            if not cs:
                continue
            # Nordic prior first, sitelinks second
            v = max(cs, key=lambda c: (c['country'] in NORDIC, c['sl']))
            cache[q] = {'query_name': q, 'qid': v['qid'], 'label': v['label'],
                        'lat': v['lat'], 'lon': v['lon'], 'country': v['country'],
                        'sitelinks': v['sl']}
        print(f'  batch {i//BATCH+1}/{(len(todo)+BATCH-1)//BATCH}: '
              f'{sum(1 for q in chunk if q in cache)}/{len(chunk)}', flush=True)
        time.sleep(1.5)

    with open(cache_p, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['query_name', 'qid', 'label', 'lat', 'lon',
                                          'country', 'sitelinks'])
        w.writeheader()
        for q in sorted(cache):
            w.writerow(cache[q])
    got = sum(targets[q]['n'] for q in targets if q in cache)
    print(f'\nresolved {len(cache)}/{len(targets)} names, covering {got} charters')
    print(f'wrote {cache_p}')

if __name__ == '__main__':
    main()
