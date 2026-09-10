#!/usr/bin/env python3
"""Geocode SDHK issue places, reusing every gazetteer already built.

Chain, most precise first:
  1 SDHK overrides (hand-pinned, country-constrained)
  2 DD curated/Wikidata table   - the papal curia and Hanseatic hubs SDHK shares
  3 DN places (already geocoded)
  4 Diplomatarium Fennicum       - Abo, Viborg and the Finnish side
  5 Wikidata SPARQL for whatever is left and frequent enough to matter
  6 TORA (Aldre geometriska kartorna) - Swedish settlements and, for 'X haradsting',
    the centroid of that harad
  7 GeoNames, settlements and admin units only - deliberately NOT farms
  else unresolved (kept, flagged)

Every row carries `precision`: 'point' for a located settlement, 'harad' for a
hundred-level centroid. The rule throughout is that a coarse placement which is
certainly in the right region beats a precise one that may be in the wrong province,
so ambiguity backs off to a larger unit rather than guessing or dropping the row.
"""
import csv, io, json, os, re, sys, collections
import numpy as np

ROOT = '/home/pontus/dd_geo_map'
sys.path.insert(0, ROOT)
from geocode import norm

QUOTES = '"”“„«»’‘'
INST = re.compile(r'\s+(kloster|slott|kyrka|domkyrka|gård|gaard|hus|socken|'
                  r'prästgård|borg|kungsgård|biskopsgård|tingsplats|tingställe)\.?$', re.I)
IN_PLACE = re.compile(r'^.+?\s+i\s+([A-ZÅÄÖ][\wåäöéü-]+)$')   # Peterskyrkan i Rom -> Rom

def clean(s):
    s = (s or '').strip().strip(QUOTES).strip()
    s = re.sub(r'^\((.*)\)\.?$', r'\1', s).strip()
    s = re.sub(r'\s*\([^)]*\)', '', s).strip()
    s = s.replace('(', '').replace(')', '').strip()
    s = s.strip(QUOTES).strip().rstrip('.').strip()
    return re.sub(r'\s+', ' ', s)

def variants(s):
    """Every form worth trying, most specific first."""
    out, seen = [], set()
    def add(x):
        x = (x or '').strip().rstrip('.').strip()
        if x and x not in seen:
            seen.add(x); out.append(x)
    c = clean(s)
    add(c)
    # '(Vadstena) kloster' loses its head to the parenthesis-stripping in clean(),
    # leaving the bare generic 'kloster'. Keep a form with the brackets merely removed.
    kept = re.sub(r'\s+', ' ', re.sub(r'[()]', ' ', (s or ''))).strip().strip(QUOTES).strip()
    if kept:
        add(kept)
    m = IN_PLACE.match(c)                       # 'Peterskyrkan i Rom' -> 'Rom'
    if m:
        add(m.group(1))
    h = c
    prev = None
    while prev != h:                            # 'Stockholms slott' -> 'Stockholms'
        prev = h
        h = INST.sub('', h).strip().rstrip('.').strip()
    add(h)
    if len(h) > 4 and h.endswith('s'):          # Swedish genitive: 'Stockholms'
        add(h[:-1])
    if len(c) > 4 and c.endswith('s'):
        add(c[:-1])
    return out

def load_gazetteers():
    """name_norm -> (lat, lon, label, source), first writer wins per source order."""
    g = {}
    def put(k, lat, lon, label, src):
        k = norm(k)
        if k and k not in g:
            g[k] = (float(lat), float(lon), label, src)

    for r in csv.DictReader(open(os.path.join(ROOT, 'gazetteer', 'curated_places.csv'),
                                 encoding='utf-8')):
        if r['lat']:
            put(r['query_name'], r['lat'], r['lon'], r['modern_name'], 'dd_curated')
            put(r['issue_place_raw'], r['lat'], r['lon'], r['modern_name'], 'dd_curated')

    dn = {}
    for line in open(os.path.join(ROOT, 'data', 'dn_charters_geocoded.jsonl'),
                     encoding='utf-8'):
        j = json.loads(line)
        dn.setdefault(j['place_name'], (j['lat'], j['lon']))
    for nm, (la, lo) in dn.items():
        put(nm, la, lo, nm, 'dn')

    for row in csv.reader(open(os.path.join(ROOT, 'df_platser.csv'),
                               encoding='utf-8-sig'), delimiter=';'):
        if len(row) >= 5 and row[3] and row[4]:
            try:
                put(row[0].split(',')[0], row[3], row[4], row[0], 'fennicum')
            except ValueError:
                pass

    # DigDag is deliberately NOT in this chain. It is a Danish-only gazetteer, and
    # against a Swedish corpus it produces cross-border false friends: Torso (the
    # island in Vanern) -> Torso Ejerlav in Jutland, Risinge kyrka (Ostergotland)
    # -> Risinge Ejerlav on Fyn, Karby/Lot/Horn/Broby likewise. It contributed 119
    # charters, most of them wrong. The Danish places SDHK actually names - Lund,
    # Kobenhavn, Helsingborg, Malmo - are already in the DD curated table.
    return g

def load_geonames(countries=('SE', 'FI')):
    """Settlements (P) and admin units (A) only. Farms and spot features are
    excluded on purpose: they are the records most likely to match the wrong
    place, and a farm-level hit in the wrong province is worse than no hit."""
    base = os.path.join(ROOT, 'external', 'geonames')
    idx = collections.defaultdict(list)
    for c in countries:
        f = os.path.join(base, f'{c}_x', f'{c}.txt')
        if not os.path.exists(f):
            continue
        for line in open(f, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) < 9 or p[6] not in ('P', 'A'):
                continue
            try:
                lat, lon = float(p[4]), float(p[5])
            except ValueError:
                continue
            for nm in {p[1], p[2]} | {x for x in p[3].split(',') if x}:
                k = norm(nm)
                if k:
                    idx[k].append((lat, lon, p[1]))
    return idx

def main():
    g = load_gazetteers()
    print(f'combined gazetteer: {len(g):,} name keys', flush=True)

    ov = {}
    p = os.path.join(ROOT, 'gazetteer', 'sdhk_overrides.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            ov[norm(r['raw'])] = r

    # Wikidata results resolved for SDHK specifically (built by the --resolve pass)
    wk = {}
    wp = os.path.join(ROOT, 'gazetteer', 'sdhk_wikidata.csv')
    if os.path.exists(wp):
        for r in csv.DictReader(open(wp, encoding='utf-8')):
            if r['lat']:
                wk[norm(r['query_name'])] = (float(r['lat']), float(r['lon']),
                                             r['label'], 'wikidata')

    try:
        from tora import Tora
        tora = Tora()
        print(f'TORA: {tora.n_units:,} units, {len(tora.harad)} härad', flush=True)
    except Exception as e:
        print(f'TORA unavailable ({e})'); tora = None

    gn = load_geonames()
    print(f'GeoNames (P/A, SE+FI): {len(gn):,} name keys', flush=True)

    def gn_lookup(name):
        cands = gn.get(norm(name))
        if not cands:
            return None
        lats = [c[0] for c in cands]; lons = [c[1] for c in cands]
        mlat, mlon = float(np.median(lats)), float(np.median(lons))
        spread = max((float(np.hypot((a-mlat)*111.0,
                                     (b-mlon)*111.0*np.cos(np.radians(mlat))))
                      for a, b in zip(lats, lons)), default=0.0)
        return (mlat, mlon, cands[0][2]) if spread <= 25.0 else None

    # A match found only after reducing the string (stripping a genitive or a
    # 'kloster'/'slott' suffix) is weaker evidence than one on the string itself:
    # 'Holmis' reduces to 'Holmi', which is a real village in Mersin, Turkey.
    # Foreign places reach the map through the curated table earlier in the chain,
    # so the last-resort steps are bounded to the Nordic/Baltic region when they
    # are working from a reduced form.
    NORDIC_BOX = (54.0, 71.0, 4.0, 33.0)      # latmin, latmax, lonmin, lonmax

    def plausible(lat, lon, reduced):
        if not reduced:
            return True
        a, b, c_, d = NORDIC_BOX
        return a <= lat <= b and c_ <= lon <= d

    def resolve(raw):
        vs = variants(raw)
        for v in vs:                                    # 1 overrides
            o = ov.get(norm(v))
            if o:
                hit = wk.get(norm(o['query_name'])) or g.get(norm(o['query_name']))
                if hit:
                    return hit[0], hit[1], hit[2], 'override', 'curated', 'point'
        for v in vs:                                    # 2-4 existing gazetteers
            hit = g.get(norm(v))
            if hit:
                conf = 'high' if v == vs[0] else 'medium'
                return hit[0], hit[1], hit[2], hit[3], conf, 'point'
        for v in vs:                                    # 5 SDHK Wikidata pass
            hit = wk.get(norm(v))
            if hit and plausible(hit[0], hit[1], v != vs[0]):
                return (hit[0], hit[1], hit[2], 'wikidata',
                        ('high' if v == vs[0] else 'medium'), 'point')
        if tora is not None:                            # 6 TORA, with härad backoff
            t = tora.resolve(raw)
            if t:
                lat, lon, label, prec, src = t
                return (lat, lon, label, src,
                        'medium' if prec == 'point' else 'low', prec)
        for v in vs:                                    # 7 GeoNames, settlements only
            h = gn_lookup(v)
            if h and plausible(h[0], h[1], v != vs[0]):
                return (h[0], h[1], h[2], 'geonames',
                        'low', 'point')
        return None, None, None, 'unresolved', 'none', None

    inp = os.path.join(ROOT, 'data', 'sdhk_charters.jsonl')
    outp = os.path.join(ROOT, 'data', 'sdhk_charters_geocoded.jsonl')
    src = collections.Counter(); unres = collections.Counter()
    n = geo = tagged = 0
    with open(inp, encoding='utf-8') as f, open(outp, 'w', encoding='utf-8') as o:
        for line in f:
            r = json.loads(line); n += 1
            raw = r.get('issue_place_raw')
            if not raw:
                r.update(place_name=None, lat=None, lon=None,
                         geo_source='no_place', confidence='none', precision=None)
                src['no_place'] += 1
                o.write(json.dumps(r, ensure_ascii=False) + '\n'); continue
            tagged += 1
            lat, lon, label, s, conf, prec = resolve(raw)
            r.update(place_name=label, lat=lat, lon=lon, geo_source=s,
                     confidence=conf, precision=prec)
            src[s] += 1
            if lat is not None:
                geo += 1
            else:
                unres[raw] += 1
            o.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f'charters        : {n:,}')
    print(f'with a place    : {tagged:,}')
    print(f'geocoded        : {geo:,}  ({100*geo/tagged:.1f}% of tagged)')
    print('\nby source:')
    for k, v in src.most_common():
        print(f'  {k:<16} {v:>7,}')
    up = os.path.join(ROOT, 'data', 'sdhk_unresolved_places.csv')
    with open(up, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['issue_place_raw', 'n_charters'])
        for k, v in unres.most_common():
            w.writerow([k, v])
    print(f'\nunresolved      : {len(unres):,} strings / {sum(unres.values()):,} charters')
    print(f'wrote {outp}')
    print(f'wrote {up}')

if __name__ == '__main__':
    main()
