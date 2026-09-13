# -*- coding: utf-8 -*-
"""Basse externe des vannes (valve_database.json) — données modifiables sans recompiler.

Le fichier JSON est recherché (dans cet ordre) :
  1. dossier de l'exécutable (mode PYINSTALLER_FROZEN),
  2. au chemin explicitement fourni par la variable VALVE_DATABASE_PATH,
  3. à la racine du projet (dossier contenant book).

S'il est absent, on retombe sur un catalogue interne (TRIFON/CEAI/PSA)
identique à la méthode fixe du README (socle inchangé).

Expositions principales (compatibles avec la structure historique catalogues.py) :
  TRIFON, CEAI, PSA, DEPRESSION_NOMINALE  -> utilisés par le moteur de calcul.
  FOURNISSEURS                            -> base complète (kit UI/exports).
  source / chemins_essayes                -> où le JSON a été trouvé.
"""

import json
import math
import os
import sys

DEPRESSION_NOMINALE: int = -3  # mce (socle fixe, NF EN 805)

_SECTION_PI = math.pi / 4.0  # facteur section : π·D²/4, D en m


# ---------------------------------------------------------------------------
# Catalogue interne de repli (identique à la méthode fixe du README)
# ---------------------------------------------------------------------------
_FALLBACK_TRIFON = {  # ventouse triple fonction (FIRM) — grand orifice, admission @ -3 mce
    50: {"q": {-4: 800, -3: 750, -2: 650}},
    65: {"q": {-4: 1400, -3: 1200, -2: 1050}},
    80: {"q": {-4: 2300, -3: 2100, -2: 1850}},
    100: {"q": {-4: 4200, -3: 3800, -2: 3400}},
    150: {"q": {-4: 9000, -3: 8000, -2: 7000}},
    200: {"q": {-4: 18000, -3: 17000, -2: 15000}},
    250: {"q": {-4: 28000, -3: 26000, -2: 23000}},
    300: {"q": {-4: 42000, -3: 38000, -2: 34000}},
}

_FALLBACK_CEAI = {  # clapet d'entrée d'air (Ramus) @ -3 mce
    80: {"section": 0.0050, "q": {-4: 1901, -3: 1800, -2: 1598}},
    100: {"section": 0.0079, "q": {-4: 3100, -3: 2902, -2: 2498}},
    150: {"section": 0.0177, "q": {-4: 6901, -3: 6300, -2: 5699}},
    200: {"section": 0.0314, "q": {-4: 12398, -3: 11304, -2: 10102}},
    250: {"section": 0.0491, "q": {-4: 19400, -3: 17600, -2: 15800}},
    300: {"section": 0.0707, "q": {-4: 27900, -3: 26701, -2: 22799}},
    350: {"section": 0.0962, "q": {-4: 38002, -3: 34600, -2: 31100}},
    400: {"section": 0.1256, "q": {-4: 49702, -3: 47401, -2: 40601}},
    500: {"section": 0.1963, "q": {-4: 77699, -3: 70600, -2: 63500}},
}

_FALLBACK_PSA = {  # purgeur sonic PSA (Ramus) — évacuation air au remplissage
    80: {"q_remplissage": 1200, "pfa": "10/16"},
    100: {"q_remplissage": 1600, "pfa": "10/16"},
    150: {"q_remplissage": 2200, "pfa": "10/16"},
    200: {"q_remplissage": 2200, "pfa": "10/16"},
    250: {"q_remplissage": 3500, "pfa": "10/16"},
}


def _chemin_base_valves() -> str:
    """Retourne le chemin du fichier valve_database.json s'il existe, sinon ''."""
    # 1) exe
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        p = os.path.join(base, "valve_database.json")
        if os.path.isfile(p):
            return p
    # 2) variable d'environnement
    env = os.environ.get("VALVE_DATABASE_PATH", "")
    if env and os.path.isfile(env):
        return env
    # 3) racine du projet (parent du package app/)
    here = os.path.dirname(os.path.abspath(__file__))  # .../app/data
    root = os.path.dirname(os.path.dirname(here))      # .../MK_AA_2026
    p = os.path.join(root, "valve_database.json")
    if os.path.isfile(p):
        return p
    return ""


def _section_dn(dn):
    return round(_SECTION_PI * (dn / 1000.0) ** 2, 6) if dn else 0.0


def _construire_standard(data: dict) -> tuple:
    """Construit TRIFON/CEAI/PSA (structures moteur) depuis le JSON.

    Retourne (TRIFON, CEAI, PSA).
    """
    four = data.get("fournisseurs", {})

    # TRIFON : ventouses
    trifon = {}
    for it in four.get("TRIFON", {}).get("ventouses", []):
        dn = it.get("dn")
        q = it.get("q_capacity")
        if dn and q:
            trifon[dn] = {"q": {DEPRESSION_NOMINALE: float(q)},
                          "section": _section_dn(dn)}
    if not trifon:
        trifon = dict(_FALLBACK_TRIFON)

    # CEAI : clapets
    ceai = {}
    for it in four.get("CEAI", {}).get("ventouses", []):
        dn = it.get("dn")
        q = it.get("q_capacity")
        if dn and q:
            ceai[dn] = {"q": {DEPRESSION_NOMINALE: float(q)},
                        "section": _section_dn(dn)}
    if not ceai:
        ceai = dict(_FALLBACK_CEAI)

    # PSA : pas de fournisseur "PSA" dans le JSON → repli interne (méthode fixe)
    psa = dict(_FALLBACK_PSA)

    return trifon, ceai, psa


def _construire_fournisseurs(data: dict, ceai_sections: dict) -> list:
    """Liste ordonnée des fournisseurs pour l'UI/exports.

    Chaque élément : {"nom","statut","origine",
        "ventouses":[{"dn","q"}], "clapets":[{"dn","q","modele"}],
        "purgeurs":[{"dn","q","modele","tuyere_dn","orifice","pressions"}]}
    """
    four = data.get("fournisseurs", {})
    liste = []
    for nom, spec in four.items():
        entree = {
            "nom": nom,
            "statut": spec.get("statut", ""),
            "origine": spec.get("origine", ""),
            "ventouses": list(spec.get("ventouses", [])),
            "clapets": list(spec.get("clapets", [])),
            "purgeurs": list(spec.get("purgeurs", [])),
        }
        liste.append(entree)
    return liste


# ---------------------------------------------------------------------------
# Chargement (une seule fois)
# ---------------------------------------------------------------------------
_SOURCE = ""
_CHEMINS_ESSAYES: list = []
_DONNEES = None

TRIFON = {}
CEAI = {"section": {}, "q": {}}
PSA = {}


def _charger():
    global _SOURCE, _CHEMINS_ESSAYES, _DONNEES, TRIFON, CEAI, PSA

    chemin = _chemin_base_valves()
    _CHEMINS_ESSAYES = [chemin] if chemin else []

    if chemin:
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                data = json.load(f)
            trifon, ceai, psa = _construire_standard(data)
            # PS : CEAI modifiable depuis JSON, PSA reste l'interne
            TRIFON = trifon
            CEAI = ceai
            PSA = psa
            _SOURCE = chemin
            _DONNEES = data
            return
        except Exception:
            _CHEMINS_ESSAYES.append(f"ERREUR lecture : {chemin}")

    # repli interne
    TRIFON = dict(_FALLBACK_TRIFON)
    CEAI = dict(_FALLBACK_CEAI)
    PSA = dict(_FALLBACK_PSA)
    _SOURCE = "(catalogue interne)"
    _DONNEES = {"fournisseurs": {}} if _DONNEES is None else _DONNEES


_charger()

FOURNISSEURS = _construire_fournisseurs(_DONNEES, CEAI) if _DONNEES else []


def racharger() -> str:
    """Recharge la base (utile si le JSON est édité en cours de session)."""
    _charger()
    global FOURNISSEURS
    FOURNISSEURS = _construire_fournisseurs(_DONNEES, CEAI)
    return _SOURCE


def source_base() -> str:
    """Chemin/source du fichier valve_database.json réellement utilisé."""
    return _SOURCE


def fournisseur(nom: str) -> dict:
    """Retourne l'entrée d'un fournisseur (ou {} si absent)."""
    for f in FOURNISSEURS:
        if f["nom"].lower() == str(nom).lower():
            return f
    return {}


def table_capacite(nom: str, role: str) -> dict:
    """Débit d'air (m³/h) par DN pour un fournisseur donné et un rôle.

    role ∈ {"ventouse", "clapet", "purgeur"}.
    Pour "clapet", on préfère la table clapets du fournisseur, sinon ses ventouses.
    Retourne {dn: q_capacity}.
    """
    f = fournisseur(nom)
    if not f:
        return {}
    if role == "clapet":
        items = f.get("clapets") or f.get("ventouses") or []
    elif role == "purgeur":
        items = f.get("purgeurs") or []
    else:  # ventouse
        items = f.get("ventouses") or f.get("clapets") or []
    return {int(it["dn"]): float(it.get("q_capacity", 0.0))
            for it in items if it.get("dn") and it.get("q_capacity") is not None}


def table_moteur(nom: str, role: str, depr: int = DEPRESSION_NOMINALE) -> dict:
    """Table au format moteur (dimensionnement §8) pour un fournisseur.

    Retourne {dn: {"q": {depr: capacité}}} — structure identique aux
    catalogues TRIFON/CEAI utilisés par app.core.dimensionnement.
    Retourne {} si le fournisseur est inconnu ou sans rôle compatible.
    """
    return {dn: {"q": {depr: cap}}
            for dn, cap in table_capacite(nom, role).items()}
