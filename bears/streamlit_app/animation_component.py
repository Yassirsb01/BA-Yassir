"""
animation_component.py
========================
Schlanke, eigenstaendige MapLibre-Karte NUR fuer die Bewegungs-Animation:
echte Carpathian-GPS-Route + zugehoerige Alternativ-Kandidaten aus
Fabians Modell (siehe sync_simulation.py) - garantiert derselbe Baer,
derselbe Tag, dieselben Zeitpunkte.

Darstellung (bewusst so gewaehlt, siehe Meeting-Protokoll 21.08.2026 -
"echte und simulierte Baeren nebeneinander, Realitaetspruefung"):
  - Blauer Punkt + Route: die ECHTE GPS-Bewegung, animiert (interpoliert
    zwischen den echten Fixpunkten).
  - Oranger "Faecher": an JEDEM echten Schritt zeigt es alle N Alternativ-
    Kandidaten, die das Modell an genau diesem Punkt/Zeitpunkt erzeugt hat -
    KEINE eigene wandernde Route (das waere fachlich falsch, da die
    Alternativen keinen zusammenhaengenden Pfad bilden, sondern N
    unabhaengige Optionen PRO Schritt sind). Der Faecher aktualisiert sich
    diskret, sobald der echte Punkt zum naechsten Schritt weiterzieht.
"""

import json
import streamlit as st
import streamlit.components.v1 as components

BASEMAP_STYLES = {
    "Liberty": "https://tiles.openfreemap.org/styles/liberty",
    "Positron": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Dark Matter": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
}


def _empty_fc():
    return {"type": "FeatureCollection", "features": []}


def render_animation_map(
    carpathian: dict | None = None,
    alternatives: dict | None = None,
    basemap: str = "Liberty",
    height: int = 750,
):
    """
    Args:
        carpathian: {"points": GeoJSON, "paths": GeoJSON} - echte GPS-Route
            EINES Baeren an EINEM Tag, volle Aufloesung.
        alternatives: GeoJSON FeatureCollection der Alternativ-Kandidaten
            (aus sync_simulation.build_synced_geojson()["alternative"]) -
            jede Alternative hat properties.timestamp EXAKT auf den
            zugehoerigen echten Schritt gesetzt.
    """
    carpathian = carpathian or {}
    cp_points = carpathian.get("points", _empty_fc())
    cp_paths = carpathian.get("paths", _empty_fc())
    alt_points = alternatives or _empty_fc()

    has_cp = bool(cp_points.get("features"))
    has_alt = bool(alt_points.get("features"))

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

    status_line = []
    if has_cp:
        status_line.append(f"Echte Route: {len(cp_points['features'])} Punkte")
    if has_alt:
        n_steps = len(set(f["properties"].get("timestamp") for f in alt_points["features"]))
        status_line.append(f"Alternativen: {len(alt_points['features'])} ({n_steps} Schritte)")
    status_text = " | ".join(status_line) if status_line else "Keine Daten geladen"

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
  <style>
    html, body {{ margin:0; padding:0; height:100%; }}
    #map {{ width:100%; height:{height}px; }}
    .panel {{
      position:absolute; z-index:2; background:rgba(255,255,255,0.96);
      border-radius:10px; padding:10px 12px;
      font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
      box-shadow:0 1px 10px rgba(0,0,0,0.18);
    }}
    .status-panel {{ top:10px; left:10px; min-width:230px; font-size:12px; color:#444; }}
    .status-panel .title {{ font-weight:700; font-size:13px; margin-bottom:4px; color:#111; }}
    .legend {{ display:flex; gap:14px; margin-top:6px; font-size:11px; }}
    .legend span {{ display:inline-flex; align-items:center; gap:4px; }}
    .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
    .bm-label {{ display:block; margin-top:8px; font-size:11px; color:#777; }}
    #basemap-select {{ width:100%; margin-top:2px; padding:3px; border-radius:6px; border:1px solid #ccc; }}

    .anim-panel {{ top:10px; right:10px; min-width:230px; }}
    .anim-panel .title {{ font-weight:700; font-size:14px; margin-bottom:6px; }}
    .anim-row {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin:5px 0; }}
    .anim-label {{ font-size:12px; color:#555; }}
    .anim-row input, .anim-row select {{ font-size:12px; padding:2px 4px; }}
    .anim-buttons {{ display:flex; gap:4px; margin:8px 0 4px; }}
    .anim-buttons button {{ flex:1; padding:6px 4px; border-radius:6px; border:1px solid #ccc;
                             background:#f7f7f7; cursor:pointer; font-size:13px; }}
    .anim-buttons button:hover {{ background:#eee; }}
    #anim-scrubber {{ width:100%; margin-top:4px; }}
    .anim-time {{ font-size:13px; text-align:center; margin-top:4px; color:#222; font-weight:700; }}
    .anim-hint {{ font-size:11px; color:#999; margin-top:6px; text-align:center; }}
  </style>
</head>
<body>
  <div id="map"></div>

  <div class="panel status-panel">
    <div class="title">Bewegungs-Animation</div>
    <div>{status_text}</div>
    <div class="legend">
      <span><span class="dot" style="background:#1d6fb8"></span> echte Route</span>
      <span><span class="dot" style="background:#e8830c"></span> Alternativen (Fächer)</span>
    </div>
    <label class="bm-label">Kartenstil</label>
    <select id="basemap-select">{bm_options}</select>
  </div>

  <div class="panel anim-panel">
    <div class="title">Steuerung</div>
    <div class="anim-row">
      <label class="anim-label">Start</label>
      <input type="datetime-local" id="anim-start" />
    </div>
    <div class="anim-row">
      <label class="anim-label">Dauer</label>
      <select id="anim-duration">
        <option value="1">1 Stunde</option>
        <option value="4" selected>4 Stunden</option>
        <option value="12">12 Stunden</option>
        <option value="24">24 Stunden</option>
        <option value="-1">Gesamter Tag</option>
      </select>
    </div>
    <div class="anim-row">
      <label class="anim-label">Tempo</label>
      <select id="anim-speed">
        <option value="1">1x</option>
        <option value="10">10x</option>
        <option value="60" selected>60x</option>
        <option value="300">300x</option>
        <option value="1000">1000x</option>
      </select>
    </div>
    <div class="anim-buttons">
      <button id="anim-step-back" title="Ein Schritt zurueck">⏮</button>
      <button id="anim-play-btn">▶ Play</button>
      <button id="anim-step-fwd" title="Ein Schritt vor">⏭</button>
      <button id="anim-reset-btn" title="Zuruecksetzen">⟲</button>
    </div>
    <input type="range" id="anim-scrubber" min="0" max="100" value="0" step="0.1" />
    <div class="anim-time" id="anim-time-label">–</div>
    <div class="anim-hint" id="anim-hint"></div>
  </div>

  <script>
    const STYLES = {styles_js};
    const DATA = {{
      cp_points:  {data["cp_points"]},
      cp_paths:   {data["cp_paths"]},
      alt_points: {data["alt_points"]}
    }};

    const map = new maplibregl.Map({{
      container: 'map',
      style: STYLES["{basemap}"],
      center: [25.3, 45.6],
      zoom: 8
    }});
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    // -------------------------------------------------------
    // Sources/Layer: statischer Referenzpfad, animierter echter Punkt,
    // und der Alternativen-Faecher (diskret, kein interpolierter Punkt)
    // -------------------------------------------------------
    function addSourcesAndLayers() {{
      const addSrc = (id, d) => {{ if (!map.getSource(id)) map.addSource(id, {{ type:'geojson', data:d }}); }};
      addSrc('cp_paths_static', DATA.cp_paths);
      addSrc('anim-trail', {{ type:'FeatureCollection', features:[] }});
      addSrc('anim-marker', {{ type:'FeatureCollection', features:[] }});
      addSrc('alt-fan', {{ type:'FeatureCollection', features:[] }});
      addSrc('alt-fan-lines', {{ type:'FeatureCollection', features:[] }});

      const addLayerSafe = (spec) => {{ if (!map.getLayer(spec.id)) map.addLayer(spec); }};

      addLayerSafe({{ id:'cp-paths-static', type:'line', source:'cp_paths_static',
        paint:{{ 'line-color':'#1d6fb8', 'line-width':2, 'line-opacity':0.22 }} }});

      // Faecher-Verbindungslinien (vom aktuellen echten Punkt zu jeder Alternative)
      addLayerSafe({{ id:'alt-fan-lines', type:'line', source:'alt-fan-lines',
        paint:{{ 'line-color':'#e8830c', 'line-width':1.2, 'line-opacity':0.5, 'line-dasharray':[1,1.5] }} }});
      addLayerSafe({{ id:'alt-fan', type:'circle', source:'alt-fan',
        paint:{{ 'circle-radius':5, 'circle-color':'#e8830c', 'circle-opacity':0.75,
                 'circle-stroke-width':1, 'circle-stroke-color':'#fff' }} }});

      addLayerSafe({{ id:'anim-trail', type:'line', source:'anim-trail',
        paint:{{ 'line-color':['coalesce',['get','color'],'#1d6fb8'],'line-width':3.5,'line-opacity':0.9 }} }});
      addLayerSafe({{ id:'anim-marker-halo', type:'circle', source:'anim-marker',
        paint:{{ 'circle-radius':12,'circle-color':['coalesce',['get','color'],'#1d6fb8'],'circle-opacity':0.25 }} }});
      addLayerSafe({{ id:'anim-marker', type:'circle', source:'anim-marker',
        paint:{{ 'circle-radius':6,'circle-color':['coalesce',['get','color'],'#1d6fb8'],
                 'circle-stroke-width':2,'circle-stroke-color':'#fff' }} }});
    }}

    function fitToData() {{
      const allCoords = [];
      (DATA.cp_points.features || []).forEach(f => {{
        const c = f.geometry && f.geometry.coordinates;
        if (c && isFinite(c[0]) && isFinite(c[1])) allCoords.push(c);
      }});
      if (!allCoords.length) return;
      let minLng=Infinity, minLat=Infinity, maxLng=-Infinity, maxLat=-Infinity;
      allCoords.forEach(([lng,lat]) => {{
        minLng=Math.min(minLng,lng); maxLng=Math.max(maxLng,lng);
        minLat=Math.min(minLat,lat); maxLat=Math.max(maxLat,lat);
      }});
      map.fitBounds([[minLng,minLat],[maxLng,maxLat]], {{ padding:70, maxZoom:14, duration:0 }});
    }}

    function wireBasemapControl() {{
      const sel = document.getElementById('basemap-select');
      if (sel) sel.addEventListener('change', e => {{
        map.setStyle(STYLES[e.target.value], {{ diff:false }});
        map.once('style.load', () => {{ addSourcesAndLayers(); renderAnimationFrame(); }});
      }});
    }}

    // -------------------------------------------------------
    // ANIMATIONS-ENGINE
    // -------------------------------------------------------
    const animState = {{
      playing:false, speed:60, track:[], altFan:{{steps:[], bySteptime:{{}}}},
      startTime:null, endTime:null, currentTime:null,
      rafId:null, lastWallClock:null,
    }};

    function parseTime(v) {{
      if (!v) return NaN;
      return Date.parse(String(v).replace(' ', 'T'));
    }}

    function buildTrackFromCarpathian() {{
      const points = [];
      (DATA.cp_points.features || []).forEach(f => {{
        const p = f.properties || {{}};
        const t = parseTime(p.timestamp);
        if (isNaN(t)) return;
        points.push({{ t, lng:f.geometry.coordinates[0], lat:f.geometry.coordinates[1], color:p.color || '#1d6fb8' }});
      }});
      points.sort((a,b)=>a.t-b.t);
      return points;
    }}

    function buildAlternativeFan() {{
      // Gruppiert die Alternativen nach ihrem Zeitstempel (= zugehoeriger
      // echter Schritt), damit sie diskret als Faecher gezeigt werden
      // koennen statt als (fachlich falsche) eigene wandernde Route.
      const bySteptime = {{}};
      (DATA.alt_points.features || []).forEach(f => {{
        const p = f.properties || {{}};
        const t = parseTime(p.timestamp);
        if (isNaN(t)) return;
        (bySteptime[t] = bySteptime[t] || []).push([f.geometry.coordinates[0], f.geometry.coordinates[1]]);
      }});
      const steps = Object.keys(bySteptime).map(Number).sort((a,b)=>a-b);
      return {{ steps, bySteptime }};
    }}

    function interpolatePosition(track, t) {{
      if (!track || track.length === 0) return null;
      if (t < track[0].t) return null;
      if (t >= track[track.length-1].t) return track[track.length-1];
      let lo=0, hi=track.length-1;
      while (hi-lo>1) {{ const mid=(lo+hi)>>1; if (track[mid].t<=t) lo=mid; else hi=mid; }}
      const a=track[lo], b=track[hi];
      const frac = b.t===a.t ? 0 : (t-a.t)/(b.t-a.t);
      return {{ lng:a.lng+(b.lng-a.lng)*frac, lat:a.lat+(b.lat-a.lat)*frac, color:a.color }};
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

    function renderAnimationFrame() {{
      // Echter Punkt: interpoliert, mit wachsendem Trail
      const pos = interpolatePosition(animState.track, animState.currentTime);
      const markerFeatures = pos ? [{{ type:'Feature', properties:{{color:pos.color}}, geometry:{{type:'Point', coordinates:[pos.lng,pos.lat]}} }}] : [];
      const trailC = trailCoords(animState.track, animState.currentTime);
      const trailFeatures = trailC.length >= 2 ? [{{ type:'Feature', properties:{{color:'#1d6fb8'}}, geometry:{{type:'LineString', coordinates:trailC}} }}] : [];

      const ms = map.getSource('anim-marker'); if (ms) ms.setData({{type:'FeatureCollection', features:markerFeatures}});
      const ts = map.getSource('anim-trail');  if (ts) ts.setData({{type:'FeatureCollection', features:trailFeatures}});

      // Alternativen-Faecher: diskret, aktualisiert sich nur beim Schrittwechsel
      const stepTime = currentFanStepTime(animState.currentTime);
      const fanCoords = stepTime != null ? (animState.altFan.bySteptime[stepTime] || []) : [];
      const fanFeatures = fanCoords.map(c => ({{ type:'Feature', properties:{{}}, geometry:{{type:'Point', coordinates:c}} }}));
      const fanLines = (pos && fanCoords.length) ? fanCoords.map(c => ({{
        type:'Feature', properties:{{}}, geometry:{{type:'LineString', coordinates:[[pos.lng,pos.lat], c]}}
      }})) : [];

      const fs = map.getSource('alt-fan'); if (fs) fs.setData({{type:'FeatureCollection', features:fanFeatures}});
      const fl = map.getSource('alt-fan-lines'); if (fl) fl.setData({{type:'FeatureCollection', features:fanLines}});

      const timeLabel = document.getElementById('anim-time-label');
      if (timeLabel) timeLabel.textContent = new Date(animState.currentTime).toLocaleString('de-DE', {{
        year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit',
      }});
      const scrubber = document.getElementById('anim-scrubber');
      if (scrubber && animState.startTime != null && animState.endTime > animState.startTime) {{
        const pct = (animState.currentTime - animState.startTime) / (animState.endTime - animState.startTime) * 100;
        scrubber.value = Math.max(0, Math.min(100, pct));
      }}
    }}

    function animLoop(nowWall) {{
      if (!animState.playing) return;
      if (animState.lastWallClock == null) animState.lastWallClock = nowWall;
      const dtSec = (nowWall - animState.lastWallClock) / 1000;
      animState.lastWallClock = nowWall;
      animState.currentTime += dtSec * animState.speed * 60 * 1000;
      if (animState.currentTime >= animState.endTime) {{
        animState.currentTime = animState.endTime;
        renderAnimationFrame();
        pauseAnimation();
        return;
      }}
      renderAnimationFrame();
      animState.rafId = requestAnimationFrame(animLoop);
    }}

    function playAnimation() {{
      if (animState.playing || animState.startTime == null) return;
      if (animState.currentTime >= animState.endTime) animState.currentTime = animState.startTime;
      animState.playing = true; animState.lastWallClock = null;
      const btn = document.getElementById('anim-play-btn'); if (btn) btn.textContent = '⏸ Pause';
      animState.rafId = requestAnimationFrame(animLoop);
    }}

    function pauseAnimation() {{
      animState.playing = false;
      if (animState.rafId) cancelAnimationFrame(animState.rafId);
      const btn = document.getElementById('anim-play-btn'); if (btn) btn.textContent = '▶ Play';
    }}

    function stepAnimation(dir) {{
      if (animState.startTime == null) return;
      const times = animState.track.map(p => p.t);
      if (!times.length) return;
      let next;
      if (dir > 0) {{
        next = times.find(t => t > animState.currentTime);
        if (next == null) next = animState.endTime;
      }} else {{
        const past = times.filter(t => t < animState.currentTime);
        next = past.length ? past[past.length-1] : animState.startTime;
      }}
      animState.currentTime = Math.max(animState.startTime, Math.min(animState.endTime, next));
      renderAnimationFrame();
    }}

    function initAnimation() {{
      animState.track = buildTrackFromCarpathian();
      animState.altFan = buildAlternativeFan();

      const hint = document.getElementById('anim-hint');
      if (!animState.track.length) {{
        if (hint) hint.textContent = 'Keine zeitgestempelten GPS-Daten gefunden.';
        return false;
      }}

      const minT = animState.track[0].t, maxT = animState.track[animState.track.length-1].t;

      const startInput = document.getElementById('anim-start');
      let start = startInput.value ? parseTime(startInput.value) : minT;
      if (isNaN(start) || start < minT || start > maxT) start = minT;

      const durHours = parseFloat(document.getElementById('anim-duration').value);
      const end = durHours < 0 ? maxT : Math.min(maxT, start + durHours * 3600 * 1000);

      animState.startTime = start; animState.endTime = end; animState.currentTime = start;

      if (!startInput.value) {{
        const d = new Date(minT);
        const pad = n => String(n).padStart(2,'0');
        startInput.value = `${{d.getFullYear()}}-${{pad(d.getMonth()+1)}}-${{pad(d.getDate())}}T${{pad(d.getHours())}}:${{pad(d.getMinutes())}}`;
      }}

      let hintText = animState.track.length + ' echte Punkte geladen.';
      if (animState.altFan.steps.length) {{
        hintText += ' Faecher an ' + animState.altFan.steps.length + ' Schritten verfuegbar.';
      }} else {{
        hintText += ' Keine Alternativen geladen.';
      }}
      if (hint) hint.textContent = hintText;
      renderAnimationFrame();
      return true;
    }}

    function wireAnimationControls() {{
      const playBtn = document.getElementById('anim-play-btn');
      if (playBtn) playBtn.addEventListener('click', () => animState.playing ? pauseAnimation() : playAnimation());

      const stepFwd = document.getElementById('anim-step-fwd');
      if (stepFwd) stepFwd.addEventListener('click', () => {{ pauseAnimation(); stepAnimation(1); }});
      const stepBack = document.getElementById('anim-step-back');
      if (stepBack) stepBack.addEventListener('click', () => {{ pauseAnimation(); stepAnimation(-1); }});

      const resetBtn = document.getElementById('anim-reset-btn');
      if (resetBtn) resetBtn.addEventListener('click', () => {{
        pauseAnimation();
        if (animState.startTime != null) {{ animState.currentTime = animState.startTime; renderAnimationFrame(); }}
      }});

      const speedSel = document.getElementById('anim-speed');
      if (speedSel) speedSel.addEventListener('change', e => {{ animState.speed = parseFloat(e.target.value); }});

      const durSel = document.getElementById('anim-duration');
      if (durSel) durSel.addEventListener('change', () => {{ pauseAnimation(); initAnimation(); }});

      const startInput = document.getElementById('anim-start');
      if (startInput) startInput.addEventListener('change', () => {{ pauseAnimation(); initAnimation(); }});

      const scrubber = document.getElementById('anim-scrubber');
      if (scrubber) scrubber.addEventListener('input', e => {{
        if (animState.startTime == null) return;
        pauseAnimation();
        const pct = parseFloat(e.target.value) / 100;
        animState.currentTime = animState.startTime + pct * (animState.endTime - animState.startTime);
        renderAnimationFrame();
      }});
    }}

    map.on('load', () => {{
      addSourcesAndLayers();
      fitToData();
      wireBasemapControl();
      wireAnimationControls();
      initAnimation();
    }});
  </script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)