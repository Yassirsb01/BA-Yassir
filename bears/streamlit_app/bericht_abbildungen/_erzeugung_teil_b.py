# -*- coding: utf-8 -*-
"""Abbildungen Teil B: allgemeine Konzepte, kein Projektbezug."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, FancyArrowPatch
from matplotlib.path import Path as MplPath

OUT = os.environ.get("ABBDIR") or "bericht_abbildungen"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "axes.linewidth": 0.8,
    "hatch.linewidth": 0.6,
})

BREITE = 5.51
WEISS, HELL, MITTEL = "#ffffff", "#eceef0", "#c3c8ce"
DUNKEL, SCHWARZ = "#5a6068", "#1d2024"
TS, TM = 7.0, 8.0


def speichern(fig, name):
    pfad = os.path.join(OUT, name)
    fig.savefig(pfad, format="pdf", bbox_inches="tight", pad_inches=0.02)
    if os.environ.get("VORSCHAU"):
        fig.savefig(pfad.replace(".pdf", ".png"), dpi=190,
                    bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    print("geschrieben:", name)


def _dist_polyline(px, py, pts):
    """Kuerzester Abstand eines Punktes zu einem Linienzug."""
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
        best = min(best, ((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2) ** 0.5)
    return best


# =================================================================
# B1  Vektor- und Rasterdaten
# =================================================================
def b1():
    fig, axes = plt.subplots(1, 2, figsize=(BREITE, 3.05))

    flaeche = [(1.2, 1.4), (4.6, 1.0), (5.4, 3.6), (3.0, 4.6), (1.0, 3.4)]
    linie = [(0.6, 4.9), (2.2, 3.9), (3.4, 4.3), (4.8, 3.2), (5.8, 3.6)]
    punkt = (3.9, 2.2)

    # --- links: Vektor ---
    ax = axes[0]
    ax.set_aspect("equal")
    ax.set_xlim(0, 6.4)
    ax.set_ylim(-2.1, 5.6)
    ax.axis("off")
    ax.add_patch(Rectangle((0.1, 0.1), 6.2, 5.3, facecolor=WEISS,
                           edgecolor=SCHWARZ, lw=0.8))
    ax.add_patch(Polygon(flaeche, closed=True, facecolor=HELL,
                         edgecolor=SCHWARZ, lw=1.0, zorder=2))
    for p in flaeche:
        ax.plot(p[0], p[1], marker="o", ms=2.6, mfc=SCHWARZ, mec=SCHWARZ, zorder=4)
    xs = [p[0] for p in linie]
    ys = [p[1] for p in linie]
    ax.plot(xs, ys, color=SCHWARZ, lw=1.4, ls=(0, (5, 2)), zorder=3)
    for p in linie:
        ax.plot(p[0], p[1], marker="o", ms=2.6, mfc=WEISS, mec=SCHWARZ,
                mew=0.8, zorder=4)
    ax.plot(punkt[0], punkt[1], marker="^", ms=7, mfc=WEISS, mec=SCHWARZ,
            mew=1.1, zorder=5)

    ax.annotate("Punkt", xy=punkt, xytext=(5.4, 1.75), fontsize=TS,
                ha="center", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ))
    ax.annotate("Linie", xy=(3.4, 4.3), xytext=(1.5, 5.05), fontsize=TS,
                ha="center", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ))
    ax.annotate("Fläche", xy=(2.3, 2.6), xytext=(1.0, 0.55), fontsize=TS,
                ha="center", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ))

    ax.text(3.2, -0.45, "Vektordaten", ha="center", va="top", fontsize=TM,
            fontweight="bold")
    ax.text(3.2, -0.95,
            "Geometrien aus Stützpunkten mit\n"
            "Koordinaten, z. B. (3,9 | 2,2).\n"
            "Beliebig vergrößerbar, die Kanten\nbleiben scharf.",
            ha="center", va="top", fontsize=TS, linespacing=1.45)

    # --- rechts: Raster ---
    ax = axes[1]
    ax.set_aspect("equal")
    ax.set_xlim(0, 6.4)
    ax.set_ylim(-2.1, 5.6)
    ax.axis("off")

    poly = MplPath(flaeche)
    n = 14
    bw, bh = 6.2 / n, 5.3 / n
    for i in range(n):
        for j in range(n):
            cx = 0.1 + (i + 0.5) * bw
            cy = 0.1 + (j + 0.5) * bh
            if (cx - punkt[0]) ** 2 + (cy - punkt[1]) ** 2 < (bh * 0.8) ** 2:
                fc = DUNKEL
            elif _dist_polyline(cx, cy, linie) < 0.22:
                fc = MITTEL
            elif poly.contains_point((cx, cy)):
                fc = HELL
            else:
                fc = WEISS
            ax.add_patch(Rectangle((0.1 + i * bw, 0.1 + j * bh), bw, bh,
                                   facecolor=fc, edgecolor=MITTEL, lw=0.35))
    ax.add_patch(Rectangle((0.1, 0.1), 6.2, 5.3, facecolor="none",
                           edgecolor=SCHWARZ, lw=0.8))
    ci, cj = 8, 5
    ax.add_patch(Rectangle((0.1 + ci * bw, 0.1 + cj * bh), bw, bh,
                           facecolor="none", edgecolor=SCHWARZ, lw=1.7, zorder=6))
    ax.annotate("eine Zelle\nmit einem Wert",
                xy=(0.1 + (ci + 1) * bw, 0.1 + (cj + 0.5) * bh),
                xytext=(5.1, 1.0), fontsize=TS, ha="center", va="center",
                linespacing=1.4,
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ),
                bbox=dict(boxstyle="round,pad=0.22", fc=WEISS, ec=SCHWARZ, lw=0.5))

    ax.text(3.2, -0.45, "Rasterdaten", ha="center", va="top", fontsize=TM,
            fontweight="bold")
    ax.text(3.2, -0.95,
            "Regelmäßiges Gitter, jede Zelle trägt\n"
            "einen Wert. Die Auflösung ist fest;\n"
            "beim Vergrößern werden die Zellen\nsichtbar.",
            ha="center", va="top", fontsize=TS, linespacing=1.45)

    fig.subplots_adjust(wspace=0.04)
    speichern(fig, "abb_b1_vektor_raster.pdf")


# =================================================================
# B2  Kachelprinzip
# =================================================================
def b2():
    fig, axes = plt.subplots(1, 2, figsize=(BREITE, 3.4),
                             gridspec_kw={"width_ratios": [1.0, 1.3]})

    # --- links: Zoomstufen ---
    ax = axes[0]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.1, 4.7)
    ax.set_ylim(-3.0, 10.4)
    for z, k, y in [(0, 1, 7.4), (1, 2, 3.9), (2, 4, 0.2)]:
        t = 2.6 / k
        for i in range(k):
            for j in range(k):
                ax.add_patch(Rectangle((0.8 + i * t, y + j * t), t, t,
                                       facecolor=WEISS, edgecolor=SCHWARZ,
                                       lw=0.7))
        ax.text(0.55, y + 1.3, "z = " + str(z), ha="right", va="center",
                fontsize=TS, fontweight="bold")
        ax.text(3.6, y + 1.3, str(k * k) + " Kachel" + ("n" if k > 1 else ""),
                ha="left", va="center", fontsize=TS)
    for ya, yb in ((7.4, 6.5), (3.9, 3.0)):
        ax.add_patch(FancyArrowPatch((2.1, ya - 0.15), (2.1, yb - 0.3),
                                     arrowstyle="-|>", mutation_scale=7,
                                     lw=0.9, color=SCHWARZ))
    ax.text(2.1, -0.6,
            "Je Zoomstufe wird jede Kachel\nin vier Kacheln geteilt.",
            ha="center", va="top", fontsize=TS, linespacing=1.45)

    # --- rechts: Adressierung und sichtbarer Ausschnitt ---
    ax = axes[1]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.3, 7.1)
    ax.set_ylim(-3.0, 10.4)
    k, t = 4, 1.15
    x0, y0 = 0.3, 4.3
    sichtbar = set([(1, 1), (2, 1), (1, 2), (2, 2)])
    for i in range(k):
        for j in range(k):
            jj = k - 1 - j
            drin = (i, jj) in sichtbar
            ax.add_patch(Rectangle((x0 + i * t, y0 + j * t), t, t,
                                   facecolor=HELL if drin else WEISS,
                                   edgecolor=SCHWARZ, lw=0.7,
                                   hatch="////" if drin else None))
            ax.text(x0 + (i + 0.5) * t, y0 + (j + 0.5) * t,
                    str(i) + "/" + str(jj), ha="center", va="center",
                    fontsize=6.2, color=SCHWARZ,
                    bbox=(dict(boxstyle="square,pad=0.14", fc=WEISS, ec="none")
                          if drin else None))
    ax.add_patch(Rectangle((x0 + 1.18 * t, y0 + 1.22 * t), 1.64 * t, 1.56 * t,
                           facecolor="none", edgecolor=SCHWARZ, lw=1.8, zorder=6))
    ax.annotate("sichtbarer Ausschnitt",
                xy=(x0 + 2.8 * t, y0 + 2.76 * t),
                xytext=(x0 + 2.1 * t, y0 + 4.5 * t),
                fontsize=TS, ha="center", va="bottom", fontweight="bold",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ))
    ax.annotate("Adresse  z / x / y,\nhier  2 / 1 / 2",
                xy=(x0 + 1.5 * t, y0 + 1.5 * t),
                xytext=(x0 + 3.1 * t, y0 - 1.15 * t),
                fontsize=TS, ha="center", va="center", linespacing=1.4,
                arrowprops=dict(arrowstyle="-", lw=0.6, color=SCHWARZ),
                bbox=dict(boxstyle="round,pad=0.25", fc=WEISS, ec=SCHWARZ, lw=0.5))
    ax.text(x0 + 2.0 * t, 0.55,
            "Nur die vom Ausschnitt berührten\nKacheln werden geladen.",
            ha="center", va="top", fontsize=TS, linespacing=1.45)

    leg = [Rectangle((0, 0), 1, 1, fc=HELL, ec=SCHWARZ, hatch="////",
                     label="geladen"),
           Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, label="nicht geladen")]
    fig.legend(handles=leg, loc="lower center", ncol=2, frameon=False,
               fontsize=TS, handlelength=1.6, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(bottom=0.08, wspace=0.03)
    speichern(fig, "abb_b2_kachelprinzip.pdf")


# =================================================================
# B3  Datenquelle und Ebene in MapLibre GL JS
# =================================================================
def b3():
    fig, ax = plt.subplots(figsize=(BREITE, 3.1))
    ax.set_xlim(0, 300)
    ax.set_ylim(-16, 118)
    ax.axis("off")

    def box(x, y, w, h, text, fs=TS, weight="normal"):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=WEISS,
                               edgecolor=SCHWARZ, lw=0.8, zorder=3))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, linespacing=1.4, zorder=4, fontweight=weight)

    ax.add_patch(Rectangle((0, 0), 300, 112, facecolor=HELL,
                           edgecolor=DUNKEL, lw=0.8, zorder=1))
    ax.text(4, 106, "Style-Dokument (JSON)", ha="left", va="center",
            fontsize=TS, fontweight="bold", color=DUNKEL, zorder=5)

    box(60, 72, 180, 24,
        "Datenquelle (Source)\nGeoJSON-FeatureCollection mit allen Objekten",
        fs=TM)

    ebenen = [
        (8, "Ebene: Kreise\n(circle)", "Radius, Füllung,\nRandstärke"),
        (104, "Ebene: Linien\n(line)", "Strichstärke,\nStrichart"),
        (200, "Ebene: Beschriftung\n(symbol)", "Textfeld,\nSchriftgröße"),
    ]
    for x, titel, eig in ebenen:
        box(x, 32, 92, 22, titel, fs=TS, weight="bold")
        box(x + 8, 8, 76, 17, eig, fs=6.5)
        ax.add_patch(FancyArrowPatch((150, 72), (x + 46, 54),
                                     arrowstyle="-|>", mutation_scale=7,
                                     lw=0.9, color=SCHWARZ, zorder=2,
                                     shrinkA=0, shrinkB=0))
        ax.add_patch(FancyArrowPatch((x + 46, 32), (x + 46, 25.5),
                                     arrowstyle="-|>", mutation_scale=6,
                                     lw=0.7, color=DUNKEL, zorder=2,
                                     shrinkA=0, shrinkB=0))

    ax.text(150, -4.0,
            "Eine Datenquelle versorgt mehrere Ebenen. Was dargestellt wird, steht "
            "in der Quelle;\nwie es dargestellt wird, legen die Paint- und "
            "Layout-Eigenschaften der Ebene fest.",
            ha="center", va="top", fontsize=TS, linespacing=1.45)
    speichern(fig, "abb_b3_quelle_ebene.pdf")


if __name__ == "__main__":
    b1(); b2(); b3()
