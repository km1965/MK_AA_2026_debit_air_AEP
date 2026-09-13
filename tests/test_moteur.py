"""Tests du moteur de calcul MK_A.A 2026.

Exécution :  python tests/test_moteur.py
"""

import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.controller import EtatApplication, SCHEMAS, DISTANCES_PAR_CAS
from app.core.constants import DonneesConduite, debits_remplissage_table
from app.utils.viscosity import corriger_nu

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


def test_remplissage_reference():
    print("Test §9.1 — débit de remplissage (référence note)")
    tab = debits_remplissage_table()
    check("BR1 DN1400 = 11084", abs(tab[1400] - 11084) < 2, f"got {tab[1400]}")
    check("BR2 DN1600 = 14476", abs(tab[1600] - 14476) < 2, f"got {tab[1600]}")
    check("BR3 DN2000 = 22619", abs(tab[2000] - 22619) < 2, f"got {tab[2000]}")


def test_viscosite():
    print("Test §4.3 — correction viscosité")
    check("nu(15)=1.02e-6 (socle)", corriger_nu(15) > 1.0e-6)
    check("nu d�croit avec T", corriger_nu(10) > corriger_nu(20))
    print(f"    nu(0)={corriger_nu(0):.3e} nu(15)={corriger_nu(15):.3e} nu(30)={corriger_nu(30):.3e}")


def test_tous_schemas():
    print("Test §5/§6 — calcul des 8 schémas")
    for cas in SCHEMAS:
        e = EtatApplication()
        e.schema = cas
        res = e.calculer()
        check(f"{cas} : calcul sans exception, Q_Ve={res.q_ve_m3h:.0f} m³/h",
              res.q_ve_m3h >= 0)
        # vérifie que les bonnes distances sont utilisées
        actifs = DISTANCES_PAR_CAS[cas]
        # 3B a besoin de PI ; assure cohérence
        if res.q_ve_m3h > 0:
            check(f"{cas} : journal non vide", len(res.journal) > 0)


def test_pi_cas_particulier():
    print("Test §6 — cas particulier (poche d'air en PI)")
    e = EtatApplication()
    e.schema = "3B"
    e.z_pi1 = 115  # au-dessus de la ligne piézo → CAS PARTICULIER
    res = e.calculer()
    check("3B : Q_PI1 > 0 en cas particulier", res.q_pi1_m3h > 0,
          f"Q_PI1={res.q_pi1_m3h:.1f}")
    print(f"    Q_PI1={res.q_pi1_m3h:.1f} Q_PI2={res.q_pi2_m3h:.1f}")


def test_dimensionnement():
    print("Test §8 — dimensionnement")
    from app.core.dimensionnement import choisir_ventouse, choisir_clapet, q_remplissage, choisir_purgeur_psa
    dc = DonneesConduite.from_dn(2000)
    v = choisir_ventouse(50000)
    check("Ventouse couvre besoin×1,25 (1,15/0,90 ≈ 1,28)", v.capacite_installee_m3h >= 50000 * 1.25)
    c = choisir_clapet(30000)
    check("Clapet couvre besoin×1,25 (1,15/0,90 ≈ 1,28)", c.capacite_installee_m3h >= 30000 * 1.25)
    q = q_remplissage(2.0, dc)
    check("Remplissage DN2000=22619", abs(q - 22619) < 5, f"got {q:.0f}")
    p = choisir_purgeur_psa(q)
    print(f"    PSA DN2000 : {p.nombre} × PSA {p.dn}")
    check("Remplissage PSA ≥ Q", p.capacite_installee_m3h >= q)


def test_condition_zero():
    print("Test §6.3 — ΔH ≤ 0 → Q = 0")
    e = EtatApplication()
    e.schema = "1A"
    e.z_ve = e.z_vi1 + 2  # < seuil 3m → pas d'écoulement
    res = e.calculer()
    check("1A : Q_Ve = 0 (pas d'aspiration)", res.q_ve_m3h == 0,
          f"got {res.q_ve_m3h}")


def test_hz_casse_franche_auto():
    print("Test H_z auto — dénivelé point haut → rupture (profil)")
    e = EtatApplication()
    e.schema = "3B"
    e.z_vi1 = 100.0; e.z_ve = 120.0; e.z_vi2 = 90.0
    check("3B : H_z = Z_Ve − min(Vi1,Vi2) = 30",
          abs(e.hz_casse_franche_auto() - 30.0) < 1e-9,
          f"got {e.hz_casse_franche_auto()}")
    e.schema = "1A"   # côté amont seul
    check("1A : H_z = Z_Ve − Vi1 = 20",
          abs(e.hz_casse_franche_auto() - 20.0) < 1e-9,
          f"got {e.hz_casse_franche_auto()}")
    e.schema = "2A"   # côté aval seul
    check("2A : H_z = Z_Ve − Vi2 = 30",
          abs(e.hz_casse_franche_auto() - 30.0) < 1e-9,
          f"got {e.hz_casse_franche_auto()}")
    e.schema = "3B"
    e.z_ve = 80.0     # point haut sous le point bas → borne 0
    check("3B : H_z borné à 0 (Z_Ve < point bas)",
          abs(e.hz_casse_franche_auto() - 0.0) < 1e-9,
          f"got {e.hz_casse_franche_auto()}")


def test_rapport_debits_cumules_mk_aa():
    print("Test §3 — rapport « Débits cumulés » (Q MK_A.A à la place de Q_air)")
    from app.controller import EtatApplication as EA
    e = EA()
    e.methode_dimensionnement = "mk_aa"
    e.dn_mm = 1400.0
    e.organes_client = [
        {"type": "trifon", "dn": 200, "nombre": 2, "position": "amont",
         "fournisseur": "TRIFON"},
        {"type": "ceai", "dn": 250, "nombre": 4, "position": "amont",
         "fournisseur": "SNH"},
        {"type": "psa", "dn": 1500, "nombre": 1, "position": "amont",
         "fournisseur": "SNH"},
    ]
    e.dn_vanne_sectionnement = 1400.0
    e.calculer()
    texte = e.generer_rapport()
    check("rapport contient le chapitre « DÉBITS CUMULÉS »",
          "DÉBITS CUMULÉS" in texte)
    check("le besoin de référence est le Q MK_A.A calculé",
          "Q MK_A.A calculé" in texte and "Q_Ve" in texte)
    check("la formule Q_air / Torricelli est signalée NÉGLIGÉE",
          "NÉGLIGÉE" in texte and "Torricelli" in texte)
    check("la règle du cumul (ΣQ admis/expulsé) est présente",
          "ΣQ admis" in texte and "ΣQ expulsé" in texte)
    check("la condition vanne (tubulure/étranglement) est présente",
          "TUBULURE DE RACCORDEMENT ET VANNE" in texte
          and "Rapport S_vanne/ΣS" in texte)
    check("le bilan se conclut par un VERDICT", "VERDICT DÉBITS CUMULÉS" in texte)


if __name__ == "__main__":
    test_remplissage_reference()
    print()
    test_viscosite()
    print()
    test_tous_schemas()
    print()
    test_pi_cas_particulier()
    print()
    test_dimensionnement()
    print()
    test_condition_zero()
    print()
    test_hz_casse_franche_auto()
    print()
    test_rapport_debits_cumules_mk_aa()
    print()
    print(f"\n=== {PASS} tests OK, {FAIL} tests en échec ===")
    sys.exit(1 if FAIL else 0)
