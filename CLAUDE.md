# Brief: Visualising place names in Diplomatarium Danicum

**Goal.** Build an interactive map of the places in *Diplomatarium Danicum* (DD) —
medieval Danish charters, 789–1450 — with a time dimension, so one can watch
*where* documents were issued and which places they mention move across the
Baltic and Europe over six centuries. Hackathon scope: ~1.5 days. Ship a working
map, not a research pipeline.

Read this whole file first, then inspect the actual data to confirm the field
coverage numbers below before committing to an approach. The numbers are a
built-in sanity check for your parser.

---

## What's in the workspace

- `diplomatarium-danicum/` — cloned from `dsldk/diplomatarium-danicum`. Layout:
  - `dd-1/<year>/dd_<id>.xml` — 789–1400, 16,421 files
  - `dd-2/<year>/dd_<id>.xml` — 1401–1450 + supplements to 789–1400, 7,473 files
  - `dipdan/` — front matter only (preface/intro), ignore
  - Total charter files: **23,894**, all valid TEI P5, 0 parse failures.
- **DigDag** (historical Danish parishes/*herreder* etc.) — uploaded separately.
  Inspect it first (see Geocoding). You do not yet know its exact schema/format;
  do not assume — open it and find the name field(s), geometry, unit type, and
  any historical name variants / validity dates.

**Licensing — important.** The repo has **no LICENSE file** and the TEI headers
mark material `<availability status="restricted">` © DSL. Treat as **internal
hackathon use only**: do not republish the derived text corpus and do not deploy
the map publicly without clearing terms with DSL (repo contact `smb@dsl.dk`).

---

## Where the signal is (TEI structure)

Namespace: `http://www.tei-c.org/ns/1.0`. Per-file fields, with measured coverage
across all 23,894 docs:

| Field | XPath (relative to root) | Coverage | Use |
|---|---|---|---|
| DD id | `//teiHeader//idno[@type='dd']` (also filename stem after `dd_`) | 100% | primary key |
| **Year** | first 4 chars of the numeric id (`dd_12310416001` → `1231`) | 100% | timeline axis (robust) |
| Full issue date | `//profileDesc/creation/date/@when` (ISO `YYYY-MM-DD`) | 87% | precise date when present |
| **Issue place** | `//profileDesc/creation/placeName` (text) | 67% | Phase 1 map — **the main signal** |
| **Danish regest** | `//profileDesc/abstract//ab` | **99.97%** | Phase 2 NER target; map popups |
| Original text | `//text/body/div[@type='base_text']` | 63% | Latin/MLG/ODan; on-click detail |
| Danish translation | `//text/body/div[@type='tran_text']` (`xml:lang='ynda'`) | 60% | fuller NER target (Phase 2) |

Notes that will bite you if ignored:
- **`<placeName>` values are already normalised conventional forms** — `Avignon`,
  `Lübeck`, `Roskilde` — *not* Latin (`Reualie`). String matching is tractable.
- **~3,496 issue-place tags are the literal placeholder `empty`.** Filter these
  out (unknown issue place). Real tagged places ≈ 12,600. Distinct strings: 1,696.
- The date-encoded filename can carry placeholder `MMDD` when only the year is
  known, so derive **year** from the id but take the full date from
  `creation/date/@when` only when present.
- When extracting `tran_text`, **exclude nested editorial divs**
  `div[@type='app']` (variant apparatus), `div[@type='cit']`, `div[@type='nts']`
  (notes) — they are dense editorial noise, not charter content.
- **Do not trust `//profileDesc/langUsage/language/@ident`** — frequently `nil`.
  If you need the source language, detect from text; better, just don't depend on it.
- ~15,000 docs also have untyped body `<div>`s; the `<abstract>` is the only truly
  universal text field, which is why it's the recommended NER target.

---

## Pipeline

### Phase 1 — issue-place map (MVP, no NER, do this first)
This is a complete, low-risk deliverable on structured metadata alone.
1. `parse_tei.py`: walk `dd-1/`, `dd-2/`; emit `data/charters.jsonl` with
   `{id, year, date, issue_place_raw, abstract, has_translation, source_url}`.
   `source_url = https://tekstnet.dk/books/dipdan/{year}/{id}`.
2. Geocode `issue_place_raw` (see below) → `data/charters_geocoded.jsonl` adding
   `{place_name, lat, lon, geo_source, confidence}`. Drop `empty`; keep
   unresolved rows flagged (don't silently discard).
3. Build the map (see Visualisation).

### Phase 2 — mentioned places (enrichment, only if Phase 1 is solid)
1. NER over the `<abstract>` (clean modern Danish, name-dense, universal
   coverage) to extract mentioned place names. Start with spaCy
   `da_core_news_lg` or DaCy (`da_dacy_large_trf`), LOC/GPE; fall back to a
   few-shot LLM pass for recall (abstracts are short → cheap). Optionally also
   run over `tran_text` (apparatus stripped) for richer coverage.
2. Geocode the extracted mentions through the same resolver.
3. Add a second map layer: density/heat of mentioned places vs. issue places.

---

## Geocoding strategy

The frequency distribution decides the design. Top issue places are
**foreign-dominated** — Avignon (1025), the Rome/curia cluster
(Rom / S. Pietro / Lateranet / Viterbo / Orvieto), Lübeck (499), Stralsund,
Rostock, Marienburg, Reval, Villeneuve, Lyon, Bologna, Firenze, Westminster —
interleaved with Danish hubs (Roskilde, Lund, København, Ribe, Vordingborg,
Helsingborg, Nyborg, Kalundborg, Flensborg, Slesvig, Odense). **DigDag will not
contain the foreign places**, so it cannot be the primary resolver.

Resolve in this order:
1. **Curated table (primary).** `gazetteer/curated_places.csv` mapping raw
   issue-place strings → `{modern_name, lat, lon, country}`. Because the
   distribution is steeply Zipfian, hand-curating the **top ~100–150 strings**
   resolves the large majority of tagged documents at high precision. Seed it
   from the actual value counts (compute them first), grouped roughly as: papal
   curia, Hanseatic/Baltic, Danish towns, other European. Resolve coordinates via
   Wikidata/GeoNames and spot-check — do not hardcode from memory.
2. **DigDag (supplementary).** Build `data/gazetteer_digdag.jsonl` from the
   uploaded DigDag: extract unit name(s) + historical variants, centroid any
   polygon geometry to a point, keep unit type + validity period. Use it to
   resolve the Danish long tail (parish/*herred*/town names) not in the curated
   table, and any Danish hits from Phase-2 NER.
3. **Optional fallback.** Wikidata SPARQL / GeoNames fuzzy match for whatever
   remains unresolved.

Matching hygiene: normalise on both sides — casefold, consistent handling of
`å/ä/ø/ö`, expand `S.` → `Sankt`, strip parentheticals
(`Rom, Santi Apostoli` → `Rom`; `S. Pietro i Rom` → `Rom`). Emit a `confidence`
and `geo_source` per row. Leave unresolved places visible in a sidebar/log so the
gap is honest, not hidden.

---

## Visualisation

- Leaflet (vanilla, most control) or Folium (fastest to stand up); kepler.gl if
  you want flash for the demo. Output a single self-contained
  `output/dd_map.html`.
- **Time is the payoff.** Every charter has a year → add a time slider / animation
  over 789–1450. Watch issue locations shift: early Danish core, then the papal
  curia (Avignon/Rome) and Hanseatic Baltic light up. This is what turns a dot map
  into a story; it's nearly free given the date field.
- Markers clustered or as a heat layer; popups show the Danish `abstract` + a link
  to `source_url`. Add reign/decade filters if time allows (reign boundaries are
  in the tekstnet TOC).
- Two toggleable layers once Phase 2 exists: *issued-from* vs *places mentioned*.

---

## Definition of done

**MVP (target):** `charters.jsonl` for all docs → issue places resolved via
curated table + DigDag → interactive `dd_map.html` with a working time slider
showing issued-from locations 789–1450, popups linking back to tekstnet.
**Stretch:** NER over abstracts for mentioned-place layer; reign/decade filters;
Latin original shown on click.

Suggested day plan: (½) parser + clean JSONL, verify counts against the table
above; (½) curated gazetteer for top ~100 places + DigDag resolver + geocode;
(½) map + time slider + polish + 2 rehearsed example moments (e.g. the Avignon
papacy cluster; the Baltic/Hanseatic spread under Valdemar Atterdag). Do one rich
sub-period end-to-end first (e.g. 1340–1375) before running the full corpus.

## Suggested repo layout
```
parse_tei.py                  -> data/charters.jsonl
gazetteer/curated_places.csv  (seed: top ~100 issue-place strings)
build_gazetteer_from_digdag.py-> data/gazetteer_digdag.jsonl
geocode.py                    -> data/charters_geocoded.jsonl
build_map.py                  -> output/dd_map.html
ner_abstracts.py  (Phase 2)   -> data/mentioned_places.jsonl
```