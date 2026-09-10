# Getting TORA out of the SPARQL endpoint

Front end: `https://tora.entryscape.net/snorql/` (blocked by the Riksarkivet filter, so
it has to be run from a browser that can reach it).

Four small queries instead of one big one. Each is plain triple patterns and `OPTIONAL`
— **no `GROUP BY`, no `BIND`, no `COALESCE`, no `GROUP_CONCAT`** — because those are the
parts an endpoint is most likely to reject or time out on. Run whichever you can; the
loader joins whatever it finds.

Save each result as CSV into `external/tora/`, any filename.

---

## Query 1 — the units (the essential one)

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX geo:  <http://www.w3.org/2003/01/geo/wgs84_pos#>
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT ?unit ?name ?lat ?long ?district ?parish
WHERE {
  ?unit a tora:HistoricalSettlementUnit .
  ?unit skos:prefLabel ?name .
  OPTIONAL { ?unit geo:lat ?lat }
  OPTIONAL { ?unit geo:long ?long }
  OPTIONAL { ?unit tora:earlyModernDistrict ?district }
  OPTIONAL { ?unit tora:earlyModernParish ?parish }
}
```

If even that is too heavy, drop `?parish` and its `OPTIONAL` — **`?district` is the
column that matters**, since it is the härad and nothing else resolves `X häradsting`.

## Query 2 — district labels

`?district` above will most likely come back as a URI. This turns them into names, and
it is tiny (roughly one row per härad):

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT ?district ?districtName
WHERE {
  ?district a tora:EarlyModernDistrict .
  ?district skos:prefLabel ?districtName .
}
```

If query 1 returned readable names in `?district` rather than URIs, skip this one.

## Query 3 — parish labels

Same idea, same reason to skip:

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT ?parish ?parishName
WHERE {
  ?parish a tora:EarlyModernParish .
  ?parish skos:prefLabel ?parishName .
}
```

## Query 4 — alternative names (optional, but valuable)

One row per name, not concatenated — this is where medieval spellings live:

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT ?unit ?altname
WHERE {
  ?unit a tora:HistoricalSettlementUnit .
  ?unit skos:altLabel ?altname .
}
```

---

## If a query is capped or times out

Add paging, and **keep an `ORDER BY`** or the pages will overlap and silently drop rows:

```sparql
...
ORDER BY ?unit
LIMIT 10000
OFFSET 0
```

Then `OFFSET 10000`, `OFFSET 20000`, and so on until a page comes back empty. Separate
files are fine — the loader reads every CSV in the directory.

## Sanity check before the bulk run

Worth running once, to see what one unit actually carries:

```sparql
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT ?unit ?p ?o
WHERE {
  ?unit a tora:HistoricalSettlementUnit .
  ?unit ?p ?o .
}
LIMIT 60
```

And a count, so we know what a complete export should total:

```sparql
PREFIX tora: <https://data.riksarkivet.se/tora/schema/>

SELECT (COUNT(DISTINCT ?unit) AS ?units)
WHERE { ?unit a tora:HistoricalSettlementUnit }
```

---

## How the loader handles it

`tora.py` reads every CSV in `external/tora/`, sniffs the delimiter and matches headers
by substring, then joins the files:

- a file with a **name** column is treated as the unit table
- a two-column file mapping a **URI → label** is treated as a lookup and used to resolve
  `?district` / `?parish` URIs into names
- a file with `unit` + an **altname** column adds alternative spellings

Units with coordinates become points; units without still contribute their parish and
härad membership, which is enough to place a charter coarsely. Nothing needs renaming.
