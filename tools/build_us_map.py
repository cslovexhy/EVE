#!/usr/bin/env python3
"""EVE - Build the visual US states map data file.

Reads a public-domain per-state US GeoJSON (lon/lat polygons) and bakes a
compact, game-ready file: for each lower-48 state (+ DC) it stores a simplified
polygon and centroid in NORMALIZED 0..1 canvas coordinates (equirectangular
projection), the two-letter abbreviation, plus a static state-adjacency table.

The renderer just scales the 0..1 coords into whatever on-screen rect it wants,
so the projection math lives here, once, offline.

Usage:
    python3 tools/build_us_map.py [path_to_us-states.json]

Input GeoJSON: PublicaMundi/MappingAPI us-states.json (census-derived, public
domain). Download once to data/raw/us-states.geojson or pass a path.

Output: data/us_states_map.json
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "data", "us_states_map.json")
DEFAULT_IN = os.path.join(HERE, "..", "data", "raw", "us-states.geojson")

# Non-contiguous / territories to drop (they'd distort a flat projection).
EXCLUDE = {"Alaska", "Hawaii", "Puerto Rico"}

STATE_ABBREV = {
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

# Static lower-48 (+DC) shared-border adjacency. Symmetric; used for unlock
# gating (a state unlocks when any neighbour is >= the control threshold).
ADJACENCY = {
    "AL": ["FL", "GA", "MS", "TN"],
    "AZ": ["CA", "CO", "NM", "NV", "UT"],
    "AR": ["LA", "MO", "MS", "OK", "TN", "TX"],
    "CA": ["AZ", "NV", "OR"],
    "CO": ["AZ", "KS", "NE", "NM", "OK", "UT", "WY"],
    "CT": ["MA", "NY", "RI"],
    "DE": ["MD", "NJ", "PA"],
    "DC": ["MD", "VA"],
    "FL": ["AL", "GA"],
    "GA": ["AL", "FL", "NC", "SC", "TN"],
    "ID": ["MT", "NV", "OR", "UT", "WA", "WY"],
    "IL": ["IN", "IA", "KY", "MO", "WI"],
    "IN": ["IL", "KY", "MI", "OH"],
    "IA": ["IL", "MN", "MO", "NE", "SD", "WI"],
    "KS": ["CO", "MO", "NE", "OK"],
    "KY": ["IL", "IN", "MO", "OH", "TN", "VA", "WV"],
    "LA": ["AR", "MS", "TX"],
    "ME": ["NH"],
    "MD": ["DC", "DE", "PA", "VA", "WV"],
    "MA": ["CT", "NH", "NY", "RI", "VT"],
    "MI": ["IN", "OH", "WI"],
    "MN": ["IA", "ND", "SD", "WI"],
    "MS": ["AL", "AR", "LA", "TN"],
    "MO": ["AR", "IL", "IA", "KS", "KY", "NE", "OK", "TN"],
    "MT": ["ID", "ND", "SD", "WY"],
    "NE": ["CO", "IA", "KS", "MO", "SD", "WY"],
    "NV": ["AZ", "CA", "ID", "OR", "UT"],
    "NH": ["MA", "ME", "VT"],
    "NJ": ["DE", "NY", "PA"],
    "NM": ["AZ", "CO", "OK", "TX", "UT"],
    "NY": ["CT", "MA", "NJ", "PA", "VT"],
    "NC": ["GA", "SC", "TN", "VA"],
    "ND": ["MN", "MT", "SD"],
    "OH": ["IN", "KY", "MI", "PA", "WV"],
    "OK": ["AR", "CO", "KS", "MO", "NM", "TX"],
    "OR": ["CA", "ID", "NV", "WA"],
    "PA": ["DE", "MD", "NJ", "NY", "OH", "WV"],
    "RI": ["CT", "MA"],
    "SC": ["GA", "NC"],
    "SD": ["IA", "MN", "MT", "ND", "NE", "WY"],
    "TN": ["AL", "AR", "GA", "KY", "MO", "MS", "NC", "VA"],
    "TX": ["AR", "LA", "NM", "OK"],
    "UT": ["AZ", "CO", "ID", "NM", "NV", "WY"],
    "VT": ["MA", "NH", "NY"],
    "VA": ["DC", "KY", "MD", "NC", "TN", "WV"],
    "WA": ["ID", "OR"],
    "WV": ["KY", "MD", "OH", "PA", "VA"],
    "WI": ["IA", "IL", "MI", "MN"],
    "WY": ["CO", "ID", "MT", "NE", "SD", "UT"],
}


def _largest_ring(geom):
    """Return the outer ring (list of [lon,lat]) of the largest polygon."""
    t = geom["type"]
    if t == "Polygon":
        rings = [geom["coordinates"][0]]
    elif t == "MultiPolygon":
        rings = [poly[0] for poly in geom["coordinates"]]
    else:
        return []
    # Largest by absolute shoelace area.
    def area(ring):
        s = 0.0
        for i in range(len(ring)):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % len(ring)]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0
    return max(rings, key=area) if rings else []


def _simplify(points, tol=0.12):
    """Cheap distance-based decimation: drop a point if it's within `tol`
    degrees of the last kept point. Keeps shape recognizable, cuts point count.
    tol is in lon/lat degrees."""
    if len(points) <= 4:
        return points
    out = [points[0]]
    for p in points[1:]:
        lx, ly = out[-1]
        if (p[0] - lx) ** 2 + (p[1] - ly) ** 2 >= tol * tol:
            out.append(p)
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def _centroid(points):
    """Polygon centroid (area-weighted). Falls back to vertex mean."""
    n = len(points)
    if n < 3:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return [sum(xs) / n, sum(ys) / n]
    a = cx = cy = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a *= 0.5
    if abs(a) < 1e-9:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return [sum(xs) / n, sum(ys) / n]
    return [cx / (6 * a), cy / (6 * a)]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    with open(src) as f:
        gj = json.load(f)

    # First pass: collect simplified lon/lat rings for included states.
    raw = {}
    for feat in gj["features"]:
        name = feat["properties"].get("name") or feat["properties"].get("NAME")
        if name in EXCLUDE or name not in STATE_ABBREV:
            continue
        ring = _largest_ring(feat["geometry"])
        if not ring:
            continue
        raw[STATE_ABBREV[name]] = _simplify(ring)

    # Compute global lon/lat bounds for an equirectangular projection into 0..1.
    all_pts = [p for ring in raw.values() for p in ring]
    min_lon = min(p[0] for p in all_pts)
    max_lon = max(p[0] for p in all_pts)
    min_lat = min(p[1] for p in all_pts)
    max_lat = max(p[1] for p in all_pts)
    span_lon = max_lon - min_lon
    span_lat = max_lat - min_lat

    def project(lon, lat):
        # x grows east, y grows south (screen convention); normalized 0..1.
        x = (lon - min_lon) / span_lon
        y = (max_lat - lat) / span_lat
        return [round(x, 4), round(y, 4)]

    states = {}
    for abbrev, ring in raw.items():
        poly = [project(lon, lat) for lon, lat in ring]
        cen = _centroid(ring)
        states[abbrev] = {
            "abbrev": abbrev,
            "polygon": poly,
            "centroid": project(cen[0], cen[1]),
        }

    out = {
        "projection": "equirectangular-normalized",
        "aspect": round(span_lon / span_lat, 4),  # width:height of the map box
        "states": states,
        "adjacency": ADJACENCY,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f)
    pts = sum(len(s["polygon"]) for s in states.values())
    print(f"Wrote {OUT}: {len(states)} states, {pts} polygon points, "
          f"aspect {out['aspect']}")


if __name__ == "__main__":
    main()
