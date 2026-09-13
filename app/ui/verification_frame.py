"""Frame Vérification des organes — comparaison propositions client vs besoins.

Verdict : Conforme / Non conforme pour chaque catégorie (ventouse TRIFON,
clapet CEAI, purgeur PSA, vanne de sectionnement).

Le choix d'un fournisseur (ex. SNH, depuis valve_database.json) est possible :
les DN proposés et les capacités proviennent alors de la base externe
(modifiable sans recompiler).
"""

import customtkinter as ctk

from ..controller import EtatApplication
from ..data.catalogues import TRIFON, CEAI, PSA
from ..data import valve_db

ROLE = {"trifon": "ventouse", "ceai": "clapet", "psa": "purgeur"}

# Fournisseurs disponibles : standard + ceux de la base externe
NOMS_FOURNISSEURS = ["— Standard —"] + [f["nom"] for f in valve_db.FOURNISSEURS]

CATEGORIES = [
    ("Ventouse admission", "trifon", sorted(TRIFON.keys())),
    ("Clapet admission air", "ceai", sorted(CEAI.keys())),
    ("Purgeur remplissage", "psa", sorted(PSA.keys())),
    ("Vannes de sectionnement", "vanne", ["DN", "à préciser"]),
]

_LABELS = {"trifon": "Ventouse", "ceai": "Clapet", "psa": "Purgeur",
           "vanne": "Vannes sectionnement"}


def _dns_pour(cat, fournisseur):
    """Liste des DN disponibles pour (catégorie, fournisseur)."""
    if cat == "vanne":
        return ["DN", "à préciser"]
    standard = (not fournisseur) or fournisseur in ("— Standard —", "TRIFON", "CEAI", "PSA")
    if standard:
        base = {"trifon": TRIFON, "ceai": CEAI, "psa": PSA}[cat]
        return sorted(base.keys())
    tab = valve_db.table_capacite(fournisseur, ROLE[cat])
    return sorted(tab.keys()) or ["DN", "à préciser"]


class VerificationFrame(ctk.CTkFrame):
    """Livrable — Vérification des organes proposés par le client (conforme/non conforme)."""

    def __init__(self, master, etat: EtatApplication = None):
        super().__init__(master, corner_radius=12)
        self.etat = etat

        ctk.CTkLabel(self, text="Vérification des organes",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self,
                     text="Compare les organes proposés par le client aux besoins calculés — "
                          "verdict conforme / non conforme. Choix du fournisseur (ex. SNH) "
                          "depuis valve_database.json.",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 10))

        # --- Barre de saisie ---
        barre = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(barre, text="Fournisseur").pack(side="left", padx=(0, 6))
        self.men_four = ctk.CTkOptionMenu(barre, values=NOMS_FOURNISSEURS,
                                          width=170, command=self._on_four)
        self.men_four.set("— Standard —")
        self.men_four.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(barre, text="Catégorie").pack(side="left", padx=(0, 6))
        self.men_cat = ctk.CTkOptionMenu(barre, values=[c[0] for c in CATEGORIES],
                                         width=180, command=self._on_cat)
        self.men_cat.set(CATEGORIES[0][0])
        self.men_cat.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(barre, text="DN").pack(side="left", padx=(0, 6))
        self.men_dn = ctk.CTkOptionMenu(barre, values=[str(x) for x in CATEGORIES[0][2]])
        self.men_dn.set(str(CATEGORIES[0][2][0]))
        self.men_dn.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(barre, text="Nbr").pack(side="left", padx=(0, 6))
        self.entry_nb = ctk.CTkEntry(barre, width=70)
        self.entry_nb.insert(0, "1")
        self.entry_nb.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(barre, text="Pos").pack(side="left", padx=(0, 6))
        self.men_pos = ctk.CTkOptionMenu(barre, values=["Amont", "Aval", "PI1", "PI2"],
                                         width=90)
        self.men_pos.set("Amont")
        self.men_pos.pack(side="left", padx=(0, 12))

        ctk.CTkButton(barre, text="+ Ajouter", width=110, command=self._ajouter).pack(side="left")
        barre.pack(anchor="w", padx=16, pady=(0, 8))

        # --- Liste des organes ajoutés ---
        self.liste_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.liste_frame.pack(fill="x", padx=16, pady=(0, 8))

        # --- Verdicts ---
        self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.result_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        ctk.CTkButton(self, text="Vérifier la conformité", command=self.verifier,
                      font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(0, 10))

        self._maj_liste()

    # ------------------------------------------------------------------
    def _fournisseur(self):
        v = self.men_four.get()
        return "" if v == "— Standard —" else v

    def _on_four(self, _):
        self._regen_dn()

    def _on_cat(self, nom):
        self._regen_dn()

    def _categorie(self, nom):
        for lbl, key, dns in CATEGORIES:
            if lbl == nom:
                return key
        return None

    def _regen_dn(self):
        cat = self._categorie(self.men_cat.get())
        if cat is None:
            return
        dns = _dns_pour(cat, self._fournisseur())
        vals = [str(x) for x in dns]
        self.men_dn.configure(values=vals)
        self.men_dn.set(vals[0])

    def _ajouter(self):
        four = self._fournisseur()
        pos = self.men_pos.get().lower()
        cat = self._categorie(self.men_cat.get())
        if cat == "vanne":
            # La vanne de sectionnement n'est pas un organe d'air :
            # on met à jour dn_vanne_sectionnement directement
            dn_text = self.men_dn.get().strip()
            try:
                dn = float(dn_text.replace("DN", "").strip())
                self.etat.dn_vanne_sectionnement = dn
            except (ValueError, AttributeError):
                pass  # DN « à préciser » → ne rien faire
            self._maj_liste()
            return
        if cat in ("trifon", "ceai", "psa"):
            try:
                dn = int(self.men_dn.get())
            except ValueError:
                dn = None
            nb_text = self.entry_nb.get().strip() or "1"
            try:
                nb = max(1, int(nb_text))
            except ValueError:
                nb = 1
            entry = {"type": cat, "dn": dn, "nombre": nb, "position": pos}
            if four:
                entry["fournisseur"] = four
            self.etat.organes_client.append(entry)
        self._maj_liste()

    def _retirer(self, idx):
        # idx est un indice dans la liste combinée (vanne en tête éventuelle).
        # On ne retire que les organes d'air de organes_client.
        if self.etat.dn_vanne_sectionnement:
            idx -= 1
        try:
            self.etat.organes_client.pop(idx)
        except IndexError:
            pass
        self._maj_liste()

    def _maj_liste(self):
        for w in self.liste_frame.winfo_children():
            w.destroy()
        # La vanne de sectionnement (gérée séparément) est affichée en tête,
        # puis les organes d'air de la liste client.
        items = []
        if self.etat.dn_vanne_sectionnement:
            items.append({"type": "vanne", "dn": self.etat.dn_vanne_sectionnement,
                          "nombre": 1, "fournisseur": "", "position": "",
                          "_vanne": True})
        items += self.etat.organes_client
        if not items:
            ctk.CTkLabel(self.liste_frame, text="(Aucun organe saisi)",
                         text_color="gray").pack(anchor="w")
        for i, o in enumerate(items):
            ligne = ctk.CTkFrame(self.liste_frame, fg_color="transparent")
            dn = o.get("dn") if o.get("dn") is not None else "—"
            nom = _LABELS[o["type"]]
            four = o.get("fournisseur", "")
            lib = f"{o['nombre']} × {nom}  DN {dn}"
            if four:
                lib += f"  [{four}]"
            pos = o.get("position", "")
            if pos:
                lib += f"  ({pos})"
            ctk.CTkLabel(ligne, text=lib, anchor="w",
                         width=320, justify="left").pack(side="left")
            if o.get("_vanne"):
                ctk.CTkButton(ligne, text="Retirer", width=70,
                              command=self._retirer_vanne).pack(side="left", padx=6)
            else:
                ctk.CTkButton(ligne, text="Retirer", width=70,
                              command=lambda k=i: self._retirer(k)).pack(side="left", padx=6)
            ligne.pack(anchor="w", pady=2)

    def _retirer_vanne(self):
        self.etat.dn_vanne_sectionnement = 0.0
        self._maj_liste()

    # ------------------------------------------------------------------
    def verifier(self):
        for w in self.result_frame.winfo_children():
            w.destroy()
        verdicts = self.etat.verifier_organes()
        global_ok = all(v["conforme"] for v in verdicts)
        titre = ("Tous les organes sont CONFORMES"
                 if global_ok else "Certains organes sont NON CONFORMES")
        ctk.CTkLabel(self.result_frame, text=titre, anchor="w",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#2ECC71" if global_ok else "#E74C3C").pack(anchor="w", pady=(2, 6))

        for v in verdicts:
            bloc = ctk.CTkFrame(self.result_frame, corner_radius=8)
            statut = "✓ CONFORME" if v["conforme"] else "✗ NON CONFORME"
            couleur = "#2ECC71" if v["conforme"] else "#E74C3C"
            is_cumul = str(v["categorie"]).startswith("CUMUL")
            lbl_cat = ctk.CTkLabel(bloc, text=v["categorie"], anchor="w",
                                   font=ctk.CTkFont(weight="bold"), width=260)
            lbl_cat.grid(row=0, column=0, sticky="w", padx=10, pady=4)
            if is_cumul:
                lbl_cat.configure(text_color="darkorange")
            ctk.CTkLabel(bloc, text=statut, anchor="w", text_color=couleur,
                         font=ctk.CTkFont(weight="bold"), width=150).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(bloc, text=v["message"], anchor="w", text_color="gray80",
                         justify="left").grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))
            bloc.pack(fill="x", padx=4, pady=4)
