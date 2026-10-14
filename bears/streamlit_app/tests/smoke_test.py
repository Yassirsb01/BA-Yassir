"""
smoke_test.py
===============
Regression baseline for the cleanup. Captures the observable behaviour of
every module that the Streamlit app depends on, so that each refactoring
step can be verified not to have changed anything.

Deliberately avoids the database and the network: the test must produce the
same verdict with or without the university VPN. Database-dependent code
paths are only checked for importability and signature, not for results.

Run:  python tests/smoke_test.py
Exit code 0 means every check passed.
"""

import hashlib
import json
import os
import sys
import traceback
from datetime import datetime

# Run from anywhere: the application modules live one level up.
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_HERE)
if _APP not in sys.path:
    sys.path.insert(0, _APP)
os.chdir(_APP)

RESULTS = []


def check(name):
    """Decorator turning a function into a recorded check."""
    def wrap(fn):
        try:
            value = fn()
            RESULTS.append((name, "ok", value))
        except Exception:
            RESULTS.append((name, "FAILED", traceback.format_exc(limit=3)))
        return fn
    return wrap


def digest(obj) -> str:
    """Stable short hash of a JSON-serialisable structure."""
    blob = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


# ---------------------------------------------------------------
# Capture rendered HTML instead of starting Streamlit
# ---------------------------------------------------------------
import streamlit.components.v1 as components  # noqa: E402

_CAPTURED = {}
components.html = lambda html, **kw: _CAPTURED.__setitem__("html", html)


@check("imports: every module reachable from the app")
def _imports():
    names = [
        "activity_overlap", "animation_component", "carpathian_bears",
        "geojson_table_helper", "japan_comparison", "japan_deterrents",
        "japan_map_component", "maplibre_component", "status_widget",
        "sync_simulation", "terrain_cache", "wildlife_db_mariadb",
    ]
    import importlib
    for n in names:
        importlib.import_module(n)

    # Operator tools live in tools/ and are run as scripts, not imported
    # by the application. Import them by path so that a syntax error there
    # is still caught.
    import importlib.util
    tool = os.path.join(_APP, "tools", "prefetch_terrain.py")
    spec = importlib.util.spec_from_file_location("prefetch_terrain", tool)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))

    return f"{len(names)} modules + 1 tool"


@check("terrain cache: grid lookup")
def _terrain():
    from terrain_cache import TerrainCache
    tc = TerrainCache()
    if tc.disabled:
        return "cache disabled (corrupt file) - lookup skipped"
    from japan_comparison import load_japan_cameras
    cam = load_japan_cameras()[0]
    feats = tc.get_features(cam["lat"], cam["lng"], radius=150)
    return f"{len(tc._regions)} prefetch region(s), {len(feats)} features at first camera"


@check("terrain cache: bounding-box query")
def _terrain_box():
    from terrain_cache import TerrainCache
    from japan_comparison import load_japan_cameras
    tc = TerrainCache()
    cam = load_japan_cameras()[0]
    cells = tc.get_cells_in_box(cam["lat"] - 0.005, cam["lng"] - 0.005,
                                cam["lat"] + 0.005, cam["lng"] + 0.005)
    return f"{len(cells)} cells"


@check("japan: camera list")
def _cameras():
    from japan_comparison import load_japan_cameras
    cams = load_japan_cameras()
    return f"{len(cams)} cameras, digest {digest([(c['device_id'], c['lat'], c['lng']) for c in cams])}"


@check("japan: terrain clusters (formula 1)")
def _clusters():
    from japan_comparison import _terrain_clusters, load_japan_cameras
    from terrain_cache import TerrainCache
    tc = TerrainCache()
    cams = load_japan_cameras()
    counts = [len(_terrain_clusters((c["lat"], c["lng"]), tc)) for c in cams]
    return f"clusters per camera: {counts}"


@check("japan: free path, no terrain, fixed seed")
def _path_plain():
    import japan_comparison as jc
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    p = jc.simulate_free_path(
        start_lat=cams[0]["lat"], start_lng=cams[0]["lng"],
        start_time=datetime(2024, 6, 1, 20, 0), duration_hours=24,
        gender="F", age="A", season="summer", bear_speeds=bs,
        seed=4242, terrain_cache=None,
    )
    return f"{len(p)} positions, digest {digest([(round(x['lat'], 6), round(x['lng'], 6)) for x in p])}"


@check("japan: free path, with terrain, fixed seed")
def _path_terrain():
    import japan_comparison as jc
    from terrain_cache import TerrainCache
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    p = jc.simulate_free_path(
        start_lat=cams[0]["lat"], start_lng=cams[0]["lng"],
        start_time=datetime(2024, 6, 1, 20, 0), duration_hours=24,
        gender="F", age="A", season="summer", bear_speeds=bs,
        seed=4242, terrain_cache=TerrainCache(),
    )
    return f"{len(p)} positions, digest {digest([(round(x['lat'], 6), round(x['lng'], 6)) for x in p])}"


@check("japan: multiple bears from one sighting")
def _multi():
    import japan_comparison as jc
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    bears = jc.simulate_multiple_bears_from_sighting(
        cams[0]["lat"], cams[0]["lng"], datetime(2024, 6, 1, 20, 0),
        n_bears=4, duration_hours=6, bear_speeds=bs, seed=7, terrain_cache=None,
    )
    return f"{len(bears)} bears, digest {digest([[(round(p['lat'], 6), round(p['lng'], 6)) for p in b['path']] for b in bears])}"


@check("carpathian: synchronised real + simulated geojson")
def _sync():
    import pandas as pd
    from pyproj import Transformer
    import sync_simulation as sync
    df = pd.read_csv("data/animal_data/carpathian_bears/1_bears_RO.csv")
    df["ts"] = pd.to_datetime(df["timestamp"], format="%m/%d/%Y %H:%M")
    sub = df[(df["Name"] == "Bear2") &
             (df["ts"].dt.date == pd.Timestamp("2013-05-15").date())].sort_values("ts")
    # EPSG:3844 (Stereo70) wie in carpathian_bears.py und in der Vorarbeit;
    # EPSG:31700 ist der abgekuendigte Code und liegt bis zu 125 m daneben.
    tr = Transformer.from_crs("EPSG:3844", "EPSG:4326", always_xy=True)
    feats = []
    for _, r in sub.iterrows():
        lng, lat = tr.transform(r["X"], r["Y"])
        feats.append({
            "type": "Feature",
            "properties": {"bear_id": r["Name"],
                           "timestamp": r["ts"].strftime("%Y-%m-%d %H:%M:%S"),
                           "sex": r["Sex"], "age": r["Age"]},
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
        })
    out = sync.build_synced_geojson({"type": "FeatureCollection", "features": feats},
                                    num_alternatives=10, n_realizations=3, seed=42)
    coords = [f["geometry"]["coordinates"] for f in out["simulated"]["features"]]
    return (f"real {len(out['real']['features'])}, alt {len(out['alternative']['features'])}, "
            f"sim {len(out['simulated']['features'])}, digest {digest(coords)}")


@check("carpathian: empirical turn persistence table")
def _persistence():
    import sync_simulation as sync
    vals = [round(sync._mean_cos_for_step_length(x), 4) for x in (10, 30, 80, 150, 400, 900)]
    kappa = [round(sync._kappa_from_mean_cos(v), 4) for v in vals]
    return f"mean cos {vals}, kappa {kappa}"


@check("simulation layer: options and geojson")
def _sim_layer():
    from bear_simulation import get_simulation_options, get_simulation_geojson
    ids, info = get_simulation_options()
    total = sum(len(v) for v in info.values())
    g = get_simulation_geojson(bear_id=ids[0], season=list(info[ids[0]])[0], num_alternatives=10)
    return (f"{len(ids)} bears, {total} (bear, season) pairs, "
            f"{len(g['points']['features'])} points")


@check("render: main map")
def _render_main():
    import maplibre_component as ml
    ml.render_maplibre()
    h = _CAPTURED["html"]
    return f"{len(h)} chars, default basemap {ml.DEFAULT_BASEMAP!r}"


@check("render: carpathian animation")
def _render_anim():
    import animation_component as anim
    import sync_simulation as sync
    real = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"timestamp": "2013-05-15 11:00:00"},
         "geometry": {"type": "Point", "coordinates": [25.3, 45.6]}}]}
    anim.render_animation_map(carpathian={"points": real,
                                          "paths": {"type": "FeatureCollection", "features": []}})
    return f"{len(_CAPTURED['html'])} chars"


@check("render: japan map")
def _render_japan():
    import japan_map_component as jm
    from japan_comparison import load_japan_cameras
    cams = load_japan_cameras()
    jm.render_japan_map(cameras=cams, start_camera=cams[0], bears=[], real_events=[])
    return f"{len(_CAPTURED['html'])} chars"


@check("activity overlap: circular kde and overlap coefficient")
def _overlap():
    import numpy as np
    import activity_overlap as ao
    grid = np.linspace(0, 24, 240)
    a = ao.circular_kde([1.0, 2.0, 22.0, 23.0], grid)
    b = ao.circular_kde([1.5, 2.5, 21.5, 23.5], grid)
    d = ao.overlap_coefficient(a, b, grid[1] - grid[0])
    return f"overlap of two synthetic samples: {d:.4f}"


@check("season help text covers every value in the data")
def _seasons():
    from carpathian_bears import SEASON_DESCRIPTIONS, get_carpathian_options
    _, seasons, _, _ = get_carpathian_options()
    missing = [s for s in seasons if s not in SEASON_DESCRIPTIONS]
    if missing:
        raise AssertionError(f"undocumented seasons: {missing}")
    return f"{len(seasons)} seasons, all documented"


def main():
    width = 52
    print("=" * 70)
    print("Smoke test")
    print("=" * 70)
    failed = 0
    for name, status, value in RESULTS:
        if status == "ok":
            print(f"  [ok]   {name:<{width}} {value}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")
            print("         " + str(value).replace("\n", "\n         "))
    print("-" * 70)
    print(f"{len(RESULTS) - failed} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
