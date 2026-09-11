# DD geo map — pipeline

Phase 1 (issue-place map) is complete. Scripts run in this order from the repo root.

| Step | Script | Output |
|---|---|---|
| 1 | `build_gazetteer_from_digdag.py` | `data/gazetteer_digdag.jsonl` (76,799 name-versions, 100% with centroid) |
| 2 | `build_name_index.py` | `data/gazetteer_digdag_units.jsonl` (24,561 units), `data/gazetteer_digdag_names.csv`, `data/gazetteer_digdag_norm_index.csv` |
| 3 | `parse_tei.py` | `data/charters.jsonl` (23,894), `data/issue_place_counts.csv` |
| 4 | `resolve_wikidata.py [topN]` | `gazetteer/wikidata_resolved.csv` (cache), `gazetteer/curated_places.csv` |
| 5 | `geocode.py` | `data/charters_geocoded.jsonl`, `data/unresolved_places.csv` |
| 5b | `parse_dn.py` | `data/dn_charters_geocoded.jsonl` (Diplomatarium Norvegicum) |
| 5c | `parse_sdhk.py` → `resolve_sdhk_wikidata.py` → `geocode_sdhk.py` | `data/sdhk_charters_geocoded.jsonl` (SDHK) |
| 5d | `parse_df.py` | `data/df_charters_geocoded.jsonl` (Diplomatarium Fennicum) |
| 5e | `georef_maps.py` | `output/overlays/*.png` + `overlays.json` (historical basemaps) |
| 6 | `build_map.py` | `output/dd_map.html` |

Step 1 reads ~17 GB of shapefile geometry and takes a few minutes; steps 2–6 are fast.
Step 4 needs network (`query.wikidata.org`) and caches, so reruns are cheap.
Deps: `numpy`, `pyproj`. (`pyshp` is installed but unused — geometry is parsed directly.)

## Verified against the brief

`parse_tei.py` reproduces every coverage figure in `CLAUDE.md`: 23,894 files, **0 parse
failures**, date `@when` 87.2%, issue place 12,600, placeholder `empty` 3,496, distinct
strings 1,695, abstract 99.97%, base_text 62.7%, tran_text 59.7%.

## Things the data does that will bite you

- **`nil` is a second null placeholder** alongside `empty` (15 charters). Both filtered.
- **DigDag names are not unique places.** `Lund Ejerlav` names 12 different Danish
  places; a median across them lands in open country. Everything is therefore keyed on
  `enhedid` (the stable unit id), and names whose units sit >25 km apart are marked
  `ambiguous` with lat/lon **left blank** and candidates listed — 949 of 20,855 names.
- **DigDag has no Scania.** Skåne, Halland and Blekinge were Danish in this period but
  are absent from DigDag (it covers modern Denmark + Slesvig). `Lund`, `Helsingborg`,
  `Malmø`, `Varberg`, `Åhus` etc. come from Wikidata, not DigDag.
- **DigDag `fra` uses `1000-01-01` as an "unknown/always" sentinel** and most genuinely
  dated units start 1500s+. It is used as a *name + centroid gazetteer only* — it does
  not support claims about medieval boundaries.
- **The `source_url` pattern in `CLAUDE.md` is wrong and 404s.** The brief gives
  `books/dipdan/{year}/{id}`; the real form is
  `https://tekstnet.dk/books/dipdan/<year>/dd_<id>/` — the `dd_` prefix is required
  and the year is **zero-padded** to 4 digits (`/0895/`, not `/895/`). Verified
  against indexed pages (`/1379/dd_13791122001/`, `/0895/`). Folder year equals the
  id's first 4 chars across all 23,894 files, so the two never diverge.
- **Two files carry a malformed `<idno type="dd">`** (`14` and `n`). The filename
  stem is always well-formed, so the idno is only trusted when it matches `\d{8,}`.
- **Cross-language label collisions are the main geocoding hazard.** `Konstanz` is the
  Romanian name of Constanța; `Vienne` the French name of Vienna. `gazetteer/overrides.csv`
  pins these with a hard country constraint. Dating confirmed each fix (Konstanz median
  1417 = Council of Constance; Vienne ends 1312 = Council of Vienne; Gurre 1374–1407 =
  the Zealand castle, not Gurrë in Albania).

## Four corpora

Coloured by corpus, with a **multi-select** corpus filter and a shared time slider.
Each corpus button toggles that corpus in or out independently, so any combination can
be shown; **All** selects everything (and, pressed when everything is already on, drops
back to a single corpus). Deselected corpora are greyed out in the legend and report
zero in the sidebar. With nothing selected the map is empty and says so.

| | mapped | span | links |
|---|---|---|---|
| DD | 10,862 | 789–1450 | per-charter (tekstnet) |
| DN | 16,319 | 1061–1590 | **search page only** |
| SDHK | 26,391 | 1150–1546 | per-charter (Riksarkivet) |
| DF | 4,540 | 1154–1530 | per-charter (df.narc.fi) |
| **total** | **58,112** | **789–1590** | |

### Palette: why the colours changed when DF was added

Four categories on a map is an **all-pairs** problem — any two corpora can sit adjacent
(Avignon carries all four). Brute-forcing the documented 8-slot categorical palette with
`validate_palette.js`, exactly **two** 4-hue subsets clear every all-pairs gate in both
light and dark: `blue+yellow+magenta+green` and `yellow+magenta+green+violet`. The first
is used because it keeps DD's established blue. That is why DN moved orange→yellow and
SDHK aqua→magenta: no 4-hue set containing both orange and aqua passes.

Worst all-pairs CVD is ΔE 6.9, inside the 6–8 band that is legal **only with secondary
encoding**, so each corpus additionally carries its own marker stroke dash (DD solid,
DN `5,3`, SDHK `1,3`, DF `7,2,1,2`) and every table row is tagged with its corpus.

### Diplomatarium Fennicum

Source: [huggingface.co/datasets/Kansallisarkisto/Diplomatarium-Fennicum](https://huggingface.co/datasets/Kansallisarkisto/Diplomatarium-Fennicum),
**CC0-1.0** — the only openly licensed corpus in this project. 6,876 records, 6,854 with
a usable year, 4,562 with an issuing place.

No geocoding pass was needed at all: `df_platser.csv` is the exact companion register to
this dataset, and **99.5% of issuing places join by name** (4,216 exact + 324 on the head
before the comma, since entries like `Ajosenpää, Masku` qualify a farm by its parish).
Only 22 charters are unresolved. Zero fall outside Europe.

DF has no regest field, so popups show a transcript excerpt, falling back to the Finnish
`indexterm` taxonomy. Country names arrive in Finnish (`Suomi`, `Ruotsi`, `Saksa`) and are
mapped to English. 12 rows disagree with the register on country — all benign
historical-vs-modern cases such as Cēsis/Wenden recorded as `Saksa` but sitting in Latvia.

### SDHK

`sdhk_2411.csv` is **cp1252** (not UTF-8 — 0x94 curly quotes, 71k of them), semicolon-
delimited, CRLF, with 16 stray 0x81 bytes undefined even in cp1252, which are replaced.
44,264 rows; 43,837 have a usable year; 32,586 carry a `Place`.

Geocoding reuses everything already built — no new gazetteer was needed for 71% of it:

| source | charters |
|---|---|
| DD curated/Wikidata (shared curia + Hanseatic hubs) | 14,781 |
| hand overrides | 4,090 |
| DN places | 3,480 |
| SDHK Wikidata pass | 2,217 |
| Fennicum | 1,823 |
| TORA (name) | 663 |
| TORA (härad centroid) | 443 |
| TORA (parish centroid) | 131 |
| GeoNames (settlements/admin only) | 699 |
| **geocoded** | **28,327 (86.9% of tagged)** |

Cleaning that matters: strip curly quotes (`”Östraaros”`), strip `kloster`/`slott`/
`kyrka` suffixes, resolve `X i Rom` → `Rom` (`Peterskyrkan i Rom`, 107 charters), and
strip the **Swedish genitive -s** (`Stockholms slott` → `Stockholms` → `Stockholm`,
162 charters).

**DigDag is deliberately excluded from the SDHK chain.** Against a Swedish corpus the
Danish gazetteer produces cross-border false friends — `Torsö` (the island in Vänern)
→ Torsø Ejerlav in Jutland, `Risinge kyrka` (Östergötland) → Risinge Ejerlav on Fyn,
likewise Karby/Löt/Horn/Broby. It contributed 119 charters, most of them wrong. Those
strings are now honestly unresolved instead. Fennicum, by contrast, is excellent for
SDHK (Nådendal, Raseborg, Alvastra, Varnhem, Vårfruberga) — it covers Swedish-realm
places, not just Finnish ones.

Mis-geocodes caught by spot-check and pinned in `gazetteer/sdhk_overrides.csv`:
`Nydala` → the Skåne locality instead of the Småland abbey; `Clairvaux` →
Clairvaux-d'Aveyron instead of the Cistercian mother house in Aube; `Djula` → Diula in
Ukraine (the source itself glosses it "Djulö?", i.e. Södermanland). After fixes, **zero
of 26,391 geocoded SDHK charters fall outside Europe**, and only 33 outside the
Nordic/Baltic core — all genuine papal-itinerary places.

The range runs to **1590**, not 1450: clipping at 1450 would drop 51% of geocoded DN.
DD ends at 1450 by construction, so everything later is DN-only — the sidebar says so.
DN needs no geocoding; `Normalized_name`/`lat`/`lon` ship with the source data.

Two cosmetic consequences of keying places per corpus, both intentional: a shared place
appears twice when Both is selected (Avignon DD 418 / Avignon DN 271), and the two
projects normalise differently (`Rome` in DD, `Roma` in DN). The table tags each row
with its corpus.

### DN charter links are NOT per-charter — read this

DD links are verified deep links. **DN links go to the DN search page**, not the
individual charter. The dokpro URL is `diplom_vise_tekst.prl?b=<id>` where `b` is an
opaque internal database id that cannot be derived from volume + number: for the one
citation we could check (DN IV nr. 217 = `b=3689`), a rank-based reconstruction came
out **105 off**, which would link the wrong charter. Emitting the accurate citation
(`DN IV nr. 714`) beats emitting a confidently wrong link.

To turn these into deep links, set `DN_ITEM_URL` in `parse_dn.py` and `DN_SEARCH` in
`build_map.py` once a real per-charter URL pattern is known. One working example URL
alongside its volume/number is enough to calibrate.

**Note:** this environment sits behind the Riksarkivet web filter, which blocks
`tekstnet.dk`, `dokpro.uio.no` and `archive.org`, so none of these URLs could be
tested from here. The DD pattern rests on indexed pages, not a live fetch.

## Coverage

10,860 of 12,585 tagged charters mapped (86.3%) across 377 places.
Curated/Wikidata resolves 10,175; the institutional-compound rule (`Ribe byting` → `Ribe`)
adds 254; DigDag resolves 433 of the Danish long tail (`Houlbjerg herredsting` →
Houlbjerg Herred). 1,118 strings (1,723 charters) remain unresolved and are listed in
`data/unresolved_places.csv` and in the map sidebar — visible, not silently dropped.

## Historical basemap overlay

A sidebar toggle (Off / Blaeu / Olaus Magnus) drops a georeferenced historical map
between the tiles and the charter markers, with an opacity slider. Markers always stay
on top — the overlay lives in its own Leaflet pane at `z-index: 250`, between the tile
pane (200) and the overlay pane (400).

`georef_maps.py` warps each scan into Web Mercator so `L.imageOverlay` places it
correctly from plain lat/lon bounds.

**Method: thin-plate spline**, not a polynomial. Control points are landmarks read off
each sheet by eye. The route there is worth recording, because the obvious approaches
fail:

| fit | RMS | what happens |
|---|---|---|
| affine (order 1) | 166 px | stable, but cannot follow the conic projection |
| polynomial order 2 | 94 px | already spirals outside the control-point hull |
| polynomial order 3 | 44 px | fits the points, destroys the map — extrapolation blow-up |
| **thin-plate spline** | **6 px** | interpolates the points, degrades gracefully outside |

Two control points were badly misread on the first pass and had to be fixed against
high-zoom crops: Sicily was 130 px out (I had picked a point past the crop edge) and
Crete 30 px, which together produced a visible fold across Italy. The check that caught
it was plotting known city coordinates onto the warped image and looking — not the RMS.

| overlay | RMS | control points | note |
|---|---|---|---|
| Blaeu, *Europa recens descripta* (c. 1640) | 6.0 px | 13 | fits closely; Dublin, London, Paris, Palermo, Athens all land correctly |
| Olaus Magnus, *Carta Marina* (1539) | 99 px | 17 | **loose by construction** — a genuinely distorted 1539 map, decorative only |

Note the file named `europe_1492.jpg` is not from 1492: the cartouche reads
*Europa recens descripta a Guilielmo Blaeuw*, an Amsterdam map of about 1640.

**The overlays are inlined into the HTML as `data:` URIs**, not referenced by relative
path. Referencing `overlays/*.png` works when the page is served but not reliably when
it is opened straight off disk — browsers differ on whether a `file://` page may pull in
a sibling file, and this page is meant to be double-clicked. Inlining removes the
question, and matches the brief's "single self-contained `output/dd_map.html`".

WebP keeps the cost down: 21.4 MB of PNG becomes 4.7 MB of WebP (alpha preserved
exactly, mean RGB delta 2.9/255) and ~6.3 MB once base64-encoded. `dd_map.html` is
18.2 MB and **needs no other file** — verified by deleting `output/overlays/` and
reloading. That directory is still written, since the PNGs are useful for reuse
elsewhere (QGIS and the like), but the page does not depend on it.

## Basemap

Tiles are keyless OpenStreetMap, with CARTO as a fallback used only when OSM fails
outright. Esri's free `Canvas/World_Light_Gray_Base` is **not** used — it now stamps
"API KEY REQUIRED" across every tile.

## External data

See `external/PROVENANCE.md`. `external/dn_letters.csv` is the complete
Diplomatarium Norvegicum (25,011 records, 78% pre-geocoded) from
`Moryzont/SuperDiplomatarium` — **no licence, ask the author before reuse**.

## Coarse over precise

The resolver follows one rule throughout: **a coarse location that is certainly in the
right region beats a precise one that may be in the wrong province.** When a name is
ambiguous the chain does not pick the likeliest point and does not drop the row — it
backs off to the smallest administrative unit containing every candidate.

In practice that means backing off through three tiers:

| precision | when | drawn as |
|---|---|---|
| `point` | a located settlement | solid fill |
| `parish` | candidates share one parish, or the register knows the parish but never geocoded the name | half-filled, dashed ring |
| `harad` | candidates share one hundred, or the string is `X häradsting` | hollow, dashed ring |

`Oppunda häradsting` cannot be resolved to a building, but every settlement of Oppunda
härad is known, so the charter goes to their centroid. The opacity ramp makes certainty
legible at a glance, and the popup states the tier outright. Approximation is visible
rather than implied.

The parish/härad distinction can be finer than a reader needs, so a **"Distinguish
parish from härad" checkbox** collapses the two approximate tiers into one shared style.
The underlying `precision` value is unchanged — only the drawing and the popup wording
follow the toggle — so the data stays as precise as it was either way.

The same rule excludes GeoNames farm records: only feature classes P (populated) and A
(admin) are consulted, because a farm-level hit in the wrong province is invisible on a
map and worse than no hit at all.

## TORA — obtained via the geometric maps release

`external/aggk/` (Zenodo 15121019, CC-BY-4.0) carries TORA identifiers **with
coordinates**: 12,206 settlement units, 11,926 geocoded, 92% flagged `high` accuracy,
plus `parish`, `hundred` (150 härad) and `toraid_url`. `tora.py` builds the resolver.

Against SDHK it adds **663 charters by name, 443 by härad centroid and 131 by parish
centroid**. The härad half matters most: it is the only source that resolves
`X häradsting` at all, because neither Wikidata nor GeoNames holds medieval hundreds.

Two normalisation traps cost real coverage before they were caught. The register writes
the härad in the genitive (`Bankekinds h:d`) while the charter may not (`Bankekind ting`),
so **the same key function must be applied to both sides** — stripping the genitive on
only one lost ~440 ting strings. And parish labels must be kept in their original form
for display: deriving them from the normalised match key rendered `Skatelöv` as
`Skateloev`.

Coverage is the provinces surveyed in 1630–55 — Uppland, Östergötland, Västergötland,
Södermanland, Småland, Värmland, Västmanland, then thinning. No Skåne, Halland or
Blekinge (Danish in period), little Norrland, no Finland. It does not help DD or DN.

### Widening it: the TORA SPARQL endpoint

TORA has a public SPARQL endpoint at `tora.entryscape.net/snorql/`, which would supply
the whole register rather than the map-surveyed slice. **It cannot be reached from this
environment** — the Riksarkivet web filter blocks `entryscape.net`, and WebFetch routes
the same way — and TORA is not mirrored on GitHub, HuggingFace or Zenodo. So the export
has to be run from a browser that can reach it.

`queries/tora_sparql.md` holds the queries, written against TORA's **actual** ontology:
the class is `tora:HistoricalSettlementUnit`, and the Swedish hierarchy is
`tora:earlyModernProvince` (landskap) > **`tora:earlyModernDistrict` (härad)** >
`tora:earlyModernParish` (socken), with `skos:prefLabel`/`skos:altLabel` for names and
the W3C geo vocabulary for coordinates. Each division is dereferenced with a
`COALESCE(?label, STR(?node))` so the query works whether the property points at a
resource or a bare literal. There is a lighter variant without the `GROUP_CONCAT` for
the case where the aggregate times out.

**The ingestion side is already built and tested.** Drop any CSV into `external/tora/`
and `tora.py` picks it up automatically: it sniffs the delimiter, matches headers by
substring (so the exact SPARQL projection does not matter), and merges the rows into the
existing index — points where coordinates exist, parish/härad membership where they do
not. Verified against a synthetic export in the real query's shape: `Tingvalla
häradsting` and `Jönåkers ting`, both currently unresolvable, resolve to härad centroids;
alt-labels (`Tingwalla`, `Tingvallen`) match; a row with a parish but no coordinate lands
on the parish centroid. Two details the test caught — `district` has to be tried before
`harad` in header matching, and `altnames` must not be matched as `name`; and a label
already ending in `härad` must not have a second one appended, since the SPARQL export
spells it out where the geometric-maps CSV abbreviates to `h:d`.

Expected gain: **839 SDHK charters name a härad the current subset lacks** — `Tingvalla`
(31), `Jönåker` (24), `Trögd` (19), `Österrekarne` (13), `Sunnerbo`, `Motala` and ~500
others — which is the largest identifiable block in the 4,259 still unplaced.

The companion release for the *younger* maps (Zenodo 15118501, 1680–1700) is
**transcriptions only** — 6,533 HTML pages, no `toraid`, no coordinates — so it is a
name source, not a gazetteer, and is not wired in.

## GeoNames — available, measured, partly wired in

`download.geonames.org` is blocked by the Riksarkivet web filter, but the HuggingFace
mirror `DataDock/geonames` (CC-BY-4.0, snapshot 2026-09-01) is not, and republishes the
official per-country dumps. SE/NO/DK/FI/EE/IS are in `external/geonames/` (211 MB):
1.30 M rows, 1.68 M alternate names, 288,260 in feature classes P/A/S.

Measured against the unresolved tails, matching name variants with a per-corpus country
restriction and preferring settlements over farms:

| corpus | unresolved | GeoNames unambiguous | ambiguous | still nothing |
|---|---|---|---|---|
| SDHK (SE, FI) | 6,195 charters | **1,506 (24.3%)** | 640 | 4,049 |
| DD (DK, SE, DE) | 1,723 charters | **213 (12.4%)** | 149 | 1,361 |
| DF (FI, SE, EE) | 22 charters | 12 | 2 | 8 |

The country restriction matters: unrestricted, GeoNames put `Siena` in Norway (matching
Skien's alternate name) and `Friedland` on a Norwegian farm. Restricted, those go away.

**Only the settlement and admin records are used** (feature classes P and A, SE+FI, as
the last step before giving up), contributing 785 SDHK charters at `confidence: low`.
The farm records are deliberately excluded: they were the source of the wrong answers —
`Lybæk` matching a Danish farm when the charter means Lübeck — and under the
coarse-over-precise rule an unverifiable farm-level point is not worth having.

## What is not in this repository, and how to get it back

The bulk source data is excluded — `digdag/` alone is 17 GB with single `.shp` files
over 2 GB, and GitHub caps files at 100 MB. Everything here is either our own work,
a derived dataset, or a small openly-licensed input. To rebuild from scratch:

| Excluded | Size | How to restore |
|---|---|---|
| `digdag/` | 17 GB | The DigDag shapefile release (RETSLIG, KIRKELIG, KOMMUNAL, AMTSLIG, GEOGRAFISK, OVRIGE, POLITIVAESEN). Needed only to re-run step 1. |
| `diplomatarium-danicum/` | 975 MB | `git clone https://github.com/dsldk/diplomatarium-danicum` |
| `external/geonames/` | 211 MB | `DataDock/geonames` on HuggingFace, snapshot folder, SE/NO/DK/FI/EE/IS + `alternatenames/` |
| `external/dn_letters.csv` | 59 MB | `gh api repos/Moryzont/SuperDiplomatarium/contents/_data/letters.csv -H "Accept: application/vnd.github.raw"` |
| `sdhk_2411.csv` | 48 MB | Riksarkivet SDHK export (cp1252, semicolon) |
| `swedish_charters_enriched.csv` | 15 MB | Riksarkivet SDHK subset with NER entities |
| `external/ygk/` | 8.5 MB | Zenodo 15118501 — transcriptions only, not used by the pipeline |

`external/aggk/` (TORA, CC-BY-4.0), `historical_maps/`, `df_platser.csv` and
`cleaned_gazetteers/` **are** included: small, openly licensed, and the pipeline needs
them. `external/PROVENANCE.md` records the exact source and licence of every input.

The derived data in `data/` is committed, so the map rebuilds with
`python3 build_map.py` without restoring anything.

## Licensing

No LICENSE in the DD repo; TEI headers mark `<availability status="restricted">` © DSL.
**Internal hackathon use only** — do not republish the derived corpus or deploy the map
publicly without clearing terms with DSL (`smb@dsl.dk`). `output/dd_map.html` embeds
charter abstracts, so the file itself is restricted material.
