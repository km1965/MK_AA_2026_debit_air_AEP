"""Fenêtre principale — navigation par sidebar + orchestration du calcul."""

import customtkinter as ctk
from pathlib import Path

from ..controller import EtatApplication
from .saisie_frames import ProjetFrame, ConduiteFrame
from .schema_profil_frames import SchemaFrame, ProfilFrame
from .resultats_frames import CalculFrame, DimensionnementFrame
from .verification_frame import VerificationFrame
from .rapport_frame import RapportFrame
from .cumul_debits_frame import CumulDebitsFrame
from .profil_complet_frame import ProfilCompletFrame
from .analyse_frame import AnalyseFrame


def _chemin_icone() -> str:
    """Chemin vers l'icône du projet (assets/icon.ico)."""
    import sys
    if getattr(sys, "frozen", False):
        # PyInstaller : assets embarqués dans _MEIPASS (onefile) ou dossier exe
        racines = [
            Path(getattr(sys, "_MEIPASS", "")),
            Path(sys.executable).resolve().parent,
        ]
    else:
        racines = [Path(__file__).resolve().parent.parent.parent]
    for racine in racines:
        if not racine:
            continue
        ico = racine / "assets" / "icon.ico"
        png = racine / "assets" / "icon.png"
        if ico.exists():
            return str(ico)
        if png.exists():
            return str(png)
    return ""


class Application(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.etat = EtatApplication()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("MK_A.A 2026 — Débits d'air admis en conduites AEP")
        self.geometry("1280x820")
        self.minsize(1080, 700)

        ico = _chemin_icone()
        if ico:
            from tkinter import PhotoImage
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        self._construire_menus()

        # Grille : sidebar | contenu
        self._fichier_courant = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._construire_sidebar()
        self._construire_contenu()

        self.frames = {
            "projet": self.projet_frame,
            "conduite": self.conduite_frame,
            "schema": self.schema_frame,
            "profil": self.profil_frame,
            "calcul": self.calcul_frame,
            "dimensionnement": self.dimensionnement_frame,
            "verification": self.verification_frame,
            "cumul": self.cumul_frame,
            "rapport": self.rapport_frame,
            "profil_complet": self.profil_complet_frame,
            "analyse": self.analyse_frame,
        }
        for f in self.frames.values():
            f.grid(row=0, column=0, sticky="nsew")
        self.afficher_frame("projet")

    # ------------------------------------------------------------------
    def _construire_sidebar(self):
        side = ctk.CTkFrame(self, width=230, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)

        ctk.CTkLabel(side, text="MK_A.A 2026",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=18, pady=(20, 2))
        ctk.CTkLabel(side, text="Débits d'air admis — AEP",
                     text_color="gray").pack(anchor="w", padx=18, pady=(0, 14))

        sections = [
            ("Saisie", [
                ("projet", "1 · Projet"),
                ("conduite", "2 · Conduite"),
                ("schema", "3 · Schéma vidange"),
                ("profil", "4 · Profil en long"),
            ]),
            ("Résultats", [
                ("calcul", "5 · Calcul"),
                ("dimensionnement", "6 · Dimensionnement"),
                ("verification", "7 · Vérification organes"),
                ("cumul", "8 · Cumul des débits"),
                ("rapport", "9 · Rapport"),
                ("profil_complet", "10 · Profil complet"),
                ("analyse", "11 · Analyse piézométrique"),
            ]),
        ]
        for titre, items in sections:
            ctk.CTkLabel(side, text=titre, text_color="gray50",
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=18, pady=(8, 2))
            for key, label in items:
                btn = ctk.CTkButton(side, text=label, anchor="w",
                                    fg_color="transparent", text_color="gray85",
                                    hover_color="gray20",
                                    command=lambda k=key: self.afficher_frame(k))
                btn.pack(fill="x", padx=10, pady=2)
                self.side_buttons = getattr(self, "side_buttons", {})
                self.side_buttons[key] = btn

        # Bouton Calculer global en bas
        ctk.CTkButton(side, text="Lancer le calcul",
                      command=self._calculer_tout,
                      font=ctk.CTkFont(weight="bold")).pack(side="bottom", fill="x",
                                                            padx=16, pady=18)

    def _construire_contenu(self):
        self.contenu = ctk.CTkFrame(self, corner_radius=0)
        self.contenu.grid(row=0, column=1, sticky="nsew")
        self.contenu.grid_columnconfigure(0, weight=1)
        self.contenu.grid_rowconfigure(0, weight=1)

        self.projet_frame = ProjetFrame(self.contenu, self.etat, on_change=self._recalcul)
        self.conduite_frame = ConduiteFrame(self.contenu, self.etat, on_calc=self._recalcul)
        self.schema_frame = SchemaFrame(self.contenu, self.etat, on_change=self._recalcul)
        self.profil_frame = ProfilFrame(self.contenu, self.etat, on_calc=self._recalcul)
        self.calcul_frame = CalculFrame(self.contenu, self.etat)
        self.dimensionnement_frame = DimensionnementFrame(self.contenu, self.etat,
                                                          on_calc=self._recalcul)
        self.verification_frame = VerificationFrame(self.contenu, self.etat)
        self.cumul_frame = CumulDebitsFrame(self.contenu, self.etat, on_calc=self._recalcul)
        self.rapport_frame = RapportFrame(self.contenu, self.etat)
        self.profil_complet_frame = ProfilCompletFrame(self.contenu, self.etat)
        self.analyse_frame = AnalyseFrame(self.contenu, self.etat)


    # ------------------------------------------------------------------
    # Barre de menu
    # ------------------------------------------------------------------
    def _construire_menus(self):
        from tkinter import Menu, messagebox
        menubar = Menu(self)

        # --- Fichier ---
        m_fichier = Menu(menubar, tearoff=0)
        m_fichier.add_command(label="Nouveau projet", command=self._nouveau_projet)
        m_fichier.add_command(label="Ouvrir...", command=self._ouvrir_projet)
        m_fichier.add_command(label="Importer Excel...", command=self._importer_excel)
        m_fichier.add_separator()
        m_fichier.add_command(label="Enregistrer", command=self._enregistrer)
        m_fichier.add_command(label="Enregistrer sous...", command=self._enregistrer_sous)
        m_fichier.add_separator()
        m_fichier.add_command(label="Lancer le calcul", command=self._calculer_tout)
        m_fichier.add_command(label="Exporter le rapport (.txt)",
                              command=lambda: self.rapport_frame._export_depuis_menu())
        m_fichier.add_command(label="Exporter le rapport (.docx)",
                              command=lambda: self.rapport_frame._export_docx_depuis_menu())
        m_fichier.add_command(label="Exporter le rapport (.xlsx)",
                              command=lambda: self.rapport_frame._export_xlsx_depuis_menu())
        m_fichier.add_command(label="Exporter le croquis (.png)",
                              command=lambda: self.rapport_frame._export_png_depuis_menu())
        m_fichier.add_separator()
        m_fichier.add_command(label="Quitter", command=self.quit)
        menubar.add_cascade(label="Fichier", menu=m_fichier)

        # --- Affichage ---
        m_aff = Menu(menubar, tearoff=0)
        for key, label in [("projet", "Projet"), ("conduite", "Conduite"),
                           ("schema", "Schéma vidange"), ("profil", "Profil en long"),
                           ("calcul", "Calcul"), ("dimensionnement", "Dimensionnement"),
                           ("verification", "Vérification organes"),
                           ("cumul", "Cumul des débits"),
                           ("rapport", "Rapport"),
                           ("profil_complet", "Profil complet"),
                           ("analyse", "Analyse piézométrique")]:
            m_aff.add_command(label=label, command=lambda k=key: self.afficher_frame(k))
        menubar.add_cascade(label="Affichage", menu=m_aff)

        # --- Aide ---
        m_aide = Menu(menubar, tearoff=0)
        m_aide.add_command(label="Méthode de calcul",
                           command=lambda: messagebox.showinfo(
                               "Méthode de calcul",
                               "Formule explicite MK_A.A (2026)\n\n"
                               "Darcy-Weisbach → Colebrook-White → MK_A.A\n"
                               "Socle fixe (g, k, ν, seuil −3 mCE) — NF EN 805\n"
                               "8 schémas de vidange (amont/aval, PI, asymétrique)."))
        m_aide.add_command(label="À propos",
                           command=lambda: messagebox.showinfo(
                               "À propos",
                               "MK_A.A 2026\n"
                               "Dimensionnement des débits d'air admis en conduites AEP.\n"
                               "Note technique MK_A.A 2026 (Avril 2026) — Confidentiel.\n\n"
                               "Python + CustomTkinter."))
        menubar.add_cascade(label="Aide", menu=m_aide)

        self.config(menu=menubar)

    def _nouveau_projet(self):
        """Réinitialise l'état projet aux valeurs par défaut."""
        defaut = EtatApplication()
        for champ in defaut.__dataclass_fields__:
            setattr(self.etat, champ, getattr(defaut, champ))
        self.etat.resultat = None
        self.etat.erreur = ""
        self.etat.derniere_trace = None
        self._fichier_courant = None
        self.projet_frame.charger()
        self.conduite_frame.charger()
        self.schema_frame.charger()
        self.profil_frame.charger()
        self.verification_frame._maj_liste()
        self._rafraichir_resultats()
        self.afficher_frame("projet")

    # ------------------------------------------------------------------
    # Enregistrer / Enregistrer sous / Ouvrir
    # ------------------------------------------------------------------
    def _enregistrer(self):
        """Enregistre dans le fichier courant ; sinon demande un nom."""
        if self._fichier_courant:
            try:
                self.etat.sauvegarder(self._fichier_courant)
                return
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Enregistrement", f"Erreur : {e}")
        self._enregistrer_sous()

    def _enregistrer_sous(self):
        from tkinter import filedialog, messagebox
        defaut = f"projet_mk_aa_2026_{self.etat.projet or 'sans_titre'}.json"
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile=defaut,
                                            filetypes=[("Projet MK_A.A 2026", "*.json")])
        if not path:
            return
        try:
            self.etat.sauvegarder(path)
            self._fichier_courant = path
            self.title(f"MK_A.A 2026 — {path}")
        except Exception as e:
            messagebox.showerror("Enregistrement", f"Erreur : {e}")

    def _ouvrir_projet(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("Projet MK_A.A 2026", "*.json"), ("Tous fichiers", "*.*")])
        if not path:
            return
        try:
            self.etat.charger_dans(path)   # mutation en place : les frames gardent la référence
        except Exception as e:
            messagebox.showerror("Ouvrir", f"Erreur de lecture : {e}")
            return
        self._fichier_courant = path
        self.title(f"MK_A.A 2026 — {path}")
        self._recharger_ui()

    def _importer_excel(self):
        """Importe les données projet depuis un classeur Excel (modèle V05).

        Pré-remplit tous les champs, lance le calcul et affiche les
        avertissements éventuels du contrôle de validité.
        """
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Données projet Excel", "*.xlsx"), ("Tous fichiers", "*.*")])
        if not path:
            return
        try:
            warnings = self.etat.appliquer_excel(path)
        except Exception as e:
            messagebox.showerror("Importer Excel", f"Erreur de lecture : {e}")
            return
        self._fichier_courant = None
        self.title("MK_A.A 2026 — import Excel")
        self._recharger_ui()
        if warnings:
            messagebox.showwarning(
                "Import Excel",
                "Données importées et calcul lancé.\n\n"
                "Contrôle de validité :\n- " + "\n- ".join(warnings))
        else:
            messagebox.showinfo("Import Excel",
                                "Données importées et calcul lancé.")

    def _recharger_ui(self):
        """Recharge tous les champs depuis l'état courant."""
        self.projet_frame.charger()
        self.conduite_frame.charger()
        self.schema_frame.charger()
        self.profil_frame.charger()
        self.verification_frame._maj_liste()
        self._recalcul()
        self.afficher_frame("projet")

    # ------------------------------------------------------------------
    def afficher_frame(self, key):
        frame = self.frames[key]
        frame.tkraise()
        if key == "profil":
            self.profil_frame._actualiser_actifs()
        for k, b in self.side_buttons.items():
            b.configure(fg_color="#2E2E2E" if k == key else "transparent")

    def _recalcul(self):
        """Re-calcul automatique lorsque des données changent (léger)."""
        try:
            self.etat.calculer()
        except Exception as e:
            self.etat.erreur = str(e)
        self._rafraichir_resultats()
        if hasattr(self, "profil_frame"):
            self.profil_frame._actualiser_actifs()

    def _calculer_tout(self):
        """Recalcule explicitement et rafraîchit la saisie déduite."""
        try:
            self.etat.calculer()
            self.etat.erreur = ""
        except Exception as e:
            self.etat.erreur = str(e)
        # rafraîchir les champs déduits de la conduite
        self.conduite_frame._actualiser_deduit()
        self.profil_frame._actualiser_actifs()
        self._rafraichir_resultats()
        # aller sur l'onglet résultats
        self.afficher_frame("calcul")

    def _rafraichir_resultats(self):
        self.calcul_frame.afficher(self.etat.resultat)
        self.dimensionnement_frame.afficher(self.etat.derniere_trace)
        # synchroniser les entrées cumul
        if hasattr(self, "cumul_frame"):
            self.cumul_frame.sync_hz()
            self.cumul_frame.ent_hz.delete(0, "end")
            self.cumul_frame.ent_hz.insert(0, str(self.etat.hz_casse_franche))
            self.cumul_frame.ent_vanne_dn.delete(0, "end")
            self.cumul_frame.ent_vanne_dn.insert(0, str(self.etat.dn_vanne_sectionnement))
            self.cumul_frame.ent_pn.delete(0, "end")
            self.cumul_frame.ent_pn.insert(0, str(self.etat.pression_nominale))
        if hasattr(self, "verification_frame"):
            self.verification_frame._maj_liste()


def lancer():
    app = Application()
    app.mainloop()
