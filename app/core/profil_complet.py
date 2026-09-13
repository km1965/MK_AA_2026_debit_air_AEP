"""Méthode « profil complet » — chaîne de tronçons TR1 … TRn.

Applique la démarche développée pour les notes de calcul multi-tronçons
(BR1/BR2/BR3, TR1→TR3) à partir du moteur tronçon unique de l'app
(`NoteMKAA`) :

  * chaque tronçon TRi est calculé INDÉPENDAMMENT (schéma, cotes, distances)
    avec la formule explicite MK_A.A (2026) ;
  * les points communs entre tronçons sont recousus le long du profil :
     - Vi2(TRi) ≡ Vi1(TR(i+1))  →  VIDANGE COMMUNE (une seule entrée de
       synthèse, débit d'évacuation = max des deux pentes adjacentes) ;
  * la continuité altimétrique de la jonction est vérifiée (alerte si écart) ;
  * une SYNTHÈSE des organes d'air est produite le long du profil (point haut
    Ve → ventouse, PI → clapet si Q_PI > 0, purgeurs de remplissage, vanne) ;
  * le graphe du profil en long complet est reconstitué (abscisses cumulées)
    pour l'exportation (ASCII + PNG).
"""

from dataclasses import dataclass, field
from typing import Optional

from ..core.constants import DonneesConduite, SEUIL_DEPRESSION
from ..core.schemas import NoteMKAA, ResultatSchema
from ..core import dimensionnement as dim
from ..utils import viscosity

# Vitesse de sortie de référence des purgeurs soniques et limite anti
# blocage sonique au point le plus étroit (mêmes valeurs que le tronçon unique).
_V_SONIQUE_MS = 200.0
_V_LIMITE_AIR_MS = 40.0


def _complement_air_profil(manque_m3h: float, dn_ventouse=None,
                           dn_clapet=None) -> list:
    """Complément d'admission proposé en CAS PARTICULIER (règle « Ve/PI »).

    Mêmes règles que le tronçon unique (controller.decomposition_pi) :
      • ventouse ajoutée → TRIFON (double fonction admission + évacuation) ;
      • autre organe ajouté → clapet d'admission SNH ;
      • DN issu de la proposition client (défauts : ventouse DN300, clapet
        SNH DN250) ; sélection = l'option couvrant le manque avec le MOINS
        d'unités (égalité → ventouse TRIFON).
    """
    import math
    from ..data.catalogues import TRIFON
    from ..data.valve_db import table_capacite as _tab

    if manque_m3h <= 0:
        return []
    dn_v = int(dn_ventouse) if dn_ventouse else 300
    dn_c = int(dn_clapet) if dn_clapet else 250
    cap_v = TRIFON.get(dn_v, {}).get("q", {}).get(-3, 0.0) or 0.0
    tab_c = _tab("SNH", "clapet")
    cap_c = tab_c.get(dn_c, 0.0) or 0.0
    nb_v = math.ceil(manque_m3h / cap_v) if cap_v > 0 else 10 ** 9
    nb_c = math.ceil(manque_m3h / cap_c) if cap_c > 0 else 10 ** 9
    if nb_v <= nb_c:
        return [{
            "type": "ventouse", "fournisseur": "TRIFON", "dn": dn_v,
            "nombre": nb_v, "cap_total": nb_v * cap_v,
            "role": "admission + évacuation",
        }]
    return [{
        "type": "clapet", "fournisseur": "SNH", "dn": dn_c,
        "nombre": nb_c, "cap_total": nb_c * cap_c, "role": "admission",
    }]


def _section_dn_m2(dn) -> float:
    """Section (m²) d'un organe par son DN nominal (diamètre en mm)."""
    if not dn:
        return 0.0
    d = float(dn) / 1000.0
    import math
    return math.pi * d * d / 4.0


@dataclass
class ProfilTroncon:
    """Un tronçon de la chaîne — mêmes champs que la saisie « profil en long ».

    label est libre (ex. « TR1 », « TR2 »…). Les champs géométriques suivent
    la convention des schémas de l'app (a,b,c,d,l1,l2, z_vi1…z_vi2).
    """
    label: str = "TR1"
    schema: str = "3B"
    z_vi1: float = 100.0
    z_pi1: float = 0.0
    z_ve: float = 120.0
    z_pi2: float = 0.0
    z_vi2: float = 90.0
    a: float = 500.0
    b: float = 500.0
    c: float = 400.0
    d: float = 600.0
    l1: float = 1000.0
    l2: float = 1000.0

    # ------------------------------------------------------------------
    def has_pi1(self) -> bool:
        return self.schema in ("1B", "3B", "4A")

    def has_pi2(self) -> bool:
        return self.schema in ("2B", "3B", "4B")

    def alt_dict(self) -> dict:
        return {
            "z_vi1": self.z_vi1, "z_pi1": self.z_pi1, "z_ve": self.z_ve,
            "z_pi2": self.z_pi2, "z_vi2": self.z_vi2,
            "a": self.a, "b": self.b, "c": self.c, "d": self.d,
            "l1": self.l1, "l2": self.l2,
        }


@dataclass
class ResultatTroncon:
    """Résultat complet d'un tronçon de la chaîne."""
    troncon: ProfilTroncon
    res: ResultatSchema
    organes: dict                     # {ventouse, clapet} — SelectionOrgane
    remplissage: dict                 # {q, purgeurs, purgeurs_snh}
    nu: float
    dc: DonneesConduite
    x_debut: float = 0.0              # abscisse cumulée du Vi1 dans le profil
    proposition: dict = None          # organes proposés par le client

    @property
    def label(self) -> str:
        return self.troncon.label


@dataclass
class PointProfil:
    """Un point recousu du profil complet.

    cle  : "vi1" | "pi1" | "ve" | "pi2" | "vi2"  (repère local au tronçon)
    x    : abscisse cumulée (m)                   (0 = Vi1 de TR1)
    z    : cote altimétrique (m NGM)
    tr   : tronçon d'origine
    marque : symbole (V ventouse / • PI / v point bas)
    """
    cle: str
    x: float
    z: float
    tr: str
    marque: str = "o"


@dataclass
class Jonction:
    """Jonction entre TRi et TR(i+1) — point bas commun."""
    i: int
    z_vi2_tr_i: float
    z_vi1_tr_i1: float
    ecart_m: float
    ok: bool
    deb_max_m3h: float = 0.0          # max des débits d'évacuation des 2 pentes
    tron_gauche: str = ""             # label du tronçon amont (TRi)
    tron_droit: str = ""              # label du tronçon aval (TR(i+1))

    @property
    def label(self) -> str:
        return f"Vi2({self.tron_gauche})/Vi1({self.tron_droit})"


# Abscisse cumulée locale, dans les mêmes conventions que app/utils/croquis.py
def _cumul_abscisse_local(schema: str, d: dict) -> dict:
    """Renvoie {'vi1','pi1','ve','pi2','vi2' : abscisse locale (m) ou None}."""
    a = d.get("a", 0.0); b = d.get("b", 0.0); c = d.get("c", 0.0)
    d_ = d.get("d", 0.0); l1 = d.get("l1", 0.0); l2 = d.get("l2", 0.0)
    x = {"vi1": 0.0, "pi1": None, "ve": None, "pi2": None, "vi2": None}
    if schema == "1A":
        x["ve"] = l1; x["vi2"] = l1
    elif schema == "1B":
        x["pi1"] = a; x["ve"] = a + b; x["vi2"] = a + b
    elif schema == "2A":
        x["ve"] = 0.0; x["vi1"] = 0.0; x["vi2"] = l2
    elif schema == "2B":
        x["ve"] = 0.0; x["vi1"] = 0.0; x["pi2"] = c; x["vi2"] = c + d_
    elif schema == "3A":
        x["ve"] = l1; x["vi2"] = l1 + l2
    elif schema == "3B":
        x["pi1"] = a; x["ve"] = a + b; x["pi2"] = a + b + c
        x["vi2"] = a + b + c + d_
    elif schema == "4A":
        x["pi1"] = a; x["ve"] = a + b; x["vi2"] = a + b + l2
    elif schema == "4B":
        x["ve"] = l1; x["pi2"] = l1 + c; x["vi2"] = l1 + c + d_
    # Rattachement des points absents pour le tracé
    vals = [v for v in x.values() if v is not None]
    if x["vi1"] is None:
        x["vi1"] = min(vals)
    return x


def _longueur_troncon(schema: str, d: dict) -> float:
    """Longueur développée du tronçon (m) — = abscisse de Vi2."""
    x = _cumul_abscisse_local(schema, d)
    return max(v for v in x.values() if v is not None)


class ResultatProfilComplet:
    """Résultat global de la chaîne de tronçons."""

    def __init__(self):
        self.troncons: list[ResultatTroncon] = []
        self.points: list[PointProfil] = []
        self.jonctions: list[Jonction] = []
        self.avertissements: list[str] = []
        self.dn_mm: float = 0.0
        self.temperature: float = 15.0
        self.pression_nominale: float = 10.0
        self.propositions: list[dict] = []   # aligné sur troncons (None si vide)
        self.verifications: list = []        # verdicts de comparer_propositions()

    # ------------------------------------------------------------------
    @property
    def longueur_totale(self) -> float:
        if not self.points:
            return 0.0
        xs = [p.x for p in self.points]
        return max(xs)

    @property
    def z_min(self) -> float:
        return min(p.z for p in self.points)

    @property
    def z_max(self) -> float:
        return max(p.z for p in self.points)

    def sommets(self):
        """Points hauts Ve (ventouses) de la chaîne, ordonnés."""
        return [p for p in self.points if p.cle == "ve"]

    # ------------------------------------------------------------------
    def synthese_organes(self) -> list:
        """Synthèse des organes d'air le long de la chaîne (tableau rapport).

        Chaque entrée :
            {rep, tr, point, type, dn, nombre, besoin_m3h, z, x}
          - point haut Ve  → ventouse + clapet (besoin = Q_Ve du tronçon) ;
          - PI avec poche d'air (Q_PI > 0) → clapet complémentaire
            (besoin = Q_PI du tronçon) + purgeur sonique SNH ;
          - purgeur de remplissage par tronçon (PSA au point haut Ve) ;
          - purgeur sonique SNH à l'amont de CHAQUE point haut (Ve et PI).
        """
        lignes = []
        rep = 0
        for rt in self.troncons:
            v = rt.organes["ventouse"]
            c = rt.organes["clapet"]
            purge = rt.remplissage["purgeurs"]
            sn = rt.remplissage.get("purgeurs_snh")
            p_ve = next((p for p in self.points
                         if p.tr == rt.label and p.cle == "ve"), None)
            if v.nombre > 0:
                rep += 1
                lignes.append({
                    "rep": f"{rep:02d}", "tr": rt.label, "point": "Ve (point haut)",
                    "type": "Ventouse TRIFON",
                    "dn": v.dn, "nombre": v.nombre,
                    "besoin_m3h": v.besoin_m3h,
                    "prestation": v.nom,
                    "z": p_ve.z if p_ve else None, "x": p_ve.x if p_ve else None,
                })
            # Clapet d'admission (couvre Q_Ve — même besoin que la ventouse)
            if c.nombre > 0:
                rep += 1
                lignes.append({
                    "rep": f"{rep:02d}", "tr": rt.label, "point": "Ve (point haut)",
                    "type": "Clapet d'admission",
                    "dn": c.dn, "nombre": c.nombre,
                    "besoin_m3h": c.besoin_m3h,
                    "prestation": c.nom,
                    "z": p_ve.z if p_ve else None, "x": p_ve.x if p_ve else None,
                })
            # Purgeur de remplissage (§9) + purgeur sonique SNH au point haut Ve
            if purge.nombre > 0:
                rep += 1
                lignes.append({
                    "rep": f"{rep:02d}", "tr": rt.label, "point": "Ve (point haut)",
                    "type": "Purgeur de remplissage",
                    "dn": purge.dn, "nombre": purge.nombre,
                    "besoin_m3h": rt.remplissage["q"],
                    "prestation": purge.nom,
                    "z": p_ve.z if p_ve else None, "x": p_ve.x if p_ve else None,
                })
            if sn is not None and sn.nombre > 0:
                rep += 1
                lignes.append({
                    "rep": f"{rep:02d}", "tr": rt.label, "point": "Ve (point haut)",
                    "type": "Purgeur sonique SNH",
                    "dn": sn.dn, "nombre": 1,
                    "besoin_m3h": sn.capacite_unitaire_m3h,
                    "sonique_m3h": sn.capacite_unitaire_m3h,
                    "prestation": sn.nom,
                    "z": p_ve.z if p_ve else None, "x": p_ve.x if p_ve else None,
                })
            # CAS PARTICULIER — clapet d'admission + purgeur sonique aux PI
            for cle, lbl, q in (("pi1", "PI1 (point intermédiaire)",
                                 rt.res.q_pi1_m3h),
                                ("pi2", "PI2 (point intermédiaire)",
                                 rt.res.q_pi2_m3h)):
                if not ((q or 0) > 0):
                    continue
                if cle == "pi1" and not rt.troncon.has_pi1():
                    continue
                if cle == "pi2" and not rt.troncon.has_pi2():
                    continue
                p_pi = next((p for p in self.points
                             if p.tr == rt.label and p.cle == cle), None)
                sel_pi = dim.choisir_clapet(q)
                if sel_pi.nombre > 0:
                    rep += 1
                    lignes.append({
                        "rep": f"{rep:02d}", "tr": rt.label, "point": lbl,
                        "type": "Clapet d'admission (PI)",
                        "dn": sel_pi.dn, "nombre": sel_pi.nombre,
                        "besoin_m3h": sel_pi.besoin_m3h,
                        "prestation": sel_pi.nom,
                        "z": p_pi.z if p_pi else None,
                        "x": p_pi.x if p_pi else None,
                    })
                if sn is not None and sn.nombre > 0:
                    rep += 1
                    lignes.append({
                        "rep": f"{rep:02d}", "tr": rt.label, "point": lbl,
                        "type": "Purgeur sonique SNH",
                        "dn": sn.dn, "nombre": 1,
                        "besoin_m3h": sn.capacite_unitaire_m3h,
                        "sonique_m3h": sn.capacite_unitaire_m3h,
                        "prestation": sn.nom,
                        "z": p_pi.z if p_pi else None,
                        "x": p_pi.x if p_pi else None,
                    })
        return lignes

    def synthese_vidanges(self) -> list:
        """Vidanges du profil : points bas et jonctions communes.

        Une vidange commune (jonction TRi/TR(i+1)) est listée UNE SEULE FOIS,
        avec débit d'évacuation = max des deux pentes adjacentes.
        """
        import math as _math
        lignes = []
        # Débit d'évacuation par pente : Q_Ve du tronçon (côté sommet).
        # Pour une pente intérieure, on retient le max entre le tronçon amont
        # (côté aval Vi2) et le tronçon aval (côté amont Vi1).
        by_tr = {rt.label: rt for rt in self.troncons}
        for j in self.jonctions:
            rt_i = by_tr.get(j.tron_gauche)
            rt_i1 = by_tr.get(j.tron_droit)
            q_g = (rt_i.res.q_av_m3h if rt_i else 0.0)
            q_d = (rt_i1.res.q_am_m3h if rt_i1 else 0.0)
            lignes.append({
                "tr": j.label,
                "point": f"Vi2({j.tron_gauche}) ≡ Vi1({j.tron_droit})",
                "z": j.z_vi1_tr_i1,
                "q_amont_tr_i": q_g,
                "q_aval_tr_i1": q_d,
                "q_evacuation": _math.ceil(max(q_g, q_d)),
                "continue": j.ok,
                "ecart_m": j.ecart_m,
            })
        return lignes

    def _cap_proposition(self, cat: str, prop: dict, pn: float = None) -> float:
        """Capacité installée (m³/h) d'un organe proposé par le client.

        Réutilise la même évaluation que l'onglet « Vérification » du tronçon
        unique (catalogues internes TRIFON/CEAI/PSA ou base externe valve_database).
        """
        from ..controller import capacite_organe
        return capacite_organe({"type": cat, "dn": prop.get("dn"),
                                "nombre": prop.get("nombre", 0),
                                "fournisseur": prop.get("fournisseur", "")},
                               depr=-3, pn=pn)

    def comparer_propositions(self, pn: float = None):
        """Compare les « organes proposés par le client » ((propositions) aux
        besoins calculés le long de la chaîne — verdict par organe + groupe
        d'air par tronçon, comme l'onglet Vérification du tronçon unique.

        Règle (défauts v3) : besoin majoré = Q_Ve × marge (+15 %) ; capacité
        requise = les organes doivent couvrir le besoin majoré (plafond 90 %).
        """
        from ..core.dimensionnement import MARGE_ACCESSOIRES_PCT, _marge_factor
        self.verifications = []
        if not self.troncons:
            return []
        pn = pn if pn is not None else (self.pression_nominale or 10.0)
        marge = _marge_factor(MARGE_ACCESSOIRES_PCT)

        for i, rt in enumerate(self.troncons):
            prop = self.propositions[i] if i < len(self.propositions) else None
            if not prop:
                continue
            trlabel = rt.label
            besoin = rt.res.q_ve_m3h
            besoin_maj = besoin * marge                      # +15 %
            besoin_remplissage = rt.remplissage["q"]

            # -- Organes proposés (dictionnaires) --
            v_org = prop.get("ventouse") or {}
            c_org = prop.get("clapet") or {}
            p_org = prop.get("purgeur") or {}
            pi_orgs = {"pi1": prop.get("clapet_pi1") or {},
                       "pi2": prop.get("clapet_pi2") or {}}
            cap_v = v_org.get("dn") and self._cap_proposition("trifon", v_org, pn)
            cap_c = c_org.get("dn") and self._cap_proposition("ceai", c_org, pn)
            cap_p = p_org.get("dn") and self._cap_proposition("psa", p_org, pn)
            cap_v = cap_v or 0.0
            cap_c = cap_c or 0.0
            cap_p = cap_p or 0.0

            def _libelle(cat):
                return {"trifon": "Ventouse admission",
                        "ceai": "Clapet admission air",
                        "psa": "Purgeur remplissage"}[cat]

            def _propose_str(org):
                if not org.get("dn"):
                    return "non renseignée"
                s = f"{org.get('nombre', 0)} × DN {org.get('dn')}"
                if org.get("fournisseur"):
                    s += f" [{org['fournisseur']}]"
                return s

            # Ventouse
            conform_v = bool(v_org.get("dn")) and cap_v >= besoin_maj
            self.verifications.append({
                "troncon": trlabel, "categorie": _libelle("trifon"),
                "propose": _propose_str(v_org), "dn": v_org.get("dn"),
                "nombre": v_org.get("nombre", 0),
                "besoin_m3h": besoin_maj, "cap_proposee_m3h": cap_v,
                "conforme": conform_v,
                "deficit_m3h": max(0.0, besoin_maj - cap_v),
                "message": (f"Besoin +15 % = {besoin_maj:.0f} m³/h ; capacité "
                            f"proposée = {cap_v:.0f} m³/h ({_propose_str(v_org)})."),
            })
            # Clapet
            conform_c = bool(c_org.get("dn")) and cap_c >= besoin_maj
            self.verifications.append({
                "troncon": trlabel, "categorie": _libelle("ceai"),
                "propose": _propose_str(c_org), "dn": c_org.get("dn"),
                "nombre": c_org.get("nombre", 0),
                "besoin_m3h": besoin_maj, "cap_proposee_m3h": cap_c,
                "conforme": conform_c,
                "deficit_m3h": max(0.0, besoin_maj - cap_c),
                "message": (f"Besoin +15 % = {besoin_maj:.0f} m³/h ; capacité "
                            f"proposée = {cap_c:.0f} m³/h ({_propose_str(c_org)})."),
            })
            # Purgeur (même règle que tronçon unique : purgeur OU grand orifice
            # de la ventouse couvre l'évacuation massive du remplissage)
            rempli_par_purgeur = cap_p >= besoin_remplissage
            rempli_par_ventouse = cap_v >= besoin_remplissage
            conform_p = bool(p_org.get("dn")) and (
                rempli_par_purgeur or rempli_par_ventouse)
            self.verifications.append({
                "troncon": trlabel, "categorie": _libelle("psa"),
                "propose": _propose_str(p_org), "dn": p_org.get("dn"),
                "nombre": p_org.get("nombre", 0),
                "besoin_m3h": besoin_remplissage, "cap_proposee_m3h": cap_p,
                "conforme": conform_p,
                "deficit_m3h": max(0.0, besoin_remplissage - cap_p),
                "message": (f"Besoin remplissage = {besoin_remplissage:.0f} m³/h ; "
                            f"capacité purgeur = {cap_p:.0f} m³/h"
                            + (f" (ventouse grand orifice {cap_v:.0f} m³/h couvre "
                               f"l'évacuation massive)."
                               if (not rempli_par_purgeur and rempli_par_ventouse)
                               else ("." if rempli_par_purgeur
                                     else f" ; ventouse {cap_v:.0f} m³/h — "
                                          f"à compléter."))),
            })
            # Groupe d'air (admission) du tronçon — mêmes critères que
            # l'onglet Vérification (cumul ventouse+clapet+purgeur)
            cap_groupe = cap_v + cap_c + cap_p
            conform_g = cap_groupe > 0 and cap_groupe >= besoin
            # Annexe « organes vs conduite » : uniquement quand la vanne suit la
            # conduite (DN vanne ≤ DN principal, non précisée comprise). Dans ce
            # cas il n'y a aucun étranglement de vanne à justifier (DN vanne/DN
            # principal = 1) : si le groupe demandé dépasse la capacité de
            # passage de la conduite à 40 m/s, ce SONT LES ORGANES qu'il faut
            # corriger, pas la vanne.
            dn_vanne_spec0 = prop.get("vanne_dn")
            vanne_suivant_conduite = (not bool(dn_vanne_spec0)) or (
                float(dn_vanne_spec0) <= float(self.dn_mm or 0.0) + 1e-9)
            section_conduite = _section_dn_m2(self.dn_mm)
            cap_passage_conduite_40 = (_V_LIMITE_AIR_MS * section_conduite * 3600.0
                                       if section_conduite > 0 else float("inf"))
            organes_en_trop_conduite = (vanne_suivant_conduite
                                        and cap_groupe > cap_passage_conduite_40)
            if organes_en_trop_conduite:
                conform_g = False
            msg_groupe = (f"{cap_v:.0f} + {cap_c:.0f} + {cap_p:.0f} "
                          f"= {cap_groupe:.0f} m³/h vs besoin "
                          f"{besoin:.0f} m³/h → "
                          f"{'COUVERT' if conform_g else 'INSUFFISANT'}.")
            if organes_en_trop_conduite:
                v_exc = cap_groupe / 3600.0 / section_conduite
                msg_groupe += (f" — ⚠ capacité de passage de la DN principale "
                               f"(DN {self.dn_mm:g}) à {_V_LIMITE_AIR_MS:g} m/s = "
                               f"{cap_passage_conduite_40:,.0f} m³/h < groupe "
                               f"proposé {cap_groupe:,.0f} m³/h (vitesse "
                               f"équivalente {v_exc:.1f} m/s) : ORGANES "
                               f"SURDIMENSIONNÉS pour cette conduite → à corriger "
                               f"(réduire les ventouses/clapets ou élargir le "
                               f"collecteur/piquage), la vanne de sectionnement "
                               f"n'étant pas en cause (DN vanne/DN principal = 1).")
            self.verifications.append({
                "troncon": trlabel, "categorie":
                    f"Groupe d'air {trlabel} (admission)",
                "propose": "cumul trifon+ceai+psa", "dn": None,
                "nombre": 0, "besoin_m3h": besoin,
                "cap_proposee_m3h": cap_groupe,
                "cap_passage_conduite_40_m3h": cap_passage_conduite_40,
                "organes_surdimensionnes": organes_en_trop_conduite,
                "conforme": conform_g,
                "deficit_m3h": max(0.0, besoin - cap_groupe),
                "message": msg_groupe,
            })

            # -- Vanne de sectionnement (point haut Ve) --
            # Règles de lecture :
            #  · vanne NON précisée → elle suit la conduite principale :
            #    DN vanne/DN principal = 1 → AUCUN étranglement à justifier,
            #    la vanne ne peut pas être en cause.
            #  · vanne précisée > DN principal → piquage/collecteur élargi,
            #    aucune restriction non plus.
            #  · vanne précisée < DN principal → réel étranglement : contrôle
            #    S vanne vs Σ sections appareils + vitesse d'air à 40 m/s.
            dn_princ = float(self.dn_mm or 0.0)
            vanne_restreinte = (bool(dn_vanne_spec0)
                                and float(dn_vanne_spec0) < dn_princ - 1e-9)
            suit_conduite = (not bool(dn_vanne_spec0)) or (
                float(dn_vanne_spec0) <= dn_princ + 1e-9)
            dn_vanne = float(dn_vanne_spec0) if bool(dn_vanne_spec0) else dn_princ
            section_vanne = _section_dn_m2(dn_vanne)
            # Sections d'écoulement réelles des appareils amont (transitent par
            # la vanne) : DN pour ventouses/clapets, col sonique pour les purgeurs.
            sec_v = _section_dn_m2(v_org.get("dn")) * max(v_org.get("nombre", 0), 0)
            sec_c = _section_dn_m2(c_org.get("dn")) * max(c_org.get("nombre", 0), 0)
            sec_p = (cap_p / (_V_SONIQUE_MS * 3600.0)
                     if cap_p > 0 else 0.0)
            section_amont = sec_v + sec_c + sec_p
            ratio = (section_vanne / section_amont if section_amont > 0
                     else (0.0 if section_vanne == 0 else float("inf")))
            groupe_cap = cap_v + cap_c + cap_p
            capacite_passage_40 = (_V_LIMITE_AIR_MS * section_vanne * 3600.0
                                   if section_vanne > 0 else 0.0)

            if not vanne_restreinte:
                # vanne = conduite (ou élargie) → pas d'étranglement à
                # justifier ; la vitesse de référence est celle de la conduite.
                etranglement_ok = True
                sonique_ok = True
                vitesse_ref = (groupe_cap / 3600.0 / section_conduite
                               if section_conduite > 0 else float("inf"))
                conform_vanne = True
                if bool(dn_vanne_spec0) and dn_vanne > dn_princ + 1e-9:
                    source_vanne = f"DN {dn_vanne:g} (précisée, > DN principal)"
                    bilan_vanne = ("piquage/collecteur élargi au-delà du DN "
                                   "principal : aucune restriction.")
                elif bool(dn_vanne_spec0):
                    source_vanne = f"DN {dn_vanne:g} (précisée, = DN principal)"
                    bilan_vanne = ("DN vanne/DN principal = 1 → aucun "
                                   "étranglement à justifier ; la vanne épouse "
                                   "la conduite principale.")
                else:
                    source_vanne = "DN principal (non précisée par le client)"
                    bilan_vanne = ("DN vanne/DN principal = 1 → aucun "
                                   "étranglement à justifier ; la vanne épouse "
                                   "la conduite principale.")
            else:
                # vanne réellement plus étroite que la conduite → contrôle
                # d'étranglement (S vanne vs Σ sections appareils) et vitesse
                # de passage à travers la vanne (anti blocage sonique 40 m/s).
                etranglement_ok = (section_vanne > 0
                                   and (section_amont == 0 or ratio > 1.0))
                vitesse_ref = (groupe_cap / 3600.0 / section_vanne
                               if section_vanne > 0 else float("inf"))
                sonique_ok = vitesse_ref <= _V_LIMITE_AIR_MS + 1e-9
                conform_vanne = section_vanne > 0 and etranglement_ok and sonique_ok
                source_vanne = f"DN {dn_vanne:g} (précisée, < DN principal)"
                bilan_vanne = (f"S vanne = {section_vanne:.3f} m² vs "
                               f"Σ sections appareils = {section_amont:.3f} m² "
                               f"(ratio {ratio:.2f} "
                               f"{'> 1' if ratio > 1 else '≤ 1 — étranglement !'}) ; "
                               f"vitesse air = {vitesse_ref:.1f} m/s (limite "
                               f"{_V_LIMITE_AIR_MS:g} m/s, anti blocage sonique).")
            self.verifications.append({
                "troncon": trlabel, "categorie": "Vanne de sectionnement",
                "propose": source_vanne, "dn": dn_vanne, "nombre": 1,
                "besoin_m3h": besoin, "cap_proposee_m3h": groupe_cap,
                "conforme": conform_vanne, "deficit_m3h": 0.0,
                "section_vanne_m2": section_vanne,
                "section_amont_m2": section_amont,
                "section_conduite_m2": section_conduite,
                "ratio_etranglement": ratio,
                "v_vanne_ms": vitesse_ref,
                "v_limite_ms": _V_LIMITE_AIR_MS,
                "capacite_passage_40_m3h": capacite_passage_40,
                "vanne_restreinte": vanne_restreinte,
                "suit_conduite": suit_conduite,
                "etranglement_ok": etranglement_ok,
                "sonique_ok": sonique_ok,
                "message": f"Vanne {source_vanne} ; {bilan_vanne} "
                           f"(cap. passage à {_V_LIMITE_AIR_MS:g} m/s = "
                           f"{capacite_passage_40:,.0f} m³/h).",
            })

            # -- CAS PARTICULIER : décomposition Ve / PI (admission poche d'air) --
            # Mêmes règles que le tronçon unique (controller.decomposition_pi) :
            # Ve couvert par les ventouses TRIFON du client ; l'excédent + les
            # clapets SNH couvrent le(s) point(s) intermédiaire(s) (Q_PI > 0) ;
            # complément TRIFON/SNH aux DN proposés par le client si insuffisant.
            # Si un clapet DÉDIÉ a été saisi pour le PI (clapet_pi1/clapet_pi2),
            # le PI est vérifié contre son propre organe (prioritaire).
            from ..core.dimensionnement import (PLAFOND_UTILISATION_PCT,
                                                _marge_factor)
            from ..core.dimensionnement import MARGE_ACCESSOIRES_PCT as _MARGE
            fs = (_marge_factor(_MARGE) / (PLAFOND_UTILISATION_PCT / 100.0))
            besoin_ve_fs = besoin * fs
            surplus_ve = max(cap_v - besoin_ve_fs, 0.0)
            cap_pi_initiale = surplus_ve + cap_c
            for cle, lbl_pi in (("pi1", "PI1 (amont)"),
                                ("pi2", "PI2 (aval)")):
                q_pi = getattr(rt.res, f"q_{cle}_m3h")
                if not ((q_pi or 0) > 0):
                    continue
                if cle == "pi1" and not rt.troncon.has_pi1():
                    continue
                if cle == "pi2" and not rt.troncon.has_pi2():
                    continue
                besoin_pi = q_pi * fs
                pi_org = pi_orgs[cle]
                dedie = bool(pi_org.get("dn"))
                if dedie:
                    cap_pi = self._cap_proposition("ceai", pi_org, pn)
                    manque = max(besoin_pi - cap_pi, 0.0)
                    comp = _complement_air_profil(manque, None, pi_org.get("dn"))
                    cap_ret = cap_pi + (comp[0]["cap_total"] if comp else 0.0)
                    propose = (f"{pi_org.get('nombre', 0)} × clapet "
                               f"DN{pi_org.get('dn')} (dédié "
                               f"{lbl_pi.split(' ')[0]})")
                else:
                    cap_pi = cap_pi_initiale
                    manque = max(besoin_pi - cap_pi_initiale, 0.0)
                    comp = _complement_air_profil(
                        manque, v_org.get("dn"), c_org.get("dn"))
                    cap_ret = cap_pi_initiale + (
                        comp[0]["cap_total"] if comp else 0.0)
                    propose = (f"excédent ventouses {surplus_ve:.0f} + "
                               f"clapets {cap_c:.0f} m³/h (client)")
                conform_pi = cap_ret >= besoin_pi
                add = ""
                if comp:
                    c0 = comp[0]
                    add = (f" → complément : {c0['nombre']}× {c0['fournisseur']} "
                           f"DN{c0['dn']} ({c0['cap_total']:.0f} m³/h, "
                           f"{c0['role']})")
                self.verifications.append({
                    "troncon": trlabel,
                    "categorie": (f"CAS PARTICULIER — {lbl_pi} "
                                  f"(débit d'air à admettre)"),
                    "propose": propose,
                    "dn": pi_org.get("dn") if dedie else None,
                    "nombre": pi_org.get("nombre", 0) if dedie else 0,
                    "besoin_m3h": besoin_pi,
                    "cap_proposee_m3h": cap_ret,
                    "conforme": conform_pi,
                    "deficit_m3h": manque,
                    "message": (f"Besoin majoré (×1,15 ÷0,90) = "
                                f"{besoin_pi:.0f} m³/h ; capacité affectée = "
                                f"{cap_ret:.0f} m³/h ({propose}).{add} → "
                                f"{'CONFORME' if conform_pi else 'NON CONFORME'}."),
                })
                if not dedie:
                    cap_pi_initiale = max(cap_ret - besoin_pi, 0.0)
        return self.verifications

    def conclusion_globale(self) -> dict:
        """Conclusion globale : conforme / non conforme + points à revoir."""
        sains = [v for v in self.verifications if v["conforme"]]
        defs = [v for v in self.verifications if not v["conforme"]]
        defauts = {}
        for v in defs:
            defauts.setdefault(v["troncon"], []).append(v)
        return {
            "conforme": not defs,
            "nb_verdicts": len(self.verifications),
            "nb_sains": len(sains),
            "nb_defauts": len(defs),
            "defauts_par_troncon": defauts,
        }

    def recap_ph(self, pn: float = None) -> list:
        """Récapitulatif « implantation par point haut » (tableau du rapport).

        Fondé sur les organes PROPOSÉS par le client (self.propositions) :
          - point haut Ve → ventouses + clapet (le purgeur de dégazage est
            signalé dans l'implantation mais EXCLU de la capacité d'admission) ;
          - PI avec poche d'air (Q_PI > 0) → clapets d'admission DÉDIÉS
            (clapet_pi1 / clapet_pi2) si saisis, sinon clapets répartis au
            prorata des Q_PI si PI1 et PI2 sont tous deux actifs ;
          - ligne « Groupe (Ve + PI) » = Σ capacités / Σ besoins (Q_Ve + Q_PI)
            lorsque le tronçon comporte au moins un PI actif ;
          - CAS NORMAL (aucun PI actif) → toute l'admission est au point haut
            Ve (ventouses + clapets confondus).

        Fs = capacité installée / besoin Q (brut) :
          - Fs ≥ 1,20 → CONFORME ;
          - 1,00 ≤ Fs < 1,20 → ADMISSIBLE — NON RECOMMANDÉ (+ suggestion
            d'ajout d'une unité du DN proposé pour atteindre ≥ 1,20) ;
          - Fs < 1,00 → NON CONFORME.
        """
        import math as _math
        pn = pn if pn is not None else (self.pression_nominale or 10.0)
        lignes = []
        if not (self.propositions or []):
            return lignes
        for i, rt in enumerate(self.troncons):
            prop = self.propositions[i] if i < len(self.propositions) else None
            if not prop:
                continue
            v_org = prop.get("ventouse") or {}
            c_org = prop.get("clapet") or {}
            p_org = prop.get("purgeur") or {}
            cap_v = self._cap_proposition("trifon", v_org, pn)
            cap_c = self._cap_proposition("ceai", c_org, pn)
            besoin_ve = rt.res.q_ve_m3h

            def _lib(org, label):
                if not org.get("dn") or not org.get("nombre"):
                    return ""
                s = f"{org['nombre']} × {label} DN{org['dn']}"
                four = (org.get("fournisseur") or "").strip()
                if four and four.upper() not in ("TRIFON", "CEAI", "PSA"):
                    s += f" [{four}]"
                return s

            v_lib = _lib(v_org, "ventouse TRIFON")
            c_lib = _lib(c_org, "clapet")
            p_lib = _lib(p_org, "purgeur")

            def _ligne(tr, ph, cap, besoin, add_cat, add_org, imp=None):
                fs = (cap / besoin) if besoin > 0 else 0.0
                if fs >= 1.20:
                    avis = "CONFORME"
                elif fs >= 1.00:
                    avis = "ADMISSIBLE — NON RECOMMANDÉ"
                else:
                    avis = "NON CONFORME"
                sug = ""
                if 1.00 <= fs < 1.20 and add_cat and add_org \
                        and add_org.get("dn"):
                    unit = self._cap_proposition(
                        add_cat, {"dn": add_org["dn"], "nombre": 1,
                                  "fournisseur": add_org.get("fournisseur", "")},
                        pn)
                    if unit > 0 and besoin > 0:
                        n = max(1, _math.ceil((1.20 * besoin - cap) / unit))
                        fs_n = (cap + n * unit) / besoin
                        nom = "ventouse" if add_cat == "trifon" else "clapet"
                        sug = (f"Ajouter {n} × {nom} DN{add_org['dn']} "
                               f"(+{unit:.0f} m³/h) → Fs = {fs_n:.2f} ≥ 1,20.")
                return {
                    "tr": tr, "ph": ph,
                    "implantation": (imp if imp is not None else
                                     " ; ".join(x for x in (v_lib, c_lib, p_lib)
                                                if x)),
                    "cap_m3h": cap, "besoin_m3h": besoin, "fs": fs,
                    "avis": avis, "suggestion": sug,
                }

            besoins_pi = []
            for cle, lbl in (("pi1", "PI1 (point intermédiaire)"),
                             ("pi2", "PI2 (point intermédiaire)")):
                q = getattr(rt.res, f"q_{cle}_m3h")
                if not ((q or 0) > 0):
                    continue
                if cle == "pi1" and not rt.troncon.has_pi1():
                    continue
                if cle == "pi2" and not rt.troncon.has_pi2():
                    continue
                besoins_pi.append((cle, lbl, q))

            if besoins_pi:
                pi_orgs = {cle: (prop.get(f"clapet_{cle}") or {})
                           for cle, _, _ in besoins_pi}
                any_dedi = any(o.get("dn") and o.get("nombre")
                               for o in pi_orgs.values())
                if any_dedi:
                    # Organes DÉDIÉS par point : Ve = ventouses + clapet (Ve) ;
                    # chaque PI vérifié contre son propre clapet (pas de prorata).
                    bes_g = besoin_ve + sum(q for _, _, q in besoins_pi)
                    cap_g = cap_v + cap_c + sum(
                        self._cap_proposition("ceai", pi_orgs[cle], pn)
                        for cle in pi_orgs)
                    lignes.append(_ligne(rt.label, "Ve (point haut)",
                                         cap_v + cap_c, besoin_ve,
                                         "trifon", v_org,
                                         imp=" ; ".join(
                                             x for x in (p_lib, v_lib, c_lib)
                                             if x) or "—"))
                    for cle, lbl, q in besoins_pi:
                        lignes.append(_ligne(rt.label, lbl,
                                             self._cap_proposition(
                                                 "ceai", pi_orgs[cle], pn),
                                             q, "ceai", pi_orgs[cle],
                                             imp=_lib(pi_orgs[cle], "clapet")
                                             or "—"))
                    lignes.append(_ligne(rt.label, "Groupe (Ve + PI)",
                                         cap_g, bes_g, "ceai",
                                         next((pi_orgs[c] for c in pi_orgs),
                                              c_org),
                                         imp=" ; ".join(x for x in (v_lib, c_lib)
                                                        if x) or "—"))
                else:
                    # Règle historique : ventouses → Ve ; clapets → PI (prorata)
                    lignes.append(_ligne(rt.label, "Ve (point haut)", cap_v,
                                         besoin_ve, "trifon", v_org,
                                         imp=" ; ".join(x for x in (p_lib, v_lib)
                                                        if x) or "—"))
                    q_tot = sum(q for _, _, q in besoins_pi)
                    for cle, lbl, q in besoins_pi:
                        alloc = cap_c * (q / q_tot) if q_tot > 0 else 0.0
                        lignes.append(_ligne(rt.label, lbl, alloc, q,
                                             "ceai", c_org,
                                             imp=c_lib or "—"))
                    bes_g = besoin_ve + q_tot
                    lignes.append(_ligne(rt.label, "Groupe (Ve + PI)",
                                         cap_v + cap_c, bes_g, "ceai", c_org,
                                         imp=" ; ".join(x for x in (v_lib, c_lib)
                                                        if x) or "—"))
            else:
                # CAS NORMAL : toute l'admission au point haut Ve
                lignes.append(_ligne(rt.label, "Ve (point haut)",
                                     cap_v + cap_c, besoin_ve,
                                     ("trifon" if v_org else "ceai"),
                                     v_org or c_org))
        return lignes


def calculer_profil(troncons: list[ProfilTroncon],
                    dn_mm: float = 1400.0,
                    temperature: float = 15.0,
                    pression_nominale: float = 10.0) -> ResultatProfilComplet:
    """Calcule la chaîne complète de tronçons.

    Chaque tronçon est résolu par `NoteMKAA` (formule explicite MK_A.A
    2026), puis les points sont recousus en abscisses cumulées et la jonction
    Vi2(TRi) ≡ Vi1(TR(i+1)) est vérifiée.
    """
    pc = ResultatProfilComplet()
    pc.dn_mm = dn_mm
    pc.temperature = temperature
    pc.pression_nominale = pression_nominale
    if not troncons:
        pc.avertissements.append("Aucun tronçon défini dans la chaîne.")
        return pc

    dc = DonneesConduite.from_dn(dn_mm)
    nu = viscosity.corriger_nu(temperature)

    x_debut = 0.0
    for i, tr in enumerate(troncons):
        note = NoteMKAA(dc, nu)
        alt = tr.alt_dict()
        res = note.calculer(tr.schema, alt, tr.has_pi1(), tr.has_pi2())

        besoin = res.q_ve_m3h
        ventouse = dim.choisir_ventouse(besoin)
        clapet = dim.choisir_clapet(besoin)
        q_rempl = dim.q_remplissage(2.0, dc)
        purgeur = dim.choisir_purgeur_psa(q_rempl)
        purgeur_snh = dim.choix_purgeur_snh(q_rempl, pression_nominale or 10.0)
        remplissage = {"q": q_rempl, "purgeurs": purgeur,
                       "purgeurs_snh": purgeur_snh}

        rt = ResultatTroncon(troncon=tr, res=res, organes={
            "ventouse": ventouse, "clapet": clapet},
            remplissage=remplissage, nu=nu, dc=dc, x_debut=x_debut)
        pc.troncons.append(rt)

        # --- Recousu des points du tronçon (abscisses cumulées) ---
        dist = {k: getattr(tr, k) for k in ("a", "b", "c", "d", "l1", "l2")}
        xloc = _cumul_abscisse_local(tr.schema, dist)
        cotes = {"vi1": tr.z_vi1, "pi1": tr.z_pi1, "ve": tr.z_ve,
                 "pi2": tr.z_pi2, "vi2": tr.z_vi2}
        marques = {"vi1": "v", "vi2": "v", "pi1": "•", "pi2": "•", "ve": "V"}
        for cle in ("vi1", "pi1", "ve", "pi2", "vi2"):
            if xloc.get(cle) is None or cotes.get(cle) is None:
                continue
            pc.points.append(PointProfil(
                cle=cle, x=x_debut + xloc[cle], z=cotes[cle],
                tr=tr.label, marque=marques[cle]))
        x_debut += _longueur_troncon(tr.schema, dist)

        # --- Défauts de saisie perçus ---
        if res.q_ve_m3h <= 0 and res.q_pi1_m3h <= 0 and res.q_pi2_m3h <= 0:
            pc.avertissements.append(
                f"{tr.label} : aucun écoulement calculé (Q_Ve = 0) — "
                "vérifier le dénivelé du profil (ΔH ≤ 3 mCE au point haut).")

    # --- Jonctions entre tronçons ---
    for i in range(len(pc.troncons) - 1):
        a = pc.troncons[i]
        b = pc.troncons[i + 1]
        z_ga = a.troncon.z_vi2
        z_dr = b.troncon.z_vi1
        ecart = abs(z_ga - z_dr)
        jonction = Jonction(
            i=i, z_vi2_tr_i=z_ga, z_vi1_tr_i1=z_dr, ecart_m=ecart,
            ok=ecart < 0.01, deb_max_m3h=max(a.res.q_av_m3h, b.res.q_am_m3h))
        # Le tronçon gauche/droit sert au libellé de la jonction
        jonction.tron_gauche = a.label
        jonction.tron_droit = b.label
        pc.jonctions.append(jonction)
        if ecart >= 0.01:
            pc.avertissements.append(
                f"Jonction {a.label}/{b.label} : discontinuité de cote "
                f"Vi2={z_ga:.1f} vs Vi1={z_dr:.1f} m NGM "
                f"(écart {ecart:.2f} m) — le profil doit être continu.")

    # Doublons d'abscisse possibles si des tronçons sont « plats » → tri
    pc.points.sort(key=lambda p: (p.x, p.cle))

    # Cohérence des vents : chaque point haut Ve doit être au-dessus de ses
    # voisins (sinon la ventouse n'aurait aucun flux → alerte déjà posée).
    return pc


# ---------------------------------------------------------------------------
# Rendu texte de la synthèse (utilisable dans l'onglet « Synthèse » et .txt)
# ---------------------------------------------------------------------------
def synthese_txt(pc: ResultatProfilComplet) -> str:
    lignes = []
    lignes.append("=" * 72)
    lignes.append("SYNTHÈSE DU PROFIL COMPLET (CHAÎNE DE TRONÇONS)")
    lignes.append("=" * 72)
    if not pc.troncons:
        lignes.append("  (chaîne vide)")
        return "\n".join(lignes)

    lignes.append("  Tronçons : " + " → ".join(rt.label for rt in pc.troncons))
    lignes.append(f"  Conduite DN {pc.dn_mm:g} mm · T = {pc.temperature:.1f} °C · "
                  f"PN {pc.pression_nominale:g} bar")
    lignes.append(f"  Longueur développée totale : {pc.longueur_totale:,.0f} m")
    lignes.append("")

    lignes.append("  Résultats par tronçon")
    lignes.append("  ——————————————————————")
    lignes.append(f"  {'TR':<6}{'Schéma':<8}{'Q_Ve':>10}{'Q_am':>10}{'Q_av':>10}"
                  f"{'Q_PI1':>10}{'Q_PI2':>10}")
    for rt in pc.troncons:
        r = rt.res
        lignes.append(f"  {rt.label:<6}{r.cas:<8}{r.q_ve_m3h:>10,.0f}"
                      f"{r.q_am_m3h:>10,.0f}{r.q_av_m3h:>10,.0f}"
                      f"{r.q_pi1_m3h:>10,.0f}{r.q_pi2_m3h:>10,.0f}")
    lignes.append("")

    vid = pc.synthese_vidanges()
    if vid:
        lignes.append("  Vidanges du profil (points bas / jonctions communes)")
        lignes.append("  ————————————————————————————————————————————————")
        for v in vid:
            co = "" if v["continue"] else "  ⚠ NON CONTINUE (écart de cote)"
            lignes.append(f"  {v['point']:<26} Z = {v['z']:.1f} m NGM  "
                          f"| Q évacuation = {v['q_evacuation']:,.0f} m³/h"
                          f"{co}")

    lignes.append("")
    lignes.append("  Synthèse des organes le long du profil")
    lignes.append("  —————————————————————————————————————")
    lignes.append(f"  {'Rép.':<6}{'TR':<6}{'Point':<22}{'Organe':<24}{'DN':<6}"
                  f"{'Qté':<5}{'Besoin':>10}")
    for o in pc.synthese_organes():
        lignes.append(f"  {o['rep']:<6}{o['tr']:<6}{o['point']:<22}{o['type']:<24}"
                      f"DN{str(o['dn']):<5}{o['nombre']:<5}{o['besoin_m3h']:>10,.0f}")

    if pc.jonctions:
        lignes.append("")
        lignes.append("  Jonctions (continuité du profil)")
        lignes.append("  ————————————————————————————————")
        for j in pc.jonctions:
            statut = "OK" if j.ok else f"ÉCART {j.ecart_m:.2f} m"
            lignes.append(f"  {j.label:<22} — {statut}")

    if pc.avertissements:
        lignes.append("")
        lignes.append("  AVERTISSEMENTS")
        lignes.append("  ———————————————")
        for a in pc.avertissements:
            lignes.append(f"  ⚠ {a}")
    return "\n".join(lignes)


def verification_txt(pc: ResultatProfilComplet) -> str:
    """Texte des conclusions — proposition client vs organes calculés.

    Chaque tronçon : organes proposés vs besoins majorés (+15 %, plafond 90 %),
    verdict individuel et groupe d'air, puis conclusion globale + préconisations.
    """
    lignes = []
    lignes.append("=" * 72)
    lignes.append("VÉRIFICATION DE LA PROPOSITION CLIENT — PROFIL COMPLET")
    lignes.append("Besoin majoré = Q_Ve × 1,15 (marge +15 %, plafond 90 %) — "
                  "défauts v3")
    lignes.append("=" * 72)
    if not pc.verifications and not any(pc.propositions or []):
        lignes.append("  Aucune proposition client saisie (Vérification non "
                      "effectuée).")
        return "\n".join(lignes)

    for trlabel, verdicts in _verdicts_par_troncon(pc).items():
        lignes.append("")
        lignes.append(f"  TRONÇON {trlabel}")
        lignes.append("  ———————————————————————")
        for v in verdicts:
            statut = "✓ CONFORME" if v["conforme"] else "✗ NON CONFORME"
            lignes.append(f"  [{v['categorie']}] {statut} | {v['message']}")
            if not v["conforme"] and v["deficit_m3h"] > 0:
                lignes.append(f"      → compter un déficit de {v['deficit_m3h']:,.0f} "
                              f"m³/h (proposé : {v['propose']}).")
            if v["categorie"] == "Vanne de sectionnement" and not v["conforme"]:
                msg = []
                if not v["section_vanne_m2"]:
                    msg.append("DN de vanne nul")
                if not v["etranglement_ok"]:
                    msg.append(f"étranglement : S vanne {v['section_vanne_m2']:.3f} m² "
                               f"≤ Σ sections appareils {v['section_amont_m2']:.3f} m²")
                if not v["sonique_ok"]:
                    msg.append(f"vitesse sonique {v['v_vanne_ms']:.1f} m/s > "
                               f"{v['v_limite_ms']:g} m/s (blocage sonique)")
                lignes.append("      → vanne à revoir : " + " ; ".join(msg) +
                              ". Cap. passage à 40 m/s = "
                              f"{v['capacite_passage_40_m3h']:,.0f} m³/h.")

    lignes.append(recap_ph_txt(pc))

    concl = pc.conclusion_globale()
    lignes.append("")
    lignes.append("=" * 72)
    if concl["conforme"]:
        lignes.append("CONCLUSION GLOBALE : PROPOSITION CONFORME")
        lignes.append(f"  {concl['nb_sains']}/{concl['nb_verdicts']} vérifications OK — "
                      "les organes proposés couvrent les besoins le long de la chaîne.")
    else:
        lignes.append("CONCLUSION GLOBALE : PROPOSITION NON CONFORME")
        lignes.append(f"  {concl['nb_sains']}/{concl['nb_verdicts']} vérifications OK ; "
                      f"{concl['nb_defauts']} à revoir.")
        lignes.append("  Préconisations par tronçon :")
        for tr_l, vs in concl["defauts_par_troncon"].items():
            for v in vs:
                besoin = v["besoin_m3h"]
                manque = v["deficit_m3h"]
                if "Ventouse" in v["categorie"]:
                    conseil = f"prévoir une ventouse (ou combinaison) de capacité ≥ {besoin:,.0f} m³/h"
                elif "Clapet" in v["categorie"]:
                    conseil = f"prévoir un clapet d'admission de capacité ≥ {besoin:,.0f} m³/h"
                elif "Purgeur" in v["categorie"]:
                    conseil = f"prévoir un purgeur couvrant ≥ {besoin:,.0f} m³/h (ou s'appuyer sur le grand orifice des ventouses)"
                elif v["categorie"] == "Vanne de sectionnement":
                    conseil = ("prévoir une vanne de sectionnement (ou élargir la "
                               "piqûre) avec S vanne > Σ sections appareils et "
                               "vitesse air < 40 m/s")
                else:
                    conseil = f"revoir l'ensemble d'admission pour couvrir {besoin:,.0f} m³/h"
                lignes.append(f"    · {tr_l} — {v['categorie']} : {manque:,.0f} "
                              f"m³/h manquants → {conseil}. "
                              f"[proposé : {v['propose']}]")
    lignes.append("=" * 72)
    return "\n".join(lignes)


def recap_ph_txt(pc: ResultatProfilComplet) -> str:
    """Texte du tableau récapitulatif « implantation par point haut » (Fs).

    Fs = capacité installée / besoin Q brut ; avis en 3 niveaux ; suggestion
    d'ajout d'une unité lorsque 1,00 ≤ Fs < 1,20. Les purgeurs (dégazage)
    figurent dans l'implantation mais sont exclus du Fs d'admission.
    """
    lignes = []
    lignes.append("")
    lignes.append("RÉCAPITULATIF IMPLANTATION PAR POINT HAUT "
                  "(Fs = capacité / besoin Q)")
    lignes.append("-" * 72)
    lignes.append("  Fs ≥ 1,20 → CONFORME · 1,00 ≤ Fs < 1,20 → ADMISSIBLE — "
                  "NON RECOMMANDÉ (+ suggestion) · Fs < 1,00 → NON CONFORME. "
                  "Purgeurs (dégazage) exclus du Fs d'admission.")
    lignes.append("-" * 72)
    for r in pc.recap_ph():
        if r["avis"] == "CONFORME":
            statut = "✓ " + r["avis"]
        elif "ADMISSIBLE" in r["avis"]:
            statut = "⚠ " + r["avis"]
        else:
            statut = "✗ " + r["avis"]
        lignes.append(f"  {r['tr']} · {r['ph']}")
        lignes.append(f"      Implantation : {r['implantation']}")
        lignes.append(f"      Capacité = {r['cap_m3h']:,.0f} m³/h · Besoin Q = "
                      f"{r['besoin_m3h']:,.0f} m³/h → Fs = {r['fs']:.2f} "
                      f"{statut}")
        if r["suggestion"]:
            lignes.append(f"        → {r['suggestion']}")
    lignes.append("-" * 72)
    return "\n".join(lignes)


def _verdicts_par_troncon(pc: ResultatProfilComplet) -> dict:
    out = {}
    for v in pc.verifications:
        out.setdefault(v["troncon"], []).append(v)
    return out