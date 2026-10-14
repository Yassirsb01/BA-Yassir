"""
direction_distribution_test.py
================================
Checks the cluster-based heading selection (see japan_comparison, comment
block "Cluster-based heading selection after Geyer/Melzer/Duennweber").

Verified here:
  1. Heading distribution: the eight gaps of the former 45-degree grid
     must have disappeared.
  2. Comparison of old and new with IDENTICAL seeds: daily distance, net
     displacement, forest share, settlement share, mean terrain score.
  3. Runtime of a 24 h run.
  4. How many clusters are typically found.
  5. That NO network requests take place.

Run:  python tests/direction_distribution_test.py
"""

import os
import sys

# Script lives in a subdirectory; the application modules are one level up.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import math
import statistics
import time

import japan_comparison as jc
from terrain_cache import TerrainCache

N_RUNS = 160
HOURS = 24
SEED_BASE = 1000


# =========================================================
# Network lock (test 5)
# =========================================================
class NetworkUsed(AssertionError):
    pass


def block_network():
    """
    Turn every socket connection attempt into an error. Stricter than
    intercepting requests: an access that bypasses the library is caught
    as well.
    """
    import socket

    def _forbidden(*a, **k):
        raise NetworkUsed("A network connection was attempted.")

    socket.socket.connect = _forbidden
    socket.create_connection = _forbidden


# =========================================================
# Helpers
# =========================================================
def collect_headings(runs=N_RUNS, hours=HOURS):
    """Run simulations from real camera locations and record every chosen
    heading."""
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds

    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    tc = TerrainCache()

    headings = []
    original = jc.choose_weighted_direction

    def recording(*args, **kwargs):
        dest, direction = original(*args, **kwargs)
        headings.append(direction)
        return dest, direction

    jc.choose_weighted_direction = recording
    try:
        from datetime import datetime
        for i in range(runs):
            cam = cams[i % len(cams)]
            jc.simulate_free_path(
                start_lat=cam["lat"], start_lng=cam["lng"],
                start_time=datetime(2024, 6, 1, 20, 0),
                duration_hours=hours, gender="F", age="A", season="summer",
                bear_speeds=bs, seed=SEED_BASE + i, terrain_cache=tc,
            )
    finally:
        jc.choose_weighted_direction = original
    return headings


def count_in_former_gaps(headings):
    """Count how many headings fall into the previously unreachable bands:
    the old grid only allowed 45*i +/- 15 degrees."""
    in_gap = 0
    for d in headings:
        rest = d % 45.0
        # Reachable were only [0,15] and [30,45] of every 45-degree sector
        if 15.0 < rest < 30.0:
            in_gap += 1
    return in_gap


def histogram(headings, bins=24):
    width = 360.0 / bins
    h = [0] * bins
    for d in headings:
        h[min(bins - 1, int(d / width))] += 1
    return h


def path_metrics(path, tc):
    """Distance, forest and settlement share, and mean score of one path."""
    from geopy.distance import geodesic
    distance = 0.0
    for a, b in zip(path, path[1:]):
        distance += geodesic((a["lat"], a["lng"]), (b["lat"], b["lng"])).meters

    # Settlement is recorded SEPARATELY on purpose: "landuse=residential"
    # is a built-up residential area, "highway=residential" only a
    # residential street. Combining both with OR massively overstated the
    # settlement share, because in this area almost every cell carries
    # some kind of road (see ANPASSUNGEN.md, item 5).
    forest = residential_area = residential_street = 0
    scores = []
    for p in path:
        f = tc.get_features(p["lat"], p["lng"], radius=150)
        if f.get("landuse=forest") or f.get("natural=wood") or f.get("forest") or f.get("wood"):
            forest += 1
        if f.get("landuse=residential"):
            residential_area += 1
        if f.get("highway=residential"):
            residential_street += 1
        scores.append(jc._score_terrain(f))
    n = max(1, len(path))

    # Net displacement: straight line from start to end. The daily
    # distance (the sum of step lengths) is unsuitable as a comparison
    # measure, because it follows from the speed table alone and does not
    # depend on heading selection at all; it is identical in every
    # variant. Only the net displacement shows whether the bear travels
    # purposefully or wanders.
    net = geodesic((path[0]["lat"], path[0]["lng"]),
                   (path[-1]["lat"], path[-1]["lng"])).meters if len(path) > 1 else 0.0
    return {
        "distance_m": distance,
        "net_m": net,
        "forest_pct": forest / n * 100,
        "residential_area_pct": residential_area / n * 100,
        "residential_street_pct": residential_street / n * 100,
        "score": statistics.mean(scores) if scores else 0.0,
    }


def legacy_heading_selection(current, step_length_m, rng, terrain_cache=None,
                             prev_direction=None, persistence_weight=None,
                             num_candidates=8, query_radius_m=150,
                             terrain_perception_m=None, selection_beta=None,
                             terrain_samples=None, cluster_attraction=None):
    """
    Verbatim copy of the heading selection BEFORE the change: eight fixed
    sectors with only +/-15 degrees of jitter, scored exclusively at the
    perception point. Serves as an honest before-reference in the
    comparison and is used only by this test, never by production code.
    """
    from GeoToolBox import GeoToolBox
    persistence_weight = jc.DEFAULT_PERSISTENCE_WEIGHT if persistence_weight is None else persistence_weight
    terrain_perception_m = jc.DEFAULT_TERRAIN_PERCEPTION_M if terrain_perception_m is None else terrain_perception_m
    selection_beta = jc.SELECTION_BETA if selection_beta is None else selection_beta

    candidates = []
    for i in range(num_candidates):
        base_angle = (360.0 / num_candidates) * i
        direction = (base_angle + rng.uniform(-15, 15)) % 360
        score = 0.0
        dest = GeoToolBox.destination_point(current, direction, step_length_m)
        if terrain_cache is not None:
            look_ahead = max(step_length_m, terrain_perception_m)
            pp = GeoToolBox.destination_point(current, direction, look_ahead)
            score += jc._score_terrain(terrain_cache.get_features(pp[0], pp[1], radius=query_radius_m))
        if prev_direction is not None:
            score += persistence_weight * math.cos(math.radians(
                jc._angular_diff_deg(direction, prev_direction)))
        candidates.append((dest, direction, score))
    scores = [c[2] for c in candidates]
    mx = max(scores)
    weights = [math.exp(selection_beta * (s - mx)) for s in scores]
    d, dirn, _ = rng.choices(candidates, weights=weights, k=1)[0]
    return d, dirn


def run_metrics(runs, hours, clusters_on):
    """Run simulations and average the metrics. clusters_on=False disables
    the cluster candidates, which reproduces the earlier candidate
    generation while keeping the rest of the code and the seeds
    identical."""
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    from datetime import datetime

    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    tc = TerrainCache()

    original_clusters = jc._terrain_clusters
    if not clusters_on:
        jc._terrain_clusters = lambda *a, **k: []

    results = []
    t0 = time.time()
    try:
        for i in range(runs):
            cam = cams[i % len(cams)]
            path = jc.simulate_free_path(
                start_lat=cam["lat"], start_lng=cam["lng"],
                start_time=datetime(2024, 6, 1, 20, 0),
                duration_hours=hours, gender="F", age="A", season="summer",
                bear_speeds=bs, seed=SEED_BASE + i, terrain_cache=tc,
            )
            results.append(path_metrics(path, tc))
    finally:
        jc._terrain_clusters = original_clusters
    elapsed = time.time() - t0

    out = {k: statistics.mean(e[k] for e in results)
           for k in ("distance_m", "net_m", "forest_pct",
                     "residential_area_pct", "residential_street_pct", "score")}
    out["seconds_per_run"] = elapsed / max(1, runs)
    return out


# =========================================================
# Entry point
# =========================================================
def main():
    block_network()
    print("Network blocked; every connection attempt raises an error.\n")

    tc = TerrainCache()
    print(f"Terrain cache usable: {not tc.disabled}, prefetch regions: {len(tc._regions)}\n")

    # ---- Test 4: number of clusters ------------------------------
    print("=" * 66)
    print("TEST 4: how many clusters are found?")
    print("=" * 66)
    cams = jc.load_japan_cameras()
    at_cameras = [len(jc._terrain_clusters((c["lat"], c["lng"]), tc)) for c in cams]
    print(f"  at the {len(cams)} camera locations: "
          f"median {statistics.median(at_cameras):.1f}, max {max(at_cameras)}, "
          f"without any cluster {sum(1 for x in at_cameras if x == 0)}")

    # Along real simulated paths, which is more informative than the
    # starting points alone.
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    from datetime import datetime
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    along_paths = []
    for i in range(20):
        cam = cams[i % len(cams)]
        path = jc.simulate_free_path(
            start_lat=cam["lat"], start_lng=cam["lng"],
            start_time=datetime(2024, 6, 1, 20, 0), duration_hours=HOURS,
            gender="F", age="A", season="summer", bear_speeds=bs,
            seed=SEED_BASE + i, terrain_cache=tc,
        )
        for p in path:
            along_paths.append(len(jc._terrain_clusters((p["lat"], p["lng"]), tc)))
    distribution = {k: along_paths.count(k) for k in sorted(set(along_paths))}
    print(f"  along the paths ({len(along_paths)} positions): median "
          f"{statistics.median(along_paths):.1f}, mean {statistics.mean(along_paths):.2f}, "
          f"max {max(along_paths)}")
    print(f"  distribution (clusters: number of positions): {distribution}")
    more_than_one = sum(1 for x in along_paths if x > 1) / len(along_paths) * 100
    print(f"  positions with MORE than one cluster: {more_than_one:.1f} %")

    # ---- Test 1: heading distribution -----------------------------
    print("\n" + "=" * 66)
    print(f"TEST 1: heading distribution ({N_RUNS} runs of {HOURS} h)")
    print("=" * 66)
    t0 = time.time()
    headings = collect_headings()
    print(f"  {len(headings)} heading decisions in {time.time()-t0:.1f}s")
    gaps = count_in_former_gaps(headings)
    print(f"  in the previously unreachable bands: {gaps} "
          f"({gaps/len(headings)*100:.1f} %), about 33 % expected")
    h = histogram(headings, bins=24)
    expected = len(headings) / 24
    print(f"  histogram (24 sectors of 15 degrees), expected {expected:.0f} per sector:")
    print(f"    {h}")
    print(f"    min {min(h)}, max {max(h)}, empty sectors: {sum(1 for x in h if x == 0)}")
    # Chi-square against a uniform distribution, reported as a figure only
    chi = sum((x - expected) ** 2 / expected for x in h)
    print(f"    chi-square against uniform: {chi:.1f} (df=23)")

    # ---- Tests 2 and 3: comparison and runtime --------------------
    print("\n" + "=" * 66)
    print("TESTS 2+3: comparison without and with clusters, same seeds")
    print("=" * 66)
    # Variant A: the actual previous code (8 sectors +/-15 deg, 1 sample)
    current_selection = jc.choose_weighted_direction
    jc.choose_weighted_direction = legacy_heading_selection
    try:
        legacy = run_metrics(60, HOURS, clusters_on=False)
    finally:
        jc.choose_weighted_direction = current_selection

    # Variant B: new code, but without cluster candidates
    without = run_metrics(60, HOURS, clusters_on=False)
    # Variant C: new code in full
    with_clusters = run_metrics(60, HOURS, clusters_on=True)

    print(f"  {'Metric':<26}{'legacy (45 grid)':>18}{'new, no cl.':>13}{'new, cl.':>11}")
    print(f"  {'-'*68}")
    for key, label, fmt in [
        ("distance_m", "Daily distance (m)", "{:.0f}"),
        ("net_m", "Net displacement (m)", "{:.0f}"),
        ("forest_pct", "Forest share (%)", "{:.1f}"),
        ("residential_area_pct", "Residential area (%)", "{:.1f}"),
        ("residential_street_pct", "Residential street (%)", "{:.1f}"),
        ("score", "Mean terrain score", "{:.2f}"),
        ("seconds_per_run", "Seconds per 24 h run", "{:.3f}"),
    ]:
        print(f"  {label:<26}{fmt.format(legacy[key]):>18}"
              f"{fmt.format(without[key]):>13}{fmt.format(with_clusters[key]):>11}")
    factor = with_clusters["seconds_per_run"] / max(1e-9, legacy["seconds_per_run"])
    print(f"\n  Runtime relative to legacy: {factor:.2f}x")

    print("\n" + "=" * 66)
    print("TEST 5: no network requests; no exception was raised up to here.")
    print("=" * 66)


if __name__ == "__main__":
    main()
