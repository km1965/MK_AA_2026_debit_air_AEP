"""Socle de calcul FIXE (non modifiable) — Note technique MK_A.A 2026.

Ces valeurs et formules constituent le cœur de calcul : elles sont identiques
pour tous les projets et ne se modifient pas dans l'application.
Cf. README_MK_A.A.md §3.
"""

from dataclasses import dataclass

# Références normatives citées dans les rapports (BCT : rapports explicites).
REFERENCES_NORMATIVES = [
    "NF EN 805 — Alimentation en eau : exigences des systèmes et des éléments hors bâtiments "
    "(dépression admissible 3 mCE, vitesses d'eau).",
    "NF EN 1074-1 — Robinetterie pour adduction d'eau : exigences d'aptitude à l'emploi "
    "(prescriptions générales et essais).",
    "NF EN 1074-4 — Robinetterie pour adduction d'eau : exigences et essais des ventouses "
    "(admission et expulsion d'air, grand orifice).",
    "NF EN 545 / ISO 2531 — Tuyaux, raccords et accessoires en fonte ductile "
    "(conductivité hydraulique des conduites AEP).",
    "Méthode de dimensionnement MK_A.A (2026) — débits d'air admis en conduites AEP : "
    "formule explicite Darcy-Weisbach / Colebrook-White / MK_A.A, 8 schémas de vidange.",
]

# ---------------------------------------------------------------------------
# 3.1 Paramètres physiques fixes
# ---------------------------------------------------------------------------
G: float = 9.81          # Accélération de la pesanteur (m/s²)
K: float = 0.0005        # Rugosité absolue fonte ductile (m)
NU_15: float = 1.02e-6   # Viscosité cinématique à 15°C (m²/s)
T_REF: float = 15.0      # Température de référence du socle (°C)
SEUIL_DEPRESSION: float = 3.0   # Dépression max admissible en Ve (mCE) — NF EN 805


@dataclass(frozen=True)
class DonneesConduite:
    """Caractéristiques géométriques déduites du diamètre nominal."""
    dn: float              # Diamètre nominal (mm)
    d: float               # Diamètre intérieur (m)
    section: float         # S = π/4·D² (m²)
    kd: float              # Rapport k/D (adimensionnel)

    @staticmethod
    def from_dn(dn_mm: float) -> "DonneesConduite":
        d = dn_mm / 1000.0
        section = 3.141592653589793 / 4.0 * d * d
        return DonneesConduite(dn=dn_mm, d=d, section=section, kd=K / d)


def debits_remplissage_table() -> dict:
    """Table de référence §9.1 (V_eau = 2 m/s)."""
    v = 2.0
    rows = {}
    for dn in (1400, 1600, 2000):
        c = DonneesConduite.from_dn(dn)
        q = v * c.section * 3600.0
        rows[dn] = round(q)
    return rows
