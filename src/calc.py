import pandas as pd
import numpy as np

def ensure_units(df, qty_col='Quantité', unit_col='Unité'):
    """
    Normalise Quantité en kg/L si unité en g ou ml.
    Retourne copie.
    """
    df = df.copy()
    if unit_col in df.columns and qty_col in df.columns:
        df[unit_col] = df[unit_col].astype(str).str.strip().str.lower()
        # masks
        mask_g = df[unit_col].str.contains(r'\bg\b', regex=True, na=False) | df[unit_col].str.contains(r'\bgram', na=False)
        mask_ml = df[unit_col].str.contains(r'\bml\b', regex=True, na=False)
        # convertir
        df.loc[mask_g, qty_col] = pd.to_numeric(df.loc[mask_g, qty_col], errors='coerce').fillna(0) / 1000.0
        df.loc[mask_ml, qty_col] = pd.to_numeric(df.loc[mask_ml, qty_col], errors='coerce').fillna(0) / 1000.0
        # autres unités : leave as is (Pièce, etc.)
    return df

def calc_cmp(tbl_stock, tbl_achats,
             col_code='Cde_Ingrdt',
             col_stock_qty='Stock Départ',
             col_stock_val='Valeur stock initiale',
             col_buy_qty="Qté d'Achat",
             col_buy_val='Valeur Ligne'):
    """
    Calcule le CMP effectif par ingrédient à partir du stock initial + achats cumulés.
    Retour : DataFrame avec colonne CMP_effectif.
    """
    # Préparer achats
    a = tbl_achats.copy()
    if col_buy_qty in a.columns:
        a[col_buy_qty] = pd.to_numeric(a[col_buy_qty], errors='coerce').fillna(0)
    else:
        a[col_buy_qty] = 0
    if col_buy_val in a.columns:
        a[col_buy_val] = pd.to_numeric(a[col_buy_val], errors='coerce').fillna(0)
    else:
        a[col_buy_val] = 0
    buys = a.groupby(col_code, as_index=False).agg({col_buy_qty:'sum', col_buy_val:'sum'})

    # Préparer stock
    s = tbl_stock.copy()
    if col_stock_qty in s.columns:
        s[col_stock_qty] = pd.to_numeric(s[col_stock_qty], errors='coerce').fillna(0)
    else:
        s[col_stock_qty] = 0
    if col_stock_val in s.columns:
        s[col_stock_val] = pd.to_numeric(s[col_stock_val], errors='coerce').fillna(0)
    else:
        s[col_stock_val] = 0

    merged = s.merge(buys, on=col_code, how='left').fillna(0)
    merged['Quantité_totale'] = merged[col_stock_qty] + merged[col_buy_qty]
    merged['Valeur_totale'] = merged[col_stock_val] + merged[col_buy_val]
    merged['CMP_effectif'] = np.where(merged['Quantité_totale']>0,
                                      merged['Valeur_totale'] / merged['Quantité_totale'],
                                      0)
    # Nettoyage minimal : garder colonnes clefs
    out = merged[[col_code,'CMP_effectif','Quantité_totale','Valeur_totale']].copy()
    return out

def cost_per_product(tbl_recettes, cmp_df,
                     code_prod='Cde_Prdt', code_ing='Cde_Ingrdt',
                     qty_col='Quantité', unit_col='Unité'):
    """
    Calcule le coût matière par produit (portion) en multipliant quantités normalisées par CMP_effectif.
    Retour : (cost_product_df, merged_debug_df)
    """
    r = tbl_recettes.copy()
    # normaliser unités (g->kg, ml->L)
    r = ensure_units(r, qty_col, unit_col)
    r[qty_col] = pd.to_numeric(r.get(qty_col,0), errors='coerce').fillna(0)
    cmp = cmp_df.copy()
    # s'assurer colonnes nommées correctement pour merge
    if code_ing not in cmp.columns:
        # si cmp a colonne différente, on laisse la merge échouer proprement (sera rempli de 0)
        pass
    merged = r.merge(cmp[[code_ing,'CMP_effectif']], left_on=code_ing, right_on=code_ing, how='left')
    merged['CMP_effectif'] = pd.to_numeric(merged.get('CMP_effectif',0), errors='coerce').fillna(0)
    merged['cout_ligne'] = merged[qty_col] * merged['CMP_effectif']
    cost_product = merged.groupby(code_prod, as_index=False)['cout_ligne'].sum().rename(columns={'cout_ligne':'Coût_Matière_Portion'})
    return cost_product, merged

def repartition_charges(tbl_charges, tbl_ventes, total_ca=None,
                        col_type='Type d’affectation', col_fam='Famille affectée',
                        col_montant='Montant_Mensuel', col_ca='CA ligne'):
    """
    Répartit charges globales par CA et charges spécifiques par famille.
    Retour : ventes_with_charges, montants_globaux, dataframe_charges_specifiques
    """
    c = tbl_charges.copy()
    # Nettoyage colonnes
    c[col_montant] = pd.to_numeric(c.get(col_montant,0), errors='coerce').fillna(0)
    c[col_type] = c.get(col_type,'').astype(str)
    # Globales
    mask_glob = c[col_type].str.lower().str.contains('glob', na=False)
    globales = c.loc[mask_glob, col_montant].sum()
    # Spécifiques par famille
    spec = c.loc[~mask_glob].groupby(col_fam, as_index=False)[col_montant].sum().rename(columns={col_montant:'Montant_Famille'})

    v = tbl_ventes.copy()
    v[col_ca] = pd.to_numeric(v.get(col_ca,0), errors='coerce').fillna(0)
    total_ca = total_ca if total_ca is not None else v[col_ca].sum()
    if total_ca > 0:
        v['Charge_Globale_Ligne'] = v[col_ca] / total_ca * globales
    else:
        v['Charge_Globale_Ligne'] = 0
    # si Qté Vendue existe
    if 'Qté Vendue' in v.columns:
        v['Charge_Globale_Par_Portion'] = v.apply(lambda r: r['Charge_Globale_Ligne']/r['Qté Vendue'] if r.get('Qté Vendue',0)>0 else 0, axis=1)
    else:
        v['Charge_Globale_Par_Portion'] = 0

    # joindre charges spécifiques aux ventes via Famille
    v = v.merge(spec, left_on='Famille', right_on=col_fam, how='left').fillna({'Montant_Famille':0})

    # calcul CA famille
    famille_ca = v.groupby('Famille', as_index=False)[col_ca].sum().rename(columns={col_ca:'CA_Famille'})
    v = v.merge(famille_ca, on='Famille', how='left')
    # Charge spécifique par portion (répartition de Montant_Famille proportionnelle au CA famille)
    v['Charge_Specifique_Par_Portion'] = 0.0
    mask = (v['CA_Famille']>0) & (v.get('Qté Vendue',0)>0)
    v.loc[mask, 'Charge_Specifique_Par_Portion'] = (v['Montant_Famille'] * (v[col_ca]/v['CA_Famille'])) / v['Qté Vendue']
    return v, globales, spec
def build_tableau_pilotage(tbl_produits, cost_prod, ventes_with_charges):
    df = tbl_produits.copy()
    df['Prix Menu'] = pd.to_numeric(df.get('Prix Menu', 0), errors='coerce').fillna(0)
    df = df.merge(cost_prod, on='Cde_Prdt', how='left').fillna(0)

    # Charges par portion (moyenne par produit)
    if not ventes_with_charges.empty:
        charges_prod = ventes_with_charges.groupby('Cde_Prdt', as_index=False).agg({
            'Charge_Globale_Par_Portion': 'mean',
            'Charge_Specifique_Par_Portion': 'mean'
        }).fillna(0)
        df = df.merge(charges_prod, on='Cde_Prdt', how='left').fillna(0)
    else:
        df['Charge_Globale_Par_Portion'] = 0
        df['Charge_Specifique_Par_Portion'] = 0

    df['Charges_par_Portion'] = df['Charge_Globale_Par_Portion'] + df['Charge_Specifique_Par_Portion']
    df['Coût_Matière_Portion'] = pd.to_numeric(df.get('Coût_Matière_Portion', df.get('Coût Moyen Portion', 0)), errors='coerce').fillna(0)
    df['Marge_brute'] = df['Prix Menu'] - df['Coût_Matière_Portion']
    df['Marge_nette'] = df['Marge_brute'] - df['Charges_par_Portion']
    df['Food cost %'] = df['Coût_Matière_Portion'] / df['Prix Menu']
    df['% Charges'] = df['Charges_par_Portion'] / df['Prix Menu']

    # Seuils et alertes
    df['Seuils Tolérés'] = 0.35
    df['Alerte'] = 'OK'
    df.loc[df['Marge_nette'] < 0, 'Alerte'] = 'Non rentable'
    df.loc[df['Food cost %'] > df['Seuils Tolérés'], 'Alerte'] = 'À surveiller'

    # Scoring simple (à adapter selon tes critères)
    df['Scoring'] = (df['Marge_nette'] > 0).astype(int) + (df['Food cost %'] < 0.35).astype(int)

    return df