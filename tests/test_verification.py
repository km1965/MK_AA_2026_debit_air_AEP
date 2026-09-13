# -*- coding: utf-8 -*-
import io, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.controller import EtatApplication, capacite_organe

e = EtatApplication(); e.calculer()
besoin_ve = e.resultat.q_ve_m3h * 1.25
print("Besoin ventouse +25%% =", round(besoin_ve))

print("\n--- Insuffisant : 1 x TRIFON 300 ---")
e.organes_client = [{"type": "trifon", "dn": 300, "nombre": 1}]
for v in e.verifier_organes():
    st = "CONFORME" if v["conforme"] else "NON CONFORME"
    print(f"  [{v['categorie']}] {st} | {v['message']}")

print("\n--- Suffisant : 2xTRIFON300 + CEAI500 + PSA250x4 + vanne ---")
e2 = EtatApplication(); e2.calculer()
e2.organes_client = [
    {"type": "trifon", "dn": 300, "nombre": 2},
    {"type": "ceai", "dn": 500, "nombre": 1},
    {"type": "psa", "dn": 250, "nombre": 4},
    {"type": "vanne", "dn": None, "nombre": 1},
]
for v in e2.verifier_organes():
    st = "CONFORME" if v["conforme"] else "NON CONFORME"
    print(f"  [{v['categorie']}] {st}")
    assert v["conforme"], v["categorie"]
print("\nToutes les catégories conformes = OK")

print("\n--- Cumul groupe d'air : suffisant vs insuffisant ---")
g = [v for v in e2.verifier_organes() if v["categorie"].startswith("CUMUL")][0]
assert g["conforme"] and g["capacite_proposee"] >= g["besoin"]
print("  Groupe d'air CONFORME : cap", g["capacite_proposee"], ">= besoin", g["besoin"])

e3 = EtatApplication(); e3.calculer()
e3.organes_client = [{"type": "ceai", "dn": 80, "nombre": 1}]
g3 = [v for v in e3.verifier_organes() if v["categorie"].startswith("CUMUL")][0]
assert not g3["conforme"] and g3["capacite_proposee"] < g3["besoin"]
print("  Groupe d'air NON CONFORME (clapet seul) : cap", g3["capacite_proposee"], "< besoin", g3["besoin"])

print("\n--- CAS PARTICULIER 3B : clapets DÉDIÉS aux PI (position pi1/pi2) ---")
e4 = EtatApplication(); e4.schema = "3B"
e4.z_pi1 = 116.0; e4.z_pi2 = 116.0
e4.calculer()
assert e4.resultat.q_pi1_m3h > 0 and e4.resultat.q_pi2_m3h > 0, \
    f"PI inactifs : Q_PI1={e4.resultat.q_pi1_m3h:.0f} Q_PI2={e4.resultat.q_pi2_m3h:.0f}"
e4.organes_client = [
    {"type": "trifon", "dn": 300, "nombre": 2},
    {"type": "ceai", "dn": 250, "nombre": 2, "position": "pi1"},
    {"type": "ceai", "dn": 250, "nombre": 2, "position": "pi2"},
    {"type": "psa", "dn": 250, "nombre": 4},
]
dec = e4.decomposition_pi()
pts = {p["cle"]: p for p in dec["points"]}
assert "pi1" in pts and "pi2" in pts
cap_pi = capacite_organe({"type": "ceai", "dn": 250, "nombre": 2})
for cle in ("pi1", "pi2"):
    src = pts[cle]["sources"]
    assert "organes dédiés" in src and "DN250" in src, src
    assert pts[cle]["cap_affectee_m3h"] >= cap_pi - 1e-9, \
        f"{cle}: {pts[cle]['cap_affectee_m3h']} < {cap_pi}"
    print(f"  {cle} : {src} → cap {pts[cle]['cap_affectee_m3h']:.0f} "
          f"(manque {pts[cle]['manque_m3h']:.0f})")

v4 = {v["categorie"]: v for v in e4.verifier_organes()}
assert v4["Clapet admission air"]["capacite_proposee"] == 0, \
    "le clapet dédié PI est exclu du lot Ve"
print("  Clapet dédié PI exclu du verdict « Clapet admission air » (Ve) = OK")
cpi_v = [x for x in e4.verifier_organes()
         if "CAS PARTICULIER" in x["categorie"]]
assert len(cpi_v) == 2 and all("dédié" in x["message"] for x in cpi_v), \
    [x["message"] for x in cpi_v]
for x in cpi_v:
    print(f"  {x['categorie']} : {x['message'][:120]}...")
print("  CAS PARTICULIER vérifiés contre les organes dédiés = OK")

print("\n--- Nouveau tableau de vérification (SANS majoration) ---")
e5 = EtatApplication(); e5.calculer()
e5.organes_client = [
    {"type": "trifon", "dn": 300, "nombre": 2},
    {"type": "ceai", "dn": 250, "nombre": 2, "position": "pi1"},
    {"type": "ceai", "dn": 250, "nombre": 2, "position": "pi2"},
    {"type": "psa", "dn": 250, "nombre": 4},
]
t = e5.tableau_verification_organes()
assert t, "tableau vide"
for r in t:
    assert set(r) == {"repere", "demande_m3h", "categorie", "dn", "nombre",
                      "implantation", "fournisseur", "capacite_m3h", "fs", "verdict"}, \
        f"clés inattendues : {set(r) ^ set({})}"
    assert r["verdict"] in ("Conforme", "Non conforme")
    if r["fs"] is not None:
        rfs = r["capacite_m3h"] / r["demande_m3h"]
        assert abs(r["fs"] - rfs) < 0.01, \
            f"Fs {r['fs']} != cap/demande brute {rfs} ({r['repere']})"
# le besoin de référence est le Q BRUT, pas le Q×1,25
ref_brut = e5.resultat.q_ve_m3h
ph = [r for r in t if r["repere"] == "Pht VE"]
assert ph and abs(ph[0]["demande_m3h"] - ref_brut) < 1e-9, \
    f"demande Ve majorée par erreur : {ph[0]['demande_m3h']} vs {ref_brut}"
# ordre des lignes : Ve puis PI1 puis PI2
order = [r["repere"] for r in t]
assert order[0] == "Pht VE", order
print("  repères ordonnés :", " | ".join(order))
print("  exemple :", {k: (round(v, 2) if isinstance(v, float) else v)
                      for k, v in t[0].items()})
print("  Fs calculés SANS majoration (cap/demande brute) = OK")
