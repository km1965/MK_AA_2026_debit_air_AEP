# -*- coding: utf-8 -*-
"""Point d'entrée — Application MK_A.A 2026 (débits d'air admis en AEP).

Lancer avec Python 3.14 ✓.
    En ligne de commande :  py -3.14 main.py
    Ou via  run_app.bat   (recommandé sur Windows).
"""

import os
import sys

PYTHON_OK = (3, 14)

# Assurer l'import du package `app` quel que soit le répertoire de lancement
_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from app.ui.main_window import lancer  # noqa: E402


def _verifier_version():
    """Affiche la version Python et avertit si elle diffère de 3.14."""
    majeur, mineur = sys.version_info[:2]
    version = f"{majeur}.{mineur}"
    print(f"Python {sys.version.split()[0]} — {sys.executable}")
    if (majeur, mineur) != PYTHON_OK:
        print(f"Avertissement : version {version} détectée, "
              f"recommandé : {PYTHON_OK[0]}.{PYTHON_OK[1]}.")


if __name__ == "__main__":
    _verifier_version()
    lancer()
