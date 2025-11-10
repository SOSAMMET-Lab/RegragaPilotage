# src/io_excel.py

import pandas as pd

def read_workbook(file_like):
    """
    Lit un fichier Excel (chemin ou file-like) et retourne un dict de DataFrames.
    Attendu: feuilles principales: tbl_Produits, tbl_Ventes, tbl_Recettes (si présentes).
    """
    try:
        xls = pd.read_excel(file_like, sheet_name=None, engine="openpyxl")
    except Exception as e:
        raise RuntimeError(f"Erreur lecture Excel: {e}")

    # Normaliser noms des feuilles clés
    data = {}
    if "tbl_Produits" in xls:
        data["produits"] = xls["tbl_Produits"].copy()
    else:
        # si pas trouvée, essayer heuristique
        for name, df in xls.items():
            if "produit" in name.lower():
                data["produits"] = df.copy()
                break

    if "tbl_Ventes" in xls:
        data["ventes"] = xls["tbl_Ventes"].copy()
    else:
        for name, df in xls.items():
            if "vente" in name.lower() or "sales" in name.lower():
                data["ventes"] = df.copy()
                break

    if "tbl_Recettes" in xls:
        data["recettes"] = xls["tbl_Recettes"].copy()
    else:
        for name, df in xls.items():
            if "recette" in name.lower() or "recipe" in name.lower():
                data["recettes"] = df.copy()
                break

    return data

def clean_codes(df, code_col_candidates=("Code produit","code","code_produit","Code")):
    """
    Retourne un DataFrame où la colonne code est normalisée en 'code'.
    """
    if df is None:
        return None
    df = df.copy()
    found = None
    for c in code_col_candidates:
        if c in df.columns:
            found = c
            break
    if found:
        df.rename(columns={found: "code"}, inplace=True)
        df["code"] = df["code"].astype(str).str.strip()
    return df