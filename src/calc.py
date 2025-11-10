# src/calc.py

import pandas as pd
import numpy as np

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df

def build_tableau_pilotage(produits_df, ventes_df):
    """
    Produit un tableau de pilotage simple: total ventes par produit, CMP et marge fictive.
    Attentes minimalistes: produits_df contient 'code' et 'CMP' (coût), ventes_df contient 'code' et 'quantité'/'qte'/'quantity'
    """
    if produits_df is None or ventes_df is None:
        return pd.DataFrame()

    produits = produits_df.copy()
    ventes = ventes_df.copy()

    # normaliser noms colonnes
    if "quantité" in ventes.columns:
        ventes.rename(columns={"quantité": "qte"}, inplace=True)
    if "qte" not in ventes.columns and "quantity" in ventes.columns:
        ventes.rename(columns={"quantity": "qte"}, inplace=True)
    if "qte" not in ventes.columns:
        # essayer d'inférer
        possible = [c for c in ventes.columns if "qte" in c.lower() or "qty" in c.lower()]
        if possible:
            ventes.rename(columns={possible[0]: "qte"}, inplace=True)
        else:
            ventes["qte"] = 1

    # CMP attendu
    if "CMP" not in produits.columns:
        # si prix d'achat manquant, essayer 'Prix' ou 'prix_achat'
        for c in ["Prix", "prix_achat", "prix"]:
            if c in produits.columns:
                produits.rename(columns={c: "CMP"}, inplace=True)
                break
    produits["CMP"] = pd.to_numeric(produits.get("CMP", pd.Series(0)), errors="coerce").fillna(0)
    ventes["qte"] = pd.to_numeric(ventes["qte"], errors="coerce").fillna(0)

    # joindre
    ventes_agg = ventes.groupby("code", as_index=False).agg({"qte":"sum"})
    table = ventes_agg.merge(produits, on="code", how="left")

    table["total_cost"] = table["CMP"] * table["qte"]
    # si tu as prix de vente, calcul marge sinon mettre NaN
    if "prix_vente" in table.columns:
        table["prix_vente"] = pd.to_numeric(table["prix_vente"], errors="coerce").fillna(0)
    elif "Prix de vente" in table.columns:
        table["prix_vente"] = pd.to_numeric(table["Prix de vente"], errors="coerce").fillna(0)

    table["revenue"] = table.get("prix_vente", 0) * table["qte"]
    table["marge"] = table["revenue"] - table["total_cost"]
    table = table.sort_values(by="qte", ascending=False)

    return table