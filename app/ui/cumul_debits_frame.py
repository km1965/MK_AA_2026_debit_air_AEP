"""Frame Cumul des débits d'air — note « Débits cumulés » (§note technique).

Vérifie que le cumul des débits d'air des appareils au point haut couvre le débit
d'eau de vidange en casse franche : Q_eau = A·√(2·g·H_z), et contrôle la vanne
de sectionnement / collecteur (pas d'étranglement, vitesse air < 40 m/s).
"""

import math
import customtkinter as ctk
from tkinter import messagebox

from ..controller import EtatApplication
from .widgets import EntryFlottante, champ_ligne


class CumulDebitsFrame(ctk.CTkFrame):
    """Onglet « 9 · Cumul des débits » — deux modes de dimensionnement.

    - Mode « MK_A.A » : dimensionnement des VENTOUSES par la formule
      explicite MK_A.A (2026) seule (pas de cumul, pas de brèche).
    - Mode « Brèche » : dimensionnement par vidange brèche (Torricelli)
      pour les débits cumulés du groupe d'admission.
    """

    def __init__(self, master, etat: EtatApplication, on_calc=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self._on_calc = on_calc
        self._res = None  # résultat cumul_debits() une fois calculé

        ctk.CTkLabel(self, text="Dimensionnement des débits d'air",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))

        # --- Sélecteur de mode (synchro avec la méthode persistée du projet) ---
        methode_init = getattr(etat, "methode_dimensionnement", "mk_aa") or "mk_aa"
        self.mode = ctk.StringVar(value=("breche" if methode_init == "breche" else "mk_aa"))
        sel = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(sel, text="Mode de dimensionnement :").pack(side="left", padx=(0, 8))
        for val, lbl in [("mk_aa", "Formule MK_A.A (ventouses)"),
                         ("breche", "Vidange brèche — Torricelli (cumul)")]:
            ctk.CTkRadioButton(sel, text=lbl, variable=self.mode, value=val,
                               command=self._changer_mode).pack(side="left", padx=(4, 16))
        sel.pack(anchor="w", padx=16, pady=(0, 6))

        # --- Saisie (H_z, vanne, PN) — utilisée en mode brèche ---
        saisie = ctk.CTkFrame(self, fg_color="transparent")
        _, self.ent_hz = champ_ligne(saisie,
                                     "H_z dénivelé point haut → rupture",
                                     valeur=10.0, unite="m", width=100)
        self.sync_hz()
        ctk.CTkLabel(saisie,
                     text="auto : Z_Ve − point bas (profil) ; modifiable",
                     text_color="gray", font=ctk.CTkFont(size=10)).pack(
            anchor="w", padx=4, pady=(0, 2))
        _, self.ent_vanne_dn = champ_ligne(saisie, "DN vanne sectionnement / collecteur",
                                           valeur=1600.0, unite="mm", width=100)
        _, self.ent_pn = champ_ligne(saisie, "PN pression nominale conduite",
                                     valeur=10.0, unite="bar", width=100)
        saisie.pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkButton(saisie, text="Calculer",
                      command=self._calculer,
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(0, 4))

        # --- Zone résultats ---
        self.zone = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.zone.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        ctk.CTkLabel(self.zone, text="(Cliquer « Calculer » après saisie.)",
                     text_color="gray").pack(anchor="w", pady=8)

    # ------------------------------------------------------------------
    def sync_hz(self):
        """Pré-remplit H_z depuis le profil (auto : Z_Ve − point bas).

        La valeur par défaut 10,0 m est traitée comme un placeholder et
        remplacée automatiquement. Toute autre valeur (saisie manuelle ou
        persistée) est conservée telle quelle.
        """
        auto = self.etat.hz_casse_franche_auto()
        courante = self.ent_hz.valeur(10.0)
        if abs(courante - 10.0) < 1e-9:
            self.ent_hz.delete(0, "end")
            self.ent_hz.insert(0, f"{auto:g}")
            self.etat.hz_casse_franche = auto

    # ------------------------------------------------------------------
    def _changer_mode(self):
        self.etat.methode_dimensionnement = self.mode.get()
        for w in self.zone.winfo_children():
            w.destroy()
        if self.mode.get() == "mk_aa":
            if self.etat.resultat is None:
                self.etat.calculer()
            self._afficher_mk_aa()
        else:
            self._calculer()

    # ------------------------------------------------------------------
    def _calculer(self):
        """Exécute le calcul par mode et affiche le résultat."""
        # Synchroniser H_z (auto si non saisie), DN vanne et PN dans l'état
        self.sync_hz()
        self.etat.hz_casse_franche = self.ent_hz.valeur(10.0)
        self.etat.dn_vanne_sectionnement = self.ent_vanne_dn.valeur(1600.0)
        self.etat.pression_nominale = self.ent_pn.valeur(10.0)
        if self.etat.resultat is None:
            self.etat.calculer()
        if self.mode.get() == "mk_aa":
            self._afficher_mk_aa()
            return
        self._res = self.etat.cumul_debits()
        self._afficher_breche()

    # ------------------------------------------------------------------
    # MODE MK_A.A — ventouses uniquement, détail complet du calcul
    # ------------------------------------------------------------------
    def _afficher_mk_aa(self):
        for w in self.zone.winfo_children():
            w.destroy()
        res = self.etat.resultat
        if res is None:
            self._ligne("Erreur", "Aucun résultat — le calcul n'a pas abouti.", color="#E74C3C")
            return
        self._bloc_titre("Mode de dimensionnement : Formule explicite MK_A.A (2026)")
        self._ligne("Schéma de vidange", str(res.cas))
        self._ligne("CE QUI EST DIMENSIONNÉ ICI",
                    "Les VENTOUSES (admission d'air), et elles seules.",
                    bold=True)
        self._ligne("Ce qui est EXCLU de ce mode",
                    "Cumul des débits du groupe / vidange par brèche (Torricelli) "
                    "→ voir l'autre mode.",
                    color="gray70")

        self._bloc_titre("Débit admis au point haut — Q_Ve")
        self._ligne("Q_Ve (formule MK_A.A)", f"{res.q_ve_m3h:,.1f} m³/h", bold=True)
        self._ligne("Dont amont", f"{res.q_am_m3h:,.1f} m³/h")
        self._ligne("Dont aval", f"{res.q_av_m3h:,.1f} m³/h")
        self._ligne("PI1", f"{res.q_pi1_m3h:,.1f} m³/h")
        self._ligne("PI2", f"{res.q_pi2_m3h:,.1f} m³/h")

        # Détail du journal de calcul pas-à-pas
        self._bloc_titre("Détail du calcul pas-à-pas (journal)")
        jtxt = "\n".join(res.journal) if res.journal else "(journal vide)"
        tx = ctk.CTkTextbox(self.zone, wrap="word",
                            font=ctk.CTkFont(family="Consolas", size=12),
                            height=260)
        tx.insert("1.0", jtxt)
        tx.configure(state="disabled")
        tx.pack(fill="x", padx=4, pady=4)

        # Ventouses dimensionnées
        self._bloc_titre("Dimensionnement des ventouses (marge +15 %)")
        try:
            org = self.etat.derniere_trace["organes"]
            v = org["ventouse"]
            c = org["clapet"]
            self._ligne("Ventouse",
                        f"{v.nombre} × {v.nom} DN{v.dn} — cap. inst. "
                        f"{v.capacite_installee_m3h:,.0f} m³/h "
                        f"(need {v.besoin_m3h:,.0f}, taux {v.taux_utilisation:.0f} %)",
                        bold=True)
            self._ligne("Clapet (organe associé)",
                        f"{c.nombre} × {c.nom} DN{c.dn} — cap. inst. "
                        f"{c.capacite_installee_m3h:,.0f} m³/h "
                        f"(need {c.besoin_m3h:,.0f}, taux {c.taux_utilisation:.0f} %)")
        except Exception as e:
            self._ligne("Ventouse", f"(indisponible : {e})", color="gray70")

        # --- Vérification du GROUPE installé face aux débits MK_A.A ---
        self._bloc_titre("Vérification du groupe face aux débits MK_A.A (vitesse sonique)")
        try:
            g = self.etat.verifier_groupe_mk_aa()
            col_conf = "#27AE60" if g["conforme"] else "#E74C3C"
            self._ligne("Groupe installé (ventouses + clapets + purgeurs)",
                        f"{g['admission']['total']:,.0f} m³/h", bold=True)
            self._ligne("Besoin MK_A.A Q_Ve", f"{g['besoin_mk_aa']:,.0f} m³/h")
            self._ligne("Besoin majoré (+15 %, plafond 90 %)",
                        f"{g['besoin_majore']:,.0f} m³/h → cap. min. inst. "
                        f"{g['cap_min_installee']:,.0f} m³/h")
            self._ligne("Dont ventouses / clapets / purgeurs",
                        f"{g['admission']['trifon']:,.0f} / "
                        f"{g['admission']['ceai']:,.0f} / "
                        f"{g['admission']['psa']:,.0f} m³/h")
            self._ligne("Répartition amont / aval",
                        f"{g['amont']:,.0f} / {g['aval']:,.0f} m³/h")
            self._ligne("Purgeur sonique (capacité NSH au goulot 200 m/s)",
                        f"{g['purgeur_sonique']:,.0f} m³/h")
            self._ligne("Vitesse de l'air — vanne (limite 40 m/s)",
                        f"{g['vitesse']['vanne']:.1f} m/s "
                        f"({'OK' if g['vitesse']['ok'] else 'INSUFFISANT'})")
            self._ligne("Vitesse de l'air — aval conduite (limite 40 m/s)",
                        f"{g['vitesse']['aval']:.1f} m/s "
                        f"({'OK' if g['vitesse']['ok'] else 'INSUFFISANT'})")
            self._ligne("Group CONFORME face aux débits MK_A.A",
                        "OUI" if g["conforme"] else "NON",
                        bold=True, color=col_conf)
        except Exception as e:
            self._ligne("Groupe", f"(indisponible : {e})", color="gray70")

    # ------------------------------------------------------------------
    # MODE BRÈCHE — cumul des débits (Torricelli)
    # ------------------------------------------------------------------
    def _afficher_breche(self):
        for w in self.zone.winfo_children():
            w.destroy()
        r = self._res
        dc = r["dc"]
        adm = r["admission"]
        exp = r["expulsion"]
        vanne = r["vanne"]
        vit = r["limite_vitesse"]

        self._bloc_titre("Mode de dimensionnement : Vidange brèche — Torricelli")
        self._ligne("CE QUI EST DIMENSIONNÉ ICI",
                    "Les DÉBITS CUMULÉS du groupe d'admission "
                    "(ventouses + clapets + purgeurs), face au besoin de la casse franche.",
                    bold=True)
        self._ligne("Ce qui est EXCLU de ce mode",
                    "Dimensionnement ventouse seule par formule MK_A.A "
                    "→ voir l'autre mode.",
                    color="gray70")

        # ---- Q_eau casse franche ----
        self._bloc_titre("1. Débit d'eau de vidange par la brèche (casse franche)")
        self._ligne("Diamètre intérieur conduit", f"D = {dc.d:.3f} m")
        self._ligne("Section conduite", f"A = {r['section_conduite']:.4f} m²")
        self._ligne("Dénivelé H_z (utilisé)", f"{r['hz']:.1f} m (NGM)", bold=True)
        self._ligne("Auto depuis profil (Z_Ve − point bas)",
                    f"{self.etat.hz_casse_franche_auto():.1f} m", color="gray70")
        self._ligne("Vitesse d'écoulement", f"V = √(2·g·H_z) = {r['v_ecoulement']:.2f} m/s")
        self._ligne("Débit d'eau de vidange",
                     f"Q_eau = A·V = {r['q_eau_m3s']:.4f} m³/s = {r['besoin_casse']:.1f} m³/h",
                     bold=True)
        self._ligne("Débit d'air requis ≈ Q_eau",
                     f"Q_air requis ≥ {r['besoin_casse']:.1f} m³/h", bold=True)

        # ---- Cumul admission ----
        self._bloc_titre("2. Cumul des débits d'air — admission (anti-dépression)")
        self._ligne("Ventouses TRIFON", f"{adm['trifon']:.1f} m³/h")
        self._ligne("Clapets CEAI", f"{adm['ceai']:.1f} m³/h")
        self._ligne("Purgeurs PSA", f"{adm['psa']:.1f} m³/h")
        self._ligne("TOTAL admission cumulé", f"{adm['total']:.1f} m³/h", bold=True)

        if r["strictly_missing"]:
            self._ligne("Verdict admission", "✗ AUCUN DÉBIT RENSEIGNÉ — NON CONFORME",
                         color="#E74C3C", bold=True)
        else:
            ok = r["verdict_admission"]
            statut = ("✓ CONFORME" if ok else "✗ NON CONFORME")
            couleur = "#2ECC71" if ok else "#E74C3C"
            self._ligne("Verdict admission",
                         f"{statut} — {adm['total']:.1f} m³/h ≥ {r['besoin_casse']:.1f} m³/h",
                         color=couleur, bold=True)

        # ---- Cumul expulsion ----
        self._bloc_titre("3. Cumul des débits d'air — expulsion (remplissage)")
        self._ligne("Ventouses TRIFON", f"{exp['trifon']:.1f} m³/h")
        self._ligne("Purgeurs PSA (échappement)", f"{exp['psa']:.1f} m³/h")
        self._ligne("TOTAL expulsion cumulé", f"{exp['total']:.1f} m³/h", bold=True)
        ok_exp = r["verdict_expulsion"]
        self._ligne("Verdict expulsion",
                     "✓ Présence d'équipements d'échappement"
                     if ok_exp else "✗ Aucun équipement d'expulsion renseigné",
                     color="#2ECC71" if ok_exp else "#E74C3C", bold=True)

        # ---- Vanne de sectionnement / collecteur ----
        self._bloc_titre("4. Vanne de sectionnement / collecteur")
        self._ligne("DN vanne / collecteur", f"DN {vanne['dn']:.0f} mm")
        self._ligne("Section vanne", f"{vanne['section_vanne']:.3f} m²")
        section_amont = vanne["section_amont"]
        section_aval = vanne["section_aval"]
        self._ligne("Σ sections appareils (amont)", f"{section_amont:.3f} m²")
        if section_aval > 0:
            self._ligne("Σ sections appareils (aval)", f"{section_aval:.3f} m²")
        self._ligne("Vitesse de passage à la vanne",
                     f"{vit['v_air']:.1f} m/s (transit amont "
                     f"{adm.get('amont', 0):,.0f} m³/h / {vit['v_limite']:.0f} m/s)")
        if section_aval > 0:
            self._ligne("Vitesse aval (bypass conduite)",
                         f"{vit['v_aval']:.1f} m/s ({adm.get('aval', 0):,.0f} m³/h)")
        if section_amont > 0 and vanne["section_vanne"] > 0:
            ok_e = vanne["conforme"]
            self._ligne("Ratio vanne / Σ sections amont",
                         f"{vanne['ratio']:.2f} × — "
                         + ("✓ Pas d'étranglement" if ok_e else "✗ Étranglement potentiel"))
        else:
            self._ligne("Ratio vanne / Σ sections amont",
                         "Non applicable (DN vanne ou organes amont non renseignés)")
        ok_v = vanne["conforme"]
        self._ligne("Verdict vanne",
                     "✓ Pas d'étranglement" if ok_v else "✗ Section vanne insuffisante ou non renseignée",
                     color="#2ECC71" if ok_v else "#E74C3C", bold=True)

        # ---- Contrainte de vitesse air ----
        self._bloc_titre("5. Contrainte de vitesse de passage de l'air")
        self._ligne("Vitesse limite (anti blocage sonique)",
                     f"{vit['v_limite']:.0f} m/s")
        v_air = vit["v_air"]
        v_str = f"{v_air:.1f} m/s" if v_air < 1e6 else "∞ (section vanne non renseignée)"
        self._ligne("Vitesse vanne — transit amont", v_str, bold=True)
        v_aval = vit["v_aval"]
        self._ligne("Vitesse aval — bypass conduite",
                     f"{v_aval:.1f} m/s" if v_aval < 1e6 else "—")
        ok_van = vit.get("ok_vanne", vit["ok"])
        ok_aval = vit.get("ok_aval", True)
        if not ok_aval:
            self._ligne("Verdict vitesse aval",
                         "✗ Vitesse aval excessive — blocage sonique possible",
                         color="#E74C3C", bold=True)
        self._ligne("Verdict vitesse",
                     "✓ Pas de blocage sonique"
                     if vit["ok"] else "✗ Vitesse excessive — blocage sonique possible",
                     color="#2ECC71" if vit["ok"] else "#E74C3C", bold=True)
        ok_son = vit["ok"]

        # ---- Contacts / notes ----
        self._bloc_titre("6. Notes / points de vigilance")
        for titre, valeur, note in r.get("contacts", []):
            self._ligne(titre, f"{valeur}  —  {note}", color="gray70")

        # ---- Vérification du groupe complet face aux débits MK_A.A ----
        self._bloc_titre("Vérification du groupe complet face aux débits MK_A.A (Q_Ve)")
        try:
            g = self.etat.verifier_groupe_mk_aa()
            col_conf = "#27AE60" if g["conforme"] else "#E74C3C"
            self._ligne("Groupe installé (ventouses + clapets + purgeurs)",
                        f"{g['admission']['total']:,.0f} m³/h", bold=True)
            self._ligne("Besoin MK_A.A Q_Ve (majoré +15 %, plafond 90 %)",
                        f"{g['besoin_mk_aa']:,.0f} → {g['besoin_majore']:,.0f} m³/h")
            self._ligne("Dont ventouses / clapets / purgeurs",
                        f"{g['admission']['trifon']:,.0f} / "
                        f"{g['admission']['ceai']:,.0f} / "
                        f"{g['admission']['psa']:,.0f} m³/h")
            self._ligne("Vitesse de l'air — vanne (limite 40 m/s)",
                        f"{g['vitesse']['vanne']:.1f} m/s "
                        f"({'OK' if g['vitesse']['ok'] else 'INSUFFISANT'})")
            self._ligne("Vitesse de l'air — aval conduite (limite 40 m/s)",
                        f"{g['vitesse']['aval']:.1f} m/s "
                        f"({'OK' if g['vitesse']['ok'] else 'INSUFFISANT'})")
            self._ligne("Group CONFORME vs débits MK_A.A",
                        "OUI" if g["conforme"] else "NON",
                        bold=True, color=col_conf)
        except Exception as _e:
            self._ligne("Groupe", f"(indisponible : {_e})", color="gray70")

        # Verdict global
        self._bloc_titre("Verdict global")
        global_ok = (r["verdict_admission"] and vanne["conforme"]
                     and vit["ok"])
        self._ligne("CONFORMITÉ CUMUL DÉBITS",
                     "✓ CONFORME" if global_ok else "✗ NON CONFORME",
                     color="#2ECC71" if global_ok else "#E74C3C", bold=True)

        # Groupe optimisé proposé en cas de NON-CONFORMITÉ (TRIFON + SNH)
        if not global_ok:
            opt = self.etat.groupe_optimise()
            self._bloc_titre("7. Groupe optimisé nécessaire (ventouses TRIFON + SNH)")
            self._ligne("Besoin casse franche (Q_air requis)",
                         f"{opt['besoin']:,.0f} m³/h")
            self._ligne("Capacité admission existante",
                         f"{opt['admis_existant']:,.0f} m³/h")
            self._ligne("Manque à couvrir",
                         f"{opt['manque']:,.0f} m³/h", bold=True)
            cap = opt["capacites"]
            self._ligne("Ventouses TRIFON", f"{cap['ventouse']:,.0f} m³/h")
            self._ligne("Clapets admission SNH", f"{cap['clapet_snh']:,.0f} m³/h")
            self._ligne("Purgeurs soniques SNH (dégazage)",
                         f"{cap['purgeur_snh']:,.0f} m³/h")
            rep = opt["repartition"]
            self._ligne("Répartition amont (transit vanne)",
                         f"{rep['amont']:,.0f} m³/h (≤ {rep['kap']:,.0f} m³/h @40 m/s)")
            self._ligne("Répartition aval (bypass conduite)",
                         f"{rep['aval']:,.0f} m³/h")
            if opt.get("vanne_dn"):
                self._ligne("Vanne de sectionnement recommandée",
                             f"DN {opt['vanne_dn']} (= DN principal)", bold=True)
            self._ligne("Couverture totale",
                         f"{opt['coverage']:,.0f} m³/h → "
                         f"{'montage optimisé CONFORME' if opt['conforme'] else 'compléter'}", bold=True)
            for o in opt["groupe"]:
                nom = {"trifon": "Ventouse TRIFON", "ceai": "Clapet SNH",
                       "psa": "Purgeur sonique SNH",
                       "vanne": "Vanne sectionnement"}[o["type"]]
                pos = o.get("position", "")
                lib = f"{o['nombre']} × {nom}  DN {o['dn']}"
                if pos:
                    lib += f"  [{pos}]"
                self._ligne("  •", lib, color="gray80")
            if opt["note"]:
                self._ligne("Note", opt["note"], color="gray70")
            ctk.CTkButton(self.zone, text="Appliquer le groupe optimisé (Vérification)",
                          command=self._appliquer_groupe,
                          font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))

            # --- Variante DÉJÀ COMMANDÉE : même DN, nombre ajusté ---
            try:
                var = self.etat.corriger_variante_client()
                self._bloc_titre("8. Corrigé variante DÉJÀ COMMANDÉE (mêmes DN, nombre ajusté)")
                self._ligne("Principe",
                            "On conserve les diamètres (et fournisseurs) déjà commandés ; "
                            "on augmente le NOMBRE d'organes jusqu'à couvrir le besoin.",
                            color="gray70")
                self._ligne("Besoin casse franche", f"{var['besoin']:,.0f} m³/h")
                self._ligne("Manque à couvrir", f"{var['manque']:,.0f} m³/h", bold=True)
                cap_var = var["capacites"]
                self._ligne("Ventouses", f"{cap_var['ventouse']:,.0f} m³/h")
                self._ligne("Clapets", f"{cap_var['clapet_snh']:,.0f} m³/h")
                repvar = var["repartition"]
                self._ligne("Répartition amont (transit vanne)",
                            f"{repvar['amont']:,.0f} m³/h (≤ {repvar['kap']:,.0f} m³/h @40 m/s)")
                self._ligne("Répartition aval (POINT INTERMÉDIAIRE / bypass élargi)",
                            f"{repvar['aval']:,.0f} m³/h")
                self._ligne("Vitesse vanne / aval",
                            f"{var['v_vanne']:.1f} m/s / {var['v_aval']:.1f} m/s (≤ 40)",
                            color="gray70")
                self._ligne("Couverture totale",
                            f"{var['coverage']:,.0f} m³/h → "
                            f"{'variante corrigée CONFORME' if var['conforme'] else 'encore insuffisant'}",
                            bold=True,
                            color="#2ECC71" if var["conforme"] else "#E74C3C")
                for o in var["groupe"]:
                    nom = {"trifon": "Ventouse", "ceai": "Clapet",
                           "psa": "Purgeur sonique",
                           "vanne": "Vanne sectionnement"}[o["type"]]
                    pos = o.get("position", "")
                    lib = f"{o['nombre']} × {nom}  DN {o['dn']}"
                    if pos:
                        lib += f"  [{pos}]"
                    self._ligne("  •", lib, color="gray80")
                if var["note"]:
                    self._ligne("Note", var["note"], color="gray70")
                ctk.CTkButton(
                    self.zone,
                    text="Appliquer la variante corrigée (mêmes DN) — Vérification",
                    command=self._appliquer_variante,
                    font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))
            except Exception as _e:
                self._ligne("Variante commandée", f"(indisponible : {_e})", color="gray70")

    def _appliquer_groupe(self):
        """Renseigne la liste des organes client avec le groupe optimisé."""
        if self._res is None:
            return
        opt = self.etat.groupe_optimise()
        self.etat.organes_client = list(opt["groupe"])
        if opt.get("vanne_dn"):
            self.etat.dn_vanne_sectionnement = float(opt["vanne_dn"])
        from tkinter import messagebox
        messagebox.showinfo(
            "Groupe optimisé",
            "Groupe optimisé renseigné dans l'onglet Vérification.\n"
            "Vanne de sectionnement = DN principal.\n"
            "Cliquer « Vérifier la conformité » pour le confirmer.")
        if self._on_calc:
            self._on_calc()

    def _appliquer_variante(self):
        """Renseigne l'onglet Vérification avec la variante commandée corrigée."""
        if self._res is None:
            return
        var = self.etat.corriger_variante_client()
        groupe_sans_vanne = [o for o in var["groupe"] if o.get("type") != "vanne"]
        self.etat.organes_client = list(groupe_sans_vanne)
        if var.get("vanne_dn"):
            self.etat.dn_vanne_sectionnement = float(var["vanne_dn"])
        from tkinter import messagebox
        messagebox.showinfo(
            "Variante corrigée",
            "Variante commandée (mêmes DN, nombre ajusté) renseignée dans "
            "l'onglet Vérification.\nVanne de sectionnement = DN principal.\n"
            "Cliquer « Vérifier la conformité » pour la confirmer.")
        if self._on_calc:
            self._on_calc()

    # ------------------------------------------------------------------
    # Helpers affichage
    # ------------------------------------------------------------------
    def _bloc_titre(self, txt):
        ctk.CTkLabel(self.zone, text=txt,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(anchor="w", pady=(12, 2))

    def _ligne(self, label, valeur, color=None, bold=False):
        f = ctk.CTkFrame(self.zone, fg_color="transparent")
        kw = {}
        if color:
            kw["text_color"] = color
        ctk.CTkLabel(f, text=label, anchor="w", width=340,
                     font=ctk.CTkFont(weight="bold" if bold else "normal"),
                     **kw).pack(side="left")
        kw2 = {}
        if color:
            kw2["text_color"] = color
        ctk.CTkLabel(f, text=valeur, anchor="w",
                     font=ctk.CTkFont(weight="bold" if bold else "normal"),
                     **kw2).pack(side="left")
        f.pack(anchor="w", padx=4, pady=2)
