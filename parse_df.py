#!/usr/bin/env python3
"""Parse the Diplomatarium Fennicum dataset into the common charter shape.

Source: https://huggingface.co/datasets/Kansallisarkisto/Diplomatarium-Fennicum
(CC0-1.0, National Archives of Finland) -> external/df_fennicum.json.
Coordinates come from the DF place register df_platser.csv, which is the exact
companion to this dataset: 99.5% of issuing places join by name.
"""
import csv, json, os, re, sys, collections

ROOT = '/home/pontus/dd_geo_map'
sys.path.insert(0, ROOT)
from geocode import norm

SRC = os.path.join(ROOT, 'external', 'df_fennicum.json')
REG = os.path.join(ROOT, 'df_platser.csv')
DF_URL = 'https://df.narc.fi/document/{id}'      # verified against indexed pages

# issuingplacecountry is given in Finnish
COUNTRY = {'Suomi': 'Finland', 'Ruotsi': 'Sweden', 'Italia': 'Italy',
           'Viro': 'Estonia', 'Ranska': 'France', 'Saksa': 'Germany',
           'Tanska': 'Denmark', 'Puola': 'Poland', 'Latvia': 'Latvia',
           'Norja': 'Norway', 'Venaja': 'Russia', 'Venäjä': 'Russia',
           'Belgia': 'Belgium', 'Alankomaat': 'Netherlands', 'Sveitsi': 'Switzerland',
           'Englanti': 'England', 'Espanja': 'Spain', 'Itavalta': 'Austria',
           'Liettua': 'Lithuania', 'Tsekki': 'Czech Republic', 'Unkari': 'Hungary'}

def load_register():
    """name -> (lat, lon, country). Keyed on the full name and on the head
    before the comma ('Ajosenpää, Masku' is a farm qualified by its parish)."""
    exact, head = {}, {}
    for row in csv.reader(open(REG, encoding='utf-8-sig'), delimiter=';'):
        if len(row) < 5 or not row[3] or not row[4]:
            continue
        try:
            lat, lon = float(row[3]), float(row[4])
        except ValueError:
            continue
        name = row[0].strip()
        cty = row[5].strip() if len(row) > 5 else ''
        exact.setdefault(norm(name), (lat, lon, name, cty))
        head.setdefault(norm(name.split(',')[0]), (lat, lon, name, cty))
    return exact, head

def main():
    data = json.load(open(SRC, encoding='utf-8'))
    exact, head = load_register()
    out = os.path.join(ROOT, 'data', 'df_charters_geocoded.jsonl')

    n = kept = noyear = noplace = geo = 0
    src = collections.Counter(); unres = collections.Counter(); mismatch = []
    with open(out, 'w', encoding='utf-8') as f:
        for r in data:
            n += 1
            ys = (r.get('dating_start_year') or '').strip()
            if not ys.isdigit():
                noyear += 1
                continue
            y = int(ys)
            if not (700 <= y <= 1700):
                noyear += 1
                continue
            place = (r.get('issuingplace') or '').strip()
            cty_fi = (r.get('issuingplacecountry') or '').strip()
            lat = lon = None; label = None; s = 'no_place'
            if place:
                hit = exact.get(norm(place)) or head.get(norm(place)) \
                      or head.get(norm(place.split(',')[0]))
                if hit:
                    lat, lon, label, rcty = hit
                    s = 'df_register'
                    geo += 1
                    if cty_fi and rcty and cty_fi != rcty:
                        mismatch.append((place, cty_fi, rcty))
                else:
                    s = 'unresolved'
                    unres[place] += 1
            else:
                noplace += 1
            src[s] += 1

            tr = (r.get('transcript') or '').strip()
            idx = (r.get('indexterm') or '').strip()
            # DF has no regest; the transcript is the charter itself, index terms
            # are the nearest thing to a summary
            abstract = (tr[:400] if tr else '') or idx or None

            did = str(r.get('df') or '').strip()
            kept += 1
            f.write(json.dumps({
                'corpus': 'DF',
                'id': did,
                'citation': f'DF {did}',
                'year': y,
                'date': None,
                'issue_place_raw': place or None,
                'abstract': abstract,
                'place_name': label,
                'lat': lat, 'lon': lon,
                'country': COUNTRY.get(cty_fi, cty_fi) or None,
                'lang': (r.get('language') or '').strip() or None,
                'geo_source': s,
                'confidence': 'high' if s == 'df_register' else 'none',
                'source_url': DF_URL.format(id=did) if did else None,
            }, ensure_ascii=False) + '\n')

    tagged = kept - noplace
    print(f'records read   : {n}')
    print(f'  unusable year: {noyear}')
    print(f'kept           : {kept}')
    print(f'  with a place : {tagged}')
    print(f'geocoded       : {geo}  ({100*geo/max(tagged,1):.1f}% of tagged)')
    print('\nby source:')
    for k, v in src.most_common():
        print(f'  {k:<14} {v:>6}')
    print(f'\ncountry disagreements (dataset vs register): {len(mismatch)}')
    for m in mismatch[:5]:
        print('   ', m)
    up = os.path.join(ROOT, 'data', 'df_unresolved_places.csv')
    with open(up, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['issue_place_raw', 'n_charters'])
        for k, v in unres.most_common():
            w.writerow([k, v])
    print(f'unresolved     : {len(unres)} strings / {sum(unres.values())} charters')
    print(f'wrote {out}')

if __name__ == '__main__':
    main()
