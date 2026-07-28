"""Generateurs de graphiques SVG calcules cote serveur.

Le projet reste volontairement sans framework JS (Jinja2 pur) : ces
fonctions calculent les coordonnees/segments necessaires pour dessiner des
graphiques (courbe, donut, sparkline) directement en SVG dans les templates.
"""

import math

COULEURS_CATEGORIES = [
    "#3D9B84", "#3D6B9B", "#C97A2B", "#6E5AA6", "#C0392B",
    "#2E9E9E", "#9B3D6B", "#7A9B3D", "#B08A3D", "#5A6E9B",
]


def segments_donut(repartition, rayon=60):
    """repartition : liste de (label, valeur).

    Retourne (segments, circonference) ou chaque segment est pret a etre
    dessine sur un <circle> via stroke-dasharray/stroke-dashoffset (la
    technique classique de donut chart en SVG pur, sans arcs a calculer).
    """
    circonference = 2 * math.pi * rayon
    total = sum(float(v) for _, v in repartition) or 1

    segments = []
    cumul = 0.0
    for i, (label, valeur) in enumerate(repartition):
        valeur = float(valeur)
        part = valeur / total
        longueur = part * circonference
        segments.append({
            "label": label,
            "valeur": valeur,
            "pourcentage": round(part * 100, 1),
            "couleur": COULEURS_CATEGORIES[i % len(COULEURS_CATEGORIES)],
            "dasharray": f"{longueur:.2f} {circonference - longueur:.2f}",
            "dashoffset": f"{-cumul:.2f}",
        })
        cumul += longueur

    return segments, circonference


def points_courbe(valeurs, largeur=560, hauteur=160, marge=20):
    """Retourne (chaine_points, liste_points) pour un polyline/aire SVG."""
    if not valeurs:
        return "", []

    maximum = max(valeurs) or 1
    n = len(valeurs)
    pas_x = (largeur - 2 * marge) / max(n - 1, 1)

    points = []
    for i, v in enumerate(valeurs):
        x = marge + i * pas_x
        y = hauteur - marge - (float(v) / float(maximum)) * (hauteur - 2 * marge)
        points.append((round(x, 1), round(y, 1)))

    chaine = " ".join(f"{x},{y}" for x, y in points)
    return chaine, points


def sparkline_points(valeurs, largeur=110, hauteur=32, marge=3):
    chaine, _ = points_courbe(valeurs, largeur, hauteur, marge)
    return chaine
