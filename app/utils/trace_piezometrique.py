# -*- coding: utf-8 -*-
"""Tracé piézométrique générique du profil en long (8 schémas) — PNG.

Utilisation CLI :  python app\\utils\\trace_piezometrique.py <projet.json> [sortie.png]
Depuis l'application : fenêtre « Analyse piézométrique » (app.ui.analyse_frame).
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEP_DEFAUT = 3.0  # dépression maximale admissible au point haut (mCE)

_LABELS = {
    "Vi1": "Vi1\n(entrée)",
    "PI1": "PI1\n(amont)",
    "Ve": "Ve\n(point haut)",
    "PI2": "PI2\n(aval)",
    "Vi2": "Vi2\n(sortie)",
}
_COULEURS = {"Vi1": "black", "PI1": "red", "Ve": "green",
             "PI2": "blue", "Vi2": "black"}

# Points du profil par schéma : (nom, portée_x, champ_z). La portée_x est un
# nombre (0 pour le premier point) ou le nom d'un champ distance du modèle.
ORDRE_POINTS = {
    "1A": [("Vi1", 0, "z_vi1"), ("Ve", "l1", "z_ve")],
    "1B": [("Vi1", 0, "z_vi1"), ("PI1", "a", "z_pi1"), ("Ve", "b", "z_ve")],
    "2A": [("Ve", 0, "z_ve"), ("Vi2", "l2", "z_vi2")],
    "2B": [("Ve", 0, "z_ve"), ("PI2", "c", "z_pi2"), ("Vi2", "d", "z_vi2")],
    "3A": [("Vi1", 0, "z_vi1"), ("Ve", "l1", "z_ve"), ("Vi2", "l2", "z_vi2")],
    "3B": [("Vi1", 0, "z_vi1"), ("PI1", "a", "z_pi1"), ("Ve", "b", "z_ve"),
           ("PI2", "c", "z_pi2"), ("Vi2", "d", "z_vi2")],
    "4A": [("Vi1", 0, "z_vi1"), ("PI1", "a", "z_pi1"), ("Ve", "b", "z_ve"),
           ("Vi2", "l2", "z_vi2")],
    "4B": [("Vi1", 0, "z_vi1"), ("Ve", "l1", "z_ve"), ("PI2", "c", "z_pi2"),
           ("Vi2", "d", "z_vi2")],
}


def charger_depuis_json(chemin_json):
    """Reconstruit un EtatApplication depuis un fichier de projet (.json)."""
    import json
    from app.controller import EtatApplication
    with open(chemin_json, encoding="utf-8") as f:
        proj = json.load(f)
    e = EtatApplication()
    for k in EtatApplication.CHAMPS_EDITABLES:
        if k in proj:
            setattr(e, k, proj[k])
    return e


def _coord_poly(etat, schema):
    """Coordonnées physiques du profil : [(x, z, nom), …] pour le schéma."""
    spec = ORDRE_POINTS.get(schema)
    if spec is None:
        raise ValueError(f"Schéma de vidange inconnu : {schema}")
    x, pts = 0.0, []
    for nom, portee, zchamp in spec:
        if isinstance(portee, str):
            x += float(getattr(etat, portee))
        pts.append((x, float(getattr(etat, zchamp)), nom))
    return pts


def tracer_profil(etat, chemin_png=None, dep=DEP_DEFAUT, taille=(15, 7)):
    """Trace le profil piézométrique du tronçon courant et l'enregistre.

    Retourne (fig, infos) — infos = {q_ve, q_pi1, q_pi2, cas_pi1, cas_pi2,
    h1, h2, verdict1, verdict2, journal}.
    """
    if etat.resultat is None:
        etat.calculer()
    r = etat.resultat
    schema = etat.schema
    pts = _coord_poly(etat, schema)
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    par_nom = {p[2]: (p[0], p[1]) for p in pts}
    noms = set(par_nom)

    x_ve, z_ve = par_nom["Ve"]

    infos = {
        "q_ve": getattr(r, "q_ve_m3h", 0.0),
        "q_pi1": getattr(r, "q_pi1_m3h", 0.0),
        "q_pi2": getattr(r, "q_pi2_m3h", 0.0),
        "cas_pi1": getattr(r, "cas_pi1", None),
        "cas_pi2": getattr(r, "cas_pi2", None),
        "h1": None, "h2": None,
        "verdict1": None, "verdict2": None,
        "journal": list(getattr(r, "journal", [])),
    }

    def pio_ami(x):
        x0, z0 = par_nom["Vi1"]
        return z0 + (x - x0) / (x_ve - x0) * (z_ve - dep - z0)

    def pio_aval(x):
        x2, z2 = par_nom["Vi2"]
        return z2 + (x2 - x) / (x2 - x_ve) * (z_ve - dep - z2)

    fig, ax = plt.subplots(figsize=taille)

    # Fond
    ax.fill_between(xs, zs, min(zs) - 25, color="#e8f5e9", alpha=0.45)

    # Profil topographique
    ax.plot(xs, zs, "k-o", lw=2.8, ms=8, zorder=5,
            label="Profil topographique (Z)")

    # Piézométrie amont (rouge) / aval (bleu)
    if "Vi1" in noms:
        x0, z0 = par_nom["Vi1"]
        ax.plot([x0, x_ve], [z0, z_ve - dep], color="red", ls="--", lw=2.2,
                label=f"Piézométrie amont (Z_Ve−{dep:.0f} → Z_Vi1)")
    if "Vi2" in noms:
        x2, z2 = par_nom["Vi2"]
        ax.plot([x_ve, x2], [z_ve - dep, z2], color="blue", ls="--", lw=2.2,
                label=f"Piézométrie aval (Z_Ve−{dep:.0f} → Z_Vi2)")

    # Ligne repère Z_Ve−dep
    ax.axhline(y=z_ve - dep, color="gray", ls=":", lw=0.8, alpha=0.5)
    ax.text(xs[-1] + 5, z_ve - dep,
            f"Z_Ve − {dep:.0f} = {z_ve - dep:.2f} m",
            color="gray", fontsize=8, va="center")

    # H₁ (PI amont)
    if "PI1" in par_nom and "Vi1" in noms:
        x1, z1 = par_nom["PI1"]
        p1 = pio_ami(x1)
        h1 = z1 - p1
        infos["h1"] = h1
        infos["verdict1"] = ("CAS PARTICULIER — organe requis" if h1 >= dep
                             else "CAS NORMAL")
        col1 = "red" if h1 >= dep else "green"
        ax.annotate("", xy=(x1, p1), xytext=(x1, z1),
                    arrowprops=dict(arrowstyle="<->", color=col1, lw=2.8))
        verdict1 = ("⚠ ≥ 3 m → CAS PARTICULIER → ORGANE PI1 requis"
                    if h1 >= dep else "✓ < 3 m → CAS NORMAL")
        ax.text(x1 + 15, (z1 + p1) / 2, f"H₁ = {h1:+.2f} m\n{verdict1}",
                fontsize=9.5, color=col1, fontweight="bold", va="center",
                bbox=dict(boxstyle="round,pad=0.45", fc="lightyellow", alpha=0.92))

    # H₂ (PI aval)
    if "PI2" in par_nom and "Vi2" in noms:
        x1, z1 = par_nom["PI2"]
        p1 = pio_aval(x1)
        h2 = z1 - p1
        infos["h2"] = h2
        infos["verdict2"] = ("CAS PARTICULIER — organe requis" if h2 >= dep
                             else "CAS NORMAL")
        col2 = "red" if h2 >= dep else "green"
        ax.annotate("", xy=(x1, p1), xytext=(x1, z1),
                    arrowprops=dict(arrowstyle="<->", color=col2, lw=2.8))
        verdict2 = ("⚠ ≥ 3 m → CAS PARTICULIER → ORGANE PI2 requis"
                    if h2 >= dep else "✓ < 3 m → CAS NORMAL")
        ax.text(x1 - 165, (z1 + p1) / 2, f"H₂ = {h2:+.2f} m\n{verdict2}",
                fontsize=9.5, color=col2, fontweight="bold", va="center",
                bbox=dict(boxstyle="round,pad=0.45", fc="lightyellow", alpha=0.92))

    # Points critiques
    for xp, zp, nom in pts:
        ax.annotate(f"{_LABELS.get(nom, nom)}\nZ = {zp:.2f} m", (xp, zp),
                    textcoords="offset points", xytext=(0, 14),
                    fontsize=8.5, ha="center",
                    color=_COULEURS.get(nom, "black"), fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8,
                              ec=_COULEURS.get(nom, "black")))

    # Titres / légende
    titre = f"Profil piézométrique — {etat.projet or 'Projet sans titre'}"
    if etat.branches:
        titre += f" ({etat.branches})"
    extra = f"  ·  Q_Ve = {infos['q_ve']:,.0f} m³/h"
    if infos["q_pi1"]:
        extra += f"  ·  Q_PI1 = {infos['q_pi1']:,.0f} m³/h"
    if infos["q_pi2"]:
        extra += f"  ·  Q_PI2 = {infos['q_pi2']:,.0f} m³/h"
    ax.set_title(f"{titre}\nSchéma {schema}  ·  DN {etat.dn_mm:.0f} mm{extra}",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Distance le long du tronçon (m)", fontsize=11)
    ax.set_ylabel("Altitude (m NGM)", fontsize=11)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax.grid(True, ls=":", alpha=0.4)
    ax.set_xlim(-30, xs[-1] + 40)
    ax.set_ylim(min(zs) - 20, max(zs) + 25)

    plt.tight_layout()
    if chemin_png:
        fig.savefig(chemin_png, dpi=150)
    return fig, infos


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    sys.path.insert(0, _ROOT)

    if len(sys.argv) < 2:
        print("Usage : python app\\utils\\trace_piezometrique.py "
              "<projet.json> [sortie.png]")
        sys.exit(1)
    chemin_json = sys.argv[1]
    chemin_png = sys.argv[2] if len(sys.argv) > 2 else "trace.png"
    etat = charger_depuis_json(chemin_json)
    fig, infos = tracer_profil(etat, chemin_png)
    print(f"Projet    : {etat.projet} ({etat.branches})")
    print(f"Schéma    : {etat.schema}  ·  DN {etat.dn_mm:.0f} mm")
    print(f"Q_Ve = {infos['q_ve']:,.1f} m3/h"
          f"   Q_PI1 = {infos['q_pi1']:,.1f} m3/h"
          f"   Q_PI2 = {infos['q_pi2']:,.1f} m3/h")
    if infos["h1"] is not None:
        print(f"H1 = {infos['h1']:+.2f} m -> {infos['verdict1']}")
    if infos["h2"] is not None:
        print(f"H2 = {infos['h2']:+.2f} m -> {infos['verdict2']}")
    print(f"Tracé enregistré -> {chemin_png}")