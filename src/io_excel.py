import pandas as pd

def read_workbook(path_or_buffer):
    """
    Lit l'Excel et retourne un dict de DataFrame pour les feuilles attendues.
    path_or_buffer peut être un chemin ou un buffer uploadé par Streamlit.
    """
    xls = pd.read_excel(path_or_buffer, sheet_name=None, engine="openpyxl")
    # noms de feuilles attendues (ajoute/retire selon ton fichier)
    expected = [
        "tbl_Ventes","tbl_Recettes","tbl_Stock","tbl_Produits",
        "tbl_Charges_Fixes","tbl_Achats","tbl_Sorties","Référentiels",
        "tbl_Couts","tbl_PtDj&Sup","tbl_PtDj","tbl_PtDj_sup"
    ]
    out = {}
    for name in expected:
        out[name] = xls.get(name, pd.DataFrame()).copy()
    # Ajoute toutes les feuilles non listées aussi (si besoin)
    for name, df in xls.items():
        if name not in out:
            out[name] = df.copy()
    return out

def clean_codes(df, col):
    """Nettoyage basique d'une colonne code : strip, normaliser espaces"""
    df = df.copy()
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.replace(r'\s+',' ', regex=True)
    return df