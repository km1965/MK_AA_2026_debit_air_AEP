"""Onglet « Profil complet » — chaîne de tronçons (méthode multi-TR)."""

import customtkinter as ctk

from .widgets import EntryFlottante
from ..controller import SCHEMAS
from ..core.profil_complet import (
    ProfilTroncon, ResultatProfilComplet, calculer_profil, synthese_txt,
)
from ..utils import export as export_txt
from ..utils import export_office
from ..utils import croquis as croquis_mod


_DEFS = {"z_vi1": 100.0, "z_ve": 120.0, "z_vi2": 90.0,
         "z_pi1": 0.0, "z_pi2": 0.0,
         "a": 500.0, "b": 500.0, "c": 400.0, "d": 600.0,
         "l1": 1000.0, "l2": 1000.0}

_CHAMPS_ALT = [("z_vi1", "Z Vi1 (bas amont)", "m NGM"),
               ("z_ve", "Z Ve (point haut)", "m NGM"),
               ("z_vi2", "Z Vi2 (bas aval)", "m NGM"),
               ("z_pi1", "Z PI1", "m NGM"),
               ("z_pi2", "Z PI2", "m NGM")]
_CHAMPS_DIST = [("a", "a Vi1→PI1", "m"), ("b", "b PI1→Ve", "m"),
                ("c", "c Ve→PI2", "m"), ("d", "d PI2→Vi2", "m"),
                ("l1", "L₁ Vi1→Ve", "m"), ("l2", "L₂ Ve→Vi2", "m")]


class ProfilCompletFrame(ctk.CTkFrame):
    """Saisie de la chaîne de tronçons + calcul + synthèse + exports."""

    def __init__(self, master, etat, on_calc=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self.on_calc = on_calc
        self.entrees = {}                 # label -> {"carte", "schema", "champs"}
        self.dernier_pc: ResultatProfilComplet = None
        self._compteur = 0

        # Zone principale DÉFILANTE : toute la page (tronçons + synthèse +
        # vérification + boutons) peut déborder de l'écran → scroll vertical.
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        ctk.CTkLabel(self.scroll, text="Profil complet — chaîne de tronçons",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(self.scroll, text="Plusieurs tronçons TR1…TRn recousus "
                     "(Vi2(TRi) ≡ Vi1(TRi+1)) — formule explicite MK_A.A 2026.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 8))

        # --- Paramètres globaux ---
        bande = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bande.pack(fill="x", padx=16)
        self.globaux_entries = {}
        for key, lib, unit in [("dn_mm", "DN (mm)", "mm"),
                               ("temperature", "Température", "°C"),
                               ("pression_nominale", "PN", "bar")]:
            f = ctk.CTkFrame(bande, fg_color="transparent")
            f.pack(side="left", padx=(0, 14))
            ctk.CTkLabel(f, text=lib).pack(side="left", padx=(0, 4))
            e = EntryFlottante(f, width=90)
            defaut = getattr(etat, key, None)
            if defaut is None:
                defaut = {"dn_mm": 1400.0, "temperature": 15.0,
                          "pression_nominale": 10.0}[key]
            e.insert(0, str(defaut))
            e.pack(side="left", padx=(0, 4))
            ctk.CTkLabel(f, text=unit).pack(side="left")
            self.globaux_entries[key] = e

        # --- Zone des tronçons (le parent est déjà défilant) ---
        self.corps = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.corps.pack(fill="x", padx=16, pady=(10, 6))
        self.corps.grid_columnconfigure(0, weight=1)

        bout = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bout.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(bout, text="＋ Ajouter un tronçon",
                      command=self._ajouter).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bout, text="－ Supprimer le dernier",
                      command=self._supprimer_dernier).pack(side="left")
        self.lbl_statut = ctk.CTkLabel(bout, text="", text_color="gray")
        self.lbl_statut.pack(side="left", padx=14)

        # --- Synthèse (lecture seule) ---
        ctk.CTkLabel(self.scroll, text="Synthèse du profil complet",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=16, pady=(8, 2))
        self.txt = ctk.CTkTextbox(self.scroll, height=220,
                                  font=ctk.CTkFont(family="Consolas", size=11))
        self.txt.pack(fill="x", padx=16, pady=(0, 6))

        # --- Vérification proposition client ---
        ctk.CTkLabel(self.scroll, text="Vérification — proposition client"
                     " (organes proposés vs besoins)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=16, pady=(2, 2))
        self.txt_verif = ctk.CTkTextbox(self.scroll, height=180,
                                        font=ctk.CTkFont(family="Consolas",
                                                         size=11))
        self.txt_verif.pack(fill="x", padx=16, pady=(0, 6))

        # --- Boutons calcul + exports ---
        act_b = ctk.CTkFrame(self.scroll, fg_color="transparent")
        act_b.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(act_b, text="Calculer le profil complet",
                      command=self._calculer, font=ctk.CTkFont(weight="bold"),
                      width=200).pack(side="left", padx=(0, 10))
        ctk.CTkButton(act_b, text="Comparer la proposition client",
                      command=self._compare_client, width=200).pack(
            side="left", padx=(0, 10))
        self.lbl_concl = ctk.CTkLabel(act_b, text="", text_color="gray")
        self.lbl_concl.pack(side="left", padx=(0, 10))
        self.b_exp_txt = ctk.CTkButton(act_b, text="Rapport (.txt)",
                                       command=self._export_txt,
                                       state="disabled")
        self.b_exp_txt.pack(side="left", padx=4)
        self.b_exp_docx = ctk.CTkButton(act_b, text="Rapport (.docx)",
                                        command=self._export_docx,
                                        state="disabled")
        self.b_exp_docx.pack(side="left", padx=4)
        self.b_exp_xlsx = ctk.CTkButton(act_b, text="Rapport (.xlsx)",
                                        command=self._export_xlsx,
                                        state="disabled")
        self.b_exp_xlsx.pack(side="left", padx=4)
        self.b_exp_png = ctk.CTkButton(act_b, text="Croquis (.png)",
                                       command=self._export_png,
                                       state="disabled")
        self.b_exp_png.pack(side="left", padx=4)

        for _ in range(3):
            self._ajouter()

    # ------------------------------------------------------------------
    def _prochain_label(self) -> str:
        num = 1
        while f"TR{num}" in self.entrees:
            num += 1
        return f"TR{num}"

    def _ajouter(self, defauts=None):
        label = self._prochain_label()
        d = dict(_DEFS)
        if defauts:
            d.update(defauts)
        carte = ctk.CTkFrame(self.corps, corner_radius=8, border_width=1)
        carte.grid(sticky="ew", padx=4, pady=6)

        tete = ctk.CTkFrame(carte, fg_color="transparent")
        tete.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(tete, text=label,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkLabel(tete, text="Schéma").pack(side="left", padx=(18, 4))
        om = ctk.CTkOptionMenu(tete, values=list(SCHEMAS), width=70)
        om.set((defauts or {}).get("schema", "3B"))
        om.pack(side="left")
        ctk.CTkButton(tete, text="Supprimer", width=80, fg_color="gray28",
                      command=lambda: self._supprimer(label)).pack(side="right")

        ligne_alt = ctk.CTkFrame(carte, fg_color="transparent")
        ligne_alt.pack(fill="x", padx=10)
        champs = {}
        for i, (key, lib, unit) in enumerate(_CHAMPS_ALT):
            f, e = self._champ(ligne_alt, lib, d[key], unit,
                               label_width=104, entry_width=62)
            f.grid(row=0, column=i, sticky="w", padx=(0, 8), pady=2)
            champs[key] = e
            ligne_alt.grid_columnconfigure(i, weight=1)

        ligne_dist = ctk.CTkFrame(carte, fg_color="transparent")
        ligne_dist.pack(fill="x", padx=10, pady=(0, 8))
        for i, (key, lib, unit) in enumerate(_CHAMPS_DIST):
            f, e = self._champ(ligne_dist, lib, d[key], unit,
                               label_width=70, entry_width=58)
            f.grid(row=0, column=i, sticky="w", padx=(0, 8), pady=2)
            champs[key] = e
            ligne_dist.grid_columnconfigure(i, weight=1)

        ligne_prop = ctk.CTkFrame(carte, fg_color="transparent")
        ligne_prop.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(ligne_prop, text="Proposition client :",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(
            side="left", padx=(0, 10))
        for cat, libc, lw in (("ventouse", "Ventouse", 62),
                              ("clapet", "Clapet", 62),
                              ("clapet_pi1", "Clap. PI1", 44),
                              ("clapet_pi2", "Clap. PI2", 44),
                              ("purgeur", "Purgeur", 62),
                              ("vanne", "Vanne sect.", 62)):
            bloc = ctk.CTkFrame(ligne_prop, fg_color="transparent")
            bloc.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(bloc, text=libc, width=lw, anchor="w",
                         font=ctk.CTkFont(size=10)).pack(side="left")
            e_dn = EntryFlottante(bloc, width=48)
            e_dn.insert(0, "")
            e_dn.pack(side="left", padx=(0, 2))
            if cat == "vanne":
                ctk.CTkLabel(bloc, text="DN", width=16,
                             font=ctk.CTkFont(size=9)).pack(side="left")
                # vanne : pas de compteur ; GN principal si vide
                champs[f"prop_{cat}_dn"] = e_dn
                continue
            ctk.CTkLabel(bloc, text="×", width=8).pack(side="left")
            e_nb = EntryFlottante(bloc, width=38)
            e_nb.insert(0, "1")
            e_nb.pack(side="left", padx=(0, 4))
            champs[f"prop_{cat}_dn"] = e_dn
            champs[f"prop_{cat}_nb"] = e_nb
        ctk.CTkLabel(ligne_prop,
                     text="(vanne vide = DN canalisation principale · Clap. PI1/PI2 "
                          "= clapets dédiés aux points intermédiaires)",
                     text_color="gray", font=ctk.CTkFont(size=9)).pack(
            side="left")

        self.entrees[label] = {"carte": carte, "schema": om, "champs": champs}
        self.lbl_statut.configure(text=f"{len(self.entrees)} tronçon(s)")
        return label

    def _champ(self, parent, lib, valeur, unit, label_width=120,
               entry_width=90) -> tuple:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text=lib, width=label_width, anchor="w").pack(side="left")
        e = EntryFlottante(f, width=entry_width)
        e.insert(0, str(valeur))
        e.pack(side="left", padx=(0, 4))
        if unit:
            ctk.CTkLabel(f, text=unit).pack(side="left")
        return f, e

    def _supprimer(self, label):
        if len(self.entrees) <= 1:
            self.lbl_statut.configure(text="Garder au moins 1 tronçon.")
            return
        ent = self.entrees.pop(label)
        ent["carte"].destroy()
        self.lbl_statut.configure(text=f"{len(self.entrees)} tronçon(s)")

    def _supprimer_dernier(self):
        cls = sorted(self.entrees.keys(),
                     key=lambda k: int(k[2:]) if k[2:].isdigit() else 0)
        if cls:
            self._supprimer(cls[-1])

    # ------------------------------------------------------------------
    def _lire_troncons(self) -> list:
        trs = []
        for label in sorted(self.entrees.keys(),
                            key=lambda k: int(k[2:]) if k[2:].isdigit() else 0):
            ent = self.entrees[label]
            vals = {key: ent["champs"][key].valeur(_DEFS[key]) for key in _DEFS}
            trs.append(ProfilTroncon(
                label=label, schema=ent["schema"].get(),
                z_vi1=vals["z_vi1"], z_ve=vals["z_ve"], z_vi2=vals["z_vi2"],
                z_pi1=vals["z_pi1"], z_pi2=vals["z_pi2"],
                a=vals["a"], b=vals["b"], c=vals["c"], d=vals["d"],
                l1=vals["l1"], l2=vals["l2"]))
        return trs

    def _lire_propositions(self) -> list:
        """Lecture des organes proposés par le client, aligné sur les tronçons.

        Retourne par tronçon : {ventouse, clapet, clapet_pi1, clapet_pi2,
        purgeur} = {dn, nombre} (valeur None pour un tronçon sans proposition).
        """
        props = []
        for label in sorted(self.entrees.keys(),
                            key=lambda k: int(k[2:]) if k[2:].isdigit() else 0):
            ch = self.entrees[label]["champs"]
            prop_tr = {}
            for cat in ("ventouse", "clapet", "clapet_pi1", "clapet_pi2",
                        "purgeur"):
                dn = ch.get(f"prop_{cat}_dn")
                nb = ch.get(f"prop_{cat}_nb")
                if dn is None or nb is None:
                    continue
                v_dn = dn.valeur(0.0)
                v_nb = int(nb.valeur(1.0))
                if v_dn and v_dn > 0 and v_nb > 0:
                    prop_tr[cat] = {"dn": int(v_dn), "nombre": v_nb}
            vdn = ch.get("prop_vanne_dn")
            if vdn is not None:
                v_vanne = vdn.valeur(0.0)
                if v_vanne and v_vanne > 0:
                    prop_tr["vanne_dn"] = int(v_vanne)
            props.append(prop_tr if prop_tr else None)
        return props

    def _calculer(self):
        g = {k: e.valeur({"dn_mm": 1400.0, "temperature": 15.0,
                          "pression_nominale": 10.0}[k])
             for k, e in self.globaux_entries.items()}
        try:
            pc = calculer_profil(self._lire_troncons(),
                                 dn_mm=float(g["dn_mm"]),
                                 temperature=float(g["temperature"]),
                                 pression_nominale=float(g["pression_nominale"]))
            self.dernier_pc = pc
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", synthese_txt(pc))
            for b in (self.b_exp_txt, self.b_exp_docx, self.b_exp_xlsx,
                      self.b_exp_png):
                b.configure(state="normal")
            self.lbl_statut.configure(
                text=f"Calcul OK — {len(pc.troncons)} tronçon(s), "
                     f"L = {pc.longueur_totale:,.0f} m")
            self._ajouter_propositions(pc)
            if self.on_calc:
                self.on_calc()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Profil complet", f"Erreur de calcul : {e}")

    def _ajouter_propositions(self, pc):
        from ..core.profil_complet import verification_txt
        self.lbl_concl.configure(text="", text_color="gray")
        self.txt_verif.delete("1.0", "end")
        pc.propositions = self._lire_propositions()
        if any(pc.propositions):
            pc.comparer_propositions()
            concl = pc.conclusion_globale()
            self.txt_verif.insert("1.0", verification_txt(pc))
            self.lbl_concl.configure(
                text=("✓ PROPOSITION CONFORME" if concl["conforme"]
                      else "✗ PROPOSITION NON CONFORME — à revoir"),
                text_color="#2ECC71" if concl["conforme"] else "#E74C3C")
        else:
            self.txt_verif.insert("1.0",
                                  "(Aucune proposition client renseignée — "
                                  "comparaison non effectuée.)")

    def _compare_client(self):
        if self.dernier_pc is None:
            from tkinter import messagebox
            messagebox.showinfo("Profil complet", "Calculer d'abord le profil "
                                                  "complet.")
            return
        self._ajouter_propositions(self.dernier_pc)

    # ------------------------------------------------------------------
    def _demande_user_path(self, nom: str, ftypes):
        from tkinter import filedialog
        return filedialog.asksaveasfilename(defaultextension=ftypes[0][1],
                                            initialfile=nom, filetypes=ftypes)

    def _export_txt(self):
        if not self.dernier_pc:
            return
        from tkinter import messagebox
        nom = f"profil_complet_{self.etat.projet or 'sans_titre'}.txt"
        path = self._demande_user_path(nom, [("Texte", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_txt.generer_rapport_profil(self.dernier_pc, self.etat))
            messagebox.showinfo("Export", f"Rapport généré :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}")

    def _export_docx(self):
        self._export_office("docx")

    def _export_xlsx(self):
        self._export_office("xlsx")

    def _export_office(self, ext):
        if not self.dernier_pc:
            return
        from tkinter import messagebox
        nom = f"profil_complet_{self.etat.projet or 'sans_titre'}.{ext}"
        path = self._demande_user_path(nom, [("Rapport", f"*.{ext}")])
        if not path:
            return
        try:
            if ext == "docx":
                export_office.exporter_docx_profil(self.dernier_pc, self.etat, path)
            else:
                export_office.exporter_xlsx_profil(self.dernier_pc, self.etat, path)
            messagebox.showinfo("Export", f"Rapport généré :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}")

    def _export_png(self):
        if not self.dernier_pc:
            return
        from tkinter import messagebox
        nom = f"profil_complet_{self.etat.projet or 'sans_titre'}.png"
        path = self._demande_user_path(nom, [("Image", "*.png")])
        if not path:
            return
        try:
            croquis_mod.croquis_chain_png(self.dernier_pc, path)
            messagebox.showinfo("Export", f"Croquis généré :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}")