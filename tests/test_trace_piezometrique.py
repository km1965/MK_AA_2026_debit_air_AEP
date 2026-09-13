"""Tests du moteur de tracé piézométrique (fenêtre « Analyse piézométrique »).

Exécution :  python tests/test_trace_piezometrique.py
"""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PIL import Image

from app.controller import EtatApplication
from app.utils import trace_piezometrique as tz

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


def _etat(schema):
    e = EtatApplication()
    e.schema = schema
    e.dn_mm = 1600
    e.projet = "Profil test"
    e.branches = "BR1"
    e.z_ve = 100.0
    e.z_vi1 = 5.0
    e.z_vi2 = 8.0
    e.z_pi1 = 130.0   # au-dessus de la piézométrie → organe requis
    e.z_pi2 = 10.0    # dans la vallée → pas d'organe
    for cle, val in (("l1", 400.0), ("l2", 300.0), ("a", 150.0),
                     ("b", 60.0), ("c", 120.0), ("d", 80.0)):
        setattr(e, cle, val)
    return e


def test_trace_8_schemas():
    print("Test — tracé PNG sur les 8 schémas")
    for schema in ("1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"):
        e = _etat(schema)
        chemin = os.path.join(tempfile.gettempdir(), f"trace_{schema}.png")
        fig, infos = tz.tracer_profil(e, chemin)
        import matplotlib.pyplot as plt
        plt.close(fig)
        taille = os.path.getsize(chemin) if os.path.exists(chemin) else 0
        ok_img = False
        if taille > 0:
            with Image.open(chemin) as im:
                ok_img = im.size[0] > 0 and im.size[1] > 0
        check(f"{schema} : PNG généré ({taille} octets)",
              taille > 0 and ok_img, chemin)
        check(f"{schema} : infos Q présents",
              infos["q_ve"] >= 0 and infos["journal"] is not None, infos)
        os.remove(chemin)


def test_verdicts_pi():
    print("Test — verdicts H1/H2 (critère ≥ 3 m)")
    for schema in ("1B", "3B", "4A"):
        e = _etat(schema)
        fig, infos = tz.tracer_profil(e)
        import matplotlib.pyplot as plt
        plt.close(fig)
        check(f"{schema} : H1 calculé", infos["h1"] is not None, infos)
        check(f"{schema} : PI1 haut → organe requis",
              infos["verdict1"] == "CAS PARTICULIER — organe requis",
              infos["verdict1"])
    for schema in ("2B", "3B", "4B"):
        e = _etat(schema)
        fig, infos = tz.tracer_profil(e)
        import matplotlib.pyplot as plt
        plt.close(fig)
        check(f"{schema} : H2 calculé", infos["h2"] is not None, infos)
        check(f"{schema} : PI2 bas → cas normal",
              infos["verdict2"] == "CAS NORMAL", infos["verdict2"])
    for schema in ("1A", "2A", "3A"):
        e = _etat(schema)
        fig, infos = tz.tracer_profil(e)
        import matplotlib.pyplot as plt
        plt.close(fig)
        check(f"{schema} : aucun PI → H1/H2 absents",
              infos["h1"] is None and infos["h2"] is None, infos)


def test_charger_json():
    print("Test — chargement d'un projet JSON")
    import json
    base = {"projet": "P", "branches": "BR", "schema": "1A", "dn_mm": 1400,
            "z_ve": 50.0, "z_vi1": 0.0, "l1": 300.0, "temperature": 15}
    chemin = os.path.join(tempfile.gettempdir(), "trace_proj_test.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(base, f)
    e = tz.charger_depuis_json(chemin)
    check("champs chargés", e.schema == "1A" and e.dn_mm == 1400, e)
    os.remove(chemin)


if __name__ == "__main__":
    test_trace_8_schemas()
    test_verdicts_pi()
    test_charger_json()
    print(f"\n{'-' * 60}")
    print(f"Résultat : {PASS} OK / {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)