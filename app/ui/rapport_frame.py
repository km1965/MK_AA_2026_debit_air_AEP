"""Frame Rapport de synthèse — croquis graphique + rapport pas-à-pas + annexes catalogue."""

import datetime
import io
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from ..utils import croquis as croquis_mod


class RapportFrame(ctk.CTkFrame):
    """Livrable n°5 — Rapport de synthèse.

    Affiche le croquis du profil en long (PNG) et le rapport textuel.
    Permet l'export : rapport .txt et croquis .png.
    """

    def __init__(self, master, etat=None):
        super().__init__(master, corner_radius=12)
        self.etat = etat
        self._img = None          # référence pour éviter le ramasse-miettes
        self._photo = None
        self._png_bytes = None

        ctk.CTkLabel(self, text="Rapport de synthèse",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self, text="Croquis du profil + méthodologie, hypothèses, calculs, annexes catalogue (§11).",
                     text_color="gray").pack(anchor="w", padx=16, pady=(0, 8))

        # Barre d'actions
        bar = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkButton(bar, text="Générer / Actualiser", command=self._generer).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exporter .docx", command=self._exporter_docx).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exporter .xlsx", command=self._exporter_xlsx).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Exporter .txt", command=self._exporter_txt).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="MÉTHODOLOGIE .docx", command=self._exporter_methodologie).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="NOMENCLATURE .xlsx", command=self._exporter_nomenclature).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Croquis .png", command=self._exporter_png).pack(side="left")
        bar.pack(anchor="w", padx=16, pady=(4, 8))

        # Canevas pour le croquis PNG
        self.canvas = ctk.CTkCanvas(self, height=230, bg="#1a1a1a",
                                    highlightthickness=0)
        self.canvas.pack(fill="x", padx=16, pady=(0, 8))
        self.lbl_croquis = ctk.CTkLabel(self, text="Cliquer sur « Générer / Actualiser » pour afficher le croquis.",
                                        text_color="gray")
        self.lbl_croquis.pack(anchor="w", padx=16, pady=(0, 4))

        # Zone texte du rapport
        self.txt = ctk.CTkTextbox(self, wrap="word",
                                  font=ctk.CTkFont(family="Consolas", size=12))
        self.txt.pack(fill="both", expand=True, padx=16, pady=(4, 16))

    # ------------------------------------------------------------------
    def _generer(self):
        if self.etat is None:
            return
        self._maj_croquis()
        rapport = self.etat.generer_rapport()
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", rapport)

    def _maj_croquis(self):
        """Génère le croquis PNG en mémoire et l'affiche."""
        try:
            buf = io.BytesIO()
            # matplotlib écrit un fichier : on passe par un chemin temporaire
            tmp = os.path.join(os.environ.get("TEMP", "."), "_mk_aa_croquis_tmp.png")
            croquis_mod.croquis_png(self.etat, tmp)
            with open(tmp, "rb") as f:
                data = f.read()
            self._png_bytes = data
            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")
            # Redimensionnement pour tenir dans le canevas (largeur max)
            cw = self.canvas.winfo_width() or 1000
            ratio = min(1.0, (cw) / img.width)
            nh = int(img.height * ratio)
            nw = int(img.width * ratio)
            img = img.resize((nw, nh))
            self._img = img
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.configure(height=nh)
            self.canvas.create_image(cw // 2, nh // 2, image=self._photo)
            self.lbl_croquis.configure(text="Croquis du profil en long (schéma %s)." % self.etat.schema)
        except ImportError as e:
            self.lbl_croquis.configure(text=f"Croquis PNG indisponible : {e}")
        except Exception as e:  # ne doit jamais bloquer
            self.lbl_croquis.configure(text=f"Erreur croquis : {e}")

    # ------------------------------------------------------------------
    def _exporter_txt(self):
        if self.etat is None:
            return
        rapport = self.etat.generer_rapport()
        defaut = f"rapport_mk_aa_2026_{datetime.date.today().isoformat()}.txt"
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile=defaut,
                                            filetypes=[("Fichier texte", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(rapport)
            messagebox.showinfo("Export", f"Rapport exporté :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _exporter_png(self):
        if self._png_bytes is None:
            self._maj_croquis()
        if self._png_bytes is None:
            messagebox.showwarning("Export", "Aucun croquis à exporter.")
            return
        defaut = f"croquis_profil_{datetime.date.today().isoformat()}.png"
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile=defaut,
                                            filetypes=[("Image PNG", "*.png")])
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._png_bytes)
            messagebox.showinfo("Export", f"Croquis exporté :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _exporter_methodologie(self):
        if self.etat is None:
            return
        self.etat.calculer()
        defaut = "METHODOLOGIE_MK_A.A_2026.docx"
        path = filedialog.asksaveasfilename(
            defaultextension=".docx", initialfile=defaut,
            filetypes=[("Word Document", "*.docx")])
        if not path:
            return
        try:
            from ..utils.export_office import exporter_methodologie
            exporter_methodologie(self.etat, path)
            messagebox.showinfo(
                "Export",
                f"Note MÉTHODOLOGIE MK_A.A_2026 exportée :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}\n(python-docx est-il installé ?)")

    def _exporter_nomenclature(self):
        if self.etat is None:
            return
        self.etat.calculer()
        defaut = "NOMENCLATURE_MK_A.A_2026.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=defaut,
            filetypes=[("Excel Workbook", "*.xlsx")])
        if not path:
            return
        try:
            from ..utils.export_office import exporter_nomenclature
            exporter_nomenclature(self.etat, path)
            messagebox.showinfo(
                "Export",
                f"Nomenclature exportée :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}\n(openpyxl est-il installé ?)")

    def _exporter_docx(self):
        if self.etat is None:
            return
        if self.etat.resultat is None:
            self.etat.calculer()
        defaut = f"rapport_mk_aa_2026_{datetime.date.today().isoformat()}.docx"
        path = filedialog.asksaveasfilename(defaultextension=".docx",
                                            initialfile=defaut,
                                            filetypes=[("Word Document", "*.docx")])
        if not path:
            return
        try:
            from ..utils.export_office import exporter_docx
            exporter_docx(self.etat, path)
            messagebox.showinfo("Export", f"Rapport Word exporté :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}\n(python-docx est-il installé ?)")

    def _exporter_xlsx(self):
        if self.etat is None:
            return
        if self.etat.resultat is None:
            self.etat.calculer()
        defaut = f"rapport_mk_aa_2026_{datetime.date.today().isoformat()}.xlsx"
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                            initialfile=defaut,
                                            filetypes=[("Excel Workbook", "*.xlsx")])
        if not path:
            return
        try:
            from ..utils.export_office import exporter_xlsx
            exporter_xlsx(self.etat, path)
            messagebox.showinfo("Export", f"Classeur Excel exporté :\n{path}")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur : {e}\n(openpyxl est-il installé ?)")

    # Alias publics pour la barre de menu
    def _export_depuis_menu(self):
        self._exporter_txt()

    def _export_docx_depuis_menu(self):
        self._exporter_docx()

    def _export_xlsx_depuis_menu(self):
        self._exporter_xlsx()

    def _export_png_depuis_menu(self):
        self._exporter_png()
