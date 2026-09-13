"""Frames de résultats : Calcul (journal pas-à-pas) et Dimensionnement + Remplissage."""

import customtkinter as ctk

from ..data import valve_db


class CalculFrame(ctk.CTkFrame):
    """Affichage du journal de calcul pas-à-pas (livrable n°2)."""

    def __init__(self, master, etat=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat

        ctk.CTkLabel(self, text="Résultat du calcul",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text="Journal de calcul pas-à-pas — Formule MK_A.A (2026).",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 8))

        self.frame_resume = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_resume.pack(fill="x", padx=16, pady=(4, 8))

        self.lbl_qve = ctk.CTkLabel(self, text="Q_Ve = —",
                                    font=ctk.CTkFont(size=22, weight="bold"),
                                    text_color="#2ECC71")
        self.lbl_qve.pack(anchor="w", padx=16, pady=(0, 4))
        self.lbl_detail = ctk.CTkLabel(self, text="", justify="left", text_color="gray70")
        self.lbl_detail.pack(anchor="w", padx=16, pady=(0, 8))

        self.txt = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(family="Consolas", size=13))
        self.txt.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    def afficher(self, res):
        if res is None:
            self.lbl_qve.configure(text="—")
            self.txt.delete("1.0", "end")
            return
        self.lbl_qve.configure(text=f"Q_Ve = {res.q_ve_m3h:,.1f} m³/h")
        self.lbl_detail.configure(
            text=(f"Schéma {res.cas}   ·   amont {res.q_am_m3h:,.1f} m³/h   ·   "
                  f"aval {res.q_av_m3h:,.1f} m³/h   ·   "
                  f"PI1 {res.q_pi1_m3h:,.1f} m³/h   ·   PI2 {res.q_pi2_m3h:,.1f} m³/h"))
        self.txt.delete("1.0", "end")
        for ligne in res.journal:
            self.txt.insert("end", ligne + "\n")
        self.txt.configure(state="disabled")


class DimensionnementFrame(ctk.CTkFrame):
    """Résultat du dimensionnement des organes (§8) et remplissage (§9)."""

    NOMS_FOURNISSEURS = ["— Standard —"] + \
        [f["nom"] for f in valve_db.FOURNISSEURS
         if f["nom"] not in ("TRIFON", "CEAI")]

    def __init__(self, master, etat=None, on_calc=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self._on_calc = on_calc

        ctk.CTkLabel(self, text="Dimensionnement des organes",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text="§8 — Fournisseur sélectionnable par organe "
                     "(ventouse / clapet) : catalogue standard ou base fournisseurs "
                     "valve_database.json — §9 Remplissage & purgeur sonique.",
                     text_color="gray", wraplength=820, justify="left").pack(anchor="w", padx=16, pady=(0, 8))

        barre = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(barre, text="Ventouse").pack(side="left", padx=(0, 6))
        self.men_v = ctk.CTkOptionMenu(barre, values=self.NOMS_FOURNISSEURS,
                                       width=200, command=self._on_v)
        self.men_v.set(self._label("fournisseur_ventouse"))
        self.men_v.pack(side="left", padx=(0, 18))

        ctk.CTkLabel(barre, text="Clapet").pack(side="left", padx=(0, 6))
        self.men_c = ctk.CTkOptionMenu(barre, values=self.NOMS_FOURNISSEURS,
                                       width=200, command=self._on_c)
        self.men_c.set(self._label("fournisseur_clapet"))
        self.men_c.pack(side="left")
        barre.pack(anchor="w", padx=16, pady=(4, 8))
        ctk.CTkLabel(self, text="Le calcul est relancé et la vérification/"
                     "dimensionnement utilisent ces fournisseurs.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 8))

        self.lbl_vnom = ctk.CTkLabel(self, text="—", anchor="w", text_color="gray70")
        self.lbl_cnom = ctk.CTkLabel(self, text="—", anchor="w", text_color="gray70")
        self.lignes = {}
        for key, lbl in [("ventouse", self.lbl_vnom), ("clapet", self.lbl_cnom)]:
            f = ctk.CTkFrame(self, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=4)
            lbl.pack(side="left", anchor="w", padx=8)
            self.lignes[key] = ctk.CTkLabel(f, text="—", anchor="w", justify="left",
                                            text_color="gray90")
            self.lignes[key].pack(side="left", padx=(8, 0))

        # Ligne remplissage
        ctk.CTkLabel(self, text="Paragraphe REMPLISSAGE", text_color="gray60",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(10, 2))
        self.lignes["remplissage"] = ctk.CTkLabel(self, text="—", anchor="w", justify="left",
                                                  text_color="gray90")
        self.lignes["remplissage"].pack(anchor="w", padx=24)
        self.lignes["purgeur"] = ctk.CTkLabel(self, text="—", anchor="w", justify="left",
                                              text_color="gray90")
        self.lignes["purgeur"].pack(anchor="w", padx=24, pady=(2, 6))
        self.lignes["purgeur_snh"] = ctk.CTkLabel(self, text="—", anchor="w",
                                                  justify="left", text_color="gray90")
        self.lignes["purgeur_snh"].pack(anchor="w", padx=24, pady=(2, 6))

    def _label(self, champ):
        if self.etat is not None and (getattr(self.etat, champ) or "").strip() \
                and getattr(self.etat, champ) != "— Standard —":
            return getattr(self.etat, champ)
        return self.NOMS_FOURNISSEURS[0]

    def _on_v(self, valeur):
        if self.etat is None:
            return
        self.etat.fournisseur_ventouse = "" if valeur.startswith("—") else valeur
        if self._on_calc:
            self._on_calc()

    def _on_c(self, valeur):
        if self.etat is None:
            return
        self.etat.fournisseur_clapet = "" if valeur.startswith("—") else valeur
        if self._on_calc:
            self._on_calc()

    def afficher(self, trace):
        self.men_v.set(self._label("fournisseur_ventouse"))
        self.men_c.set(self._label("fournisseur_clapet"))
        if trace is None:
            for k in self.lignes:
                self.lignes[k].configure(text="—")
            self.lbl_vnom.configure(text="—")
            self.lbl_cnom.configure(text="—")
            return
        org = trace["organes"]
        v = org["ventouse"]; c = org["clapet"]
        self.lbl_vnom.configure(text=f"Ventouse — {v.nom}")
        self.lbl_cnom.configure(text=f"Clapet — {c.nom}")
        self.lignes["ventouse"].configure(
            text=(f"{v.nombre} × {v.nom} DN{v.dn} — cap. inst. {v.capacite_installee_m3h:,.0f} m³/h "
                  f"(need {v.besoin_m3h:,.0f} +15%, taux {v.taux_utilisation:.0f}%)"))
        self.lignes["clapet"].configure(
            text=(f"{c.nombre} × {c.nom} DN{c.dn} — cap. inst. {c.capacite_installee_m3h:,.0f} m³/h "
                  f"(need {c.besoin_m3h:,.0f} +15%, taux {c.taux_utilisation:.0f}%)"))
        remp = trace["remplissage"]
        self.lignes["remplissage"].configure(
            text=f"Débit de remplissage (V_eau = 2 m/s) : {remp['q']:,.0f} m³/h")
        p = remp["purgeurs"]
        self.lignes["purgeur"].configure(
            text=f"Purgeur PSA : {p.nombre} × {p.nom} DN{p.dn} (cap. unit. {p.capacite_unitaire_m3h:,.0f} m³/h)")
        sn = remp.get("purgeurs_snh")
        if sn is not None:
            self.lignes["purgeur_snh"].configure(
                text=("Purgeur sonique SNH (NSH) — physique : "
                      f"{sn.nombre} × {sn.nom} DN{sn.dn} "
                      f"(Q_fill sonique {sn.capacite_unitaire_m3h:,.1f} m³/h, "
                      "Q_fill = q_cap·P_fill/P_svc) ; le débit à P≈atm est faible "
                      "→ grand orifice TRIFON pour l'évacuation massive"))
