# app.py
# Prototype léger pour gestion économat local (lecture/écriture Excel)
# Utilise pandas + openpyxl pour manipuler le classeur et tkinter pour l'interface.
import pathlib
import threading
import time
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox

# -------- CONFIG --------
EXCEL_PATH = pathlib.Path("Dashboard Regraga 2026.xlsx")  # nom du fichier (déjà présent)
# On choisira dynamiquement les noms d'onglets si nécessaire
SHEET_VENTES = "tbl_Ventes"
SHEET_PRODUITS_PREFIX = "tbl_Produits"  # on accepte "tbl_Produits" ou "tbl_Produits " (espace)
SAVE_INTERVAL_SEC = 0  # si >0 : auto-save périodique (0 = pas d'auto save)
# ------------------------

def find_sheet_by_prefix(xl: pd.ExcelFile, prefix: str):
    for s in xl.sheet_names:
        if s == prefix or s.startswith(prefix):
            return s
    return None

def load_tables():
    """Charge les tables principales depuis le fichier Excel."""
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Fichier introuvable : {EXCEL_PATH.resolve()}")
    xl = pd.ExcelFile(EXCEL_PATH, engine="openpyxl")
    # Trouver sheet produits avec tolérance d'espace/trailing
    sheet_produits = find_sheet_by_prefix(xl, SHEET_PRODUITS_PREFIX) or "tbl_Produits"
    ventes = pd.read_excel(xl, SHEET_VENTES) if SHEET_VENTES in xl.sheet_names else pd.DataFrame()
    produits = pd.read_excel(xl, sheet_produits) if sheet_produits in xl.sheet_names else pd.DataFrame()
    return ventes, produits

def save_tables(ventes, produits):
    """Réécrit les deux onglets en créant un fichier temporaire puis remplace l'original."""
    import tempfile, os
    # charger tout le classeur existant
    xl = pd.ExcelFile(EXCEL_PATH, engine="openpyxl")
    # créer writer sur un fichier temporaire et recopier tout en remplaçant les onglets ciblés
    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
        # recopier onglets non ciblés
        for sheet in xl.sheet_names:
            if sheet == SHEET_VENTES:
                ventes.to_excel(writer, sheet_name=sheet, index=False)
            elif sheet.startswith(SHEET_PRODUITS_PREFIX):
                produits.to_excel(writer, sheet_name=sheet, index=False)
            else:
                # lire et réécrire l'onglet tel quel
                df = pd.read_excel(xl, sheet)
                df.to_excel(writer, sheet_name=sheet, index=False)
    # remplacer l'original (écrase)
    os.replace(tmp_path, EXCEL_PATH)
# utilitaires pour noms de colonnes
def choose_col(df, possibles):
    for c in possibles:
        if c in df.columns:
            return c
    return None

def compute_kpis(ventes_df, produits_df):
    """Calcule des KPI simples en s'adaptant aux noms de colonnes présents."""
    k = {}
    if ventes_df.empty:
        k["Total CA"] = 0
        k["Coût matière total"] = 0
        k["Food cost %"] = 0
        k["Top produits"] = {}
        return k

    # colonnes prévues dans ton fichier
    col_prod = choose_col(ventes_df, ["Produit", "Nom du Produit", "Nom Produit"])
    col_qte = choose_col(ventes_df, ["Qté Vendue", "Qté vendue", "Quantité", "Qte", "Qty"])
    col_prix = choose_col(ventes_df, ["Prix Menu", "Prix de vente", "Prix", "PrixVente"])
    col_ca = choose_col(ventes_df, ["CA ligne", "CA", "Montant"])
    col_cmp = choose_col(ventes_df, ["CMP_par_portion", "Coût Moyen Portion", "Coût_par_portion", "CMP"])
    col_cm_l = choose_col(ventes_df, ["Coût matière ligne", "Coût matière", "Cout_ligne"])

    # créer CA ligne si absent
    if col_ca is None:
        px = col_prix if col_prix else None
        q = col_qte if col_qte else None
        if px and q:
            ventes_df["CA ligne"] = ventes_df[px].fillna(0) * ventes_df[q].fillna(0)
        else:
            ventes_df["CA ligne"] = 0
        col_ca = "CA ligne"

    # créer Coût matière ligne si absent
    if col_cm_l is None:
        cmpcol = col_cmp if col_cmp else None
        q = col_qte if col_qte else None
        if cmpcol and q:
            ventes_df["Coût matière ligne"] = ventes_df[cmpcol].fillna(0) * ventes_df[q].fillna(0)
        else:
            ventes_df["Coût matière ligne"] = 0
        col_cm_l = "Coût matière ligne"

    total_ca = ventes_df[col_ca].sum()
    total_cm = ventes_df[col_cm_l].sum()
    k["Total CA"] = float(total_ca)
    k["Coût matière total"] = float(total_cm)
    k["Food cost %"] = float((total_cm / total_ca) * 100) if total_ca else 0.0

    # top produits par CA (utilise la colonne produit trouvée)
    prod_col_for_group = col_prod if col_prod else ventes_df.columns[0]
    top = ventes_df.groupby(prod_col_for_group, dropna=True).agg({col_ca: "sum"}).sort_values(col_ca, ascending=False).head(5)
    k["Top produits"] = top[col_ca].to_dict() if not top.empty else {}
    return k

# ---------- Interface Tkinter ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Regraga Economat - Prototype local")
        self.geometry("820x520")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            self.ventes_df, self.produits_df = load_tables()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier Excel:\n{e}")
            self.ventes_df = pd.DataFrame()
            self.produits_df = pd.DataFrame()
        self.create_widgets()
        self.refresh_ui()

        if SAVE_INTERVAL_SEC > 0:
            self.auto_save_thread = threading.Thread(target=self.auto_save_loop, daemon=True)
            self.auto_save_thread.start()

    def create_widgets(self):
        # Frame KPIs
        f_kpi = ttk.LabelFrame(self, text="KPI rapides")
        f_kpi.pack(fill="x", padx=10, pady=8)
        self.kpi_vars = {
            "Total CA": tk.StringVar(value="0"),
            "Coût matière total": tk.StringVar(value="0"),
            "Food cost %": tk.StringVar(value="0")
        }
        for i, (k, v) in enumerate(self.kpi_vars.items()):
            ttk.Label(f_kpi, text=k + ":").grid(row=0, column=2*i, sticky="w", padx=6)
            ttk.Label(f_kpi, textvariable=v, foreground="blue").grid(row=0, column=2*i+1, sticky="w")

        # Frame saisie vente
        f_sale = ttk.LabelFrame(self, text="Saisie vente")
        f_sale.pack(fill="x", padx=10, pady=8)
        ttk.Label(f_sale, text="Produit:").grid(row=0, column=0, padx=6, pady=6, sticky="e")

        prod_col = "Produit" if "Produit" in self.produits_df.columns else (self.produits_df.columns[0] if len(self.produits_df.columns)>0 else "")
        self.prod_cb = ttk.Combobox(f_sale, values=list(self.produits_df.get(prod_col, [])))
        self.prod_cb.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(f_sale, text="Quantité:").grid(row=0, column=2, padx=6, pady=6, sticky="e")
        self.qty_e = ttk.Entry(f_sale, width=8)
        self.qty_e.grid(row=0, column=3, padx=6, pady=6)
        ttk.Button(f_sale, text="Enregistrer vente", command=self.add_sale).grid(row=0, column=4, padx=8)

        # Frame journal ventes (table)
        f_table = ttk.LabelFrame(self, text="Journal ventes (dernières lignes)")
        f_table.pack(fill="both", expand=True, padx=10, pady=8)
        cols = ["Date", "Produit", "Qté Vendue", "Prix Menu", "CA ligne"]
        self.tree = ttk.Treeview(f_table, columns=cols, show="headings", height=14)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140)
        self.tree.pack(fill="both", expand=True)

        # Buttons bas
        bframe = ttk.Frame(self)
        bframe.pack(fill="x", padx=10, pady=6)
        ttk.Button(bframe, text="Rafraîchir (recharger fichier)", command=self.manual_reload).pack(side="left")
        ttk.Button(bframe, text="Sauvegarder maintenant", command=self.manual_save).pack(side="left", padx=6)
        ttk.Button(bframe, text="Ouvrir fichier Excel (OneDrive)", command=self.open_excel).pack(side="right")

    def refresh_ui(self):
        # recalc KPIs et rafraichir table
        try:
            self.ventes_df, self.produits_df = load_tables()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier Excel:\n{e}")
            return
        k = compute_kpis(self.ventes_df, self.produits_df)
        self.kpi_vars["Total CA"].set(f"{k['Total CA']:.2f}")
        self.kpi_vars["Coût matière total"].set(f"{k['Coût matière total']:.2f}")
        self.kpi_vars["Food cost %"].set(f"{k['Food cost %']:.1f}%")
        # remplir table ventes (dernières 50)
        for i in self.tree.get_children():
            self.tree.delete(i)
        if not self.ventes_df.empty:
            # déterminer colonnes sources pour affichage
            col_date = choose_col(self.ventes_df, ["Date", "date"])
            col_prod = choose_col(self.ventes_df, ["Produit", "Nom du Produit", "Nom Produit"]) or self.ventes_df.columns[0]
            col_qte = choose_col(self.ventes_df, ["Qté Vendue", "Qté vendue", "Quantité", "Qte", "Qty"])
            col_prix = choose_col(self.ventes_df, ["Prix Menu", "Prix de vente", "Prix", "PrixVente"])
            col_ca = choose_col(self.ventes_df, ["CA ligne", "CA", "Montant"]) or "CA ligne"
            last = self.ventes_df.tail(50).fillna("")
            for _, r in last.iterrows():
                ca = r.get(col_ca, r.get(col_qte, 0) * r.get(col_prix, 0))
                self.tree.insert("", "end", values=[r.get(col_date, ""), r.get(col_prod, ""), r.get(col_qte, ""), r.get(col_prix, ""), f"{float(ca or 0):.2f}"])

        # rafraîchir combobox produits
        prod_col = "Produit" if "Produit" in self.produits_df.columns else (self.produits_df.columns[0] if len(self.produits_df.columns)>0 else "")
        self.prod_cb["values"] = list(self.produits_df.get(prod_col, []))

    def add_sale(self):
        prod = self.prod_cb.get().strip()
        try:
            qty = float(self.qty_e.get())
        except:
            messagebox.showwarning("Saisie", "Quantité invalide")
            return
        if prod == "" or qty <= 0:
            messagebox.showwarning("Saisie", "Produit ou quantité manquante")
            return
        # trouver prix et CMP dans tbl_Produits
        prod_col = "Produit" if "Produit" in self.produits_df.columns else (self.produits_df.columns[0] if len(self.produits_df.columns)>0 else "")
        row = self.produits_df[self.produits_df.get(prod_col,"") == prod]
        if row.empty:
            messagebox.showerror("Produit", "Produit introuvable dans tbl_Produits")
            return
        prix = float(row.iloc[0].get("Prix Menu", row.iloc[0].get("Prix Menu", 0) or 0))
        cmp_par = float(row.iloc[0].get("Coût Moyen Portion", row.iloc[0].get("Coût Moyen Portion", 0) or 0))
        ca_ligne = qty * prix
        cout_ligne = qty * cmp_par
        # construire nouvelle ligne de ventes
        new = {
            "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Produit": prod,
            "Qté Vendue": qty,
            "Prix Menu": prix,
            "CA ligne": ca_ligne,
            "CMP_par_portion": cmp_par,
            "Coût matière ligne": cout_ligne
        }
        self.ventes_df = pd.concat([self.ventes_df, pd.DataFrame([new])], ignore_index=True)
        try:
            save_tables(self.ventes_df, self.produits_df)
        except Exception as e:
            messagebox.showerror("Erreur sauvegarde", f"Impossible de sauvegarder:\n{e}")
            return
        self.qty_e.delete(0, "end")
        self.refresh_ui()
        messagebox.showinfo("OK", "Vente enregistrée et fichier mis à jour.")

    def manual_reload(self):
        self.refresh_ui()
        messagebox.showinfo("Rafraîchi", "Fichier rechargé depuis le disque.")

    def manual_save(self):
        try:
            save_tables(self.ventes_df, self.produits_df)
            messagebox.showinfo("Sauvegarde", "Fichier Excel sauvegardé.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder :\n{e}")

    def open_excel(self):
        import os, subprocess
        try:
            subprocess.Popen([str(EXCEL_PATH.resolve())], shell=True)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le fichier :\n{e}")

    def auto_save_loop(self):
        while True:
            time.sleep(SAVE_INTERVAL_SEC)
            try:
                save_tables(self.ventes_df, self.produits_df)
            except:
                pass

    def on_close(self):
        if messagebox.askyesno("Quitter", "Souhaitez-vous quitter l'application ?"):
            self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()