# -*- coding: utf-8 -*-
"""Analyse graphique profil piézométrique — Oued Nfifikh (exemple).

Réécrit sur le moteur générique `app.utils.trace_piezometrique` :
le même tracé (profil + ligne piézométrique Z_Ve − 3 mCE + critère H aux
points intermédiaires) est disponible dans l'application via le menu
latéral « 11 · Analyse piézométrique » (saisie manuelle des données).

Usage :  python analysis_oued.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.utils import trace_piezometrique as trace_z

PROJECT = (r"D:\Downloads\Azhar SP0\OUED NFIFIKH\RAPPORTS VERSION FINAL"
            r"\executables\projet_BR3_TR2_DEVIATION LGV OUED NFIFIKH.json")
OUTPUT = r"C:\Users\SMARTH~1\AppData\Local\Temp\opencode\profile_oued_nfifikh.png"

etat = trace_z.charger_depuis_json(PROJECT)
fig, infos = trace_z.tracer_profil(etat, OUTPUT)
import matplotlib.pyplot as plt
plt.close(fig)

print(f"Projet  : {etat.projet} ({etat.branches})")
print(f"Schema  : {etat.schema}  DN {etat.dn_mm:.0f} mm")
print(f"Z_Vi1={etat.z_vi1:.2f}  Z_PI1={etat.z_pi1:.2f}  "
      f"Z_Ve={etat.z_ve:.2f}  Z_PI2={etat.z_pi2:.2f}  Z_Vi2={etat.z_vi2:.2f}")
print(f"a={etat.a:.2f}  b={etat.b:.2f}  c={etat.c:.2f}  d={etat.d:.2f}\n")
print(f"Q_Ve   = {infos['q_ve']:,.1f} m³/h")
print(f"Q_PI1  = {infos['q_pi1']:,.1f} m³/h")
print(f"Q_PI2  = {infos['q_pi2']:,.1f} m³/h")
print(f"CAS PI1 : {infos['cas_pi1'] or '—'}   CAS PI2 : {infos['cas_pi2'] or '—'}")
if infos["h1"] is not None:
    print(f"H1 = {infos['h1']:+.2f} m -> {infos['verdict1']}")
if infos["h2"] is not None:
    print(f"H2 = {infos['h2']:+.2f} m -> {infos['verdict2']}")
print("\n--- Journal Allouane ---")
for line in infos["journal"]:
    print(" ", line)
print(f"\nFig sauvegardee -> {OUTPUT}")