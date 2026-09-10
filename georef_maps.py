#!/usr/bin/env python3
"""Georeference the historical maps and warp them into Web Mercator so Leaflet's
L.imageOverlay can lay them over the modern map.

Control points are read off the scans by eye (coast landmarks, islands). A 2nd
order polynomial in (lon, lat) -> (px, py) absorbs the projection plus the
engraver's distortion better than an affine or projective fit, which is the
point: these are not accurate maps and a rigid transform will not sit on them.

Output PNG is linear in Mercator x/y across its bounds, which is exactly what
L.imageOverlay assumes, so the bounds it is given place it correctly.
"""
import json, os, sys
import numpy as np
from PIL import Image

ROOT = '/home/pontus/dd_geo_map'
SRC = os.path.join(ROOT, 'historical_maps')
OUT = os.path.join(ROOT, 'output', 'overlays')
R = 6378137.0

def merc_y(lat):
    lat = np.clip(lat, -85.05, 85.05)
    return R * np.log(np.tan(np.pi/4 + np.radians(lat)/2))

def merc_x(lon):
    return R * np.radians(lon)

def inv_merc_y(y):
    return np.degrees(2*np.arctan(np.exp(y/R)) - np.pi/2)

def inv_merc_x(x):
    return np.degrees(x/R)

# --- control points: (lon, lat, px, py) --------------------------------------
MAPS = {
 'europe_blaeu': {
   'file': 'europe_1492.jpg',
   'title': 'Blaeu, Europa recens descripta (Amsterdam, c. 1640)',
   'points': [
     (-5.60, 35.95,  335, 1037),   # Strait of Gibraltar
     (-8.99, 37.02,  180,  978),   # Cabo de Sao Vicente
     ( 3.00, 39.60,  782,  978),   # Mallorca
     ( 9.00, 40.10, 1020,  980),   # Sardinia
     ( 9.10, 42.15, 1012,  900),   # Corsica
     (14.20, 37.60, 1125, 1005),   # Sicily
     (-5.72, 50.07,  425,  622),   # Land's End
     ( 1.50, 51.00,  550,  632),   # Strait of Dover
     (10.63, 57.74,  752,  472),   # Skagen (N tip of Jutland)
     (18.50, 57.50,  965,  325),   # Gotland
     (24.90, 35.20, 1240, 1048),   # Crete
     (33.40, 35.10, 1435,  980),   # Cyprus
     (-19.0, 64.90,  400,  100),   # Iceland
   ],
   'bounds': (-15.0, 34.5, 36.0, 66.0),   # lon_min, lat_min, lon_max, lat_max
 },
 'carta_marina': {
   'file': 'carta_marina.jpeg',
   'title': 'Olaus Magnus, Carta Marina (Venice, 1539)',
   # Read off the sheet by name: Olaus labels his towns, so the control points
   # are the labels themselves. Note this is a 1539 map with real distortion -
   # the fit is loose by construction and the overlay is decorative, not survey.
   'points': [
     ( 8.77, 55.33, 1885, 3160),   # Ripe (Ribe)
     (12.08, 55.64, 2415, 3145),   # Roskild
     (12.57, 55.68, 2465, 3110),   # Hafnia (Copenhagen)
     (13.20, 55.70, 2620, 3100),   # Lundia
     (10.40, 55.30, 2210, 3115),   # Fionia (Fyn)
     (11.48, 54.77, 2360, 3215),   # Lalandia (Lolland)
     ( 9.80, 54.10, 1980, 3330),   # Holsatia
     (18.50, 57.50, 3060, 3000),   # Gotlandia
     (16.36, 56.66, 2860, 3095),   # Calmar
     (18.07, 59.33, 2960, 2600),   # Holmia (Stockholm)
     ( 7.05, 57.98, 1970, 2650),   # Lindesnes
     (10.41, 59.27, 2110, 2555),   # Tonsberg
     (13.30, 58.90, 2430, 2710),   # Lacus Vener (Vanern)
     (22.27, 60.45, 3695, 2107),   # Finlandia / Abo
     (24.10, 56.95, 4113, 3010),   # Livonia / Riga
     ( 5.32, 60.39, 2023, 2073),   # Norvegia / Bergen
     (25.80, 71.20, 3026,  485),   # Finmarchia / North Cape
   ],
   'bounds': (2.0, 52.0, 32.0, 71.0),
   'lam': 50.0,      # heavier smoothing: the source is genuinely inconsistent
 },
}

def fit(points, order=2):
    """Least-squares polynomial (lon,lat) -> (px,py)."""
    P = np.array(points, float)
    lon, lat, px, py = P[:,0], P[:,1], P[:,2], P[:,3]
    A = design(lon, lat, order)
    cx, *_ = np.linalg.lstsq(A, px, rcond=None)
    cy, *_ = np.linalg.lstsq(A, py, rcond=None)
    rx = A @ cx - px
    ry = A @ cy - py
    rms = float(np.sqrt(np.mean(rx**2 + ry**2)))
    return cx, cy, rms

def fit_projective(points):
    """Homography (lon,lat)->(px,py). 8 dof, stable inside the frame - unlike a
    cubic polynomial, which fits these points better but spirals off outside
    their convex hull."""
    P = np.array(points, float)
    u, v, X, Y = P[:,0], P[:,1], P[:,2], P[:,3]
    n = len(P); A = np.zeros((2*n, 8)); b = np.zeros(2*n)
    A[0::2] = np.column_stack([u, v, np.ones(n), np.zeros((n,3)), -X*u, -X*v])
    A[1::2] = np.column_stack([np.zeros((n,3)), u, v, np.ones(n), -Y*u, -Y*v])
    b[0::2] = X; b[1::2] = Y
    h, *_ = np.linalg.lstsq(A, b, rcond=None)
    H = np.append(h, 1.0).reshape(3,3)
    return H

def apply_projective(H, lon, lat):
    d = H[2,0]*lon + H[2,1]*lat + H[2,2]
    return ((H[0,0]*lon + H[0,1]*lat + H[0,2]) / d,
            (H[1,0]*lon + H[1,1]*lat + H[1,2]) / d)

def _tps_U(r2):
    out = np.zeros_like(r2)
    nz = r2 > 1e-12
    out[nz] = r2[nz] * np.log(np.sqrt(r2[nz]))
    return out

def fit_tps(points, lam=0.0):
    """Thin-plate spline. Interpolates the control points; away from them the
    affine part dominates, so it degrades gracefully instead of exploding."""
    P = np.array(points, float)
    c = P[:, :2]; n = len(P)
    r2 = ((c[:,None,:] - c[None,:,:])**2).sum(-1)
    K = _tps_U(r2) + lam*np.eye(n)
    Pm = np.column_stack([np.ones(n), c])
    L = np.zeros((n+3, n+3))
    L[:n,:n] = K; L[:n,n:] = Pm; L[n:,:n] = Pm.T
    W = []
    for col in (2,3):
        rhs = np.concatenate([P[:,col], np.zeros(3)])
        W.append(np.linalg.lstsq(L, rhs, rcond=None)[0])
    return c, np.array(W)

def apply_tps(model, lon, lat):
    c, W = model
    pts = np.column_stack([lon.ravel(), lat.ravel()])
    out = []
    CH = 200000
    res = [np.empty(len(pts)), np.empty(len(pts))]
    for i in range(0, len(pts), CH):
        blk = pts[i:i+CH]
        r2 = ((blk[:,None,:] - c[None,:,:])**2).sum(-1)
        U = _tps_U(r2)
        A = np.column_stack([U, np.ones(len(blk)), blk])
        res[0][i:i+CH] = A @ W[0]
        res[1][i:i+CH] = A @ W[1]
    return res[0].reshape(lon.shape), res[1].reshape(lon.shape)

def design(lon, lat, order):
    cols = [np.ones_like(lon), lon, lat]
    if order >= 2:
        cols += [lon*lon, lon*lat, lat*lat]
    if order >= 3:
        cols += [lon**3, lon**2*lat, lon*lat**2, lat**3]
    return np.column_stack(cols)

def warp(name, spec, width=2000, order=3):
    im = Image.open(os.path.join(SRC, spec['file'])).convert('RGBA')
    src = np.asarray(im)
    H0, W0 = src.shape[:2]
    method = spec.get('method', 'tps')
    if method == 'tps':
        model = fit_tps(spec['points'], spec.get('lam', 10.0))
        P = np.array(spec['points'], float)
        tx, ty = apply_tps(model, P[:,0].copy(), P[:,1].copy())
        rms = float(np.sqrt(np.mean((tx-P[:,2])**2 + (ty-P[:,3])**2)))
    else:
        cx, cy, rms = fit(spec['points'], order)
    lon0, lat0, lon1, lat1 = spec['bounds']

    mx0, mx1 = merc_x(lon0), merc_x(lon1)
    my0, my1 = merc_y(lat0), merc_y(lat1)
    height = int(round(width * (my1-my0) / (mx1-mx0)))

    # output pixel centres -> mercator -> lon/lat -> source pixel
    xs = mx0 + (np.arange(width) + 0.5) / width * (mx1-mx0)
    ys = my1 - (np.arange(height) + 0.5) / height * (my1-my0)
    LON = inv_merc_x(xs)[None, :].repeat(height, 0)
    LAT = inv_merc_y(ys)[:, None].repeat(width, 1)
    if method == 'tps':
        sx, sy = apply_tps(model, LON, LAT)
    else:
        A = design(LON.ravel(), LAT.ravel(), order)
        sx = (A @ cx).reshape(height, width)
        sy = (A @ cy).reshape(height, width)

    xi = np.clip(np.round(sx).astype(int), 0, W0-1)
    yi = np.clip(np.round(sy).astype(int), 0, H0-1)
    out = src[yi, xi]
    inside = (sx >= 0) & (sx < W0) & (sy >= 0) & (sy < H0)
    out[..., 3] = np.where(inside, 255, 0)

    img = Image.fromarray(out)
    p = os.path.join(OUT, f'{name}.png')
    img.save(p, optimize=True)
    # WebP too: it is ~5x smaller with identical alpha, and build_map.py inlines
    # it as a data: URI so the finished page has no external file dependencies.
    wp = os.path.join(OUT, f'{name}.webp')
    img.save(wp, 'WEBP', quality=88, method=5)
    return p, rms, (lat0, lon0, lat1, lon1), (width, height), method

def main():
    meta = {}
    for name, spec in MAPS.items():
        p, rms, bounds, size, method = warp(name, spec)
        meta[name] = {'file': os.path.basename(p),
                      'webp': os.path.basename(p).replace('.png', '.webp'),
                      'title': spec['title'], 'method': method,
                      'bounds': [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
                      'rms_px': round(rms, 1), 'size': size,
                      'n_points': len(spec['points'])}
        print(f'{name}: {size[0]}x{size[1]}  fit RMS {rms:.1f}px over '
              f'{len(spec["points"])} control points ({method})  -> '
              f'png {os.path.getsize(p)/1e6:.1f} MB / '
              f'webp {os.path.getsize(p.replace(".png",".webp"))/1e6:.1f} MB')
    json.dump(meta, open(os.path.join(OUT, 'overlays.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
