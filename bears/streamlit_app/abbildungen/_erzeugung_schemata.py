# -*- coding: utf-8 -*-
"""Schematische Abbildungen 1-5 zur Geländegewichtung."""
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Rectangle, Polygon, Circle, FancyArrowPatch

OUT = os.environ.get("FIGDIR") or "abbildungen"
os.makedirs(OUT, exist_ok=True)

WALD      = "#3f7d4f"
WALD_HELL = "#9fc6a8"
WALD_MID  = "#6ea87c"
GRAU      = "#b9bec4"
GRAU_D    = "#6b7177"
ROT       = "#c0392b"
ROT_HELL  = "#f2bdb7"
BLAU      = "#2c6fa8"
BLAU_HELL = "#a9c8e2"
BAER      = "#5d4037"
DORF      = "#d9a441"
TEXT      = "#1d2024"
GOLD      = "#9c7211"
NEUTRAL   = "#f2f3f5"
AUS       = "#e4e6e9"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["text.color"] = TEXT


def finish(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=150, facecolor="white")
    plt.close(fig)
    print("geschrieben:", name)


def blank(ax):
    ax.set_aspect("equal")
    ax.axis("off")


# ===================================================================
# 1  Richtungslücken
# ===================================================================
def abb1():
    fig = plt.figure(figsize=(13.5, 7.6))
    fig.suptitle("Das erste Problem: ein Drittel aller Richtungen war gesperrt",
                 fontsize=20, fontweight="bold", y=0.965)

    for k, (jitter, titel, farbe) in enumerate((
            (15,   "VORHER:  acht Richtungen, ±15° Streuung",   ROT),
            (22.5, "JETZT:  acht Richtungen, ±22,5° Streuung", WALD))):
        ax = fig.add_axes([0.04 + k * 0.49, 0.17, 0.45, 0.70])
        blank(ax)
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.35, 1.45)

        if jitter == 15:
            ax.add_patch(Circle((0, 0), 1.0, facecolor=ROT_HELL, ec="none", zorder=1))
        for i in range(8):
            m = i * 45
            ax.add_patch(Wedge((0, 0), 1.0, m - jitter, m + jitter,
                               facecolor=WALD_HELL, edgecolor=WALD, lw=1.4, zorder=2))
            r = math.radians(m)
            ax.plot([0, .97 * math.cos(r)], [0, .97 * math.sin(r)],
                    color=WALD, lw=1.0, ls=(0, (3, 3)), zorder=3)
        ax.add_patch(Circle((0, 0), 1.0, facecolor="none", edgecolor=GRAU_D, lw=1.6, zorder=4))
        ax.add_patch(Circle((0, 0), .075, facecolor=BAER, edgecolor="white", lw=1.6, zorder=6))
        ax.set_title(titel, fontsize=15, fontweight="bold", color=farbe, pad=16)

        if jitter == 15:
            ax.add_patch(Wedge((0, 0), 1.0, 15, 30, facecolor=ROT, alpha=.8,
                               edgecolor=ROT, lw=1.5, zorder=5))
            ax.annotate("gesperrt:  15° bis 30°",
                        xy=(.78 * math.cos(math.radians(22.5)),
                            .78 * math.sin(math.radians(22.5))),
                        xytext=(.55, 1.3), fontsize=12, fontweight="bold",
                        color=ROT, ha="center",
                        arrowprops=dict(arrowstyle="->", color=ROT, lw=1.8))
            ax.text(0, -1.18, "Jeder Sektor deckt nur 30 von 45 Grad ab.\n"
                              "8 rote Lücken — zusammen ein Drittel des Kreises.",
                    ha="center", va="center", fontsize=12.3, color=ROT)
        else:
            ax.text(0, -1.18, "22,5 + 22,5 = 45  →  die Sektoren stoßen aneinander.\n"
                              "Jede Richtung ist erreichbar, keine Lücke.",
                    ha="center", va="center", fontsize=12.3, color=WALD)

    fig.text(0.5, 0.045,
             "Nachgemessen an 3 840 Entscheidungen: vorher lag in den roten Bändern keine einzige. "
             "Jetzt 31,9 % — bei Gleichverteilung wären es 33 %.",
             ha="center", fontsize=12.5, style="italic", color=GRAU_D)
    finish(fig, "01_richtungsluecken.png")


# ===================================================================
# 2  Analogie Sensormatte <-> Geländeraster
# ===================================================================
def tri_pts(row, idx, s=1.0):
    """Eckpunkte des idx-ten Dreiecks in Reihe row."""
    h = s * math.sqrt(3) / 2
    y0 = row * h
    if idx % 2 == 0:
        x0 = (idx // 2) * s
        return [(x0, y0), (x0 + s, y0), (x0 + s / 2, y0 + h)]
    x0 = ((idx - 1) // 2) * s
    return [(x0 + s / 2, y0 + h), (x0 + 1.5 * s, y0 + h), (x0 + s, y0)]


def centroid(pts):
    return (sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3)


def abb2():
    fig = plt.figure(figsize=(15.5, 9.6))
    fig.suptitle("Die Übertragung:  Sensormatte  →  Geländeraster",
                 fontsize=21, fontweight="bold", y=0.975)

    axL = fig.add_axes([0.035, 0.42, 0.44, 0.48])
    axR = fig.add_axes([0.525, 0.42, 0.44, 0.48])
    blank(axL); blank(axR)

    # ---------- links: Matte ----------
    fig.text(0.255, 0.915, "Im Paper:  wo genau steht der Fuß?",
             ha="center", fontsize=15.5, fontweight="bold", color=BLAU)
    fuss_l = {(1, 3): 0.9, (1, 4): 0.6, (1, 5): 0.5, (0, 4): 0.4}
    fuss_r = {(1, 9): 0.8, (1, 10): 0.95, (1, 11): 0.5, (0, 10): 0.3}
    aktiv = {**fuss_l, **fuss_r}
    for row in (0, 1, 2):
        for idx in range(0, 15):
            pts = tri_pts(row, idx)
            w = aktiv.get((row, idx))
            fc = (0.17, 0.44, 0.66, 0.25 + 0.7 * w) if w else NEUTRAL
            axL.add_patch(Polygon(pts, closed=True, facecolor=fc,
                                  edgecolor=GRAU_D, lw=0.7, zorder=2))
    # Gruppen umranden + Schwerpunkt
    for grp, lab, lx in ((fuss_l, "P  linker Fuß", 2.4), (fuss_r, "P  rechter Fuß", 5.9)):
        for (row, idx) in grp:
            axL.add_patch(Polygon(tri_pts(row, idx), closed=True, facecolor="none",
                                  edgecolor=BLAU, lw=2.6, zorder=6))
        sw = sum(grp.values())
        px = sum(centroid(tri_pts(r, i))[0] * w for (r, i), w in grp.items()) / sw
        py = sum(centroid(tri_pts(r, i))[1] * w for (r, i), w in grp.items()) / sw
        axL.plot(px, py, marker="X", ms=19, color=ROT, mec="white", mew=2.2, zorder=9)
        axL.annotate(lab, xy=(px, py), xytext=(lx, 3.45), fontsize=12.5,
                     fontweight="bold", color=ROT, ha="center",
                     arrowprops=dict(arrowstyle="->", color=ROT, lw=1.6,
                                     shrinkA=2, shrinkB=10))
    axL.set_xlim(-0.4, 8.4)
    axL.set_ylim(-1.9, 4.1)
    axL.text(4.0, -0.45, "Mehrere Dreiecksfelder melden einen Wert w.\n"
                         "Nicht das stärkste Feld gewinnt — es wird gewichtet\n"
                         "gemittelt. Ergebnis: ein stufenloser Punkt.",
             ha="center", va="top", fontsize=12.2, color=BLAU)

    # ---------- rechts: Raster ----------
    fig.text(0.745, 0.915, "Bei uns:  wo liegt das nächste Waldstück?",
             ha="center", fontsize=15.5, fontweight="bold", color=WALD)
    waldA = {(1, 3): 3, (2, 3): 3, (1, 2): 2, (2, 2): 3, (3, 3): 1}
    waldB = {(6, 3): 3, (7, 3): 2, (6, 2): 3, (7, 2): 3}
    alle = {**waldA, **waldB}
    for i in range(0, 9):
        for j in range(0, 5):
            v = alle.get((i, j))
            fc = WALD if v == 3 else WALD_MID if v == 2 else WALD_HELL if v == 1 else NEUTRAL
            axR.add_patch(Rectangle((i, j), 1, 1, facecolor=fc,
                                    edgecolor=GRAU_D, lw=0.7))
            if v:
                axR.text(i + .09, j + .09, f"+{v}", ha="left", va="bottom",
                         fontsize=10, color="white", fontweight="bold")
    for grp, lab, lx in ((waldA, "P  Wald A", 1.3), (waldB, "P  Wald B", 7.4)):
        for (i, j) in grp:
            axR.add_patch(Rectangle((i, j), 1, 1, facecolor="none",
                                    edgecolor=WALD, lw=2.8, zorder=6))
        sw = sum(grp.values())
        px = sum((i + .5) * w for (i, j), w in grp.items()) / sw
        py = sum((j + .5) * w for (i, j), w in grp.items()) / sw
        axR.plot(px, py, marker="X", ms=19, color=ROT, mec="white", mew=2.2, zorder=9)
        axR.annotate(lab, xy=(px, py), xytext=(lx, 5.55), fontsize=12.5,
                     fontweight="bold", color=ROT, ha="center",
                     arrowprops=dict(arrowstyle="->", color=ROT, lw=1.6,
                                     shrinkA=2, shrinkB=10))
        axR.annotate("", xy=(px, py), xytext=(4.5, -0.55),
                     arrowprops=dict(arrowstyle="-|>", color=ROT, lw=2.4,
                                     shrinkA=12, shrinkB=12), zorder=7)
    axR.add_patch(Circle((4.5, -0.55), .27, facecolor=BAER, edgecolor="white",
                         lw=1.8, zorder=10))
    axR.text(5.05, -0.58, "Bär", fontsize=12, fontweight="bold", color=BAER, va="center")
    axR.set_xlim(-0.3, 9.3)
    axR.set_ylim(-2.9, 6.1)
    axR.text(4.5, -1.5, "Geländezellen tragen eine Bewertung.\n"
                        "Dieselbe Rechnung — heraus kommt ein stufenloser\n"
                        "Zielpunkt je Waldstück, also eine Richtung.",
             ha="center", va="top", fontsize=12.2, color=WALD)

    # ---------- Zuordnung ----------
    axM = fig.add_axes([0.05, 0.065, 0.90, 0.30])
    blank(axM)
    axM.set_aspect("auto")
    axM.set_xlim(0, 100); axM.set_ylim(0, 100)
    axM.add_patch(Rectangle((0, 0), 100, 100, facecolor="#f4f6f8", edgecolor=GRAU, lw=1.2))
    axM.text(50, 88, "Was wem entspricht", ha="center", fontsize=14.5, fontweight="bold")
    paare = [("Dreiecksfeld der Matte", "Geländezelle (ca. 167 m Kantenlänge)"),
             ("Kapazitätswert  w", "Geländebewertung (Wald +3, Buschland +2, Wiese +1 …)"),
             ("ein Fuß", "ein zusammenhängendes Waldstück"),
             ("Fußposition  P", "Zielpunkt, auf den der Bär zusteuert")]
    for k, (a, b) in enumerate(paare):
        y = 68 - k * 17
        axM.text(5, y, a, fontsize=12.8, color=BLAU, va="center")
        axM.annotate("", xy=(43, y), xytext=(36, y),
                     arrowprops=dict(arrowstyle="-|>", color=GRAU_D, lw=1.8))
        axM.text(46, y, b, fontsize=12.8, color=WALD, va="center")

    fig.text(0.5, 0.018,
             "Formel (1) des Papers:   P = Σ (w · p) / Σ w   —   in beiden Fällen dieselbe Rechnung.",
             ha="center", fontsize=13, style="italic", color=GRAU_D)
    finish(fig, "02_analogie_matte_gelaende.png")


# ===================================================================
# 3  Warum erst getrennt werden muss
# ===================================================================
def abb3():
    fig = plt.figure(figsize=(16, 6.3))
    fig.suptitle("Warum erst getrennt werden muss — das Argument mit den zwei Füßen",
                 fontsize=20, fontweight="bold", y=0.965)

    waldN = [(1, 4), (2, 4), (3, 4), (1, 3), (2, 3)]
    waldS = [(5, 0), (6, 0), (5, 1), (6, 1), (7, 1)]
    dorf = [(3, 2), (4, 2), (3, 1), (4, 1), (4, 3)]

    def raster(ax):
        blank(ax)
        for i in range(8):
            for j in range(5):
                fc = WALD if (i, j) in waldN + waldS else DORF if (i, j) in dorf else NEUTRAL
                ax.add_patch(Rectangle((i, j), 1, 1, facecolor=fc, edgecolor=GRAU_D, lw=0.7))
        ax.add_patch(Circle((.5, .5), .3, facecolor=BAER, edgecolor="white", lw=1.8, zorder=11))
        ax.set_xlim(-0.3, 8.3)
        ax.set_ylim(-2.4, 6.4)

    titel = ("a)  Die Lage", "b)  OHNE Trennen — falsch", "c)  MIT Trennen — richtig")
    farben = (TEXT, ROT, WALD)
    unten = ("Zwei Waldstücke,\nein Dorf dazwischen.",
             "Der Mittelwert landet mitten im Dorf —\ndort ist gar kein Wald.\n"
             "Im Paper: der Punkt zwischen den Füßen.",
             "Benachbarte Zellen werden zu Gebieten\ngruppiert — zwei Gebiete, zwei Ziele.\n"
             "Der Bär kann sich für eines entscheiden.")

    for k in range(3):
        ax = fig.add_axes([0.025 + k * 0.325, 0.17, 0.31, 0.66])
        raster(ax)
        ax.set_title(titel[k], fontsize=15, fontweight="bold", color=farben[k], pad=12)

        if k == 0:
            ax.text(2.0, 3.5, "Wald A", ha="center", va="center", fontsize=12.5,
                    fontweight="bold", color="white")
            ax.text(5.95, 0.5, "Wald B", ha="center", va="center", fontsize=12.5,
                    fontweight="bold", color="white")
            ax.text(3.5, 1.5, "Dorf", ha="center", va="center", fontsize=12.5,
                    fontweight="bold", color="white")
        if k == 1:
            alleW = waldN + waldS
            px = sum(i + .5 for i, j in alleW) / len(alleW)
            py = sum(j + .5 for i, j in alleW) / len(alleW)
            ax.annotate("", xy=(px, py), xytext=(.5, .5),
                        arrowprops=dict(arrowstyle="-|>", color=ROT, lw=3.2,
                                        shrinkA=15, shrinkB=15), zorder=9)
            ax.plot(px, py, marker="X", ms=23, color=ROT, mec="white", mew=2.5, zorder=12)
            ax.text(4.0, 5.75, "ein einziger Mittelpunkt über alles", ha="center",
                    fontsize=12.5, fontweight="bold", color=ROT)
        if k == 2:
            for grp in (waldN, waldS):
                px = sum(i + .5 for i, j in grp) / len(grp)
                py = sum(j + .5 for i, j in grp) / len(grp)
                ax.annotate("", xy=(px, py), xytext=(.5, .5),
                            arrowprops=dict(arrowstyle="-|>", color=ROT, lw=2.8,
                                            shrinkA=15, shrinkB=14), zorder=9)
                ax.plot(px, py, marker="X", ms=20, color=ROT, mec="white", mew=2.3, zorder=12)
            ax.text(4.0, 5.75, "zwei getrennte Mittelpunkte", ha="center",
                    fontsize=12.5, fontweight="bold", color=WALD)

        ax.text(4.0, -0.6, unten[k], ha="center", va="top", fontsize=12.2, color=farben[k])

    fig.text(0.5, 0.055,
             "Genau dieser Trennschritt greift in unserem Gebiet aber nur bei 3,4 % der Positionen — siehe Abbildung 6.",
             ha="center", fontsize=12.5, style="italic", color=GRAU_D)
    finish(fig, "03_warum_trennen.png")


# ===================================================================
# 4  Die vier Schritte
# ===================================================================
def abb4():
    fig = plt.figure(figsize=(18, 6.1))
    fig.suptitle("Was bei jedem Schritt des Bären passiert",
                 fontsize=20, fontweight="bold", y=0.965)

    werte = {(1, 4): 3, (2, 4): 3, (1, 3): 2, (2, 3): 3, (3, 4): 1,
             (6, 4): 3, (7, 4): 2, (6, 3): 3,
             (4, 1): -0.5, (5, 1): -0.5, (3, 1): 0.5, (0, 2): 0.5,
             (2, 0): -1.5, (7, 1): 0.5, (5, 0): -0.5}
    grpA = [(1, 4), (2, 4), (1, 3), (2, 3), (3, 4)]
    grpB = [(6, 4), (7, 4), (6, 3)]
    BX, BY = 4.0, 2.5

    titel = ("1.  Einsammeln", "2.  Schwelle anlegen", "3.  Trennen", "4.  Formel (1)")
    unten = ("Alle Geländezellen im Umkreis\nvon 350 m aus dem lokalen\nSpeicher holen und bewerten.",
             "Alles unter der Schwelle 1,0\nfällt weg. Übrig bleibt nur,\nwas attraktiv ist.",
             "Zellen, die aneinandergrenzen,\nwerden zu einem Gebiet\nzusammengefasst.",
             "Je Gebiet ein gewichteter\nMittelpunkt — daraus wird\neine Richtung.")

    for k in range(4):
        ax = fig.add_axes([0.015 + k * 0.248, 0.17, 0.225, 0.66])
        blank(ax)
        ax.set_xlim(-0.3, 8.3)
        ax.set_ylim(-2.6, 6.0)
        for i in range(8):
            for j in range(5):
                v = werte.get((i, j), 0.0)
                attr = v >= 1
                if k == 0:
                    fc = WALD if v >= 3 else WALD_MID if v >= 2 else WALD_HELL if v >= 1 else NEUTRAL
                elif k == 1:
                    fc = (WALD if v >= 3 else WALD_MID if v >= 2 else WALD_HELL) if attr else AUS
                else:
                    fc = WALD if (i, j) in grpA else BLAU if (i, j) in grpB else AUS
                ax.add_patch(Rectangle((i, j), 1, 1, facecolor=fc, edgecolor=GRAU_D, lw=0.65))
                if k == 0 and v:
                    ax.text(i + .5, j + .5, ("+" if v > 0 else "") + f"{v:g}".replace(".", ","),
                            ha="center", va="center", fontsize=8.5,
                            color="white" if v >= 2 else TEXT)
                if k == 1 and not attr and v:
                    ax.text(i + .5, j + .5, "✕", ha="center", va="center",
                            fontsize=10, color=GRAU_D)
        ax.add_patch(Circle((BX, BY), .27, facecolor=BAER, edgecolor="white", lw=1.7, zorder=12))
        ax.set_title(titel[k], fontsize=15, fontweight="bold", pad=12)

        if k == 0:
            ax.add_patch(Rectangle((BX - 2.4, BY - 2.4), 4.8, 4.8, facecolor="none",
                                   edgecolor=GOLD, lw=2.2, ls=(0, (6, 4)), zorder=9))
            ax.text(4.0, 5.5, "350 m Suchbereich", fontsize=12.5, color=GOLD,
                    ha="center", fontweight="bold")
        if k == 2:
            ax.text(1.6, 5.5, "Gebiet A", fontsize=12.5, fontweight="bold", color=WALD, ha="center")
            ax.text(6.6, 5.5, "Gebiet B", fontsize=12.5, fontweight="bold", color=BLAU, ha="center")
        if k == 3:
            for grp in (grpA, grpB):
                sw = sum(werte[c] for c in grp)
                px = sum((c[0] + .5) * werte[c] for c in grp) / sw
                py = sum((c[1] + .5) * werte[c] for c in grp) / sw
                ax.annotate("", xy=(px, py), xytext=(BX, BY),
                            arrowprops=dict(arrowstyle="-|>", color=ROT, lw=2.6,
                                            shrinkA=13, shrinkB=12), zorder=10)
                ax.plot(px, py, marker="X", ms=18, color=ROT, mec="white", mew=2.1, zorder=13)
            ax.text(4.0, 5.5, "zwei Zielrichtungen", fontsize=12.5,
                    fontweight="bold", color=ROT, ha="center")

        ax.text(4.0, -0.75, unten[k], ha="center", va="top", fontsize=12)

    for x in (0.247, 0.495, 0.743):
        fig.text(x, 0.47, "→", fontsize=30, color=GRAU_D, ha="center", va="center")

    fig.text(0.5, 0.055,
             "Formel (1):   P = Σ (w · p) / Σ w        "
             "Gewicht einer Zelle = Bewertung − Schwelle + 0,5   (damit alle Gewichte positiv bleiben)",
             ha="center", fontsize=12.8, style="italic", color=GRAU_D)
    finish(fig, "04_ablauf_vier_schritte.png")


# ===================================================================
# 5  Wie ein einzelner Schritt zustande kommt
# ===================================================================
def abb5():
    import random
    fig = plt.figure(figsize=(15, 8.6))
    fig.suptitle("Wie ein einzelner Schritt zustande kommt",
                 fontsize=20, fontweight="bold", y=0.965)

    ax = fig.add_axes([0.01, 0.07, 0.56, 0.84])
    blank(ax)
    ax.set_xlim(-1.95, 1.95)
    ax.set_ylim(-1.75, 1.75)

    rng = random.Random(11)
    for i in range(8):
        a = (45 * i + rng.uniform(-22.5, 22.5)) % 360
        r = math.radians(a)
        ax.annotate("", xy=(1.1 * math.cos(r), 1.1 * math.sin(r)), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=GRAU, lw=1.6,
                                    shrinkA=10, shrinkB=0), zorder=3)

    for a, lw, lab in ((62, 4.2, "großes Waldstück\n→ großer Bonus"),
                       (205, 2.8, "kleineres Waldstück\n→ kleiner Bonus")):
        r = math.radians(a)
        ax.annotate("", xy=(1.28 * math.cos(r), 1.28 * math.sin(r)), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=WALD, lw=lw,
                                    shrinkA=11, shrinkB=0), zorder=5)
        ax.plot(1.33 * math.cos(r), 1.33 * math.sin(r), marker="X", ms=16,
                color=ROT, mec="white", mew=1.9, zorder=6)
        ax.text(1.62 * math.cos(r), 1.62 * math.sin(r), lab, fontsize=11.5,
                fontweight="bold", color=WALD, ha="center", va="center")

    rp = math.radians(242)
    ax.annotate("", xy=(0.95 * math.cos(rp), 0.95 * math.sin(rp)), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-", color=GOLD, lw=2.6, ls="--",
                                shrinkA=10, shrinkB=0), zorder=4)
    ax.text(1.18 * math.cos(rp), 1.18 * math.sin(rp), "woher der Bär kam",
            fontsize=11.5, color=GOLD, ha="center", va="center", fontweight="bold")

    rg = math.radians(62)
    ax.plot([0, 1.3 * math.cos(rg)], [0, 1.3 * math.sin(rg)],
            color=ROT, lw=13, alpha=.22, solid_capstyle="round", zorder=1)
    ra = math.radians(20)
    ax.text(0.78 * math.cos(ra), 0.78 * math.sin(ra), "gewählt", fontsize=13,
            fontweight="bold", color=ROT, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=ROT, lw=1.4))
    ax.add_patch(Circle((0, 0), .085, facecolor=BAER, edgecolor="white", lw=2, zorder=14))

    # ---- Erläuterungskasten ----
    axT = fig.add_axes([0.59, 0.07, 0.40, 0.84])
    blank(axT); axT.set_aspect("auto")
    axT.set_xlim(0, 100); axT.set_ylim(0, 100)
    axT.add_patch(Rectangle((0, 0), 100, 100, facecolor="#f4f6f8", edgecolor=GRAU, lw=1.2))
    axT.text(50, 94, "Jeder Kandidat bekommt Punkte", ha="center",
             fontsize=14.5, fontweight="bold")

    zeilen = [(GRAU_D, "8 freie Richtungen",
               "über den ganzen Kreis verteilt, eine je\nSektor. Damit der Bär nicht für immer\nim Wald kleben bleibt."),
              (WALD, "+  Richtungen zu Waldstücken",
               "aus Formel (1). Der Bonus wächst mit\nder Größe des Waldstücks, ist aber\nnach oben gedeckelt."),
              (BLAU, "+  Gelände auf dem Weg",
               "drei Stichproben entlang der Strecke,\nnicht nur am Ziel — sonst läuft er\ndurchs Dorf zum Wald dahinter."),
              (GOLD, "+  Richtungstreue",
               "nah an der letzten Richtung ist besser,\neine Kehrtwende schlechter.")]
    y = 86
    for col, kopf, txt in zeilen:
        axT.add_patch(Rectangle((4, y - 1.6), 2.6, 3.4, facecolor=col, ec="none"))
        axT.text(9.5, y, kopf, fontsize=12.6, fontweight="bold", va="center", color=col)
        axT.text(9.5, y - 4.0, txt, fontsize=11.2, va="top", color=TEXT, linespacing=1.5)
        y -= 19.0

    axT.add_patch(Rectangle((4, 2.5), 92, 13.0, facecolor="white", edgecolor=ROT, lw=1.8))
    axT.text(50, 9.0, "Dann wird gezogen — nicht das Maximum genommen.\n"
                      "Gute Kandidaten sind nur wahrscheinlicher, nicht sicher.",
             ha="center", va="center", fontsize=12, color=ROT, fontweight="bold",
             linespacing=1.6)

    fig.text(0.5, 0.012,
             "Es bleibt ein Zufallsmodell. Ohne Zufall wäre der Pfad bei gleichem Startpunkt immer derselbe.",
             ha="center", fontsize=12.5, style="italic", color=GRAU_D)
    finish(fig, "05_ein_schritt.png")


if __name__ == "__main__":
    abb1(); abb2(); abb3(); abb4(); abb5()
