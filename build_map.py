#!/usr/bin/env python3
"""Render output/dd_map.html - a self-contained Leaflet map of charter issue
places from Diplomatarium Danicum and Diplomatarium Norvegicum, 789-1590,
with a time slider and a corpus filter."""
import json, os, csv, collections, html

ROOT = '/home/pontus/dd_geo_map'
YMIN, YMAX = 789, 1590      # DD ends 1450 by construction; DN runs on to 1590

# Colour encodes corpus - the question the map now answers. Slots 1 and 2 of the
# validated categorical palette (all-pairs safe in both modes).
# key, full name, short label, data file, light hue, dark hue, marker dash
#
# Four categories on a map is an ALL-PAIRS problem (any two corpora can sit
# adjacent - Avignon carries all four). Brute-forcing the documented 8-slot
# palette, exactly two 4-hue subsets clear every all-pairs gate in both light
# and dark: blue+yellow+magenta+green and yellow+magenta+green+violet. The first
# is used here because it keeps DD's established blue. Worst all-pairs CVD is
# dE 6.9, which sits in the 6-8 band that is legal ONLY with secondary encoding,
# so each corpus also carries its own stroke dash and every table row is tagged.
CORPORA = [
    ('DD',   'Diplomatarium Danicum',    'Danicum',
     'data/charters_geocoded.jsonl',      '#2a78d6', '#3987e5', None),
    ('DN',   'Diplomatarium Norvegicum', 'Norvegicum',
     'data/dn_charters_geocoded.jsonl',   '#eda100', '#c98500', '5,3'),
    ('SDHK', 'Svenskt Diplomatarium (SDHK)', 'Suecanum',
     'data/sdhk_charters_geocoded.jsonl', '#e87ba4', '#d55181', '1,3'),
    ('DF',   'Diplomatarium Fennicum',   'Fennicum',
     'data/df_charters_geocoded.jsonl',   '#008300', '#008300', '7,2,1,2'),
]

def display_name(n):
    for suf in (' Municipality', ' Kommune', ' Parish', ' Sogn'):
        if n.endswith(suf):
            return n[:-len(suf)]
    return n

def load(path, corpus):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        if r.get('lat') is None or r.get('year') is None:
            continue
        if not (YMIN <= r['year'] <= YMAX):
            continue
        r['corpus'] = corpus
        out.append(r)
    return out

def main():
    loaded = {k: load(os.path.join(ROOT, path), k)
              for k, _, _, path, _, _, _ in CORPORA}
    allrows = [r for k, _, _, _, _, _, _ in CORPORA for r in loaded[k]]

    n_dd_total = sum(1 for _ in open(os.path.join(ROOT, 'data', 'charters.jsonl'),
                                     encoding='utf-8'))
    places, per_decade = {}, collections.Counter()
    for r in allrows:
        y, c = r['year'], r['corpus']
        per_decade[(c, y // 10 * 10)] += 1
        dnm = display_name(r['place_name'])
        # 'harad' means the charter is placed at the centroid of its hundred, not
        # at a located settlement - drawn hollow so approximate never reads as exact
        prec = r.get('precision') or 'point'
        k = (c, dnm, round(r['lat'], 5), round(r['lon'], 5))
        p = places.setdefault(k, {'n': dnm, 'la': round(r['lat'], 5),
                                  'lo': round(r['lon'], 5), 'c': c,
                                  'co': r.get('country') or '', 'p': prec, 'ch': []})
        cit = r.get('citation') or f'DD {r["id"]}'
        p['ch'].append([y, r['id'], (r.get('abstract') or '')[:180], cit])
    for p in places.values():
        p['ch'].sort(key=lambda x: x[0])
    # draw big first so small markers land on top and stay clickable
    P = sorted(places.values(), key=lambda p: -len(p['ch']))

    unres = list(csv.DictReader(open(os.path.join(ROOT, 'data',
                                                  'unresolved_places.csv'),
                                     encoding='utf-8')))
    keys = [k for k, _, _, _, _, _, _ in CORPORA]
    ovp = os.path.join(ROOT, 'output', 'overlays', 'overlays.json')
    overlays = json.load(open(ovp)) if os.path.exists(ovp) else {}
    # Inline each overlay as a data: URI. Referencing overlays/*.png by relative
    # path works when the page is served, but browsers differ on whether a
    # file:// page may pull in a sibling file, and this page is opened straight
    # off disk. Inlining removes the question entirely (CLAUDE.md asks for a
    # single self-contained file anyway). WebP keeps the cost to ~6 MB base64.
    import base64
    for k, v in list(overlays.items()):
        src = os.path.join(ROOT, 'output', 'overlays',
                           v.get('webp') or v['file'])
        if not os.path.exists(src):
            src = os.path.join(ROOT, 'output', 'overlays', v['file'])
        if not os.path.exists(src):
            print(f'  ! overlay image missing for {k}: {src}')
            overlays.pop(k); continue
        mime = 'image/webp' if src.endswith('.webp') else 'image/png'
        with open(src, 'rb') as f:
            v['data'] = (f'data:{mime};base64,'
                         + base64.b64encode(f.read()).decode('ascii'))
        v.pop('file', None); v.pop('webp', None)
        print(f'  inlined {k}: {os.path.getsize(src)/1e6:.1f} MB '
              f'-> {len(v["data"])/1e6:.1f} MB base64')
    ovbtns = ''.join(
        f'<button data-h="{k}">{html.escape(v["title"].split(",")[0])}</button>'
        for k, v in overlays.items())
    ovnote = ' &middot; '.join(
        f'{html.escape(v["title"])}' for v in overlays.values())

    sp = os.path.join(ROOT, 'data', 'sdhk_unresolved_places.csv')
    sunres = list(csv.DictReader(open(sp, encoding='utf-8'))) if os.path.exists(sp) else []
    decades = [[d] + [per_decade[(k, d)] for k in keys]
               for d in range(YMIN // 10 * 10, YMAX + 10, 10)]

    payload = json.dumps({'places': P, 'decades': decades,
                          'unresolved': [[r['issue_place_raw'], int(r['n_charters'])]
                                         for r in unres[:40]]},
                         ensure_ascii=False, separators=(',', ':'))
    cssvars = '\n'.join(f'  --c-{k}: {lt};' for k, _, _, _, lt, _, _ in CORPORA)
    cssdark = '\n'.join(f'    --c-{k}: {dk};' for k, _, _, _, _, dk, _ in CORPORA)
    legend = ''.join(
        f'<span class="lg" data-lg="{k}"><i style="background:var(--c-{k})"></i>'
        f'{html.escape(lab)}</span>'
        for k, lab, _, _, _, _, _ in CORPORA)
    statrows = ''.join(
        f'<div class="stat"><span><span class="dot" style="background:var(--c-{k})"></span>'
        f'{html.escape(short)}</span><b id="s-{k}">0</b></div>'
        for k, _, short, _, _, _, _ in CORPORA)
    corpbtns = ('<button data-c="all" class="on">All</button>' + ''.join(
        f'<button data-c="{k}">{html.escape(short)}</button>'
        for k, _, short, _, _, _, _ in CORPORA))
    covrows = ''.join(
        f'<div class="stat"><span>{k} mapped</span><b>{len(loaded[k]):,}</b></div>'
        for k, _, _, _, _, _, _ in CORPORA)

    tpl = r'''<!doctype html>
<html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nordic diplomataria &mdash; issue places 789&ndash;1590</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
:root{
  color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f2f1ee; --border:#dedcd5;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#77756e;
__CSSVARS__
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#232322; --border:#3a3a38;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#94938b;
__CSSDARK__
  }
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:var(--surface-1);color:var(--text-primary)}
#wrap{display:flex;height:100%}
#side{width:340px;flex:0 0 340px;background:var(--surface-2);border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow:hidden}
#side header{padding:18px 18px 12px}
h1{font-size:16px;margin:0 0 4px;letter-spacing:-.01em}
.sub{font-size:12px;color:var(--text-secondary);margin:0}
#side .body{overflow-y:auto;padding:0 18px 18px;flex:1}
h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-muted);
  margin:20px 0 8px;font-weight:600}
.stat{display:flex;justify-content:space-between;font-variant-numeric:tabular-nums;
  padding:3px 0;font-size:13px;color:var(--text-secondary)}
.stat b{color:var(--text-primary);font-weight:600}
.lg{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text-secondary);padding:3px 0}
.lg i{width:11px;height:11px;border-radius:50%;flex:0 0 11px;box-shadow:0 0 0 2px var(--surface-2)}
.lg.off{opacity:.32}
.lg.off i{filter:grayscale(1)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-weight:600;color:var(--text-muted);font-size:11px;
  text-transform:uppercase;letter-spacing:.05em;padding:4px 0;border-bottom:1px solid var(--border)}
td{padding:4px 0;border-bottom:1px solid var(--border);color:var(--text-secondary)}
td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--text-primary);font-weight:600}
td .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}
td .cx{font-size:10px;color:var(--text-muted);letter-spacing:.04em;margin-left:3px}
#main{flex:1;display:flex;flex-direction:column;min-width:0}
#map{flex:1;background:var(--surface-2)}
#ctl{border-top:1px solid var(--border);background:var(--surface-2);padding:12px 18px 14px}
.row{display:flex;align-items:center;gap:14px}
button{font:inherit;font-size:13px;padding:6px 14px;border-radius:6px;cursor:pointer;
  border:1px solid var(--border);background:var(--surface-1);color:var(--text-primary)}
button:hover{border-color:var(--text-muted)}
button.on{background:var(--text-primary);color:var(--surface-1);border-color:var(--text-primary)}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:6px;overflow:hidden}
.seg button{border:0;border-radius:0;padding:6px 12px;font-size:12.5px}
.seg button+button{border-left:1px solid var(--border)}
.seg.wrap{display:flex;flex-wrap:wrap;width:100%}
.seg.wrap button{flex:1 1 auto;white-space:nowrap}
.orow{display:flex;align-items:center;gap:10px;margin-top:9px;font-size:12px;color:var(--text-secondary)}
.orow input[type=range]{flex:1;accent-color:var(--c-DD)}
.orow input[type=checkbox]{accent-color:var(--c-DD);width:14px;height:14px;margin:0}
.seg button.on{background:var(--text-primary);color:var(--surface-1)}
input[type=range]{flex:1;accent-color:var(--c-DD);min-width:0}
select{font:inherit;font-size:13px;padding:5px 8px;border-radius:6px;border:1px solid var(--border);
  background:var(--surface-1);color:var(--text-primary)}
#yr{font-variant-numeric:tabular-nums;font-weight:600;font-size:20px;min-width:132px;letter-spacing:-.01em}
#spark{display:block;width:100%;height:46px;margin-bottom:6px}
.note{font-size:11.5px;color:var(--text-muted);line-height:1.45}
.leaflet-popup-content{margin:12px 14px;font-size:13px;max-height:290px;overflow-y:auto}
.leaflet-popup-content h3{margin:0 0 2px;font-size:14px}
.leaflet-popup-content .pm{color:#666;font-size:11.5px;margin:0 0 8px}
.leaflet-popup-content li{margin-bottom:9px;list-style:none}
.leaflet-popup-content ul{padding:0;margin:0}
.leaflet-popup-content a{color:#2a78d6;font-weight:600;text-decoration:none}
.leaflet-popup-content a:hover{text-decoration:underline}
.leaflet-popup-content .ab{color:#444;font-size:12px;line-height:1.4}
.leaflet-popup-content .yr{color:#666;font-variant-numeric:tabular-nums}
</style></head><body>
<div id="wrap">
 <aside id="side">
  <header>
    <h1>Nordic diplomataria</h1>
    <p class="sub">Where charters were issued, 789&ndash;1590</p>
  </header>
  <div class="body">
    <h2>In view</h2>
    <div class="stat"><span>Charters</span><b id="s-ch">0</b></div>
    <div class="stat"><span>Places</span><b id="s-pl">0</b></div>
__STATROWS__
    <h2>Corpus</h2>
    <div id="legend">__LEGEND__</div>
    <p class="note" style="margin-top:-2px" id="precnote"></p>
    <label class="orow" for="precsplit" style="cursor:pointer">
      <input type="checkbox" id="precsplit" checked>
      <span>Distinguish parish from härad</span></label>
    <h2>Historical basemap</h2>
    <span class="seg wrap" id="hist">
      <button data-h="off" class="on">Off</button>__OVBTNS__
    </span>
    <div class="orow"><label for="hop">Opacity</label>
      <input type="range" id="hop" min="0" max="100" value="70"></div>
    <p class="note" id="histerr"></p>
    <p class="note">Georeferenced by thin-plate spline from landmarks read off
      each sheet. The Blaeu fits closely; the 1539 Carta Marina does not and
      cannot &mdash; it is a decorative overlay, not a survey.</p>
    <h2>Top places in window</h2>
    <table><thead><tr><th>Place</th><th style="text-align:right">Charters</th></tr></thead>
      <tbody id="tbl"></tbody></table>
    <h2>Coverage</h2>
    <div class="stat"><span>DD parsed</span><b>__NDDTOTAL__</b></div>
__COVROWS__
    <p class="note">DD ends at 1450 by construction, so anything later is DN,
      SDHK and DF. DD, SDHK and DF link to the individual charter;
      <b>DN links go to the DN search page</b>, not the charter &mdash; see README.</p>
    <h2>Unresolved</h2>
    <p class="note">Not on the map: __NUNRES__ DD place strings
      (__NUNRESCH__ charters) and __NSUNRES__ SDHK strings (__NSUNRESCH__ charters).
      Largest DD:</p>
    <table><tbody id="unres"></tbody></table>
  </div>
 </aside>
 <div id="main">
  <div id="map"></div>
  <div id="ctl">
    <svg id="spark" aria-label="Charters per decade by corpus"></svg>
    <div class="row">
      <button id="play">&#9654;&nbsp; Play</button>
      <span id="yr"></span>
      <input type="range" id="slider" min="__YMIN__" max="__YMAX__" value="1400">
      <span class="seg" id="corp">__CORPBTNS__</span>
      <select id="win">
        <option value="25">25-year window</option>
        <option value="50" selected>50-year window</option>
        <option value="100">100-year window</option>
        <option value="0">Cumulative</option>
      </select>
    </div>
  </div>
 </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const DATA = __PAYLOAD__;
const YMIN = __YMIN__, YMAX = __YMAX__;
const DN_SEARCH = '__DNSEARCH__';
const CORPUS_NAME = __CORPUSNAME__;
const DASH = __DASH__;
const SDHK_URL = '__SDHKURL__';
const css = k => getComputedStyle(document.documentElement).getPropertyValue('--c-'+k).trim();
const KEYS = __KEYS__;
// Corpora are a set, not a single choice: each button toggles its own corpus in
// or out, and "All" selects everything.
let active = new Set(KEYS);
let splitPrecision = true;

// zoom 4 so the whole span fits on load: north Norway down to Rome, Avignon to Reval
const map = L.map('map', {worldCopyJump:false, minZoom:3}).setView([55.0, 12.0], 4);
const ATTR = 'data: Diplomatarium Danicum (DSL), Diplomatarium Norvegicum, '+
  'Svenskt Diplomatarium (SDHK), Diplomatarium Fennicum (CC0) &middot; internal use';
// Keyless OSM. Esri's free Canvas layer stamps "API KEY REQUIRED" on every tile.
let base = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {attribution:'&copy; OpenStreetMap contributors &middot; '+ATTR,
   subdomains:'abc', maxZoom:12}).addTo(map);
let tileErrs = 0, tileOk = 0, swapped = false;
base.on('tileload', () => { tileOk++; });
base.on('tileerror', () => {
  if (swapped || tileOk > 0 || ++tileErrs < 8) return;
  swapped = true; map.removeLayer(base);
  base = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    {attribution:'&copy; OpenStreetMap, &copy; CARTO &middot; '+ATTR,
     subdomains:'abcd', maxZoom:12}).addTo(map);
});
// historical overlays live in their own pane between the tiles (200) and the
// markers (400) so charters always stay on top of the old map
map.createPane('histPane');
map.getPane('histPane').style.zIndex = 250;
map.getPane('histPane').style.pointerEvents = 'none';
const HIST = __HIST__;
let histLayer = null, histKey = 'off';
function setHist(key){
  histKey = key;
  if (histLayer){ map.removeLayer(histLayer); histLayer = null; }
  if (key !== 'off' && HIST[key]){
    const h = HIST[key];
    histLayer = L.imageOverlay(h.data, h.bounds,
      {opacity: +document.getElementById('hop').value / 100,
       pane: 'histPane', interactive: false}).addTo(map);
    histLayer.on('error', () => {
      const n = document.getElementById('histerr');
      if (n) n.textContent = 'Overlay image failed to load.';
    });
  }
}
document.querySelectorAll('#hist button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#hist button').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); setHist(b.dataset.h);
});
document.getElementById('hop').oninput = e => {
  if (histLayer) histLayer.setOpacity(+e.target.value / 100);
};

const layer = L.layerGroup().addTo(map);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// DD and SDHK deep-link to the charter; DN can only reach its search page (README).
function charterUrl(corpus, year, id){
  if (corpus === 'DD')
    return `https://tekstnet.dk/books/dipdan/${String(year).padStart(4,'0')}/dd_${id}/`;
  if (corpus === 'SDHK') return SDHK_URL.replaceAll('{id}', id);
  if (corpus === 'DF') return 'https://df.narc.fi/document/' + id;
  return DN_SEARCH;
}

function render(){
  const win = +document.getElementById('win').value;
  const hi  = +document.getElementById('slider').value;
  const lo  = win ? hi - win : YMIN;
  document.getElementById('yr').textContent = win ? lo + '–' + hi : '≤ ' + hi;

  layer.clearLayers();
  let nch = 0, npl = 0; const per = {}; KEYS.forEach(k => per[k] = 0);
  const rows = [];
  for (const p of DATA.places){
    if (!active.has(p.c)) continue;
    const inw = p.ch.filter(c => c[0] > lo && c[0] <= hi);
    if (!inw.length) continue;
    nch += inw.length; npl++;
    per[p.c] += inw.length;
    rows.push([p, inw.length]);
    // the coarser the placement, the more transparent the mark, so certainty
    // is legible at a glance: solid = a located settlement, hollow = a hundred
    const approx = p.p === 'harad' || p.p === 'parish';
    const fillOp = !approx ? 0.72
                 : !splitPrecision ? 0.28
                 : p.p === 'harad' ? 0.16 : 0.40;
    L.circleMarker([p.la, p.lo], {
      radius: Math.max(4.5, Math.min(30, 3.6*Math.sqrt(inw.length))),
      color: approx ? css(p.c) : '#fff',
      weight: approx ? 2.5 : 2,
      opacity: .95,
      dashArray: approx ? '3,3' : (DASH[p.c] || null),
      fillColor: css(p.c),
      fillOpacity: fillOp
    }).addTo(layer).bindPopup(() => {
      const list = inw.slice(-14).reverse().map(c =>
        `<li><a href="${charterUrl(p.c, c[0], c[1])}" target="_blank" rel="noopener">${esc(c[3])}</a>
           <span class="yr">&middot; ${c[0]}</span>
           <div class="ab">${esc(c[2])}${c[2].length>=180?'…':''}</div></li>`).join('');
      const corpusName = CORPUS_NAME[p.c] || p.c;
      return `<h3>${esc(p.n)}</h3><p class="pm">${corpusName}${p.co?' &middot; '+esc(p.co):''}
        &middot; ${inw.length} charter${inw.length>1?'s':''} in ${win?lo+'–'+hi:'≤'+hi}
        ${inw.length>14?' &middot; latest 14':''}${approx
          ? '<br><b>Approximate</b> — placed at the centroid of this '
            + (splitPrecision ? (p.p === 'harad' ? 'härad (hundred)' : 'parish')
                              : (p.p === 'harad' ? 'härad' : 'parish'))
            + ', not at a located settlement.'
          : ''}</p><ul>${list}</ul>`;
    }, {maxWidth:340});
  }
  document.getElementById('s-ch').textContent = nch.toLocaleString();
  document.getElementById('s-pl').textContent = npl.toLocaleString();
  KEYS.forEach(k => document.getElementById('s-'+k).textContent = per[k].toLocaleString());

  rows.sort((a,b) => b[1]-a[1]);
  document.getElementById('tbl').innerHTML = rows.slice(0,12).map(([p,n]) =>
    `<tr><td><span class="dot" style="background:${css(p.c)}"></span>${esc(p.n)}${
      active.size > 1 ? ` <span class="cx">${p.c}</span>` : ''}</td>
     <td class="num">${n}</td></tr>`).join('') ||
    `<tr><td colspan="2" class="note">${active.size
        ? 'No charters in this window.'
        : 'No corpora selected — pick one above.'}</td></tr>`;
  drawSpark(lo, hi, win);
}

function drawSpark(lo, hi, win){
  const sv = document.getElementById('spark');
  const W = sv.clientWidth || 900, H = 46, PAD = 13;
  const val = d => KEYS.reduce((a,k,i) => a + (active.has(k) ? d[i+1] : 0), 0);
  const mx = Math.max(...DATA.decades.map(val)) || 1;
  const bw = W / DATA.decades.length;
  const muted = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim();
  sv.setAttribute('viewBox', `0 0 ${W} ${H}`);
  let out = '';
  for (const d of DATA.decades){
    const x = ((d[0]-YMIN)/10)*bw, on = win ? (d[0] > lo && d[0] <= hi) : d[0] <= hi;
    const w = Math.max(1, bw-1);
    // stacked: DD below, DN above, so the corpus mix stays readable over time
    let yb = H-PAD;
    for (const [key, v] of KEYS.map((k,i) => [k, d[i+1]])){
      if (!active.has(key)) continue;
      if (!v) continue;
      const h = Math.max(1, (v/mx)*(H-PAD-3));
      yb -= h;
      out += `<rect x="${x.toFixed(1)}" y="${yb.toFixed(1)}" width="${w.toFixed(1)}"
        height="${h.toFixed(1)}" fill="${on?css(key):muted}" opacity="${on?0.95:0.25}"
        ><title>${d[0]}s ${key}: ${v}</title></rect>`;
    }
  }
  out += [800,1000,1200,1400,1590].map(y =>
    `<text x="${Math.min(W-22,((y-YMIN)/10)*bw).toFixed(1)}" y="${H-1}" font-size="9.5"
      fill="${muted}" opacity=".85">${y}</text>`).join('');
  sv.innerHTML = out;
}

document.getElementById('unres').innerHTML = DATA.unresolved.map(([s,n]) =>
  `<tr><td>${esc(s)}</td><td class="num">${n}</td></tr>`).join('');

function paintCorpusButtons(){
  document.querySelectorAll('#corp button').forEach(b => {
    const c = b.dataset.c;
    b.classList.toggle('on', c === 'all' ? active.size === KEYS.length : active.has(c));
  });
  // grey out the legend entries for corpora that are switched off
  document.querySelectorAll('#legend .lg').forEach(e =>
    e.classList.toggle('off', !active.has(e.dataset.lg)));
}
document.querySelectorAll('#corp button').forEach(b => b.onclick = () => {
  const c = b.dataset.c;
  if (c === 'all'){
    // pressing All when everything is already on clears back to a single corpus
    active = (active.size === KEYS.length) ? new Set([KEYS[0]]) : new Set(KEYS);
  } else if (active.has(c)){
    active.delete(c);
  } else {
    active.add(c);
  }
  paintCorpusButtons(); render();
});
paintCorpusButtons();

const NOTE_SPLIT = 'Faded markers are <b>approximate</b>: placed at the centroid of a '
  + '<b>parish</b> (half-filled) or a <b>härad</b> (hollow) where the exact settlement '
  + 'could not be identified. A coarse location beats none at all.';
const NOTE_MERGED = 'Faded markers are <b>approximate</b>: placed at the centroid of the '
  + 'parish or härad the charter belongs to, where the exact settlement could not be '
  + 'identified. A coarse location beats none at all.';
function paintPrecNote(){
  document.getElementById('precnote').innerHTML = splitPrecision ? NOTE_SPLIT : NOTE_MERGED;
}
document.getElementById('precsplit').onchange = e => {
  splitPrecision = e.target.checked; paintPrecNote(); render();
};
paintPrecNote();

let timer = null;
const btn = document.getElementById('play'), sl = document.getElementById('slider');
btn.onclick = () => {
  if (timer){ clearInterval(timer); timer=null; btn.textContent='▶  Play'; btn.classList.remove('on'); return; }
  btn.textContent='■  Pause'; btn.classList.add('on');
  if (+sl.value >= YMAX) sl.value = YMIN;
  timer = setInterval(() => {
    sl.value = Math.min(YMAX, +sl.value + 5); render();
    if (+sl.value >= YMAX){ clearInterval(timer); timer=null;
      btn.textContent='▶  Play'; btn.classList.remove('on'); }
  }, 110);
};
sl.oninput = render;
document.getElementById('win').onchange = render;
addEventListener('resize', render);
render();
</script></body></html>'''

    out = (tpl.replace('__CSSVARS__', cssvars).replace('__CSSDARK__', cssdark)
              .replace('__LEGEND__', legend).replace('__PAYLOAD__', payload)
              .replace('__STATROWS__', statrows).replace('__COVROWS__', covrows)
              .replace('__CORPBTNS__', corpbtns)
              .replace('__KEYS__', json.dumps(keys))
              .replace('__OVBTNS__', ovbtns)
              .replace('__HIST__', json.dumps(overlays))
              .replace('__DASH__',
                       json.dumps({k: dash for k, _, _, _, _, _, dash in CORPORA}))
              .replace('__CORPUSNAME__',
                       json.dumps({k: lab for k, lab, _, _, _, _, _ in CORPORA}))
              .replace('__YMIN__', str(YMIN)).replace('__YMAX__', str(YMAX))
              .replace('__DNSEARCH__',
                       'https://www.dokpro.uio.no/dipl_norv/diplom_felt.html')
              .replace('__SDHKURL__',
                       'https://sok.riksarkivet.se/sdhk/{id}'
                       '?EndastDigitaliserat=false&SDHK={id}')
              .replace('__NDDTOTAL__', f'{n_dd_total:,}')
              .replace('__NUNRES__', f'{len(unres):,}')
              .replace('__NUNRESCH__',
                       f'{sum(int(r["n_charters"]) for r in unres):,}')
              .replace('__NSUNRES__', f'{len(sunres):,}')
              .replace('__NSUNRESCH__',
                       f'{sum(int(r["n_charters"]) for r in sunres):,}'))
    os.makedirs(os.path.join(ROOT, 'output'), exist_ok=True)
    p = os.path.join(ROOT, 'output', 'dd_map.html')
    open(p, 'w', encoding='utf-8').write(out)
    for k, lab, _, _, _, _, _ in CORPORA:
        print(f'{k:<5} mapped : {len(loaded[k]):>7,}  '
              f'({sum(1 for x in P if x["c"]==k):,} places)')
    print(f'total charters: {len(allrows):,}')
    print(f'place markers : {len(P):,}')
    print(f'wrote {p}  ({os.path.getsize(p)/1e6:.1f} MB)')

if __name__ == '__main__':
    main()
