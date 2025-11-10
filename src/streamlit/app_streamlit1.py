import streamlit as st
import pandas as pd
from src.io_excel import read_workbook, clean_codes
from src.calc import calc_cmp, cost_per_product, repartition_charges

st.set_page_config(page_title="Regraga - Mini application coûts", layout="wide")
st.title("Regraga - Mini application coûts")

uploaded = st.file_uploader("Chargez votre fichier Excel (Dashboard_Regraga.xlsx) ou glissez‑déposez", type=["xlsx"])
# Option: lire directement depuis data si tu veux (décommenter)
# path = "data/Copie de Dashboard Regraga 2026.xlsx"
# tables = read_workbook(path)

if uploaded is not None:
    tables = read_workbook(uploaded)
    st.success("Fichier chargé")
    # Affiche feuilles détectées
    non_empty = [k for k,v in tables.items() if isinstance(v, pd.DataFrame) and not v.empty]
    st.write("Fichiers chargés:", non_empty)

    # Nettoyage codes de base (exemples)
    for sheet in ['tbl_Ventes','tbl_Recettes','tbl_Stock','tbl_Produits','tbl_Achats','tbl_Charges_Fixes']:
        if sheet in tables and not tables[sheet].empty:
            # normaliser noms de colonnes simples si besoin
            pass

    # 1) CMP
    if 'tbl_Stock' in tables and 'tbl_Achats' in tables and (not tables['tbl_Stock'].empty) and (not tables['tbl_Achats'].empty):
        cmp_df = calc_cmp(tables['tbl_Stock'], tables['tbl_Achats'])
        st.subheader("CMP effectif (extrait)")
        st.dataframe(cmp_df.head(100))
    else:
        cmp_df = pd.DataFrame()
        st.warning("tbl_Stock ou tbl_Achats manquante pour calcul CMP")

    # 2) Coût matière par produit
    if 'tbl_Recettes' in tables and not tables['tbl_Recettes'].empty:
        cost_prod, merged_lines = cost_per_product(tables['tbl_Recettes'], cmp_df)
        st.subheader("Coût matière par produit (extrait)")
        st.dataframe(cost_prod.head(200))
    else:
        cost_prod = pd.DataFrame()
        st.warning("tbl_Recettes manquante")

    # 3) Répartition des charges
    if 'tbl_Charges_Fixes' in tables and 'tbl_Ventes' in tables and (not tables['tbl_Charges_Fixes'].empty) and (not tables['tbl_Ventes'].empty):
        ventes_with_charges, total_glob, spec_df = repartition_charges(tables['tbl_Charges_Fixes'], tables['tbl_Ventes'])
        st.subheader("Ventes avec charges réparties (extrait)")
        to_show = ['Cde_Prdt','Famille','CA ligne','Charge_Globale_Par_Portion','Charge_Specifique_Par_Portion']
        present = [c for c in to_show if c in ventes_with_charges.columns]
        st.dataframe(ventes_with_charges[present].head(200))
    else:
        ventes_with_charges = pd.DataFrame()
        st.warning("tbl_Charges_Fixes ou tbl_Ventes manquante pour répartition charges")

    # 4) Tableau final produits
    if not cost_prod.empty and 'tbl_Produits' in tables and not tables['tbl_Produits'].empty:
        prod = tables['tbl_Produits'].copy()
        # garantir colonnes numériques
        prod['Prix Menu'] = pd.to_numeric(prod.get('Prix Menu',0), errors='coerce').fillna(0)
        prod = prod.merge(cost_prod, on='Cde_Prdt', how='left').fillna(0)
        # charges par produit (moyenne par produit depuis ventes_with_charges)
        if not ventes_with_charges.empty:
            charges_prod = ventes_with_charges.groupby('Cde_Prdt', as_index=False).agg({
                'Charge_Globale_Par_Portion':'mean',
                'Charge_Specifique_Par_Portion':'mean'
            }).fillna(0)
            prod = prod.merge(charges_prod, on='Cde_Prdt', how='left').fillna(0)
        prod['Charges_par_Portion'] = prod.get('Charge_Globale_Par_Portion',0) + prod.get('Charge_Specifique_Par_Portion',0)
        prod['Coût_Matière_Portion'] = pd.to_numeric(prod.get('Coût_Matière_Portion', prod.get('Coût Moyen Portion',0)), errors='coerce').fillna(0)
        prod['Marge_brute'] = prod['Prix Menu'] - prod['Coût_Matière_Portion']
        prod['Marge_nette'] = prod['Marge_brute'] - prod['Charges_par_Portion']
        st.subheader("Tableau produits final")
        show_cols = ['Cde_Prdt','Produit','Famille','Coût_Matière_Portion','Prix Menu','Charges_par_Portion','Marge_brute','Marge_nette']
        present_cols = [c for c in show_cols if c in prod.columns]
        st.dataframe(prod[present_cols].head(200))

        # Export Excel - préparation et bouton
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            prod.to_excel(writer, index=False, sheet_name='Produits_Final')
            if not cmp_df.empty:
                cmp_df.to_excel(writer, index=False, sheet_name='CMP')
            if not cost_prod.empty:
                cost_prod.to_excel(writer, index=False, sheet_name='Coût_Produits')
            if not ventes_with_charges.empty:
                ventes_with_charges.to_excel(writer, index=False, sheet_name='Ventes_Charges')
        st.download_button("Télécharger résultats (Excel)", buffer.getvalue(), file_name="Regraga_Resultats.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Impossible de construire le tableau final produits (vérifier que tbl_Produits, tbl_Recettes et CMP existent).")
else:
    st.info("Chargez votre fichier Excel (Dashboard_Regraga.xlsx) depuis le bouton ci‑dessous.")
from src.calc import build_tableau_pilotage

# Génération du tableau final de pilotage
if not cost_prod.empty and not tables['tbl_Produits'].empty:
    tableau = build_tableau_pilotage(tables['tbl_Produits'], cost_prod, ventes_with_charges)
    st.subheader("📊 Tableau final de pilotage")
    colonnes = [
        'Cde_Prdt','Produit','Famille','Prix Menu','Coût_Matière_Portion',
        'Charge_Globale_Par_Portion','Charge_Specifique_Par_Portion','Charges_par_Portion',
        'Marge_brute','Marge_nette','Food cost %','% Charges','Scoring','Seuils Tolérés','Alerte'
    ]
    st.dataframe(tableau[colonnes].head(100))

    # Export Excel
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        tableau.to_excel(writer, index=False, sheet_name='Tableau_Pilotage')
        cost_prod.to_excel(writer, index=False, sheet_name='Coût_Produits')
        ventes_with_charges.to_excel(writer, index=False, sheet_name='Ventes_Charges')
    st.download_button("📥 Télécharger le tableau de pilotage", buffer.getvalue(), file_name="Pilotage_Regraga.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")