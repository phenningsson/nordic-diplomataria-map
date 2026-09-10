# External sources

## `dn_letters.csv` — Diplomatarium Norvegicum

- Source: `Moryzont/SuperDiplomatarium`, path `_data/letters.csv` (fetched 2026-09-09)
- Site: https://moryzont.github.io/SuperDiplomatarium/
- **Licence: NONE.** The repo carries no LICENSE file and the README is a single
  heading. The author states the data was scraped from the Diplomatarium Norvegicum
  web edition. **Ask the author before reusing or redistributing.** Treat exactly
  like the DD corpus: internal use, do not republish.
- 25,011 records; 19,561 (78.2%) already carry `lat`/`lon`; years 1018–1727.
- Columns: `SD_ID, DN_REF, RN_REF, sammendrag, regest, DN_source, RN_source,
  DN_dato, RN_dato, date_start, date_end, DN_sted, RN_sted, Normalized_name,
  lat, lon, uncertain_loc, brevtekst, fotnoter_DN, fotnoter_RN, Tillegg`
- Maps onto our schema: `DN_sted` → `issue_place_raw`, `Normalized_name` →
  `place_name`, `lat`/`lon` → `lat`/`lon`, `uncertain_loc` → `confidence`,
  `date_start` → `date`. Their null placeholder is `[No_loc]` (945 rows), the
  analogue of our `empty`/`nil`.

## `superdiplomatarium_map.js`

Their Leaflet map code, kept for reference. Same repo, same licence caveat.

## `df_fennicum.json` — Diplomatarium Fennicum

- Source: https://huggingface.co/datasets/Kansallisarkisto/Diplomatarium-Fennicum
  (`diplomatarium-fennicum.json`, fetched 2026-09-10)
- Database: https://df.narc.fi/ — National Archives of Finland
- **Licence: CC0-1.0** (public domain). The only corpus here without reuse restrictions.
- 6,876 records. Fields: `df` (id), `dating_start_year`, `dating_end_year`,
  `issuingplace`, `issuingplacecountry`, `language`, `indexterm`, `transcript`.
- Coordinates come from `df_platser.csv` (the DF place register, 484 entries with
  lat/lon); 99.5% of issuing places join by name.
- Per-charter permalink: `https://df.narc.fi/document/<df>` — verified against
  indexed pages (DF 344, DF 5763, DF 41111).

## `geonames/` — GeoNames Nordic extracts

- Source: HuggingFace mirror `DataDock/geonames`, snapshot **2026-09-01**
  (`https://huggingface.co/datasets/DataDock/geonames`), which republishes the
  official per-country dumps. **Licence: CC-BY-4.0** (GeoNames' own terms).
- Fetched via the mirror because `download.geonames.org` is blocked by the
  Riksarkivet web filter on this network; the mirror is byte-identical in content.
- Countries: SE, NO, DK, FI, EE, IS — main files plus `alternatenames`.
  1.30 M main rows, 1.68 M alternate names; 288,260 rows in feature classes
  P (populated), A (admin), S (spot/building), 314,930 distinct normalised names.
- Column order (tab-separated, no header): geonameid, name, asciiname,
  alternatenames, lat, lon, feature class, feature code, country, cc2,
  admin1-4, population, elevation, dem, timezone, modified.
- **Not yet wired into the resolver** — see README for the measured trade-off.

## `aggk/` — Äldre geometriska kartorna (with TORA identifiers + coordinates)

- Source: Zenodo record 15121019, *Data from the project "Nationalutgåva av de äldre
  geometriska kartorna", 1630–1655*, v5 (2025-04-01), ed. Olof Karsvall; data collected
  by Riksarkivet and Isof. Found via `sok.riksarkivet.se/data-api`.
- **Licence: CC-BY-4.0.**
- Fetched through a headless browser: Zenodo returns 403 to plain HTTP clients here.
- Files taken (of 41): `Basic_settlement_unit_v1.0.csv`,
  `Place_and_personal_names_v1.1.csv`, `Map_object-cadastral_farm_unit_v1.0.csv`,
  `Map_object-church_v1.0.csv`, `Basic_cadastral_unit_v1.0.csv`,
  `Map_object-ancient_monument_v1.0.csv`.
- **This is the practical route to TORA.** `Basic_settlement_unit_v1.0.csv` has 12,206
  settlement units with `toraid`, `tora_prefLabel`, `tora_altLabel`, `parish`,
  `hundred` (härad), `tora_province`, `tora_wgs84_lat/long` and `toraid_url`
  (`https://sok.riksarkivet.se/topografi/<id>`). 11,926 (97.7%) carry coordinates,
  11,266 of them flagged `high` accuracy.
- `Place_and_personal_names_v1.1.csv`: 46,461 names (29,931 `bebyggelsenamn`,
  4,700 `ägonamn`, 4,395 `naturnamn`, 5,927 personal names), 35,758 with coordinates.
- **Watch the decimal separator**: `Basic_settlement_unit` uses `.`,
  `Place_and_personal_names` uses `,` (e.g. `57,768`). Parse both.
- Coverage is the provinces surveyed by the 1630–55 maps: Uppland, Östergötland,
  Västergötland, Södermanland, Småland, Värmland, Västmanland, then thin. **No Skåne,
  Halland or Blekinge** (Danish in period), little Norrland, no Finland.

## `ygk/` — Yngre geometriska kartor 1680–1700

- Source: Zenodo record 15118501, same editor (Olof Karsvall), CC-BY-4.0, v1 2025-04-01.
- **Transcriptions only.** One file, 6,533 HTML pages across 47 volumes of map text.
  No `toraid`, no coordinates, no CSV tables — unlike the 1630–55 record.
- Useful as evidence that a name existed on a 1680–1700 map, not as a gazetteer.
  Not wired into the resolver.
