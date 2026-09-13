"""Dimensionnement des organes — §8 (organes) et §9 (remplissage & purgeur).

Sélection avec marge de sécurité et plafond d'utilisation en cascade.

La sur-capacité totale demandée est le produit des deux facteurs :
    besoin × marge × 1/plafond
Le plafond d'utilisation (90 %) réserve déjà une marge sur la capacité
installée ; une marge directe supplémentaire de 25 % en parallèle donnerait
un total de 1,25/0,90 ≈ 1,39 (+39 %), excessif. On retient donc une marge
directe de 15 % pour un total de 1,15/0,90 ≈ 1,28 (+28 %), toujours
supérieur à l'ancienne marge unique de 25 % (§8.1) et aligné sur les
défauts de la note MK_A.A 2026 (marge +15 %, plafond d'utilisation 90 %).

Plusieurs organes en parallèle si nécessaire.

Données catalogue : app.data.catalogues (CEAI, TRIFON, PSA).
"""

from dataclasses import dataclass, field
import math

from ..data.catalogues import CEAI, TRIFON, PSA, DEPRESSION_NOMINALE
from ..core.constants import DonneesConduite

# Marge directe sur le débit dimensionnant (coudes, accessoires, incertitudes).
MARGE_ACCESSOIRES_PCT: float = 15.0
# Plafond d'utilisation de la capacité installée (réserve de sécurité).
PLAFOND_UTILISATION_PCT: float = 90.0


@dataclass
class SelectionOrgane:
    """Résultat de la sélection d'un organe (éventuellement en parallèle)."""
    nom: str
    dn: int
    capacite_unitaire_m3h: float
    nombre: int
    capacite_installee_m3h: float
    besoin_m3h: float
    taux_utilisation: float          # % : besoin / capacité installée
    marge_appliquee: float           # % appliqué sur le besoin


def _marge_factor(marge_pct: float) -> float:
    """Convertit une marge % en facteur multiplicatif (15 % → 1.15)."""
    return 1.0 + marge_pct / 100.0


def _nombre_parallele(capacite_installee_m3h: float, capacite_unitaire_m3h: float) -> int:
    """Nombre d'organes en parallèle (arrondi supérieur), min 1."""
    if capacite_unitaire_m3h <= 0:
        return 1
    return max(1, math.ceil(capacite_installee_m3h / capacite_unitaire_m3h))


def choisir_ventouse(besoin_m3h: float, marge_pct: float = MARGE_ACCESSOIRES_PCT,
                     plafond_pct: float = PLAFOND_UTILISATION_PCT, table: dict = None,
                     nom: str = "") -> SelectionOrgane:
    """Sélection d'une ventouse couvrant le besoin avec marge.

    Choisit le plus petit DN dont [capacité unitaire ≥ besoin×marge / plafond]
    ou plusieurs organes en parallèle si le DN max ne suffit pas.

    table : catalogue {dn: {"q": {depr: cap}}} (défaut : TRIFON).
    nom   : libellé du fournisseur pour la sélection (défaut : TRIFON).
    """
    t = table or TRIFON
    nom_org = nom or "TRIFON"
    besoin_majore = besoin_m3h * _marge_factor(marge_pct)
    depr = DEPRESSION_NOMINALE
    dns = sorted(t.keys())
    dn_max = dns[-1]
    cap_max = t[dn_max]["q"][depr]

    # Capacité installée minimale pour respecter le plafond d'utilisation
    cap_min_installee = besoin_majore / (plafond_pct / 100.0)

    if besoin_m3h <= 0:
        return SelectionOrgane(nom_org, dn_max, cap_max, 0, 0, 0, 0.0, marge_pct)

    # Cas où un seul organe suffit
    for dn in dns:
        cap = t[dn]["q"][depr]
        if cap >= besoin_majore and cap >= cap_min_installee:
            taux = besoin_majore / cap * 100.0
            return SelectionOrgane(nom_org, dn, cap, 1, cap, besoin_majore,
                                   taux, marge_pct)

    # Sinon : plusieurs organes en parallèle (DN max)
    nombre = _nombre_parallele(cap_min_installee, cap_max)
    installee = nombre * cap_max
    taux = besoin_majore / installee * 100.0
    return SelectionOrgane(nom_org, dn_max, cap_max, nombre, installee,
                           besoin_majore, taux, marge_pct)


def choisir_clapet(besoin_m3h: float, marge_pct: float = MARGE_ACCESSOIRES_PCT,
                   plafond_pct: float = PLAFOND_UTILISATION_PCT, table: dict = None,
                   nom: str = "") -> SelectionOrgane:
    """Sélection d'un clapet d'entrée d'air à la dépression nominale.

    table : catalogue {dn: {"q": {depr: cap}}} (défaut : CEAI).
    nom   : libellé du fournisseur pour la sélection (défaut : CEAI).
    """
    t = table or CEAI
    nom_org = nom or "CEAI"
    besoin_majore = besoin_m3h * _marge_factor(marge_pct)
    depr = DEPRESSION_NOMINALE
    dns = sorted(t.keys())
    dn_max = dns[-1]
    cap_max = t[dn_max]["q"][depr]
    cap_min_installee = besoin_majore / (plafond_pct / 100.0) if besoin_majore > 0 else 0

    if besoin_m3h <= 0:
        return SelectionOrgane(nom_org, dn_max, cap_max, 0, 0, 0, 0.0, marge_pct)

    for dn in dns:
        cap = t[dn]["q"][depr]
        if cap >= besoin_majore and cap >= cap_min_installee:
            taux = besoin_majore / cap * 100.0
            return SelectionOrgane(nom_org, dn, cap, 1, cap, besoin_majore, taux, marge_pct)

    nombre = _nombre_parallele(cap_min_installee, cap_max)
    installee = nombre * cap_max
    taux = besoin_majore / installee * 100.0
    return SelectionOrgane(nom_org, dn_max, cap_max, nombre, installee,
                           besoin_majore, taux, marge_pct)


# ---------------------------------------------------------------------------
# §9 — Remplissage & purgeur PSA
# ---------------------------------------------------------------------------

def q_remplissage(v_eau_ms: float, dc: DonneesConduite) -> float:
    """§9.1 : Q_remplissage = V_eau × (π/4) × D² × 3600  [m³/h]."""
    return v_eau_ms * dc.section * 3600.0


def choisir_purgeur_psa(q_remplissage_m3h: float, dn_psa: int = 250,
                        plafond_pct: float = PLAFOND_UTILISATION_PCT) -> SelectionOrgane:
    """Sélection du nombre de purgeurs PSA (§9.2).

    Nombre requis = Q_remplissage / capacité unitaire PSA (arrondi supérieur),
    conformément à la note (§9.2, Tableau Annexe C).
    """
    cap = PSA[dn_psa]["q_remplissage"]
    if q_remplissage_m3h <= 0:
        return SelectionOrgane(f"PSA {dn_psa}", dn_psa, cap, 1, cap, 0, 0.0, 0.0)
    nombre = math.ceil(q_remplissage_m3h / cap)
    installee = nombre * cap
    taux = q_remplissage_m3h / installee * 100.0
    return SelectionOrgane(f"PSA {dn_psa}", dn_psa, cap, nombre, installee,
                           q_remplissage_m3h, taux, 0.0)


# Vitesse de sortie d'air sonique de référence (README §9.2 / Annexe C)
# --- Modèle physique du purgeur sonique SNH (NSH) --------------------------
# Détendeur sonique (orifice convergent) : débit massique en condition
# sonique (détente gazeuse) = C_d · A_t · P_amont · C*, avec
#     C* = sqrt( k/(R·T) · (2/(k+1))**((k+1)/(k-1)) )
# k=1,4 (air), R=287,06 J/kg·K, T=293,15 K (20 °C), C_d≈0,8.
# Le catalogue NSH donne la capacité sonique q_capacity (air libre) à la
# pression de service nominale P_svc. Comme le débit sonique est proportionnel
# à la pression amont absolue, la capacité à la pression de remplissage
# P_fill (absolue) vaut :  Q_fill = q_capacity · P_fill_abs / P_svc_abs.

K_AIR = 1.4
R_AIR_J = 287.06  # J/kg·K
T_AIR_K = 293.15  # 20 °C
C_D_ORIFICE = 0.8

# Pression de service nominale SNH (bar abs) = 10 bar (catalogue NSH)
P_SVC_SNH_BAR = 10.0
# Surpression de remplissage à l'évent (bar) : petite hauteur d'eau à l'avancée
# du front → on applique une faible surpression (≈0,1 bar) au-dessus de l'atm.
P_FILL_GAUGE_BAR = 0.1
P_ATM_BAR = 1.013

# Coefficients soniques (démonstration / traçabilité)
C_STAR = math.sqrt(K_AIR / (R_AIR_J * T_AIR_K)
                   * (2.0 / (K_AIR + 1.0)) ** ((K_AIR + 1.0) / (K_AIR - 1.0)))
RHO_AIR_STD = P_ATM_BAR * 1e5 / (R_AIR_J * T_AIR_K)  # kg/m³
# Section effective (m²) équivalente au débit sonique catalogue à P_svc :
#   A_t = (q_capacity/3600)·ρ_std / (C_d·P_svc·C*)
AREA_CONST = (1.0 / 3600.0) * RHO_AIR_STD / (C_D_ORIFICE
               * (P_SVC_SNH_BAR * 1e5) * C_STAR)


def _cap_sonique_snh(q_capacity_std: float, p_svc_bar: float = P_SVC_SNH_BAR) -> float:
    """Capacité sonique de remplissage SNH (m³/h, air libre) d'après le modèle
    physique : Q_fill = q_capacity · P_fill_abs / P_svc_abs.

    p_svc_bar : pression de service nominale (classe PN) à laquelle la capacité
    catalogue q_capacity a été relevée (10 bar par défaut)."""
    p_fill = (P_ATM_BAR + P_FILL_GAUGE_BAR) * 1e5
    p_svc = p_svc_bar * 1e5
    return q_capacity_std * (p_fill / p_svc)


def choix_purgeur_snh(q_remplissage_m3h: float, pn: float = 10.0) -> SelectionOrgane:
    """Dimensionne les purgeurs soniques SNH (NSH) au remplissage.

    Méthode : modèle physique de débit sonique (orifice convergent) ancré sur
    la capacité catalogue NSH — Q_fill = q_capacity·(P_fill/P_svc).
    La pression au remplissage (≈ atmosphérique + faible surpression) rend la
    capacité sonique de très faible ordre : l'évacuation massive au remplissage
    est normalement assurée par le grand orifice des ventouses TRIFON.

    pn : classe PN du projet — la capacité catalogue des purgeurs SNH/NSH est
    relevée SELON la classe PN (cf. « Débit air purgeur sonique NSH.xlsx »),
    ex. DN1500 : PN10→180 m³/h, PN16→144 m³/h.

    Retour : SelectionOrgane (nom "NSH <modèle>", dn = DN purgeur).
    """
    from ..data import valve_db

    def _q_pn(p):
        pressions = p.get("pressions") or {}
        key = str(int(round(float(pn or 10.0))))
        if key in pressions:
            return float(pressions[key])
        return float(p.get("q_capacity") or 0.0)

    f = valve_db.fournisseur("SNH")
    purge = f.get("purgeurs", [])
    if not purge:
        tab = valve_db.table_capacite("SNH", "purgeur")
        dn = max(tab) if tab else 250
        cap = _cap_sonique_snh(tab.get(dn, 0.0), pn)
        if q_remplissage_m3h <= 0:
            return SelectionOrgane("NSH (SNH)", dn, cap, 1, cap, 0, 0.0, 0.0)
        nb = math.ceil(q_remplissage_m3h / cap) if cap > 0 else 0
        return SelectionOrgane("NSH (SNH)", dn, cap, nb, nb * cap,
                               q_remplissage_m3h, q_remplissage_m3h / (nb * cap) * 100.0 if cap else 0.0, 0.0)

    cap0 = _cap_sonique_snh(_q_pn(purge[0]), pn)
    if q_remplissage_m3h <= 0:
        return SelectionOrgane(f"{purge[0]['modele']} (SNH)", purge[0]["dn"],
                               cap0, 1, cap0, 0, 0.0, 0.0)
    if cap0 <= 0:
        return SelectionOrgane("NSH (SNH)", purge[0]["dn"], 0.0, 0, 0.0,
                               q_remplissage_m3h, 0.0, 0.0)

    # Plus grand débit catalogue (à la classe PN) → moindre nombre d'unités.
    p = max(purge, key=_q_pn)
    cap = _cap_sonique_snh(_q_pn(p), pn)
    nb = math.ceil(q_remplissage_m3h / cap)
    installee = nb * cap
    taux = q_remplissage_m3h / installee * 100.0
    return SelectionOrgane(f"{p['modele']} (SNH)", p["dn"], cap, nb,
                           installee, q_remplissage_m3h, taux, 0.0)
