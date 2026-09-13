"""Frames : sélection du schéma de vidange et profil en long."""

import customtkinter as ctk

from .widgets import champ_ligne
from ..controller import SCHEMAS, SCHEMA_LABELS, DISTANCES_PAR_CAS


class SchemaFrame(ctk.CTkFrame):
    """§5 — Choix du schéma de vidange parmi les 8 cas."""

    def __init__(self, master, etat, on_change=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self.on_change = on_change

        ctk.CTkLabel(self, text="Schéma de vidange",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text="§5 — 8 variantes couvrant toutes les configurations de vidange.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 12))

        self.boutons = {}
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=16)
        grid.grid_columnconfigure((0, 1), weight=1)
        # Variable partagée : un seul schéma sélectionnable à la fois.
        self.schema_var = ctk.StringVar(value=etat.schema)
        for i, cas in enumerate(SCHEMAS):
            b = ctk.CTkRadioButton(
                grid, text=f"{cas} — {SCHEMA_LABELS[cas]}",
                variable=self.schema_var, value=cas,
                command=lambda: self._select(self.schema_var.get()))
            b.grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=6)
            self.boutons[cas] = b

    def _select(self, cas):
        self.etat.schema = cas
        if self.on_change:
            self.on_change()

    def charger(self):
        self.schema_var.set(self.etat.schema)
        for cas, b in self.boutons.items():
            if cas == self.etat.schema:
                b.select()


class ProfilFrame(ctk.CTkFrame):
    """§4.4 — Altimétrie / profil en long, adapté au schéma choisi."""

    def __init__(self, master, etat, on_calc=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self.on_calc = on_calc
        self.entrees = {}

        self.frame_titre = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.frame_titre, text="Profil en long / altimétrie",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        self.frame_titre.pack(anchor="w", padx=16, pady=(16, 4))
        self.lbl_admin = ctk.CTkLabel(self, text="", text_color="gray")
        self.lbl_admin.pack(anchor="w", padx=16, pady=(0, 8))

        # Les altitudes sont toujours visibles
        self.carte_alt = ctk.CTkFrame(self, fg_color="transparent")
        self.carte_alt.pack(fill="x", padx=16)
        self.alt_specs = [
            ("Z_Ve  — point haut (ventouse)", "z_ve"),
            ("Z_Vi1 — point bas amont", "z_vi1"),
            ("Z_PI1 — point intermédiaire amont", "z_pi1"),
            ("Z_Vi2 — point bas aval", "z_vi2"),
            ("Z_PI2 — point intermédiaire aval", "z_pi2"),
        ]
        for i, (lib, key) in enumerate(self.alt_specs):
            f, e = champ_ligne(self.carte_alt, lib, getattr(etat, key), "m NGM", row=i)
            e.bind("<KeyRelease>", lambda _ev, k=key: self._sync_alt(k))
            self.entrees[key] = e

        # Les distances s'adaptent au schéma
        self.carte_dist = ctk.CTkFrame(self, fg_color="transparent")
        self.carte_dist.pack(fill="x", padx=16, pady=(10, 4))
        self._construire_dist(frame=self.carte_dist)
        self.lbl_dist_info = ctk.CTkLabel(self, text="", text_color="gray", justify="left")
        self.lbl_dist_info.pack(anchor="w", padx=24, pady=(2, 6))

    def _sync_alt(self, key):
        widget = self.entrees.get(key) or self.dist_entries.get(key)
        if widget is None:
            return
        try:
            setattr(self.etat, key, float(widget.get().replace(",", ".")))
        except ValueError:
            pass

    def _construire_dist(self, frame):
        for w in frame.winfo_children():
            w.destroy()
        self.dist_entries = {}
        specs = [
            ("a   — Vi1 → PI1 (m)", "a"),
            ("b   — PI1 → Ve (m)", "b"),
            ("c   — Ve → PI2 (m)", "c"),
            ("d   — PI2 → Vi2 (m)", "d"),
            ("L₁  — Vi1 → Ve (m)", "l1"),
            ("L₂  — Ve → Vi2 (m)", "l2"),
        ]
        for i, (lib, key) in enumerate(specs):
            f, e = champ_ligne(frame, lib, getattr(self.etat, key), "m", row=i,
                               width=120)
            e.bind("<KeyRelease>", lambda _ev, k=key: self._sync_alt(k))
            self.dist_entries[key] = e

    def charger(self):
        for key, e in self.entrees.items():
            e.delete(0, "end")
            e.insert(0, str(getattr(self.etat, key)))
        self._construire_dist(self.carte_dist)
        for key, e in self.dist_entries.items():
            e.delete(0, "end")
            e.insert(0, str(getattr(self.etat, key)))
        self._actualiser_actifs()

    def _actualiser_actifs(self):
        """Grise les distances non pertinentes selon le schéma."""
        actifs = set(DISTANCES_PAR_CAS.get(self.etat.schema, []))
        label_extra = ""
        if self.etat.schema in ("1A", "1B"):
            label_extra = "Vidange amont seule — seule la partie amont est saisie."
        elif self.etat.schema in ("2A", "2B"):
            label_extra = "Vidange aval seule — seule la partie aval est saisie."
        elif self.etat.schema in ("3A", "3B", "4A", "4B"):
            label_extra = "Vidanges amont + aval — parties amont et aval saisies."
        self.lbl_dist_info.configure(text=label_extra)
        for key, e in self.dist_entries.items():
            etat_actif = key in actifs
            # griser les champs non pertinents pour le schéma choisi
            e.configure(state="normal" if etat_actif else "disabled")

    def afficher_resume_schema(self):
        self._actualiser_actifs()
