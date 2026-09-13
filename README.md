# MK_AA_2026_debit_air_AEP

Application de calcul des **débits d'air admis** aux points hauts (Ve) et points
intermédiaires (PI1/PI2) des conduites **AEP** — dimensionnement des ventouses,
clapets d'entrée d'air et purgeurs lors d'une **casse franche** (NF EN 805, −3 mCE).

Méthode : Darcy-Weisbach → Colebrook-White → **formule explicite MK_A.A 2026**. Les 8
schémas de vidange (1A…4B) sont couverts, avec gestion du CAS PARTICULIER (point
intermédiaire au-dessus de la ligne piézométrique) et calcul du débit de remplissage.

## Prérequis

- **Python 3.14** (vérifié : 3.14.7) — `py -3.14 --version`
- Windows (interface customtkinter)

## Installation

```bat
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lancement

```bat
run_app.bat         :: recommandé
.venv\Scripts\python.exe main.py
```

## Tests

Chaque suite est un script autonome :

```bat
.venv\Scripts\python.exe tests\test_moteur.py            :: 37 OK
.venv\Scripts\python.exe tests\test_profil_complet.py    :: 91 OK
.venv\Scripts\python.exe tests\test_excel_import.py      :: 32 OK
.venv\Scripts\python.exe tests\test_trace_piezometrique.py :: 32 OK
.venv\Scripts\python.exe tests\test_verification.py
```

## Structure

```
app/
  core/     → socle de calcul FIXE (mk_aa.py, schemas.py, profil_complet.py, dimensionnement.py)
  data/     → catalogues d'organes (valve_database.json, catalogues.py)
  ui/       → fenêtres customtkinter
  utils/    → import Excel, exports docx/xlsx/PNG, tracé piézométrique
tests/      → suites de tests (moteur, profil complet, import Excel, piézométrie, vérification)
scripts/    → build PyInstaller, icônes
```

## Documentation

- `README_MK_AA_2026.md` — cahier des charges et note technique MK_A.A 2026 (socle de
  calcul, schémas de vidange, annexes catalogue, historique des versions).
- `*.spec` — builds PyInstaller (`MK_AA_2026_V01/_V02/_V01_Pro.spec`).