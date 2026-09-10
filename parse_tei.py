#!/usr/bin/env python3
"""Parse the Diplomatarium Danicum TEI corpus into data/charters.jsonl.

One JSON object per charter:
  {id, year, date, issue_place_raw, abstract, base_text, tran_text,
   has_translation, source_url}
"""
import json, os, re, sys
import xml.etree.ElementTree as ET

ROOT = '/home/pontus/dd_geo_map'
CORPUS = os.path.join(ROOT, 'diplomatarium-danicum')
TEI = '{http://www.tei-c.org/ns/1.0}'

# editorial divs that are apparatus/notes, not charter content
SKIP_DIV_TYPES = {'app', 'cit', 'nts'}

def text_of(el, skip_div_types=frozenset()):
    """Concatenate descendant text, optionally pruning editorial <div> subtrees."""
    parts = []
    def walk(e):
        if (e.tag == TEI + 'div'
                and e.get('type') in skip_div_types):
            if e.tail:
                parts.append(e.tail)
            return
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
        if e.tail:
            parts.append(e.tail)
    if el.text:
        parts.append(el.text)
    for c in el:
        walk(c)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()

def find_body_div(root, dtype):
    for d in root.iter(TEI + 'div'):
        if d.get('type') == dtype:
            return d
    return None

def parse(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return None, f'{os.path.basename(path)}: {e}'

    stem = os.path.basename(path)[3:-4]          # dd_12310906001.xml -> 12310906001

    # Two files carry a malformed <idno type="dd"> ("14", "n"); the filename stem
    # is always well-formed, so only trust the idno when it looks like a DD id.
    dd_id = stem
    for idno in root.iter(TEI + 'idno'):
        if idno.get('type') == 'dd':
            t = (idno.text or '').strip()
            if re.fullmatch(r'\d{8,}', t):
                dd_id = t
            break

    # year from the id is 100% reliable; the MMDD part can be a placeholder
    m = re.match(r'(\d{4})', dd_id)
    year = int(m.group(1)) if m else None
    year_str = m.group(1) if m else None      # zero-padded: tekstnet uses /0895/

    date = None
    place_raw = None
    creation = None
    for pd in root.iter(TEI + 'profileDesc'):
        creation = pd.find(TEI + 'creation')
        if creation is not None:
            break
    if creation is not None:
        d = creation.find(TEI + 'date')
        if d is not None and d.get('when'):
            date = d.get('when').strip() or None
        p = creation.find(TEI + 'placeName')
        if p is not None:
            place_raw = text_of(p) or None

    abstract = None
    for ab_parent in root.iter(TEI + 'abstract'):
        abstract = text_of(ab_parent) or None
        break

    base_div = find_body_div(root, 'base_text')
    tran_div = find_body_div(root, 'tran_text')
    base_text = text_of(base_div, SKIP_DIV_TYPES) if base_div is not None else None
    tran_text = text_of(tran_div, SKIP_DIV_TYPES) if tran_div is not None else None

    return {
        'id': dd_id,
        'year': year,
        'date': date,
        'issue_place_raw': place_raw,
        'abstract': abstract or None,
        'base_text': base_text or None,
        'tran_text': tran_text or None,
        'has_translation': bool(tran_text),
        # NB: the pattern in CLAUDE.md omits the dd_ prefix and 404s. Real form is
        # https://tekstnet.dk/books/dipdan/<year>/dd_<id>/  (verified against
        # indexed pages, e.g. .../1379/dd_13791122001/). Folder year always
        # equals the id's first 4 chars across all 23,894 files.
        'source_url': (f'https://tekstnet.dk/books/dipdan/{year_str}/dd_{dd_id}/'
                       if year_str else None),
    }, None

def main():
    files = []
    for sub in ('dd-1', 'dd-2'):
        d = os.path.join(CORPUS, sub)
        for dirpath, _, names in os.walk(d):
            for n in sorted(names):
                if n.startswith('dd_') and n.endswith('.xml'):
                    files.append(os.path.join(dirpath, n))
    files.sort()
    print(f'{len(files)} charter files', flush=True)

    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    out = os.path.join(ROOT, 'data', 'charters.jsonl')
    errors = []
    n = 0
    stats = {'date': 0, 'place': 0, 'place_empty': 0, 'abstract': 0,
             'base': 0, 'tran': 0}
    places = {}
    with open(out, 'w', encoding='utf-8') as f:
        for i, p in enumerate(files):
            rec, err = parse(p)
            if err:
                errors.append(err); continue
            n += 1
            if rec['date']: stats['date'] += 1
            pr = rec['issue_place_raw']
            if pr:
                if pr.strip().lower() == 'empty':
                    stats['place_empty'] += 1
                else:
                    stats['place'] += 1
                    places[pr] = places.get(pr, 0) + 1
            if rec['abstract']: stats['abstract'] += 1
            if rec['base_text']: stats['base'] += 1
            if rec['tran_text']: stats['tran'] += 1
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if (i + 1) % 5000 == 0:
                print(f'  {i+1}/{len(files)}', flush=True)

    pct = lambda k: f'{100*stats[k]/n:.2f}%'
    print(f'\nparsed          : {n} / {len(files)}   parse failures: {len(errors)}')
    print(f'full date @when : {stats["date"]:>6}  {pct("date")}   (brief: 87%)')
    print(f'issue place     : {stats["place"]:>6}  {pct("place")}   (brief: 67% / ~12,600)')
    print(f'  placeholder "empty": {stats["place_empty"]}          (brief: ~3,496)')
    print(f'  distinct place strings: {len(places)}                (brief: 1,696)')
    print(f'abstract        : {stats["abstract"]:>6}  {pct("abstract")}   (brief: 99.97%)')
    print(f'base_text       : {stats["base"]:>6}  {pct("base")}   (brief: 63%)')
    print(f'tran_text       : {stats["tran"]:>6}  {pct("tran")}   (brief: 60%)')
    if errors:
        print('\nfirst errors:'); [print('  ', e) for e in errors[:10]]

    # value counts drive the curated gazetteer; write them out for seeding
    vc = os.path.join(ROOT, 'data', 'issue_place_counts.csv')
    import csv
    with open(vc, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['issue_place_raw', 'n_charters'])
        for k, v in sorted(places.items(), key=lambda kv: (-kv[1], kv[0])):
            w.writerow([k, v])
    print(f'\nwrote {out}')
    print(f'wrote {vc}')

if __name__ == '__main__':
    main()
