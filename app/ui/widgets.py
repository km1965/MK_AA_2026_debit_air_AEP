"""Widgets partagés — entrées numériques, labels, cartes."""

import customtkinter as ctk


class EntryFlottante(ctk.CTkEntry):
    """Champ numérique flottant avec lecture tolérante."""

    def __init__(self, master, width=140, **kw):
        super().__init__(master, width=width, **kw)

    def valeur(self, defaut: float = 0.0) -> float:
        texte = self.get().strip().replace(",", ".")
        if texte == "":
            return defaut
        try:
            return float(texte)
        except ValueError:
            return defaut


def champ_ligne(parent, libelle: str, valeur: float = 0.0, unite: str = "",
                width: int = 140, row: int = None) -> tuple:
    """Crée une ligne label + entrée (et unité). Retourne (frame, entry)."""
    f = ctk.CTkFrame(parent, fg_color="transparent")
    lbl = ctk.CTkLabel(f, text=libelle, width=200, anchor="w")
    lbl.pack(side="left", padx=(0, 8))
    e = EntryFlottante(f, width=width)
    e.insert(0, str(valeur))
    e.pack(side="left", padx=(0, 4))
    if unite:
        ctk.CTkLabel(f, text=unite, anchor="w").pack(side="left")
    if row is not None:
        f.grid(row=row, column=0, sticky="w", pady=3)
    else:
        f.pack(fill="x", padx=4, pady=3)
    return f, e
