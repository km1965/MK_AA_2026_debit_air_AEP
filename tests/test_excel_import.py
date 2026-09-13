"""Tests du module d'import Excel (ROADMAP §14.1 — V05).

Exécution :  python tests/test_excel_import.py
"""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from openpyxl import Workbook

from app.controller import EtatApplication
from app.utils import excel_import as xi

PASS = 0
FAIL = 0


def check(nom, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK]  {nom}")
    else:
        FAIL += 1
        print(f"  [FAIL] {nom}  {detail}")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ecrire(donnees, organes=None) -> str:
    """Classeur temporaire avec les deux feuilles du modèle V05."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Données projet"
    ws.append(["Paramètre", "Valeur", "Unité", "Description"])
    for row in donnees:
        ws.append(list(row))
    ws2 = wb.create_sheet("Organes client")
    ws2.append(["Type", "DN (mm)", "Nombre", "Position", "Fournisseur"])
    for row in (organes or []):
        ws2.append(list(row))
    chemin = os.path.join(tempfile.gettempdir(), "test_import_mk_aa.xlsx")
    wb.save(chemin)
    wb.close()
    return chemin


def test_exemple_fourni():
    print("Test V05 — lecture du classeur d'exemple (anonymisé)")
    p = _ecrire(
        [("Maître d'ouvrage", "XXX", "—", ""),
         ("Projet / marché", "Projet type AEP", "—", ""),
         ("Référence document", "NC_mk_aa_2026-BR2-TR1", "—", ""),
         ("Branches étudiées", "BR1, BR2, BR3", "—", ""),
         ("Diamètre nominal DN", 1600, "mm", ""),
         ("Température de l'eau", 15, "°C", ""),
         ("Pression nominale PN", 16, "bar", ""),
         ("Schéma de vidange", "3A", "—", ""),
         ("Z_Vi1", "100,00", "m NGM", ""),
         ("Z_Ve", "87,68", "m NGM", ""),
         ("Z_Vi2", "4,86", "m NGM", ""),
         ("L1 (Vi1→Ve)", "73,55", "m", ""),
         ("L2 (Ve→Vi2)", "361,82", "m", ""),
         ("H_z dénivelé géométrique", "auto", "mCE", ""),
         ("DN vanne de sectionnement", "1600", "mm", "")],
        organes=[("trifon", 250, 2, "amont", "TRIFON"),
                 ("ceai", 400, 1, "amont", "SNH"),
                 ("ceai", 400, 1, "aval", "SNH"),
                 ("psa", 250, 1, "amont", "SNH"),
                 ("vanne", 1600, 1, "", "")])
    d, w = xi.lire_donnees_projet(p)
    check("maître d'ouvrage", d.get("moe") == "XXX", d)
    check("projet", d.get("projet", "").startswith("Projet type AEP"), d)
    check("DN = 1600", d.get("dn_mm") == 1600.0, d)
    check("schéma 3A", d.get("schema") == "3A", d)
    check("Z_Ve = 87,68", abs(d.get("z_ve", 0) - 87.68) < 1e-9, d)
    check("Z_Vi2 = 4,86", abs(d.get("z_vi2", 0) - 4.86) < 1e-9, d)
    check("L1 = 73,55", abs(d.get("l1", 0) - 73.55) < 1e-9, d)
    check("L2 = 361,82", abs(d.get("l2", 0) - 361.82) < 1e-9, d)
    check("PI absents (schéma 3A)", "z_pi1" not in d and "z_pi2" not in d, d)
    check("DN vanne = 1600", d.get("dn_vanne_sectionnement") == 1600.0, d)
    org = d.get("organes_client", [])
    check("4 organes d'air (vanne exclue)", len(org) == 4, org)
    check("aucun organe 'vanne'",
          all(o.get("type") != "vanne" for o in org), org)
    check("aucun avertissement", not w, w)


def test_lecture_decimale_et_organes():
    print("Test V05 — décimale française, H_z auto, organes (dont vanne)")
    p = _ecrire(
        [("Maître d'ouvrage", "TEST_MOE", "—", ""),
         ("Diamètre nominal DN", 2000, "mm", ""),
         ("Schéma de vidange", "3a", "—", ""),
         ("Z_Vi1", "4,00", "m NGM", ""),
         ("Z_Ve", "102,99", "m NGM", ""),
         ("Z_Vi2", "2,00", "m NGM", ""),
         ("L1 (Vi1→Ve)", "73,55", "m", ""),
         ("L2 (Ve→Vi2)", "361,82", "m", ""),
         ("H_z dénivelé géométrique", "auto", "mCE", ""),
         ("DN vanne de sectionnement", "1600", "mm", "")],
        organes=[("ceai", 250, 2, "AVAL", "SNH"),
                 ("trifon", 200, 3, "", "TRIFON"),
                 ("vanne", 1600, 1, "", "")])
    d, w = xi.lire_donnees_projet(p)
    check("décimale virgule → 102,99", abs(d.get("z_ve", 0) - 102.99) < 1e-9, d)
    check("DN = 2000", d.get("dn_mm") == 2000.0, d)
    check("schéma normalisé en majuscule", d.get("schema") == "3A", d)
    check("H_z 'auto' → non renseigné", "hz_casse_franche" not in d, d)
    check("DN vanne conservé", d.get("dn_vanne_sectionnement") == 1600.0, d)
    org = d.get("organes_client", [])
    check("2 organes d'air", len(org) == 2, org)
    check("position en minuscules",
          org[0].get("position") == "aval", org)
    check("fournisseur SNH", org[0].get("fournisseur") == "SNH", org)
    check("nombre 3", org[1].get("nombre") == 3, org)
    check("aucun avertissement", not w, w)


def test_controles_validite():
    print("Test V05 — contrôle de validité")
    p1 = _ecrire([("Z_Ve", 100.0, "m", "")])
    d1, w1 = xi.lire_donnees_projet(p1)
    check("schéma manquant signalé",
          any("Schéma de vidange non renseigné" in m for m in w1), w1)
    check("Z_Ve présent OK", d1.get("z_ve") == 100.0, d1)

    p2 = _ecrire([("Schéma de vidange", "3A", "—", ""),
                  ("Z_Ve", 100.0, "m", "")])
    _d2, w2 = xi.lire_donnees_projet(p2)
    check("distances manquantes signalées",
          any("Distances manquantes" in m for m in w2), w2)

    p3 = _ecrire([("Schéma de vidange", "4B", "—", "")])
    _d3, w3 = xi.lire_donnees_projet(p3)
    check("Z_Ve manquant signalé",
          any("Z_Ve" in m for m in w3), w3)

    p4 = _ecrire([("Température de l'eau", "abc", "°C", "")])
    _d4, w4 = xi.lire_donnees_projet(p4)
    check("valeur numérique invalide signalée",
          any("invalide" in m for m in w4), w4)


def test_appliquer_excel_integration():
    print("Test V05 — EtatApplication.appliquer_excel + calcul")
    p = _ecrire(
        [("Maître d'ouvrage", "TEST", "—", ""),
         ("Diamètre nominal DN", 1600, "mm", ""),
         ("Température de l'eau", 15, "°C", ""),
         ("Schéma de vidange", "3A", "—", ""),
         ("Z_Vi1", 4.0, "m NGM", ""),
         ("Z_Ve", 100.0, "m NGM", ""),
         ("Z_Vi2", 2.0, "m NGM", ""),
         ("L1 (Vi1→Ve)", 73.55, "m", ""),
         ("L2 (Ve→Vi2)", 361.82, "m", "")],
        organes=[("trifon", 250, 2, "amont", "TRIFON")])
    e = EtatApplication()
    w = e.appliquer_excel(p)
    check("champs appliqués", e.schema == "3A" and abs(e.z_ve - 100.0) < 1e-9, e)
    check("organes appliqués", len(e.organes_client) == 1, e)
    check("pas d'avertissement bloquant", not w, w)
    e.calculer()
    check("calcul réussi", e.resultat is not None and e.erreur == "",
          (e.resultat, e.erreur))


if __name__ == "__main__":
    test_exemple_fourni()
    test_lecture_decimale_et_organes()
    test_controles_validite()
    test_appliquer_excel_integration()
    print(f"\n{'-' * 60}")
    print(f"Résultat : {PASS} OK / {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)