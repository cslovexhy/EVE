#!/usr/bin/env python3
"""Build normalized EVE world data for one state from public datasets.

Joins four raw sources (downloaded into data/raw/) by FIPS county code:
  - BEA CAGDP2  : county GDP ("All industry total", LineCode=1), 2024
  - Census co-est2024 : county population (SUMLEV=050)
  - County Health Rankings 2024 : homicide rate /100k (safety proxy)
  - Census SUB-EST2024 : incorporated places -> primary county (SUMLEV=157)

Produces a Country > State > County > City tree where each region carries real
metrics plus derived, bounded game values:
  - reward     : money for taking a city (percentile of city GDP share)
  - difficulty : 0..1 (blend of county GDP + homicide percentiles) -> mob power

Virginia note: the 38 independent cities are county-equivalents (their own
FIPS). They become county nodes containing a single same-named city. Counties
with no incorporated places get one synthesized city named after the county.

Usage:
  python tools/build_world_data.py --state VA --out data/world/virginia.json
"""
import argparse
import csv
import json
import os
import sys

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

STATE_FIPS = {"VA": "51", "NV": "32", "CA": "06", "NY": "36", "TX": "48"}
STATE_NAME = {"VA": "Virginia", "NV": "Nevada", "CA": "California",
              "NY": "New York", "TX": "Texas"}

# Reward range (money) mapped across the state's cities by GDP percentile.
REWARD_MIN, REWARD_MAX = 150, 6000

# --- Power model ---------------------------------------------------------
# Each region has two opposing forces:
#   underworld_power = K_UNDERWORLD * crime_rate * population  (conquerable rival gangs)
#   police_power     = K_POLICE     * region_GDP              (raid boss; never conquered)
# crime_rate * population is proportional to the actual NUMBER of violent
# crimes (crime_rate is homicides per 100k), i.e. the real size of the local
# underworld. police scales with wealth (funding). Factors are tuned on
# Virginia so the median city's underworld power is ~100 and police power
# stays larger than underworld everywhere (VA: ratio min ~2.4x at the poorest
# violent town, ~35x median, up to ~400x in rich safe suburbs). Suppressed
# (too-few-to-report) counties use CRIME_FLOOR.
K_UNDERWORLD = 0.015
K_POLICE = 0.0358
CRIME_FLOOR = 3.0


def clean(s: str) -> str:
    return s.strip().strip('"').strip()


def load_county_gdp(state_fips: str) -> dict:
    """FIPS -> GDP in thousands of dollars (2024), for LineCode=1."""
    path = os.path.join(RAW, "CAGDP2__ALL_AREAS_2001_2024.csv")
    out = {}
    with open(path, encoding="latin-1") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) < 9:
                continue
            fips = clean(row[0])
            if len(fips) != 5 or not fips.startswith(state_fips):
                continue
            if clean(row[4]) != "1":  # All industry total
                continue
            val = clean(row[-1])  # 2024
            try:
                out[fips] = int(val)
            except ValueError:
                out[fips] = None  # (D) suppressed / (NA)
    return out


def load_county_pop(state_fips: str) -> dict:
    """FIPS -> (county_name, population 2024) for county-equivalents."""
    path = os.path.join(RAW, "co-est2024-alldata.csv")
    out = {}
    with open(path, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            if row["SUMLEV"] != "050" or row["STATE"] != state_fips:
                continue
            fips = row["STATE"] + row["COUNTY"]
            try:
                pop = int(row["POPESTIMATE2024"])
            except ValueError:
                pop = 0
            out[fips] = (row["CTYNAME"], pop)
    return out


def load_homicide(state_fips: str) -> dict:
    """FIPS -> homicide rate per 100k (float) or None."""
    path = os.path.join(RAW, "analytic_data2024.csv")
    out = {}
    with open(path, encoding="latin-1") as f:
        r = csv.reader(f)
        header = next(r)
        try:
            hi = header.index("Homicides raw value")
            fi = header.index("5-digit FIPS Code")
        except ValueError:
            return out
        for row in r:
            if len(row) <= hi:
                continue
            fips = row[fi].strip()
            if len(fips) != 5 or not fips.startswith(state_fips):
                continue
            v = row[hi].strip()
            try:
                out[fips] = float(v)
            except ValueError:
                out[fips] = None
    return out


def load_places(state_fips: str) -> dict:
    """FIPS(county) -> list of (place_name, pop). Incorporated places only,
    assigned to the county holding the largest population part (SUMLEV=157)."""
    path = os.path.join(RAW, "sub-est2024.csv")
    # place identity = (PLACE fips, NAME); track best (largest) county part.
    best = {}  # place_key -> (county_fips, pop, name)
    with open(path, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            if row["SUMLEV"] != "157" or row["STATE"] != state_fips:
                continue
            name = row["NAME"]
            if name.startswith("Balance of") or name.endswith("CDP"):
                continue
            if not (name.endswith(" city") or name.endswith(" town")):
                continue
            try:
                pop = int(row["POPESTIMATE2024"])
            except ValueError:
                pop = 0
            cfips = row["STATE"] + row["COUNTY"]
            key = row["PLACE"] + "|" + name
            if key not in best or pop > best[key][1]:
                best[key] = (cfips, pop, name)
    by_county = {}
    for cfips, pop, name in best.values():
        by_county.setdefault(cfips, []).append((name, pop))
    for lst in by_county.values():
        lst.sort(key=lambda x: -x[1])
    return by_county


def percentile_map(values):
    """Map each distinct value to its 0..1 percentile rank."""
    vs = sorted(v for v in values if v is not None)
    n = len(vs)
    if n <= 1:
        return {v: 0.5 for v in vs}
    return {v: i / (n - 1) for i, v in enumerate(vs)}


def build(state_abbr: str) -> dict:
    sf = STATE_FIPS[state_abbr]
    gdp = load_county_gdp(sf)
    pop = load_county_pop(sf)
    hom = load_homicide(sf)
    places = load_places(sf)

    # BEA folds some county-equivalents into "combination areas" (common in VA,
    # where independent cities are merged with a neighbouring county), leaving
    # the individual county's GDP absent. Estimate those from population x the
    # state's median GDP-per-capita (a reasonable, flagged fake).
    per_caps = [gdp[f] / pop[f][1] for f in pop
                if gdp.get(f) and pop[f][1]]
    per_caps.sort()
    median_pc = per_caps[len(per_caps) // 2] if per_caps else 0.0

    # Pass 1: resolve a GDP (real or estimated) for every county-equivalent.
    resolved = {}  # fips -> dict(name, pop, gdp, hom, estimated)
    for fips, (cname, cpop) in pop.items():
        cgdp = gdp.get(fips)
        estimated = False
        if not cgdp and cpop:
            cgdp = int(cpop * median_pc)
            estimated = True
        resolved[fips] = {"name": cname, "pop": cpop, "gdp": cgdp,
                          "hom": hom.get(fips), "estimated": estimated}

    # Percentiles across the (now complete) set.
    gdp_pct = percentile_map([r["gdp"] for r in resolved.values() if r["gdp"]])
    known_hom = sorted(r["hom"] for r in resolved.values() if r["hom"] is not None)
    hom_pct = percentile_map(known_hom)
    median_hom = known_hom[len(known_hom) // 2] if known_hom else 0.0

    # Pass 2: build county nodes + cities, collect city GDP for reward ranking.
    counties = {}
    tmp_cities = {}
    all_city_gdp = []
    for fips, r in resolved.items():
        cname, cpop, cgdp, chom = r["name"], r["pop"], r["gdp"], r["hom"]
        g_p = gdp_pct.get(cgdp, 0.5)
        h_p = hom_pct.get(chom, hom_pct.get(median_hom, 0.5)) if chom is not None \
            else hom_pct.get(median_hom, 0.5)
        difficulty = round(0.5 * g_p + 0.5 * h_p, 3)

        city_list = places.get(fips, [])
        if not city_list:
            leaf = cname.replace(" County", "").strip()
            city_list = [(leaf, cpop)]

        cities_out = []
        for cityname, citypop in city_list:
            share = (citypop / cpop) if cpop else 0.0
            citygdp = int(cgdp * share) if (cgdp and share) else 0
            all_city_gdp.append(citygdp)
            cities_out.append((cityname, citypop, citygdp))

        tmp_cities[cname] = cities_out
        counties[cname] = {
            "fips": fips,
            "gdp_thousands": cgdp,
            "gdp_estimated": r["estimated"],
            "population": cpop,
            "homicide_rate": chom,
            "difficulty": difficulty,
        }

    city_gdp_pct = percentile_map(all_city_gdp)
    for cname, cobj in counties.items():
        crime = cobj["homicide_rate"] if cobj["homicide_rate"] is not None else CRIME_FLOOR
        cdict = {}
        for cityname, citypop, citygdp in tmp_cities[cname]:
            pct = city_gdp_pct.get(citygdp, 0.0)
            reward = int(round(REWARD_MIN + (REWARD_MAX - REWARD_MIN) * pct))
            underworld = int(round(K_UNDERWORLD * crime * citypop))
            police = int(round(K_POLICE * citygdp))
            cdict[cityname] = {
                "population": citypop,
                "gdp_thousands": citygdp,
                "crime_rate": round(crime, 2),
                "reward": reward,
                "difficulty": cobj["difficulty"],
                "underworld_power": underworld,
                "police_power": police,
            }
        cobj["cities"] = cdict

    return {
        "country": "United States",
        "state": STATE_NAME[state_abbr],
        "state_fips": sf,
        "counties": counties,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="VA")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.state not in STATE_FIPS:
        sys.exit(f"Unknown state {args.state}; known: {sorted(STATE_FIPS)}")

    data = build(args.state)
    out = args.out or os.path.join(
        os.path.dirname(__file__), "..", "data", "world",
        STATE_NAME[args.state].lower().replace(" ", "_") + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, indent=2)

    counties = data["counties"]
    total_cities = sum(len(c["cities"]) for c in counties.values())
    indep = [n for n in counties if n.endswith(" city")]
    print(f"Wrote {out}")
    print(f"  counties/equivalents: {len(counties)}  (independent cities: {len(indep)})")
    print(f"  total cities/leaves : {total_cities}")


if __name__ == "__main__":
    main()
