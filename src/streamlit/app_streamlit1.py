# src/streamlit/app_streamlit1.py

import sys
import os

# rendre accessible le dossier parent 'src' si on exécute depuis src/streamlit
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import streamlit as st
import pandas as pd
import plotly.express as px

from io_excel import read_workbook, clean_codes
from calc import build_tableau_pilotage

st.set_page_config(page_title="Regraga - Pilotage", layout="wide")

st.title("Regraga - Tableau de Pilotage")

uploaded = st.file_uploader("Charge ton fichier Excel (.xlsx) contenant tbl_Produits / tbl_Ventes / tbl_Recettes", type=["xlsx"])

# zone d'aide et exemple
with st.expander("Exemple de données / Tutoriel rapide"):
    st.write("- Feuille `tbl_Produits` : colonnes au minimum `Code produit` ou `code`, `CMP` (coût moyen) ;")
    st.write("- Feuille `tbl_Ventes` : colonnes au minimum `Code produit` ou `code`, `qte` ou `quantité` ;")
    st.write("Tu peux charger un fichier d'exemple si tu veux tester.")

if uploaded is None:
    st.info("Charge un fichier Excel pour générer le tableau de pilotage. Tu peux aussi tester avec un fichier minimal.")
    # bouton test
    if st.button("Générer avec données de test"):
        # créer jeux de test minimal
        produits = pd.DataFrame({
            "code":["P1","P2","P3"],
            "CMP":[10.0, 5.0, 2.5],
            "Description":["Prod A","Prod B","Prod C"],
            "prix_vente":[15.0, 8.0, 4.0]
        })
        ventes = pd.DataFrame({
            "code":["P1","P2","P1"],
            "qte":[3, 5, 2]
        })
        table = build_tableau_pilotage(produits, ventes)
        st.dataframe(table)
        csv = table.to_csv(index=False).encode("utf-8")
        st.download_button("Télécharger CSV", csv, file_name="pilotage_test.csv", mime="text/csv")
    st.stop()

# try reading the uploaded file
try:
    data = read_workbook(uploaded)
except Exception as e:
    st.error(f"Erreur lors de la lecture du fichier Excel: {e}")
    st.stop()

produits = data.get("produits")
ventes = data.get("ventes")

if produits is None:
    st.error("Feuille 'tbl_Produits' introuvable ou mal nommée. Vérifie ton fichier Excel.")
    st.stop()
if ventes is None:
    st.warning("Feuille 'tbl_Ventes' introuvable. L'analyse sera limitée.")

# normaliser codes
produits = clean_codes(produits)
ventes = clean_codes(ventes)

# build tableau
try:
    table_pilotage = build_tableau_pilotage(produits, ventes)
except Exception as e:
    st.error(f"Erreur lors du calcul du tableau de pilotage: {e}")
    st.exception(e)
    st.stop()

st.markdown("### Résultats")
st.dataframe(table_pilotage)

# graphique simple
if not table_pilotage.empty:
    fig = px.bar(table_pilotage, x="code", y="qte", title="Quantités vendues par produit")
    st.plotly_chart(fig, use_container_width=True)

# bouton export Excel minimal
from io import BytesIO
import xlsxwriter

def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine="xlsxwriter")
    df.to_excel(writer, index=False, sheet_name="pilotage")
    writer.save()
    output.seek(0)
    return output

st.download_button("Télécharger tableau (Excel)", data=to_excel(table_pilotage), file_name="tableau_pilotage.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")