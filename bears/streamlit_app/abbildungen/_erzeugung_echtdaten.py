# -*- coding: utf-8 -*-
"""
Abbildungen 6 und 7 aus den ECHTEN Daten des Projekts.

Kein Netzwerkzugriff: jede Socket-Verbindung wird vorher blockiert,
alle Werte stammen aus dem lokalen Rasterspeicher terrain_cache.db.
"""
import os
import sys
import math
import socket
from datetime import datetime

# Das Projektverzeichnis enthaelt einen Umlaut, den die Shell beim
# Weiterreichen zerstoert. Deshalb KEINE absoluten Pfade aus getcwd()
# bilden: die Shell setzt das Arbeitsverzeichnis, hier wird nur relativ
# importiert. Nur das Ausgabeverzeichnis ist absolut und rein ASCII.
OUT = os.environ.get("FIGDIR") or "abbildungen"
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ".")


def _blocked(*a, **k):
    raise OSError("Netzwerkzugriff blockiert")


socket.socket.connect = _blocked
socket.create_connection = _blocked

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D

import japan_comparison as jc
from terrain_cache import TerrainCache
from data.DatabaseConnection import DatabaseConnection
from data.BearSpeeds import BearSpeeds

WALD      = "#3f7d4f"
WALD_MID  = "#6ea87c"
WALD_HELL = "#9fc6a8"
GRAU      = "#b9bec4"
GRAU_D    = "#6b7177"
ROT       = "#c0392b"
BLAU      = "#2c6fa8"
BAER      = "#5d4037"
STRASSE   = "#e8c88a"
TEXT      = "#1d2024"
NEUTRAL   = "#f2f3f5"
GOLD      = "#9c7211"
RAND      = "#111318"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["text.color"] = TEXT

tc = TerrainCache()
cams = jc.load_japan_cameras()
G = tc.grid_size_deg


def mkproj(lat0, lon0):
    kx = 111320.0 * math.cos(math.radians(lat0))
    return (lambda lat, lon: ((lon - lon0) * kx, (lat - lat0) * 111320.0)), kx


def zellen(lat0, lon0, halb_m):
    dlat = halb_m / 111320.0
    dlon = halb_m / (111320.0 * math.cos(math.radians(lat0)))
    return tc.get_cells_in_box(lat0 - dlat, lon0 - dlon, lat0 + dlat, lon0 + dlon,
                               radius=150)


def flutfuellung(cells):
    """Gleiche Gruppierung wie _terrain_clusters: 8er-Nachbarschaft."""
    scored = {}
    for lat_k, lon_k, feats in cells:
        s = jc._habitat_score(feats)
        if s < jc.TERRAIN_ATTRACTIVE_MIN:
            continue
        scored[(int(round(lat_k / G)), int(round(lon_k / G)))] = (s, lat_k, lon_k)
    nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    seen, gruppen = set(), []
    for start in scored:
        if start in seen:
            continue
        stack, members = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            members.append(cur)
            for da, db in nb:
                n = (cur[0] + da, cur[1] + db)
                if n in scored and n not in seen:
                    seen.add(n)
                    stack.append(n)
        gruppen.append([(scored[m][1], scored[m][2], scored[m][0]) for m in members])
    gruppen.sort(key=lambda g: -sum(c[2] - jc.TERRAIN_ATTRACTIVE_MIN + 0.5 for c in g))
    return gruppen


def zeichne_raster(ax, cells, proj, kx):
    bw = G * kx
    bh = G * 111320.0
    for lat_k, lon_k, feats in cells:
        h = jc._habitat_score(feats)
        t = jc._score_terrain(feats)
        if h >= 3:
            fc = WALD
        elif h >= 2:
            fc = WALD_MID
        elif h >= 1:
            fc = WALD_HELL
        elif t < 0:
            fc = STRASSE
        else:
            fc = NEUTRAL
        x, y = proj(lat_k, lon_k)
        ax.add_patch(Rectangle((x - bw / 2, y - bh / 2), bw, bh, facecolor=fc,
                               edgecolor="white", lw=0.5, zorder=1))


# ===================================================================
# Abbildung 6: echte Kameras, echte Gebiete
# ===================================================================
def abb6():
    auswahl = [(3, "Kamera 002007",
                "Hier greift der Trennschritt:\nzwei getrennte Waldstücke."),
               (18, "Kamera 001000",
                "Hier gibt es nichts zu trennen:\nkein attraktives Gebiet in Reichweite.")]
    R = 620

    fig = plt.figure(figsize=(14.5, 9.2))
    fig.suptitle("Echte Daten: was der Bär an zwei echten Kamerastandorten vorfindet",
                 fontsize=19, fontweight="bold", y=0.97)

    for k, (idx, name, note) in enumerate(auswahl):
        cam = cams[idx]
        lat0, lon0 = cam["lat"], cam["lng"]
        proj, kx = mkproj(lat0, lon0)
        ax = fig.add_axes([0.045 + k * 0.49, 0.20, 0.42, 0.66])
        ax.set_aspect("equal")
        ax.axis("off")
        # Fehlende Zellen sollen neutral aussehen, nicht weiß
        ax.add_patch(Rectangle((-R, -R), 2 * R, 2 * R, facecolor=NEUTRAL,
                               edgecolor="none", zorder=0))
        zeichne_raster(ax, zellen(lat0, lon0, R), proj, kx)

        gruppen = flutfuellung(zellen(lat0, lon0, jc.CLUSTER_SEARCH_RADIUS_M))
        echte = jc._terrain_clusters((lat0, lon0), tc)
        bw, bh = G * kx, G * 111320.0
        for grp in gruppen:
            for lat_k, lon_k, _s in grp:
                x, y = proj(lat_k, lon_k)
                ax.add_patch(Rectangle((x - bw / 2, y - bh / 2), bw, bh,
                                       facecolor="none", edgecolor=RAND,
                                       lw=2.8, zorder=5))
        for gi, cl in enumerate(echte):
            x, y = proj(*cl["center"])
            ax.plot(x, y, marker="X", ms=19, color=ROT, mec="white", mew=2.3, zorder=9)
            ax.annotate(f"Gebiet {chr(65 + gi)}", xy=(x, y), xytext=(x, y - 205),
                        ha="center", fontsize=11.5, fontweight="bold", color=RAND,
                        zorder=12,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=RAND, lw=1.1),
                        arrowprops=dict(arrowstyle="->", color=RAND, lw=1.4,
                                        shrinkA=2, shrinkB=11))

        # Der Code fragt ein RECHTECK von +/-350 m ab, keinen Kreis
        # (_terrain_clusters -> get_cells_in_box). Genau so gezeichnet.
        Rm = jc.CLUSTER_SEARCH_RADIUS_M
        ax.add_patch(Rectangle((-Rm, -Rm), 2 * Rm, 2 * Rm, facecolor="none",
                               edgecolor=GOLD, lw=2.2, ls=(0, (6, 4)), zorder=6))
        ax.add_patch(Circle((0, 0), 26, facecolor=BAER, edgecolor="white", lw=1.8, zorder=10))

        ax.set_xlim(-R - 40, R + 40)
        ax.set_ylim(-1010, 800)
        ax.set_title(f"{name}  —  {len(echte)} Gebiet{'e' if len(echte) != 1 else ''} gefunden",
                     fontsize=14.5, fontweight="bold",
                     color=WALD if echte else ROT, pad=10)
        ax.text(0, 690, "350 m Suchbereich (Rechteck)", ha="center", fontsize=11.5,
                color=GOLD, fontweight="bold")
        ax.plot([-R, -R + 300], [-685, -685], color=TEXT, lw=2.6, zorder=11)
        ax.text(-R + 150, -665, "300 m", ha="center", fontsize=10.5, color=TEXT)
        ax.text(0, -790, note, ha="center", va="top", fontsize=12.3,
                color=WALD if echte else ROT)

    leg = [Line2D([], [], marker="s", ls="", ms=13, mfc=WALD, mec="white", label="Wald (+3)"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=WALD_MID, mec="white", label="Buschland (+2)"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=WALD_HELL, mec="white", label="Wiese, Feuchtgebiet (+1)"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=STRASSE, mec="white", label="Straße, Siedlung (negativ)"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=NEUTRAL, mec=GRAU, label="ohne Merkmale"),
           Line2D([], [], marker="s", ls="", ms=13, mfc="none", mec=RAND, mew=2.4,
                  label="Zellen eines Gebiets"),
           Line2D([], [], marker="X", ls="", ms=14, mfc=ROT, mec="white", label="Zielpunkt nach Formel (1)"),
           Line2D([], [], marker="o", ls="", ms=11, mfc=BAER, mec="white", label="Kamera")]
    fig.legend(handles=leg, loc="lower center", ncol=4, frameon=False,
               fontsize=11.5, bbox_to_anchor=(0.5, 0.058), columnspacing=1.6,
               handletextpad=0.5)
    fig.text(0.5, 0.012,
             "An 9 der 20 Kameras findet der Bär gar kein Gebiet, an 9 genau eines, an 2 mehr als eines.\n"
             "Deshalb greift der Trennschritt nur bei 3,4 % der Positionen.",
             ha="center", fontsize=12.3, style="italic", color=GRAU_D, linespacing=1.5)
    fig.savefig(os.path.join(OUT, "06_echte_kameras.png"), dpi=150, facecolor="white")
    plt.close(fig)
    print("geschrieben: 06_echte_kameras.png")


# ===================================================================
# Abbildung 7: derselbe Bär, derselbe Zufall, zwei Verfahren
# ===================================================================
def legacy_auswahl(current, step_length_m, rng, terrain_cache=None,
                   prev_direction=None, persistence_weight=None,
                   num_candidates=8, query_radius_m=150,
                   terrain_perception_m=None, selection_beta=None,
                   terrain_samples=None, cluster_attraction=None):
    """Wortgleiche Kopie der Richtungswahl VOR der Umstellung
    (aus tests/direction_distribution_test.py)."""
    from GeoToolBox import GeoToolBox
    pw = jc.DEFAULT_PERSISTENCE_WEIGHT if persistence_weight is None else persistence_weight
    tp = jc.DEFAULT_TERRAIN_PERCEPTION_M if terrain_perception_m is None else terrain_perception_m
    sb = jc.SELECTION_BETA if selection_beta is None else selection_beta
    cand = []
    for i in range(num_candidates):
        d = ((360.0 / num_candidates) * i + rng.uniform(-15, 15)) % 360
        score = 0.0
        dest = GeoToolBox.destination_point(current, d, step_length_m)
        if terrain_cache is not None:
            pp = GeoToolBox.destination_point(current, d, max(step_length_m, tp))
            score += jc._score_terrain(terrain_cache.get_features(pp[0], pp[1],
                                                                  radius=query_radius_m))
        if prev_direction is not None:
            score += pw * math.cos(math.radians(jc._angular_diff_deg(d, prev_direction)))
        cand.append((dest, d, score))
    sc = [c[2] for c in cand]
    mx = max(sc)
    w = [math.exp(sb * (s - mx)) for s in sc]
    d, dirn, _ = rng.choices(cand, weights=w, k=1)[0]
    return d, dirn


def lauf(cam, seed, legacy):
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    orig = jc.choose_weighted_direction
    if legacy:
        jc.choose_weighted_direction = legacy_auswahl
    try:
        return jc.simulate_free_path(
            start_lat=cam["lat"], start_lng=cam["lng"],
            start_time=datetime(2024, 6, 1, 20, 0), duration_hours=24,
            gender="F", age="A", season="summer", bear_speeds=bs,
            seed=seed, terrain_cache=tc)
    finally:
        jc.choose_weighted_direction = orig


def waldanteil(path):
    n = w = 0
    for p in path:
        f = tc.get_features(p["lat"], p["lng"], radius=150)
        n += 1
        if f.get("landuse=forest") or f.get("natural=wood"):
            w += 1
    return 100.0 * w / max(1, n)


def abb7():
    cam = cams[2]
    seed = 303
    alt = lauf(cam, seed, True)
    neu = lauf(cam, seed, False)
    w_alt, w_neu = waldanteil(alt), waldanteil(neu)
    lat0, lon0 = cam["lat"], cam["lng"]
    proj, kx = mkproj(lat0, lon0)

    pts = [(p["lat"], p["lng"]) for p in alt + neu]
    span = max(max(abs(la - lat0) * 111320 for la, lo in pts),
               max(abs(lo - lon0) * kx for la, lo in pts)) + 260

    fig = plt.figure(figsize=(13.5, 11.0))
    fig.suptitle("Ein Beispiellauf: derselbe Bär, derselbe Zufall, 24 Stunden",
                 fontsize=19, fontweight="bold", y=0.972)
    fig.text(0.5, 0.934, "Kamera 003000 — nur die Richtungswahl unterscheidet sich",
             ha="center", fontsize=13.5, color=GRAU_D)

    ax = fig.add_axes([0.05, 0.225, 0.90, 0.665])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((-span, -span), 2 * span, 2 * span, facecolor=NEUTRAL,
                           edgecolor="none", zorder=0))
    zeichne_raster(ax, zellen(lat0, lon0, span + 200), proj, kx)

    for path, col in ((alt, ROT), (neu, BLAU)):
        xs, ys = zip(*[proj(p["lat"], p["lng"]) for p in path])
        ax.plot(xs, ys, color=col, lw=2.8, alpha=.92, zorder=6, solid_capstyle="round")
        ax.plot(xs[-1], ys[-1], marker="o", ms=12, color=col, mec="white", mew=2, zorder=8)
    ax.add_patch(Circle((0, 0), span * 0.028, facecolor=BAER, edgecolor="white",
                        lw=2, zorder=9))
    ax.text(span * 0.05, span * 0.05, "Start", ha="left", va="bottom", fontsize=12.5,
            fontweight="bold", color=BAER, zorder=10,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BAER, lw=1.1))

    ax.set_xlim(-span, span)
    ax.set_ylim(-span, span)
    ax.plot([-span * 0.94, -span * 0.94 + 500], [-span * 0.92] * 2, color=TEXT, lw=2.6)
    ax.text(-span * 0.94 + 250, -span * 0.92 + span * 0.022, "500 m",
            ha="center", fontsize=11, color=TEXT)

    leg = [Line2D([], [], color=ROT, lw=3,
                  label=f"alt: 45°-Raster  —  in diesem Lauf {w_alt:.0f} % im Wald"),
           Line2D([], [], color=BLAU, lw=3,
                  label=f"neu: mit Formel (1)  —  in diesem Lauf {w_neu:.0f} % im Wald"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=WALD, mec="white", label="Wald"),
           Line2D([], [], marker="s", ls="", ms=13, mfc=STRASSE, mec="white",
                  label="Straße, Siedlung")]
    fig.legend(handles=leg, loc="lower center", ncol=2, frameon=False,
               fontsize=12, bbox_to_anchor=(0.5, 0.120), columnspacing=2.5)
    fig.text(0.5, 0.078,
             "Gleicher Startpunkt, gleiche Zufallszahlen, gleiche Tagesstrecke — "
             "der einzige Unterschied ist die Richtungswahl.",
             ha="center", fontsize=12.3, style="italic", color=GRAU_D)
    fig.text(0.5, 0.012, va="bottom",
             s="Achtung: ein einzelner Lauf, bewusst als Beispiel gewählt.\n"
             "Im Mittel über 160 Läufe beträgt der Waldanteil 34,5 % (alt) gegenüber 39,1 % (neu).",
             ha="center", fontsize=12.3, fontweight="bold", color=ROT, linespacing=1.5)
    fig.savefig(os.path.join(OUT, "07_pfadvergleich.png"), dpi=150, facecolor="white")
    plt.close(fig)
    print(f"geschrieben: 07_pfadvergleich.png  (alt {w_alt:.1f} %, neu {w_neu:.1f} %)")


if __name__ == "__main__":
    abb6()
    abb7()
