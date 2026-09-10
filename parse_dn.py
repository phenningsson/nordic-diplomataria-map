#!/usr/bin/env python3
"""Convert external/dn_letters.csv (Diplomatarium Norvegicum) into the same
record shape as data/charters_geocoded.jsonl, so both corpora feed one map.

Source: Moryzont/SuperDiplomatarium — already geocoded, so no resolver runs here.
"""
import csv, json, os, re, sys, collections

ROOT = '/home/pontus/dd_geo_map'
csv.field_size_limit(10 ** 9)

NULL_PLACES = {'', '[no_loc]', 'no_loc', 'ukjent'}

# The dokpro deep-link parameter (?b=) is an opaque internal database id that
# cannot be derived from volume+number — a rank-based guess came out 105 off on
# the one citation we could check, which would link the WRONG charter. So we emit
# an accurate citation and a search URL. Set DN_ITEM_URL to a template using
# {vol}/{num} once a real per-charter URL is confirmed.
DN_SEARCH_URL = 'https://www.dokpro.uio.no/dipl_norv/diplom_felt.html'
DN_ITEM_URL = None          # e.g. 'https://example.org/dn/{vol}/{num}'

ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI',
         'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI',
         'XXII', 'XXIII', 'XXIV', 'XXV']

def cite(ref, prefix):
    m = re.fullmatch(rf'{prefix}(\d{{3}})(\d{{5}})', ref or '')
    if not m:
        return None, None, None
    vol, num = int(m.group(1)), int(m.group(2))
    roman = ROMAN[vol] if vol < len(ROMAN) else str(vol)
    return f'{prefix} {roman} nr. {num}', vol, num

def main():
    src = os.path.join(ROOT, 'external', 'dn_letters.csv')
    rows = list(csv.DictReader(open(src, encoding='utf-8')))
    out = os.path.join(ROOT, 'data', 'dn_charters_geocoded.jsonl')

    n = kept = nogeo = noyear = nullplace = 0
    with open(out, 'w', encoding='utf-8') as f:
        for r in rows:
            n += 1
            raw = (r.get('DN_sted') or r.get('RN_sted') or '').strip()
            norm_name = (r.get('Normalized_name') or '').strip()
            if norm_name.lower() in NULL_PLACES:
                nullplace += 1
                continue
            d = (r.get('date_start') or r.get('date_end') or '').strip()
            y = int(d[:4]) if d[:4].isdigit() else None
            if y is None:
                noyear += 1
                continue
            if not (r.get('lat') and r.get('lon')):
                nogeo += 1
                continue
            try:
                lat, lon = float(r['lat']), float(r['lon'])
            except ValueError:
                nogeo += 1
                continue

            dn_cit, vol, num = cite(r.get('DN_REF'), 'DN')
            rn_cit, rvol, rnum = cite(r.get('RN_REF'), 'RN')
            citation = dn_cit or rn_cit or (r.get('SD_ID') or '')

            url = DN_SEARCH_URL
            if DN_ITEM_URL and vol and num:
                url = DN_ITEM_URL.format(vol=vol, num=num)

            abstract = (r.get('sammendrag') or r.get('regest') or '').strip() or None
            uncertain = (r.get('uncertain_loc') or '').strip().upper() == 'TRUE'

            kept += 1
            f.write(json.dumps({
                'corpus': 'DN',
                'id': r.get('DN_REF') or r.get('RN_REF') or r.get('SD_ID'),
                'citation': citation,
                'year': y,
                'date': d or None,
                'issue_place_raw': raw or None,
                'abstract': abstract,
                'place_name': norm_name,
                'lat': round(lat, 6), 'lon': round(lon, 6),
                'country': None,
                'geo_source': 'superdiplomatarium',
                'confidence': 'medium' if uncertain else 'high',
                'source_url': url,
            }, ensure_ascii=False) + '\n')

    print(f'DN rows read      : {n}')
    print(f'  null place      : {nullplace}')
    print(f'  no usable year  : {noyear}')
    print(f'  no coordinates  : {nogeo}')
    print(f'mapped            : {kept}')
    print(f'wrote {out}')

if __name__ == '__main__':
    main()
