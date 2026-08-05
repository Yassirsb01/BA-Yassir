"""
maplibre_component.py
=====================
Gemeinsame MapLibre-Hauptkarte fuer alle drei Systeme.

Bugfixes gegenueber vorheriger Version:
  - setStyle() + map.once('style.load') + diff:false -> zuverlässige Layer-Wiederherstellung
  - addLayer mit beforeId (vor erstem Symbol-Layer) -> Städte-/Ländernamen bleiben sichtbar
"""

import json
import streamlit.components.v1 as components


BASEMAP_NAMES = ["Liberty", "Bright", "Positron", "Dark", "OSM Raster", "Esri Satellite"]


def _build_styles():
    """Alle Stile als dict {Name: URL-String oder Style-Objekt}."""
    vector = {
        "Liberty":  "https://tiles.openfreemap.org/styles/liberty",
        "Bright":   "https://tiles.openfreemap.org/styles/bright",
        "Positron": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "Dark":     "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    }
    raster = {
        "OSM Raster": {
            "version": 8,
            "sources": {"osm": {
                "type": "raster",
                "tiles": ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                          "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
                          "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"],
                "tileSize": 256, "attribution": "(c) OpenStreetMap contributors"}},
            "layers": [{"id": "osm", "type": "raster", "source": "osm"}],
        },
        "Esri Satellite": {
            "version": 8,
            "sources": {"esri": {
                "type": "raster",
                "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                "tileSize": 256, "attribution": "Tiles (c) Esri"}},
            "layers": [{"id": "esri", "type": "raster", "source": "esri"}],
        },
    }
    return {**vector, **raster}


def _empty_fc():
    return {"type": "FeatureCollection", "features": []}


def render_maplibre(
    japan=None,
    carpathian=None,
    simulation=None,
    wolf_lynx=None,
    gbif_bears=None,
    basemap: str = "Liberty",
    center=None,
    zoom: float = None,
    initial_visible: set = None,
    refit_on_load: set = None,
    height: int = 650,
):
    japan = japan or {}
    carpathian = carpathian or {}
    simulation = simulation or {}
    wolf_lynx = wolf_lynx or {}
    gbif_bears = gbif_bears or {}

    jp_deterrents = japan.get("deterrents", _empty_fc())
    jp_markers    = japan.get("markers", _empty_fc())
    jp_polygons   = japan.get("polygons", _empty_fc())
    cp_points     = carpathian.get("points", _empty_fc())
    cp_paths      = carpathian.get("paths", _empty_fc())
    sim_points    = simulation.get("points", _empty_fc())
    sim_paths     = simulation.get("paths", _empty_fc())
    # wolf_lynx / gbif_bears kommen bereits als fertige FeatureCollection
    # (nicht wie die anderen als dict mit Unterkategorien) -> direkt uebernehmen.
    wolf_lynx_fc  = wolf_lynx if wolf_lynx.get("type") == "FeatureCollection" else _empty_fc()
    gbif_bears_fc = gbif_bears if gbif_bears.get("type") == "FeatureCollection" else _empty_fc()

    has_japan = bool(japan)
    has_carpathian = bool(carpathian)
    has_simulation = bool(simulation)
    has_wolf_lynx = bool(wolf_lynx_fc.get("features"))
    has_gbif_bears = bool(gbif_bears_fc.get("features"))

    if center is None:
        center = (45.0, 80.0)
    center_lat, center_lng = center
    if zoom is None:
        zoom = 2
    if basemap not in BASEMAP_NAMES:
        basemap = "Liberty"

    styles_js = json.dumps(_build_styles())
    refit_json = json.dumps(sorted(refit_on_load)) if refit_on_load else "[]"

    data = {
        "jp_deterrents": json.dumps(jp_deterrents),
        "jp_markers":    json.dumps(jp_markers),
        "jp_polygons":   json.dumps(jp_polygons),
        "cp_points":     json.dumps(cp_points),
        "cp_paths":      json.dumps(cp_paths),
        "sim_points":    json.dumps(sim_points),
        "sim_paths":     json.dumps(sim_paths),
        "wolf_lynx":     json.dumps(wolf_lynx_fc),
        "gbif_bears":    json.dumps(gbif_bears_fc),
    }

    # Welche Layer sollen beim Rendern schon angehakt sein?
    # - initial_visible kommt aus den URL-Query-Parametern (letzter bekannter
    #   Zustand vom Client) -> exakt das wiederherstellen.
    # - Erststart (noch keine URL-Parameter, initial_visible is None) ->
    #   alte Default-Logik: Simulation vorausgewaehlt, Rest aus.
    if initial_visible is None:
        default_checked = {"simulation"} if has_simulation else set()
    else:
        default_checked = set(initial_visible)

    checkbox_rows = ""
    if has_japan:
        n = len(jp_deterrents.get("features", [])) + len(jp_markers.get("features", []))
        chk = " checked" if "japan" in default_checked else ""
        checkbox_rows += (f'<label><input type="checkbox" id="tg-japan"{chk} /> '
                          f'Japan Deterrents <span class="cnt">{n}</span>'
                          f'<span class="dot" style="background:#d33"></span></label>')
    if has_carpathian:
        n = len(cp_points.get("features", []))
        chk = " checked" if "carpathian" in default_checked else ""
        checkbox_rows += (f'<label><input type="checkbox" id="tg-carpathian"{chk} /> '
                          f'Carpathian GPS <span class="cnt">{n}</span>'
                          f'<span class="dot" style="background:#1d6fb8"></span></label>')
    if has_simulation:
        n = len(sim_points.get("features", []))
        chk = " checked" if "simulation" in default_checked else ""
        checkbox_rows += (f'<label><input type="checkbox" id="tg-simulation"{chk} /> '
                          f'Simulation <span class="cnt">{n}</span>'
                          f'<span class="dot" style="background:#e8830c"></span></label>')
    if has_wolf_lynx:
        n = len(wolf_lynx_fc.get("features", []))
        chk = " checked" if "wolf_lynx" in default_checked else ""
        checkbox_rows += (f'<label><input type="checkbox" id="tg-wolf-lynx"{chk} /> '
                          f'Wolf/Luchs (BfN) <span class="cnt">{n}</span>'
                          f'<span class="dot" style="background:#5b3a29"></span></label>')
    if has_gbif_bears:
        n = len(gbif_bears_fc.get("features", []))
        chk = " checked" if "gbif_bears" in default_checked else ""
        checkbox_rows += (f'<label><input type="checkbox" id="tg-gbif-bears"{chk} /> '
                          f'Bär-Sichtungen (GBIF) <span class="cnt">{n}</span>'
                          f'<span class="dot" style="background:#c77b2e"></span></label>')
    if not checkbox_rows:
        checkbox_rows = '<div class="muted">Keine Daten geladen.</div>'

    bm_options = "".join(
        f'<option value="{name}"{" selected" if name == basemap else ""}>{name}</option>'
        for name in BASEMAP_NAMES
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; }}
    #map {{ width: 100%; height: {height}px; }}
    .panel {{
      position: absolute; top: 10px; left: 10px; z-index: 2;
      background: rgba(255,255,255,0.96); border-radius: 10px;
      padding: 10px 12px; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      box-shadow: 0 1px 10px rgba(0,0,0,0.18); min-width: 230px;
    }}
    .panel .title {{ font-weight: 700; margin-bottom: 8px; font-size: 14px; }}
    .panel label {{ display: flex; align-items: center; gap: 8px; margin: 6px 0;
                    cursor: pointer; font-size: 13px; }}
    .cnt {{ color:#888; font-size:11px; margin-left:auto; }}
    .dot {{ display:inline-block; width:11px; height:11px; border-radius:50%; margin-left:8px; }}
    .muted {{ color:#666; font-size:12px; }}
    .sep {{ border-top:1px solid #e6e6e6; margin:9px 0 7px; }}
    .bm-label {{ font-size:12px; color:#555; display:block; margin-bottom:4px; }}
    #basemap-select {{ width:100%; padding:5px 6px; border-radius:6px;
                       border:1px solid #ccc; font-size:13px; background:#fff; cursor:pointer; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="panel">
    <div class="title">Layer anzeigen</div>
    {checkbox_rows}
    <div class="sep"></div>
    <label class="bm-label">Kartenstil</label>
    <select id="basemap-select">{bm_options}</select>
  </div>

  <script>
    const STYLES = {styles_js};
    // Layer, deren Daten sich seit dem letzten Rendern geaendert haben
    // (z.B. anderer Baer/Zeitraum ausgewaehlt) -> beim Laden automatisch
    // dorthin navigieren, auch wenn der Layer schon vorher sichtbar war.
    const REFIT_ON_LOAD = {refit_json};
    const DATA = {{
      jp_deterrents: {data["jp_deterrents"]},
      jp_markers:    {data["jp_markers"]},
      jp_polygons:   {data["jp_polygons"]},
      cp_points:     {data["cp_points"]},
      cp_paths:      {data["cp_paths"]},
      sim_points:    {data["sim_points"]},
      sim_paths:     {data["sim_paths"]},
      wolf_lynx:     {data["wolf_lynx"]},
      gbif_bears:    {data["gbif_bears"]}
    }};

    const GROUPS = {{
      japan:      {{ id:'tg-japan',      layers:['jp-deterrents','jp-markers','jp-polygons-fill','jp-polygons-line'],
                     fcs:[DATA.jp_deterrents, DATA.jp_markers, DATA.jp_polygons] }},
      carpathian: {{ id:'tg-carpathian', layers:['cp-points','cp-paths'],
                     fcs:[DATA.cp_points, DATA.cp_paths] }},
      simulation: {{ id:'tg-simulation', layers:['sim-points','sim-paths'],
                     fcs:[DATA.sim_points, DATA.sim_paths] }},
      wolf_lynx:  {{ id:'tg-wolf-lynx',  layers:['wolf-lynx-fill','wolf-lynx-line'],
                     fcs:[DATA.wolf_lynx] }},
      gbif_bears: {{ id:'tg-gbif-bears', layers:['gbif-bears-points'],
                     fcs:[DATA.gbif_bears] }}
    }};

    const map = new maplibregl.Map({{
      container: 'map',
      style: STYLES["{basemap}"],
      center: [{center_lng}, {center_lat}],
      zoom: {zoom}
    }});
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    // -------------------------------------------------------
    // Zustand (Center/Zoom/Basemap/sichtbare Layer) in die URL des
    // umgebenden Streamlit-Fensters schreiben. So kann Python beim naechsten
    // Rerun (z.B. Filter "Anwenden") ueber st.query_params genau dort wieder
    // starten, statt die Karte auf die Default-Ansicht zurueckzusetzen.
    // Kein echter Rueckkanal (das koennte nur eine declare_component()-
    // Loesung), aber ausreichend, um den Kamera-/Layer-Zustand zwischen
    // Reruns "mitzunehmen".
    // -------------------------------------------------------
    let currentStyleName = "{basemap}";

    function debounce(fn, wait) {{
      let t;
      return (...args) => {{ clearTimeout(t); t = setTimeout(() => fn(...args), wait); }};
    }}

    function saveStateToUrl() {{
      try {{
        const parentWin = window.parent;
        if (!parentWin || parentWin === window) return;

        const params = new URLSearchParams(parentWin.location.search);
        const c = map.getCenter();
        params.set('m_lat', c.lat.toFixed(5));
        params.set('m_lng', c.lng.toFixed(5));
        params.set('m_zoom', map.getZoom().toFixed(2));
        params.set('m_style', currentStyleName);

        const visible = Object.keys(GROUPS).filter(k => {{
          const cb = document.getElementById(GROUPS[k].id);
          return cb && cb.checked;
        }});
        params.set('m_layers', visible.join(','));

        const newUrl = parentWin.location.pathname + '?' + params.toString() + parentWin.location.hash;
        parentWin.history.replaceState(null, '', newUrl);
      }} catch (e) {{
        // z.B. Cross-Origin-Restriktion -> stumm ignorieren, Karte bleibt
        // trotzdem normal nutzbar, nur ohne Zustands-Persistenz.
      }}
    }}

    const saveStateDebounced = debounce(saveStateToUrl, 400);

    // -------------------------------------------------------
    // FIX 2: ID des ersten Symbol-Layers finden.
    // Eigene Layer werden DAVOR eingefuegt, damit Vektor-Labels
    // (Stadte, Laender) weiterhin UEBER unseren Daten gerendert werden.
    // Rasterstile haben keine Symbol-Layer -> beforeId = undefined -> normal anhaengen.
    // -------------------------------------------------------
    function firstSymbolLayerId() {{
      const layers = (map.getStyle() || {{}}).layers || [];
      for (const l of layers) {{
        if (l.type === 'symbol') return l.id;
      }}
      return undefined;
    }}

    function addLayerSafe(spec) {{
      if (map.getLayer(spec.id)) return;
      map.addLayer(spec, firstSymbolLayerId());  // immer VOR Labels
    }}

    function setVis(ids, vis) {{
      ids.forEach(id => {{
        if (map.getLayer(id))
          map.setLayoutProperty(id, 'visibility', vis ? 'visible' : 'none');
      }});
    }}

    // -------------------------------------------------------
    // Quellen + Layer hinzufuegen (idempotent)
    // -------------------------------------------------------
    function addSourcesAndLayers() {{
      const addSrc = (id, d) => {{ if (!map.getSource(id)) map.addSource(id, {{ type:'geojson', data:d }}); }};
      addSrc('jp_deterrents', DATA.jp_deterrents);
      addSrc('jp_markers',    DATA.jp_markers);
      addSrc('jp_polygons',   DATA.jp_polygons);
      addSrc('cp_points',     DATA.cp_points);
      addSrc('cp_paths',      DATA.cp_paths);
      addSrc('sim_points',    DATA.sim_points);
      addSrc('sim_paths',     DATA.sim_paths);
      addSrc('wolf_lynx',     DATA.wolf_lynx);
      addSrc('gbif_bears',    DATA.gbif_bears);

      // JAPAN
      addLayerSafe({{ id:'jp-polygons-fill', type:'fill', source:'jp_polygons',
        paint:{{ 'fill-color':'#2a8f2a','fill-opacity':0.20 }} }});
      addLayerSafe({{ id:'jp-polygons-line', type:'line', source:'jp_polygons',
        paint:{{ 'line-color':'#2a8f2a','line-width':2 }} }});
      addLayerSafe({{ id:'jp-deterrents', type:'circle', source:'jp_deterrents',
        paint:{{ 'circle-radius':7,'circle-color':'#d33','circle-stroke-width':2,'circle-stroke-color':'#fff' }} }});
      addLayerSafe({{ id:'jp-markers', type:'circle', source:'jp_markers',
        paint:{{ 'circle-radius':7,'circle-color':'#3186cc','circle-stroke-width':2,'circle-stroke-color':'#fff' }} }});

      // CARPATHIAN
      addLayerSafe({{ id:'cp-paths', type:'line', source:'cp_paths',
        paint:{{ 'line-width':3,'line-opacity':0.85,'line-color':['coalesce',['get','color'],'#1d6fb8'] }} }});
      addLayerSafe({{ id:'cp-points', type:'circle', source:'cp_points',
        paint:{{ 'circle-radius':4,'circle-opacity':0.9,'circle-stroke-width':1,'circle-stroke-color':'#fff',
                 'circle-color':['coalesce',['get','color'],'#1d6fb8'] }} }});

      // SIMULATION
      // Linie: realer GPS-Pfad (blau, gestrichelt)
      addLayerSafe({{ id:'sim-paths', type:'line', source:'sim_paths',
        paint:{{ 'line-width':3,
                 'line-color':['coalesce',['get','color'],'#1565c0'],
                 'line-dasharray':[2,2],
                 'line-opacity':0.9 }} }});
      // Punkte: echte Schritte (blau, größer) + Alternativen (orange, kleiner)
      // Farbe und Radius werden per Feature-Property gesteuert.
      addLayerSafe({{ id:'sim-points', type:'circle', source:'sim_points',
        paint:{{
          'circle-color': ['coalesce',['get','color'],'#ff9800'],
          'circle-radius': ['case',['==',['get','type'],'real'],7,5],
          'circle-opacity': ['case',['==',['get','type'],'real'],0.95,0.70],
          'circle-stroke-width': ['case',['==',['get','type'],'real'],2,1],
          'circle-stroke-color': '#fff'
        }} }});

      // WOLF/LUCHS (BfN, besetzte 10x10km Rasterzellen als Polygone).
      // Bewusst nur duenner Umriss statt kraeftiger Flaechenfuellung: die
      // Zelle bedeutet "irgendwo hier mind. 1 C1/C2-Nachweis", nicht eine
      // praezise Position. Eine kraeftige Fuellung wuerde eine Genauigkeit
      // vortaeuschen, die die Daten nicht hergeben - und mehrere angrenzende
      // Zellen wirken sonst wie eine durchgehende Flaeche ("Blanket-Effekt").
      addLayerSafe({{ id:'wolf-lynx-fill', type:'fill', source:'wolf_lynx',
        paint:{{ 'fill-color':['coalesce',['get','color'],'#5b3a29'],'fill-opacity':0.08 }} }});
      addLayerSafe({{ id:'wolf-lynx-line', type:'line', source:'wolf_lynx',
        paint:{{ 'line-color':['coalesce',['get','color'],'#5b3a29'],'line-width':1.2,'line-opacity':0.8 }} }});

      // BÄR-SICHTUNGEN (GBIF, Punkte DE+RO)
      addLayerSafe({{ id:'gbif-bears-points', type:'circle', source:'gbif_bears',
        paint:{{ 'circle-radius':5,'circle-opacity':0.85,'circle-stroke-width':1,'circle-stroke-color':'#fff',
                 'circle-color':['coalesce',['get','color'],'#5b3a29'] }} }});
    }}

    // Sichtbarkeit aus den Checkboxen (DOM bleibt erhalten) wiederherstellen
    function applyVisibilityFromCheckboxes() {{
      Object.values(GROUPS).forEach(g => {{
        const cb = document.getElementById(g.id);
        setVis(g.layers, cb ? cb.checked : false);
      }});
    }}

    // -------------------------------------------------------
    // Popups (werden nur einmal registriert)
    // -------------------------------------------------------
    function wirePopups() {{
      const pop = (e, html) => new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map);

      map.on('click','jp-deterrents',(e)=>{{ const p=e.features[0].properties||{{}};
        pop(e,'<h3>Deterrent</h3><b>ID:</b> '+(p.directory_name||p.id||'N/A')+
              '<br><b>Device Images:</b> '+(p.device_count||0)+
              '<br><b>Trail Images:</b> '+(p.trail_count||0)); }});
      map.on('mouseenter','jp-deterrents',()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave','jp-deterrents',()=>map.getCanvas().style.cursor='');

      map.on('click','jp-markers',(e)=>{{ const p=e.features[0].properties||{{}};
        pop(e,'<h3>Custom Marker</h3><b>ID:</b> '+(p.id||'N/A')+
              '<br><b>Time:</b> '+(p.timestamp||'')); }});

      map.on('click','cp-points',(e)=>{{ const p=e.features[0].properties||{{}};
        const col=p.color||'#1d6fb8';
        pop(e,'<h3>Bear '+(p.bear_id||'')+
              ' <span style=\\"display:inline-block;width:12px;height:12px;border-radius:50%;background:'+col+';vertical-align:middle\\"></span></h3>'+
              '<b>Time:</b> '+(p.timestamp||'')+'<br><b>Sex:</b> '+(p.sex||'')+
              '<br><b>Age:</b> '+(p.age||'')+'<br><b>Season:</b> '+(p.season||'')); }});
      map.on('mouseenter','cp-points',()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave','cp-points',()=>map.getCanvas().style.cursor='');

      map.on('click','sim-points',(e)=>{{ const p=e.features[0].properties||{{}};
        const isReal = p.type==='real';
        const isAlt  = p.type==='alternative';
        const title  = isReal ? 'Echter GPS-Schritt' : isAlt ? 'Simulierte Alternative' : 'Simulation';
        const col    = p.color||'#e8830c';
        let details  = '<b>Bär:</b> '+(p.bear_id||'')+'<br>';
        if (isReal) details += '<b>Zeit:</b> '+(p.timestamp||'')+'<br><b>Saison:</b> '+(p.season||'')+'<br><b>Schrittlänge:</b> '+(p.length_m?Math.round(p.length_m)+'m':'')+'<br>';
        if (isAlt)  details += '<b>Schritt #:</b> '+(p.step_idx||'')+'<br><b>Sim. Länge:</b> '+(p.length_m?Math.round(p.length_m)+'m':'')+'<br><b>Richtung:</b> '+(p.angle?Math.round(p.angle)+'°':'')+'<br>';
        pop(e,'<h3>'+title+' <span style=\\"display:inline-block;width:10px;height:10px;border-radius:50%;background:'+col+';vertical-align:middle\\"></span></h3>'+details); }});

      map.on('click','wolf-lynx-fill',(e)=>{{ const p=e.features[0].properties||{{}};
        const isWolf = (p.REFERENCESPECIESNAME||'').toLowerCase().includes('lupus') || p.species==='wolf';
        const title  = isWolf ? 'Wolf' : 'Luchs';
        pop(e,'<h3>'+title+' (BfN-Monitoring)</h3>'+
              '<b>Rasterzelle:</b> '+(p.ID_LOCALID||p.GmlID||'')+
              '<br><span style=\\"font-size:12px;color:#555\\">Mind. 1 bestätigter Nachweis (C1/C2: Genetik, '+
              'Foto, Spur, Riss o.ä.) irgendwo in dieser 10x10km-Zelle - keine exakte Position.</span>'+
              '<br><span style=\\"font-size:11px;color:#777\\">Quelle: geodienste.bfn.de, kostenfrei nutzbar</span>'); }});
      map.on('mouseenter','wolf-lynx-fill',()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave','wolf-lynx-fill',()=>map.getCanvas().style.cursor='');

      map.on('click','gbif-bears-points',(e)=>{{ const p=e.features[0].properties||{{}};
        const link = p.gbif_url ? '<br><a href=\\"'+p.gbif_url+'\\" target=\\"_blank\\" rel=\\"noopener\\">Datensatz auf GBIF ansehen</a>' : '';
        pop(e,'<h3>'+(p.scientific_name||'Ursus arctos')+'</h3>'+
              '<b>Land:</b> '+(p.country||'')+
              '<br><b>Datum:</b> '+(p.event_date||'')+
              '<br><b>Quelle:</b> '+(p.institution||'')+link); }});
      map.on('mouseenter','gbif-bears-points',()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave','gbif-bears-points',()=>map.getCanvas().style.cursor='');
    }}

    // -------------------------------------------------------
    // Bounds + Toggle + Kartenstil-Wechsel
    // -------------------------------------------------------
    // Koordinate ist gueltig wenn sie nicht (0,0) oder fast (0,0) ist.
    // Devices ohne GPS werden mit lat=0, lng=0 gespeichert und
    // wuerden sonst fitBounds auf Weltansicht aufweiten.
    function isValidCoord(c) {{
      return Math.abs(c[0]) > 0.01 || Math.abs(c[1]) > 0.01;
    }}

    function boundsOf(fcs) {{
      const b = new maplibregl.LngLatBounds(); let has = false;
      fcs.forEach(fc => {{
        (fc.features || []).forEach(f => {{
          const g = f.geometry; if (!g) return;
          if (g.type === 'Point') {{
            if (isValidCoord(g.coordinates)) {{ b.extend(g.coordinates); has = true; }}
          }}
          else if (g.type === 'LineString') {{
            g.coordinates.forEach(c => {{ if (isValidCoord(c)) {{ b.extend(c); has = true; }} }});
          }}
          else if (g.type === 'Polygon') {{
            g.coordinates.forEach(r => r.forEach(c => {{ if (isValidCoord(c)) {{ b.extend(c); has = true; }} }}));
          }}
          else if (g.type === 'MultiPolygon') {{
            g.coordinates.forEach(poly => poly.forEach(r => r.forEach(c => {{ if (isValidCoord(c)) {{ b.extend(c); has = true; }} }})));
          }}
        }});
      }});
      return has ? b : null;
    }}

    // Feste Zoom-Ziele pro System (vermeidet fitBounds-Probleme mit (0,0)-Koordinaten)
    const ZOOM_TARGETS = {{
      japan:      {{ center: [139.93, 37.48], zoom: 11 }},
      carpathian: {{ center: null, zoom: 8 }},   // dynamisch via fitBounds (Daten haben valide Koordinaten)
      simulation: {{ center: null, zoom: 8 }},   // dynamisch via fitBounds
      wolf_lynx:  {{ center: null, zoom: 6 }},   // dynamisch, deckt ganz Deutschland ab
      gbif_bears: {{ center: null, zoom: 5 }}    // dynamisch, deckt DE+RO ab
    }};

    function navigateToGroup(groupKey) {{
      const g = GROUPS[groupKey];
      const t = ZOOM_TARGETS[groupKey];
      if (t.center) {{
        // Festes Ziel (z.B. Japan) -> kein fitBounds noetig
        map.flyTo({{ center: t.center, zoom: t.zoom, duration: 800 }});
      }} else {{
        // Dynamisch: fitBounds aus den Daten
        const b = boundsOf(g.fcs);
        if (b) map.fitBounds(b, {{ padding: 60, maxZoom: 12, duration: 800 }});
      }}
    }}

    function onToggle(groupKey, checked) {{
      const g = GROUPS[groupKey];
      setVis(g.layers, checked);
      if (checked) navigateToGroup(groupKey);
      saveStateToUrl();
    }}

    function wireControls() {{
      const bind = (key) => {{
        const cb = document.getElementById(GROUPS[key].id);
        if (cb) cb.addEventListener('change', e => onToggle(key, e.target.checked));
      }};
      bind('japan'); bind('carpathian'); bind('simulation'); bind('wolf_lynx'); bind('gbif_bears');

      // -------------------------------------------------------
      // FIX 1: Kartenstil-Wechsel
      //   map.once('style.load', ...) nach jedem setStyle() stellt
      //   Layer sicher NACH dem vollstaendigen Style-Reset wieder her.
      //   diff:false -> sauberer Reset ohne Race Condition.
      // -------------------------------------------------------
      const sel = document.getElementById('basemap-select');
      if (sel) sel.addEventListener('change', e => {{
        currentStyleName = e.target.value;
        map.setStyle(STYLES[e.target.value], {{ diff: false }});
        map.once('style.load', () => {{
          addSourcesAndLayers();
          applyVisibilityFromCheckboxes();
        }});
        saveStateToUrl();
      }});

      // Kamera-Position (Pan/Zoom) laufend merken, debounced damit nicht
      // bei jedem einzelnen Drag-Frame geschrieben wird.
      map.on('moveend', saveStateDebounced);
    }}

    // Initialer Start: map.on('load') feuert genau einmal
    map.on('load', () => {{
      addSourcesAndLayers();
      applyVisibilityFromCheckboxes();
      wirePopups();
      wireControls();

      // Fuer bereits sichtbare Layer, deren Daten sich geaendert haben
      // (z.B. neuer Baer/Zeitraum via "Anwenden"), zur neuen Position fliegen -
      // sonst bleibt die Kamera an der alten Stelle stehen (Persistenz-Fix),
      // obwohl dort gar keine Daten des neu gewaehlten Filters liegen.
      let didRefit = false;
      REFIT_ON_LOAD.forEach(key => {{
        const g = GROUPS[key];
        const cb = g ? document.getElementById(g.id) : null;
        if (cb && cb.checked) {{ navigateToGroup(key); didRefit = true; }}
      }});
      if (didRefit) saveStateToUrl();
    }});
  </script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)