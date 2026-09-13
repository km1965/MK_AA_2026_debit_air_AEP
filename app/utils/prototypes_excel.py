# -*- coding: utf-8 -*-
"""Génération des classeurs prototypes pour l'import Excel (ROADMAP §14.1).

Deux fichiers sont produits à la racine du projet (et recopiés à côté des
EXE lors des builds) :
  * `Donnees_projet_vide.xlsx`      — gabarit vierge à remplir par le projeteur ;
  * `Donnees_projet_Exemple.xlsx`   — exemple complet (maître d'ouvrage anonymisé, BR2-TR1, schéma 3A).

Exécution :  python -m app.utils.prototypes_excel
"""

from __future__ import annotations

import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_BLEU = "DDEBF7"
_GRIS = "F2F2F2"
_JAUNE = "FFF2CC"

_FONT_TITRE = Font(bold=True, size=13)
_FONT_SECTION = Font(bold=True, italic=True, size=11, color="1F4E79")
_FONT_ENTETE = Font(bold=True, color="FFFFFF")
_FILL_ENTETE = PatternFill("solid", fgColor="4472C4")
_FILL_SECTION = PatternFill("solid", fgColor=_BLEU)
_FILL_SAISIE = PatternFill("solid", fgColor=_JAUNE)
_FILL_AIDE = PatternFill("solid", fgColor=_GRIS)

_BORDS = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)

_ALIGN_GAUCHE = Alignment(horizontal="left", vertical="center")
_ALIGN_CENTRE = Alignment(horizontal="center", vertical="center")


def _large(ws, largeurs):
    for i, w in enumerate(largeurs, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _style_ligne(ws, ligne, fonte, n_cols=4, remplir=None):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=ligne, column=c)
        cell.font = fonte
        cell.border = _BORDS
        if remplir is not None:
            cell.fill = remplir


# ---------------------------------------------------------------------------
# Feuille « Données projet »
# ---------------------------------------------------------------------------
def _ecrire_projet(ws, valeurs: dict):
    """Une ligne par paramètre : Paramètre | Valeur | Unité | Description."""
    _large(ws, [30, 16, 10, 60])
    ws.append(["Paramètre", "Valeur", "Unité", "Description"])
    _style_ligne(ws, 1, _FONT_ENTETE, remplir=_FILL_ENTETE)
    for c in range(1, 5):
        ws.cell(row=1, column=c).alignment = _ALIGN_CENTRE
    ws.freeze_panes = "A2"

    ligne = 2
    sections = [
        ("— 1. Identification —", [
            ("Maître d'ouvrage", "moe", "—", "§4.1"),
            ("Projet / marché", "projet", "—", "§4.1"),
            ("Référence document", "reference", "—", "§4.1"),
            ("Branches étudiées", "branches", "—", "§4.1"),
        ]),
        ("— 2. Conduite —", [
            ("Diamètre nominal DN", "dn_mm", "mm", "§4.2"),
            ("Température de l'eau", "temperature", "°C", "§4.3 (ν corrigé si ≠ 15)"),
            ("Pression nominale PN", "pression_nominale", "bar", "flambement / nomenclature"),
        ]),
        ("— 3. Profil en long —", [
            ("Schéma de vidange", "schema", "—", "§5 (1A…4B)"),
            ("Z_Vi1", "z_vi1", "m NGM", "point bas amont"),
            ("Z_PI1", "z_pi1", "m NGM", "point intermédiaire amont (vide si absent)"),
            ("Z_Ve", "z_ve", "m NGM", "point haut (ventouse)"),
            ("Z_PI2", "z_pi2", "m NGM", "point intermédiaire aval (vide si absent)"),
            ("Z_Vi2", "z_vi2", "m NGM", "point bas aval"),
            ("a (Vi1→PI1)", "a", "m", "si schéma avec PI1"),
            ("b (PI1→Ve)", "b", "m", "si schéma avec PI1"),
            ("c (Ve→PI2)", "c", "m", "si schéma avec PI2"),
            ("d (PI2→Vi2)", "d", "m", "si schéma avec PI2"),
            ("L1 (Vi1→Ve)", "l1", "m", "si schéma sans PI"),
            ("L2 (Ve→Vi2)", "l2", "m", "si schéma sans PI"),
        ]),
        ("— 4. Casse franche —", [
            ("H_z dénivelé géométrique", "hz", "mCE", "« auto » (défaut) ou valeur explicite"),
            ("DN vanne de sectionnement", "dn_vanne", "mm", "0 si non renseignée"),
        ]),
    ]

    for titre, champs in sections:
        ws.cell(row=ligne, column=1, value=titre)
        _style_ligne(ws, ligne, _FONT_SECTION, remplir=_FILL_SECTION)
        ligne += 1
        for lib, cle, unite, desc in champs:
            ws.cell(row=ligne, column=1, value=lib).alignment = _ALIGN_GAUCHE
            for c in range(1, 5):
                ws.cell(row=ligne, column=c).border = _BORDS
            ws.cell(row=ligne, column=2).alignment = _ALIGN_CENTRE
            ws.cell(row=ligne, column=2).fill = _FILL_SAISIE
            ws.cell(row=ligne, column=3, value=unite).border = _BORDS
            ws.cell(row=ligne, column=4, value=desc).alignment = _ALIGN_GAUCHE

            valeur = "" if cle not in valeurs else valeurs[cle]
            if valeur is None:
                valeur = ""
            ws.cell(row=ligne, column=2, value=valeur)
            ligne += 1

    ws.cell(row=ligne + 1, column=1, value=(
        "Remarques : saisir les cellules jaunes · décimale virgule (100,00) · "
        "« auto » pour H_z · DN en mm numériques · laisser vide ce qui n'appartient pas au schéma."))
    ws.cell(row=ligne + 1, column=1).font = Font(italic=True, color="808080")


def _ecrire_organes(ws, organes: list):
    _large(ws, [14, 12, 10, 12, 16])
    entetes = ["Type", "DN (mm)", "Nombre", "Position", "Fournisseur"]
    ws.append(entetes)
    _style_ligne(ws, 1, _FONT_ENTETE, n_cols=5, remplir=_FILL_ENTETE)
    for c in range(1, 6):
        ws.cell(row=1, column=c).alignment = _ALIGN_CENTRE
    ws.freeze_panes = "A2"
    for o in organes:
        ws.append([o.get("type", ""), o.get("dn", ""), o.get("nombre", ""),
                   o.get("position", ""), o.get("fournisseur", "")])
    for r in range(2, 2 + len(organes) + 6):
        _style_ligne(ws, r, Font(), n_cols=5)
    dernier = 2 + len(organes)
    note = ws.cell(row=dernier + 1, column=1, value=(
        "Type : trifon (ventouse) · ceai (clapet admission) · psa (purgeur) · "
        "vanne (sectionnement, → DN vanne) — Position : amont / aval."))
    note.font = Font(italic=True, color="808080")


# ---------------------------------------------------------------------------
def _generer(chemin: str, valeurs: dict, organes: list) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Données projet"
    _ecrire_projet(ws, valeurs)
    ws2 = wb.create_sheet("Organes client")
    _ecrire_organes(ws2, organes)
    wb.save(chemin)
    return chemin


_VALEURS_EXEMPLE = {
    "moe": "XXX (maître d'ouvrage anonymisé)",
    "projet": "Projet type AEP · Marché N° XXXXXX",
    "reference": "NC_mk_aa_2026-BR2-TR1",
    "branches": "BR1, BR2, BR3",
    "dn_mm": 1600,
    "temperature": 15,
    "pression_nominale": 16,
    "schema": "3A",
    "z_vi1": 100.0,
    "z_pi1": None,
    "z_ve": 87.68,
    "z_pi2": None,
    "z_vi2": 4.86,
    "l1": 73.55,
    "l2": 361.82,
    "hz": "auto",
    "dn_vanne": 1600,
}

_ORGANES_EXEMPLE = [
    {"type": "trifon", "dn": 250, "nombre": 2, "position": "amont", "fournisseur": "TRIFON"},
    {"type": "ceai", "dn": 400, "nombre": 1, "position": "amont", "fournisseur": "SNH"},
    {"type": "ceai", "dn": 400, "nombre": 1, "position": "aval", "fournisseur": "SNH"},
    {"type": "psa", "dn": 250, "nombre": 1, "position": "amont", "fournisseur": "SNH"},
    {"type": "vanne", "dn": 1600, "nombre": 1, "position": "", "fournisseur": ""},
]


def generer(racine: str) -> dict:
    vide = _generer(os.path.join(racine, "Donnees_projet_vide.xlsx"),
                    {}, [])
    exemple = _generer(os.path.join(racine, "Donnees_projet_Exemple.xlsx"),
                       dict(_VALEURS_EXEMPLE), list(_ORGANES_EXEMPLE))
    return {"vide": vide, "exemple": exemple}


if __name__ == "__main__":
    RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    resultats = generer(RACINE)
    for nom, chemin in resultats.items():
        print(f"{nom} : {chemin}")