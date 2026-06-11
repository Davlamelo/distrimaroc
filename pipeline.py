# -*- coding: utf-8 -*-
"""
pipeline.py — DistriMaroc
Ingestion et nettoyage des exports Excel bruts -> base de données propre.

Entrées : ventes_2024.xlsx, ventes_2025.xlsx, clients.xlsx, stock_depots.xlsx
Sorties : data/clean/ventes.parquet, clients.parquet, stock.parquet,
          distrimaroc.db (SQLite) + rapport qualité (console et data/clean/rapport_qualite.txt)

Usage : python pipeline.py [--input data/raw] [--output data/clean]
"""
import argparse
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Rapport qualité : on compte chaque problème corrigé (matière pour l'étude de cas)
# ----------------------------------------------------------------------
rapport = {}

def log(cle: str, n: int):
    if n:
        rapport[cle] = rapport.get(cle, 0) + int(n)

# ----------------------------------------------------------------------
# Utilitaires de nettoyage
# ----------------------------------------------------------------------
def corriger_mojibake(s):
    """Répare l'encodage cassé UTF-8 lu en latin-1 (ex: 'HÃ´tel' -> 'Hôtel')."""
    if not isinstance(s, str) or "Ã" not in s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def parser_date(v):
    """Gère les formats mélangés : dd/mm/yyyy, yyyy-mm-dd, dd-mm-yy, espaces parasites."""
    if pd.isna(v):
        return pd.NaT
    if isinstance(v, pd.Timestamp):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except ValueError:
            continue
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def parser_montant(v):
    """Convertit '1275,0' ou '828.0 MAD' ou 1275.0 -> float."""
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("MAD", "").strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return np.nan

def normaliser_nom(s):
    """Nettoie un nom client : espaces, casse, encodage, position du 'SARL'."""
    if not isinstance(s, str):
        return s
    s = corriger_mojibake(s)
    s = re.sub(r"\s+", " ", s).strip()
    # uniformiser SARL en suffixe
    if s.upper().startswith("SARL "):
        s = s[5:].strip() + " SARL"
    # restaurer une casse propre si tout en majuscules
    if s.isupper():
        s = s.title().replace("Sarl", "SARL")
    return s

def normaliser_tel(t):
    """'+212 6 12 34 56 78' et '0612345678' -> format unique 06XXXXXXXX."""
    if not isinstance(t, str):
        return t
    chiffres = re.sub(r"\D", "", t)
    if chiffres.startswith("212"):
        chiffres = "0" + chiffres[3:]
    return chiffres

# ----------------------------------------------------------------------
# 1. Ventes : harmonisation des deux exports + nettoyage
# ----------------------------------------------------------------------
COLONNES_CIBLE = {
    "N° Commande": "num_commande", "date_commande": "date", "client": "nom_client",
    "qte": "quantite", "pu_ht": "prix_unitaire", "montant_ttc": "montant",
}

def charger_ventes(chemin: Path) -> pd.DataFrame:
    df = pd.read_excel(chemin)
    renommees = {c: COLONNES_CIBLE[c] for c in df.columns if c in COLONNES_CIBLE}
    log("colonnes_harmonisees", len(renommees))
    df = df.rename(columns=renommees)
    df["fichier_source"] = chemin.name
    return df

def nettoyer_ventes(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)

    # lignes entièrement vides
    vides = df.drop(columns=["fichier_source"]).isna().all(axis=1)
    df = df[~vides].copy()
    log("lignes_vides_supprimees", vides.sum())

    # doublons exacts
    dups = df.duplicated(subset=[c for c in df.columns if c != "fichier_source"])
    df = df[~dups].copy()
    log("doublons_exacts_supprimes", dups.sum())

    # dates
    avant = df["date"].apply(lambda x: isinstance(x, str)).sum()
    df["date"] = df["date"].apply(parser_date)
    log("dates_normalisees", avant)
    invalides = df["date"].isna()
    df = df[~invalides].copy()
    log("dates_invalides_supprimees", invalides.sum())

    # montants en texte
    en_texte = df["montant"].apply(lambda x: isinstance(x, str)).sum()
    df["montant"] = df["montant"].apply(parser_montant)
    log("montants_texte_convertis", en_texte)

    # noms clients
    modifs = (df["nom_client"] != df["nom_client"].apply(normaliser_nom)).sum()
    df["nom_client"] = df["nom_client"].apply(normaliser_nom)
    log("noms_clients_normalises", modifs)
    # source de vérité : l'id_client (stable) -> nom canonique = le plus fréquent par id
    canon = df.groupby("id_client")["nom_client"].agg(lambda s: s.mode().iat[0])
    df["nom_client"] = df["id_client"].map(canon)

    # quantités manquantes : ré-imputées depuis montant / prix unitaire
    manquantes = df["quantite"].isna()
    imputables = manquantes & df["montant"].notna() & (df["prix_unitaire"] > 0)
    df.loc[imputables, "quantite"] = (df.loc[imputables, "montant"]
                                      / df.loc[imputables, "prix_unitaire"]).round()
    log("quantites_imputees", imputables.sum())
    restantes = df["quantite"].isna()
    df = df[~restantes].copy()
    log("quantites_irrecuperables_supprimees", restantes.sum())

    # cohérence montant = quantite * prix (recalcul systématique = source de vérité)
    incoherents = (df["montant"] - df["quantite"] * df["prix_unitaire"]).abs() > 0.05
    log("montants_recalcules", incoherents.sum())
    df["montant"] = (df["quantite"] * df["prix_unitaire"]).round(2)

    # colonnes dérivées pour le dashboard
    df["marge_unitaire"] = df["prix_unitaire"] - df["cout_unitaire"]
    df["marge_totale"] = (df["marge_unitaire"] * df["quantite"]).round(2)
    df["annee"] = df["date"].dt.year
    df["mois"] = df["date"].dt.to_period("M").astype(str)

    df["quantite"] = df["quantite"].astype(int)
    rapport["lignes_ventes_finales"] = len(df)
    return df

# ----------------------------------------------------------------------
# 2. Clients : normalisation + dédoublonnage flou
# ----------------------------------------------------------------------
def nettoyer_clients(chemin: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_excel(chemin)
    df["nom_client"] = df["nom_client"].apply(normaliser_nom)
    df["tel"] = df["tel"].apply(normaliser_tel)
    df["email"] = df["email"].replace("", np.nan)

    # dédoublonnage : même (nom normalisé, ville) -> on garde le plus petit id
    cle = df["nom_client"].str.lower().str.replace(" sarl", "", regex=False) + "|" + df["ville"].str.lower()
    df["_cle"] = cle
    df = df.sort_values("id_client")
    doublons = df.duplicated(subset="_cle", keep="first")
    # table de correspondance id_doublon -> id_canonique (pour réaffecter les ventes)
    mapping = {}
    for _, grp in df[df["_cle"].isin(df.loc[doublons, "_cle"])].groupby("_cle"):
        ids = grp["id_client"].tolist()
        for i in ids[1:]:
            mapping[i] = ids[0]
    log("clients_doublons_fusionnes", doublons.sum())
    df = df[~doublons].drop(columns="_cle").reset_index(drop=True)
    return df, mapping

# ----------------------------------------------------------------------
# 3. Stock : dates d'inventaire mélangées
# ----------------------------------------------------------------------
def nettoyer_stock(chemin: Path) -> pd.DataFrame:
    df = pd.read_excel(chemin)
    df.columns = ["depot", "ref_produit", "produit", "categorie",
                  "stock_unites", "cout_unitaire", "date_inventaire"]
    avant = df["date_inventaire"].apply(lambda x: isinstance(x, str)).sum()
    df["date_inventaire"] = df["date_inventaire"].apply(parser_date)
    log("dates_inventaire_normalisees", avant)
    df["valeur_stock"] = (df["stock_unites"] * df["cout_unitaire"]).round(2)
    return df

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/raw")
    ap.add_argument("--output", default="data/clean")
    args = ap.parse_args()
    src, out = Path(args.input), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print("=== Pipeline DistriMaroc ===")
    ventes = pd.concat(
        [charger_ventes(src / "ventes_2024.xlsx"), charger_ventes(src / "ventes_2025.xlsx")],
        ignore_index=True,
    )
    rapport["lignes_ventes_brutes"] = len(ventes)
    ventes = nettoyer_ventes(ventes)
    clients, mapping = nettoyer_clients(src / "clients.xlsx")
    stock = nettoyer_stock(src / "stock_depots.xlsx")

    # réaffecter les ventes des clients doublons vers l'id canonique
    n_reaffectees = ventes["id_client"].isin(mapping).sum()
    ventes["id_client"] = ventes["id_client"].replace(mapping)
    log("ventes_reaffectees_apres_fusion", n_reaffectees)

    # exports
    ventes.to_parquet(out / "ventes.parquet", index=False)
    clients.to_parquet(out / "clients.parquet", index=False)
    stock.to_parquet(out / "stock.parquet", index=False)
    with sqlite3.connect(out / "distrimaroc.db") as con:
        ventes.to_sql("ventes", con, if_exists="replace", index=False)
        clients.to_sql("clients", con, if_exists="replace", index=False)
        stock.to_sql("stock", con, if_exists="replace", index=False)

    # rapport qualité
    lignes = ["", "=== Rapport qualité des données ==="]
    for k, v in sorted(rapport.items()):
        lignes.append(f"  {k:<42} {v:>8,}".replace(",", " "))
    texte = "\n".join(lignes)
    print(texte)
    (out / "rapport_qualite.txt").write_text(texte, encoding="utf-8")
    print(f"\nSorties écrites dans {out.resolve()}")

if __name__ == "__main__":
    main()
