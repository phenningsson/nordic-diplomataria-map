#!/usr/bin/env python3
"""Collate every DigDag shapefile layer into a single place-name gazetteer.

Reads the .dbf attribute tables (place names + validity dates) and computes an
area-weighted centroid from the .shp geometry, reprojected EPSG:25832 -> WGS84.

Outputs
  data/gazetteer_digdag.jsonl        one row per name-version (temporal records kept)
  data/gazetteer_digdag_names.csv    deduplicated name index, one row per unique name
"""
import csv, glob, json, os, struct, sys, unicodedata
import numpy as np

ROOT = '/home/pontus/dd_geo_map'
DIGDAG = os.path.join(ROOT, 'digdag')

# ---------------------------------------------------------------- DBF reader
def read_dbf(path, encoding='cp1252'):
    with open(path, 'rb') as f:
        data = f.read()
    nrec, hlen, rlen = struct.unpack('<IHH', data[4:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        fd = data[off:off + 32]
        fields.append((fd[0:11].split(b'\x00')[0].decode('ascii', 'replace'),
                       chr(fd[11]), fd[16]))
        off += 32
    out = []
    for i in range(nrec):
        rec = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        if len(rec) < rlen:
            break
        if rec[0:1] == b'*':          # deleted
            continue
        vals, p = {}, 1
        for name, ftype, flen in fields:
            vals[name.lower()] = rec[p:p + flen].decode(encoding, 'replace').strip()
            p += flen
        out.append(vals)
    return out

# ------------------------------------------------------------- SHP centroids
def ring_centroids(path):
    """Yield (area_weighted_centroid_x, y, bbox_cx, bbox_cy) per record, in file order."""
    f = open(path, 'rb')
    f.seek(24)
    file_words = struct.unpack('>I', f.read(4))[0]
    file_len = file_words * 2
    f.seek(100)
    pos = 100
    while pos < file_len:
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        _, clen_words = struct.unpack('>II', hdr)
        content = f.read(clen_words * 2)
        pos += 8 + clen_words * 2
        if len(content) < 4:
            yield (None, None, None, None); continue
        shptype = struct.unpack('<i', content[0:4])[0]
        if shptype == 0:                                  # null shape
            yield (None, None, None, None); continue
        if shptype in (1, 11, 21):                        # point
            x, y = struct.unpack('<dd', content[4:20])
            yield (x, y, x, y); continue
        if shptype not in (3, 5, 13, 15, 23, 25):         # polyline / polygon
            yield (None, None, None, None); continue
        xmin, ymin, xmax, ymax = struct.unpack('<dddd', content[4:36])
        nparts, npoints = struct.unpack('<ii', content[36:44])
        po = 44 + nparts * 4
        parts = np.frombuffer(content, dtype='<i4', count=nparts, offset=44)
        pts = np.frombuffer(content, dtype='<f8', count=npoints * 2,
                            offset=po).reshape(-1, 2)
        bcx, bcy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
        # signed shoelace over every ring; holes carry negative area and cancel
        A2 = 0.0; Cx = 0.0; Cy = 0.0
        bounds = list(parts) + [npoints]
        for k in range(nparts):
            r = pts[bounds[k]:bounds[k + 1]]
            if len(r) < 3:
                continue
            if r[0, 0] != r[-1, 0] or r[0, 1] != r[-1, 1]:
                r = np.vstack([r, r[0]])
            x0, y0 = r[:-1, 0], r[:-1, 1]
            x1, y1 = r[1:, 0], r[1:, 1]
            cross = x0 * y1 - x1 * y0
            A2 += cross.sum()
            Cx += ((x0 + x1) * cross).sum()
            Cy += ((y0 + y1) * cross).sum()
        if abs(A2) > 1e-9:
            yield (Cx / (3.0 * A2), Cy / (3.0 * A2), bcx, bcy)
        else:                                             # degenerate -> mean of points
            yield (float(pts[:, 0].mean()), float(pts[:, 1].mean()), bcx, bcy)
    f.close()

# ------------------------------------------------------------ name normalising
UNIT_WORDS = {
    'sogn', 'sogne', 'ejerlav', 'herred', 'herreder', 'birk', 'købstad', 'koebstad',
    'len', 'amt', 'kommune', 'sognekommune', 'købstadskommune', 'pastorat', 'provsti',
    'stift', 'retskreds', 'landsret', 'landsting', 'landsoverret', 'forligskreds',
    'politikreds', 'amtsret', 'amtsgericht', 'amtsdistrikt', 'amtsbezirk', 'fysikat',
    'lægekreds', 'lægedistrikt', 'amtslægekreds', 'landvæsensdistrikt', 'skyldkreds',
    'vurderingskreds', 'opstillingskreds', 'storkreds', 'landsdel', 'landsdelskreds',
    'landstingskreds', 'statsamt', 'statsforvaltning', 'stiftamt', 'amtsrådskreds',
    'region', 'handelsdistrikt', 'handelsområde', 'afstemningsområde', 'valgdistrikt',
    'valgkreds', 'udskrivningskreds', 'udskrivningsdistrikt', 'lægd', 'kog',
    'godsdistrikt', 'kancelligods', 'gods', 'fogderi', 'herredsfogderi', 'flække',
    'geobyggeklods', 'kredskasse', 'amtstuedistrikt', 'landkreds', 'kreis',
    'totalforsvarsregion', 'beskæftigelsesregion', 'hjemmeværnsdistrikt', 'by- og herredsret',
    'herredsret', 'byret', 'ret',
}
FOLD = str.maketrans({'å': 'aa', 'Å': 'aa', 'ä': 'ae', 'Ä': 'ae', 'ø': 'oe', 'Ø': 'oe',
                      'ö': 'oe', 'Ö': 'oe', 'æ': 'ae', 'Æ': 'ae', 'ü': 'ue', 'Ü': 'ue',
                      'é': 'e', 'è': 'e', 'ô': 'o', 'ó': 'o', 'á': 'a'})

def strip_unit_suffix(navn):
    """Drop trailing administrative-type words: 'Aaker Sogn' -> 'Aaker'."""
    toks = navn.split()
    while toks and toks[-1].strip('.,').lower() in UNIT_WORDS:
        toks.pop()
    return ' '.join(toks) if toks else navn

def norm(s):
    """Canonical ASCII match key: casefold, fold Nordic chars, collapse punctuation."""
    s = s.translate(FOLD).lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in s)
    return ' '.join(s.split())

# --------------------------------------------------------------------- main
def main():
    from pyproj import Transformer
    tf = Transformer.from_crs('EPSG:25832', 'EPSG:4326', always_xy=True)

    dbfs = sorted(glob.glob(os.path.join(DIGDAG, '*', '*.dbf')))
    print(f'{len(dbfs)} layers found', flush=True)

    rows = []
    for i, dbf in enumerate(dbfs, 1):
        layer = os.path.splitext(os.path.basename(dbf))[0]
        folder = os.path.basename(os.path.dirname(dbf))
        shp = dbf[:-4] + '.shp'
        recs = read_dbf(dbf)
        size_mb = os.path.getsize(shp) / 1e6
        print(f'[{i:2}/{len(dbfs)}] {layer:<45} {len(recs):>6} recs  {size_mb:8.1f} MB',
              flush=True)
        cents = list(ring_centroids(shp)) if os.path.exists(shp) else []
        if len(cents) != len(recs):
            print(f'         ! geometry/attribute count mismatch: '
                  f'{len(cents)} shapes vs {len(recs)} records', flush=True)
        for j, r in enumerate(recs):
            navn = r.get('navn', '')
            if not navn:
                continue
            cx = cy = bcx = bcy = None
            if j < len(cents):
                cx, cy, bcx, bcy = cents[j]
            lon = lat = None
            if cx is not None and np.isfinite(cx) and np.isfinite(cy):
                lon, lat = tf.transform(cx, cy)
                lon, lat = round(lon, 6), round(lat, 6)
            base = strip_unit_suffix(navn)
            rows.append({
                'layer': layer, 'folder': folder,
                'navn': navn, 'name_base': base, 'name_norm': norm(base),
                'art': r.get('art', ''),
                'fra': r.get('fra', ''), 'til': r.get('til', ''),
                'enhedid': r.get('enhedid', ''), 'enhedtype': r.get('enhedtype', ''),
                'lat': lat, 'lon': lon,
                'utm_x': round(cx, 2) if cx is not None else None,
                'utm_y': round(cy, 2) if cy is not None else None,
            })

    # numeric fields arrive as float text ('1.23096000000e+005'); make them ints
    def num(s):
        s = (s or '').strip()
        if not s:
            return ''
        try:
            f = float(s)
            return str(int(f)) if f == int(f) else str(f)
        except ValueError:
            return s
    for r in rows:
        r['enhedid'] = num(r['enhedid'])
        r['enhedtype'] = num(r['enhedtype'])

    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    jl = os.path.join(ROOT, 'data', 'gazetteer_digdag.jsonl')
    with open(jl, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # deduplicated name index: one row per unique raw name
    idx = {}
    for r in rows:
        e = idx.setdefault(r['navn'], {
            'navn': r['navn'], 'name_base': r['name_base'], 'name_norm': r['name_norm'],
            'arts': set(), 'layers': set(), 'n_versions': 0,
            'fra': [], 'til': [], 'lats': [], 'lons': [],
        })
        e['arts'].add(r['art']); e['layers'].add(r['layer']); e['n_versions'] += 1
        if r['fra']: e['fra'].append(r['fra'])
        if r['til']: e['til'].append(r['til'])
        if r['lat'] is not None:
            e['lats'].append(r['lat']); e['lons'].append(r['lon'])

    csvp = os.path.join(ROOT, 'data', 'gazetteer_digdag_names.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['navn', 'name_base', 'name_norm', 'art', 'layers', 'n_versions',
                    'earliest_fra', 'latest_til', 'lat', 'lon', 'coord_spread_km'])
        for navn in sorted(idx):
            e = idx[navn]
            lat = lon = spread = ''
            if e['lats']:
                lat = round(float(np.median(e['lats'])), 6)
                lon = round(float(np.median(e['lons'])), 6)
                if len(e['lats']) > 1:
                    dlat = (max(e['lats']) - min(e['lats'])) * 111.0
                    dlon = ((max(e['lons']) - min(e['lons'])) * 111.0
                            * np.cos(np.radians(lat)))
                    spread = round(float(np.hypot(dlat, dlon)), 2)
                else:
                    spread = 0.0
            w.writerow([navn, e['name_base'], e['name_norm'],
                        '; '.join(sorted(x for x in e['arts'] if x)),
                        '; '.join(sorted(e['layers'])), e['n_versions'],
                        min(e['fra']) if e['fra'] else '',
                        max(e['til']) if e['til'] else '', lat, lon, spread])

    geo = sum(1 for r in rows if r['lat'] is not None)
    print(f'\nrecords        : {len(rows)}')
    print(f'with centroid  : {geo} ({100*geo/max(len(rows),1):.1f}%)')
    print(f'unique names   : {len(idx)}')
    print(f'unique name_norm: {len(set(r["name_norm"] for r in rows))}')
    print(f'wrote {jl}')
    print(f'wrote {csvp}')

if __name__ == '__main__':
    main()
