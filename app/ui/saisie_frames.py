"""Frames de saisie : Projet, Conduite, Profil en long (données variables §4)."""

import customtkinter as ctk

from .widgets import champ_ligne


class ProjetFrame(ctk.CTkFrame):
    """§4.1 — Identification du projet / maître d'ouvrage."""

    def __init__(self, master, etat, on_change=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self.on_change = on_change

        t = ctk.CTkLabel(self, text="Identification du projet / maître d'ouvrage",
                         font=ctk.CTkFont(size=18, weight="bold"))
        t.pack(anchor="w", padx=16, pady=(16, 4))
        sub = ctk.CTkLabel(self, text="Données variables (§4.1) — socle de calcul figé.",
                           text_color="gray")
        sub.pack(anchor="w", padx=16, pady=(0, 12))

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16)
        container.grid_columnconfigure(0, weight=1)

        self.entrees = {}
        specs = [
            ("Maître d'ouvrage", "moe"),
            ("Projet / marché", "projet"),
            ("Référence document / indice", "reference"),
            ("Branches étudiées", "branches"),
        ]
        for i, (lib, key) in enumerate(specs):
            f = ctk.CTkFrame(container, fg_color="transparent")
            ctk.CTkLabel(f, text=lib, width=220, anchor="w").pack(side="left", padx=(0, 8))
            e = ctk.CTkEntry(f, width=360)
            e.insert(0, str(getattr(etat, key)))
            e.pack(side="left")
            e.bind("<KeyRelease>", lambda _ev, k=key: self._sync(k))
            self.entrees[key] = e
            f.grid(row=i, column=0, sticky="w", pady=5)

    def _sync(self, key):
        setattr(self.etat, key, self.entrees[key].get())
        if self.on_change:
            self.on_change()

    def charger(self):
        for key, e in self.entrees.items():
            e.delete(0, "end")
            e.insert(0, str(getattr(self.etat, key)))


class ConduiteFrame(ctk.CTkFrame):
    """§4.2 / §4.3 — Caractéristiques de la conduite et température."""

    def __init__(self, master, etat, on_calc=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self.on_calc = on_calc

        t = ctk.CTkLabel(self, text="Caractéristiques de la canalisation principale",
                         font=ctk.CTkFont(size=18, weight="bold"))
        t.pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text="§4.2 §4.3 — DN, diamètre, section, température.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 8))

        # Choix du DN prédéfini (ou saisie libre via bouton "DN autre")
        ligne = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(ligne, text="Diamètre nominal (mm)", width=190, anchor="w").pack(side="left", padx=(0, 8))
        self.menu_dn = ctk.CTkOptionMenu(ligne, values=["1400", "1600", "2000"],
                                         command=self._on_dn)
        self.menu_dn.set(str(int(etat.dn_mm)))
        self.menu_dn.pack(side="left")
        self.menu_dn.bind("<Configure>", lambda _e: self._on_dn(self.menu_dn.get()) if self.on_calc else None)
        ligne.pack(anchor="w", padx=16, pady=5)

        # Affichage des déductions automatiques
        self.lbl_deduit = ctk.CTkLabel(self, text="", justify="left", text_color="gray70",
                                       font=ctk.CTkFont(size=12))
        self.lbl_deduit.pack(anchor="w", padx=24, pady=(0, 10))

        f_t = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(f_t, text="Température de l'eau (°C)", width=190, anchor="w").pack(side="left", padx=(0, 8))
        self.entry_t = ctk.CTkEntry(f_t, width=140)
        self.entry_t.insert(0, str(etat.temperature))
        self.entry_t.bind("<KeyRelease>", lambda _e: self._sync_t())
        self.entry_t.pack(side="left")
        self.lbl_nu = ctk.CTkLabel(f_t, text="", text_color="gray70")
        self.lbl_nu.pack(side="left", padx=(10, 0))
        f_t.pack(anchor="w", padx=16, pady=5)

        ctk.CTkLabel(self, text="Faites Calculer pour mettre à jour les valeurs déduites.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(8, 4))

        self._actualiser_deduit()

    def _on_dn(self, val):
        try:
            self.etat.dn_mm = float(val)
        except ValueError:
            pass
        self._actualiser_deduit()
        if self.on_calc:
            self.on_calc()

    def _sync_t(self):
        try:
            self.etat.temperature = float(self.entry_t.get().replace(",", "."))
        except ValueError:
            pass
        from ..utils.viscosity import corriger_nu
        self.lbl_nu.configure(text=f"ν = {corriger_nu(self.etat.temperature):.3e} m²/s")

    def _actualiser_deduit(self):
        dc = self.etat.dc()
        self.lbl_deduit.configure(
            text=(f"D = {dc.d:.3f} m   ·   S = {dc.section:.4f} m²"
                  f"   ·   k/D = {dc.kd:.3e}"))
        self._sync_t()

    def charger(self):
        try:
            self.menu_dn.set(str(int(self.etat.dn_mm)))
        except Exception:
            self.menu_dn.set(self.menu_dn.cget("values")[0])
        self.entry_t.delete(0, "end")
        self.entry_t.insert(0, str(self.etat.temperature))
        self._actualiser_deduit()
