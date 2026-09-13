"""Tests de la méthode « profil complet » (chaîne de tronçons).

Exécution :  python tests/test_profil_complet.py
"""

import io
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.core.profil_complet import (
    ProfilTroncon, ResultatProfilComplet, calculer_profil, synthese_txt,
    _cumul_abscisse_local, _longueur_troncon,
)
from app.utils import export as export_txt
from app.utils import croquis as croquis_mod

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


def chaine_temoin():
    return [
        ProfilTroncon(label="TR1", schema="3B", z_vi1=90.0, z_ve=120.0, z_vi2=85.0,
                      z_pi1=118.0, z_pi2=86.0,
                      a=400, b=500, c=300, d=400),
        ProfilTroncon(label="TR2", schema="3A", z_vi1=85.0, z_ve=130.0, z_vi2=80.0,
                      l1=700, l2=500),
        ProfilTroncon(label="TR3", schema="3B", z_vi1=80.0, z_ve=125.0, z_vi2=75.0,
                      z_pi1=123.0, z_pi2=76.0,
                      a=300, b=400, c=300, d=300),
    ]


def test_longueurs():
    print("Test — abscisses cumulées locales")
    check("3B : L = a+b+c+d = 1600",
          abs(_longueur_troncon("3B", {"a": 400, "b": 500, "c": 300, "d": 400}) - 1600) < 1e-9)
    check("3A : L = l1+l2 = 1200",
          abs(_longueur_troncon("3A", {"l1": 700, "l2": 500}) - 1200) < 1e-9)
    x = _cumul_abscisse_local("3B", {"a": 400, "b": 500, "c": 300, "d": 400})
    check("3B : x(Ve) = a+b = 900", abs(x["ve"] - 900) < 1e-9)
    check("3B : x(Vi2) = 1600", abs(x["vi2"] - 1600) < 1e-9)
    x4B = _cumul_abscisse_local("4B", {"l1": 700, "c": 300, "d": 400})
    check("4B : x(Ve) = l1 = 700", abs(x4B["ve"] - 700) < 1e-9)
    check("4B : x(Vi2) = l1+c+d = 1400", abs(x4B["vi2"] - 1400) < 1e-9)


def test_chainage():
    print("Test — recousu des points le long du profil")
    pc = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                         pression_nominale=10.0)
    check("3 tronçons calculés", len(pc.troncons) == 3)
    check("résultats par TR (Q_Ve > 0)", all(rt.res.q_ve_m3h > 0 for rt in pc.troncons))
    check("13 points recousus (5+4+4)",
          len(pc.points) == 13, f"got {len(pc.points)}")

    # abscisses cumulées attendues
    x_ve_tr2 = [p.x for p in pc.points if p.tr == "TR2" and p.cle == "ve"][0]
    check("Ve(TR2) à x = 1600 + 700 = 2300", abs(x_ve_tr2 - 2300) < 1e-9,
          f"got {x_ve_tr2}")
    # longueur totale = 1600 + 1200 + 1300 = 4100
    check("Ltot = 4100 m", abs(pc.longueur_totale - 4100) < 1e-9,
          f"got {pc.longueur_totale}")

    check("sommet max = 130 m (Ve TR2)",
          abs(pc.z_max - 130.0) < 1e-9, f"got {pc.z_max}")
    check("point bas min = 75 m (Vi2 TR3)",
          abs(pc.z_min - 75.0) < 1e-9, f"got {pc.z_min}")


def test_jonctions():
    print("Test — continuité Vi2(TRi) ≡ Vi1(TR(i+1))")
    pc = calculer_profil(chaine_temoin())
    check("2 jonctions", len(pc.jonctions) == 2)
    ok = all(j.ok for j in pc.jonctions)
    check("jonctions continues (ΔZ < 1 cm)", ok)
    # une jonction délibérément discontinue
    tr = chaine_temoin()
    tr[1].z_vi1 = 87.0   # TR1 Vi2=85, TR2 Vi1=87 → écart 2 m
    pc2 = calculer_profil(tr)
    check("détection d'un écart de 2 m", not pc2.jonctions[0].ok)
    check("avertissement levé",
          any("TR1/TR2" in a for a in pc2.avertissements))


def test_vidanges_communes():
    print("Test — fusion des vidanges (une entrée par point bas)")
    pc = calculer_profil(chaine_temoin())
    vid = pc.synthese_vidanges()
    check("2 vidanges communes", len(vid) == 2)
    check("Q évacuation ≥ max des pentes adjacentes",
          all(v["q_evacuation"] >= max(v["q_amont_tr_i"], v["q_aval_tr_i1"])
              for v in vid))
    check("vidange 1 à Z = 85 m", abs(vid[0]["z"] - 85.0) < 1e-9)
    check("vidange 2 à Z = 80 m", abs(vid[1]["z"] - 80.0) < 1e-9)


def test_synthese_organes():
    print("Test — synthèse des organes le long du profil")
    pc = calculer_profil(chaine_temoin())
    org = pc.synthese_organes()
    check("6 organes/TR prévu : TR1 et TR3 (3B, PI actif → clapet PI + purgeur "
          "sonique SNH en plus du point haut) ; TR2 (3A) : 4",
          [len([o for o in org if o["tr"] == t]) for t in ("TR1", "TR2", "TR3")]
          == [6, 4, 6], f"got {len(org)}")
    types = {o["type"] for o in org}
    check("types présents", {"Ventouse TRIFON", "Clapet d'admission",
                             "Purgeur de remplissage",
                             "Clapet d'admission (PI)",
                             "Purgeur sonique SNH"} <= types)
    check("ordres de rép. séquentiels", [o["rep"] for o in org] ==
          ["%02d" % i for i in range(1, 17)])
    # ventouse TR1 co-localisée avec la 1re vidange du TR1 vers cul-de-sac
    v_ve = [o for o in org if o["type"] == "Ventouse TRIFON"]
    check("ventouses triées par abscisse croissante",
          all(v_ve[i]["x"] < v_ve[i + 1]["x"] for i in range(len(v_ve) - 1)))


def test_rapport_txt():
    print("Test — génération du rapport texte (multi-TR) + croquis ASCII")
    pc = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                         pression_nominale=10.0)
    txt = export_txt.generer_rapport_profil(pc)
    for jeton in ["PROFIL COMPLET", "TR1 → TR2 → TR3", "§1", "§2", "§3",
                  "SYNTHÈSE DES ORGANES", "VIDANGES COMMUNES",
                  "CROQUIS DU PROFIL COMPLET"]:
        check(f"rapport contient « {jeton} »", jeton in txt)
    ascii_c = croquis_mod.croquis_chain_ascii(pc)
    check("croquis ASCII non vide", len(ascii_c) > 200)


def test_rapport_office():
    print("Test — exports .docx / .xlsx / .png")
    from types import SimpleNamespace
    from app.utils import export_office
    import tempfile

    pc = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                         pression_nominale=10.0)
    pc.propositions = [{"ventouse": {"dn": 300, "nombre": 3}}] + [None] * 2
    pc.comparer_propositions()
    etat = SimpleNamespace(moe="MOE", projet="Test", reference="R1",
                           branches="BR", schema="profil", wn="—", dn_mm=1600.0)
    tmp = tempfile.mkdtemp(prefix="profil_test_")
    try:
        p_docx = os.path.join(tmp, "r.docx")
        export_office.exporter_docx_profil(pc, etat, p_docx)
        check("docx généré", os.path.getsize(p_docx) > 20_000)
        p_xlsx = os.path.join(tmp, "r.xlsx")
        export_office.exporter_xlsx_profil(pc, etat, p_xlsx)
        check("xlsx généré", os.path.getsize(p_xlsx) > 2_000)
        from openpyxl import load_workbook
        wb = load_workbook(p_xlsx)
        check("xlsx a la feuille « Vérification client »",
              "Vérification client" in wb.sheetnames)
        ws_v = wb["Vérification client"]
        has_concl = any("CONCLUSION" in str(c.value or "")
                        for row in ws_v.iter_rows() for c in row)
        check("xlsx contient la conclusion", has_concl)
        has_recap = any("Récapitulatif implantation par point haut"
                        in str(c.value or "")
                        for row in ws_v.iter_rows() for c in row)
        check("xlsx feuille Vérification contient le récap Fs par point haut",
              has_recap)
        p_txt = os.path.join(tmp, "r.txt")
        with open(p_txt, "w", encoding="utf-8") as f:
            f.write(export_txt.generer_rapport_profil(pc, etat))
        contenu = open(p_txt, encoding="utf-8").read()
        check("txt contient la vérification client",
              "VÉRIFICATION DE LA PROPOSITION CLIENT" in contenu)
        p_png = os.path.join(tmp, "r.png")
        croquis_mod.croquis_chain_png(pc, p_png)
        check("png généré", os.path.getsize(p_png) > 20_000)
    finally:
        for f in (p_docx, p_xlsx, p_png, p_txt):
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def test_propositions_client():
    print("Test — vérification proposition client (verdicts + conclusions)")
    from app.core.profil_complet import verification_txt

    pc = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                         pression_nominale=10.0)
    # TR1 : ventouse 3×DN300 + clapet DN400 (insuffisant) + purgeur 4×DN250
    #        + vanne de sectionnement DN 1600 (DN principal)
    pc.propositions = [
        {"ventouse": {"dn": 300, "nombre": 3},
         "clapet": {"dn": 400, "nombre": 1},
         "purgeur": {"dn": 250, "nombre": 4},
         "vanne_dn": 1600},
        None,
        {"ventouse": {"dn": 300, "nombre": 4},
         "clapet": {"dn": 400, "nombre": 3},
         "purgeur": {"dn": 250, "nombre": 4}},
    ]
    v = pc.comparer_propositions()
    check("verdicts produits (3 organes + groupe + vanne par TR renseigné, "
          "+1 CAS PARTICULIER PI par TR 3B à PI active)",
          len(v) == 12, f"got {len(v)}")
    ventouse = [x for x in v if "Ventouse" in x["categorie"]]
    clapets = [x for x in v if "Clapet" in x["categorie"]]
    check("TR1 ventouse conforme (3×DN300=114000 ≥ besoin+15%)",
          ventouse[0]["conforme"])
    check("TR1 clapet DN400 insuffisant", not clapets[0]["conforme"])
    check("TR3 clapet 3×DN400 conforme (142203 ≥ besoin+15%)",
          clapets[1]["conforme"])
    check("TR2 sans proposition ignoré (aucun verdict)",
          not any(x["troncon"] == "TR2" for x in v))

    vannes = [x for x in v if "Vanne" in x["categorie"]]
    check("vanne TR1 (DN1600 précisée, = DN principal) : pas d'étranglement à "
          "justifier → conforme", vannes[0]["conforme"]
          and vannes[0]["etranglement_ok"] and vannes[0]["sonique_ok"])
    check("vanne TR3 non précisée → DN principal 1600 appliqué",
          vannes[1]["dn"] == 1600)
    check("vanne TR3 : DN vanne/DN principal = 1 → aucun étranglement, vanne "
          "n'est pas en cause (conforme)", vannes[1]["conforme"]
          and "aucun étranglement" in vannes[1]["message"])
    check("vitesse de référence vanne TR1 < 40 m/s",
          vannes[0]["v_vanne_ms"] < 40)

    # Annexe « organes vs conduite » : TR3 groupe proposé 308 203 m³/h >
    # capacité DN1600 à 40 m/s (289 584 m³/h) → ce SONT LES ORGANES à corriger
    # (pas la vanne, qui suit la conduite)
    groupes = [x for x in v if "Groupe d'air" in x["categorie"]]
    check("groupe TR3 non conforme (organes surdimensionnés pour la DN1600)",
          not groupes[1]["conforme"] and groupes[1]["organes_surdimensionnes"])
    check("l'annexe signale bien la correction des ORGANES",
          "ORGANES SURDIMENSIONNÉS" in groupes[1]["message"]
          and "la vanne de sectionnement n'étant pas en cause"
          in groupes[1]["message"])
    check("groupe TR1 conforme (175 401 m³/h < 289 584 m³/h)",
          groupes[0]["conforme"])

    # Vanne trop étroite (< DN principal) → étranglement + blocage sonique
    pc3 = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                          pression_nominale=10.0)
    pc3.propositions = [{"ventouse": {"dn": 300, "nombre": 4},
                         "clapet": {"dn": 400, "nombre": 3},
                         "purgeur": {"dn": 250, "nombre": 4},
                         "vanne_dn": 200}]
    pc3.comparer_propositions()
    v_etroit = [x for x in pc3.verifications
                if x["categorie"] == "Vanne de sectionnement"][0]
    check("vanne DN200 : NON CONFORME (étranglement + sonique)",
          not v_etroit["conforme"] and (not v_etroit["etranglement_ok"]
                                        or not v_etroit["sonique_ok"]))

    concl = pc.conclusion_globale()
    check("conclusion NON CONFORME (clapet TR1 défaillant)", not concl["conforme"])
    check("déficit clapet TR1 > 0",
          any(x["deficit_m3h"] > 0 for x in clapets if x["troncon"] == "TR1"))
    check("défauts regroupés par tronçon", "TR1" in concl["defauts_par_troncon"])

    txt = verification_txt(pc)
    for jeton in ["VÉRIFICATION DE LA PROPOSITION CLIENT",
                  "CONCLUSION GLOBALE : PROPOSITION NON CONFORME",
                  "TRONÇON TR1", "prévoir un clapet d'admission"]:
        check(f"verification_txt contient « {jeton} »", jeton in txt)

    # Cas conforme général : ventouse 4×DN300 + clapet 3×DN400 suffisent partout ;
    # vanne de sectionnement DN2000 (gros groupes → passage d'air < 40 m/s)
    pc2 = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                          pression_nominale=10.0)
    pc2.propositions = [
        {"ventouse": {"dn": 300, "nombre": 4},
         "clapet": {"dn": 400, "nombre": 3},
         "purgeur": {"dn": 250, "nombre": 4},
         "vanne_dn": 2000},
        {"ventouse": {"dn": 300, "nombre": 4},
         "clapet": {"dn": 400, "nombre": 3},
         "purgeur": {"dn": 250, "nombre": 4},
         "vanne_dn": 2000},
        {"ventouse": {"dn": 300, "nombre": 4},
         "clapet": {"dn": 400, "nombre": 3},
         "purgeur": {"dn": 250, "nombre": 4},
         "vanne_dn": 2000},
    ]
    pc2.comparer_propositions()
    check("conclusion CONFORME (tous les organes couvrent, vannes DN2000 "
          "incluses)", pc2.conclusion_globale()["conforme"])
    vannes_cf = [x for x in pc2.verifications
                 if x["categorie"] == "Vanne de sectionnement"]
    check("les 3 vannes DN2000 conformes (étranglement bon + sonique < 40 m/s)",
          len(vannes_cf) == 3 and all(x["conforme"] and x["etranglement_ok"]
                                      and x["sonique_ok"] for x in vannes_cf))


def test_recap_ph_fs():
    print("Test — récapitulatif implantation par point haut (Fs + avis + "
          "suggestion)")
    from app.core.profil_complet import recap_ph_txt, verification_txt
    from app.data.catalogues import TRIFON, CEAI

    pc = calculer_profil(chaine_temoin(), dn_mm=1600.0, temperature=15.0,
                         pression_nominale=10.0)
    rt1 = pc.troncons[0]
    # TR1 (3B, PI1 actif) : 2× ventouse DN200 + 4× clapet DN250 + 1× purgeur
    # DN1500 → ventouses au Ve, clapets au PI1, purgeur hors Fs.
    pc.propositions = [
        {"ventouse": {"dn": 200, "nombre": 2},
         "clapet": {"dn": 250, "nombre": 4},
         "purgeur": {"dn": 1500, "nombre": 1}},
        None, None,
    ]
    pc.comparer_propositions()
    rows = pc.recap_ph()
    phs = [r["ph"] for r in rows]
    check("TR1 (PI1 actif) → 3 lignes : Ve + PI1 + Groupe",
          phs == ["Ve (point haut)", "PI1 (point intermédiaire)",
                  "Groupe (Ve + PI)"], str(phs))
    cap_dn200 = TRIFON.get(200, {}).get("q", {}).get(-3, 0.0)
    cap_dn250 = CEAI.get(250, {}).get("q", {}).get(-3, 0.0)
    ve, pi, gp = rows
    check("Fs Ve = 2×DN200 / Q_Ve (dégazage purgeur exclu)",
          abs(ve["fs"] - (2 * cap_dn200) / rt1.res.q_ve_m3h) < 1e-9,
          f"got {ve['fs']:.4f}")
    check("Fs PI1 = 4×DN250 / Q_PI1",
          abs(pi["fs"] - (4 * cap_dn250) / rt1.res.q_pi1_m3h) < 1e-9)
    check("Fs Groupe = (ventouses+clapets) / (Q_Ve+Q_PI1)",
          abs(gp["fs"] - (2 * cap_dn200 + 4 * cap_dn250) /
              (rt1.res.q_ve_m3h + rt1.res.q_pi1_m3h)) < 1e-9)
    check("le purgeur figure dans l'implantation du Ve",
          "purgeur DN1500" in ve["implantation"])
    check("purgeur exclu de la capacité du Ve",
          abs(ve["cap_m3h"] - 2 * cap_dn200) < 1e-9)
    check("clapets affectés au PI1 (pas au Ve)",
          "clapet" in pi["implantation"] and "clapet" not in ve["implantation"])
    check("avis cohérent avec Fs (règle 3 niveaux)", all(
        (r["avis"] == "CONFORME") == (r["fs"] >= 1.20)
        and (r["avis"] == "NON CONFORME") == (r["fs"] < 1.00)
        and (r["avis"] == "ADMISSIBLE — NON RECOMMANDÉ")
        == (1.00 <= r["fs"] < 1.20) for r in rows))
    has_sug = [r for r in rows if r["suggestion"]]
    check("suggestion présente uniquement si 1,00 ≤ Fs < 1,20",
          all((1.00 <= r["fs"] < 1.20) == bool(r["suggestion"]) for r in rows),
          str([(r["ph"], round(r["fs"], 2)) for r in rows]))

    # Branche ADMISSIBLE — NON RECOMMANDÉ garantie : ventouses juste sous 1,20
    rt2 = pc.troncons[1]
    q_ve2 = rt2.res.q_ve_m3h
    cap200 = TRIFON.get(200, {}).get("q", {}).get(-3, 0.0)
    k = 0
    while cap200 > 0 and (k * cap200 < q_ve2 or k * cap200 >= 1.20 * q_ve2):
        k += 1
    pc2 = calculer_profil([ProfilTroncon(label="TR2", schema="3A",
                                         z_vi1=85.0, z_ve=130.0, z_vi2=80.0,
                                         l1=700, l2=500)],
                          dn_mm=1600.0, temperature=15.0,
                          pression_nominale=10.0)
    pc2.propositions = [{"ventouse": {"dn": 200, "nombre": k}}]
    pc2.comparer_propositions()
    r2 = pc2.recap_ph()
    check("CAS NORMAL : une seule ligne Ve (ventouse+clapet confondus)",
          [x["ph"] for x in r2] == ["Ve (point haut)"], str(r2))
    if cap200 > 0 and k > 0:
        check("Fs Ve (normal) = capacité ventouses / Q_Ve",
              abs(r2[0]["fs"] - (k * cap200) / q_ve2) < 1e-9)
        check("branche 1,00 ≤ Fs < 1,20 → avis ADMISSIBLE — NON RECOMMANDÉ "
              "+ suggestion d'ajout pour atteindre ≥ 1,20",
              r2[0]["avis"] == "ADMISSIBLE — NON RECOMMANDÉ"
              and "Ajouter" in r2[0]["suggestion"]
              and "DN200" in r2[0]["suggestion"]
              and "≥ 1,20" in r2[0]["suggestion"],
              f"fs={r2[0]['fs']:.3f} avis={r2[0]['avis']} "
              f"sug={r2[0]['suggestion']!r}")

    # recap_ph_txt intégré à verification_txt (donc au rapport .txt)
    txt = verification_txt(pc)
    check("verification_txt intègre le récap Fs par point haut",
          "RÉCAPITULATIF IMPLANTATION PAR POINT HAUT" in txt)
    r_txt = recap_ph_txt(pc)
    check("recap_ph_txt affiche tronçon, Fs, avis et suggestion",
          "TR1" in r_txt and "→ Fs = " in r_txt
          and ("✓ CONFORME" in r_txt or "⚠ " in r_txt or "✗ " in r_txt))


def test_recap_pi_dedie():
    print("Test — organes DÉDIÉS par point intermédiaire (clapet_pi1/clapet_pi2)")
    from app.controller import capacite_organe

    # 3B avec PI1 ET PI2 actifs (poches d'air des deux côtés)
    pc = calculer_profil(
        [ProfilTroncon(label="TR1", schema="3B", z_vi1=90.0, z_ve=120.0,
                       z_vi2=85.0, z_pi1=115.0, z_pi2=110.0,
                       a=400, b=500, c=300, d=400)],
        dn_mm=1600.0, temperature=15.0, pression_nominale=10.0)
    rt1 = pc.troncons[0]
    check("TR1 : PI1 ET PI2 actifs (Q > 0)",
          (rt1.res.q_pi1_m3h > 0 and rt1.res.q_pi2_m3h > 0),
          f"got Q_PI1={rt1.res.q_pi1_m3h:.0f} Q_PI2={rt1.res.q_pi2_m3h:.0f}")

    pc.propositions = [
        {"ventouse": {"dn": 300, "nombre": 3},
         "clapet": {"dn": 250, "nombre": 4},
         "clapet_pi1": {"dn": 250, "nombre": 2},
         "clapet_pi2": {"dn": 250, "nombre": 2}},
    ]
    pc.comparer_propositions()
    rows = pc.recap_ph()
    check("récap → Ve + PI1 + PI2 + Groupe",
          [r["ph"] for r in rows] == ["Ve (point haut)",
                                      "PI1 (point intermédiaire)",
                                      "PI2 (point intermédiaire)",
                                      "Groupe (Ve + PI)"],
          str([r["ph"] for r in rows]))

    cap_v = capacite_organe({"type": "trifon", "dn": 300, "nombre": 3})
    cap_c = capacite_organe({"type": "ceai", "dn": 250, "nombre": 4})
    cap_pi = capacite_organe({"type": "ceai", "dn": 250, "nombre": 2})
    vs, p1, p2, gp = rows
    q_ve = rt1.res.q_ve_m3h
    check("Ve = ventouses + clapet (Ve) ; Fs Ve sur Q_Ve",
          abs(vs["cap_m3h"] - (cap_v + cap_c)) < 1e-9
          and abs(vs["fs"] - (cap_v + cap_c) / q_ve) < 1e-9,
          f"cap={vs['cap_m3h']:.0f} fs={vs['fs']:.3f}")
    check("PI1 = son propre clapet (pas de prorata)",
          abs(p1["cap_m3h"] - cap_pi) < 1e-9
          and abs(p1["fs"] - cap_pi / rt1.res.q_pi1_m3h) < 1e-9)
    check("PI2 = son propre clapet (pas de prorata)",
          abs(p2["cap_m3h"] - cap_pi) < 1e-9
          and abs(p2["fs"] - cap_pi / rt1.res.q_pi2_m3h) < 1e-9)
    check("Groupe = Σ capacités (Ve+clapet+PI1+PI2) / Σ besoins",
          abs(gp["cap_m3h"] - (cap_v + cap_c + 2 * cap_pi)) < 1e-9
          and abs(gp["fs"] - (cap_v + cap_c + 2 * cap_pi) /
                  (q_ve + rt1.res.q_pi1_m3h + rt1.res.q_pi2_m3h)) < 1e-9)

    # comparer_propositions : chaque PI vérifié contre son organe dédié
    cas = [x for x in pc.verifications if "CAS PARTICULIER" in x["categorie"]]
    check("2 verdicts CAS PARTICULIER (PI1 + PI2)", len(cas) == 2,
          f"got {len(cas)}")
    p1_v = [x for x in cas if "PI1" in x["categorie"]][0]
    p2_v = [x for x in cas if "PI2" in x["categorie"]][0]
    check("PI1 vérifié contre son clapet dédié DN250×2",
          "dédié PI1" in p1_v["propose"] and "DN250" in p1_v["propose"]
          and p1_v["cap_proposee_m3h"] >= cap_pi - 1e-9,
          f"cap={p1_v['cap_proposee_m3h']:.0f} propose={p1_v['propose']}")
    check("PI2 vérifié contre son clapet dédié DN250×2",
          "dédié PI2" in p2_v["propose"] and "DN250" in p2_v["propose"]
          and p2_v["cap_proposee_m3h"] >= cap_pi - 1e-9,
          f"cap={p2_v['cap_proposee_m3h']:.0f} propose={p2_v['propose']}")

    # Fallback : sans clapet dédié, la règle historique (prorata) reste active
    pc3 = calculer_profil(
        [ProfilTroncon(label="TR1", schema="3B", z_vi1=90.0, z_ve=120.0,
                       z_vi2=85.0, z_pi1=115.0, z_pi2=110.0,
                       a=400, b=500, c=300, d=400)],
        dn_mm=1600.0, temperature=15.0, pression_nominale=10.0)
    pc3.propositions = [{"ventouse": {"dn": 300, "nombre": 3},
                         "clapet": {"dn": 250, "nombre": 4}}]
    pc3.comparer_propositions()
    rows3 = pc3.recap_ph()
    pr_rows = [r for r in rows3 if r["ph"].startswith("PI")]
    q_tot = sum(r["besoin_m3h"] for r in pr_rows)
    check("fallback : clapets répartis au prorata des Q_PI (pas de dédié)",
          q_tot > 0 and abs(sum(r["cap_m3h"] for r in pr_rows) - cap_c) < 1e-9
          and all(abs(r["cap_m3h"] - cap_c * r["besoin_m3h"] / q_tot) < 1e-9
                  for r in pr_rows),
          str([(r["ph"], r["cap_m3h"]) for r in pr_rows]))


def test_regression_defaults():
    print("Test — défauts harmonisés (marge 15 %, plafond 90 %)")
    from app.core import dimensionnement as dim
    check("MARGE_ACCESSOIRES_PCT = 15", dim.MARGE_ACCESSOIRES_PCT == 15.0)
    check("PLAFOND_UTILISATION_PCT = 90", dim.PLAFOND_UTILISATION_PCT == 90.0)
    dc = __import__("app.core.constants",
                    fromlist=["DonneesConduite"]).DonneesConduite
    v = dim.choisir_ventouse(50000)
    check("plafond par défaut appliqué (ventouse)",
          v.capacite_installee_m3h >= 50000 * 1.25)
    c = dim.choisir_clapet(30000)
    check("plafond par défaut appliqué (clapet)",
          c.capacite_installee_m3h >= 30000 * 1.25)


def _regression_suite():
    globs = dict(globals())
    for nom, fn in list(globs.items()):
        if nom.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  [EXC] {nom} : {e!r}")
                global FAIL
                FAIL += 1


if __name__ == "__main__":
    _regression_suite()
    print(f"\n{'-' * 44}\n  → {PASS} OK · {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)