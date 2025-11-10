# list_sheets.py
import pandas as pd, pathlib
p = pathlib.Path("Dashboard Regraga 2026.xlsx")
xl = pd.ExcelFile(p, engine="openpyxl")
print("Feuilles:", xl.sheet_names)
for s in ["tbl_Ventes", "tbl_Produits", "tbl_Produits "]:
    if s in xl.sheet_names:
        df = pd.read_excel(xl, s)
        print(f"\nTrouvé onglet: {s} shape:", df.shape)
        print(df.head(3).to_dict('records'))
    else:
        print(f"\nOnglet absent: {s}")