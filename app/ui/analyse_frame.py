# -*- coding: utf-8 -*-
"""Fenêtre « Analyse piézométrique » — saisie manuelle + tracé PNG.

Saisie libre des données du tronçon (identification, conduite, schéma,
altimétrie, distances) ; l'utilisateur génère le profil piézométrique
(ligne Z_Ve − 3 mCE, critère H ≥ 3 m aux PI) et enregistre/ouvre le PNG.
Les valeurs saisies ici sont indépendantes du projet de l'application.
"""

from __future__ import annotations

import os
import tempfile

import customtkinter as ctk
from PIL import Image, ImageTk

from ..controller import EtatApplication, SCHEMAS, DISTANCES_PAR_CAS
from ..utils import trace_piezometrique as trace_z
from .widgets import champ_ligne

_TEXTE = ["projet", "branches"]
_NUM = ["dn_mm", "temperature", "z_vi1", "z_pi1", "z_ve", "z_pi2", "z_vi2",
        "a", "b", "c", "d", "l1", "l2"]


class AnalyseFrame(ctk.CTkFrame):
    """Onglet « Analyse piézométrique »."""

    def __init__(self, master, etat, **kw):
        super().__init__(master, corner_radius=12, **kw)
        self.etat = etat
        self._png = os.path.join(tempfile.gettempdir(), "trace_piezometrique.png")
        self._photo = None
        self.entries = {}      # champs numériques → EntryFlottante
        self.txt_entries = {}  # champs texte → CTkEntry

        ctk.CTkLabel(self, text="Analyse piézométrique",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(
            anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(self, text=(
            "Profil en long + ligne piézométrique (Z_Ve − 3 mCE) · critère des "
            "points intermédiaires H ≥ 3 m → organe d'air requis."),
            text_color="gray").pack(anchor="w", padx=18, pady=(0, 6))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(0, 4))
        ctk.CTkButton(bar, text="Calculer & tracer (.png)",
                      command=self._calculer,
                      font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(bar, text="Ouvrir le tracé",
                      command=self._ouvrir).pack(side="left", padx=8)
        ctk.CTkButton(bar, text="Reprendre les données de l'app",
                      command=self._reprendre).pack(side="left")
        self.lbl_etat = ctk.CTkLabel(self, text="", text_color="gray")
        self.lbl_etat.pack(anchor="w", padx=18)

        corps = ctk.CTkFrame(self, fg_color="transparent")
        corps.pack(fill="both", expand=True, padx=10, pady=6)
        corps.grid_columnconfigure(0, weight=0)
        corps.grid_columnconfigure(1, weight=1)
        corps.grid_rowconfigure(0, weight=1)

        gauche = ctk.CTkScrollableFrame(corps, width=440)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        droite = ctk.CTkScrollableFrame(corps)
        droite.grid(row=0, column=1, sticky="nsew")

        self._construire_gauche(gauche)
        self._construire_droite(droite)
        self._actualiser_actifs()

    # ------------------------------------------------------------------
    def _construire_gauche(self, frame):
        ctk.CTkLabel(frame, text="1 · Identification",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(6, 2))
        for cle, lib in (("projet", "Projet / marché"),
                         ("branches", "Branche(s)")):
            f = ctk.CTkFrame(frame, fg_color="transparent")
            f.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(f, text=lib, width=170, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f)
            e.pack(side="left", fill="x", expand=True, padx=(0, 4))
            self.txt_entries[cle] = e

        ctk.CTkLabel(frame, text="2 · Conduite",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(8, 2))
        self._champ(frame, "Diamètre nominal DN", "dn_mm", "mm")
        self._champ(frame, "Température de l'eau", "temperature", "°C")

        ctk.CTkLabel(frame, text="3 · Schéma de vidange",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(8, 2))
        self.schema_var = ctk.StringVar(value="4A")
        ctk.CTkOptionMenu(frame, values=list(SCHEMAS),
                          variable=self.schema_var,
                          command=lambda _: self._actualiser_actifs()).pack(
            anchor="w", padx=8, pady=(0, 4))

        ctk.CTkLabel(frame, text="4 · Altimétrie",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(8, 2))
        for lib, cle in (("Z_Vi1 — point bas amont", "z_vi1"),
                         ("Z_PI1 — intermédiaire amont", "z_pi1"),
                         ("Z_Ve — point haut (ventouse)", "z_ve"),
                         ("Z_PI2 — intermédiaire aval", "z_pi2"),
                         ("Z_Vi2 — point bas aval", "z_vi2")):
            self._champ(frame, lib, cle, "m NGM")

        ctk.CTkLabel(frame, text="5 · Distances",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(8, 2))
        for lib, cle in (("a — Vi1 → PI1", "a"), ("b — PI1 → Ve", "b"),
                         ("c — Ve → PI2", "c"), ("d — PI2 → Vi2", "d"),
                         ("L1 — Vi1 → Ve", "l1"), ("L2 — Ve → Vi2", "l2")):
            self._champ(frame, lib, cle, "m")

        ctk.CTkLabel(frame, text="6 · Résultats",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(8, 2))
        self.lbl_res = ctk.CTkLabel(frame, text="(lancer le calcul)",
                                    justify="left", anchor="w",
                                    text_color="gray")
        self.lbl_res.pack(anchor="w", padx=6, pady=(0, 4))
        ctk.CTkLabel(frame, text="Journal de calcul",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=6, pady=(2, 0))
        self.txt_journal = ctk.CTkTextbox(
            frame, height=120, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_journal.pack(fill="x", padx=6, pady=(2, 8))

    def _construire_droite(self, frame):
        ctk.CTkLabel(frame, text="Aperçu du tracé",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=6, pady=(6, 2))
        self.canvas = ctk.CTkFrame(frame, fg_color="transparent")
        self.canvas.pack(fill="both", expand=True, padx=6, pady=4)
        self.lbl_msg = ctk.CTkLabel(
            frame, text="Cliquer « Calculer & tracer » pour générer le profil.",
            text_color="gray")
        self.lbl_msg.pack(anchor="w", padx=6, pady=(0, 8))

    # ------------------------------------------------------------------
    def _champ(self, frame, lib, cle, unite):
        _, e = champ_ligne(frame, lib, getattr(self.etat, cle, 0.0), unite,
                           width=100)
        self.entries[cle] = e

    def _actualiser_actifs(self):
        if not getattr(self, "entries", None):
            return
        actifs = set(DISTANCES_PAR_CAS.get(self.schema_var.get(), []))
        for cle, e in self.entries.items():
            if cle in ("a", "b", "c", "d", "l1", "l2"):
                e.configure(state="normal" if cle in actifs else "disabled")

    def _reprendre(self):
        for cle, e in self.txt_entries.items():
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, str(getattr(self.etat, cle, "")))
        self.schema_var.set(self.etat.schema)
        for cle, e in self.entries.items():
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, str(getattr(self.etat, cle, 0.0)))
        self._actualiser_actifs()

    def _calculer(self):
        try:
            e = EtatApplication()
            e.projet = self.txt_entries["projet"].get().strip()
            e.branches = self.txt_entries["branches"].get().strip()
            e.schema = self.schema_var.get()
            for cle, ent in self.entries.items():
                setattr(e, cle, ent.valeur(0.0))
            fig, infos = trace_z.tracer_profil(e, self._png)
            import matplotlib.pyplot as plt
            plt.close(fig)
            self._afficher_resultats(infos)
            self._afficher_png()
            self.lbl_etat.configure(text=f"Tracé enregistré : {self._png}")
        except Exception as ex:
            self.lbl_etat.configure(text=f"Erreur : {ex}")

    def _afficher_resultats(self, infos):
        lignes = [f"Q_Ve   = {infos['q_ve']:,.1f} m³/h",
                  f"Q_PI1  = {infos['q_pi1']:,.1f} m³/h",
                  f"Q_PI2  = {infos['q_pi2']:,.1f} m³/h"]
        if infos["h1"] is not None:
            lignes.append(f"H1 = {infos['h1']:+.2f} m  →  {infos['verdict1']}")
        if infos["h2"] is not None:
            lignes.append(f"H2 = {infos['h2']:+.2f} m  →  {infos['verdict2']}")
        self.lbl_res.configure(text="\n".join(lignes), text_color="white")
        j = "\n".join(infos["journal"]) or "(journal vide)"
        self.txt_journal.delete("1.0", "end")
        self.txt_journal.insert("1.0", j)

    def _afficher_png(self):
        img = Image.open(self._png).convert("RGB")
        cw = self.canvas.winfo_width() or 900
        ratio = min(1.0, cw / img.width)
        nh = int(img.height * ratio)
        nw = int(img.width * ratio)
        self._photo = ImageTk.PhotoImage(img.resize((nw, nh)))
        img.close()
        self.lbl_msg.configure(
            text=f"Aperçu réduit — fichier : {self._png}\n"
                 "Bouton « Ouvrir le tracé » pour le PNG complet.")
        # On affiche l'image sous forme d'un label — simple et scrollable.
        for w in self.canvas.winfo_children():
            w.destroy()
        impl = ctk.CTkLabel(self.canvas, image=self._photo, text="")
        impl.pack()

    def _ouvrir(self):
        if os.path.exists(self._png):
            os.startfile(self._png)  # noqa: ensure_open_outside_editor
        else:
            self.lbl_etat.configure(text="Aucun tracé généré pour l'instant.")