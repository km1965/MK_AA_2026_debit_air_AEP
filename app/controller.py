"""Contrôleur applicatif — état global + coordonnateur entre UI et moteur."""

import json
import math
from dataclasses import dataclass, field
from typing import Optional

from .core.constants import DonneesConduite, SEUIL_DEPRESSION
from .core.schemas import NoteMKAA, ResultatSchema
from .core import dimensionnement as dim
from .utils import viscosity
from .utils import export as export_mod

# Ordre des 8 schémas pour l'affichage/navigation
SCHEMAS = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"]

# Description courte de chaque schéma (pour l'UI)
SCHEMA_LABELS = {
    "1A": "A · Amont seul (sans PI)",
    "1B": "A · Amont seul (avec PI1)",
    "2A": "B · Aval seul (sans PI)",
    "2B": "B · Aval seul (avec PI2)",
    "3A": "C · Amont + Aval (sans PI)",
    "3B": "C · Amont + Aval (PI1+PI2)",
    "4A": "D · Asymétrique (PI1 amont)",
    "4B": "D · Asymétrique (PI2 aval)",
}

# Champs d'altimétrie attendus selon le cas
DISTANCES_PAR_CAS = {
    "1A": ["l1"],
    "1B": ["a", "b"],
    "2A": ["l2"],
    "2B": ["c", "d"],
    "3A": ["l1", "l2"],
    "3B": ["a", "b", "c", "d"],
    "4A": ["a", "b", "l2"],
    "4B": ["l1", "c", "d"],
}


# Vitesse de sortie d'air de référence des purgeurs soniques (§9.2)
V_SONIQUE_MS = 200.0

# Classe PN du projet courant (rappel : la capacité catalogue des purgeurs SNH
# est relevée selon la classe PN — cf. « Débit air purgeur sonique NSH.xlsx »).
# Rafraîchi à chaque calcul depuis EtatApplication.pression_nominale.
_PN_COURANT = 10.0


def _cap_purgeur_pn(four: str, dn, pn: float) -> float:
    """Capacité (m³/h) d'un purgeur externe à la classe PN donnée.

    Lit la colonne « pressions » du catalogue (valve_database.json) qui relève
    le débit par classe PN (ex. NSH DN1500 : PN10→180, PN16→144 m³/h). Retombe
    sur le q_capacity par défaut si la classe PN demandée n'est pas listée."""
    try:
        from .data import valve_db
        f = valve_db.fournisseur(four)
        for p in (f.get("purgeurs") or []):
            if p.get("dn") == dn:
                pressions = p.get("pressions") or {}
                key = str(int(round(float(pn or 10.0))))
                if key in pressions:
                    return float(pressions[key])
                return float(p.get("q_capacity") or 0.0)
    except Exception:
        pass
    return 0.0


def _capacite_sonique_purgeur(org: dict, pn: float = None) -> float:
    """Capacité sonique (m³/h) d'un purgeur — standard PSA ou externe (SNH NSH).

    PSA : q_remplissage du catalogue (débit sonique au remplissage).
    Externe (SNH) : capacité sonique de remplissage physique
                    Q_fill = q_cap · (P_fill/P_svc) (cf. dimensionnement).
    """
    nb = max(org.get("nombre", 0), 0)
    if nb <= 0:
        return 0.0
    pn = pn if pn is not None else _PN_COURANT
    dn = org.get("dn")
    four = org.get("fournisseur", "") or ""
    standard = (not four) or four.upper() in ("TRIFON", "CEAI", "PSA")
    if standard:
        from .data.catalogues import PSA
        val = PSA.get(dn, {}).get("q_remplissage", 0.0)
        if val > 0:
            return val * nb
        # Repli NSH pour les grands DNs non couverts par le PSA standard
        from .core.dimensionnement import _cap_sonique_snh
        q_cap = _cap_purgeur_pn("SNH", dn, pn)
        return _cap_sonique_snh(q_cap, pn) * nb
    from .core.dimensionnement import _cap_sonique_snh
    q_cap = _cap_purgeur_pn(four, dn, pn)
    return _cap_sonique_snh(q_cap, pn) * nb


def capacite_organe(org: dict, depr: int = -3, pn: float = None) -> float:
    """Débit d'air installé (m³/h) d'un organe client, fournisseur compris.

    organes_client : {"type": trifon|ceai|psa|vanne, "dn", "nombre",
                      "fournisseur": str (ex. SNH)}
    Fournisseurs standards (TRIFON/CEAI/PSA ou vide) → catalogues internes.
    Fournisseur externe (ex. SNH) → table du valve_database.json.
    pn : classe PN du projet (pour les purgeurs SNH dont la capacité catalogue
         dépend de la classe PN). Par défaut : PN courant mémorisé.
    """
    cat = org.get("type", "")
    dn = org.get("dn")
    nb = max(org.get("nombre", 0), 0)
    if cat == "vanne":
        return 0.0
    pn = pn if pn is not None else _PN_COURANT
    four = org.get("fournisseur", "") or ""
    standard = (not four) or four.upper() in ("TRIFON", "CEAI", "PSA")
    if standard:
        from .data.catalogues import TRIFON, CEAI, PSA
        if cat == "trifon":
            return TRIFON.get(dn, {}).get("q", {}).get(depr, 0.0) * nb
        if cat == "ceai":
            return CEAI.get(dn, {}).get("q", {}).get(depr, 0.0) * nb
        if cat == "psa":
            cap = PSA.get(dn, {}).get("q_remplissage", 0.0) * nb
            if cap > 0 or not dn:
                return cap
            # Repli : le catalogue PSA standard ne couvre pas ce DN (grands
            # purgeurs NSH) → on cherche dans la base purgeurs SNH/NSH, source
            # réelle des purgeurs soniques (DN1200/DN1500…), à la classe PN.
            # Capacité INSTALLÉE (catalogue, PN-aware) — ex. DN1500@PN16=144.
            return _cap_purgeur_pn("SNH", dn, pn) * nb
        return 0.0
    # fournisseur externe (ex. SNH)
    role = {"trifon": "ventouse", "ceai": "clapet", "psa": "purgeur"}.get(cat, "")
    if not role:
        return 0.0
    if role == "purgeur":
        # Capacité INSTALLÉE (catalogue, PN-aware) — ex. DN1500@PN16=144.
        return _cap_purgeur_pn(four, dn, pn) * nb
    from .data.valve_db import table_capacite
    tab = table_capacite(four, role)
    return tab.get(dn, 0.0) * nb


@dataclass
class EtatApplication:
    """État persistant de la saisie projet (données variables uniquement)."""

    # §4.1 Identification
    moe: str = ""
    projet: str = ""
    reference: str = ""
    branches: str = ""
    # §4.2 Conduite
    dn_mm: float = 1400.0
    # §4.3 Température
    temperature: float = 15.0
    # §4.4 Profil en long
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
    # §5
    schema: str = "3B"

    # Fournisseurs des organes d'air pour le dimensionnement (§8), par organe.
    # "" ou "— Standard —" = catalogue interne du rôle (ventouse : TRIFON, clapet : CEAI).
    # Sinon : nom du fournisseur dans valve_database.json (ex. SNH, PAM…).
    fournisseur_ventouse: str = ""
    fournisseur_clapet: str = ""

    # Organes proposés par le client (onglet Vérification)
    # Chaque entrée : {"dn": int|None, "nombre": int, "type": str}
    #   type ∈ "trifon" (ventouse), "ceai" (clapet admission),
    #          "psa" (purgeur remplissage), "vanne" (vanne sectionnement)
    organes_client: list = field(default_factory=list)

    # --- Onglet « Cumul des débits » (§ note « Débits cumulés ») ---
    # H_z : dénivelé géométrique (mCE) entre le point haut et la rupture
    #       (casse franche d'une conduite DN) — pour Q_eau = A·√(2·g·H_z).
    hz_casse_franche: float = 10.0
    # DN de la vanne de sectionnement / collecteur sous les appareils
    # (ex. DN 1600 sous les ventouses). 0 = non renseignée.
    dn_vanne_sectionnement: float = 1600.0
    # Pression nominale de la conduite (bar) — pour vérification flambement
    # (PN 10 par défaut, à adapter selon le projet : PN 10, PN 16, PN 25…)
    pression_nominale: float = 10.0
    # Méthode de dimensionnement/acceptation du groupe (onglet Cumul) :
    #   "mk_aa" → le groupe est jugé face aux débits MK_A.A (Q_Ve) ;
    #   "breche"   → le groupe est jugé face à la vidange brèche (Torricelli, Q_eau).
    # Persisté dans le projet ; pilote le « Groupe retenu » des rapports et le croquis.
    methode_dimensionnement: str = "mk_aa"

    # Résultats calculés
    resultat: Optional[ResultatSchema] = None
    erreur: str = ""                       # message d'erreur éventuel
    derniere_trace: Optional[dict] = None  # trace pour le rapport

    # ------------------------------------------------------------------
    def dc(self) -> DonneesConduite:
        return DonneesConduite.from_dn(self.dn_mm)

    def _alt_dict(self) -> dict:
        return {
            "z_vi1": self.z_vi1, "z_pi1": self.z_pi1, "z_ve": self.z_ve,
            "z_pi2": self.z_pi2, "z_vi2": self.z_vi2,
            "a": self.a, "b": self.b, "c": self.c, "d": self.d,
            "l1": self.l1, "l2": self.l2,
        }

    def has_pi1(self) -> bool:
        return self.schema in ("1B", "3B", "4A")

    def has_pi2(self) -> bool:
        return self.schema in ("2B", "3B", "4B")

    def hz_casse_franche_auto(self) -> float:
        """H_z auto — dénivelé « point haut → rupture » issu du profil.

        La rupture (casse franche) se traite au point bas de la conduite
        vidangée : H_z = Z_Ve − point_bas. Côtés actifs selon le schéma
        (mêmes règles que schemas.py) :
            amont : 1A, 1B, 3A, 3B, 4A, 4B
            aval  : 2A, 2B, 3A, 3B, 4A, 4B
        Les PI (crêtes intermédiaires) ne sont pas des points bas.
        """
        amont = self.schema in ("1A", "1B", "3A", "3B", "4A", "4B")
        aval = self.schema in ("2A", "2B", "3A", "3B", "4A", "4B")
        bornes = []
        if amont:
            bornes.append(self.z_vi1)
        if aval:
            bornes.append(self.z_vi2)
        point_bas = min(bornes) if bornes else self.z_ve
        return max(self.z_ve - point_bas, 0.0)

    def calculer(self) -> ResultatSchema:
        """Exécute le calcul complet et remplit aussi la trace (dimensionnement)."""
        global _PN_COURANT
        _PN_COURANT = self.pression_nominale or 10.0
        dc = self.dc()
        nu = viscosity.corriger_nu(self.temperature)
        note = NoteMKAA(dc, nu)
        alt = self._alt_dict()
        res = note.calculer(self.schema, alt, self.has_pi1(), self.has_pi2())
        self.resultat = res

        # Dimensionnement des organes (§8) — fournisseur sélectionnable PAR organe
        from .core.dimensionnement import MARGE_ACCESSOIRES_PCT
        marge = MARGE_ACCESSOIRES_PCT
        besoin_ve = res.q_ve_m3h
        from .data import valve_db as _db

        fv = (self.fournisseur_ventouse or "").strip()
        if fv and fv != "— Standard —":
            tab_v = _db.table_moteur(fv, "ventouse")
            ventouse = dim.choisir_ventouse(besoin_ve, marge,
                                            table=tab_v or None,
                                            nom=(fv if tab_v else ""))
        else:
            fv = ""
            ventouse = dim.choisir_ventouse(besoin_ve, marge)
        self.fournisseur_ventouse = fv

        fc = (self.fournisseur_clapet or "").strip()
        if fc and fc != "— Standard —":
            tab_c = _db.table_moteur(fc, "clapet")
            clapet = dim.choisir_clapet(besoin_ve, marge,
                                        table=tab_c or None,
                                        nom=(fc if tab_c else ""))
        else:
            fc = ""
            clapet = dim.choisir_clapet(besoin_ve, marge)
        self.fournisseur_clapet = fc

        organes = {
            "ventouse": ventouse,
            "clapet": clapet,
        }

        # Remplissage §9
        q_rempl = dim.q_remplissage(2.0, dc)
        purgeur = dim.choisir_purgeur_psa(q_rempl)
        purgeur_snh = dim.choix_purgeur_snh(q_rempl, self.pression_nominale or 10.0)
        remplissage = {"q": q_rempl, "purgeurs": purgeur, "purgeurs_snh": purgeur_snh}

        self.derniere_trace = {
            "dc": dc, "nu": nu, "temperature": self.temperature,
            "fournisseur_ventouse": fv, "fournisseur_clapet": fc,
            "organes": organes, "remplissage": remplissage,
        }
        self.erreur = ""
        return res

    def generer_rapport(self) -> str:
        """Génère le rapport de synthèse en texte.

        Recalcule systématiquement depuis l'état courant : le rapport doit
        toujours refléter les entrées saisies, y compris après changement de
        schéma (les PIs a/b/c/d désactivés ne doivent jamais être pris en
        compte par un résultat périmé).
        """
        self.calculer()
        trace = self.derniere_trace
        return export_mod.generer_rapport(
            self, self.resultat, trace, trace["remplissage"],
            trace["nu"], self.temperature)

    # ------------------------------------------------------------------
    # Sérialisation — Enregistrer / Enregistrer sous / Ouvrir
    # ------------------------------------------------------------------
    CHAMPS_EDITABLES = (
        "moe", "projet", "reference", "branches", "dn_mm", "temperature",
        "z_vi1", "z_pi1", "z_ve", "z_pi2", "z_vi2",
        "a", "b", "c", "d", "l1", "l2", "schema", "organes_client",
        "hz_casse_franche", "dn_vanne_sectionnement", "pression_nominale",
        "methode_dimensionnement",
        "fournisseur_ventouse", "fournisseur_clapet",
    )

    def to_dict(self) -> dict:
        return {c: getattr(self, c) for c in self.CHAMPS_EDITABLES}

    @classmethod
    def from_dict(cls, d: dict) -> "EtatApplication":
        e = cls()
        for c in cls.CHAMPS_EDITABLES:
            if c in d:
                setattr(e, c, d[c])
        # Migration des anciens projets (fournisseur_air unique → par organe)
        if "fournisseur_air" in d and "fournisseur_ventouse" not in d \
                and "fournisseur_clapet" not in d:
            e.fournisseur_ventouse = d.get("fournisseur_air", "")
            e.fournisseur_clapet = d.get("fournisseur_air", "")
        # Migration : supprimer les vanne de sectionnement des organes_client
        # (la vanne est dans dn_vanne_sectionnement, pas dans organes_client)
        if e.organes_client:
            e.organes_client = [o for o in e.organes_client
                                if o.get("type") != "vanne"]
        return e

    def sauvegarder(self, chemin: str) -> None:
        """Sauvegarde le projet en JSON."""
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def charger(cls, chemin: str) -> "EtatApplication":
        """Charge un projet depuis un fichier JSON."""
        e = cls()
        e.charger_dans(chemin)
        return e

    def charger_dans(self, chemin: str) -> None:
        """Charge le projet dans CETTE instance (mutation en place).

        Les frames de l'UI gardent la référence à l'objet EtatApplication :
        on modifie donc l'instance existante au lieu d'en créer une nouvelle,
        sinon les champs des onglets ne seraient pas rafraîchis.
        """
        with open(chemin, "r", encoding="utf-8") as f:
            d = json.load(f)
        for c in self.CHAMPS_EDITABLES:
            if c in d:
                setattr(self, c, d[c])
        # Migration des anciens projets (fournisseur_air unique → par organe)
        if "fournisseur_air" in d and "fournisseur_ventouse" not in d \
                and "fournisseur_clapet" not in d:
            self.fournisseur_ventouse = d.get("fournisseur_air", "")
            self.fournisseur_clapet = d.get("fournisseur_air", "")
        # Migration : supprimer les vanne de sectionnement des organes_client
        if self.organes_client:
            self.organes_client = [o for o in self.organes_client
                                   if o.get("type") != "vanne"]
        self.resultat = None
        self.erreur = ""
        self.derniere_trace = None

    def appliquer_excel(self, chemin: str) -> list:
        """Importe les données projet depuis un classeur Excel (modèle V05).

        Mutation en place (les frames gardent la référence à l'instance).
        Retourne la liste des avertissements du contrôle de validité.

        Seuls les champs renseignés dans le fichier sont appliqués ; les
        autres conservent leur valeur actuelle (défaut).
        """
        from .utils import excel_import
        d, warnings = excel_import.lire_donnees_projet(chemin)
        for c in self.CHAMPS_EDITABLES:
            if c in d:
                setattr(self, c, d[c])
        self.resultat = None
        self.erreur = ""
        self.derniere_trace = None
        return warnings

    # ------------------------------------------------------------------
    # Vérification des organes proposés par le client
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Vérification des organes / groupe / catégorie
    # ------------------------------------------------------------------
    def _libelle_categorie(self, typ: str) -> str:
        """Libellé de catégorie pour un type d'organe.

        Reflète le FOURNISSEUR réel des organes client de cette catégorie
        (ex. « Clapet admission air (SNH) ») au lieu d'un nom de constructeur
        générique (CEAI), qui laissait croire que le client utilisait du CEAI
        alors qu'il n'utilise que TRIFON et SNH. Retombe sur le nom par défaut
        si le fournisseur est absent ou mélangé."""
        base = {
            "trifon": "Ventouse admission",
            "ceai": "Clapet admission air",
            "psa": "Purgeur remplissage",
            "vanne": "Vanne de sectionnement",
        }.get(typ, typ)
        if typ == "vanne":
            return base
        fournisseurs = {
            str(o.get("fournisseur") or "").strip().upper()
            for o in self.organes_client if o.get("type") == typ
        }
        fournisseurs.discard("")
        fournisseurs.discard("—")
        if len(fournisseurs) == 1:
            return f"{base} ({next(iter(fournisseurs))})"
        return base

    def _organes_ve(self) -> list:
        """Organes client affectés au point haut Ve (hors organes dédiés PI).

        Un organe est « dédié PI » lorsque sa position est « pi1 » ou « pi2 ».
        """
        return [o for o in self.organes_client
                if o.get("type") in ("trifon", "ceai", "psa")
                and (o.get("position") or "").lower() not in ("pi1", "pi2")]

    def _organes_pi(self, cle: str) -> list:
        """Organes client dédiés à un point intermédiaire (position « pi1 »/« pi2 »)."""
        return [o for o in self.organes_client
                if o.get("type") in ("trifon", "ceai", "psa")
                and (o.get("position") or "").lower() == cle]

    def verifier_organes(self) -> list:
        """Compare les organes client (§ organes_client) aux besoins calculés.

        Retourne une liste de dictionnaires :
            {categorie, besoin, propose, capacite_proposee, conforme, message}
        """
        if self.resultat is None or self.derniere_trace is None:
            self.calculer()
        trace = self.derniere_trace
        dc = trace["dc"]

        # --- Besoins de référence ---
        from .core.dimensionnement import MARGE_ACCESSOIRES_PCT, _marge_factor
        besoin_ve = self.resultat.q_ve_m3h
        besoin_ve_majore = besoin_ve * _marge_factor(MARGE_ACCESSOIRES_PCT)  # +15 %
        besoin_remplissage = trace["remplissage"]["q"]

        # Résumé des propositions par catégorie
        prop = {"trifon": [], "ceai": [], "psa": [], "vanne": []}
        for o in self._organes_ve():
            cat = o.get("type", "")
            if cat in prop:
                prop[cat].append(o)
        # La vanne de sectionnement est gérée séparément (dn_vanne_sectionnement) :
        # on la matérialise dans la section « Vannes de sectionnement ».
        if self.dn_vanne_sectionnement:
            prop["vanne"].append({
                "type": "vanne",
                "dn": self.dn_vanne_sectionnement,
                "nombre": 1,
                "fournisseur": "—",
                "_source": "dn_vanne_sectionnement",
            })

        def _capacite_categorie(cat, org, depr=-3):
            """Calcule q (m³/h) installé cumulé d'une liste d'organes."""
            if cat == "vanne":
                # vanne sectionnement : on ne compare pas à un débit d'air ;
                # on vérifie présence/cohérence. Capacité = None (sans objet).
                return None
            return sum(capacite_organe(o, depr) for o in org)

        resultat = []

        # Ventouse TRIFON : doit couvrir besoin_ve majoré
        cap_ve = _capacite_categorie("trifon", prop["trifon"])
        conform_ve = bool(prop["trifon"]) and (cap_ve is not None and cap_ve >= besoin_ve_majore)
        resultat.append({
            "categorie": self._libelle_categorie("trifon"),
            "besoin": besoin_ve_majore,
            "propose": prop["trifon"],
            "capacite_proposee": cap_ve,
            "conforme": conform_ve,
            "message": (f"Besoin +15 % = {besoin_ve_majore:.0f} m³/h ; "
                        f"capacité proposée = {cap_ve:.0f} m³/h."
                        if cap_ve is not None else "Aucune ventouse renseignée."),
        })

        # Clapet admission CEAI (associé à la ventouse) : même besoin Q_Ve
        cap_ceai = _capacite_categorie("ceai", prop["ceai"])
        conform_ceai = bool(prop["ceai"]) and (cap_ceai is not None and cap_ceai >= besoin_ve_majore)
        resultat.append({
            "categorie": self._libelle_categorie("ceai"),
            "besoin": besoin_ve_majore,
            "propose": prop["ceai"],
            "capacite_proposee": cap_ceai,
            "conforme": conform_ceai,
            "message": (f"Besoin +15 % = {besoin_ve_majore:.0f} m³/h ; "
                        f"capacité proposée = {cap_ceai:.0f} m³/h."
                        if cap_ceai is not None else "Aucun clapet renseigné."),
        })

        # Purgeur PSA (remplissage/dégazage)
        cap_psa = _capacite_categorie("psa", prop["psa"])
        cap_ve_inst = cap_ve or 0.0
        # L'évacuation massive au remplissage est assurée par le grand orifice
        # des ventouses TRIFON (fonction 3) ; le purgeur (sonique) assure le
        # dégazage contrôlé. → conforme si le purgeur couvre le besoin OU si la
        # ventouse couvre l'évacuation massive du remplissage.
        rempli_par_purgeur = (cap_psa or 0.0) >= besoin_remplissage
        rempli_par_ventouse = cap_ve_inst >= besoin_remplissage
        conform_psa = bool(prop["psa"]) and (rempli_par_purgeur or rempli_par_ventouse)
        resultat.append({
            "categorie": self._libelle_categorie("psa"),
            "besoin": besoin_remplissage,
            "propose": prop["psa"],
            "capacite_proposee": cap_psa,
            "conforme": conform_psa,
            "message": (f"Besoin remplissage = {besoin_remplissage:.0f} m³/h ; "
                        f"capacité purgeur = {cap_psa or 0:.0f} m³/h"
                        + (f" (ventouse grand orifice {cap_ve_inst:.0f} m³/h couvre "
                           f"l'évacuation massive)."
                           if (not rempli_par_purgeur and rempli_par_ventouse)
                           else ("" if rempli_par_purgeur
                                 else f" — {cap_ve_inst:.0f} m³/h par ventouse.")
                           )
                        if cap_psa is not None else "Aucun purgeur renseigné."),
        })

        # Vanne de sectionnement : contrôle de présence (côté vidange)
        vanne_dn = getattr(self, "dn_vanne_sectionnement", 0) or 0
        conform_vanne = bool(prop["vanne"]) and bool(vanne_dn)
        resultat.append({
            "categorie": "Vannes de sectionnement",
            "besoin": None,
            "propose": prop["vanne"],
            "capacite_proposee": None,
            "conforme": conform_vanne,
            "message": (f"Vanne de sectionnement DN {vanne_dn:g} : conforme."
                        if conform_vanne else "Aucune vanne de sectionnement renseignée."),
        })

        # --- Vérification CUMULÉE GROUPE D'AIR (admission / casse franche) ---
        # Tous les organes d'admission (ventouse + clapet + purgeur) travaillent en
        # parallèle pour faire entrer l'air destiné à compenser le vide laissé par la
        # vidange en casse franche : le cumul se fait sur les débits d'air réels,
        # pas sur la somme des DN. Q_air requis ≈ Q_eau de vidange par la brèche.
        cap_ventouse = _capacite_categorie("trifon", prop["trifon"])
        cap_clapet = _capacite_categorie("ceai", prop["ceai"])
        cap_purgeur = _capacite_categorie("psa", prop["psa"])
        cap_groupe = (cap_ventouse or 0.0) + (cap_clapet or 0.0) + (cap_purgeur or 0.0)
        besoin_casse = besoin_ve  # débit d'air requis = débit de vidange par la brèche
        conform_groupe = cap_groupe > 0 and cap_groupe >= besoin_casse
        part_msg = (f"Ventouses {cap_ventouse or 0:.0f} + Clapets {cap_clapet or 0:.0f} "
                    f"+ Purgeurs {cap_purgeur or 0:.0f} = {cap_groupe:.0f} m³/h")
        resultat.append({
            "categorie": "CUMUL GROUPE D'AIR (admission, casse franche)",
            "besoin": besoin_casse,
            "propose": {"cumul": True},
            "capacite_proposee": cap_groupe,
            "conforme": conform_groupe,
            "message": (f"{part_msg} vs besoin casse franche {besoin_casse:.0f} m³/h → "
                        f"{'COUVERT' if conform_groupe else 'INSUFFISANT'}. "
                        f"Conformité soumise au contrôle de la vitesse de passage de l'air "
                        f"(< 40 m/s au point le plus étroit du collecteur, anti blocage "
                        f"sonique) et à l'absence d'étranglement de la vanne/piquage de "
                        f"sectionnement par rapport à la somme des sections des appareils."),
        })

        # --- CAS PARTICULIER : décomposition Ve / PI (admission poche d'air) ---
        dec = self.decomposition_pi()
        if dec["actif"]:
            for pt in dec["points"]:
                if pt["cle"] == "ve":
                    continue  # Ve déjà vérifié ci-dessus (ventouses TRIFON)
                comp = pt.get("complement") or []
                if comp:
                    c0 = comp[0]
                    add = (f" → complément : {c0['nombre']}× {c0['fournisseur']} "
                           f"DN{c0['dn']} ({c0['cap_total']:.0f} m³/h, "
                           f"{c0['role']})")
                else:
                    add = ""
                st = "CONFORME" if pt["conforme"] else "NON CONFORME"
                resultat.append({
                    "categorie": (f"CAS PARTICULIER — {pt['point']} "
                                  f"(débit d'air à admettre)"),
                    "besoin": pt["besoin_cap_m3h"],
                    "propose": {"_pi": True, "manque_m3h": pt["manque_m3h"]},
                    "capacite_proposee": pt["cap_affectee_m3h"],
                    "conforme": pt["conforme"],
                    "message": (f"Besoin majoré (×1,15 ÷0,90) = "
                                f"{pt['besoin_cap_m3h']:.0f} m³/h ; capacité "
                                f"affectée = {pt['cap_affectee_m3h']:.0f} m³/h "
                                f"({pt['sources']}).{add} → {st}."),
                })

        return resultat
    def _dn_client(self, cat: str, defaut: int, organes=None) -> int:
        """Plus grand DN proposé par le client pour une catégorie (complément).

        Par défaut sur les organes du point haut Ve (hors organes dédiés PI) ;
        `organes` permet de cibler une autre liste (ex. organes dédiés PI).
        """
        organes = self._organes_ve() if organes is None else organes
        dns = [int(o.get("dn") or 0) for o in organes
               if o.get("type") == cat and o.get("dn")]
        return max(dns) if dns else defaut

    def _complement_air(self, manque_m3h: float, clients: dict,
                        organes: list = None) -> list:
        """Complément proposé pour couvrir un manque d'admission d'air.

        Règle « Ve/PI » : ventouse ajoutée = TRIFON (double fonction admission +
        évacuation), autre organe ajouté = clapet SNH — DN issu de la proposition
        client (défauts : ventouse TRIFON DN300, clapet SNH DN250).
        Sélection : l'option couvrant le manque avec le MOINS d'unités
        (égalité → ventouse TRIFON, double fonction).
        """
        import math
        from .data.catalogues import TRIFON
        from .data.valve_db import table_capacite as _tab

        if manque_m3h <= 0:
            return []
        organes = self._organes_ve() if organes is None else organes

        dn_v = self._dn_client("trifon", 300, organes)
        cap_v = TRIFON.get(dn_v, {}).get("q", {}).get(-3, 0.0) or 0.0
        dn_c = self._dn_client("ceai", 250, organes)
        tab_c = _tab("SNH", "clapet")
        cap_c = tab_c.get(dn_c, 0.0) or 0.0

        nb_v = math.ceil(manque_m3h / cap_v) if cap_v > 0 else 10 ** 9
        nb_c = math.ceil(manque_m3h / cap_c) if cap_c > 0 else 10 ** 9

        # Choix : le moins d'unités (ventouse TRIFON en cas d'égalité).
        if nb_v <= nb_c:
            return [{
                "type": "ventouse", "fournisseur": "TRIFON", "dn": dn_v,
                "nombre": nb_v, "cap_unitaire": cap_v,
                "cap_total": nb_v * cap_v, "role": "admission + évacuation",
            }]
        return [{
            "type": "clapet", "fournisseur": "SNH", "dn": dn_c,
            "nombre": nb_c, "cap_unitaire": cap_c,
            "cap_total": nb_c * cap_c, "role": "admission",
        }]

    def decomposition_pi(self) -> dict:
        """Décompose la proposition d'organes client entre les points hauts
        (Ve) et intermédiaires (PI) lorsqu'un CAS PARTICULIER (poche d'air,
        Q_PI > 0) doit être admis en casse franche.

        Principe :
          • PH(Ve) : couvert par les VENTOUSES TRIFON du client ;
            l'excédent de capacité est reporté au(x) point(s) intermédiaire(s).
          • PI1/PI2 : couverts par l'excédent des ventouses + les CLAPETS
            d'admission (SNH) du client ; si manque → complément proposé
            (ventouse TRIFON ou clapets SNH, DN de la proposition client).
          • Des organes DÉDIÉS peuvent être saisis pour chaque PI grâce à la
            position « PI1 »/« PI2 » de l'onglet Vérification : chaque PI est
            alors vérifié contre son propre lot d'organes (prioritaire sur
            l'excédent ventouses + clapets partagés).
          • Un PURGEUR SONIQUE SNH (NSH) est recommandé à l'amont de chacun
            des points hauts (Ve et PI) pour l'évacuation sonique au
            remplissage.

        Facteur de référence : capacité requise = 1,15 × débit / 0,90
        (marge accessoires 15 % + plafond d'utilisation 90 %).

        Retour : {"actif": bool, "fs": float, "points": [...], "purgeurs_soniques": [...]}
        """
        from .core.dimensionnement import (MARGE_ACCESSOIRES_PCT,
                                           PLAFOND_UTILISATION_PCT,
                                           _marge_factor, choix_purgeur_snh)
        if self.resultat is None or self.derniere_trace is None:
            self.calculer()
        res = self.resultat

        fs = (_marge_factor(MARGE_ACCESSOIRES_PCT)
              / (PLAFOND_UTILISATION_PCT / 100.0))

        # Points intermédiaires actifs (poche d'air amont/aval).
        cibles = []
        if self.has_pi1() and (res.q_pi1_m3h or 0) > 0:
            cibles.append({"cle": "pi1", "label": "PI1 (amont)",
                           "z": self.z_pi1, "besoin": res.q_pi1_m3h})
        if self.has_pi2() and (res.q_pi2_m3h or 0) > 0:
            cibles.append({"cle": "pi2", "label": "PI2 (aval)",
                           "z": self.z_pi2, "besoin": res.q_pi2_m3h})
        if not cibles:
            return {"actif": False, "fs": fs, "points": [], "purgeurs_soniques": []}

        # Capacités installées proposées par le client (point haut Ve —
        # les organes « dédiés PI » sont gérés par point intermédiaire).
        prop = {"trifon": [], "ceai": [], "psa": []}
        for o in self._organes_ve():
            prop[o["type"]].append(o)
        cap_ventouse = sum(capacite_organe(o, -3) for o in prop["trifon"])
        cap_clapet = sum(capacite_organe(o, -3) for o in prop["ceai"])

        q_ve = max(res.q_ve_m3h or 0.0, 0.0)
        besoin_ve = q_ve * fs

        # --- PH(Ve) : ventouses du client ---
        manque_ve = max(besoin_ve - cap_ventouse, 0.0)
        complement_ve = self._complement_air(manque_ve, prop)
        surplus_ve = max(cap_ventouse - besoin_ve, 0.0)
        if complement_ve:
            surplus_ve = max((cap_ventouse + complement_ve[0]["cap_total"])
                             - besoin_ve, 0.0)
        cap_ve_ret = (cap_ventouse
                      + (complement_ve[0]["cap_total"] if complement_ve else 0.0))

        points = [{
            "point": "Ve (point haut)",
            "cle": "ve", "z": self.z_ve,
            "besoin_m3h": q_ve, "besoin_cap_m3h": besoin_ve,
            "cap_affectee_m3h": cap_ve_ret,
            "sources": "ventouses TRIFON (client)" if cap_ventouse else "—",
            "conforme": cap_ve_ret >= besoin_ve,
            "manque_m3h": manque_ve,
            "complement": complement_ve,
            "surplus_m3h": surplus_ve,
        }]

        # --- PI : organes DÉDIÉS (position « pi1 »/« pi2 ») s'ils ont été
        # saisis, sinon excédent des ventouses + clapets (règle historique) ---
        cap_pi_initiale = surplus_ve + cap_clapet
        for c in cibles:
            besoin = c["besoin"] * fs
            propres = self._organes_pi(c["cle"])
            cap_propres = sum(capacite_organe(o, -3) for o in propres)
            if propres:
                # Organes dédiés → chaque PI est vérifié contre son propre lot.
                manque = max(besoin - cap_propres, 0.0)
                complement = self._complement_air(manque, prop, organes=propres)
                cap_ret = cap_propres + (complement[0]["cap_total"] if complement else 0.0)
                detail = " — " + " + ".join(
                    f"{o.get('nombre', 1)}× DN{o.get('dn')}"
                    + (f" [{o.get('fournisseur')}]" if o.get("fournisseur") else "")
                    for o in propres)
                sources = (f"organes dédiés {c['label']} (client){detail}")
            else:
                manque = max(besoin - cap_pi_initiale, 0.0)
                complement = self._complement_air(manque, prop)
                cap_ret = cap_pi_initiale + (complement[0]["cap_total"] if complement else 0.0)
                sources = (f"excédent ventouses {surplus_ve:.0f} + "
                           f"clapets {cap_clapet:.0f} m³/h (client)")
                cap_pi_initiale = max(cap_ret - besoin, 0.0)
            points.append({
                "point": f"{c['label']} (point intermédiaire)",
                "cle": c["cle"], "z": c["z"],
                "besoin_m3h": c["besoin"], "besoin_cap_m3h": besoin,
                "cap_affectee_m3h": cap_ret,
                "sources": sources,
                "conforme": cap_ret >= besoin,
                "manque_m3h": manque,
                "complement": complement,
                "surplus_m3h": max(cap_ret - besoin, 0.0),
                "organes_dedies_m3h": cap_propres if propres else None,
            })

        # --- Purgeurs soniques SNH (NSH) à l'amont de chaque point haut ---
        q_rempl = self.derniere_trace["remplissage"]["q"]
        sel_snh = choix_purgeur_snh(q_rempl, self.pression_nominale or 10.0)
        purgeurs = [{
            "point": p["point"], "cle": p["cle"],
            "dn": sel_snh.dn, "modele": sel_snh.nom,
            "cap_sonique_m3h": sel_snh.capacite_unitaire_m3h,
        } for p in points]

        return {"actif": True, "fs": fs, "points": points,
                "purgeurs_soniques": purgeurs}

    # ------------------------------------------------------------------
    # Cumul des débits d'air (note « Débits cumulés »)
    # ------------------------------------------------------------------
    def cumul_debits(self) -> dict:
        """Cumule les débits d'air des appareils au point haut et vérifie la
        capacité d'admission en casse franche (Q_eau = A·√(2·g·H_z)).

        Retourne un dictionnaire de synthèse utilisable par l'onglet « Cumul »
        et par les rapports :
            {
              besoin_casse: Q_eau (m³/h) à faire entrer par la brèche,
              q_eau_m3s:    Q_eau (m³/s),
              admission:   {trifon, ceai, psa, total}  (m³/h),
              expulsion:   {trifon, psa, total}        (m³/h),
              vanne:       {dn, section_vanne, section_amont, section_aval, ratio, conforme},
              limite_vitesse: {vitesse_max, v_appareils, ok},
              contacts:    liste de contrôles,
              strictly_missing: bool (aucun débit d'admission renseigné),
              verdict_admission: bool,
              verdict_expulsion: bool,
            }
        """
        if self.derniere_trace is None:
            self.calculer()
        dc = self.derniere_trace["dc"]

        # --- Regroupement des organes proposés ---
        prop = {"trifon": [], "ceai": [], "psa": [], "vanne": []}
        amont = {"trifon": [], "ceai": [], "psa": []}
        aval = {"trifon": [], "ceai": [], "psa": []}
        for o in self.organes_client:
            cat = o.get("type", "")
            if cat in prop:
                prop[cat].append(o)
            pos = (o.get("position") or "amont").lower()
            if cat in amont:
                (amont if pos == "amont" else aval)[cat].append(o)

        def _cap(cat, org, depr=-3):
            """Capacité cumulée installée (m³/h) d'une liste d'organes."""
            return sum(capacite_organe(o, depr) for o in org)

        def _section_dn(dn):
            """Section (m²) d'un organe par son DN nominal en mm."""
            if not dn:
                return 0.0
            return math.pi * (dn / 1000.0) ** 2 / 4.0

        def _section_ecoulement(o):
            """Section d'écoulement (m²) réelle d'un organe.

            Ventouses / clapets : DN nominal (corps ≈ passage d'air).
            Purgeurs soniques : la section effective du goulot (orifice/tuyère)
            est bien plus faible que le DN enveloppe → dérivée de la capacité
            sonique à la vitesse de sortie de référence (200 m/s, §9.2).
            """
            if o.get("type") != "psa":
                return _section_dn(o.get("dn")) * max(o.get("nombre", 0), 0)
            q = _capacite_sonique_purgeur(o)
            return (q / (V_SONIQUE_MS * 3600.0)) * max(o.get("nombre", 0), 0)

        def _sections(orgs):
            """Somme des sections réelles (m²) d'une liste d'organes."""
            return sum(_section_ecoulement(o) for o in orgs)

        # --- Besoin casse franche : Q_eau = A·√(2·g·H_z) ---
        g = 9.81
        hz = max(self.hz_casse_franche, 0.0)
        section_conduite = math.pi * dc.d ** 2 / 4.0   # A (m²) conduite DN
        v_ecoulement = math.sqrt(2 * g * hz)            # m/s
        q_eau_m3s = section_conduite * v_ecoulement     # m³/s
        q_eau_m3h = q_eau_m3s * 3600.0

        # --- Cumul admission (anti-dépression / casse franche) ---
        # Ventouses + clapets + purgeurs travaillent en parallèle pour faire
        # entrer l'air : on cumule les DÉBITS réels, pas les DN.
        a_ventouse = _cap("trifon", prop["trifon"])
        a_clapet = _cap("ceai", prop["ceai"])
        a_purgeur = _cap("psa", prop["psa"])          # purgeurs en entrée d'air
        total_admission = a_ventouse + a_clapet + a_purgeur

        # --- Répartition amont / aval de la vanne de sectionnement ---
        # Amont : l'air circule à travers la vanne (point le plus étroit).
        # Aval  : l'air entre directement en aval de la vanne (bypass).
        a_amont = (_cap("trifon", amont["trifon"]) + _cap("ceai", amont["ceai"])
                   + _cap("psa", amont["psa"]))
        a_aval = (_cap("trifon", aval["trifon"]) + _cap("ceai", aval["ceai"])
                  + _cap("psa", aval["psa"]))

        # --- Cumul expulsion (remplissage / régime permanent) ---
        # Seuls les éléments conçus pour l'échappement interviennent :
        # ventouses + purgeurs soniques.
        e_ventouse = a_ventouse
        e_purgeur = a_purgeur
        total_expulsion = e_ventouse + e_purgeur

        verdict_admission = total_admission > 0 and total_admission >= q_eau_m3h
        verdict_expulsion = total_expulsion > 0

        # --- Vérification vanne de sectionnement / collecteur (amont) ---
        dn_vanne = self.dn_vanne_sectionnement or 0.0
        section_vanne = _section_dn(dn_vanne)
        v_limite = 40.0  # m/s, générique (anti blocage sonique)

        # Seuls les organes AMONT transitent par la vanne → on leur compare la
        # section de vanne (pas d'étranglement : S_vanne > Σ sections amont).
        section_amont = _sections(amont["trifon"] + amont["ceai"] + amont["psa"])
        ratio_amont = (section_vanne / section_amont if section_amont > 0
                       else (0.0 if section_vanne == 0 else float("inf")))
        vanne_conforme = section_vanne > 0 and (section_amont == 0 or ratio_amont > 1.0)

        # --- Vitesse de passage de l'air ---
        # Point le plus étroit amont : la vanne → V = Q_amont / S_vanne.
        transit_vanne = a_amont
        vitesse_vanne = (transit_vanne / 3600.0 / section_vanne
                         if section_vanne > 0 else float("inf"))
        # Point le plus étroit aval : la conduite (DN principal) → V = Q_aval/S_dn.
        section_aval = _sections(aval["trifon"] + aval["ceai"] + aval["psa"])
        vitesse_aval = (a_aval / 3600.0 / section_conduite
                        if section_conduite > 0 else float("inf"))
        ratio_aval = (section_conduite / section_aval if section_aval > 0
                      else (0.0 if section_conduite == 0 else float("inf")))

        ok_vitesse_vanne = vitesse_vanne <= v_limite + 1e-9
        ok_vitesse_aval = vitesse_aval <= v_limite + 1e-9
        ok_vitesse = ok_vitesse_vanne and ok_vitesse_aval

        # Capacité de passage maximale de la vanne à la limite de vitesse
        capacite_passage_40 = 40.0 * section_vanne * 3600.0 if section_vanne > 0 else 0.0

        contacts = [
            ("Dépression de référence", f"-3 mCE (ΔP seuil anti-dépression)",
             "Les courbes constructeurs fournissent les débits d'air à cette ΔP."),
            ("Admission amont (transite par la vanne)",
             f"{a_amont:,.0f} m³/h",
             "Abaisser en amont pour réduire la vitesse dans la vanne."),
            ("Admission aval (bypass direct conduit)",
             f"{a_aval:,.0f} m³/h",
             "Les organes en aval n'étranglent pas la vanne de sectionnement."),
            ("Vitesse de passage de l'air",
             f"{vitesse_vanne:.1f} m/s à la vanne (limite 40 m/s)",
             "Vérifier l'absence de blocage sonique prématuré au point le plus étroit."),
            ("Section vanne sectionnement",
             f"{section_vanne:.2f} m² vs {section_amont:.2f} m² (Σ sections amont)",
             "La vanne/piquage ne doit pas étrangler le passage d'air (ratio > 1)."),
        ]

        strictly_missing = total_admission <= 0
        if strictly_missing:
            verdict_admission = False

        return {
            "dc": dc,
            "hz": hz,
            "section_conduite": section_conduite,
            "v_ecoulement": v_ecoulement,
            "q_eau_m3s": q_eau_m3s,
            "besoin_casse": q_eau_m3h,
            "admission": {"trifon": a_ventouse, "ceai": a_clapet,
                          "psa": a_purgeur, "total": total_admission,
                          "amont": a_amont, "aval": a_aval},
            "expulsion": {"trifon": e_ventouse, "psa": e_purgeur,
                          "total": total_expulsion},
            "vanne": {"dn": dn_vanne, "section_vanne": section_vanne,
                      "section_amont": section_amont, "section_aval": section_aval,
                      "section_conduite": section_conduite,
                      "ratio": ratio_amont, "ratio_aval": ratio_aval,
                      "conforme": vanne_conforme},
            "limite_vitesse": {"v_limite": v_limite, "v_air": vitesse_vanne,
                               "v_aval": vitesse_aval, "ok": ok_vitesse,
                               "ok_vanne": ok_vitesse_vanne, "ok_aval": ok_vitesse_aval,
                               "capacite_passage_40": capacite_passage_40},
            "contacts": contacts,
            "strictly_missing": strictly_missing,
            "verdict_admission": verdict_admission,
            "verdict_expulsion": verdict_expulsion,
        }

    def verifier_groupe_mk_aa(self) -> dict:
        """Vérifie le GROUPE installé (ventouses + clapets + purgeurs) face aux
        DÉBITS MK_A.A (point haut Q_Ve), et non face à la brèche.

        C'est la vérification demandée pour le mode « Formule MK_A.A » :
        le besoin de référence est le débit d'air qui doit entrer au point haut
        (Q_Ve = q_ve_m3h), majoré de la marge 15 %, et le respect de la
        vitesse sonique (anti-étranglement ≤ 40 m/s au point le plus étroit).

        Retour :
            {
              besoin_mk_aa: Q_Ve (m³/h),
              besoin_majore:   Q_Ve × 1,15,
              cap_min_installee: besoin_majore / 0,90 (plafond 90 %),
              admission:      {trifon, ceai, psa, total}  installés,
              amont/aval:     répartition réelle,
              conforme, manque,
              vitesse:        {vanne, aval, limite_40, ok},
              purgeur_sonique: capacité sonique du NSH retenu,
              verite_brèche:  rappel du besoin brèche (comparaison moins disant),
              moins_disant:   la base qui exige le moins (MK_A.A vs brèche),
            }
        """
        if self.resultat is None or self.derniere_trace is None:
            self.calculer()
        res = self.resultat
        dc = self.derniere_trace["dc"]

        besoin_mk_aa = max(res.q_ve_m3h or 0.0, 0.0)
        from .core.dimensionnement import MARGE_ACCESSOIRES_PCT, PLAFOND_UTILISATION_PCT
        besoin_majore = besoin_mk_aa * (1.0 + MARGE_ACCESSOIRES_PCT / 100.0)
        cap_min_installee = (besoin_majore / (PLAFOND_UTILISATION_PCT / 100.0)
                             if besoin_majore > 0 else 0.0)

        prop = {"trifon": [], "ceai": [], "psa": []}
        amont = {"trifon": [], "ceai": [], "psa": []}
        aval = {"trifon": [], "ceai": [], "psa": []}
        for o in self.organes_client:
            cat = o.get("type", "")
            if cat not in prop:
                continue
            prop[cat].append(o)
            pos = (o.get("position") or "amont").lower()
            (amont if pos == "amont" else aval)[cat].append(o)

        def _cap(orgs):
            return sum(capacite_organe(o) for o in orgs)

        a_ventouse = _cap(prop["trifon"])
        a_clapet = _cap(prop["ceai"])
        a_purgeur = _cap(prop["psa"])
        total = a_ventouse + a_clapet + a_purgeur

        a_amont = (_cap(amont["trifon"]) + _cap(amont["ceai"]) + _cap(amont["psa"]))
        a_aval = (_cap(aval["trifon"]) + _cap(aval["ceai"]) + _cap(aval["psa"]))

        def _section_dn(dn):
            return math.pi * (dn / 1000.0) ** 2 / 4.0 if dn else 0.0

        dn_vanne = self.dn_vanne_sectionnement or 0.0
        v_limite = 40.0
        section_vanne = _section_dn(dn_vanne)
        section_conduite = math.pi * dc.d ** 2 / 4.0
        vitesse_vanne = (a_amont / 3600.0 / section_vanne
                         if section_vanne > 0 else float("inf"))
        vitesse_aval = (a_aval / 3600.0 / section_conduite
                        if section_conduite > 0 else float("inf"))
        ok_vitesse = vitesse_vanne <= v_limite + 1e-9 and vitesse_aval <= v_limite + 1e-9

        cap_psa_sonique = sum(_capacite_sonique_purgeur(o) for o in prop["psa"])

        besoin_breche = self.cumul_debits().get("besoin_casse", 0.0)
        moins_disant = "MK_A.A" if besoin_mk_aa <= besoin_breche else "brèche"

        conforme = total > 0 and total >= besoin_majore

        return {
            "besoin_mk_aa": besoin_mk_aa,
            "besoin_majore": besoin_majore,
            "cap_min_installee": cap_min_installee,
            "admission": {"trifon": a_ventouse, "ceai": a_clapet,
                          "psa": a_purgeur, "total": total},
            "amont": a_amont, "aval": a_aval,
            "conforme": conforme,
            "manque": max(besoin_majore - total, 0.0),
            "capacite_passage_40": 40.0 * section_vanne * 3600.0 if section_vanne > 0 else 0.0,
            "vitesse": {"vanne": vitesse_vanne, "aval": vitesse_aval,
                        "limite": v_limite, "ok": ok_vitesse},
            "purgeur_sonique": cap_psa_sonique,
            "besoin_breche": besoin_breche,
            "moins_disant": moins_disant,
        }

 
    # ------------------------------------------------------------------
    # Implantation & justification amont/aval (repère : vanne de sectionnement)
    # ------------------------------------------------------------------
    def plan_pose(self) -> dict:
        """Structure « Implantation & justification » pour les rapports.

        Repère : la vanne de sectionnement. La ventouse Ve se trouve au même
        emplacement en plan que la vanne ; les deux sont distingués par leur
        altitude Z. Amont = côté point haut Ve (l'air transite par la vanne) ;
        aval = côté conduite (bypass, n'étrangle pas la vanne).

        Retour : {repere, organes_par_position, cumul, combo}
        """
        cumul = self.cumul_debits() if self.organes_client else None
        par_pos = {"amont": [], "aval": [], "pi1": [], "pi2": [],
                   "sans_position": []}
        for o in self.organes_client:
            # La vanne de sectionnement n'est pas un organe d'air : exclue du plan de pose
            if o.get("type") == "vanne":
                continue
            pos = (o.get("position") or "").lower()
            lib = {
                "trifon": "Ventouse d'admission",
                "ceai": "Clapet d'entrée d'air",
                "psa": "Purgeur remplissage",
                "vanne": "Vanne de sectionnement",
            }.get(o.get("type"), o.get("type"))
            dn = o.get("dn") if o.get("dn") is not None else "—"
            four = (" [" + o["fournisseur"] + "]") if o.get("fournisseur") else ""
            ligne = (f"{max(o.get('nombre', 0), 0)} × {lib} DN {dn}{four}")
            if pos in par_pos:
                par_pos[pos].append(ligne)
            else:
                par_pos["sans_position"].append(ligne)

        if not cumul:
            return {"repere": self._texte_repere_vanne(), "organes_par_position": par_pos,
                    "cumul": None, "combo": not (self.organes_client)}

        rep = cumul["admission"]
        v = cumul["vanne"]
        lv = cumul["limite_vitesse"]
        combo = {
            "amont": rep["amont"], "aval": rep["aval"],
            "q_amont_pct": (rep["amont"] / rep["total"] * 100.0
                            if rep["total"] > 0 else 0.0),
            "q_aval_pct": (rep["aval"] / rep["total"] * 100.0
                           if rep["total"] > 0 else 0.0),
            "capacite_passage_40": lv["capacite_passage_40"],
            "v_air": lv["v_air"], "v_aval": lv["v_aval"], "v_limite": lv["v_limite"],
            "section_vanne": v["section_vanne"], "section_amont": v["section_amont"],
            "section_conduite": v["section_conduite"],
            "ratio": v["ratio"], "ratio_aval": v["ratio_aval"],
            "dn_vanne": v["dn"],
        }
        # Bloc texte de justification (réutilisation dans txt/pdf/DOCX)
        just = [
            "Repère d'implantation : la VANNE DE SECTIONNEMENT. La ventouse Ve "
            "est positionnée au même emplacement en plan que la vanne — les deux "
            "sont distingués par leur altitude Z.",
            f"Organes AMONT (côté point haut Ve) : l'air transite par la vanne de "
            f"sectionnement (point le plus étroit). Débit amont = {rep['amont']:,.0f} "
            f"m³/h ({combo['q_amont_pct']:.0f} % de l'admission).",
            f"Organes AVAL (côté conduite) : l'air entre directement en aval de la "
            f"vanne (bypass conduite) et n'étrangle pas le passage de la vanne. "
            f"Débit aval = {rep['aval']:,.0f} m³/h ({combo['q_aval_pct']:.0f} %).",
        ]
        if v["dn"]:
            bilan_etranglement = ("pas d'étranglement" if v["conforme"]
                                  else "étranglement à lever")
            just.append(
                f"Vérification vanne DN {v['dn']:g} : section de vanne "
                f"{v['section_vanne']:.2f} m² vs Σ sections amont {v['section_amont']:.2f} "
                f"m² → ratio {v['ratio']:.2f} ({bilan_etranglement}).")
        if lv["capacite_passage_40"] > 0:
            just.append(
                f"Capacité de passage de la vanne à la limite de vitesse ({lv['v_limite']:g} m/s) = "
                f"{lv['capacite_passage_40']:,.0f} m³/h — les organes amont cumulent "
                f"{rep['amont']:,.0f} m³/h, vitesse amont {lv['v_air']:.1f} m/s "
                f"({'≤ 40 m/s OK' if lv['ok_vanne'] else '> 40 m/s : à répartir davantage en aval'}).")
        combo["justifications"] = just
        return {"repere": just[0], "organes_par_position": par_pos,
                "cumul": cumul, "combo": combo}

    def _texte_repere_vanne(self) -> str:
        return ("Repère d'implantation : la VANNE DE SECTIONNEMENT. La ventouse Ve "
                "est positionnée au même emplacement en plan que la vanne — les "
                "deux sont distingués par leur altitude Z.")

    # ------------------------------------------------------------------
    # Tableau d'implantation X, Y, Z (livrable exécution)
    # ------------------------------------------------------------------
    def plan_xyz(self) -> dict:
        """Coordonnées X, Y, Z d'exécution du montage validé/conforme.

        Les coordonnées sont PRISES AUTOMATIQUEMENT depuis le profil en long :
          - organe AMONT : placé au point haut Ve (même emplacement en plan que
            la vanne de sectionnement) → X = X_Ve, Z = Z_Ve, Y = 0 (axe conduite) ;
          - organe AVAL : placé sur la branche descendant, juste après la vanne
            (côté conduite) → X légèrement en aval de Ve, Z interpolée sur la
            branche ve→vi2, Y = 0 ;
          - sans position : repli au point haut.

        Retour : {"organes":[{ref,type,dn,nombre,fournisseur,position,
                              x_m,y_m,z_m,remarque}], "base": "profil en long"}
        """
        from .utils import croquis as croq
        pts = croq.points_profil(self)
        mapping = {k: (x, z) for k, x, z, _ in pts}

        # Montage à dessiner (même règle que le croquis : conforme ou optimisé)
        try:
            grp = croq._groupe_a_dessiner(self)
            organes = grp["organes"]
        except Exception:
            organes = [o for o in (self.organes_client or [])
                       if o.get("type") != "vanne"]

        # x (m) du point où l'on interpole la cote, pour la branche ve→vi2
        x_ve = mapping.get("ve", (0.0, 0.0))[0]

        # Branche aval : segment ve→vi2 (pour interpolation d'altitude)
        branche = None
        if "ve" in mapping and "vi2" in mapping:
            (x1, z1), (x2, z2) = mapping["ve"], mapping["vi2"]
            branche = (x1, z1, x2, z2)

        def _z_branche(x):
            if not branche or (branche[2] - branche[0]) == 0:
                return branche[1] if branche else None
            t = (x - branche[0]) / (branche[2] - branche[0])
            return branche[1] + t * (branche[3] - branche[1])

        liste = []
        ref_cpt = 0
        for i, o in enumerate(organes, start=1):
            pos = (o.get("position") or "").lower()
            dn = o.get("dn") if o.get("dn") is not None else "—"
            ref_cpt += 1
            if pos == "amont":
                xm = x_ve
                zm = mapping.get("ve", (0.0, 0.0))[1]
                remarque = "Au point haut Ve (même emplacement en plan que la vanne) — air transite par la vanne"
            elif pos == "aval":
                # Légèrement en aval de la vanne, sur la branche côté conduite
                delta = 5.0
                xm = x_ve + delta
                zm = _z_branche(xm)
                remarque = "Sur la branche aval, après la vanne (côté conduite) — by-pass de la vanne"
            elif pos in ("pi1", "pi2"):
                # Organes dédiés au point intermédiaire (poche d'air) : placés
                # au point haut PI lui-même → X = X_PI et Z = Z_PI (réels).
                mp = mapping.get(pos)
                if mp:
                    xm = mp[0]
                    zm = mp[1]
                    remarque = (f"Point intermédiaire {pos.upper()} — organes dédiés "
                                f"(poche d'air) : altitude réelle du point haut {pos.upper()}")
                else:
                    xm = x_ve
                    zm = mapping.get("ve", (0.0, 0.0))[1]
                    remarque = (f"Point intermédiaire {pos.upper()} absent du profil — "
                                "replacé au point haut Ve")
            else:
                xm = x_ve
                zm = mapping.get("ve", (0.0, 0.0))[1]
                remarque = "Position non renseignée — replacé au point haut"
            liste.append({
                "ref": f"P{ref_cpt:02d}",
                "type": {"trifon": "Ventouse", "ceai": "Clapet", "psa": "Purgeur",
                         "vanne": "Vanne"}.get(o.get("type"), o.get("type")),
                "dn": dn,
                "nombre": max(o.get("nombre", 0), 0),
                "fournisseur": (o.get("fournisseur") or ""),
                "position": pos or "—",
                "x_m": round(xm, 1),
                "y_m": 0.0,
                "z_m": (round(zm, 2) if zm is not None else None),
                "remarque": remarque,
            })

        return {
            "organes": liste,
            "base": "Coordonnées prises automatiquement depuis le profil en long "
                    "(axe Y = 0 sur l'axe de la conduite).",
            "optimise": (grp["optimise"] if 'grp' in dir() else False),
        }

    # ------------------------------------------------------------------
    # Tableau de vérification des organes — proposition client (rapport)
    # ------------------------------------------------------------------
    def tableau_verification_organes(self) -> list:
        """Lignes du tableau « Vérification des organes (proposition client) ».

        Une ligne par organe d'air proposé par le client, rattachée au point
        haut où il est implanté (Ve, PI1 ou PI2). Le Fs est calculé sur le
        BESOIN BRUT du point en casse franche (Q MK_A.A), SANS majoration :
            Fs = Capacité installée du point / Demande du point.
        Verdict : Fs ≥ 1,00 → « Conforme » (le contrôleur juge la valeur du Fs
        dans ses écrits et observations). Les purgeurs soniques (organes de
        service au remplissage) n'ont pas de Fs : verdict « Conforme ».

        Retour : [ {repere, demande_m3h, categorie, dn, nombre, implantation,
                    fournisseur, capacite_m3h, fs, verdict} ]
        """
        if self.resultat is None or self.derniere_trace is None:
            self.calculer()
        res = self.resultat
        besoins = {
            "ve": max(res.q_ve_m3h or 0.0, 0.0),
            "pi1": max(res.q_pi1_m3h or 0.0, 0.0),
            "pi2": max(res.q_pi2_m3h or 0.0, 0.0),
        }
        lib_cat = {"trifon": "Ventouse", "ceai": "Clapet", "psa": "Purgeur"}
        ordre_point = {"ve": 0, "pi1": 1, "pi2": 2}
        ordre_type = {"trifon": 0, "ceai": 1, "psa": 2}

        def _point(o):
            pos = (o.get("position") or "").lower()
            return pos if pos in ("pi1", "pi2") else "ve"

        organes = [o for o in (self.organes_client or [])
                   if o.get("type") not in (None, "", "vanne")]
        organes.sort(key=lambda o: (ordre_point.get(_point(o), 3),
                                    ordre_type.get(o.get("type", ""), 9)))

        rows = []
        for o in organes:
            typ = o.get("type", "")
            pt = _point(o)
            demande = besoins.get(pt, 0.0)
            nombre = max(o.get("nombre", 0), 0)
            cap_tot = capacite_organe(o, -3)
            if typ in ("trifon", "ceai"):
                fs = (cap_tot / demande if demande > 0 else None)
                verdict = "Conforme" if (fs is not None and fs >= 1.0) else "Non conforme"
            else:
                fs = None
                verdict = "Conforme"
            rep = f"Pht {pt.upper()}"
            impl = rep
            if typ == "psa" and pt in ("pi1", "pi2"):
                impl = f"Amt {pt.upper()}"
            rows.append({
                "repere": rep,
                "demande_m3h": (demande if typ in ("trifon", "ceai") else None),
                "categorie": lib_cat.get(typ, typ),
                "dn": o.get("dn"),
                "nombre": nombre,
                "implantation": impl,
                "fournisseur": o.get("fournisseur", "") or "—",
                "capacite_m3h": cap_tot if cap_tot else None,
                "fs": (round(fs, 2) if fs is not None else None),
                "verdict": verdict,
            })
        return rows

    # ------------------------------------------------------------------
    # Nomenclature des organes — à partir du montage validé/conforme
    # ------------------------------------------------------------------
    def nomenclature(self) -> dict:
        """Génère la nomenclature des équipements à partir du montage validé.

        Se base sur le GROUPE VALIDÉ/CONFORME (même règle que le croquis et le
        plan XYZ : proposition client conforme sinon groupe optimisé). Chaque
        organe du montage est détaillé avec repère, désignation, DN, PN, quantité
        et rôle.

        Retour :
        {
          "organes": [{rep, designation, dn, pn, qte, role}],
          "complement": [{designation, dn, pn, qte, role}],  # pièces annexes
          "base": "montage validé/conforme"
        }
        """
        from .utils import croquis as croq
        try:
            grp = croq._groupe_a_dessiner(self)
            organes = grp["organes"]
            optimise = grp["optimise"]
            montage = grp["titre"]
        except Exception:
            organes = [o for o in (self.organes_client or [])
                       if o.get("type") != "vanne"]
            optimise = False
            montage = "Montage retenu (proposition client)"

        pn = getattr(self, "pression_nominale", 10.0) or 10.0
        labels = {
            "trifon": "Ventouse triple fonction (grand orifice)",
            "ceai": "Clapet d'admission d'air grand débit",
            "psa": "Purgeur d'air automatique",
        }
        positions = {
            "amont": "côté point haut Ve (transite par la vanne)",
            "aval": "côté conduite (bypass de la vanne)",
            "": "—",
        }

        liste = []
        # Regroupement par (type-famille, dn, fournisseur) pour cumuler les qtés
        group = {}
        for o in organes:
            t = o.get("type", "")
            if t == "vanne":
                continue
            dn = o.get("dn") or "—"
            four = o.get("fournisseur") or ""
            pos = (o.get("position") or "").lower()
            key = (t, str(dn), four)
            if key not in group:
                group[key] = {"qte": 0, "pos": pos, "dn": dn, "type": t,
                              "four": four}
            group[key]["qte"] += max(o.get("nombre", 0), 0)

        for (t, dn, four), g in group.items():
            designation = labels.get(t, t.capitalize())
            if four:
                designation += f" — {four}"
            role = (g["pos"] and positions.get(g["pos"], g["pos"])) or "—"
            name_role = ("Admission d'air — " if t in ("trifon", "ceai")
                         else "Évacuation/dégazage d'air — " if t == "psa"
                         else "")
            liste.append({
                "rep": f"{len(liste)+1:02d}",
                "designation": designation,
                "dn": f"DN {dn}",
                "pn": f"PN {pn:g}",
                "qte": g["qte"],
                "role": f"{name_role}{role}",
            })

        # Pièces annexes (vannes d'isolement, joints, nourrices…)
        complement = []
        # 1 vanne d'isolement par organe d'air équipé, même DN
        for it in liste:
            if it["role"].startswith(("Admission", "Évacuation")):
                complement.append({
                    "designation": "Vanne d'isolement à opercule passage intégral",
                    "dn": it["dn"], "pn": it["pn"], "qte": it["qte"],
                    "role": f"Sous {it['designation'].split(' —')[0]} "
                            f"({it['dn']}) pour maintenance",
                })
        complement.append({
            "designation": "Vanne de sectionnement principale (papillon double "
                           "excentration)",
            "dn": f"DN {self.dn_vanne_sectionnement:g}" if self.dn_vanne_sectionnement else "DN —",
            "pn": f"PN {pn:g}",
            "qte": 1,
            "role": "Sépare amont/aval de la conduite au point haut",
        })
        dn_vanne = (f"{self.dn_vanne_sectionnement:g}" if self.dn_vanne_sectionnement
                    else "—")
        for it in liste + [c for c in complement if c["dn"] == f"DN {dn_vanne}"]:
            if it["designation"].startswith("Vanne d'isolement"):
                complement.append({
                    "designation": "Joint de démontage autobuté",
                    "dn": it["dn"], "pn": it["pn"], "qte": it["qte"],
                    "role": f"Monté avec chaque vanne {it['dn']} pour pose/dépose",
                })

        return {
            "organes": liste,
            "complement": complement,
            "base": (f"Nomenclature établie depuis le {montage}. "
                     "PN = classe de pression de la conduite."),
        }

    # ------------------------------------------------------------------
    # Analyse numérique du groupe retenu (base de contrôle transparente)
    # ------------------------------------------------------------------
    def _analyse_num_dimensionnement(self) -> list:
        """Lignes d'analyse numérique du groupe retenu, pour aider le
        contrôleur à valider ou écarter le dimensionnement corrigé.

        Les valeurs dépendent de la méthode sélectionnée :
        - MK_A.A : besoin Q_Ve majoré (+15 %, plafond 90 %) + vitesses ;
        - Brèche/Torricelli : besoin casse franche Q_eau + vanne + vitesses."""
        try:
            methode = (self.methode_dimensionnement or "mk_aa")
            lines = []
            if methode != "breche":
                ga = self.verifier_groupe_mk_aa()
                adm = ga["admission"]; vt = ga["vitesse"]
                lines.append(
                    f"Besoin MK_A.A Q_Ve = {ga['besoin_mk_aa']:,.0f} m³/h ; "
                    f"majoré +15 % = {ga['besoin_majore']:,.0f} m³/h ; plafond 90 % "
                    f"→ capacité minimale requise = {ga['cap_min_installee']:,.0f} m³/h.")
                lines.append(
                    f"Cumul admission installé = {adm['total']:,.0f} m³/h "
                    f"(ventouses {adm['trifon']:,.0f} + clapets {adm['ceai']:,.0f} "
                    f"+ purgeurs {adm['psa']:,.0f}) ≥ {ga['besoin_majore']:,.0f} m³/h "
                    f"→ {'CONFORME' if ga['conforme'] else 'NON CONFORME'} "
                    f"(manque {ga.get('manque', 0):,.0f} m³/h).")
                lines.append(
                    f"Vitesse air : vanne {vt['vanne']:,.1f} m/s ; aval "
                    f"{vt['aval']:,.1f} m/s (limite 40 m/s) → "
                    f"{'OK' if vt['ok'] else 'INSUFFISANT'}.")
                if ga.get("purgeur_sonique"):
                    lines.append(
                        f"Purgeur sonique (débit sonique) : "
                        f"{ga['purgeur_sonique']:,.0f} m³/h.")
            else:
                cum = self.cumul_debits()
                adm = cum["admission"]; vn = cum["vanne"]; vt = cum["limite_vitesse"]
                lines.append(
                    f"Besoin casse franche Q_eau (Torricelli) = "
                    f"{cum['besoin_casse']:,.0f} m³/h (H_z = {cum['hz']:,.1f} m).")
                lines.append(
                    f"Cumul admission installé = {adm['total']:,.0f} m³/h "
                    f"(ventouses {adm['trifon']:,.0f} + clapets {adm['ceai']:,.0f} "
                    f"+ purgeurs {adm['psa']:,.0f}) ≥ {cum['besoin_casse']:,.0f} m³/h "
                    f"→ {'CONFORME' if cum['verdict_admission'] else 'NON CONFORME'}.")
                if vn["section_vanne"] > 0:
                    lines.append(
                        f"Vanne DN {vn['dn']:,.0f} : rapport vanne/Σ amont = "
                        f"{vn['ratio']:.2f} → "
                        f"{'sans étranglement' if vn['conforme'] else 'ÉTRANGLEMENT'}.")
                v_str = f"{vt['v_air']:,.1f} m/s" if vt['v_air'] < 1e6 else "n.c."
                lines.append(
                    f"Vitesse air à la vanne : {v_str} (limite {vt['v_limite']:,.0f} m/s) "
                    f"→ {'OK' if vt['ok'] else 'INSUFFISANT'}.")
            return lines
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Proposition client vs. dimensionnement retenu (tableau comparatif)
    # ------------------------------------------------------------------
    def proposition_client_justifiee(self) -> dict:
        """Génère les données des tableaux « Proposition client » et « Groupe retenu ».

        Le 1ᵉʳ tableau liste chaque organe proposé par le client avec une
        cellule « Justification » détaillant la non-conformité éventuelle,
        en s'appuyant sur les verdicts de `verifier_organes()` (cohérence avec
        l'onglet Vérification). Le 2ᵉ tableau montre le groupe finalement retenu
        (conservé si conforme, sinon le groupe optimisé de `groupe_optimise()`).

        Retour :
        {
          "proposition": [{rep, categorie, dn, nombre, fournisseur, position,
                           conforme, justification}],
          "retenu":      [{rep, categorie, dn, nombre, fournisseur, position, role}],
          "client_conforme": bool,
          "verdict_global": str,
        }
        """
        if self.resultat is None or self.derniere_trace is None:
            self.calculer()

        # Verdicts détaillés (mêmes règles que l'onglet Vérification)
        verdicts = self.verifier_organes()

        cat_labels_sih = {
            "trifon": "Ventouse TRIFON",
            "ceai": "Clapet admission SNH",
            "psa": "Purgeur sonique SNH",
            "vanne": "Vanne sectionnement",
        }
        cap_org = capacite_organe

        # --- Tableau 1 : proposition client ---
        # La justification détaille, par organe, la capacité installée et le
        # contrôle applicable (même libellé que verifier_organes()).
        proposition = []
        for o in self.organes_client:
            typ = o.get("type", "")
            cap = cap_org(o, -3)
            lib = self._libelle_categorie(typ)
            cap_txt = f"{cap:,.0f} m³/h" if cap else "n.c."
            if typ in ("trifon", "ceai"):
                v = next((x for x in verdicts if x["categorie"] == lib), None)
                conforme = v["conforme"] if v else False
                if not conforme:
                    j = (f"{o['nombre']}×DN{o.get('dn')} — {cap_txt} ; "
                         f"catégorie « {lib} » : {v['message']}." if v
                         else "Non conforme.")
                else:
                    j = f"Proposition conforme — conservée (catégorie : {v['message']})."
            elif typ == "psa":
                v = next((x for x in verdicts if x["categorie"] == lib), None)
                conforme = v["conforme"] if v else False
                j = (f"{o['nombre']}×DN{o.get('dn')} — {cap_txt} ; "
                     f"catégorie « {lib} » : {v['message']}." if v and not conforme
                     else "Proposition conforme — conservée.")
            elif typ == "vanne":
                conforme = bool(self.dn_vanne_sectionnement)
                j = ("Vanne de sectionnement conforme."
                     if conforme else "Vanne de sectionnement non renseignée.")
            else:
                conforme = False
                j = "Type inconnu."

            proposition.append({
                "rep": "",
                "categorie": lib,
                "dn": o.get("dn"),
                "nombre": o.get("nombre", 1),
                "fournisseur": o.get("fournisseur", ""),
                "position": o.get("position", "") or "—",
                "conforme": conforme,
                "capacite_m3h": cap,
                "justification": j,
            })
        for i, p in enumerate(proposition):
            p["rep"] = f"{i + 1:02d}"

        # Conformité au 1ᵉʳ tour = Fs SANS majoration (casse franche) : chaque
        # organe d'air couvre son point avec Fs ≥ 1,00 (cf. tableau de
        # vérification). Le contrôleur juge la valeur du Fs dans ses écrits.
        client_conforme = True
        try:
            client_conforme = all(
                r["verdict"] == "Conforme"
                for r in self.tableau_verification_organes())
        except Exception:
            client_conforme = all(v["conforme"] for v in verdicts)

        # --- Tableau 2 : groupe retenu ---
        if client_conforme:
            retenu = []
            for i, o in enumerate(self.organes_client):
                typ = o.get("type", "")
                cap = cap_org(o, -3)
                role = (f"Capacité {cap:,.0f} m³/h"
                        if typ in ("trifon", "ceai", "psa") and cap
                        else "Vanne de sectionnement" if typ == "vanne"
                        else "")
                retenu.append({
                    "rep": f"{i + 1:02d}",
                    "categorie": cat_labels_sih.get(typ, typ),
                    "dn": o.get("dn"),
                    "nombre": o.get("nombre", 1),
                    "fournisseur": o.get("fournisseur", "") or "—",
                    "position": o.get("position", "") or "—",
                    "role": role,
                })
            # --- Analyse Fs (SANS majoration) : base transparente pour le
            # contrôleur — il juge la valeur des Fs dans ses écrits ---
            fs_lignes = []
            try:
                for r in self.tableau_verification_organes():
                    if r["fs"] is not None:
                        fs_lignes.append(
                            f"{r['repere']} — {r['categorie']} : capacité "
                            f"{r['capacite_m3h']:,.1f} m³/h vs demande "
                            f"{r['demande_m3h']:,.1f} m³/h → Fs = {r['fs']:.2f}.")
            except Exception:
                fs_lignes = []
            _res = self.resultat
            q_p = [(l, v) for l, v in (
                ("Q_Ve", _res.q_ve_m3h or 0.0),
                ("Q_PI1", _res.q_pi1_m3h or 0.0),
                ("Q_PI2", _res.q_pi2_m3h or 0.0)) if v > 0]
            troncon_total = sum(v for _, v in q_p)
            besoin_txt = " + ".join(f"{l} {v:,.1f}" for l, v in q_p) or "0"
            bloc = "\n".join("  • " + d for d in fs_lignes)
            verdict = (
                f"Proposition client CONFORME — groupe conservé tel quel "
                f"(débits MK_A.A 2026, vérification SANS majoration). "
                f"Besoin réel du tronçon : {troncon_total:,.1f} m³/h "
                f"({besoin_txt} — casse franche)."
                + ("\n" + bloc if bloc else ""))
        else:
            opt = self.groupe_optimise()
            retenu = []
            for i, o in enumerate(opt["groupe"]):
                typ = o.get("type", "")
                cap = (opt["capacites"].get("ventouse", 0) if typ == "trifon"
                       else opt["capacites"].get("clapet_snh", 0) if typ == "ceai"
                       else opt["capacites"].get("purgeur_snh", 0) if typ == "psa"
                       else None)
                role = (f"Capacité {cap:,.0f} m³/h" if cap
                        else "Vanne de sectionnement" if typ == "vanne"
                        else "")
                retenu.append({
                    "rep": f"{i + 1:02d}",
                    "categorie": cat_labels_sih.get(typ, typ),
                    "dn": o.get("dn"),
                    "nombre": o.get("nombre", 1),
                    "fournisseur": o.get("fournisseur", "") or "—",
                    "position": o.get("position", "") or "—",
                    "role": role,
                })
            verdict = ("Proposition client NON CONFORME — "
                       f"groupe optimisé retenu (couverture "
                       f"{opt['coverage']:,.0f} m³/h ≥ besoin "
                       f"{opt['besoin']:,.0f} m³/h, vérifié sans majoration).")

        return {
            "proposition": proposition,
            "retenu": retenu,
            "client_conforme": client_conforme,
            "verdict_global": verdict,
        }

    # ------------------------------------------------------------------
    # Vérification de flambement (collapse) — résistance au vide
    # ------------------------------------------------------------------
    def verifier_flambement(self) -> dict:
        """Vérifie que la dépression maximale admissible reste inférieure
        à la marge de sécurité de résistance structurelle du tube.

        Critère simple (AWWA M11 / NF EN 1295-1) :
            ΔH_max < 50 % × P_nominale (bar) convertie en mCE

        Si P_nominale n'est pas renseignée, on utilise une valeur par défaut
        de 10 bar (classe PN10, courant pour les conduites AEP grand DN).

        Retour : dict avec keys delta_h_max, p_nominale_bar,
                 p_collapse_mce, conforme, message, reference.
        """
        # Dépression maximale du calcul (3 mCE nominale selon NF EN 805)
        delta_h_max = SEUIL_DEPRESSION

        # Pression nominale du tube — défaut 10 bar si non renseignée
        p_nom_bar = self.pression_nominale or 10.0
        # Conversion bar → mCE : 1 bar ≈ 10,197 mCE ≈ 10,2 mCE
        p_collapse_mce = p_nom_bar * 10.197
        # Marge de sécurité 50% (AWWA M11 / facteur 2 sur la pression critique)
        marge = p_collapse_mce * 0.50
        conforme = delta_h_max < marge

        if conforme:
            msg = (f"ΔH_max = {delta_h_max:.2f} mCE < 50% × P_nom "
                   f"= {marge:.1f} mCE → CONFORME (pas de risque de flambement).")
        else:
            msg = (f"ΔH_max = {delta_h_max:.2f} mCE ≥ 50% × P_nom "
                   f"= {marge:.1f} mCE → NON CONFORME — vérifier la tenue "
                   "structurelle du tube sous dépression (AWWA C200/M11 Ch.6).")

        return {
            "delta_h_max": delta_h_max,
            "p_nominale_bar": p_nom_bar,
            "p_collapse_mce": round(p_collapse_mce, 1),
            "marge_mce": round(marge, 1),
            "conforme": conforme,
            "message": msg,
            "reference": "AWWA M11 Ch.6 / NF EN 1295-1 (vérification simplifiée)",
        }

    # ------------------------------------------------------------------
    # Perte de charge locale — passage d'air à travers la vanne
    # ------------------------------------------------------------------
    def perte_charge_vanne(self) -> dict:
        """Calcule la perte de charge locale à la vanne de sectionnement.

        Formule : Δp = K × ρ_air × V² / 2

        K = 0,2 à 0,5 (vanne papillon ouverte) ; K = 2 à 5 (vanne partially
        fermée / source d'étranglement).
        ρ_air = 1,225 kg/m³ (air à 15 °C, 1 atm)
        V = vitesse d'air dans le collet (section vanne ou section amont si
        plus étroite).

        Retour : dict avec keys k, rho, v_collet, delta_p_pa, delta_p_mce,
                 vitesse_limite, message.
        """
        try:
            cum = self.cumul_debits()
            vt = cum["limite_vitesse"]
            vn = cum["vanne"]
        except Exception:
            return {"message": "Données insuffisantes pour le calcul de perte de charge."}

        v_vanne = vt.get("v_air", 0.0)
        v_aval = vt.get("v_aval", 0.0)

        # Section collet = section vanne si elle existe, sinon section amont
        s_collet = vn.get("section_vanne", 0.0) or vn.get("section_amont", 0.0)

        # Coefficient de perte selon la configuration
        # Vanne papillon pleine ouverture : K ≈ 0,2 — vanne partiellement fermée : K ≈ 2,5
        k_vanne = 0.3 if vn.get("conforme") else 2.5

        rho_air = 1.225  # kg/m³ à 15 °C

        # Vitesse de référence dans le collet (section la plus étroite côté amont)
        v_collet = v_vanne  # m/s (calculé dans cumul_debits)

        # Perte de charge en Pa : Δp = K × ρ × V² / 2
        delta_p_pa = k_vanne * rho_air * v_collet ** 2 / 2.0
        # Conversion en mCE d'air : Δp (Pa) / (ρ_eau × g) ≈ Δp / 9810
        # Mais c'est la perte de charge d'AIR — on la exprime en mmCE d'air
        # ou directement en Pa (plus pertinent pour l'aéraulique)
        # En mCE d'eau équivalente : très faible, on reste en Pa
        delta_p_mce_air = delta_p_pa / (rho_air * 9.81)  # en m d'air
        delta_p_mmceau = delta_p_pa / 9810.0 * 1000  # en mmCE d'eau

        # Vérification vitesse limite (anti sonique, ISO 6358-1)
        v_limite = 40.0  # m/s

        if v_collet <= v_limite:
            msg = (f"V_collet = {v_collet:.1f} m/s ≤ {v_limite:.0f} m/s (anti blocage "
                   f"sonique, ISO 6358-1) → OK. "
                   f"Δp_vanne = {delta_p_pa:.1f} Pa ({delta_p_mmceau:.2f} mmCE eau) "
                   f"— négligeable devant la dépression de {SEUIL_DEPRESSION:.1f} mCE.")
        else:
            msg = (f"V_collet = {v_collet:.1f} m/s > {v_limite:.0f} m/s → "
                   "RÉGIME SONIQUE — l'air est bloqué, débit réel inférieur au calcul. "
                   f"Δp_vanne = {delta_p_pa:.1f} Pa — NON CONFORME.")

        return {
            "k": k_vanne,
            "rho_air": rho_air,
            "v_collet": round(v_collet, 1),
            "v_aval": round(v_aval, 1),
            "delta_p_pa": round(delta_p_pa, 1),
            "delta_p_mmceau": round(delta_p_mmceau, 2),
            "vitesse_limite": v_limite,
            "conforme": v_collet <= v_limite,
            "message": msg,
            "reference": "ISO 6358-1 / pertes locales Δp = K·ρ·V²/2",
        }

    # ------------------------------------------------------------------
    # Références normatives complètes (pour la note)
    # ------------------------------------------------------------------
    def references_completes(self) -> list:
        """Renvoie la liste complète des références normatives y compris
        celles du document d'orientation (AWWA, DVGW, ISO, BS).
        """
        from .core.constants import REFERENCES_NORMATIVES
        ajouts = [
            "AWWA M11 — Steel Pipe — A Guide for Design and Installation "
            "(Ch.6 : External Pressure, calcul de collapse)",
            "AWWA M9 — Concrete Pressure Pipe (dimensionnement et protection vide)",
            "AWWA C200 — Steel Water Pipe (pression externe / vide)",
            "DVGW W 312 — Dimensionnement des adducteurs (Allemagne)",
            "DVGW W 392 — Sélection des organes d'admission/échappement d'air",
            "ISO 6358-1 — Fluides compressibles — caractéristiques de débit "
            "(blocage sonique, rapport de pression critique)",
            "ISO 5167 — Mesure de débit par différence de pression "
            "(coefficients de décharge, pertes de charge)",
            "NF EN 1295-1 — Canalisations enterrées — résistance mécanique "
            "(rigidité annulaire, tenue à la dépression interne)",
            "BS 5500 / ISO 16770 — Structures cylindriques sous dépression uniforme",
            "NF EN 593 — Vannes à papillon métalliques (vanne principale DN 1600)",
            "NF EN 1171 — Vannes à opercule en fonte (vanne isolement DN 200/250)",
            "Fascicule 71 (CCTG Travaux Publics) — Implantation des organes "
            "de vidange et de protection d'air aux points hauts/bas",
        ]
        return list(REFERENCES_NORMATIVES) + ajouts

    # ------------------------------------------------------------------
    # Tableau récapitulatif des entrées utilisateur
    # ------------------------------------------------------------------
    def tableau_entrees(self) -> dict:
        """Retourne un dict structuré de toutes les entrées projet pour
        affichage dans le rapport (tableau récapitulatif, §1 de la note).
        """
        organes = []
        for o in (self.organes_client or []):
            if o.get("type") == "vanne":
                continue  # la vanne est gérée séparément (dn_vanne_sectionnement)
            organes.append({
                "type": {"trifon": "Ventouse", "ceai": "Clapet",
                         "psa": "Purgeur"}.get(o.get("type"), o.get("type")),
                "dn": o.get("dn"),
                "nombre": o.get("nombre"),
                "fournisseur": (o.get("fournisseur") or "—"),
                "position": (o.get("position") or "—"),
            })
        try:
            dc = self.dc()
        except Exception:
            dc = None
        try:
            nu = viscosity.corriger_nu(self.temperature)
        except Exception:
            nu = None
        lib_dist = {
            "a": "Distance a (Vi1→PI1)",
            "b": "Distance b (PI1→Ve)",
            "c": "Distance c (Ve→PI2)",
            "d": "Distance d (PI2→Vi2)",
            "l1": "Distance L1 (Vi1→Ve)",
            "l2": "Distance L2 (Ve→Vi2)",
        }
        distances = [(lib_dist[k], getattr(self, k, 0.0), "m")
                     for k in DISTANCES_PAR_CAS.get(self.schema, ["l1", "l2"])]
        return {
            "moe": self.moe or "—",
            "projet": self.projet or "—",
            "reference": self.reference or "—",
            "branches": self.branches or "—",
            "dn_mm": self.dn_mm,
            "d_m": dc.d if dc else None,
            "section_m2": dc.section if dc else None,
            "kd": dc.kd if dc else None,
            "k_m": 0.0005,
            "schema": self.schema,
            "z_ve": self.z_ve,
            "z_vi1": self.z_vi1,
            "z_vi2": self.z_vi2,
            "l1": self.l1,
            "l2": self.l2,
            "distances": distances,
            "hz_casse_franche": self.hz_casse_franche,
            "dn_vanne": self.dn_vanne_sectionnement,
            "pression_nominale": self.pression_nominale,
            "temperature": self.temperature,
            "nu": nu,
            "delta_h": SEUIL_DEPRESSION,
            "organes": organes,
        }

    # ------------------------------------------------------------------
    # Groupe optimisé en cas de NON-CONFORMITÉ (ventouses TRIFON + SNH)
    # ------------------------------------------------------------------
    def groupe_optimise(self) -> dict:
        """Propose le groupe d'organes optimal pour couvrir le besoin casse franche.

        Base : ventouses TRIFON (organe de référence Tier-1) + équipements SNH
        (clapets d'admission + purgeurs soniques de dégazage), extraits de
        valve_database.json. La vanne de sectionnement n'appartient à aucun
        fournisseur précis (composant neutre).

        Retour : {besoin, manque, groupe, coverage, conforme, note}.
        """
        r = self.cumul_debits()
        besoin = r["besoin_casse"]
        admis_ex = r["admission"]["total"]
        manque = max(0.0, besoin - admis_ex)

        from .data import valve_db as db
        from .data.catalogues import TRIFON
        from .core import dimensionnement as dim

        # Le groupe proposé remplace entièrement les organes client → il doit
        # couvrir le BESOIN complet (pas seulement le manque d'admission).
        besoin_group = besoin
        # Petites parts admises par les ventouses TRIFON (grande & petite orifice)
        trifon_dns = sorted(TRIFON.keys())
        trifon_max = TRIFON[trifon_dns[-1]]["q"][-3]
        part_ventouse = min(besoin_group, trifon_max)

        # --- Ventouse TRIFON : part amont (petites sections → ratio>1) ---
        # La ventouse TRIFON (grand orifice) assure aussi l'évacuation au
        # remplissage ; on la place en amont de la vanne.
        sel_ventouse = dim.choisir_ventouse(part_ventouse, marge_pct=0.0)

        # --- Clapets d'admission SNH ---
        snh_clap = db.table_capacite("SNH", "clapet")
        snh_purge = db.table_capacite("SNH", "purgeur")

        # Vanne recommandée = DN de la conduite principale (maximum physique).
        dn_vanne_opt = int(self.dn_mm)
        s_vanne_opt = math.pi * (dn_vanne_opt / 1000.0) ** 2 / 4.0
        cap_passage_40 = 40.0 * s_vanne_opt * 3600.0

        # Répartition AMONT / AVAL :
        #   - AMONT : l'air transite par la vanne → plafonné à la capacité de
        #     passage à 40 m/s (cap_passage_40) pour éviter le blocage sonique.
        #   - AVAL  : l'air entre directement en aval de la vanne (bypass
        #     conduite) → couvre le surplus sans solliciter la vanne.
        amont_cible = min(besoin_group, cap_passage_40)
        aval_cible = max(0.0, besoin_group - amont_cible)

        # Sélection des clapets SNH (DN400, le plus fort débit) en parallèle.
        # L'amont est CALCULÉ pour rester sous la limite : on borne nb_am.
        nb_am = 0
        nb_av = 0
        q_clap = 0.0
        dn_clap = None
        cap_clapet = 0.0
        restrict = []
        if snh_clap:
            dn_clap = max(snh_clap)
            q_clap = snh_clap[dn_clap]
            sec_app = math.pi * (dn_clap / 1000.0) ** 2 / 4.0
            cap_ventouse_sel = sel_ventouse.capacite_installee_m3h
            # Amont : remplir jusqu'à la limite (marge 1 %) sans la dépasser
            amont_room = cap_passage_40 * 0.99 - cap_ventouse_sel
            if amont_room > 1e-9:
                nb_am = int(amont_room / q_clap)
            # Aval : couvre le reste du besoin
            aval_cible = max(0.0, besoin_group - cap_ventouse_sel - nb_am * q_clap)
            if aval_cible > 0:
                nb_av = math.ceil(aval_cible / q_clap)
            # Vérification des sections vs la vanne / la conduite (ratio > 1)
            sec_am = nb_am * sec_app
            sec_av = nb_av * sec_app
            if sec_am + 1e-9 > s_vanne_opt:
                restrict.append(f"Sections amont {sec_am:.2f} m² ≥ vanne {s_vanne_opt:.2f} m²")
            if sec_av + 1e-9 > s_vanne_opt:
                restrict.append(f"Sections aval {sec_av:.2f} m² ≥ conduite {s_vanne_opt:.2f} m²")
            cap_clapet = (nb_am + nb_av) * q_clap

        # --- Purgeur sonique SNH (NSH) : dégazage / évacuation contrôlée ---
        q_remplissage_m3h = dim.q_remplissage(2.0, r.get("dc")) if r.get("dc") else 0.0
        nb_pur = 0
        dn_pur = None
        q_pur = 0.0
        cap_purgeur = 0.0
        if snh_purge and q_remplissage_m3h > 0:
            dns_max = max(snh_purge)
            p_nsh = next((x for x in (db.fournisseur("SNH").get("purgeurs") or [])
                          if x["dn"] == dns_max), None)
            if p_nsh is not None:
                dn_pur = p_nsh["dn"]
                q_pur = dim._cap_sonique_snh(_cap_purgeur_pn("SNH", p_nsh["dn"], _PN_COURANT), _PN_COURANT)
                nb_pur = 1
                cap_purgeur = q_pur

        cap_ventouse = sel_ventouse.capacite_installee_m3h
        coverage = cap_ventouse + cap_clapet + cap_purgeur

        # Débits RÉELS retenus par position (tels qu'appliqués dans le groupe)
        amont_reel = cap_ventouse + nb_am * q_clap
        aval_reel = nb_av * q_clap

        groupe = []
        if sel_ventouse.nombre > 0:
            groupe.append({"type": "trifon", "dn": sel_ventouse.dn,
                           "nombre": sel_ventouse.nombre, "position": "amont"})
        if nb_am > 0:
            groupe.append({"type": "ceai", "dn": dn_clap, "nombre": nb_am,
                           "fournisseur": "SNH", "position": "amont"})
        if nb_av > 0:
            groupe.append({"type": "ceai", "dn": dn_clap, "nombre": nb_av,
                           "fournisseur": "SNH", "position": "aval"})
        if nb_pur > 0:
            groupe.append({"type": "psa", "dn": dn_pur, "nombre": nb_pur,
                           "fournisseur": "SNH", "position": "amont"})
        # Vanne de sectionnement recommandée : DN principal (neutre).
        groupe.append({"type": "vanne", "dn": dn_vanne_opt, "nombre": 1})

        # Conformité globale du montage proposé (répartition amont/aval)
        amont_charge = min(amont_reel, amont_cible)  # transit effectif à la vanne
        v_vanne = amont_reel / s_vanne_opt / 3600.0 if s_vanne_opt > 0 else float("inf")
        v_dn = aval_reel / s_vanne_opt / 3600.0 if s_vanne_opt > 0 else float("inf")
        conforme = (coverage >= besoin_group - 1e-9 and v_vanne <= 40.0
                    and v_dn <= 40.0 and not restrict)

        note = ("Vanne de sectionnement recommandée = DN de la conduite "
                f"principale (DN{dn_vanne_opt} — composant neutre, fournisseur "
                "indépendant). ")
        if aval_reel > 1e-9:
            note += (f"Admission répartie : amont {amont_reel:,.0f} m³/h (transite "
                     f"par la vanne, limite 40 m/s) + aval {aval_reel:,.0f} m³/h "
                     "(entrée directe en aval, bypass de la vanne).")
        else:
            note += (f"Admission entièrement en amont : {amont_reel:,.0f} m³/h ≤ "
                     f"capacité de passage à 40 m/s ({cap_passage_40:,.0f} m³/h).")
        if nb_pur > 0:
            note += (" Purgeur sonique SNH : dégazage contrôlé (Q_fill ≈ q_cap·"
                     "P_fill/P_svc, faible) ; l'évacuation massive au remplissage "
                     "revient au grand orifice des ventouses TRIFON.")

        return {
            "besoin": besoin,
            "admis_existant": admis_ex,
            "manque": manque,
            "groupe": groupe,
            "coverage": coverage,
            "capacites": {"ventouse": cap_ventouse, "clapet_snh": cap_clapet,
                          "purgeur_snh": cap_purgeur,
                          "amont": amont_reel, "aval": aval_reel,
                          "passage_40": cap_passage_40},
            "vanne_dn": dn_vanne_opt,
            "v_vanne": v_vanne, "v_dn": v_dn,
            "repartition": {"amont": amont_reel, "aval": aval_reel,
                            "kap": cap_passage_40},
            "conforme": conforme,
            "note": note,
        }

    def corriger_variante_client(self) -> dict:
        """Corrige la variante DÉJÀ COMMANDÉE du client en CONSERVANT les
        diamètres commandés et en ADAPTANT LE NOMBRE d'organes.

        Contraintes :
          - On garde les DN et le fournisseur des organes commandés (variante
            déjà commandée : pas de ré-achat à d'autres diamètres).
          - On augmente le nombre de ventouses puis de clapets jusqu'à couvrir
            le besoin casse franche.
          - L'amont (transite par la vanne) est plafonné à la capacité de
            passage à 40 m/s ; le surplus est admis par un POINT INTERMÉDIAIRE
            GÉNÉRIQUE EN AVAL (bypass élargi) — c'est la « réserve » qui
            débloque la capacité sans solliciter la vanne au-delà de 40 m/s.
          - Le purgeur sonique reste tel que commandé (dégazage, débit
            d'admission négligeable).
          - Vanne de sectionnement = DN de la conduite (composant neutre).

        Retour : {besoin, manque, groupe, coverage, conforme, note,
                  repartition:{amont,aval,kap}, dns_conserves:bool}
        """
        r = self.cumul_debits()
        besoin = r["besoin_casse"]
        admis_ex = r["admission"]["total"]
        manque = max(0.0, besoin - admis_ex)

        # --- Chauffe sur les diamètres COMMANDÉS ---
        ve_ordre = next((o for o in self.organes_client if o.get("type") == "trifon"), None)
        cl_ordre = next((o for o in self.organes_client if o.get("type") == "ceai"), None)
        pu_ordre = next((o for o in self.organes_client if o.get("type") == "psa"), None)
        four = (ve_ordre or cl_ordre or {}).get("fournisseur", "") or "SNH"

        # Capacité UNITAIRE de chaque organe commandé, calculée par la MÊME
        # fonction que la vérification (capacite_organe) — indispensable pour
        # rester cohérent avec le cumul (sinon « corrigé conforme » ne le serait
        # pas vraiment une fois appliqué). On copie l'organe commandé avec
        # nombre=1 pour obtenir le débit d'une unité.
        def _cap_unit(o):
            if not o:
                return 0.0
            unit = dict(o)
            unit["nombre"] = 1
            return capacite_organe(unit, -3)

        dn_ve = (ve_ordre or {}).get("dn")
        q_ve = _cap_unit(ve_ordre)
        dn_cl = (cl_ordre or {}).get("dn")
        q_cl = _cap_unit(cl_ordre)
        dn_pu = (pu_ordre or {}).get("dn")
        q_pu = _cap_unit(pu_ordre) if pu_ordre and pu_ordre.get("type") == "psa" else 0.0

        dn_vanne = int(self.dn_mm)
        s_vanne = math.pi * (dn_vanne / 1000.0) ** 2 / 4.0
        cap_passage_40 = 40.0 * s_vanne * 3600.0

        # Nombre de ventouses : on CONSERVE le commandé (les ventouses amont
        # transitent par la vanne, elles ne servent pas de levier ici — la
        # capacité vient des clapets).
        nb_ve = max(ve_ordre.get("nombre", 0), 0) if ve_ordre else 0
        cup_ve = nb_ve * q_ve

        # Capacité restante à couvrir par les clapets (même DN commandé)
        restant = max(0.0, besoin - cup_ve - q_pu)

        # Répartition clapets : AMONT tant que la vanne n'est pas saturée,
        # puis les clapets restants en AVAL = POINT INTERMÉDIAIRE GÉNÉRIQUE
        # (bypass élargi) qui ne sollicite pas la vanne.
        restant_am = max(0.0, cap_passage_40 - cup_ve)
        nb_am = 0
        nb_av = 0
        if q_cl > 0 and restant > 0:
            max_am = int(restant_am / q_cl) if restant_am > 0 else 0
            nb_am = min(max_am, int(math.ceil(restant / q_cl)))
            couvert_am = nb_am * q_cl
            restant_av = max(0.0, restant - couvert_am)
            if restant_av > 0:
                nb_av = math.ceil(restant_av / q_cl)

        # --- Couverture ---
        cap_ve = cup_ve
        cap_cl = (nb_am + nb_av) * q_cl
        cap_pu = q_pu
        coverage = cap_ve + cap_cl + cap_pu
        amont_reel = cap_ve + nb_am * q_cl
        aval_reel = nb_av * q_cl + cap_pu

        v_vanne = amont_reel / s_vanne / 3600.0 if s_vanne > 0 else float("inf")
        v_aval = aval_reel / s_vanne / 3600.0 if s_vanne > 0 else float("inf")

        groupe = []
        if nb_ve > 0:
            groupe.append({"type": "trifon", "dn": dn_ve, "nombre": nb_ve,
                           "fournisseur": four, "position": "amont"})
        if nb_am > 0:
            groupe.append({"type": "ceai", "dn": dn_cl, "nombre": nb_am,
                           "fournisseur": four, "position": "amont"})
        if nb_av > 0:
            groupe.append({"type": "ceai", "dn": dn_cl, "nombre": nb_av,
                           "fournisseur": four, "position": "aval"})
        if pu_ordre and pu_ordre.get("nombre", 0) > 0:
            groupe.append({"type": "psa", "dn": dn_pu, "nombre": pu_ordre["nombre"],
                           "fournisseur": four, "position": pu_ordre.get("position", "amont")})
        groupe.append({"type": "vanne", "dn": dn_vanne, "nombre": 1})

        conforme = (coverage >= besoin - 1e-9 and v_vanne <= 40.0
                    and v_aval <= 40.0)

        note = ("Variante DÉJÀ COMMANDÉE — diamètres commandés CONSERVÉS "
                f"({dn_ve and 'VE DN'+str(dn_ve)+' ' or ''}"
                f"{dn_cl and 'clapet DN'+str(dn_cl)+' ' or ''}"
                f"{dn_pu and 'purgeur DN'+str(dn_pu) or ''}). ")
        note += ("Nombre d'organes AUGMENTÉ pour couvrir le besoin casse "
                 "franche. ")
        if nb_av > 0:
            note += (f"Admission répartie : amont {amont_reel:,.0f} m³/h (transite "
                     f"par la vanne ≤ {cap_passage_40:,.0f} m³/h @40 m/s) + POINT "
                     f"INTERMÉDIAIRE AVAL/bypass élargi {aval_reel:,.0f} m³/h "
                     "(entrée directe en aval, ne sollicite pas la vanne).")
        else:
            note += (f"Admission entièrement en amont : {amont_reel:,.0f} m³/h "
                     f"≤ {cap_passage_40:,.0f} m³/h @40 m/s.")
        note += (f" Couverture totale {coverage:,.0f} m³/h ≥ besoin "
                 f"{besoin:,.0f} m³/h → "
                 f"{'CONFORME' if conforme else 'encore insuffisant'} "
                 f"(vitesse vanne {v_vanne:.1f} m/s ≤ 40, aval {v_aval:.1f} m/s ≤ 40).")

        return {
            "besoin": besoin,
            "manque": manque,
            "groupe": groupe,
            "coverage": coverage,
            "capacites": {"ventouse": cap_ve, "clapet_snh": cap_cl,
                          "purgeur_snh": cap_pu, "amont": amont_reel,
                          "aval": aval_reel, "passage_40": cap_passage_40},
            "repartition": {"amont": amont_reel, "aval": aval_reel,
                            "kap": cap_passage_40},
            "v_vanne": v_vanne, "v_aval": v_aval,
            "vanne_dn": dn_vanne,
            "dns_conserves": True,
            "conforme": conforme,
            "note": note,
        }

    def catalogue_verification(self) -> list:
        """Catalogue des équipements pour vérification — par fournisseur et rôle.

        Liste les DNs avec capacité d'air admise (m³/h à la dépression nominale)
        pour chaque fournisseur/rôle pertinent, et signale les DNs réellement
        retenus (proposition client, groupe optimisé, variante corrigée).

        TRIFON (ventouses) et CEAI (clapets) sont présentés en entrées
        distinctes pour faciliter la vérification des variantes.

        Retour : liste de dict :
            {nom, role, role_lib, statut, origine, items:[{dn,q_capacity,retenu,nombre}]}
        """
        from .data import valve_db as db

        retenus = {}

        def _ajout_org(o):
            typ = o.get("type", "")
            role = {"trifon": "ventouse", "ceai": "clapet",
                    "psa": "purgeur"}.get(typ)
            if not role:
                return
            four = (o.get("fournisseur", "") or "").strip()
            full = (four or "").upper()
            if full in ("TRIFON", "CEAI"):
                four = full
            elif not four:
                four = "TRIFON" if role == "ventouse" else "CEAI"
            dn = o.get("dn")
            nb = max(o.get("nombre", 0), 1)
            if dn:
                key = (four, role, dn)
                retenus[key] = retenus.get(key, 0) + nb

        for o in self.organes_client:
            _ajout_org(o)
        if self.resultat is not None:
            try:
                for o in self.groupe_optimise().get("groupe", []):
                    _ajout_org(o)
            except Exception:
                pass
            try:
                for o in self.corriger_variante_client().get("groupe", []):
                    _ajout_org(o)
            except Exception:
                pass

        invites = ["TRIFON", "CEAI", "SNH"]
        acts = {f for (f, _r, _d) in retenus}
        ordre_set = set(invites) | acts
        premiers = [n for n in ("TRIFON", "CEAI", "SNH") if n in ordre_set]
        autres = sorted(n for n in ordre_set if n not in premiers)
        ordre = premiers + autres

        role_lib_map = {"ventouse": "Ventouse",
                        "clapet": "Clapet d'admission d'air",
                        "purgeur": "Purgeur sonique"}
        # Rôles à afficher PAR fournisseur (TRIFON/CEAI séparés en entrées
        # distinctes ; clé JSON lue pour chaque rôle).
        def _roles_affichables(nom):
            if nom == "TRIFON":
                return [("ventouse", "ventouses")]
            if nom == "CEAI":
                return [("clapet", "ventouses")]
            if nom == "SNH":
                return [("clapet", "clapets"), ("purgeur", "purgeurs")]
            if nom == "PSA":
                return []
            return [("ventouse", "ventouses")]

        sections = []
        for four in ordre:
            entree = db.fournisseur(four)
            if not entree:
                continue
            for role, cle_json in _roles_affichables(four):
                items_json = entree.get(cle_json) or (
                    entree.get("ventouses") if role == "clapet" else [])
                if not items_json:
                    continue
                table = {int(it["dn"]): float(it.get("q_capacity", 0.0))
                         for it in items_json
                         if it.get("dn") and it.get("q_capacity") is not None}
                if not table:
                    continue
                lignes = []
                for dn in sorted(table):
                    # Purgeurs : capacité INSTALLÉE à la classe PN du projet
                    # (ex. SNH DN1500@PN16 = 144 m³/h vs 180 à PN10).
                    cap_unitaire = (table[dn] if role != "purgeur"
                                    else _cap_purgeur_pn(four, dn, _PN_COURANT))
                    lignes.append({
                        "dn": dn,
                        "q_capacity": cap_unitaire,
                        "retenu": (four, role, dn) in retenus,
                        "nombre": retenus.get((four, role, dn), 0),
                    })
                sections.append({
                    "nom": four,
                    "role": role,
                    "role_lib": role_lib_map.get(role, role),
                    "statut": entree.get("statut", ""),
                    "origine": entree.get("origine", ""),
                    "items": lignes,
                })
        return sections
