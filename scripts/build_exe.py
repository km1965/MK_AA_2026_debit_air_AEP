# -*- coding: utf-8 -*-
"""Compile l'application en EXE onefile (MK_AA_2026.exe) et place
valve_database.json à côté, prêt à l'emploi. Utilise Python 3.14 (py -3.14).

Usage : py -3.14 scripts\\build_exe.py
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "MK_AA_2026.spec")
DIST = os.path.join(ROOT, "dist_MK_AA_2026")
DB = os.path.join(ROOT, "valve_database.json")


def main():
    os.chdir(ROOT)
    print("=== Compilation PyInstaller ===")
    subprocess.check_call([sys.executable, "-m", "PyInstaller",
                           "--clean", "--noconfirm", SPEC])
    # Place la base éditable à côté de l'exe
    dst = os.path.join(DIST, "valve_database.json")
    shutil.copyfile(DB, dst)
    print(f"=== Terminé : {os.path.join(DIST, 'MK_AA_2026.exe')} ===")
    print(f"    Base modifiable : {dst}")


if __name__ == "__main__":
    main()
