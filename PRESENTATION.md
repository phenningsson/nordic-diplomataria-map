# Mapping the Nordic diplomataria — 5-minute talk

Budget: **4 slides, ~5 min**. Roughly 60s / 45s / 2 min / 45s, leaving slack.
Speak from the bold lines; the rest is backup if asked.

---

## Slide 1 — The idea (~60s)

### Mapping every charter's place of issue across the Nordic diplomataria

- Every Nordic country at this hackathon has a **diplomatarium** — a scholarly
  edition of its surviving medieval charters.
- A **charter** is a single legal document: a grant, a sale, a judgement, a
  privilege. It normally records **who**, **when**, and **where it was issued**.
- Those three fields make a charter corpus a dataset, not just a text.

| Diplomatarium | Country | Charters |
|---|---|---|
| Diplomatarium Danicum | Denmark | ~24,000 |
| Diplomatarium Norvegicum | Norway | ~25,000 |
| Svenskt Diplomatarium (SDHK) | Sweden | ~44,000 |
| Diplomatarium Fennicum | Finland | ~7,000 |
| **Together** | | **~100,000** |

- **Two thirds state where they were issued** — about 66,000 charters.
- The Nordic countries have also published **open, coordinate-bearing gazetteers**
  of historical places: **TORA** (Sweden), **DigDag** (Denmark), the
  **Diplomatarium Fennicum place register** (Finland).

> **The question: can we put all of them on one map, and watch it move through time?**

A shared spatial layer over corpora that have always been read nation by nation —
opening up questions like how scribal and chancery networks form, and how they cross
Nordic borders.

---

## Slide 2 — How (~45s)

Keep this deliberately light. Three steps and one honest caveat.

1. **Parse** each corpus to a common shape — id, year, place of issue, summary, link.
   Four different formats: TEI XML, CSV, JSON.
2. **Resolve** each place name to coordinates, in order of confidence:
   a curated table for the big recurring places → each country's own gazetteer →
   Wikidata → GeoNames.
3. **Map** it with Leaflet: one self-contained HTML file, time slider, corpus filters.

**The honest part — we do not always know exactly where.**
When a name is ambiguous we do not guess a point and we do not drop the charter.
We fall back to the **smallest unit we can be sure of** — the parish, or the
*härad* (hundred) — and **draw it hollow** so approximation is visible.

> A coarse location that is certainly right beats a precise one that might be wrong.

Result: **60,220 of 66,000 placed — 91%.** Everything unresolved is listed, not hidden.

---

## Slide 3 — The result (~2 min, the centrepiece)

### An interactive map of 60,220 Nordic charters, 789–1590

**Lead with the GIF**: cumulative play-through, all four corpora, 789 → 1590.
Say nothing for the first few seconds — let it run.

Then two or three live moments, no more:

1. **Avignon lights up.** Drag to ~1305–1380. The papal curia moves to Avignon and
   a cluster blooms in southern France across *all four* corpora at once.
   The single most legible "history happening" moment on the map.
2. **Filter by corpus.** Turn the four on and off. Denmark, Norway, Sweden and
   Finland each have a visibly different geography — and they overlap in Rome,
   Avignon and Lübeck.
3. **Click a dot.** Any Stockholm or Vadstena marker: real charters, real summaries,
   each linking straight back to the source edition.

**Optional flourish if the room is warm:** switch on the **historical basemap** —
Blaeu's 1640 map of Europe, or Olaus Magnus's 1539 *Carta Marina* — and let the
charters sit on a map their own scribes might have recognised.

**The finding to say out loud:** across ~60,000 Nordic charters, the three most
common places of issue are

| | | |
|---|---|---|
| **Stockholm** | 3,544 | |
| **Rome** | 3,165 | |
| **Avignon** | 2,620 | |

then Vadstena, Oslo, Bergen, Uppsala, Lund, Lübeck.

> Two of the three commonest places of issue in the Nordic charter record are in
> Italy and France. The Nordic middle ages were run, in part, from Avignon.

4,704 distinct places, 17 modern countries.

---

## Slide 4 — What it opens up (~45s)

**As a research instrument**

- **Scribal and chancery networks over time** — where documents are actually
  produced, and how those centres shift.
- **Cross-border comparison on one surface**, instead of four national silos.
- **The curia as a Nordic institution** — the sheer weight of Rome and Avignon is
  hard to see in a national edition and obvious on a shared map.

**Next**

- **Places mentioned**, not just places of issue — the corpora are already
  NER-tagged in places; that turns ~60,000 dots into hundreds of thousands.
- **Iceland** — Diplomatarium Islandicum has no machine-readable edition yet.
- **Finish the gazetteer coverage** — Scania, Halland and Blekinge were Danish in
  this period but sit in no Danish gazetteer, which is the largest remaining gap.

**Built in a day and a half. Every dataset used is openly licensed or
institutionally available; the pipeline is scripted end to end and rebuilds from
source in one command.**

---

## If you get asked

- **"How accurate is it?"** 91% of charters with a stated place are placed. Of those,
  99% are at a specific settlement; ~570 are deliberately coarse — a parish or härad
  centroid, drawn hollow. Unresolved names are listed in the sidebar rather than
  quietly dropped.
- **"What did you geocode with?"** Country gazetteers first — TORA, DigDag, the DF
  register — then Wikidata, then GeoNames, with a hand-curated table for the ~150
  places that recur most. Every row records which source placed it.
- **"Biggest surprise?"** How completely the papal curia dominates. Also how often the
  same place appears in all four corpora — these are not four separate geographies.
- **"Hardest part?"** Not the mapping — the names. `Konstanz` is the Romanian name of
  Constanța; `Holmis` reduces to a village in Turkey; `Torsö` exists in both Sweden and
  Denmark. Cross-language and cross-border false friends were the main source of error.
