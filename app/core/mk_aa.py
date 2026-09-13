"""Formule explicite en débit — MK_A.A (2026) — §3.3 du cahier des charges.

Le système Darcy-Weisbach (①) + Colebrook-White (②), implicite en λ, est résolu
explicitement en Q :

    Q = −(π/2) · D^(5/2) · √(2g·ΔH/L) · log₁₀[ k/(3,71·D)
                  + 2,51·ν / (D^(3/2)·√(2g·ΔH/L)) ]

Propriétés :
    - Q > 0 car log₁₀(arg) < 0 en régime turbulent (arg < 1).
    - Validité : Re > 4000 et k/D ∈ [10⁻⁶ ; 10⁻²] (à vérifier après calcul).
    - Précision ± 3 % vs méthode itérative complète.
    - Directement applicable sans itération.
"""

import math

from .constants import G, K


class ValiditeError(ValueError):
    """Levée quand les conditions de validité de la formule ne sont pas vérifiées."""


def formule_mk_aa(dh: float, l: float, d: float, nu: float,
                     verification: bool = True) -> dict:
    """Applique la formule explicite MK_A.A (2026).

    Paramètres
    ----------
    dh : ΔH perte de charge totale disponible (m) — doit être > 0
    l  : longueur du tronçon (m) — doit être > 0
    d  : diamètre intérieur de la conduite (m)
    nu : viscosité cinématique (m²/s)
    verification : active la vérification des conditions de validité (Re, k/D)

    Retour
    ------
    dict contenant : q (m³/s), v (vitesse, m/s), re (Reynolds), log10_argument,
    kd, et les validités.
    """
    if dh <= 0:
        return {
            "q": 0.0, "v": 0.0, "re": 0.0,
            "log10_argument": None, "kd": K / d,
            "valide": True, "message": "ΔH ≤ 0 → pas d'écoulement gravitaire (Q = 0)",
        }
    if l <= 0:
        raise ValueError("Longueur L doit être > 0")

    # Terme √(2g·ΔH/L)
    racine = math.sqrt(2.0 * G * dh / l)

    # Argument du log₁₀
    arg = K / (3.71 * d) + 2.51 * nu / (d ** 1.5 * racine)

    if arg >= 1.0:
        # log₁₀(arg) ≥ 0 → pas de régime turbulent gravitaire (Q ≤ 0)
        return {
            "q": 0.0, "v": 0.0, "re": 0.0,
            "log10_argument": arg, "kd": K / d,
            "valide": True, "message": "log₁₀(arg) ≥ 0 → Q = 0 (pas de turbulence)",
        }

    log10_arg = math.log10(arg)
    q = -(math.pi / 2.0) * (d ** 2.5) * racine * log10_arg
    q = max(q, 0.0)

    # Vitesse et Reynolds
    section = math.pi / 4.0 * d * d
    v = q / section if section > 0 else 0.0
    re = v * d / nu if nu > 0 else 0.0

    # Conditions de validité
    kd = K / d
    validations = {
        "re_ok": re > 4000,
        "kd_ok": 1e-6 <= kd <= 1e-2,
    }
    valide = validations["re_ok"] and validations["kd_ok"]

    if verification and not valide:
        msgs = []
        if not validations["re_ok"]:
            msgs.append(f"Re = {re:.0f} ≤ 4000 (régime non vérifié)")
        if not validations["kd_ok"]:
            msgs.append(f"k/D = {kd:.3e} hors domaine [10⁻⁶ ; 10⁻²]")
        raise ValiditeError("Conditions de validité non vérifiées : " + "; ".join(msgs))

    return {
        "q": q, "v": v, "re": re,
        "log10_argument": log10_arg, "kd": kd,
        "valide": valide, "dh": dh, "l": l,
        "validations": validations,
    }


def q_m3h(q_ms: float) -> float:
    """Convertit un débit en m³/s vers m³/h."""
    return q_ms * 3600.0


def q_m3s(q_m3h: float) -> float:
    """Convertit un débit en m³/h vers m³/s."""
    return q_m3h / 3600.0
