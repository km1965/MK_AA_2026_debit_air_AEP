# -*- coding: utf-8 -*-
"""Croquis schématique du profil en long — format texte (ASCII).

Représente les points Vi1, PI1, Ve, PI2, Vi2 en fonction des distances cumulées
(abscisse) et des cotes (ordonnée §4.4). Le croquis ne montre que le profil et
ses points (pas les organes installés, vus dans l'onglet Vérification) :
    V  = point haut Ve (ventouse)
    •  = point intermédiaire (PI)
    v  = point bas (Vi1 / Vi2)
"""

MARQUEUR = {
    "vi1": "v", "vi2": "v",
    "pi1": "•", "pi2": "•",
    "ve": "V",
}

LARGEUR = 60   # largeur du canevas (colonnes)
HAUTEUR = 12   # hauteur utile (lignes)


def _cumul_abscisse(schema: str, distances: dict) -> dict:
    """Calcule l'abscisse cumulée (m) de chaque point selon le schéma.

    distances : dictionnaire a,b,c,d,l1,l2 avec les valeurs effectives.
    """
    a = distances.get("a", 0.0)
    b = distances.get("b", 0.0)
    c = distances.get("c", 0.0)
    d = distances.get("d", 0.0)
    l1 = distances.get("l1", 0.0)
    l2 = distances.get("l2", 0.0)

    # Abscisse de base des points (en m), selon la topologie du schéma
    x = {"vi1": 0.0, "pi1": None, "ve": None, "pi2": None, "vi2": None}

    if schema == "1A":
        x["ve"] = l1; x["vi2"] = l1
    elif schema == "1B":
        x["pi1"] = a; x["ve"] = a + b; x["vi2"] = a + b
    elif schema == "2A":
        x["ve"] = 0.0; x["vi1"] = 0.0; x["vi2"] = l2
    elif schema == "2B":
        x["ve"] = 0.0; x["vi1"] = 0.0; x["pi2"] = c; x["vi2"] = c + d
    elif schema == "3A":
        x["ve"] = l1; x["vi2"] = l1 + l2
    elif schema == "3B":
        x["pi1"] = a; x["ve"] = a + b; x["pi2"] = a + b + c; x["vi2"] = a + b + c + d
    elif schema == "4A":
        x["pi1"] = a; x["ve"] = a + b; x["vi2"] = a + b + l2
    elif schema == "4B":
        x["ve"] = l1; x["pi2"] = l1 + c; x["vi2"] = l1 + c + d

    # Rattacher les valeurs manquantes aux bornes connues (pour le tracé)
    vals = [v for v in x.values() if v is not None]
    if x["vi1"] is None:
        x["vi1"] = min(vals)
    for k in ("pi1", "ve", "pi2"):
        if x[k] is None:
            x[k] = None
    return x


def _interp(abscisses: dict, key):
    """Renvoie l'abscisse d'un point, ou une valeur par défaut."""
    return abscisses.get(key)


def croquis_profil(etat) -> str:
    """Génère le croquis ASCII du profil en long pour l'état projet courant."""
    schema = etat.schema
    distances = {k: getattr(etat, k) for k in ("a", "b", "c", "d", "l1", "l2")}
    xabs = _cumul_abscisse(schema, distances)

    cotes = {
        "vi1": etat.z_vi1, "pi1": etat.z_pi1, "ve": etat.z_ve,
        "pi2": etat.z_pi2, "vi2": etat.z_vi2,
    }

    # --- Grille de cotes (ordonnée) ---
    z_min = min(v for v in cotes.values() if v is not None) - 1
    z_max = max(v for v in cotes.values() if v is not None) + 1
    span = max(z_max - z_min, 1e-6)

    # --- Grille d'abscisse (horizontale) ---
    xs = [v for v in xabs.values() if v is not None]
    x_min = min(xs)
    x_max = max(xs)
    x_span = max(x_max - x_min, 1e-6)

    def proj_x(x):
        if x is None:
            return None
        idx = int(round((x - x_min) / x_span * (LARGEUR - 1)))
        return max(0, min(LARGEUR - 1, idx))

    def proj_y(z):
        if z is None:
            return None
        idx = int(round((z_max - z) / span * (HAUTEUR - 1)))
        return max(0, min(HAUTEUR - 1, idx))

    # --- Tracé ---
    grille = [[" " for _ in range(LARGEUR)] for _ in range(HAUTEUR)]

    # Segment entre points consécutifs présents
    points_ordre = ["vi1", "pi1", "ve", "pi2", "vi2"]
    pts = [(k, xabs.get(k), cotes.get(k)) for k in points_ordre
           if xabs.get(k) is not None and cotes.get(k) is not None]

    for (_, x1, z1), (_, x2, z2) in zip(pts, pts[1:]):
        px1, py1 = proj_x(x1), proj_y(z1)
        px2, py2 = proj_x(x2), proj_y(z2)
        # Interpolation linéaire entre les deux points
        steps = max(abs(px2 - px1), abs(py2 - py1), 1)
        for t in range(int(steps) + 1):
            xi = px1 + (px2 - px1) * t / steps
            yi = py1 + (py2 - py1) * t / steps
            cx = int(round(xi))
            cy = int(round(yi))
            if 0 <= cx < LARGEUR and 0 <= cy < HAUTEUR:
                if grille[cy][cx] == " ":
                    grille[cy][cx] = "-"

    # Place les marqueurs des points par-dessus
    for key in points_ordre:
        if xabs.get(key) is None:
            continue
        px = proj_x(xabs[key])
        py = proj_y(cotes[key])
        if px is not None and py is not None:
            grille[py][px] = MARQUEUR.get(key, "o")

    # --- Rendu lignes + échelles ---
    lignes = []
    lignes.append("CROQUIS DU PROFIL EN LONG (schématique)")
    lignes.append("+" + "-" * LARGEUR + "+")
    for r in range(HAUTEUR):
        # cote gauche (max en haut)
        z_gauche = z_max - (r + 0.5) / HAUTEUR * span
        lignes.append(f"|{''.join(grille[r])}| {z_gauche:6.1f}")
    lignes.append("+" + "-" * LARGEUR + "+")

    # --- Légende points ---
    lignes.append(f"Abscisse cumulée : {x_min:.0f} → {x_max:.0f} m")
    lignes.append("Points :")
    for key in points_ordre:
        if xabs.get(key) is None:
            continue
        nom = {"vi1": "Vi1 (bas amont)", "pi1": "PI1", "ve": "Ve (ventouse)",
               "pi2": "PI2", "vi2": "Vi2 (bas aval)"}[key]
        lignes.append(f"    {MARQUEUR.get(key, 'o')} {nom:16s} x={xabs[key]:.0f} m  Z={cotes[key]:.1f} m NGM")
    lignes.append("")
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Version image (PNG) du croquis — matplotlib (backend non-interactif)
# ---------------------------------------------------------------------------

NOM_POINTS = {
    "vi1": "Vi1 (bas amont)", "pi1": "PI1", "ve": "Ve (ventouse)",
    "pi2": "PI2", "vi2": "Vi2 (bas aval)",
}


def _groupe_a_dessiner(etat):
    """Groupe d'organes à représenter sur le profil en long.

    Règle : on dessine toujours le MONTAGE VALIDÉ/CONFORME, jugé sur le
    critère de la MÉTHODE DE DIMENSIONNEMENT SÉLECTIONNÉE (etat.methode_dimensionnement) :
      - "mk_aa" : cumul conforme face aux débits MK_A.A (Q_Ve majoré)
        + vitesse ≤ 40 m/s → la proposition client est dessinée telle quelle ;
      - "breche"   : cumul conforme face à la casse franche (Q_eau) + vanne
        sans étranglement + vitesse < 40 m/s → la proposition client est dessinée ;
      - sinon → le groupe optimisé proposé (etat.groupe_optimise()["groupe"]),
        marqué « montage retenu proposé ».

    Retour : {"organes":[...], "optimise":bool, "titre":str}
    """
    methode = (getattr(etat, "methode_dimensionnement", "mk_aa") or "mk_aa").lower()
    client_conforme = False
    if etat.organes_client:
        try:
            if methode == "breche":
                c = etat.cumul_debits()
                client_conforme = (c["verdict_admission"] and c["vanne"]["conforme"]
                                   and c["limite_vitesse"]["ok"])
            else:
                g = etat.verifier_groupe_mk_aa()
                client_conforme = g["conforme"] and g["vitesse"]["ok"]
        except Exception:
            client_conforme = False

    if client_conforme:
        organes = [o for o in etat.organes_client if o.get("type") != "vanne"]
        titre = "Montage validé — proposition client (conforme)"
        optimise = False
    else:
        try:
            opt = etat.groupe_optimise()
            organes = [o for o in opt.get("groupe", []) if o.get("type") != "vanne"]
            titre = "Montage retenu proposé (groupe optimisé conforme)"
            optimise = True
        except Exception:
            organes = [o for o in (etat.organes_client or []) if o.get("type") != "vanne"]
            titre = "Organes (proposition client)"
            optimise = False
    return {"organes": organes, "optimise": optimise, "titre": titre}


def points_profil(etat) -> list:
    """Retourne la liste ordonnée des points pertinents du profil.

    Chaque élément : (clé, x_m, z_m, marqueur). Seuls les points effectivement
    présents dans le schéma sont renvoyés (Ni1 toujours, PI selon le schéma).
    """
    distances = {k: getattr(etat, k) for k in ("a", "b", "c", "d", "l1", "l2")}
    xabs = _cumul_abscisse(etat.schema, distances)
    cotes = {
        "vi1": etat.z_vi1, "pi1": etat.z_pi1, "ve": etat.z_ve,
        "pi2": etat.z_pi2, "vi2": etat.z_vi2,
    }
    ordre = ["vi1", "pi1", "ve", "pi2", "vi2"]
    pts = []
    for k in ordre:
        xm = xabs.get(k)
        if xm is None or cotes.get(k) is None:
            continue
        pts.append((k, xm, cotes[k], MARQUEUR.get(k, "o")))
    return pts


def croquis_png(etat, chemin: str) -> str:
    """Génère le croquis du profil en long en PNG (matplotlib).

    Retourne le chemin du fichier écrit. Lève ImportError si matplotlib absent.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "matplotlib requis pour le croquis PNG — `pip install matplotlib`"
        ) from e

    pts = points_profil(etat)
    xs = [p[1] for p in pts]
    zs = [p[2] for p in pts]

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    # ligne de profil
    ax.plot(xs, zs, color="#1f6feb", linewidth=2.2, zorder=2,
            marker="o", markersize=7, markerfacecolor="white",
            markeredgecolor="#1f6feb", markeredgewidth=2)

    # marqueurs spécifiques selon le type (ventouse en rouge)
    styles = {"ve": ("#d64545", "^", 13), "pi": ("#f1c40f", "s", 9), "vi": ("#555", "o", 9)}
    for k, xm, zm, marq in pts:
        if k == "ve":
            ax.plot(xm, zm, marker="^", color="#d64545", markersize=13, zorder=4)
        elif k == "pi1" or k == "pi2":
            ax.plot(xm, zm, marker="s", color="#f1c40f", markersize=9, zorder=4)
        else:
            ax.plot(xm, zm, marker="o", color="#333333", markersize=9, zorder=4)

    # annotations des points
    for k, xm, zm, marq in pts:
        nom = NOM_POINTS[k]
        dy = 6 if k == "ve" else (4 if k in ("pi1", "pi2") else -8)
        ax.annotate(f"{nom}\nZ={zm:.1f} m", (xm, zm), textcoords="offset points",
                    xytext=(0, dy), ha="center", fontsize=8, color="#222",
                    arrowprops=dict(arrowstyle="-", color="#888", lw=0.8))

    # Le croquis ne représente pas les organes installés (voir l'onglet
    # « Vérification des organes » et le récapitulatif par point haut).
    ax.set_xlabel("Abscisse cumulée (m)")
    ax.set_ylabel("Altitude (m NGM)")
    ax.set_title(f"Profil en long — Schéma {etat.schema} (MK_A.A 2026)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlim(min(xs) - (max(xs) - min(xs)) * 0.05,
                max(xs) + (max(xs) - min(xs)) * 0.05)
    marg = max(max(zs) - min(zs), 5) * 0.2
    ax.set_ylim(min(zs) - marg, max(zs) + marg)

    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    return chemin


# ---------------------------------------------------------------------------
# Version « profil complet » — chaîne de tronçons (ASCII + PNG)
# ---------------------------------------------------------------------------

def croquis_chain_ascii(pc) -> str:
    """Croquis ASCII du profil complet (multi-tronçons).

    pc : ResultatProfilComplet (app.core.profil_complet).
    """
    if not pc.points:
        return "CROQUIS DU PROFIL COMPLET : aucune donnée (aucun tronçon)."
    largeur = 76
    hauteur = 12

    # --- Grille des cotes ---
    z_min = pc.z_min - 1
    z_max = pc.z_max + 1
    span = max(z_max - z_min, 1e-6)
    xa = [p.x for p in pc.points]
    x_min = min(xa); x_max = max(xa)
    x_span = max(x_max - x_min, 1e-6)

    def proj_x(x):
        idx = int(round((x - x_min) / x_span * (largeur - 1)))
        return max(0, min(largeur - 1, idx))

    def proj_y(z):
        idx = int(round((z_max - z) / span * (hauteur - 1)))
        return max(0, min(hauteur - 1, idx))

    grille = [[" " for _ in range(largeur)] for _ in range(hauteur)]
    pts = sorted(pc.points, key=lambda p: p.x)
    for (p1, p2) in zip(pts, pts[1:]):
        px1, py1 = proj_x(p1.x), proj_y(p1.z)
        px2, py2 = proj_x(p2.x), proj_y(p2.z)
        steps = max(abs(px2 - px1), abs(py2 - py1), 1)
        for t in range(int(steps) + 1):
            cx = int(round(px1 + (px2 - px1) * t / steps))
            cy = int(round(py1 + (py2 - py1) * t / steps))
            if 0 <= cx < largeur and 0 <= cy < hauteur and grille[cy][cx] == " ":
                grille[cy][cx] = "-"
    # Marqueurs par-dessus
    for p in pts:
        px, py = proj_x(p.x), proj_y(p.z)
        if 0 <= px < largeur and 0 <= py < hauteur:
            grille[py][px] = p.marque

    lignes = ["CROQUIS DU PROFIL COMPLET (chaîne de tronçons, schématique)"]
    lignes.append("+-----------------------------------" + "-" * (largeur - 35) + "+")
    for r in range(hauteur):
        z_g = z_max - (r + 0.5) / hauteur * span
        lignes.append(f"|{''.join(grille[r])}| {z_g:6.1f}")
    lignes.append("+-----------------------------------" + "-" * (largeur - 35) + "+")
    lignes.append(f"Abscisse cumulée : {x_min:.0f} → {x_max:.0f} m")
    lignes.append("Points (V ventouse · • point intermédiaire · v point bas) :")
    for p in pts:
        nom = {"vi1": "Vi1", "pi1": "PI1", "ve": "Ve", "pi2": "PI2",
               "vi2": "Vi2"}.get(p.cle, p.cle)
        lignes.append(f"    {p.marque} {p.tr}/{nom:3s} x={p.x:.0f} m  Z={p.z:.1f} m NGM")
    return "\n".join(lignes)


def croquis_chain_png(pc, chemin: str) -> str:
    """Génère le PNG du profil en long complet (multi-tronçons, matplotlib)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "matplotlib requis pour le croquis PNG — `pip install matplotlib`"
        ) from e

    if not pc.points:
        raise ValueError("Aucun point de profil à dessiner (chaîne vide).")

    pts = sorted(pc.points, key=lambda p: p.x)
    xs = [p.x for p in pts]
    zs = [p.z for p in pts]

    fig, ax = plt.subplots(figsize=(11, 4.5), dpi=150)
    ax.plot(xs, zs, color="#1f6feb", linewidth=2.2, zorder=2,
            marker="o", markersize=6, markerfacecolor="white",
            markeredgecolor="#1f6feb", markeredgewidth=2)

    titre = "Profil en long complet — chaîne " + " → ".join(
        rt.label for rt in pc.troncons)
    by_tr = {rt.label: rt for rt in pc.troncons}
    for p in pts:
        if p.cle == "ve":
            ax.plot(p.x, p.z, marker="^", color="#d64545", markersize=13, zorder=4)
            if p.tr in by_tr:
                q = by_tr[p.tr].res.q_ve_m3h
                ax.annotate(f"{p.tr} Ve — Q_Ve = {q:,.0f} m³/h\nZ={p.z:.1f} m",
                            (p.x, p.z), textcoords="offset points", xytext=(0, 12),
                            ha="center", fontsize=8, color="#7a1f1f",
                            arrowprops=dict(arrowstyle="-", color="#d64545", lw=0.8))
            else:
                ax.annotate(f"{p.tr} Ve\nZ={p.z:.1f} m", (p.x, p.z),
                            textcoords="offset points", xytext=(0, 12),
                            ha="center", fontsize=8, color="#7a1f1f",
                            arrowprops=dict(arrowstyle="-", color="#d64545", lw=0.8))
        elif p.cle in ("pi1", "pi2"):
            ax.plot(p.x, p.z, marker="s", color="#f1c40f", markersize=8, zorder=4)
            ax.annotate(f"{p.tr} {p.cle.upper()}\nZ={p.z:.1f} m", (p.x, p.z),
                        textcoords="offset points", xytext=(0, 4),
                        ha="center", fontsize=7, color="#555",
                        arrowprops=dict(arrowstyle="-", color="#aaa", lw=0.6))
        else:
            ax.plot(p.x, p.z, marker="o", color="#333333", markersize=8, zorder=4)

    # Marquer les jonctions (vidanges communes) d'un anneau
    for j in pc.jonctions:
        # abscisse du point commun = longueur cumulée en fin de TRi
        rt_i = next((rt for rt in pc.troncons if rt.label == j.tron_gauche), None)
        if rt_i is None:
            continue
        x_jonc = rt_i.x_debut + max(
            v for v in _cumul_abscisse(
                rt_i.troncon.schema,
                {k: getattr(rt_i.troncon, k)
                 for k in ("a", "b", "c", "d", "l1", "l2")}).values()
            if v is not None)
        if x_jonc < min(xs) or x_jonc > max(xs):
            continue
        z_jonc = j.z_vi1_tr_i1
        ok_c = "OK" if j.ok else f"écart {j.ecart_m:.2f} m"
        ax.annotate(f"{j.label}\nZ={z_jonc:.1f} m — {ok_c}",
                    (x_jonc, z_jonc), textcoords="offset points", xytext=(0, -22),
                    ha="center", fontsize=7, color="#134a8e",
                    arrowprops=dict(arrowstyle="-", color="#134a8e", lw=0.8))
        ax.scatter([x_jonc], [z_jonc], s=90, facecolors="none",
                   edgecolors="#134a8e", linewidths=1.4, zorder=5)

    ax.set_xlabel("Abscisse cumulée (m)")
    ax.set_ylabel("Altitude (m NGM)")
    ax.set_title(titre)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlim(min(xs) - (max(xs) - min(xs)) * 0.03,
                max(xs) + (max(xs) - min(xs)) * 0.03)
    marg = max(max(zs) - min(zs), 5) * 0.2
    ax.set_ylim(min(zs) - marg, max(zs) + marg)
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    return chemin
