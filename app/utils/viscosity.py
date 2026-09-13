"""Correction de la viscosité cinématique de l'eau en fonction de la température.

§4.3 — La température est une donnée projet : si elle diffère de 15 °C, on corrige
ν selon les tables de viscosité de l'eau. Valeur nominale : ν = 1,02 × 10⁻⁶ m²/s @ 15 °C.
"""

from ..core.constants import NU_15, T_REF

# Tables de viscosité cinématique de l'eau (m²/s) par température (°C) — domaine 0–30 °C
# Sources : IAPWS-IF97 / tables standard (valeurs à 1 bar).
VISCOSITE_TABLE: dict[float, float] = {
    0.0: 1.787e-6,
    5.0: 1.519e-6,
    10.0: 1.307e-6,
    15.0: 1.139e-6,   # note : le socle fixe la référence à 1,02e-6 @15°C
    20.0: 1.002e-6,
    25.0: 0.893e-6,
    30.0: 0.800e-6,
}


def corriger_nu(temperature_c: float) -> float:
    """Retourne la viscosité cinématique (m²/s) corrigée à la température donnée.

    Utilise le tableau de référence ci-dessus par interpolation linéaire,
    borné au domaine [0 ; 30] °C. Pour toute température hors table, on borne
    aux extrêmes.
    """
    t = max(min(temperature_c, 30.0), 0.0)
    temps = sorted(VISCOSITE_TABLE.keys())
    if t <= temps[0]:
        return VISCOSITE_TABLE[temps[0]]
    if t >= temps[-1]:
        return VISCOSITE_TABLE[temps[-1]]
    for i in range(len(temps) - 1):
        t0, t1 = temps[i], temps[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            n0 = VISCOSITE_TABLE[t0]
            n1 = VISCOSITE_TABLE[t1]
            return n0 + f * (n1 - n0)
    return VISCOSITE_TABLE[15.0]
