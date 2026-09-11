# Nordic diplomataria — charter map

An interactive map of **60,220 medieval charters** from the four Nordic diplomataria,
placed by their stated place of issue and animated across **789–1590**.

![Charters across the Nordic world, 789–1590](docs/charter_map.gif)

Built in about a day and a half at a Nordic digital humanities hackathon.

## What it shows

Every Nordic country has a *diplomatarium* — a scholarly edition of its surviving
medieval charters. A charter is a single legal document (a grant, a sale, a judgement)
and usually records who issued it, when, and **where**. Those corpora have always been
read nation by nation; this puts all four on one surface.

| Diplomatarium | Country | Charters | With a stated place | Mapped |
|---|---|---:|---:|---:|
| Diplomatarium Danicum | Denmark | 23,894 | 12,585 | 10,862 |
| Diplomatarium Norvegicum | Norway | 25,011 | 16,324 | 16,319 |
| Svenskt Diplomatarium (SDHK) | Sweden | 44,264 | 32,586 | 28,499 |
| Diplomatarium Fennicum | Finland | 6,876 | 4,562 | 4,540 |
| **Total** | | **100,045** | **66,057** | **60,220** |

4,704 distinct places across 17 modern countries. The three commonest places of issue
across the whole Nordic charter record are **Stockholm** (3,544), **Rome** (3,165) and
**Avignon** (2,620) — two of the top three are in Italy and France.

## Using it

```bash
git clone https://github.com/phenningsson/nordic-diplomataria-map
```

Then open **`output/dd_map.html`** in a browser. It is one self-contained file, ~19 MB,
with no server and no dependencies — the historical map overlays are embedded in it.

- **Time slider** with play, and 25/50/100-year or cumulative windows
- **Corpus filter** — toggle any combination of the four
- **Popups** with the charter's summary and a link back to its source edition
- **Historical basemaps** — Blaeu's *Europa recens descripta* (c. 1640) and Olaus
  Magnus's *Carta Marina* (1539), georeferenced and toggleable
- **Hollow markers** mark approximate placements: where the exact settlement could not
  be identified, the charter sits at the centroid of its parish or *härad* rather than
  being guessed at or dropped

## Where the data comes from

| Corpus | Source | Licence |
|---|---|---|
| Diplomatarium Danicum | [dsldk/diplomatarium-danicum](https://github.com/dsldk/diplomatarium-danicum) | **No licence file**; TEI headers mark the material `restricted`, © Det Danske Sprog- og Litteraturselskab |
| Diplomatarium Norvegicum | [Moryzont/SuperDiplomatarium](https://github.com/Moryzont/SuperDiplomatarium) | **No licence file**; the author states the data was scraped from the DN web edition |
| Svenskt Diplomatarium (SDHK) | Riksarkivet | Riksarkivet terms |
| Diplomatarium Fennicum | [Kansallisarkisto/Diplomatarium-Fennicum](https://huggingface.co/datasets/Kansallisarkisto/Diplomatarium-Fennicum) | **CC0-1.0** |

Gazetteers used for geocoding: **DigDag** (Denmark), **TORA** via the *Äldre geometriska
kartorna* release ([Zenodo 15121019](https://zenodo.org/records/15121019), CC-BY-4.0),
the **Diplomatarium Fennicum place register**, **Wikidata** and **GeoNames**.

`external/PROVENANCE.md` records the exact origin and licence of every input.

> **Note on reuse.** Three of the four corpora are *publicly readable* but not *openly
> licensed* — only Diplomatarium Fennicum carries an open licence. `data/*.jsonl` and
> `output/dd_map.html` contain charter summaries from all four. Treat this repository as
> internal research material and clear terms with the rights holders before publishing
> anything derived from it. DSL's contact for Diplomatarium Danicum is `smb@dsl.dk`.

## How it was built

Four parsers normalise very different source formats (TEI XML, CSV, JSON) into a common
charter record; place names are resolved through a confidence-ordered chain of curated
tables, national gazetteers, Wikidata and GeoNames; the map is generated as a single
Leaflet page. **91% of charters with a stated place are placed.**

Full technical write-up, including the geocoding traps that cost the most time, is in
**[docs/PIPELINE.md](docs/PIPELINE.md)**. The bulk source data (17 GB of shapefiles) is
not committed — that file lists how to restore each input.
