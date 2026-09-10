#!/usr/bin/env python3
"""TORA resolver built from the Äldre geometriska kartorna release (Zenodo 15121019).

Design follows one rule: **a coarse location that is certainly in the right region
beats a precise one that may be in the wrong province.** So when a name is ambiguous
we do not pick the likeliest point and we do not drop the row — we fall back to the
smallest administrative unit that contains every candidate:

    exact, agreeing candidates       -> point            (precision 'point')
    candidates spread, one parish    -> parish centroid  (precision 'parish')
    name known but never geocoded,
      parish recorded                -> parish centroid  (precision 'parish')
    candidates spread, one härad     -> härad centroid   (precision 'harad')
    'X häradsting' / 'X ting'        -> härad centroid   (precision 'harad')
    otherwise                        -> unresolved

A parish beats a härad where both are known: it is the tighter unit. A parish
location is still far better than none, since an unresolved charter is simply
invisible on the map.

Every result carries `precision` so the map can show how sure the placement is.
"""
import csv, os, re, sys, collections
import numpy as np

ROOT = '/home/pontus/dd_geo_map'
AGGK = os.path.join(ROOT, 'external', 'aggk')
FULL = os.path.join(ROOT, 'external', 'tora')   # a full SPARQL export, if one exists
sys.path.insert(0, ROOT)
from geocode import norm
from geocode_sdhk import variants, clean

AGREE_KM = 25.0        # candidates closer than this are treated as one place

TING = re.compile(r'\s*(häradsting|häradzting|tingsplats|tingstad|tingställe|'
                  r'ting|härad|hered|hundare)\.?$', re.I)
PARISH_SUFFIX = re.compile(r'\s*(församling|socken|sn|pastorat)\.?$', re.I)

def parish_key(s):
    """'Murums församling' -> 'murum'. The register writes the parish in the
    genitive before 'församling', the settlement table writes it bare."""
    c = PARISH_SUFFIX.sub('', (s or '').strip()).strip().rstrip('.,').strip()
    if re.search(r'(?<=\w\w)s$', c):
        c = c[:-1]
    return norm(c)

def _num(s):
    """The two CSVs disagree on decimal separator: '59.51' and '57,768' both occur."""
    s = (s or '').strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

def _rows(fn):
    p = os.path.join(AGGK, fn)
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding='utf-8'), delimiter=';'))

def harad_key(s):
    """Canonical härad key, applied to BOTH sides of the match.

    The register writes 'Bankekinds h:d' and 'Oppunda h:d'; a charter writes
    'Bankekinds häradsting' or 'Oppunda ting'. Stripping the genitive on only one
    side silently loses the match, which cost ~440 ting strings until caught.
    """
    c = (s or '').strip()
    c = re.sub(r'\s*h:d\.?$', '', c, flags=re.I)
    prev = None
    while prev != c:
        prev = c
        c = TING.sub('', c).strip().rstrip('.,').strip()
    if re.search(r'(?<=\w\w)e?s$', c):
        c = re.sub(r'e?s$', '', c)
    return norm(c)

# Column-name guesses for a full TORA export from the SPARQL endpoint. The exact
# projection is not known here (the endpoint is blocked by the Riksarkivet filter -
# see queries/tora_sparql.md), so match on substrings rather than exact headers.
# Header names produced by the bulk query in queries/tora_sparql.md, plus the
# variants an alternative projection might use. Matched by substring, first hit
# wins, so order matters: 'district' is TORA's word for härad and must be tried
# before the looser 'harad'.
FULL_COLS = {
    'lat':     ('lat', 'latitude', 'wgs84_lat', 'y_wgs84'),
    'lon':     ('long', 'lon', 'longitude', 'wgs84_long', 'x_wgs84'),
    'name':    ('preflabel', 'prefname', 'name', 'namn', 'label'),
    'alt':     ('altnames', 'altname', 'altlabel', 'altnamn', 'alternate'),
    'parish':  ('parish', 'socken', 'forsamling', 'församling'),
    'hundred': ('district', 'hundred', 'harad', 'härad'),
    'province': ('province', 'landskap'),
    'id':      ('unit', 'toraid', 'tora', 'uri', 'id'),
}

def _pick(fieldnames, keys):
    """First header whose lowercased name contains one of `keys`."""
    low = {f: (f or '').strip().lower() for f in fieldnames}
    for key in keys:
        for f, l in low.items():
            if key in l:
                return f
    return None

class Tora:
    def __init__(self):
        self.names = collections.defaultdict(list)   # norm -> [(lat,lon,label,harad,parish)]
        self.harad = collections.defaultdict(list)   # norm harad -> [(lat,lon)]
        self.parish = collections.defaultdict(list)  # norm parish -> [(lat,lon)]
        self.name_area = collections.defaultdict(set)  # norm name -> {('p',key)|('h',key)}
        self.harad_label = {}                        # key -> display form
        self.parish_label = {}
        self.n_units = 0
        self.n_full = 0

        for r in _rows('Basic_settlement_unit_v1.0.csv'):
            la, lo = _num(r['tora_wgs84_lat']), _num(r['tora_wgs84_long'])
            if la is None or lo is None:
                continue
            self.n_units += 1
            h_raw = (r.get('hundred') or '').strip()
            h = re.sub(r'\s*h:d$', '', h_raw)
            pk = parish_key(r.get('parish'))
            if pk:
                self.parish_label.setdefault(
                    pk, PARISH_SUFFIX.sub('', (r.get('parish') or '').strip()).strip())
            label = r['tora_prefLabel']
            for nm in [label] + [x.strip() for x in (r.get('tora_altLabel') or '').split(',') if x.strip()]:
                k = norm(nm)
                if k:
                    self.names[k].append((la, lo, label, h, pk))
            if h_raw:
                self.harad[harad_key(h_raw)].append((la, lo))
                self.harad_label.setdefault(harad_key(h_raw), h)
            if pk:
                self.parish[pk].append((la, lo))

        for r in _rows('Place_and_personal_names_v1.1.csv'):
            if (r.get('kategori') or '') == 'personnamn':
                continue
            la, lo = _num(r['tora_wgs84_lat']), _num(r['tora_wgs84_long'])
            if la is None or lo is None:
                continue
            h_raw = (r.get('härad') or '').strip()
            h = re.sub(r'\s*h:d$', '', h_raw)
            pk = parish_key(r.get('socken'))
            k = norm(r.get('namn') or '')
            if k:
                self.names[k].append((la, lo, r['namn'], h, pk))
            if h_raw:
                self.harad[harad_key(h_raw)].append((la, lo))
                self.harad_label.setdefault(harad_key(h_raw), h)
            if pk:
                self.parish[pk].append((la, lo))

        self._load_full()

        # A name with no coordinate is still placeable if the register records
        # which parish (or failing that, which härad) it belonged to. 7,980 rows
        # are in exactly that position.
        for r in _rows('Place_and_personal_names_v1.1.csv'):
            if (r.get('kategori') or '') == 'personnamn':
                continue
            if _num(r['tora_wgs84_lat']) is not None:
                continue
            k = norm(r.get('namn') or '')
            if not k:
                continue
            pk = parish_key(r.get('socken'))
            hk = harad_key(r.get('härad'))
            if pk:
                self.name_area[k].add(('p', pk))
            elif hk:
                self.name_area[k].add(('h', hk))

    def _load_full(self):
        """Merge a full TORA export from external/tora/.

        The export arrives as several small CSVs rather than one wide table (see
        queries/tora_sparql.md - simple queries are far likelier to survive the
        endpoint than one with GROUP_CONCAT and BIND in it). So: read every CSV,
        work out what each one is from its headers, then join on the unit URI.

          name column present        -> the unit table
          two columns, URI -> label  -> a lookup, resolving district/parish URIs
          unit + altname             -> alternative spellings
        """
        if not os.path.isdir(FULL):
            return
        files = sorted(f for f in os.listdir(FULL) if f.lower().endswith('.csv'))
        if not files:
            return

        units = []            # [{id, name, lat, lon, district, parish}]
        lookup = {}           # URI or label -> label
        alts = collections.defaultdict(list)   # unit id -> [names]

        for fn in files:
            path = os.path.join(FULL, fn)
            with open(path, encoding='utf-8-sig') as fh:
                sample = fh.read(8192); fh.seek(0)
                try:
                    delim = csv.Sniffer().sniff(sample, delimiters=';,\t').delimiter
                except csv.Error:
                    delim = ','
                rd = csv.DictReader(fh, delimiter=delim)
                fns = [f for f in (rd.fieldnames or []) if f]
                if not fns:
                    continue
                c = {k: _pick(fns, v) for k, v in FULL_COLS.items()}
                if c['name'] and c['name'] == c['alt']:
                    c['name'] = _pick([f for f in fns if f != c['alt']], FULL_COLS['name'])
                rows = list(rd)

                def uri_frac(col):
                    vals = [(r.get(col) or '').strip() for r in rows[:200]]
                    vals = [v for v in vals if v]
                    return (sum(v.startswith('http') for v in vals) / len(vals)) if vals else 0.0

                has_coords = bool(c['lat'] or c['lon'])

                # Classify by the shape of the data, not by which semantic key the
                # header happened to match: a districts lookup has a column literally
                # called "district", which would otherwise read as a units table.
                if not has_coords and c['alt'] and c['id'] and len(fns) == 2:
                    for r in rows:
                        u = (r.get(c['id']) or '').strip()
                        v = (r.get(c['alt']) or '').strip()
                        if u and v:
                            alts[u].append(v)
                    print(f'  full TORA: {fn} -> {len(rows):,} alternative names')
                    continue

                if not has_coords and len(fns) == 2:
                    # the URI-valued column is the key, the other is the label
                    fracs = {f: uri_frac(f) for f in fns}
                    keycol = max(fns, key=lambda f: fracs[f])
                    valcol = next(f for f in fns if f != keycol)
                    if fracs[keycol] >= 0.5:
                        n = 0
                        for r in rows:
                            k = (r.get(keycol) or '').strip()
                            v = (r.get(valcol) or '').strip()
                            if k and v:
                                lookup[k] = v; n += 1
                        print(f'  full TORA: {fn} -> {n:,} label lookups '
                              f'({keycol} -> {valcol})')
                        continue

                if not c['name']:
                    print(f'  ! {fn}: no name column in {fns} - skipped')
                    continue

                for r in rows:
                    units.append({
                        'id':   (r.get(c['id']) or '').strip() if c['id'] else '',
                        'name': (r.get(c['name']) or '').strip(),
                        'lat':  _num(r.get(c['lat'])) if c['lat'] else None,
                        'lon':  _num(r.get(c['lon'])) if c['lon'] else None,
                        'district': (r.get(c['hundred']) or '').strip() if c['hundred'] else '',
                        'parish':   (r.get(c['parish']) or '').strip() if c['parish'] else '',
                        'alt':  (r.get(c['alt']) or '').strip() if c['alt'] else '',
                    })
                print(f'  full TORA: {fn} -> {len(rows):,} units '
                      f'({", ".join(f"{k}={v}" for k, v in c.items() if v)})')

        def label(v):
            """A district/parish cell may be a URI, a label, or a URI we have a
            label for. Fall back to the last path segment of a bare URI."""
            v = (v or '').strip()
            if not v:
                return ''
            if v in lookup:
                return lookup[v]
            if v.startswith('http'):
                return v.rstrip('/').rsplit('/', 1)[-1].replace('_', ' ')
            return v

        for u in units:
            if not u['name']:
                continue
            d_raw, p_raw = label(u['district']), label(u['parish'])
            hk, pk = harad_key(d_raw), parish_key(p_raw)
            names = [u['name']]
            if u['alt']:
                names += [x.strip() for x in re.split(r'[|,;]', u['alt']) if x.strip()]
            if u['id'] and u['id'] in alts:
                names += alts[u['id']]
            la, lo = u['lat'], u['lon']
            if la is not None and lo is not None:
                for nm in names:
                    k = norm(nm)
                    if k:
                        self.names[k].append((la, lo, u['name'], d_raw, pk))
                if hk:
                    self.harad[hk].append((la, lo))
                    self.harad_label.setdefault(hk, d_raw)
                if pk:
                    self.parish[pk].append((la, lo))
                    self.parish_label.setdefault(pk, p_raw)
            else:
                for nm in names:
                    k = norm(nm)
                    if not k:
                        continue
                    if pk:
                        self.name_area[k].add(('p', pk))
                    elif hk:
                        self.name_area[k].add(('h', hk))
            self.n_full += 1

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _centre(pts):
        lats = [p[0] for p in pts]; lons = [p[1] for p in pts]
        mlat, mlon = float(np.median(lats)), float(np.median(lons))
        spread = max((float(np.hypot((a - mlat) * 111.0,
                                     (b - mlon) * 111.0 * np.cos(np.radians(mlat))))
                      for a, b in zip(lats, lons)), default=0.0)
        return mlat, mlon, spread

    def hlabel(self, k):
        """Display form ending in exactly one 'härad'. The geometric-maps CSV writes
        'Oppunda h:d' (suffix stripped on load) but a SPARQL export may write
        'Oppunda härad' in full, which would otherwise double up."""
        lab = self.harad_label.get(k, k.title()).strip()
        return lab if re.search(r'härad$', lab, re.I) else f'{lab} härad'

    def plabel(self, k):
        lab = self.parish_label.get(k, k.title()).strip()
        return lab if re.search(r'(parish|socken|församling)$', lab, re.I) else f'{lab} parish'

    def harad_centroid(self, h):
        pts = self.harad.get(h if isinstance(h, str) else '')
        if not pts:
            return None
        mlat, mlon, _ = self._centre(pts)
        return mlat, mlon, len(pts)

    def parish_centroid(self, p):
        pts = self.parish.get(p if isinstance(p, str) else '')
        if not pts:
            return None
        mlat, mlon, _ = self._centre(pts)
        return mlat, mlon, len(pts)

    # ---------------------------------------------------------------- resolve
    def resolve(self, raw):
        """-> (lat, lon, label, precision, source) or None."""
        for v in variants(raw):
            cands = self.names.get(norm(v))
            if not cands:
                continue
            mlat, mlon, spread = self._centre(cands)
            if spread <= AGREE_KM:
                return (mlat, mlon, cands[0][2], 'point', 'tora')
            # ambiguous: back off to the tightest unit that contains them all
            ps = {c[4] for c in cands if c[4]}
            if len(ps) == 1:
                pc = self.parish_centroid(next(iter(ps)))
                if pc:
                    return (pc[0], pc[1], self.plabel(next(iter(ps))),
                            'parish', 'tora_parish')
            hs = {harad_key(c[3]) for c in cands if c[3]}
            if len(hs) == 1:
                hc = self.harad_centroid(list(hs)[0])
                if hc:
                    return (hc[0], hc[1], self.hlabel(list(hs)[0]),
                            'harad', 'tora_harad')
            # candidates disagree and span several härad -> refuse
            return None
        # name is in the register but was never geocoded: use its recorded area
        for v in variants(raw):
            areas = self.name_area.get(norm(v))
            if not areas:
                continue
            pk = {a[1] for a in areas if a[0] == 'p'}
            if len(pk) == 1:
                pc = self.parish_centroid(next(iter(pk)))
                if pc:
                    return (pc[0], pc[1], self.plabel(next(iter(pk))),
                            'parish', 'tora_parish')
            hk = {a[1] for a in areas if a[0] == 'h'}
            if len(hk) == 1:
                hc = self.harad_centroid(next(iter(hk)))
                if hc:
                    return (hc[0], hc[1], self.hlabel(next(iter(hk))),
                            'harad', 'tora_harad')
        # 'X socken' / 'X kyrka' with no settlement match -> the parish itself
        pk = parish_key(clean(raw))
        if pk and pk in self.parish:
            pc = self.parish_centroid(pk)
            if pc:
                return (pc[0], pc[1], self.plabel(pk), 'parish', 'tora_parish')
        h = harad_key(raw)
        if h:
            hc = self.harad_centroid(h)
            if hc:
                return (hc[0], hc[1], self.hlabel(h), 'harad', 'tora_harad')
        return None

def main():
    t = Tora()
    print(f'TORA settlement units with coords : {t.n_units:,}')
    if t.n_full:
        print(f'rows from a full TORA export      : {t.n_full:,}')
    else:
        print('full TORA export                  : none found in external/tora/'
              ' (see queries/tora_sparql.md)')
    print(f'distinct normalised names         : {len(t.names):,}')
    print(f'härad with centroids              : {len(t.harad):,}')
    print(f'parishes with centroids           : {len(t.parish):,}')
    print(f'names known but never geocoded    : {len(t.name_area):,}')
    up = os.path.join(ROOT, 'data', 'sdhk_unresolved_places.csv')
    if not os.path.exists(up):
        return
    rows = [(r['issue_place_raw'], int(r['n_charters']))
            for r in csv.DictReader(open(up, encoding='utf-8'))]
    c = collections.Counter(); ch = collections.Counter()
    for s, n in rows:
        r = t.resolve(s)
        key = r[3] if r else 'none'
        c[key] += 1; ch[key] += n
    tot = sum(ch.values())
    print(f'\nagainst SDHK unresolved ({tot:,} charters):')
    for k in ('point', 'parish', 'harad', 'none'):
        print(f'  {k:<7} {c[k]:>5,} strings / {ch[k]:>6,} charters ({100*ch[k]/tot:5.1f}%)')

if __name__ == '__main__':
    main()
