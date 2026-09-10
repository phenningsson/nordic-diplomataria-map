#!/usr/bin/env python3
"""Parse sdhk_2411.csv (Svenskt Diplomatariums huvudkartotek, full set) into
data/sdhk_charters.jsonl + data/sdhk_place_counts.csv.

The file is cp1252 (curly quotes at 0x94), semicolon-delimited, CRLF, with 16
stray 0x81 bytes that are undefined even in cp1252 - those are replaced.
"""
import csv, io, json, os, re, collections

ROOT = '/home/pontus/dd_geo_map'
SRC = os.path.join(ROOT, 'sdhk_2411.csv')
csv.field_size_limit(10 ** 9)

# Confirmed working short form (the UI adds a long tail of filter params):
#   https://sok.riksarkivet.se/sdhk/12516?EndastDigitaliserat=false&SDHK=12516
SDHK_URL = 'https://sok.riksarkivet.se/sdhk/{id}?EndastDigitaliserat=false&SDHK={id}'

def read_rows():
    raw = open(SRC, 'rb').read().decode('cp1252', errors='replace')
    return list(csv.DictReader(io.StringIO(raw), delimiter=';'))

def parse_date(s):
    """-> (year, iso_date_or_None). Date is YYYYMMDD, sometimes with a trailing
    comment; MMDD=0000 means only the year is known."""
    s = (s or '').strip()
    m = re.match(r'(\d{4})(\d{2})(\d{2})', s)
    if m:
        y, mo, d = int(m.group(1)), m.group(2), m.group(3)
        if y < 700 or y > 1700:
            return None, None                     # 0/00000000 junk
        iso = f'{y:04d}-{mo}-{d}' if mo != '00' and d != '00' else None
        return y, iso
    m = re.match(r'(\d{4})', s)                   # '1430; odat.; omkring 1430'
    if m:
        y = int(m.group(1))
        return (y, None) if 700 <= y <= 1700 else (None, None)
    return None, None

def main():
    rows = read_rows()
    out = os.path.join(ROOT, 'data', 'sdhk_charters.jsonl')
    counts = collections.Counter()
    n = kept = noyear = noplace = 0
    with open(out, 'w', encoding='utf-8') as f:
        for r in rows:
            n += 1
            y, iso = parse_date(r.get('Date'))
            if y is None:
                noyear += 1
                continue
            place = (r.get('Place') or '').strip()
            if place:
                counts[place] += 1
            else:
                noplace += 1
            rid = (r.get('Id') or '').strip()
            kept += 1
            f.write(json.dumps({
                'corpus': 'SDHK',
                'id': rid,
                'citation': (r.get('Title') or f'SDHK nr {rid}').strip(),
                'year': y,
                'date': iso,
                'issue_place_raw': place or None,
                'abstract': (r.get('Summary') or '').strip() or None,
                'lang': (r.get('Lang') or '').strip() or None,
                'source_url': SDHK_URL.format(id=rid) if rid else None,
            }, ensure_ascii=False) + '\n')

    cp = os.path.join(ROOT, 'data', 'sdhk_place_counts.csv')
    with open(cp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['issue_place_raw', 'n_charters'])
        for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            w.writerow([k, v])

    print(f'rows read      : {n}')
    print(f'  unusable date: {noyear}')
    print(f'kept           : {kept}')
    print(f'  with a place : {kept-noplace}')
    print(f'  no place     : {noplace}')
    print(f'distinct places: {len(counts)}')
    print(f'wrote {out}')
    print(f'wrote {cp}')

if __name__ == '__main__':
    main()
