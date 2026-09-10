#!/usr/bin/env python3
"""Build the resolver-facing name index from data/gazetteer_digdag.jsonl.

Two levels, because a raw name is NOT a unique place:
  data/gazetteer_digdag_units.jsonl  one row per real unit (layer+enhedid),
                                     centroid = median over its time-versions
  data/gazetteer_digdag_names.csv    one row per unique name, carrying an
                                     explicit ambiguity verdict

'Lund Ejerlav' names 12 different Danish places; collapsing them to one median
coordinate lands in open country between them. Names whose units are spread wider
than AMBIG_KM are marked ambiguous with lat/lon left blank, so the geocoder must
disambiguate rather than silently accept a fabricated point.
"""
import csv, json, os, collections
import numpy as np

ROOT = '/home/pontus/dd_geo_map'
AMBIG_KM = 25.0          # units farther apart than this are genuinely different places

def km(lat1, lon1, lat2, lon2):
    return float(np.hypot((lat2 - lat1) * 111.0,
                          (lon2 - lon1) * 111.0 * np.cos(np.radians((lat1 + lat2) / 2))))

def main():
    rows = [json.loads(l) for l in
            open(os.path.join(ROOT, 'data', 'gazetteer_digdag.jsonl'), encoding='utf-8')]

    # ---- level 1: units (layer, enhedid) ---------------------------------
    units = collections.defaultdict(list)
    for r in rows:
        units[(r['layer'], r['enhedid'])].append(r)

    unit_rows = []
    for (layer, eid), vs in units.items():
        lats = [v['lat'] for v in vs if v['lat'] is not None]
        lons = [v['lon'] for v in vs if v['lon'] is not None]
        if not lats:
            continue
        names = collections.Counter(v['navn'] for v in vs)
        fra = [v['fra'] for v in vs if v['fra']]
        til = [v['til'] for v in vs if v['til']]
        unit_rows.append({
            'layer': layer, 'enhedid': eid,
            'navn': names.most_common(1)[0][0],
            'name_variants': sorted(names),
            'name_base': vs[0]['name_base'], 'name_norm': vs[0]['name_norm'],
            'art': vs[0]['art'],
            'lat': round(float(np.median(lats)), 6),
            'lon': round(float(np.median(lons)), 6),
            'n_versions': len(vs),
            'fra': min(fra) if fra else '', 'til': max(til) if til else '',
        })

    up = os.path.join(ROOT, 'data', 'gazetteer_digdag_units.jsonl')
    with open(up, 'w', encoding='utf-8') as f:
        for u in sorted(unit_rows, key=lambda u: (u['layer'], u['navn'])):
            f.write(json.dumps(u, ensure_ascii=False) + '\n')

    # ---- level 2: name index over units ----------------------------------
    def build(key):
        idx = collections.defaultdict(list)
        for u in unit_rows:
            if u[key]:
                idx[u[key]].append(u)
        return idx

    for key, fname in (('navn', 'gazetteer_digdag_names.csv'),
                       ('name_norm', 'gazetteer_digdag_norm_index.csv')):
        idx = build(key)
        outp = os.path.join(ROOT, 'data', fname)
        n_ambig = 0
        with open(outp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([key, 'name_base', 'art', 'layers', 'n_units', 'n_versions',
                        'earliest_fra', 'latest_til', 'ambiguous', 'spread_km',
                        'lat', 'lon', 'candidates'])
            for name in sorted(idx):
                us = idx[name]
                lats = [u['lat'] for u in us]; lons = [u['lon'] for u in us]
                mlat, mlon = float(np.median(lats)), float(np.median(lons))
                spread = max((km(mlat, mlon, a, b) for a, b in zip(lats, lons)),
                             default=0.0)
                ambiguous = len(us) > 1 and spread > AMBIG_KM
                if ambiguous:
                    n_ambig += 1
                fra = [u['fra'] for u in us if u['fra']]
                til = [u['til'] for u in us if u['til']]
                cands = '' if not ambiguous else ' | '.join(
                    f"{u['enhedid']}@{u['lat']:.4f},{u['lon']:.4f}"
                    for u in sorted(us, key=lambda u: -u['n_versions'])[:12])
                w.writerow([
                    name, us[0]['name_base'],
                    '; '.join(sorted({u['art'] for u in us if u['art']})),
                    '; '.join(sorted({u['layer'] for u in us})),
                    len(us), sum(u['n_versions'] for u in us),
                    min(fra) if fra else '', max(til) if til else '',
                    'yes' if ambiguous else 'no', round(spread, 2),
                    '' if ambiguous else round(mlat, 6),
                    '' if ambiguous else round(mlon, 6),
                    cands,
                ])
        print(f'{fname:<38} {len(idx):>6} keys, {n_ambig:>5} ambiguous '
              f'({100*n_ambig/max(len(idx),1):.1f}%)')

    print(f'\nversion rows : {len(rows)}')
    print(f'units        : {len(unit_rows)}')
    print(f'wrote {up}')

if __name__ == '__main__':
    main()
