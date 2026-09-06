"""
animation_component.py
========================
Eigenstaendige MapLibre-Karte fuer die Bewegungs-Animation der
Carpathian-Baeren (echte GPS-Route + zugehoerige Alternativ-Kandidaten
aus Fabians Modell, siehe sync_simulation.py) - garantiert derselbe
Baer, derselbe Tag, dieselben Zeitpunkte.

Ausgelegt als Analysewerkzeug: Forschende sollen nachvollziehen koennen,
WO und WANN sich ein Baer bewegt hat und wie plausibel die simulierten
Alternativen dazu sind.

Darstellung:
  - Blauer Punkt + mitwachsende Spur: die ECHTE GPS-Bewegung, zwischen den
    Fixpunkten interpoliert. Der Gesamtpfad ist standardmaessig NICHT
    vorgezeichnet (sonst waere das Ergebnis schon vor dem Abspielen
    sichtbar) - per Schalter einblendbar.
  - Oranger "Faecher": an JEDEM echten Schritt alle N Alternativ-Kandidaten,
    die das Modell an genau diesem Punkt/Zeitpunkt erzeugt hat. KEIN eigener
    Pfad - die Alternativen sind N unabhaengige Optionen PRO Schritt.

Kartengrundlagen:
  - Satellit (Esri World Imagery) fuer Gelaendekontext - dieselbe Quelle,
    die auch carpathian_bears.py schon nutzt
  - Positron / Liberty / Dark Matter als Vektor-Alternativen
  - Optionaler 3D-Modus: Hoehenmodell (Mapterhorn, kostenfrei ohne
    Schluessel - Quelle aus dem offiziellen MapLibre-3D-Beispiel) +
    Kameraneigung. Bewusst opt-in, da zusaetzliche Netzwerk-Kacheln noetig
    sind; bei Fehlern bleibt die Karte in 2D nutzbar (Hinweis im Panel).
"""

import json
import streamlit as st
import streamlit.components.v1 as components

# Esri World Imagery liefert in abgelegenen Gebieten (Karpaten) nur ~1 m
# Aufloesung, das entspricht etwa Zoomstufe 17. Wird eine hoehere maxzoom
# angegeben, fordert MapLibre Kacheln an, die dort nicht existieren - Esri
# antwortet dann mit der Platzhalter-Kachel "Map data not yet available".
# Mit korrekt gesetztem maxzoom skaliert MapLibre stattdessen die
# vorhandenen Kacheln hoch (leicht unschaerfer, aber immer Bild).
ESRI_NATIVE_MAXZOOM = 17

_ESRI_IMAGERY_SOURCE = {
    "type": "raster",
    "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    "tileSize": 256,
    "maxzoom": ESRI_NATIVE_MAXZOOM,
    "attribution": "Luftbild: &copy; Esri, Maxar, Earthstar Geographics",
}

# Transparente Beschriftungs-/Grenzenebene, um im Satellitenbild die
# Orientierung zu behalten (Ortsnamen, Verwaltungsgrenzen).
_ESRI_REFERENCE_SOURCE = {
    "type": "raster",
    "tiles": ["https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"],
    "tileSize": 256,
    "maxzoom": ESRI_NATIVE_MAXZOOM,
    "attribution": "&copy; Esri",
}

_SATELLITE_STYLE = {
    "version": 8,
    "sources": {"esri-imagery": _ESRI_IMAGERY_SOURCE},
    "layers": [{"id": "esri-imagery", "type": "raster", "source": "esri-imagery"}],
}

_SATELLITE_LABELS_STYLE = {
    "version": 8,
    "sources": {"esri-imagery": _ESRI_IMAGERY_SOURCE, "esri-reference": _ESRI_REFERENCE_SOURCE},
    "layers": [
        {"id": "esri-imagery", "type": "raster", "source": "esri-imagery"},
        {"id": "esri-reference", "type": "raster", "source": "esri-reference"},
    ],
}

BASEMAP_STYLES = {
    "Satellit": _SATELLITE_STYLE,
    "Satellit + Beschriftung": _SATELLITE_LABELS_STYLE,
    "Positron": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Liberty": "https://tiles.openfreemap.org/styles/liberty",
    "Dark Matter": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
}

# Etwas ueber der nativen Aufloesung erlaubt, damit man noch nah heran kann -
# aber nicht so weit, dass das Hochskalieren unbrauchbar unscharf wird.
MAP_MAX_ZOOM = 18.5

# Kostenfreie Hoehendaten ohne API-Schluessel (Quelle des offiziellen
# MapLibre-3D-Terrain-Beispiels).
TERRAIN_TILEJSON = "https://tiles.mapterhorn.com/tilejson.json"


def _empty_fc():
    return {"type": "FeatureCollection", "features": []}


def render_animation_map(
    carpathian: dict | None = None,
    alternatives: dict | None = None,
    basemap: str = "Satellit",
    bear_label: str = "",
    dataset_label: str = "Carpathian Bears · GPS-Tracking (Rumänien)",
    source_label: str = "",
    height: int = 900,
):
    """
    Args:
        carpathian: {"points": GeoJSON, "paths": GeoJSON} - echte GPS-Route
            EINES Baeren an EINEM Tag, volle Aufloesung.
        alternatives: GeoJSON FeatureCollection der Alternativ-Kandidaten
            (aus sync_simulation.build_synced_geojson()["alternative"]).
        bear_label: z.B. "BÄR 7" - Kennzeichnung oben rechts im Panel.
        dataset_label: welcher Datensatz gezeigt wird (fuer Forschende, die
            die Karte ohne Vorwissen oeffnen).
        source_label: woher die Daten kommen (z.B. "MariaDB (ursus)").
    """
    carpathian = carpathian or {}
    cp_points = carpathian.get("points", _empty_fc())
    cp_paths = carpathian.get("paths", _empty_fc())
    alt_points = alternatives or _empty_fc()

    styles_js = json.dumps(BASEMAP_STYLES)
    bm_options = "".join(
        f'<option value="{name}"{" selected" if name == basemap else ""}>{name}</option>'
        for name in BASEMAP_STYLES
    )

    data = {
        "cp_points": json.dumps(cp_points),
        "cp_paths": json.dumps(cp_paths),
        "alt_points": json.dumps(alt_points),
    }

    n_points_label = f"{len(cp_points.get('features', []))} Pkt."
    n_alts_label = f"{len(alt_points.get('features', []))} Kand."

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg:#e9e6e1; --ink:#1a1917; --ink-soft:#4a4741; --ink-faint:#8a8680;
      --panel:rgba(252,251,249,0.94); --line:rgba(18,17,15,.10); --line-strong:rgba(18,17,15,.13);
      --blue:#1d6fb8; --orange:#e8830c;
    }}
    html, body {{ margin:0; padding:0; height:100%; background:var(--bg);
                  font-family:'IBM Plex Sans',system-ui,-apple-system,sans-serif; color:var(--ink); }}
    #map {{ position:absolute; inset:0; width:100%; height:{height}px; }}
    .wrap {{ position:relative; width:100%; height:{height}px; overflow:hidden; }}
    .mono {{ font-family:'IBM Plex Mono',monospace; }}
    .glass {{
      background:var(--panel); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
      box-shadow:0 1px 0 rgba(255,255,255,.7) inset, 0 6px 24px rgba(20,18,15,.13), 0 0 0 1px rgba(18,17,15,.08);
      border-radius:13px;
    }}

    .status-panel {{ position:absolute; top:16px; left:16px; width:264px; padding:14px 15px 13px; z-index:3; }}
    .status-top {{ display:flex; align-items:baseline; justify-content:space-between; gap:8px; }}
    .status-title {{ font-size:13px; font-weight:600; letter-spacing:-0.01em; }}
    .status-tag {{ font-size:10px; color:var(--ink-faint); }}
    .dataset {{ margin-top:3px; font-size:10.5px; color:var(--ink-faint); line-height:1.4; }}
    .source-badge {{
      display:inline-flex; align-items:center; gap:5px; margin-top:7px;
      font-family:'IBM Plex Mono',monospace; font-size:9.5px; color:var(--ink-soft);
      background:rgba(18,17,15,.05); padding:3px 7px; border-radius:6px;
    }}
    .source-dot {{ width:5px; height:5px; border-radius:50%; background:#3aa76d; }}
    .legend {{ margin-top:10px; display:grid; gap:7px; }}
    .legend-row {{ display:flex; align-items:center; gap:8px; }}
    .ldot {{ width:9px; height:9px; border-radius:50%; flex:none; }}
    .ltext {{ font-size:11.5px; color:var(--ink-soft); }}
    .lcount {{ margin-left:auto; font-size:11px; color:var(--ink-faint); }}
    .hr {{ height:1px; background:var(--line); margin:12px 0 10px; }}
    .section-label {{ font-size:10px; letter-spacing:.07em; text-transform:uppercase; color:var(--ink-faint); margin-bottom:5px; }}
    #basemap-select {{
      width:100%; appearance:none; font-family:inherit; font-size:12px; color:var(--ink);
      padding:7px 9px; border-radius:8px; border:1px solid var(--line-strong); background:#fff; cursor:pointer;
    }}
    .switch-row {{ display:flex; align-items:center; gap:8px; margin-top:9px; font-size:11.5px; color:var(--ink-soft); cursor:pointer; }}
    .switch-row input {{ accent-color:var(--blue); cursor:pointer; }}
    .terrain-note {{ font-size:10px; color:#b4553c; margin-top:6px; line-height:1.4; display:none; }}

    .control-bar {{
      position:absolute; left:50%; transform:translateX(-50%); bottom:20px;
      width:min(880px, calc(100% - 32px)); z-index:4; padding:15px 18px 13px;
    }}
    .scrub-row {{ display:flex; align-items:center; gap:12px; margin-bottom:13px; }}
    .time-label {{ font-size:11px; color:var(--ink-faint); width:74px; flex:none; }}
    .time-label.right {{ text-align:right; }}
    .track {{ position:relative; flex:1; height:22px; display:flex; align-items:center; cursor:pointer; touch-action:none; }}
    .track-bg {{ position:absolute; left:0; right:0; height:5px; border-radius:3px; background:rgba(18,17,15,.10); }}
    .ticks {{ position:absolute; inset:0; }}
    .tick {{ position:absolute; top:50%; width:1px; height:9px; margin-top:-4.5px; background:rgba(18,17,15,.18); }}
    .track-fill {{ position:absolute; left:0; height:5px; border-radius:3px; background:var(--blue); width:0%; }}
    .track-thumb {{
      position:absolute; top:50%; width:15px; height:15px; margin-top:-7.5px; margin-left:-7.5px;
      border-radius:50%; background:#fff; box-shadow:0 1px 4px rgba(20,18,15,.28), 0 0 0 1px rgba(18,17,15,.10); left:0%;
    }}
    .controls-row {{ display:flex; align-items:center; gap:14px; }}
    .btn-cluster {{ display:flex; align-items:center; gap:6px; }}
    .icon-btn {{
      width:34px; height:34px; display:flex; align-items:center; justify-content:center;
      border:1px solid var(--line-strong); background:#fff; border-radius:9px; cursor:pointer; color:var(--ink);
    }}
    .icon-btn:hover {{ background:#f2efea; }}
    .play-btn {{
      width:42px; height:42px; display:flex; align-items:center; justify-content:center;
      border:none; background:var(--ink); border-radius:11px; cursor:pointer; color:#fff;
      box-shadow:0 2px 8px rgba(20,18,15,.24);
    }}
    .play-btn:hover {{ background:#33302b; }}
    .divider {{ width:1px; height:34px; background:var(--line); }}
    .clock-block {{ display:flex; flex-direction:column; gap:1px; min-width:170px; }}
    .clock {{ font-size:19px; font-weight:500; letter-spacing:-0.01em; line-height:1.1; }}
    .clock-sub {{ font-size:10.5px; color:var(--ink-faint); }}
    .metrics {{ display:flex; gap:14px; }}
    .metric-val {{ font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:500; line-height:1.2; }}
    .metric-lbl {{ font-size:9.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-faint); }}
    .right-controls {{ margin-left:auto; display:flex; align-items:center; gap:10px; }}
    .speed-pills {{ display:flex; align-items:center; gap:2px; padding:3px; border-radius:10px; background:rgba(18,17,15,.055); }}
    .speed-pill {{
      border:none; cursor:pointer; font-family:'IBM Plex Mono',monospace; font-size:11.5px; font-weight:500;
      padding:6px 9px; border-radius:7px; background:transparent; color:var(--ink-faint);
    }}
    .speed-pill.active {{ background:#fff; color:var(--ink); box-shadow:0 1px 3px rgba(20,18,15,.16); }}
    .range-btn {{
      display:flex; align-items:center; gap:7px; height:34px; padding:0 12px;
      border:1px solid var(--line-strong); background:#fff; border-radius:9px; cursor:pointer;
      font-family:inherit; font-size:12px; color:var(--ink);
    }}
    .range-btn:hover, .range-btn.open {{ background:#f2efea; }}
    .rdot {{ width:6px; height:6px; border-radius:50%; background:var(--blue); }}
    .range-popover {{
      position:absolute; right:18px; bottom:calc(100% + 10px); width:300px; padding:15px 16px 16px;
      border-radius:13px; background:rgba(252,251,249,0.97); backdrop-filter:blur(18px);
      box-shadow:0 10px 34px rgba(20,18,15,.18), 0 0 0 1px rgba(18,17,15,.08); display:none;
    }}
    .popover-title {{ font-size:12.5px; font-weight:600; margin-bottom:12px; }}
    #anim-start {{
      width:100%; box-sizing:border-box; font-family:'IBM Plex Mono',monospace; font-size:12px;
      padding:7px 9px; border-radius:8px; border:1px solid var(--line-strong); background:#fff; color:var(--ink);
    }}
    .duration-pills {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }}
    .duration-pill {{
      border:1px solid var(--line-strong); cursor:pointer; font-family:inherit; font-size:11.5px;
      padding:6px 11px; border-radius:8px; background:#fff; color:var(--ink-soft);
    }}
    .duration-pill.active {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
    .range-detail {{
      margin-top:13px; padding-top:11px; border-top:1px solid var(--line);
      font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--ink-faint); line-height:1.5;
    }}
    .hint-caption {{
      position:absolute; left:16px; bottom:20px; z-index:3;
      font-family:'IBM Plex Mono',monospace; font-size:10px; color:#7d7972;
      background:rgba(252,251,249,.8); padding:4px 8px; border-radius:6px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div id="map"></div>

    <div class="status-panel glass">
      <div class="status-top">
        <div class="status-title">Bewegungs-Animation</div>
        <div class="status-tag mono">{bear_label}</div>
      </div>
      <div class="dataset">{dataset_label}</div>
      <div class="source-badge"><span class="source-dot"></span>{source_label}</div>

      <div class="legend">
        <div class="legend-row">
          <span class="ldot" style="background:var(--blue); box-shadow:0 0 0 3px rgba(29,111,184,.16)"></span>
          <span class="ltext">Echte GPS-Route</span>
          <span class="lcount mono">{n_points_label}</span>
        </div>
        <div class="legend-row">
          <span class="ldot" style="background:var(--orange); box-shadow:0 0 0 3px rgba(232,131,12,.16)"></span>
          <span class="ltext">Alternativen (Fächer)</span>
          <span class="lcount mono">{n_alts_label}</span>
        </div>
      </div>

      <div class="hr"></div>
      <div class="section-label">Kartenstil</div>
      <select id="basemap-select">{bm_options}</select>

      <label class="switch-row"><input type="checkbox" id="toggle-3d" /> 3D-Gelände (Höhenmodell)</label>
      <label class="switch-row"><input type="checkbox" id="toggle-fullpath" /> Gesamtpfad einblenden</label>
      <div class="terrain-note" id="terrain-note">Höhendaten nicht erreichbar – Karte bleibt in 2D.</div>
    </div>

    <div class="control-bar glass">
      <div class="scrub-row">
        <div class="time-label mono" id="start-label">–</div>
        <div class="track" id="track">
          <div class="track-bg"></div>
          <div class="ticks" id="ticks"></div>
          <div class="track-fill" id="track-fill"></div>
          <div class="track-thumb" id="track-thumb"></div>
        </div>
        <div class="time-label right mono" id="end-label">–</div>
      </div>

      <div class="controls-row">
        <div class="btn-cluster">
          <button id="step-back" class="icon-btn" title="Ein Schritt zurück">
            <svg width="13" height="13" viewBox="0 0 12 12"><rect x="1" y="1.5" width="1.8" height="9" fill="currentColor"></rect><polygon points="11,1.5 11,10.5 4,6" fill="currentColor"></polygon></svg>
          </button>
          <button id="play-btn" class="play-btn" title="Play/Pause">
            <svg id="play-icon" width="13" height="13" viewBox="0 0 12 12"><polygon points="2.5,1.2 11,6 2.5,10.8" fill="currentColor"></polygon></svg>
          </button>
          <button id="step-fwd" class="icon-btn" title="Ein Schritt vor">
            <svg width="13" height="13" viewBox="0 0 12 12"><polygon points="1,1.5 1,10.5 8,6" fill="currentColor"></polygon><rect x="9.2" y="1.5" width="1.8" height="9" fill="currentColor"></rect></svg>
          </button>
          <button id="reset-btn" class="icon-btn" title="Zurücksetzen" style="font-size:15px;">↺</button>
        </div>

        <div class="divider"></div>

        <div class="clock-block">
          <div class="clock mono" id="clock-label">–</div>
          <div class="clock-sub" id="clock-sub">–</div>
        </div>

        <div class="divider"></div>

        <div class="metrics">
          <div>
            <div class="metric-val" id="metric-dist">–</div>
            <div class="metric-lbl">Strecke</div>
          </div>
          <div>
            <div class="metric-val" id="metric-speed">–</div>
            <div class="metric-lbl">Tempo</div>
          </div>
        </div>

        <div class="right-controls">
          <div class="speed-pills" id="speed-pills"></div>
          <button id="range-toggle" class="range-btn">
            <span class="rdot"></span><span id="range-label">Gesamt</span>
          </button>
        </div>
      </div>

      <div class="range-popover" id="range-popover">
        <div class="popover-title">Zeitraum</div>
        <div class="section-label">Startzeitpunkt</div>
        <input type="datetime-local" id="anim-start" />
        <div class="section-label" style="margin-top:13px">Dauer</div>
        <div class="duration-pills" id="duration-pills"></div>
        <div class="range-detail" id="range-detail">–</div>
      </div>
    </div>

    <div class="hint-caption" id="anim-hint"></div>
  </div>

  <script>
    const STYLES = {styles_js};
    const TERRAIN_TILEJSON = "{TERRAIN_TILEJSON}";
    const DATA = {{
      cp_points:  {data["cp_points"]},
      cp_paths:   {data["cp_paths"]},
      alt_points: {data["alt_points"]}
    }};

    const map = new maplibregl.Map({{
      container:'map', style:STYLES["{basemap}"], center:[25.3,45.6], zoom:8,
      maxPitch:85, maxZoom:{MAP_MAX_ZOOM},
      // Quellenangabe ist bei Esri-Luftbildern Pflicht (kompakt eingeklappt)
      attributionControl:{{ compact:true }},
    }});
    map.addControl(new maplibregl.NavigationControl({{ visualizePitch:true }}), 'top-right');
    map.addControl(new maplibregl.ScaleControl({{ maxWidth:110, unit:'metric' }}), 'bottom-right');

    // -------------------------------------------------------
    // Sources + Layer (werden nach jedem Kartenstil-Wechsel neu angelegt)
    // -------------------------------------------------------
    function addSourcesAndLayers() {{
      const addSrc = (id, d) => {{ if (!map.getSource(id)) map.addSource(id, {{ type:'geojson', data:d }}); }};
      addSrc('cp_paths_static', DATA.cp_paths);
      addSrc('anim-trail', {{ type:'FeatureCollection', features:[] }});
      addSrc('anim-marker', {{ type:'FeatureCollection', features:[] }});
      addSrc('alt-fan', {{ type:'FeatureCollection', features:[] }});
      addSrc('alt-fan-lines', {{ type:'FeatureCollection', features:[] }});

      if (!map.getSource('terrain-dem')) {{
        try {{ map.addSource('terrain-dem', {{ type:'raster-dem', url:TERRAIN_TILEJSON }}); }}
        catch (e) {{ console.warn('Terrain-Quelle nicht verfuegbar:', e); }}
      }}

      const addLayerSafe = (spec) => {{ if (!map.getLayer(spec.id)) map.addLayer(spec); }};

      // Schummerung (nutzt dasselbe Hoehenmodell wie der 3D-Modus): macht
      // Hangrichtung und Gelaendeform sichtbar, was im reinen Luftbild oft
      // schwer zu erkennen ist. Wird zusammen mit 3D ein-/ausgeschaltet und
      // liegt UNTER allen Datenebenen, damit Route und Faecher lesbar bleiben.
      if (map.getSource('terrain-dem')) {{
        addLayerSafe({{ id:'hillshade', type:'hillshade', source:'terrain-dem',
          layout:{{ visibility:'none' }},
          paint:{{ 'hillshade-exaggeration':0.45, 'hillshade-shadow-color':'#3b3226' }} }});
      }}

      // Gesamtpfad: standardmaessig AUS (sonst ist das Ergebnis schon vor
      // dem Abspielen sichtbar) - per Schalter einblendbar.
      addLayerSafe({{ id:'cp-paths-static', type:'line', source:'cp_paths_static',
        layout:{{ visibility:'none' }},
        paint:{{ 'line-color':'#1d6fb8','line-width':2,'line-opacity':0.35,'line-dasharray':[2,2] }} }});

      addLayerSafe({{ id:'alt-fan-lines', type:'line', source:'alt-fan-lines',
        paint:{{ 'line-color':'#e8830c','line-width':1.2,'line-opacity':0.55,'line-dasharray':[1,1.5] }} }});
      addLayerSafe({{ id:'alt-fan', type:'circle', source:'alt-fan',
        paint:{{ 'circle-radius':5,'circle-color':'#e8830c','circle-opacity':0.8,
                 'circle-stroke-width':1,'circle-stroke-color':'#fff' }} }});

      addLayerSafe({{ id:'anim-trail', type:'line', source:'anim-trail',
        paint:{{ 'line-color':'#1d6fb8','line-width':3.5,'line-opacity':0.95 }} }});
      addLayerSafe({{ id:'anim-marker-halo', type:'circle', source:'anim-marker',
        paint:{{ 'circle-radius':13,'circle-color':'#1d6fb8','circle-opacity':0.25 }} }});
      addLayerSafe({{ id:'anim-marker', type:'circle', source:'anim-marker',
        paint:{{ 'circle-radius':6.5,'circle-color':'#1d6fb8','circle-stroke-width':2.5,'circle-stroke-color':'#fff' }} }});

      applyFullPathVisibility();
      if (uiState.terrain3d) applyTerrain(true);
    }}

    function fitToData() {{
      const coords = [];
      (DATA.cp_points.features || []).forEach(f => {{
        const c = f.geometry && f.geometry.coordinates;
        if (c && isFinite(c[0]) && isFinite(c[1])) coords.push(c);
      }});
      if (!coords.length) return;
      let minLng=Infinity,minLat=Infinity,maxLng=-Infinity,maxLat=-Infinity;
      coords.forEach(([lng,lat]) => {{
        minLng=Math.min(minLng,lng); maxLng=Math.max(maxLng,lng);
        minLat=Math.min(minLat,lat); maxLat=Math.max(maxLat,lat);
      }});
      map.fitBounds([[minLng,minLat],[maxLng,maxLat]], {{ padding:110, maxZoom:15, duration:0 }});
    }}

    // -------------------------------------------------------
    // Kartenstil / 3D / Gesamtpfad
    // -------------------------------------------------------
    const uiState = {{ terrain3d:false, fullPath:false }};

    function applyFullPathVisibility() {{
      if (map.getLayer('cp-paths-static')) {{
        map.setLayoutProperty('cp-paths-static','visibility', uiState.fullPath ? 'visible' : 'none');
      }}
    }}

    function applyTerrain(on) {{
      try {{
        if (map.getLayer('hillshade')) {{
          map.setLayoutProperty('hillshade','visibility', on ? 'visible' : 'none');
        }}
        if (on) {{
          if (map.getSource('terrain-dem')) map.setTerrain({{ source:'terrain-dem', exaggeration:1.4 }});
          map.easeTo({{ pitch:62, duration:700 }});
        }} else {{
          map.setTerrain(null);
          map.easeTo({{ pitch:0, duration:500 }});
        }}
      }} catch (e) {{
        console.warn('Terrain konnte nicht gesetzt werden:', e);
        showTerrainNote();
      }}
    }}

    function showTerrainNote() {{
      const n = document.getElementById('terrain-note');
      if (n) n.style.display = 'block';
      const cb = document.getElementById('toggle-3d');
      if (cb) cb.checked = false;
      uiState.terrain3d = false;
    }}

    // Fehlende Hoehen-Kacheln melden, ohne die Karte zu blockieren
    map.on('error', (e) => {{
      const msg = (e && e.error && e.error.message) || '';
      if (uiState.terrain3d && /terrain|dem|mapterhorn/i.test(msg)) showTerrainNote();
    }});

    function wireMapControls() {{
      const sel = document.getElementById('basemap-select');
      if (sel) sel.addEventListener('change', e => {{
        map.setStyle(STYLES[e.target.value], {{ diff:false }});
        map.once('style.load', () => {{ addSourcesAndLayers(); renderAnimationFrame(); }});
      }});

      const t3d = document.getElementById('toggle-3d');
      if (t3d) t3d.addEventListener('change', e => {{
        uiState.terrain3d = e.target.checked;
        applyTerrain(uiState.terrain3d);
      }});

      const tfp = document.getElementById('toggle-fullpath');
      if (tfp) tfp.addEventListener('change', e => {{
        uiState.fullPath = e.target.checked;
        applyFullPathVisibility();
      }});
    }}

    // -------------------------------------------------------
    // ANIMATIONS-ENGINE
    // -------------------------------------------------------
    const SPEEDS = [1, 10, 60, 300, 1000];
    const DURATIONS = [[0.25,'15 Min'],[0.5,'30 Min'],[1,'1 Std'],[4,'4 Std'],[24,'24 Std'],[-1,'Gesamt']];

    const animState = {{
      playing:false, speed:300, track:[], altFan:{{steps:[], bySteptime:{{}}}},
      startTime:null, endTime:null, currentTime:null, durHours:-1,
      rafId:null, lastWallClock:null,
    }};

    function parseTime(v) {{ return v ? Date.parse(String(v).replace(' ','T')) : NaN; }}

    // Haversine-Distanz in Metern - fuer Streckenmessung/Tempo-Anzeige
    function haversine(a, b) {{
      const R = 6371000, toRad = d => d * Math.PI / 180;
      const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
      const s = Math.sin(dLat/2)**2 + Math.cos(toRad(a.lat))*Math.cos(toRad(b.lat))*Math.sin(dLng/2)**2;
      return 2 * R * Math.asin(Math.sqrt(s));
    }}

    function buildTrackFromCarpathian() {{
      const points = [];
      (DATA.cp_points.features || []).forEach(f => {{
        const p = f.properties || {{}};
        const t = parseTime(p.timestamp);
        if (isNaN(t)) return;
        points.push({{ t, lng:f.geometry.coordinates[0], lat:f.geometry.coordinates[1] }});
      }});
      points.sort((a,b)=>a.t-b.t);
      return points;
    }}

    function buildAlternativeFan() {{
      const bySteptime = {{}};
      (DATA.alt_points.features || []).forEach(f => {{
        const p = f.properties || {{}};
        const t = parseTime(p.timestamp);
        if (isNaN(t)) return;
        (bySteptime[t] = bySteptime[t] || []).push([f.geometry.coordinates[0], f.geometry.coordinates[1]]);
      }});
      return {{ steps: Object.keys(bySteptime).map(Number).sort((a,b)=>a-b), bySteptime }};
    }}

    function interpolatePosition(track, t) {{
      if (!track || !track.length) return null;
      if (t < track[0].t) return null;
      if (t >= track[track.length-1].t) return track[track.length-1];
      let lo=0, hi=track.length-1;
      while (hi-lo>1) {{ const mid=(lo+hi)>>1; if (track[mid].t<=t) lo=mid; else hi=mid; }}
      const a=track[lo], b=track[hi];
      const frac = b.t===a.t ? 0 : (t-a.t)/(b.t-a.t);
      return {{ lng:a.lng+(b.lng-a.lng)*frac, lat:a.lat+(b.lat-a.lat)*frac }};
    }}

    function trailCoords(track, t) {{
      const coords = [];
      for (const p of track) {{ if (p.t >= t) break; coords.push([p.lng, p.lat]); }}
      const cur = interpolatePosition(track, t);
      if (cur) coords.push([cur.lng, cur.lat]);
      return coords;
    }}

    function currentFanStepTime(t) {{
      const steps = animState.altFan.steps;
      if (!steps.length) return null;
      let chosen = steps[0];
      for (const s of steps) {{ if (s <= t) chosen = s; else break; }}
      return chosen;
    }}

    // Zurueckgelegte Strecke bis t (nur innerhalb des gewaehlten Zeitfensters)
    function distanceUntil(track, t) {{
      let total = 0, prev = null;
      for (const p of track) {{
        if (p.t < animState.startTime) continue;
        if (p.t > t) break;
        if (prev) total += haversine(prev, p);
        prev = p;
      }}
      const cur = interpolatePosition(track, t);
      if (prev && cur) total += haversine(prev, cur);
      return total;
    }}

    // Momentangeschwindigkeit aus dem aktuell laufenden GPS-Schritt
    function currentStepSpeedKmh(track, t) {{
      if (track.length < 2) return null;
      for (let i = 0; i < track.length - 1; i++) {{
        if (t >= track[i].t && t <= track[i+1].t) {{
          const dtH = (track[i+1].t - track[i].t) / 3600000;
          if (dtH <= 0) return null;
          return (haversine(track[i], track[i+1]) / 1000) / dtH;
        }}
      }}
      return null;
    }}

    function fmtClock(t) {{ return new Date(t).toLocaleTimeString('de-DE', {{ hour:'2-digit', minute:'2-digit' }}); }}
    function fmtDate(t)  {{ return new Date(t).toLocaleDateString('de-DE', {{ day:'2-digit', month:'2-digit', year:'numeric' }}); }}

    function renderAnimationFrame() {{
      const pos = interpolatePosition(animState.track, animState.currentTime);
      const markerFeatures = pos ? [{{ type:'Feature', properties:{{}}, geometry:{{type:'Point', coordinates:[pos.lng,pos.lat]}} }}] : [];
      const trailC = trailCoords(animState.track, animState.currentTime);
      const trailFeatures = trailC.length >= 2 ? [{{ type:'Feature', properties:{{}}, geometry:{{type:'LineString', coordinates:trailC}} }}] : [];

      const ms = map.getSource('anim-marker'); if (ms) ms.setData({{type:'FeatureCollection', features:markerFeatures}});
      const ts = map.getSource('anim-trail');  if (ts) ts.setData({{type:'FeatureCollection', features:trailFeatures}});

      const stepTime = currentFanStepTime(animState.currentTime);
      const fanCoords = stepTime != null ? (animState.altFan.bySteptime[stepTime] || []) : [];
      const fanFeatures = fanCoords.map(c => ({{ type:'Feature', properties:{{}}, geometry:{{type:'Point', coordinates:c}} }}));
      const fanLines = (pos && fanCoords.length) ? fanCoords.map(c => ({{
        type:'Feature', properties:{{}}, geometry:{{type:'LineString', coordinates:[[pos.lng,pos.lat], c]}}
      }})) : [];
      const fs = map.getSource('alt-fan'); if (fs) fs.setData({{type:'FeatureCollection', features:fanFeatures}});
      const fl = map.getSource('alt-fan-lines'); if (fl) fl.setData({{type:'FeatureCollection', features:fanLines}});

      const span = Math.max(1, animState.endTime - animState.startTime);
      const pct = Math.max(0, Math.min(100, (animState.currentTime - animState.startTime)/span*100));
      const fill = document.getElementById('track-fill'); if (fill) fill.style.width = pct + '%';
      const thumb = document.getElementById('track-thumb'); if (thumb) thumb.style.left = pct + '%';

      const clockEl = document.getElementById('clock-label');
      if (clockEl) clockEl.textContent = fmtClock(animState.currentTime);
      const clockSub = document.getElementById('clock-sub');
      if (clockSub) {{
        const idx = animState.track.filter(p => p.t <= animState.currentTime).length;
        clockSub.textContent = fmtDate(animState.currentTime) + ' · Schritt ' + Math.max(1, idx) + '/' + animState.track.length;
      }}

      const distEl = document.getElementById('metric-dist');
      if (distEl) {{
        const m = distanceUntil(animState.track, animState.currentTime);
        distEl.textContent = m >= 1000 ? (m/1000).toFixed(2) + ' km' : Math.round(m) + ' m';
      }}
      const spdEl = document.getElementById('metric-speed');
      if (spdEl) {{
        const kmh = currentStepSpeedKmh(animState.track, animState.currentTime);
        spdEl.textContent = kmh == null ? '–' : kmh.toFixed(2) + ' km/h';
      }}

      const playIcon = document.getElementById('play-icon');
      if (playIcon) {{
        playIcon.innerHTML = animState.playing
          ? '<rect x="2" y="1.5" width="3" height="9" rx="0.8" fill="currentColor"></rect><rect x="7" y="1.5" width="3" height="9" rx="0.8" fill="currentColor"></rect>'
          : '<polygon points="2.5,1.2 11,6 2.5,10.8" fill="currentColor"></polygon>';
      }}
    }}

    function renderTicksAndLabels() {{
      const container = document.getElementById('ticks');
      if (container) {{
        container.innerHTML = '';
        const span = Math.max(1, animState.endTime - animState.startTime);
        animState.track.filter(p => p.t >= animState.startTime && p.t <= animState.endTime).forEach(p => {{
          const tick = document.createElement('div');
          tick.className = 'tick';
          tick.style.left = ((p.t - animState.startTime)/span*100) + '%';
          container.appendChild(tick);
        }});
      }}
      const sl = document.getElementById('start-label'); if (sl) sl.textContent = fmtClock(animState.startTime);
      const el = document.getElementById('end-label');   if (el) el.textContent = fmtClock(animState.endTime);
      const rl = document.getElementById('range-label');
      if (rl) {{
        const d = DURATIONS.find(([v]) => v === animState.durHours);
        rl.textContent = d ? d[1] : (animState.durHours + ' Std');
      }}
      const rd = document.getElementById('range-detail');
      if (rd) {{
        const inRange = animState.track.filter(p => p.t >= animState.startTime && p.t <= animState.endTime).length;
        rd.textContent = inRange + ' GPS-Punkte im Zeitraum · ' + fmtClock(animState.startTime) + '–' + fmtClock(animState.endTime);
      }}
    }}

    function renderSpeedPills() {{
      const c = document.getElementById('speed-pills'); if (!c) return;
      c.innerHTML = '';
      SPEEDS.forEach(v => {{
        const b = document.createElement('button');
        b.className = 'speed-pill' + (v === animState.speed ? ' active' : '');
        b.textContent = v + '×';
        b.addEventListener('click', () => {{ animState.speed = v; renderSpeedPills(); }});
        c.appendChild(b);
      }});
    }}

    function renderDurationPills() {{
      const c = document.getElementById('duration-pills'); if (!c) return;
      c.innerHTML = '';
      DURATIONS.forEach(([v, label]) => {{
        const b = document.createElement('button');
        b.className = 'duration-pill' + (v === animState.durHours ? ' active' : '');
        b.textContent = label;
        b.addEventListener('click', () => {{ applyRange(animState.startTime, v); renderDurationPills(); }});
        c.appendChild(b);
      }});
    }}

    function animLoop(nowWall) {{
      if (!animState.playing) return;
      if (animState.lastWallClock == null) animState.lastWallClock = nowWall;
      const dtSec = (nowWall - animState.lastWallClock)/1000;
      animState.lastWallClock = nowWall;
      animState.currentTime += dtSec * animState.speed * 60 * 1000;
      if (animState.currentTime >= animState.endTime) {{
        animState.currentTime = animState.endTime;
        renderAnimationFrame(); pauseAnimation(); return;
      }}
      renderAnimationFrame();
      animState.rafId = requestAnimationFrame(animLoop);
    }}

    function playAnimation() {{
      if (animState.playing || animState.startTime == null) return;
      if (animState.currentTime >= animState.endTime) animState.currentTime = animState.startTime;
      animState.playing = true; animState.lastWallClock = null;
      renderAnimationFrame();
      animState.rafId = requestAnimationFrame(animLoop);
    }}

    function pauseAnimation() {{
      if (!animState.playing) return;
      animState.playing = false;
      if (animState.rafId) cancelAnimationFrame(animState.rafId);
      renderAnimationFrame();
    }}

    function stepAnimation(dir) {{
      if (animState.startTime == null) return;
      const times = animState.track.map(p => p.t);
      if (!times.length) return;
      let next;
      if (dir > 0) {{ next = times.find(t => t > animState.currentTime); if (next == null) next = animState.endTime; }}
      else {{ const past = times.filter(t => t < animState.currentTime); next = past.length ? past[past.length-1] : animState.startTime; }}
      animState.currentTime = Math.max(animState.startTime, Math.min(animState.endTime, next));
      renderAnimationFrame();
    }}

    function applyRange(startTime, durHours) {{
      pauseAnimation();
      const maxT = animState.track.length ? animState.track[animState.track.length-1].t : startTime;
      animState.startTime = startTime;
      animState.endTime = durHours < 0 ? maxT : Math.min(maxT, startTime + durHours*3600*1000);
      animState.durHours = durHours;
      animState.currentTime = startTime;
      renderTicksAndLabels();
      renderAnimationFrame();
    }}

    function scrubFromClientX(clientX) {{
      const el = document.getElementById('track');
      if (!el || animState.startTime == null) return;
      const r = el.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (clientX - r.left)/r.width));
      pauseAnimation();
      animState.currentTime = animState.startTime + pct * (animState.endTime - animState.startTime);
      renderAnimationFrame();
    }}

    function initAnimation() {{
      animState.track = buildTrackFromCarpathian();
      animState.altFan = buildAlternativeFan();

      const hint = document.getElementById('anim-hint');
      if (!animState.track.length) {{
        if (hint) hint.textContent = 'Keine zeitgestempelten GPS-Daten geladen.';
        return false;
      }}

      const minT = animState.track[0].t;
      applyRange(minT, animState.durHours);

      const startInput = document.getElementById('anim-start');
      if (startInput && !startInput.value) {{
        const d = new Date(minT), pad = n => String(n).padStart(2,'0');
        startInput.value = `${{d.getFullYear()}}-${{pad(d.getMonth()+1)}}-${{pad(d.getDate())}}T${{pad(d.getHours())}}:${{pad(d.getMinutes())}}`;
      }}

      renderSpeedPills();
      renderDurationPills();

      let hintText = animState.track.length + ' GPS-Punkte · ';
      hintText += animState.altFan.steps.length
        ? ('Alternativen an ' + animState.altFan.steps.length + ' Schritten')
        : 'keine Alternativen geladen';
      if (hint) hint.textContent = hintText;
      return true;
    }}

    function wireAnimationControls() {{
      document.getElementById('play-btn').addEventListener('click', () => animState.playing ? pauseAnimation() : playAnimation());
      document.getElementById('step-fwd').addEventListener('click', () => {{ pauseAnimation(); stepAnimation(1); }});
      document.getElementById('step-back').addEventListener('click', () => {{ pauseAnimation(); stepAnimation(-1); }});
      document.getElementById('reset-btn').addEventListener('click', () => {{
        pauseAnimation();
        if (animState.startTime != null) {{ animState.currentTime = animState.startTime; renderAnimationFrame(); }}
      }});

      const track = document.getElementById('track');
      track.addEventListener('pointerdown', e => {{
        scrubFromClientX(e.clientX);
        const move = ev => scrubFromClientX(ev.clientX);
        const up = () => {{ window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); }};
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', up);
      }});

      const rangeToggle = document.getElementById('range-toggle');
      const rangePopover = document.getElementById('range-popover');
      rangeToggle.addEventListener('click', () => {{
        const open = rangePopover.style.display === 'block';
        rangePopover.style.display = open ? 'none' : 'block';
        rangeToggle.classList.toggle('open', !open);
      }});

      document.getElementById('anim-start').addEventListener('change', e => {{
        const t = parseTime(e.target.value);
        if (!isNaN(t)) applyRange(t, animState.durHours);
      }});
    }}

    map.on('load', () => {{
      addSourcesAndLayers();
      fitToData();
      wireMapControls();
      wireAnimationControls();
      initAnimation();
    }});
  </script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)