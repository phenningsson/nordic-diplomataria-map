#!/usr/bin/env python3
"""Assemble a publishable copy of the project with no restricted text in it.

What is removed: `abstract`, `base_text`, `tran_text` — the editors' regests,
charter transcriptions and translations. Those are the copyrightable editorial
work, and three of the four corpora carry no open licence.

What is kept: charter identifiers and citations, years and dates, the editorial
place-of-issue string, the coordinates we derived, and the link back to the
source edition. Those are facts, citations and URLs — and the link means the
summary is one click away at the publisher's own site rather than copied here.

Diplomatarium Fennicum is CC0-1.0, so its summaries are kept: the public map
still demonstrates what a populated popup looks like.
"""
import json, os, shutil, subprocess, sys

ROOT = '/home/pontus/dd_geo_map'
OUT = os.path.join(ROOT, 'public_build')

STRIP = ('abstract', 'base_text', 'tran_text')
KEEP_TEXT = {'DF'}                      # CC0-1.0

CORPORA = {
    'DD':   'charters_geocoded.jsonl',
    'DN':   'dn_charters_geocoded.jsonl',
    'SDHK': 'sdhk_charters_geocoded.jsonl',
    'DF':   'df_charters_geocoded.jsonl',
}
# small, derived, no charter text — safe to ship so the map is reproducible
COPY_DATA = ['unresolved_places.csv', 'sdhk_unresolved_places.csv',
             'df_unresolved_places.csv', 'issue_place_counts.csv',
             'sdhk_place_counts.csv', 'gazetteer_digdag_names.csv',
             'gazetteer_digdag_units.jsonl', 'gazetteer_digdag_norm_index.csv']
COPY_FILES = ['build_map.py', 'georef_maps.py', 'tora.py', 'geocode.py',
              'geocode_sdhk.py', 'parse_tei.py', 'parse_dn.py', 'parse_sdhk.py',
              'parse_df.py', 'build_gazetteer_from_digdag.py', 'build_name_index.py',
              'resolve_wikidata.py', 'resolve_sdhk_wikidata.py',
              'make_public_build.py', 'PRESENTATION.md']
COPY_TREES = ['gazetteer', 'queries', 'historical_maps', 'docs']

def redact():
    os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
    stats = {}
    for corpus, fn in CORPORA.items():
        src = os.path.join(ROOT, 'data', fn)
        if not os.path.exists(src):
            continue
        kept_text = corpus in KEEP_TEXT
        n = removed = 0
        with open(src, encoding='utf-8') as f, \
             open(os.path.join(OUT, 'data', fn), 'w', encoding='utf-8') as g:
            for line in f:
                r = json.loads(line)
                n += 1
                if not kept_text:
                    for k in STRIP:
                        if r.get(k):
                            r[k] = None
                            removed += 1
                else:
                    for k in ('base_text', 'tran_text'):
                        r.pop(k, None)
                g.write(json.dumps(r, ensure_ascii=False) + '\n')
        stats[corpus] = (n, removed, kept_text)
        print(f'  {corpus:<5} {n:>6,} rows  '
              f'{"summaries KEPT (CC0)" if kept_text else f"{removed:,} text fields removed"}')
    return stats

def verify():
    """Fail loudly if any charter text survived into the public data."""
    bad = 0
    for corpus, fn in CORPORA.items():
        p = os.path.join(OUT, 'data', fn)
        if not os.path.exists(p) or corpus in KEEP_TEXT:
            continue
        for i, line in enumerate(open(p, encoding='utf-8')):
            r = json.loads(line)
            for k in STRIP:
                if r.get(k):
                    bad += 1
                    if bad < 4:
                        print(f'  ! {fn}:{i} still has {k}')
    return bad

def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    print('redacting corpora:')
    redact()

    print('\nverifying no charter text survived:')
    bad = verify()
    if bad:
        print(f'  FAILED: {bad} fields remain'); sys.exit(1)
    print('  clean')

    for f in COPY_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), os.path.join(OUT, f))
    for d in COPY_TREES:
        if os.path.isdir(os.path.join(ROOT, d)):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(OUT, d))
    for f in COPY_DATA:
        s = os.path.join(ROOT, 'data', f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(OUT, 'data', f))
    os.makedirs(os.path.join(OUT, 'output', 'overlays'), exist_ok=True)
    for f in os.listdir(os.path.join(ROOT, 'output', 'overlays')):
        shutil.copy2(os.path.join(ROOT, 'output', 'overlays', f),
                     os.path.join(OUT, 'output', 'overlays', f))

    print('\nbuilding the public map:')
    env = dict(os.environ, DD_DATA_DIR=os.path.join(OUT, 'data'),
               DD_OUT_DIR=os.path.join(OUT, 'output'), DD_PUBLIC='1')
    subprocess.run([sys.executable, os.path.join(ROOT, 'build_map.py')],
                   check=True, env=env)

if __name__ == '__main__':
    main()
