#!/usr/bin/env python3
"""Resolve issue-place strings to coordinates via the Wikidata SPARQL endpoint.

Writes gazetteer/wikidata_resolved.csv (cached; reruns only query new strings).
Ranking is by sitelink count within a European bounding box, which reliably picks
the historically prominent European place over same-named minor/New-World ones.
"""
import collections, csv, json, os, re, sys, time, urllib.parse, urllib.request

ROOT = '/home/pontus/dd_geo_map'
ENDPOINT = 'https://query.wikidata.org/sparql'
UA = 'dd-geo-map/0.1 (medieval charter mapping; henningssonpontus@gmail.com)'
# medieval Danish charter horizon: Iceland/Iberia to the Baltic/Levant fringe
BBOX = (34.0, 72.0, -12.0, 40.0)          # latmin, latmax, lonmin, lonmax
LANGS = ['da', 'sv', 'nb', 'nn', 'de', 'en', 'la', 'fr', 'it', 'nl',
         'pl', 'et', 'lv', 'fi', 'cs', 'es']

NULL_TOKENS = {'', 'empty', 'nil', 'ukendt', 'unknown', '-'}
# ISO code -> English Wikidata country label, for country-constrained overrides.
# Needed because cross-language altLabels collide badly: 'Konstanz' is the
# Romanian name of Constanta, 'Vienne' the French name of Vienna.
CC = {'DK':'Denmark','SE':'Sweden','NO':'Norway','FI':'Finland','DE':'Germany',
      'FR':'France','IT':'Italy','PL':'Poland','EE':'Estonia','LV':'Latvia',
      'LT':'Lithuania','NL':'Netherlands','BE':'Belgium','GB':'United Kingdom',
      'CZ':'Czech Republic','AT':'Austria','CH':'Switzerland','ES':'Spain',
      'VA':'Vatican City','RU':'Russia'}

def clean(raw):
    """Normalise a raw issue-place string into a query name."""
    s = raw.strip()
    s = re.sub(r'^\[(.*)\]$', r'\1', s).strip()      # [Næstved] -> Næstved (uncertain)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'^S\.\s+', 'Sankt ', s)
    return s

def sparql(query, retries=4):
    # POST: the VALUES clause makes GET URLs exceed the endpoint's header limit
    body = urllib.parse.urlencode({'query': query, 'format': 'json'}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        'User-Agent': UA, 'Accept': 'application/sparql-results+json',
        'Content-Type': 'application/x-www-form-urlencoded'})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if a == retries - 1:
                raise
            time.sleep(5 * (a + 1))

def build_query(names):
    latmin, latmax, lonmin, lonmax = BBOX
    values = ' '.join(f'"{n}"@{lg}' for n in names for lg in LANGS)
    return f'''
SELECT ?nm ?item ?itemLabel ?lat ?lon ?sl ?ctyLabel WHERE {{
  VALUES ?nm {{ {values} }}
  {{ ?item rdfs:label ?nm }} UNION {{ ?item skos:altLabel ?nm }}
  ?item wdt:P625 ?coord .
  ?item wikibase:sitelinks ?sl .
  OPTIONAL {{ ?item wdt:P17 ?cty }}
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  FILTER(?lat > {latmin} && ?lat < {latmax} && ?lon > {lonmin} && ?lon < {lonmax})
  FILTER(?sl > 2)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,da,de". }}
}}'''

def main():
    topn = int(sys.argv[1]) if len(sys.argv) > 1 else 250

    counts = {r['issue_place_raw']: int(r['n_charters'])
              for r in csv.DictReader(
                  open(os.path.join(ROOT, 'data', 'issue_place_counts.csv'),
                       encoding='utf-8'))}

    overrides = {}
    op = os.path.join(ROOT, 'gazetteer', 'overrides.csv')
    if os.path.exists(op):
        for r in csv.DictReader(open(op, encoding='utf-8')):
            overrides[r['raw']] = r

    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:topn]
    targets = {}                      # query_name -> {'raws':set, 'cty':label|None}
    for raw, _ in ranked:
        if raw.strip().lower() in NULL_TOKENS:
            continue
        ov = overrides.get(raw)
        qn = ov['query_name'] if ov else clean(raw)
        if qn == 'REVIEW':          # deliberately withheld for human adjudication
            continue
        cty = CC.get((ov or {}).get('country', '').strip().upper())
        t = targets.setdefault(qn, {'raws': set(), 'cty': cty})
        t['raws'].add(raw)
        if cty:
            t['cty'] = cty

    def ckey(qn):
        return qn + '|' + (targets[qn]['cty'] or '')

    cache_p = os.path.join(ROOT, 'gazetteer', 'wikidata_resolved.csv')
    cache = {}
    if os.path.exists(cache_p):
        for r in csv.DictReader(open(cache_p, encoding='utf-8')):
            cache[r['query_name']] = r

    todo = [q for q in targets if ckey(q) not in cache]
    print(f'{len(targets)} distinct query names, {len(todo)} not cached', flush=True)

    BATCH = 12
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            res = sparql(build_query(chunk))
        except Exception as e:
            print(f'  batch {i//BATCH+1} FAILED: {e}', flush=True)
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
            if want:                       # a stated country is a hard constraint
                cs = [c for c in cs if c['country'] == want]
            if not cs:
                continue
            v = max(cs, key=lambda c: c['sl'])
            cache[ckey(q)] = {'query_name': ckey(q), 'qid': v['qid'],
                              'label': v['label'], 'lat': v['lat'], 'lon': v['lon'],
                              'country': v['country'], 'sitelinks': v['sl']}
        print(f'  batch {i//BATCH+1}/{(len(todo)+BATCH-1)//BATCH}: '
              f'{sum(1 for q in chunk if ckey(q) in cache)}/{len(chunk)} resolved',
              flush=True)
        time.sleep(2.0)

    with open(cache_p, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['query_name', 'qid', 'label', 'lat', 'lon',
                                          'country', 'sitelinks'])
        w.writeheader()
        for q in sorted(cache):
            w.writerow(cache[q])

    # curated table keyed on the RAW charter string
    cp = os.path.join(ROOT, 'gazetteer', 'curated_places.csv')
    n_ok = n_missing = 0
    cov = 0
    with open(cp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['issue_place_raw', 'n_charters', 'query_name', 'modern_name',
                    'qid', 'lat', 'lon', 'country', 'source', 'confidence', 'note'])
        for raw, n in ranked:
            if raw.strip().lower() in NULL_TOKENS:
                continue
            ov = overrides.get(raw)
            qn = ov['query_name'] if ov else clean(raw)
            if qn == 'REVIEW':
                n_missing += 1
                w.writerow([raw, n, '', '', '', '', '', '', 'needs_review', 'none',
                            ov['note']])
                continue
            hit = cache.get(ckey(qn)) if qn in targets else None
            uncertain = bool(re.match(r'^\[.*\]$', raw.strip()))
            if hit:
                n_ok += 1; cov += n
                conf = 'high'
                if ov: conf = 'curated'
                if uncertain: conf = 'medium'
                w.writerow([raw, n, qn, hit['label'], hit['qid'], hit['lat'], hit['lon'],
                            hit['country'], 'wikidata' + ('+override' if ov else ''),
                            conf, ov['note'] if ov else
                            ('bracketed = uncertain in source' if uncertain else '')])
            else:
                n_missing += 1
                w.writerow([raw, n, qn, '', '', '', '', '', 'unresolved', 'none',
                            ov['note'] if ov else ''])
    total_tagged = sum(counts.values())
    print(f'\nresolved {n_ok}/{n_ok+n_missing} of top-{topn} strings')
    print(f'charter coverage from curated table: {cov}/{total_tagged} '
          f'({100*cov/total_tagged:.1f}% of tagged)')
    print(f'wrote {cp}')

if __name__ == '__main__':
    main()
