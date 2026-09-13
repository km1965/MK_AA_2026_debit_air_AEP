"""Rapport de synthèse texte — note de calcul structurée (5 parties).

Structure conforme au document d'orientation :
  §1  Tableau récapitulatif des entrées projet
  §2  Analyse du risque majeur (casse franche) — formules détaillées
  §3  Vérification de la capacité de passage de l'air (cumul, sections, vitesse)
  §4  Vérification structurelle (flambement) et aéraulique (perte de charge)
  §5  Implantation et vérification des organes
"""

from ..core import mk_aa
from ..core.constants import DonneesConduite, SEUIL_DEPRESSION, REFERENCES_NORMATIVES
from ..core.schemas import ResultatSchema
from ..data.catalogues import CEAI, TRIFON, PSA, DEPRESSION_NOMINALE
from ..core.profil_complet import ResultatProfilComplet, verification_txt
from . import croquis


def _lignes_geo(dc: DonneesConduite) -> list:
    return [
        f"  Diamètre nominal        : DN {dc.dn:g} mm",
        f"  Diamètre intérieur D    : {dc.d:.4f} m",
        f"  Section S = π/4·D²      : {dc.section:.4f} m²",
        f"  Rapport k/D             : {dc.kd:.3e}",
    ]


def _ecrire_verif_air_txt(projet, lignes):
    """§3 — Vérification de la capacité de passage de l'air (méthode
    Vidange Brèche / Torricelli). Omise en mode purement MK_A.A."""

    # =====================================================================
    # §3  VÉRIFICATION DE LA CAPACITÉ DE PASSAGE DE L'AIR
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("§3  VÉRIFICATION DE LA CAPACITÉ DE PASSAGE DE L'AIR")
    lignes.append("=" * 72)
    lignes.append("")

    lignes.append("  3.1  Cumul des débits d'air à la dépression nominale")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  MÉTHODE : VIDANGE BRÈCHE (Torricelli) — Q_eau = A·√(2·g·H_z).")
    lignes.append("  Ce cumul du groupe (ventouses + clapets + purgeurs) est DISTINCT")
    lignes.append("  du dimensionnement des ventouses par la formule MK_A.A (2026)")
    lignes.append("  (chapitre §2) : il quantifie l'air à admettre pour la rupture")
    lignes.append("  totale, PAS l'écoulement gravitaire des tronçons.")
    try:
        cum = projet.cumul_debits()
        ad = cum["admission"]
        lignes.append(f"  ΣQ_admis à −{SEUIL_DEPRESSION:.0f} mCE :")
        lignes.append(f"    Ventouses  : {ad['trifon']:,.0f} m³/h")
        lignes.append(f"    Clapets    : {ad['ceai']:,.0f} m³/h")
        lignes.append(f"    Purgeurs   : {ad['psa']:,.0f} m³/h")
        lignes.append(f"    TOTAL      = {ad['total']:,.0f} m³/h")
        lignes.append(f"  Besoin casse franche : {cum['besoin_casse']:,.0f} m³/h")
        verdict_adm = cum["verdict_admission"]
        lignes.append(f"  Verdict admission : {'CONFORME' if verdict_adm else 'NON CONFORME'}"
                      f" ({ad['total']:,.0f} {'≥' if verdict_adm else '<'} {cum['besoin_casse']:,.0f})")
        # Vérification du GROUPE COMPLET face aux débits MK_A.A (Q_Ve)
        try:
            ga = projet.verifier_groupe_mk_aa()
            lignes.append("  Vérification du groupe complet face aux débits MK_A.A (Q_Ve) :")
            lignes.append(f"    Groupe installé = {ga['admission']['total']:,.0f} m³/h "
                          f"(besoin Q_Ve = {ga['besoin_mk_aa']:,.0f} ; "
                          f"majoré +15 % = {ga['besoin_majore']:,.0f} m³/h, plafond 90 %)")
            vv = f"{ga['vitesse']['vanne']:.1f} m/s" if ga['vitesse']['vanne'] < 1e6 else "n.c."
            va = f"{ga['vitesse']['aval']:.1f} m/s" if ga['vitesse']['aval'] < 1e6 else "n.c."
            lignes.append(f"    Vitesse vanne {vv} / aval {va} (limite 40 m/s) → "
                          f"{'OK' if ga['vitesse']['ok'] else 'INSUFFISANT'}")
            lignes.append(f"    Verdict groupe vs MK_A.A : "
                          f"{'CONFORME' if ga['conforme'] else 'NON CONFORME'}")
        except Exception as ge:
            lignes.append(f"  (Vérification groupe vs MK_A.A indisponible : {ge})")
    except Exception as e:
        lignes.append(f"  (Cumul indisponible : {e})")
    lignes.append("")

    lignes.append("  3.2  Rapport des sections de passage (absence d'étranglement)")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  Condition : S_vanne > ΣS_organes_amont (pas d'étranglement)")
    try:
        vn = cum["vanne"]
        if vn["section_vanne"] > 0:
            lignes.append(f"  S_vanne = {vn['section_vanne']:.4f} m²  (DN{vn['dn']:.0f})")
            lignes.append(f"  ΣS_amont = {vn['section_amont']:.4f} m²")
            lignes.append(f"  Rapport = {vn['ratio']:.2f} ×")
            if vn["conforme"]:
                lignes.append(f"  → PAS D'ÉTRANGLEMENT (ratio > 1)")
            else:
                lignes.append(f"  → ÉTRANGLEMENT POTENTIEL (ratio ≤ 1) — aggravation de la vitesse")
        else:
            lignes.append("  (Section vanne non renseignée)")
    except Exception as e:
        lignes.append(f"  (Vérification sections indisponible : {e})")
    lignes.append("")

    lignes.append("  3.3  Vitesse d'air — limite critique sonique (ISO 6358-1)")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  Au-delà de 40 m/s, l'air atteint le régime sonique et le débit")
    lignes.append("  réel est inférieur au débit calculé (blocage aéraulique).")
    lignes.append("  La limite de 40 m/s est imposée sur toutes les sections critiques.")
    lignes.append("")
    try:
        vt = cum["limite_vitesse"]
        v_vanne = f"{vt['v_air']:.1f} m/s" if vt["v_air"] < 1e6 else "n.c."
        v_aval = f"{vt['v_aval']:.1f} m/s" if vt["v_aval"] < 1e6 else "n.c."
        lignes.append(f"  Vitesse vanne : {v_vanne}  (limite {vt['v_limite']:.0f} m/s)")
        lignes.append(f"  Vitesse aval  : {v_aval}  (limite {vt['v_limite']:.0f} m/s)")
        lignes.append(f"  Capacité de passage à la vanne : {vt['capacite_passage_40']:,.0f} m³/h")
        if not vt["ok"]:
            lignes.append("  ✗ Contrainte de vitesse NON respectée — régime sonique atteint.")
        else:
            lignes.append("  ✓ Vitesse inférieure à la limite — régime sous-sonique assuré.")
    except Exception as e:
        lignes.append(f"  (Vérification vitesse indisponible : {e})")
    lignes.append("")

    lignes.append("  VERDICT CUMUL DES DÉBITS : ", )
    try:
        vn = cum["vanne"]
        vt = cum["limite_vitesse"]
        verdict = (cum["verdict_admission"] and vn["conforme"] and vt["ok"])
        lignes[-1] = lignes[-1] + ("CONFORME." if verdict else "NON CONFORME.")
    except Exception:
        lignes[-1] = lignes[-1] + "indisponible."
    lignes.append("")

    if not verdict:
        lignes.append("  MONTAGE OPTIMISÉ PROPOSÉ (ventouses TRIFON + équipements SNH)")
        try:
            opt = projet.groupe_optimise()
            lignes.append(f"    Besoin casse franche : {opt['besoin']:,.0f} m³/h ; "
                          f"admission existante {opt['admis_existant']:,.0f} m³/h ; "
                          f"manque à couvrir {opt['manque']:,.0f} m³/h")
            rep = opt["repartition"]
            lignes.append(f"    Répartition : amont {rep['amont']:,.0f} m³/h "
                          f"(transite vanne, ≤ {rep['kap']:,.0f} m³/h @40 m/s) + "
                          f"aval {rep['aval']:,.0f} m³/h (bypass conduite)")
            lignes.append("    Composition :")
            for o in opt["groupe"]:
                nom = {"trifon": "Ventouse TRIFON", "ceai": "Clapet SNH",
                       "psa": "Purgeur sonique SNH",
                       "vanne": "Vanne sectionnement"}[o["type"]]
                posf = f" [{o['position']}]" if o.get("position") else ""
                lignes.append(f"      • {o['nombre']} × {nom} DN{o['dn']}{posf}")
            if opt["vanne_dn"]:
                lignes.append(f"    Vanne de sectionnement recommandée : DN "
                              f"{opt['vanne_dn']} (= DN conduite principale)")
            couv = ("couvre le besoin → montage CONFORME (vitesses ≤ 40 m/s)"
                    if opt["conforme"] else "ne couvre pas entièrement le besoin")
            lignes.append(f"    Couverture totale {opt['coverage']:,.0f} m³/h → {couv}.")
            if opt["note"]:
                lignes.append(f"    Note : {opt['note']}")
        except Exception as e:
            lignes.append(f"    (Optimisation indisponible : {e})")
    lignes.append("")
    # --- Références normatives chapitre casse franche ---
    lignes.append("  Références normatives — Dimensionnement d'admission d'air (casse franche) :")
    lignes.append("    • NF EN 805 (2000) — Prévention des dépressions, dépression admissible ≤ 3 mCE.")
    lignes.append("    • AWWA M51 (2020) — Air release and vacuum valves for waterworks.")
    lignes.append("    • Torricelli — Q = A·√(2·g·H) débit de vidange par orifice sous charge.")
    lignes.append("    • Critère anti-étranglement sonique : v_air < 40 m/s (AWWA).")
    lignes.append("")


def _ecrire_debits_cumules_mk_aa_txt(projet, lignes):
    """§3 — Débits cumulés (méthode MK_A.A).

    Chapitre calqué sur la note « Débits cumulés » de référence. La seule
    différence : le débit d'air requis N'EST PAS la formule de la brèche
    (Q_air = A·√(2·g·H_z), Torricelli) — celle-ci est NÉGLIGÉE pour la
    vérification — mais le débit Q MK_A.A calculé (Q_Ve) au point haut.
    """
    lignes.append("=" * 72)
    lignes.append("DÉBITS CUMULÉS — VÉRIFICATION DU GROUPE D'AIR AU POINT HAUT")
    lignes.append("=" * 72)
    lignes.append("  Pour vérifier la capacité d'admission ou d'échappement d'air à un")
    lignes.append("  point haut, on cumule les débits d'air individuels de chaque")
    lignes.append("  appareil, sous trois conditions hydrauliques et géométriques")
    lignes.append("  majeures. Le dimensionnement s'effectue sur la somme des débits")
    lignes.append("  d'air RÉELS admis ou expulsés, et non sur la simple somme des")
    lignes.append("  diamètres des appareils.")
    lignes.append("")
    try:
        ga = projet.verifier_groupe_mk_aa()
        cum = projet.cumul_debits()
    except Exception as e:
        lignes.append(f"  (Vérification des débits cumulés indisponible : {e})")
        lignes.append("")
        return
    adm = ga["admission"]
    dc = cum["dc"]
    sec_conduite = cum["section_conduite"]
    vanne = cum["vanne"]
    vt = cum["limite_vitesse"]
    exp = cum["expulsion"]

    lignes.append(f"  1. RÈGLE DU CUMUL DES DÉBITS D'AIR (ΔP = −{SEUIL_DEPRESSION:g} mCE)")
    lignes.append("  ——————————————————————————————————————————————————————————")
    lignes.append("  Le débit total à l'admission (anti-dépression lors d'une vidange")
    lignes.append("  rapide ou d'un coup de bélier) ou à l'expulsion (remplissage de la")
    lignes.append("  conduite) est la somme directe des capacités de chaque composant à")
    lignes.append("  la même différence de pression (ΔP) :")
    lignes.append("  • Pour l'admission : clapets d'admission d'air, ventouses et")
    lignes.append("    purgeurs (en phase d'entrée d'air) travaillent en parallèle.")
    lignes.append("  • Pour l'expulsion : seuls les éléments conçus pour l'échappement")
    lignes.append("    d'air (ventouses et purgeurs soniques) interviennent.")
    lignes.append(f"  ΣQ admis = ventouses {adm['trifon']:,.0f} + clapets {adm['ceai']:,.0f} "
                  f"+ purgeurs {adm['psa']:,.0f} = {adm['total']:,.0f} m³/h")
    lignes.append(f"  ΣQ expulsé = ventouses {exp['trifon']:,.0f} + purgeurs "
                  f"{exp['psa']:,.0f} = {exp['total']:,.0f} m³/h")
    lignes.append("")

    lignes.append("  2. CONDITION ESSENTIELLE : TUBULURE DE RACCORDEMENT ET VANNE DE")
    lignes.append("     SECTIONNEMENT")
    lignes.append("  ——————————————————————————————————————————————————————————")
    dn_v = vanne["dn"]
    lignes.append(f"  Piquage et vanne d'isolement sur conduite principale "
                  f"(DN {dc.dn:g}) :")
    lignes.append(f"  • Section de la vanne DN {dn_v:g} = S_vanne = "
                  f"{vanne['section_vanne']:.3f} m²")
    lignes.append(f"  • Σ sections des appareils en partie haute = "
                  f"{vanne['section_amont']:.3f} m² "
                  f"(DN réels des ventouses/clapets + col sonique des purgeurs)")
    verdict_passage = ("la vanne est largement dimensionnée et ne bridera pas le "
                       "passage d'air vers les équipements" if vanne["conforme"]
                       else "ÉTRANGLEMENT POTENTIEL (aggravation de la vitesse)")
    lignes.append(f"  • Rapport S_vanne/ΣS = {vanne['ratio']:.2f} → {verdict_passage}.")
    lignes.append("")

    lignes.append("  3. POINTS DE VIGILANCE POUR LA VÉRIFICATION DE CALCUL")
    lignes.append("  ——————————————————————————————————————————————————————————")
    lignes.append("  3.1  Principe hydraulique (vidange / coup de bélier / casse franche)")
    lignes.append("  En cas de vidange rapide ou de rupture brutale en aval du point")
    lignes.append("  haut, la lame d'eau s'échappe par gravité à grande vitesse, créant")
    lignes.append("  un effet piston immédiatement sous le dôme. Les appareils du bloc")
    lignes.append("  au-dessus de la vanne s'ouvrent en grand sous l'effet de la")
    lignes.append("  dépression instantanée et aspirent l'air en parallèle : le débit")
    lignes.append("  global admis est la somme EXACTE des débits d'air individuels")
    lignes.append("  réels de chaque appareil. Le cumul est parfaitement valable et")
    lignes.append("  constitue la base de la protection contre l'écrasement de la")
    lignes.append("  conduite.")
    lignes.append("")
    lignes.append("  3.2  Débit d'air requis pour la vérification : Q MK_A.A calculé")
    lignes.append("  (La formule du débit d'air d'entrée requis par la brèche —")
    lignes.append("  Q_air = A·√(2·g·H_z), Torricelli — est NÉGLIGÉE pour la véri-")
    lignes.append("  fication. La référence retenue est le débit MK_A.A Q_Ve, débit")
    lignes.append("  d'air admis par l'écoulement gravitaire des tronçons au point")
    lignes.append("  haut (formule MK_A.A, 2026).)")
    lignes.append(f"  Q_Ve = {ga['besoin_mk_aa']:,.1f} m³/h "
                  f"(Q_am={projet.resultat.q_am_m3h:,.1f} · "
                  f"Q_av={projet.resultat.q_av_m3h:,.1f})")
    lignes.append(f"  Besoin majoré = Q_Ve × 1,15 = {ga['besoin_majore']:,.1f} m³/h "
                  f"(marge +15 %, plafond 90 % → capacité installée minimale "
                  f"{ga['cap_min_installee']:,.1f} m³/h)")
    lignes.append("")
    lignes.append("  3.3  Vérification des conditions limites")
    lignes.append("  • Pression différentielle max. : débits extraits sur les courbes")
    lignes.append("    constructeurs à la dépression −3 mCE (NF EN 805) ; ne pas")
    lignes.append("    dépasser le seuil pour éviter l'instabilité de la conduite ou")
    lignes.append("    le blocage sonique de l'air.")
    lignes.append("  • Contrainte de vitesse au niveau du piquage/vannes :")
    v_text = f"{vt['v_air']:.1f} m/s" if vt["v_air"] < 1e6 else "n.c."
    lignes.append(f"    v = {v_text} ≤ {vt['v_limite']:.0f} m/s → "
                  f"{'régime sous-sonique, pas de perte de charge limitante'
                     if vt['ok'] else 'RÉGIME SONIQUE — débit réel réduit'}.")
    lignes.append("")

    lignes.append("  4. BILAN DE VÉRIFICATION")
    lignes.append("  ——————————————————————————————————————————————————————————")
    lignes.append(f"  • Cumul admission = {adm['total']:,.0f} m³/h vs besoin majoré "
                  f"{ga['besoin_majore']:,.1f} m³/h → "
                  f"{'COUVERT' if ga['conforme'] else 'INSUFFISANT'}"
                  + (f" (manque {ga['manque']:,.0f} m³/h)" if ga["manque"] else "") + ".")
    lignes.append(f"  • Vanne/sections : S_vanne {vanne['section_vanne']:.3f} m² vs "
                  f"ΣS appareils {vanne['section_amont']:.3f} m² → "
                  f"{'sans étranglement' if vanne['conforme'] else 'étranglement'}.")
    lignes.append(f"  • Vitesse d'air (point le plus étroit) : {v_text} ≤ "
                  f"{vt['v_limite']:.0f} m/s → "
                  f"{'sous-sonique OK' if vt['ok'] else 'blocage sonique'}.")
    verdict = ga["conforme"] and vanne["conforme"] and vt["ok"]
    lignes.append(f"  VERDICT DÉBITS CUMULÉS : {'CONFORME' if verdict else 'NON CONFORME'}.")
    lignes.append("  Références normatives : NF EN 805 (2000) ; AWWA M51 (2020) ; "
                  "v_air < 40 m/s.")
    lignes.append("")


def generer_rapport(etat, schemas_resultat: ResultatSchema, dimensionnement: dict,
                    remplissage: dict, nu: float, temperature: float) -> str:
    """Génère le rapport de synthèse complet au format texte.

    etat : objet EtatApplication (données projet + schéma).
    Structure en 5 parties conforme au document d'orientation.
    """
    projet = etat
    lignes = []
    lignes.append("=" * 72)
    lignes.append("NOTE DE CALCUL — Débits d'air admis en conduites AEP")
    lignes.append("Dimensionnement des organes d'air — Casse franche")
    lignes.append("Méthode MK_A.A 2026")
    lignes.append("=" * 72)
    lignes.append("")
    lignes.append(f"  Document établi avec l'outil de dimensionnement")
    lignes.append(f"  (méthode de calcul MK_A.A 2026 appliquée)")
    lignes.append(f"  Maître d'ouvrage : {projet.moe or '—'}")
    lignes.append(f"  Projet / marché  : {projet.projet or '—'}")
    lignes.append(f"  Référence / indice: {projet.reference or '—'}")
    lignes.append(f"  Branche(s)       : {projet.branches or '—'}")
    lignes.append("")

    # =====================================================================
    # §1  TABLEAU RÉCAPITULATIF DES ENTRÉES PROJET
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("§1  TABLEAU RÉCAPITULATIF DES ENTRÉES PROJET")
    lignes.append("=" * 72)
    lignes.append("  Toutes les données saisies par l'utilisateur pour ce calcul :")
    lignes.append("")
    try:
        ent = projet.tableau_entrees()
        lignes.append(f"  {'Paramètre':<35}{'Valeur':<20}{'Unité':<10}")
        lignes.append(f"  {'—'*35}{'—'*20}{'—'*10}")
        lignes.append(f"  {'Diamètre nominal DN':<35}{ent['dn_mm']:<20}{'mm':<10}")
        lignes.append(f"  {'Diamètre intérieur D':<35}{ent['d_m'] or '—':<20}{'m':<10}")
        lignes.append(f"  {'Section S = π/4·D²':<35}{ent['section_m2'] or '—':<20}{'m²':<10}")
        lignes.append(f"  {'Rugosité k':<35}{ent['k_m']:<20}{'m':<10}")
        lignes.append(f"  {'Rapport k/D':<35}{ent['kd'] or '—':<20}{'—':<10}")
        lignes.append(f"  {'Schéma de vidange':<35}{ent['schema']:<20}{'—':<10}")
        lignes.append(f"  {'Altitude Ve (point haut)':<35}{ent['z_ve']:<20}{'m NGM':<10}")
        lignes.append(f"  {'Altitude Vi1':<35}{ent['z_vi1'] or '—':<20}{'m NGM':<10}")
        lignes.append(f"  {'Altitude Vi2':<35}{ent['z_vi2'] or '—':<20}{'m NGM':<10}")
        for libd, vald, unitd in ent.get("distances", []):
            lignes.append(f"  {libd:<35}{vald or '—':<20}{unitd:<10}")
        lignes.append(f"  {'ΔH casse franche (hz)':<35}{ent['hz_casse_franche'] or '—':<20}{'m':<10}")
        lignes.append(f"  {'DN vanne de sectionnement':<35}{ent['dn_vanne'] or '—':<20}{'mm':<10}")
        lignes.append(f"  {'PN pression nominale conduite':<35}{ent['pression_nominale']:<20}{'bar':<10}")
        lignes.append(f"  {'Température eau':<35}{ent['temperature']:<20}{'°C':<10}")
        lignes.append(f"  {'Viscosité cinématique ν':<35}{ent['nu'] or '—':<20}{'m²/s':<10}")
        lignes.append(f"  {'Dépression admissible ΔH':<35}{ent['delta_h']:<20}{'mCE':<10}")
        lignes.append("")
        if ent["organes"]:
            lignes.append("  Organes proposés par le client :")
            lignes.append(f"  {'Type':<12}{'DN':<8}{'Qté':<6}{'Fournisseur':<20}{'Position':<10}")
            for o in ent["organes"]:
                lignes.append(f"  {o['type']:<12}DN{o['dn']:<6}{o['nombre']:<6}"
                              f"{o['fournisseur']:<20}{o['position']:<10}")
    except Exception as e:
        lignes.append(f"  (Tableau des entrées indisponible : {e})")
    lignes.append("")

    # =====================================================================
    # §2  ANALYSE DU RISQUE MAJEUR — CASSE FRANCHE (formules détaillées)
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("§2  ANALYSE DU RISQUE MAJEUR — CASSE FRANCHE")
    lignes.append("=" * 72)
    lignes.append("")
    lignes.append("  2.1  Hypothèse de brèche maximale gravitationnelle")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  En cas de rupture de la conduite, l'eau s'écoule par gravité")
    lignes.append("  au point bas. Le débit maximal évacué Q_eau détermine le besoin")
    lignes.append("  en air des organes de ventilation (admission d'air à la dépression")
    lignes.append(f"  nominale de {SEUIL_DEPRESSION:.1f} mCE — NF EN 805).")
    lignes.append("")
    lignes.append("  Formule de débit de brèche :")
    lignes.append("    Q_eau = A × V_écoulement")
    lignes.append("    V_écoulement = √(2 × g × H_z)")
    lignes.append("    A = section de la conduite = π/4 × D²")
    lignes.append("    H_z = différence d'altitude entre le point haut (Ve) et le point bas")
    lignes.append("          = z_Ve − z_Vi (selon le schéma de vidange)")
    lignes.append("")
    try:
        cum = projet.cumul_debits()
        lignes.append(f"  Application numérique :")
        lignes.append(f"    A = π/4 × D² = {cum['section_conduite']:.4f} m²")
        lignes.append(f"    H_z = {cum['hz']:.2f} m (selon le schéma {projet.schema})")
        lignes.append(f"    V = √(2 × 9,81 × {cum['hz']:.2f}) = {cum['v_ecoulement']:.2f} m/s")
        lignes.append(f"    Q_eau = {cum['section_conduite']:.4f} × {cum['v_ecoulement']:.2f}")
        lignes.append(f"           = {cum['besoin_casse']:,.0f} m³/h")
    except Exception as e:
        lignes.append(f"  (Calcul du débit de brèche indisponible : {e})")
    lignes.append("")

    lignes.append("  2.2  Égalité conservative imposée : Q_am = Q_av")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  Pour garantir une évacuation symétrique de l'air de part et")
    lignes.append("  d'autre de la vanne de sectionnement, on impose la répartition")
    lignes.append("  conservatrice :")
    lignes.append("    Q_am = Q_av = Q_Ve / 2")
    if projet.methode_dimensionnement != "mk_aa":
        lignes.append("  Cette hypothèse est vérifiée dans le cumul des débits (§3).")
    lignes.append("")
    try:
        ad = cum["admission"]
        lignes.append(f"  Vérification : Q_Ve = {cum.get('q_ve_m3h', cum['admission']['total']):,.0f} m³/h")
        lignes.append(f"    Q_am = {ad.get('amont', 0):,.0f} m³/h  (transite par la vanne)")
        lignes.append(f"    Q_av = {ad.get('aval', 0):,.0f} m³/h  (bypass direct conduite)")
        if ad.get('amont', 0) > 0 and ad.get('aval', 0) > 0:
            ratio = max(ad.get('amont', 0), ad.get('aval', 0)) / min(ad.get('amont', 0), ad.get('aval', 0))
            lignes.append(f"    Ratio Q_am / Q_av = {ratio:.2f} — "
                          f"{'≈ 1 (symétrie respectée)' if abs(ratio - 1) < 0.3 else 'asymétrie significative'}")
    except Exception:
        pass
    lignes.append("")

    lignes.append("  2.3  Choix du schéma de vidange")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append(f"  Schéma retenu : {projet.schema}")
    lignes.append(f"  Hypothèse de calcul : {'Amont seul (A)' if projet.schema.startswith('1') else 'Aval seul (B)' if projet.schema.startswith('2') else 'Amont + Aval (C)' if projet.schema.startswith('3') else 'Asymétrique (D)'}")
    lignes.append(f"  {'Sans point intermédiaire' if projet.schema[-1] == 'A' else 'Avec point(s) intermédiaire(s)'}")
    lignes.append("")
    lignes.append("-" * 72)
    lignes.append(f"CALCUL — SCHÉMA {schemas_resultat.cas}")
    lignes.append("-" * 72)
    for step in schemas_resultat.journal:
        lignes.append("  " + step)
    lignes.append("")
    lignes.append(f"RÉSULTAT : Q_Ve = {schemas_resultat.q_ve_m3h:.1f} m³/h "
                  f"(Q_am={schemas_resultat.q_am_m3h:.1f} · Q_av={schemas_resultat.q_av_m3h:.1f})")
    lignes.append("")
    # ==== §3 Débits cumulés — Q MK_A.A en mode MK_A.A ; brèche sinon ====
    if projet.methode_dimensionnement == "mk_aa":
        _ecrire_debits_cumules_mk_aa_txt(projet, lignes)
    else:
        _ecrire_verif_air_txt(projet, lignes)
    lignes.append("")

    # =====================================================================
    # §4  VÉRIFICATIONS STRUCTURELLES ET AÉRAULIQUES
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("§4  VÉRIFICATIONS STRUCTURELLES ET AÉRAULIQUES")
    lignes.append("=" * 72)
    lignes.append("")

    lignes.append("  4.1  Résistance au vide — Flambement (AWWA M11 Ch.6 / NF EN 1295-1)")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  La dépression maximale admissible dans la conduite ne doit pas")
    lignes.append("  provoquer le collapse (flambement) du tube sous l'effet de la")
    lignes.append("  pression externe (terre + eau extérieure) ou du vide intérieur.")
    lignes.append("")
    lignes.append("  Critère de vérification simplifiée :")
    lignes.append("    ΔH_max < 50% × P_nominale (convertie en mCE)")
    lignes.append("    P_nominale = pression de service nominale du tube (bar)")
    lignes.append("    1 bar ≈ 10,197 mCE (conversion eau à 4°C)")
    lignes.append("")
    try:
        fl = projet.verifier_flambement()
        lignes.append(f"  ΔH_max (dépression admissible) = {fl['delta_h_max']:.2f} mCE")
        lignes.append(f"  P_nominale = {fl['p_nominale_bar']:.1f} bar")
        lignes.append(f"  P_nominale (mCE) = {fl['p_collapse_mce']:.1f} mCE")
        lignes.append(f"  Marge sécurité (50%) = {fl['marge_mce']:.1f} mCE")
        lignes.append(f"  → {fl['message']}")
        lignes.append(f"  Référence : {fl['reference']}")
    except Exception as e:
        lignes.append(f"  (Vérification flambement indisponible : {e})")
    lignes.append("")

    lignes.append("  4.2  Perte de charge locale — Passage d'air à la vanne")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  La perte de charge subie par l'air en traversant la vanne de")
    lignes.append("  sectionnement est estimée par la formule de perte locale :")
    lignes.append("    Δp = K × ρ_air × V² / 2")
    lignes.append("    K = coefficient de perte (0,3 vanne ouverte — 2,5 vanne fermée/étranglée)")
    lignes.append("    ρ_air = 1,225 kg/m³ (air à 15°C, 1 atm)")
    lignes.append("    V = vitesse d'air dans le collet (section la plus étroite)")
    lignes.append("")
    try:
        pc = projet.perte_charge_vanne()
        lignes.append(f"  K = {pc['k']:.1f}  (vanne {'ouverte' if pc['k'] < 1 else 'partiellement fermée'})")
        lignes.append(f"  ρ_air = {pc['rho_air']:.3f} kg/m³")
        lignes.append(f"  V_collet = {pc['v_collet']:.1f} m/s")
        lignes.append(f"  Δp = {pc['k']:.1f} × {pc['rho_air']:.3f} × {pc['v_collet']:.1f}² / 2")
        lignes.append(f"     = {pc['delta_p_pa']:.1f} Pa = {pc['delta_p_mmceau']:.2f} mmCE eau")
        lignes.append(f"  → {pc['message']}")
        lignes.append(f"  Référence : {pc['reference']}")
    except Exception as e:
        lignes.append(f"  (Calcul perte de charge indisponible : {e})")
    lignes.append("")

    # =====================================================================
    # §5  DIMENSIONNEMENT, IMPLANTATION ET NORMES
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("§5  IMPLANTATION ET VÉRIFICATION DES ORGANES")
    lignes.append("=" * 72)
    lignes.append("")
    lignes.append("  (Les organes théoriques ne sont pas dimensionnés dans ce rapport :")
    lignes.append("  la proposition client est vérifiée directement, en besoins bruts")
    lignes.append("  sans majoration — Fs ≥ 1,00 → conforme. Le contrôleur juge la")
    lignes.append("  valeur du Fs dans ses écrits et observations.)")
    lignes.append("")

    lignes.append("  5.1  Remplissage (§9)")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append(f"  Débit de remplissage (V=2 m/s) : {remplissage['q']:.0f} m³/h")
    if remplissage.get("purgeurs"):
        sel = remplissage["purgeurs"]
        lignes.append(f"  Purgeur PSA : {sel.nombre} × {sel.nom} DN{sel.dn} "
                      f"(cap. unit. {sel.capacite_unitaire_m3h:.0f} m³/h)")
    if remplissage.get("purgeurs_snh"):
        sn = remplissage["purgeurs_snh"]
        lignes.append(f"  Purgeur sonic SNH : {sn.nombre} × {sn.nom} DN{sn.dn} "
                      f"(Q_fill sonique {sn.capacite_unitaire_m3h:.1f} m³/h)")
    lignes.append("")

    lignes.append("  5.2  Implantation & justification amont/aval")
    lignes.append("  ————————————————————————————————————————————————")
    try:
        plan = etat.plan_pose()
        lignes.append(f"  {plan['repere']}")
        for pos, libellé in (("amont", "Organes AMONT (côté point haut Ve)"),
                             ("aval", "Organes AVAL (côté conduite)"),
                             ("pi1", "Organes PI1 — point intermédiaire amont (dédiés)"),
                             ("pi2", "Organes PI2 — point intermédiaire aval (dédiés)"),
                             ("sans_position", "Sans position renseignée")):
            items = plan["organes_par_position"].get(pos, [])
            lignes.append(f"  {libellé} :")
            if items:
                for it in items:
                    lignes.append(f"    • {it}")
            else:
                lignes.append("    (aucun)")
        if plan.get("combo"):
            for j in plan["combo"].get("justifications", []):
                lignes.append(f"  {j}")
    except Exception as e:
        lignes.append(f"  (Implantation indisponible : {e})")
    lignes.append("")

    lignes.append("  5.3  Plan d'implantation — coordonnées X, Y, Z (exécution)")
    lignes.append("  ————————————————————————————————————————————————")
    try:
        xyz = etat.plan_xyz()
        lignes.append(f"  {xyz['base']}")
        lignes.append(f"  {'Rép.':<6}{'Organe':<12}{'DN':<7}{'Nbr':<5}{'Pos.':<8}"
                      f"{'X (m)':<8}{'Y (m)':<8}{'Z (m)':<8}Remarque")
        for o in xyz["organes"]:
            lignes.append(
                f"  {o['ref']:<6}{o['type']:<12}DN{o['dn']:<5}{o['nombre']:<5}"
                f"{o['position']:<8}{o['x_m']:<8.1f}{o['y_m']:<8.0f}"
                f"{o['z_m'] if o['z_m'] is not None else '—':<8}{o['remarque']}")
    except Exception as e:
        lignes.append(f"  (Plan d'implantation indisponible : {e})")
    lignes.append("")

    lignes.append("  5.4  Vérification des organes (proposition client)")
    lignes.append("  ————————————————————————————————————————————————")
    lignes.append("  Vérification sur le besoin BRUT des points hauts (casse franche,")
    lignes.append("  sans majoration) : Fs = Capacité installée / Demande du point ;")
    lignes.append("  Fs ≥ 1,00 → conforme. Les purgeurs soniques (remplissage) n'ont")
    lignes.append("  pas de Fs. Le contrôleur juge la valeur du Fs dans ses écrits.")
    rt = etat.resultat
    q_p = [("Q_Ve", rt.q_ve_m3h or 0.0), ("Q_PI1", rt.q_pi1_m3h or 0.0),
           ("Q_PI2", rt.q_pi2_m3h or 0.0)]
    q_p = [(l, v) for l, v in q_p if v > 0]
    lignes.append("  Besoins bruts par point : "
                  + (" ; ".join(f"{l} = {v:,.2f} m³/h" for l, v in q_p) or "—")
                  + f" → besoin réel du tronçon = {sum(v for _, v in q_p):,.2f} m³/h.")
    lignes.append("")
    lignes.append("  Rép.      Demande (m³/h)  Catégorie   DN   Nbr  Implantation"
                  "    Fournisseur   Capacité (m³/h)  Fs    Verdict")
    try:
        for r in etat.tableau_verification_organes():
            dem = f"{r['demande_m3h']:.2f}" if r["demande_m3h"] is not None else ""
            cap = f"{r['capacite_m3h']:,.2f}" if r["capacite_m3h"] is not None else ""
            fs = f"{r['fs']:.2f}" if r["fs"] is not None else ""
            lignes.append(
                f"  {r['repere']:<10}{dem:<15}{r['categorie']:<11}"
                f"{str(r['dn'] or '—'):<6}{r['nombre']:<5}{r['implantation']:<14}"
                f"{r['fournisseur']:<15}{cap:<16}{fs:<7}{r['verdict']}")
    except Exception as e:
        lignes.append(f"  (Vérification indisponible : {e})")
    lignes.append("")

    # Croquis du profil
    try:
        lignes.append(croquis.croquis_profil(etat))
        try:
            grp = croquis._groupe_a_dessiner(etat)
            if grp["organes"]:
                lignes.append("  Organes sur le profil (montage "
                              + ("retenu proposé — optimisé" if grp["optimise"]
                                 else "validé — proposition client conforme") + ") :")
                for o in grp["organes"]:
                    pos = (o.get("position") or "sans position")
                    lignes.append(f"    • {o.get('nombre', 0)}×DN{o.get('dn') or '—'} "
                                  f"[{pos}]")
        except Exception:
            pass
    except Exception as e:
        lignes.append(f"(Croquis indisponible : {e})")
    lignes.append("")

    # =====================================================================
    # VÉRIFICATIONS HYDRAULIQUES FINALES
    # =====================================================================
    lignes.append("-" * 72)
    lignes.append("VÉRIFICATIONS HYDRAULIQUES FINALES (Re, rugosité)")
    lignes.append("-" * 72)
    for tr in schemas_resultat.troncons:
        ok = tr.re > 4000 and 1e-6 <= tr.details.get("kd", 0) <= 1e-2
        lignes.append(f"  {tr.label}: Re={tr.re:.0f} {'OK' if tr.re>4000 else 'NOK'} ; "
                      f"k/D={tr.details.get('kd', 0):.3e} "
                      f"{'OK' if ok else 'NOK'}")
    lignes.append("")

    # =====================================================================
    # NORMES ET RÉFÉRENCES TECHNIQUES
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("NORMES ET RÉFÉRENCES TECHNIQUES")
    lignes.append("=" * 72)
    try:
        refs = projet.references_completes()
    except Exception:
        refs = list(REFERENCES_NORMATIVES)
    for i, ref in enumerate(refs, start=1):
        lignes.append(f"  {i:2d}. {ref}")
    lignes.append("")

    # =====================================================================
    # ANNEXES CATALOGUE
    # =====================================================================
    lignes.append("=" * 72)
    lignes.append("ANNEXES — CATALOGUES FOURNISSEURS (vérification des variantes)")
    lignes.append("=" * 72)
    lignes.append("TRIFON et CEAI présentés en entrées distinctes ; DNs retenus "
                  "dans les variantes signalés « [retenu xN] ».")
    lignes.append("")
    try:
        sections = etat.catalogue_verification()
        if not sections:
            raise RuntimeError("catalogue vide")
        for sec in sections:
            lignes.append(f"  {sec['nom']} — {sec['role_lib']} "
                          f"(statut : {sec['statut'] or '—'})")
            for it in sec["items"]:
                marque = f" [retenu ×{it['nombre']}]" if it["retenu"] else ""
                lignes.append(f"    DN{it['dn']}: {it['q_capacity']:,.0f} m³/h{marque}")
            lignes.append("")
    except Exception:
        # Repli : catalogue interne (méthode fixe) — TRIFON/CEAI/PSA
        lignes.append(f"  Ventouse TRIFON (FIRM) — grand orifice @ −{DEPRESSION_NOMINALE:.0f} mce :")
        for dn, v in TRIFON.items():
            lignes.append(f"    DN{dn}: {v['q'][DEPRESSION_NOMINALE]} m³/h")
        lignes.append(f"  Clapet CEAI (Ramus) @ −{DEPRESSION_NOMINALE:.0f} mce :")
        for dn, v in CEAI.items():
            lignes.append(f"    DN{dn}: {v['q'][DEPRESSION_NOMINALE]} m³/h")
        lignes.append("  Purgeur PSA (Ramus) — remplissage :")
        for dn, v in PSA.items():
            lignes.append(f"    DN{dn}: {v['q_remplissage']} m³/h")
    lignes.append("")
    lignes.append("--- Fin de la note de calcul ---")
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Rapport « profil complet » — chaîne de tronçons (multi-TR)
# ---------------------------------------------------------------------------

def generer_rapport_profil(pc, etat=None, temperature: float = None) -> str:
    """Rapport texte d'une chaîne de tronçons (méthode profil complet).

    pc    : ResultatProfilComplet (app.core.profil_complet).
    etat  : EtatApplication (optionnel — pour l'identification du projet).
    """
    lignes = []
    lignes.append("=" * 72)
    lignes.append("NOTE DE CALCUL — PROFIL COMPLET (CHAÎNE DE TRONÇONS)")
    lignes.append("Débits d'air admis en conduites AEP — Dimensionnement des organes")
    lignes.append("Méthode MK_A.A 2026")
    lignes.append("=" * 72)
    lignes.append("")

    if etat is not None:
        lignes.append(f"  Maître d'ouvrage : {etat.moe or '—'}")
        lignes.append(f"  Projet / marché  : {etat.projet or '—'}")
        lignes.append(f"  Référence / indice: {etat.reference or '—'}")
        lignes.append(f"  Branche(s)       : {etat.branches or '—'}")
    lignes.append(f"  Conduite DN {pc.dn_mm:g} mm · T = {pc.temperature:.1f} °C · "
                  f"PN {pc.pression_nominale:g} bar")
    lignes.append(f"  Chaîne de tronçons : {(' → '.join(rt.label for rt in pc.troncons)) if pc.troncons else '—'}")
    lignes.append(f"  Longueur développée totale : {pc.longueur_totale:,.0f} m")
    lignes.append("")

    # --- Entrées par tronçon ---
    lignes.append("=" * 72)
    lignes.append("§1  ENTRÉES PAR TRONÇON (schéma, profil, distances)")
    lignes.append("=" * 72)
    for rt in pc.troncons:
        t = rt.troncon
        lignes.append(f"  {t.label} — schéma {t.schema} "
                      f"(Vi1={t.z_vi1:.1f}, Ve={t.z_ve:.1f}, Vi2={t.z_vi2:.1f} m NGM ; "
                      f"a={t.a:.0f} b={t.b:.0f} c={t.c:.0f} d={t.d:.0f} "
                      f"l1={t.l1:.0f} l2={t.l2:.0f} m)")
    lignes.append("")

    # --- Résultats ---
    lignes.append("=" * 72)
    lignes.append("§2  RÉSULTATS PAR TRONÇON (formule explicite MK_A.A 2026)")
    lignes.append("=" * 72)
    lignes.append(f"  {'TR':<6}{'Schéma':<8}{'Q_Ve':>10}{'Q_am':>10}{'Q_av':>10}"
                  f"{'Q_PI1':>10}{'Q_PI2':>10}")
    lignes.append(f"  {'—' * 5:<6}{'—' * 6:<8}{'—' * 8:>10}{'—' * 8:>10}{'—' * 8:>10}"
                  f"{'—' * 8:>10}{'—' * 8:>10}")
    q_max = 0.0
    for rt in pc.troncons:
        r = rt.res
        q_max = max(q_max, r.q_ve_m3h)
        lignes.append(f"  {rt.label:<6}{r.cas:<8}{r.q_ve_m3h:>10,.0f}"
                      f"{r.q_am_m3h:>10,.0f}{r.q_av_m3h:>10,.0f}"
                      f"{r.q_pi1_m3h:>10,.0f}{r.q_pi2_m3h:>10,.0f}")
    lignes.append("")
    lignes.append(f"  Débit maximal retenu le long du profil : Q_Ve,max = {q_max:,.1f} m³/h")
    lignes.append("")

    # Journaux de calcul détaillés
    for rt in pc.troncons:
        lignes.append("-" * 72)
        lignes.append(f"CALCUL DÉTAILLÉ — TRONÇON {rt.label} (schéma {rt.res.cas})")
        lignes.append("-" * 72)
        for step in rt.res.journal:
            lignes.append("  " + step)
        lignes.append(f"RÉSULTAT {rt.label} : Q_Ve = {rt.res.q_ve_m3h:.1f} m³/h "
                      f"(amont {rt.res.q_am_m3h:.1f} · aval {rt.res.q_av_m3h:.1f} · "
                      f"PI1 {rt.res.q_pi1_m3h:.1f} · PI2 {rt.res.q_pi2_m3h:.1f})")
        lignes.append("")

    # --- Dimensionnement par tronçon ---
    lignes.append("=" * 72)
    lignes.append("§3  DIMENSIONNEMENT DES ORGANES PAR TRONÇON "
                  "(marge +15 %, plafond 90 %)")
    lignes.append("=" * 72)
    for rt in pc.troncons:
        lignes.append(f"  {rt.label} — besoin Q_Ve = {rt.res.q_ve_m3h:,.0f} m³/h (majoré "
                      f"+15 % = {rt.organes['ventouse'].besoin_m3h:,.0f} m³/h) :")
        for nom, sel in rt.organes.items():
            lignes.append(f"    {nom} : {sel.nombre} × {sel.nom} DN{sel.dn} — "
                          f"cap. inst. {sel.capacite_installee_m3h:,.0f} m³/h "
                          f"(taux {sel.taux_utilisation:.1f} %)")
        remp = rt.remplissage
        p = remp["purgeurs"]; sn = remp.get("purgeurs_snh")
        lignes.append(f"    Remplissage (§9) : Q = {remp['q']:,.0f} m³/h → PSA "
                      f"{p.nombre} × {p.nom} DN{p.dn}"
                      + (f"; purgeur sonique SNH {sn.nombre} × {sn.nom} DN{sn.dn}" if sn else ""))
    lignes.append("")

    # --- Vérification structurelle (flambement) ---
    lignes.append("=" * 72)
    lignes.append("§4  VÉRIFICATION STRUCTURELLE — FLAMBEMENT (résistance au vide)")
    lignes.append("=" * 72)
    p_nom_bar = pc.pression_nominale or 10.0
    p_collapse = p_nom_bar * 10.197
    marge = p_collapse * 0.50
    conforme = SEUIL_DEPRESSION < marge
    lignes.append(f"  ΔH_max = {SEUIL_DEPRESSION:.2f} mCE < 50 % × PN "
                  f"= {marge:.1f} mCE → "
                  f"{'CONFORME' if conforme else 'NON CONFORME'} "
                  f"(PN {p_nom_bar:g} bar = {p_collapse:.1f} mCE).")
    lignes.append("  Référence : AWWA M11 Ch.6 / NF EN 1295-1 (vérification simplifiée).")
    lignes.append("")

    # --- Synthèse organes + vidanges ---
    lignes.append("=" * 72)
    lignes.append("§5  SYNTHÈSE DES ORGANES LE LONG DU PROFIL")
    lignes.append("=" * 72)
    lignes.append(f"  {'Rep':<6}{'TR':<6}{'Point':<22}{'Organe':<26}{'DN':<6}{'Qté':<5}"
                  f"{'Besoin':>10}")
    for o in pc.synthese_organes():
        lignes.append(f"  {o['rep']:<6}{o['tr']:<6}{o['point']:<22}{o['type']:<26}"
                      f"DN{str(o['dn']):<5}{o['nombre']:<5}{o['besoin_m3h']:>10,.0f}")
    lignes.append("")

    vid = pc.synthese_vidanges()
    if vid:
        lignes.append("-" * 72)
        lignes.append("  VIDANGES COMMUNES (une seule entrée par point bas)")
        lignes.append("-" * 72)
        for v in vid:
            st = "OK" if v["continue"] else "⚠ NON CONTINUE"
            lignes.append(f"  {v['point']:<26} Z = {v['z']:.1f} m NGM — "
                          f"Q évacuation = {v['q_evacuation']:,.0f} m³/h  [{st}]")
        lignes.append("")

    # --- Croquis ASCII du profil complet ---
    try:
        lignes.append(croquis.croquis_chain_ascii(pc))
    except Exception as e:
        lignes.append(f"(Croquis du profil complet indisponible : {e})")
    lignes.append("")

    # --- Vérification de la proposition client ---
    if pc.propositions and any(p for p in pc.propositions):
        lignes.append(verification_txt(pc))
        lignes.append("")

    # --- Cohérence de la chaîne ---
    if pc.avertissements:
        lignes.append("=" * 72)
        lignes.append("COHÉRENCE DE LA CHAÎNE — AVERTISSEMENTS")
        lignes.append("=" * 72)
        for a in pc.avertissements:
            lignes.append(f"  ⚠ {a}")
        lignes.append("")

    # --- Références normatives ---
    lignes.append("=" * 72)
    lignes.append("NORMES ET RÉFÉRENCES TECHNIQUES")
    lignes.append("=" * 72)
    for i, ref in enumerate(REFERENCES_NORMATIVES, start=1):
        lignes.append(f"  {i:2d}. {ref}")
    lignes.append("")
    lignes.append("--- Fin de la note de calcul (profil complet) ---")
    return "\n".join(lignes)
