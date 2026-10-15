# -*- coding: utf-8 -*-
"""
Abbildung A6: Weg einer Aufnahme von der Kamera bis in die Karte.

Alle Angaben stammen aus dem Repository und der Datenbank:
  - Tabellennamen und Spalten:  SHOW CREATE TABLE
  - Zeilenzahlen und Herkunft:  SELECT ... GROUP BY source, image_type
  - Abfrageintervall 10 s:      email_extractor/WildlifePictureExtractor.py
  - Zwischenspeicher 30 s:      streamlit_app/new_images_checker.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, FancyBboxPatch

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
WEISS = "#ffffff"
HELL = "#eceef0"
DUNKEL = "#5a6068"
SCHWARZ = "#1d2024"

TS, TM, TL = 6.4, 7.2, 8.8


def kasten(ax, x, y, w, h, text=None, fc=WEISS, lw=0.8, fs=TS, hatch=None):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=SCHWARZ,
                           linewidth=lw, hatch=hatch, zorder=3))
    if text:
        bb = dict(boxstyle="square,pad=0.18", fc=WEISS, ec="none") if hatch else None
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                color=SCHWARZ, zorder=4, linespacing=1.4, bbox=bb)


def pfeil(ax, x1, y1, x2, y2, lw=0.9):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=7, linewidth=lw,
                                 color=SCHWARZ, zorder=2, shrinkA=0, shrinkB=0))


def notiz(ax, x, y, text, ha="left", va="center"):
    ax.text(x, y, text, fontsize=TS - 0.5, ha=ha, va=va, color=DUNKEL,
            style="italic", linespacing=1.35, zorder=5)


# ----------------------------------------------------------------- Vorher
def panel_vorher(ax):
    ax.text(0.0, 3.30, "Vorher: zwei getrennte Bestände", fontsize=TL,
            fontweight="bold", va="bottom", color=SCHWARZ)

    kasten(ax, 0.00, 2.55, 1.05, 0.52, "Kamera\n(E-Mail)")
    kasten(ax, 1.45, 2.55, 1.20, 0.52, "Bildextraktion")
    kasten(ax, 2.80, 2.55, 2.25, 0.52,
           "wildlife_images\nBilddaten, Zeit als Text", hatch="///")
    pfeil(ax, 1.05, 2.81, 1.45, 2.81)
    pfeil(ax, 2.65, 2.81, 2.80, 2.81)

    kasten(ax, 0.00, 1.75, 1.05, 0.52, "Ordner im\nDateisystem")
    kasten(ax, 2.80, 1.75, 2.25, 0.52,
           "image_metadata\nnur Dateipfade, Zeit als Text", hatch="\\\\\\")
    pfeil(ax, 1.05, 2.01, 2.80, 2.01)

    # Klammer rechts
    ax.plot([5.35, 5.35], [2.01, 2.81], lw=0.8, color=DUNKEL)
    ax.plot([5.05, 5.35], [2.81, 2.81], lw=0.8, color=DUNKEL)
    ax.plot([5.05, 5.35], [2.01, 2.01], lw=0.8, color=DUNKEL)
    ax.text(5.47, 2.41, "unterschiedlich aufgebaut:\nkeine gemeinsame\nAbfrage möglich",
            fontsize=TS, va="center", ha="left", color=SCHWARZ, linespacing=1.4)


# ---------------------------------------------------------------- Nachher
def panel_nachher(ax):
    ax.text(0.0, 1.18, "Nachher: ein Bestand", fontsize=TL,
            fontweight="bold", va="bottom", color=SCHWARZ)

    # eigener Prozess, gestrichelt umrandet
    ax.add_patch(FancyBboxPatch((1.33, 0.44), 1.44, 0.68,
                                boxstyle="round,pad=0.01",
                                facecolor=HELL, edgecolor=DUNKEL,
                                linewidth=0.8, linestyle=(0, (3, 2)), zorder=1))
    notiz(ax, 1.33, 0.36, "eigener Prozess,\nalle 10 s", ha="left", va="top")

    kasten(ax, 0.00, 0.56, 1.05, 0.44, "Kamera\n(E-Mail)")
    kasten(ax, 1.45, 0.56, 1.20, 0.44, "Bildextraktion")
    kasten(ax, 0.00, -0.44, 1.05, 0.44, "Ordner im\nDateisystem")

    # gemeinsame Tabelle
    bx, by, bw, bh = 2.80, -0.52, 2.25, 1.52
    kasten(ax, bx, by, bw, bh, lw=1.3)
    ax.text(bx + bw / 2, by + bh - 0.17, "bears_images_unified",
            ha="center", va="center", fontsize=TM, color=SCHWARZ, zorder=4)
    ax.plot([bx + 0.12, bx + bw - 0.12], [by + bh - 0.33, by + bh - 0.33],
            lw=0.6, color=DUNKEL, zorder=4)
    ax.text(bx + bw / 2, by + 0.78,
            "Bilddaten statt Pfad\nHerkunft als Spalte\nZeitstempel als Datumswert",
            ha="center", va="center", fontsize=TS, color=SCHWARZ,
            linespacing=1.5, zorder=4)
    ax.plot([bx + 0.12, bx + bw - 0.12], [by + 0.42, by + 0.42],
            lw=0.6, color=DUNKEL, zorder=4)
    ax.text(bx + bw / 2, by + 0.21,
            "51 Aufnahmen\n14 E-Mail, 37 Dateisystem",
            ha="center", va="center", fontsize=TS, color=SCHWARZ,
            linespacing=1.4, zorder=4)

    pfeil(ax, 1.05, 0.78, 1.45, 0.78)
    pfeil(ax, 2.65, 0.78, 2.80, 0.64)
    pfeil(ax, 1.05, -0.22, 2.80, -0.08)

    kasten(ax, 5.45, 0.02, 1.05, 0.52, "Karten-\nanwendung")
    pfeil(ax, 5.05, 0.28, 5.45, 0.28)

    # Statusweg
    kasten(ax, 2.80, -1.22, 2.25, 0.46,
           "app_status\nZeitpunkt der letzten Prüfung", fc=HELL)
    ax.plot([5.05, 5.97], [-0.99, -0.99], lw=0.9, color=SCHWARZ, zorder=2)
    pfeil(ax, 5.97, -0.99, 5.97, 0.02)
    notiz(ax, 2.80, -1.40, "überdauert den Neustart; die Statusanzeige fragt alle 30 s ab",
          ha="left", va="top")


def main():
    fig, ax = plt.subplots(figsize=(BREITE, 4.6))
    ax.set_xlim(-0.08, 7.05)
    ax.set_ylim(-1.68, 3.62)
    ax.axis("off")

    panel_vorher(ax)
    ax.plot([-0.08, 6.95], [1.48, 1.48], lw=0.6, color=DUNKEL,
            linestyle=(0, (2, 2)))
    panel_nachher(ax)

    pfad = os.path.join(OUT, "abb_a6_bildweg.pdf")
    fig.savefig(pfad, format="pdf", bbox_inches="tight", pad_inches=0.02)
    if os.environ.get("VORSCHAU"):
        fig.savefig(pfad.replace(".pdf", ".png"), dpi=190, bbox_inches="tight",
                    pad_inches=0.02, facecolor="white")
    plt.close(fig)
    print("geschrieben:", pfad)


main()
