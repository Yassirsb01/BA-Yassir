# -*- coding: utf-8 -*-
"""Abbildungen Teil A fuer den Bachelorarbeitsbericht (aus dem Repository)."""
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle, Wedge
from matplotlib.lines import Line2D

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

BREITE = 5.51          # 14 cm
WEISS  = "#ffffff"
HELL   = "#eceef0"
MITTEL = "#c3c8ce"
DUNKEL = "#5a6068"
SCHWARZ = "#1d2024"

TS, TM, TL = 7.0, 8.0, 9.5


def speichern(fig, name):
    pfad = os.path.join(OUT, name)
    fig.savefig(pfad, format="pdf", bbox_inches="tight", pad_inches=0.02)
    if os.environ.get("VORSCHAU"):
        fig.savefig(pfad.replace(".pdf", ".png"), dpi=190,
                    bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    print("geschrieben:", name)


def kasten(ax, x, y, w, h, text, fc=WEISS, ec=SCHWARZ, lw=0.8, fs=TS,
           hatch=None, style="normal", weight="normal", z=3):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=lw, hatch=hatch, zorder=z))
    # Auf schraffierten Flaechen braucht die Beschriftung einen weissen
    # Grund, sonst ist sie im Druck nicht lesbar.
    bb = dict(boxstyle="square,pad=0.22", fc=WEISS, ec="none") if hatch else None
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=SCHWARZ, zorder=z + 1, linespacing=1.35,
            style=style, fontweight=weight, bbox=bb)


def pfeil(ax, x1, y1, x2, y2, lw=0.9, ls="-", color=SCHWARZ):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=7, linewidth=lw,
                                 linestyle=ls, color=color, zorder=2,
                                 shrinkA=0, shrinkB=0))


# =================================================================
# A1  Architektur des Ausgangszustands
# =================================================================
def a1():
    fig, ax = plt.subplots(figsize=(BREITE, 3.9))
    ax.set_xlim(0, 300)
    ax.set_ylim(-34, 118)
    ax.axis("off")

    spalten = [
        (4, "Bärenabschreckung\nJapan", "Vorarbeit Lorenz",
         "Streamlit", "Folium / Leaflet", True,
         "MariaDB\ndeterrent_devices,\nimage_metadata,\nmarkers, polygons"),
        (103, "Bewegungssimulation\nKarpaten", "Vorarbeit Bräu",
         "Dash", "Folium / Leaflet,\nPlotly", True,
         "lokale SQLite\ndatabase.db\n+ CSV-Dateien\n1_bears_RO.csv"),
        (202, "Bildextraktion\naus E-Mails", "Vorarbeit Lelchat",
         "Skript ohne\nOberfläche", "keine Kartenansicht", False,
         "MariaDB\nwildlife_images\n+ Microsoft\nGraph API"),
    ]
    B = 94
    for x, titel, herkunft, ober, karte, hat_karte, daten in spalten:
        ax.add_patch(Rectangle((x, 4), B, 104, facecolor=HELL,
                               edgecolor=DUNKEL, linewidth=0.8, zorder=1))
        ax.text(x + B / 2, 100, titel, ha="center", va="center",
                fontsize=TM, fontweight="bold", color=SCHWARZ, zorder=5,
                linespacing=1.3)
        ax.text(x + B / 2, 90, herkunft, ha="center", va="center",
                fontsize=TS, style="italic", color=DUNKEL, zorder=5)
        kasten(ax, x + 6, 70, B - 12, 14, ober, fc=WEISS)
        if hat_karte:
            kasten(ax, x + 6, 46, B - 12, 18, karte, fc=WEISS, hatch="////")
            pfeil(ax, x + B / 2, 46, x + B / 2, 40.5)
        else:
            ax.add_patch(Rectangle((x + 6, 46), B - 12, 18, facecolor=WEISS,
                                   edgecolor=MITTEL, linewidth=0.8,
                                   linestyle=(0, (3, 2)), zorder=3))
            ax.text(x + B / 2, 55, karte, ha="center", va="center",
                    fontsize=TS, style="italic", color=DUNKEL, zorder=4)
        kasten(ax, x + 6, 9, B - 12, 31, daten, fc=WEISS)
        pfeil(ax, x + B / 2, 70, x + B / 2, 64.5)

    for xt in (99.5, 198.5):
        ax.plot([xt, xt], [0, 114], color=SCHWARZ, lw=1.0,
                ls=(0, (3, 3)), zorder=6)

    ax.text(150, -4.0,
            "Drei getrennte Anwendungen mit je eigener Kartenansicht und eigener "
            "Datenhaltung.\nEin gemeinsamer Blick auf alle Bestände ist nicht möglich.",
            ha="center", va="top", fontsize=TS, color=SCHWARZ, linespacing=1.45)

    leg = [Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, hatch="////",
                     label="Kartendarstellung"),
           Rectangle((0, 0), 1, 1, fc=WEISS, ec=MITTEL, ls=(0, (3, 2)),
                     label="nicht vorhanden")]
    ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, 0.005),
              frameon=False, fontsize=TS, ncol=2, handlelength=1.6)
    speichern(fig, "abb_a1_ausgangszustand.pdf")


# =================================================================
# A2  Zielarchitektur
# =================================================================
def a2():
    fig, ax = plt.subplots(figsize=(BREITE, 4.4))
    ax.set_xlim(0, 300)
    ax.set_ylim(-12, 150)
    ax.axis("off")

    def band(y, h, name):
        ax.add_patch(Rectangle((0, y), 300, h, facecolor=HELL,
                               edgecolor=DUNKEL, linewidth=0.8, zorder=1))
        ax.text(2.5, y + h - 4.5, name, ha="left", va="center",
                fontsize=TS, fontweight="bold", color=DUNKEL, zorder=5)

    band(122, 26, "Oberfläche")
    for x, t in ((8, "map.py\nHauptkarte"),
                 (105, "2_Experiments.py\nAnimation"),
                 (202, "3_Japan_Experiment.py\nKameravergleich")):
        kasten(ax, x, 126, 90, 14, t, fc=WEISS)
    ax.text(297, 144, "Streamlit", ha="right", va="center", fontsize=TS,
            style="italic", color=DUNKEL, zorder=5)

    band(86, 30, "Kartendarstellung")
    kasten(ax, 8, 90, 284, 19,
           "eine gemeinsame Kartenkomponente:  MapLibre GL JS,\n"
           "als HTML-Komponente in Streamlit eingebettet",
           fc=WEISS, fs=TM)

    band(44, 36, "Fachlogik")
    kasten(ax, 8, 48, 68, 24, "carpathian_bears\njapan_comparison", fc=WEISS)
    kasten(ax, 82, 48, 68, 24, "sync_simulation\nactivity_overlap", fc=WEISS)
    kasten(ax, 156, 48, 58, 24, "terrain_cache", fc=WEISS)
    kasten(ax, 220, 48, 72, 24, "bear_simulation\n(Vorarbeit Bräu,\nunverändert)",
           fc=WEISS, hatch="////")

    band(0, 38, "Datenhaltung")
    kasten(ax, 8, 5, 86, 26,
           "MariaDB\nbears_tracking,\nbears_images_unified,\ndeterrent_devices …",
           fc=WEISS)
    kasten(ax, 100, 5, 62, 26, "SQLite\ndatabase.db\nGeschwindigkeiten",
           fc=WEISS, hatch="////")
    kasten(ax, 168, 5, 60, 26, "SQLite\nterrain_cache.db\nGelände", fc=WEISS)
    kasten(ax, 234, 5, 58, 26, "extern\nOverpass/OSM,\nGBIF, BfN", fc=WEISS)

    for x in (53, 150, 247):
        pfeil(ax, x, 126, x, 109.5, ls=(0, (2, 2)))
    for x in (42, 116, 185, 256):
        pfeil(ax, x, 90, x, 72.5)
    for x in (42, 116, 185, 256):
        pfeil(ax, x, 48, x, 31.5)

    leg = [Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, label="neu oder ersetzt"),
           Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, hatch="////",
                     label="aus der Vorarbeit übernommen")]
    ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, -0.02),
              frameon=False, fontsize=TS, ncol=2, handlelength=1.6)
    speichern(fig, "abb_a2_zielarchitektur.pdf")


# =================================================================
# A3  Umfang und Verteilung der GPS-Daten
# =================================================================
def a3(daten):
    fig, ax = plt.subplots(figsize=(BREITE, 3.5))
    namen = [d["bear"] for d in daten]
    werte = [d["n"] for d in daten]
    gesamt = sum(werte)

    for i, d in enumerate(daten):
        h = "////" if d["sex"] == "F" else None
        ax.barh(i, d["n"], color=WEISS, edgecolor=SCHWARZ, linewidth=0.7,
                hatch=h, height=0.72)
        ax.text(d["n"] + gesamt * 0.004, i, f"{d['n']:,}".replace(",", " "),
                va="center", ha="left", fontsize=TS, color=SCHWARZ)

    ax.set_yticks(list(range(len(namen))))
    ax.set_yticklabels(namen, fontsize=TS)
    ax.invert_yaxis()
    ax.set_xlabel("Anzahl Ortungen", fontsize=TM)
    ax.set_xlim(0, max(werte) * 1.20)
    ax.tick_params(axis="x", labelsize=TS)
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", " ")))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=MITTEL, linewidth=0.5, linestyle=(0, (2, 3)))
    ax.set_axisbelow(True)

    ax.text(0.98, 0.05,
            f"{gesamt:,}".replace(",", " ") + " Ortungen von 13 Tieren\n"
            "9. August 2011 bis 31. Juli 2015\n"
            "stärkstes Tier " + f"{100 * max(werte) / gesamt:.1f}".replace(".", ",")
            + " %, schwächstes " + f"{100 * min(werte) / gesamt:.1f}".replace(".", ",")
            + " %",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=TS,
            linespacing=1.4,
            bbox=dict(boxstyle="round,pad=0.35", fc=WEISS, ec=SCHWARZ, lw=0.6))

    leg = [Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, label="männlich"),
           Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, hatch="////",
                     label="weiblich")]
    ax.legend(handles=leg, loc="lower right", bbox_to_anchor=(1.0, 0.33),
              frameon=False, fontsize=TS, handlelength=1.6)
    speichern(fig, "abb_a3_gps_verteilung.pdf")


# =================================================================
# A4  Richtungswahl vorher und nachher
# =================================================================
def a4():
    fig, axes = plt.subplots(1, 2, figsize=(BREITE, 3.2))

    for ax, jitter, unten in (
        (axes[0], 15.0,
         "acht feste Richtungen im 45°-Raster,\nStreuung ±15°  →  Lücken von je 15°"),
        (axes[1], 22.5,
         "Streuung ±22,5°  →  lückenlos, dazu\nRichtungen zu attraktiven Geländeflächen"),
    ):
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.85, 1.4)

        if jitter == 15.0:
            for i in range(8):
                m = i * 45
                ax.add_patch(Wedge((0, 0), 1.0, m + jitter, m + 45 - jitter,
                                   facecolor=WEISS, edgecolor=SCHWARZ,
                                   linewidth=0.5, hatch="xxxx", zorder=2))
        for i in range(8):
            m = i * 45
            ax.add_patch(Wedge((0, 0), 1.0, m - jitter, m + jitter,
                               facecolor=HELL, edgecolor=SCHWARZ,
                               linewidth=0.7, zorder=3))
            r = math.radians(m)
            ax.plot([0, 0.97 * math.cos(r)], [0, 0.97 * math.sin(r)],
                    color=DUNKEL, lw=0.5, ls=(0, (2, 2)), zorder=4)
        ax.add_patch(Circle((0, 0), 1.0, facecolor="none", edgecolor=SCHWARZ,
                            lw=0.9, zorder=5))
        ax.add_patch(Circle((0, 0), 0.07, facecolor=SCHWARZ, edgecolor=WEISS,
                            lw=0.8, zorder=8))

        if jitter != 15.0:
            for a, lw in ((62, 1.9), (203, 1.3)):
                r = math.radians(a)
                ax.add_patch(FancyArrowPatch(
                    (0, 0), (1.24 * math.cos(r), 1.24 * math.sin(r)),
                    arrowstyle="-|>", mutation_scale=8, linewidth=lw,
                    color=SCHWARZ, zorder=7))
                ax.plot(1.31 * math.cos(r), 1.31 * math.sin(r), marker="s",
                        ms=4, mfc=WEISS, mec=SCHWARZ, mew=0.9, zorder=8)
        ax.text(0, -1.30, unten, ha="center", va="top", fontsize=TS,
                color=SCHWARZ, linespacing=1.45)

    leg = [Rectangle((0, 0), 1, 1, fc=HELL, ec=SCHWARZ, label="erreichbarer Bereich"),
           Rectangle((0, 0), 1, 1, fc=WEISS, ec=SCHWARZ, hatch="xxxx",
                     label="nicht erreichbar"),
           Line2D([], [], color=SCHWARZ, marker="s", mfc=WEISS, mec=SCHWARZ,
                  lw=1.3, ms=4, label="Richtung zu einer Geländefläche")]
    fig.legend(handles=leg, loc="lower center", ncol=3, frameon=False,
               fontsize=TS, handlelength=1.8, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(bottom=0.12, wspace=0.02, top=0.99)
    speichern(fig, "abb_a4_richtungswahl.pdf")


# =================================================================
# A5  Ergebnis des statistischen Vergleichs
# =================================================================
def a5():
    fig, ax = plt.subplots(figsize=(BREITE, 2.35))
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(0, 1)
    ax.axis("off")

    delta, lo, hi = 0.615, 0.528, 0.683
    y = 0.68
    ax.plot([0, 1], [y, y], color=SCHWARZ, lw=1.0, solid_capstyle="butt")
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        ax.plot([t, t], [y - 0.045, y + 0.045], color=SCHWARZ, lw=0.8)
        ax.text(t, y - 0.165, f"{t:.2f}".replace(".", ","), ha="center",
                va="top", fontsize=TS, color=SCHWARZ)

    ax.add_patch(Rectangle((lo, y - 0.035), hi - lo, 0.07, facecolor=WEISS,
                           edgecolor=SCHWARZ, linewidth=0.8, hatch="////",
                           zorder=3))
    ax.plot([delta, delta], [y - 0.09, y + 0.09], color=SCHWARZ, lw=2.0, zorder=4)
    ax.text(delta, y + 0.13, "Δ = 0,615", ha="center", va="bottom",
            fontsize=TL, fontweight="bold", color=SCHWARZ)
    ax.text(lo, y - 0.075, "0,528", ha="center", va="top", fontsize=TS,
            color=SCHWARZ)
    ax.text(hi, y - 0.075, "0,683", ha="center", va="top", fontsize=TS,
            color=SCHWARZ)

    ax.text(0, y + 0.235, "keine Überlappung", ha="left", va="bottom",
            fontsize=TS, style="italic", color=DUNKEL)
    ax.text(1, y + 0.235, "identischer Tagesrhythmus", ha="right", va="bottom",
            fontsize=TS, style="italic", color=DUNKEL)

    ax.text(0.5, 0.20,
            "Datengrundlage:  50 reale Kameraauslösungen gegenüber 1 958 virtuellen\n"
            "Detektionen aus 300 Simulationsläufen à 48 h, Erfassungsradius 150 m,\n"
            "ohne Geländegewichtung.  Schraffur: 95-%-Bootstrap-Intervall.",
            ha="center", va="center", fontsize=TS, color=SCHWARZ, linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.4", fc=WEISS, ec=SCHWARZ, lw=0.6))
    speichern(fig, "abb_a5_delta_ergebnis.pdf")


if __name__ == "__main__":
    import json
    pfad = os.environ.get("GPSJSON") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_gps_kennzahlen.json")
    daten = json.load(open(pfad, encoding="utf-8"))
    a1(); a2(); a3(daten); a4(); a5()
