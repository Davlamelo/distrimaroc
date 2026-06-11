# -*- coding: utf-8 -*-
"""Génération des données DistriMaroc — grossiste alimentaire fictif, 3 dépôts.
24 mois de ventes (2024-2025) + clients + stock, avec anomalies métier et
défauts de qualité volontaires (formats mélangés, doublons, colonnes renommées).
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)

# ---------------- Produits (35 références alimentaires) ----------------
produits = [
    # (ref, nom, catégorie, cout_unitaire MAD, prix_unitaire MAD)
    ("P001", "Huile de tournesol 5L", "Huiles", 78, 92),
    ("P002", "Huile d'olive extra vierge 1L", "Huiles", 65, 89),
    ("P003", "Farine de blé T55 25kg", "Farines", 145, 172),
    ("P004", "Farine de blé T45 10kg", "Farines", 62, 75),
    ("P005", "Sucre granulé 50kg", "Sucres", 310, 355),
    ("P006", "Sucre en morceaux 5kg", "Sucres", 38, 47),
    ("P007", "Thé vert Chunmee 41022 5kg", "Thés & Cafés", 290, 360),
    ("P008", "Thé vert gunpowder 1kg", "Thés & Cafés", 68, 88),
    ("P009", "Café moulu 1kg", "Thés & Cafés", 95, 125),
    ("P010", "Riz long grain 25kg", "Riz & Pâtes", 240, 285),
    ("P011", "Pâtes spaghetti 500g x20", "Riz & Pâtes", 72, 90),
    ("P012", "Couscous moyen 25kg", "Riz & Pâtes", 215, 255),
    ("P013", "Tomate concentrée 4.5kg x6", "Conserves", 198, 240),
    ("P014", "Sardines à l'huile x50", "Conserves", 215, 268),
    ("P015", "Thon entier à l'huile x24", "Conserves", 360, 432),
    ("P016", "Pois chiches 1kg x12", "Légumineuses", 96, 118),
    ("P017", "Lentilles vertes 1kg x12", "Légumineuses", 102, 126),
    ("P018", "Haricots blancs 1kg x12", "Légumineuses", 99, 122),
    ("P019", "Lait UHT 1L x12", "Laitiers", 76, 90),
    ("P020", "Lait en poudre 2.5kg", "Laitiers", 142, 168),
    ("P021", "Beurre 200g x40", "Laitiers", 248, 296),
    ("P022", "Fromage fondu x48", "Laitiers", 130, 158),
    ("P023", "Eau minérale 1.5L x6 (pack)", "Boissons", 21, 27),
    ("P024", "Jus d'orange 1L x12", "Boissons", 84, 105),
    ("P025", "Soda cola 1L x12", "Boissons", 78, 99),
    ("P026", "Biscuits fourrés x36", "Biscuiterie", 90, 115),
    ("P027", "Gaufrettes chocolat x48", "Biscuiterie", 105, 134),
    ("P028", "Chocolat tablette 100g x50", "Biscuiterie", 175, 220),
    ("P029", "Confiture abricot 850g x12", "Épicerie sucrée", 132, 160),
    ("P030", "Miel pur 1kg x6", "Épicerie sucrée", 270, 330),
    ("P031", "Sel de table 1kg x24", "Condiments", 36, 46),
    ("P032", "Vinaigre 1L x12", "Condiments", 42, 54),
    ("P033", "Épices ras el hanout 500g x10", "Condiments", 115, 148),
    ("P034", "Olives vertes 5kg", "Condiments", 88, 110),
    ("P035", "Dattes Deglet Nour 5kg", "Épicerie sucrée", 195, 245),
]
df_prod = pd.DataFrame(produits, columns=["ref", "nom", "categorie", "cout", "prix"])

# ---------------- Clients (200 B2B marocains) ----------------
prefixes = ["Épicerie", "Supérette", "Alimentation Générale", "Marché", "Snack",
            "Café Restaurant", "Hôtel", "Traiteur", "Boulangerie", "Pâtisserie",
            "Mini Market", "Superette", "Droguerie Alimentaire", "Libre Service"]
noms = ["Al Baraka", "Atlas", "Annakhil", "Essalam", "Al Amal", "Arrahma", "Founty",
        "Al Andalous", "Tichka", "Toubkal", "Al Wifaq", "Annour", "Bab Doukkala",
        "Al Massira", "Saada", "Al Izdihar", "Yasmine", "Al Manar", "Riad", "Medina",
        "Al Fath", "Annasr", "Bensouda", "Al Qods", "Arrazi", "Chems", "Al Hidaya",
        "Bouregreg", "Al Boustane", "Zitoune", "Annahda", "Al Firdaous", "Amal",
        "Assalam", "Al Kawtar", "Nejma", "Al Madina", "Arribat", "Tafilalet", "Souss"]
villes_depots = {
    "Casablanca": ["Casablanca", "Mohammedia", "Settat", "Berrechid", "El Jadida"],
    "Rabat": ["Rabat", "Salé", "Témara", "Kénitra", "Khémisset"],
    "Marrakech": ["Marrakech", "Safi", "Essaouira", "Benguerir", "Kelaa des Sraghna"],
}

clients = []
used = set()
cid = 1
for depot, villes in villes_depots.items():
    n_clients = {"Casablanca": 85, "Rabat": 65, "Marrakech": 50}[depot]
    for _ in range(n_clients):
        while True:
            nom_c = f"{rng.choice(prefixes)} {rng.choice(noms)}"
            ville = str(rng.choice(villes))
            if (nom_c, ville) not in used:
                used.add((nom_c, ville))
                break
        # taille du client -> poids de commande
        taille = rng.choice(["petit", "moyen", "gros"], p=[0.55, 0.33, 0.12])
        clients.append({
            "id_client": f"C{cid:03d}", "nom_client": nom_c, "ville": ville,
            "depot": depot, "taille": taille,
            "tel": f"06{rng.integers(10000000, 99999999)}",
        })
        cid += 1

# 3 très gros clients nommés (dont celui qui va décrocher)
gros_clients = [
    {"id_client": "C201", "nom_client": "Marjane Distribution Nord SARL", "ville": "Casablanca",
     "depot": "Casablanca", "taille": "tres_gros", "tel": "0522456789"},
    {"id_client": "C202", "nom_client": "Groupe Hôtelier Atlas Hospitality", "ville": "Marrakech",
     "depot": "Marrakech", "taille": "tres_gros", "tel": "0524338855"},
    {"id_client": "C203", "nom_client": "Coopérative Annajah Distribution", "ville": "Kénitra",
     "depot": "Rabat", "taille": "tres_gros", "tel": "0537221144"},
]
clients += gros_clients
df_cli = pd.DataFrame(clients)

poids_taille = {"petit": 1.0, "moyen": 2.6, "gros": 6.5, "tres_gros": 22.0}

# ---------------- Saisonnalité ----------------
# Ramadan 2024: 11 mars - 9 avril | Ramadan 2025: 1 mars - 30 mars
ramadan = [(date(2024, 3, 11), date(2024, 4, 9)), (date(2025, 3, 1), date(2025, 3, 30))]

def facteur_jour(d: date) -> float:
    f = 1.0
    for deb, fin in ramadan:
        if deb - timedelta(days=14) <= d <= deb:      # rush pré-Ramadan
            f *= 1.9
        elif deb < d <= fin:                          # pendant: élevé
            f *= 1.5
        elif fin < d <= fin + timedelta(days=10):     # Aïd puis creux
            f *= 0.7
    if d.month == 8: f *= 0.65                        # creux estival
    if d.month == 12: f *= 1.15
    if d.weekday() == 6: f *= 0.25                    # dimanche quasi fermé
    if d.weekday() == 4: f *= 1.25                    # vendredi fort
    return f

cat_ramadan = {"Épicerie sucrée": 1.8, "Huiles": 1.4, "Farines": 1.5,
               "Légumineuses": 1.5, "Thés & Cafés": 1.4, "Boissons": 1.3}

# ---------------- Génération des ventes ----------------
def gen_ventes(annee: int) -> pd.DataFrame:
    rows = []
    d = date(annee, 1, 1)
    fin = date(annee, 12, 31)
    num_cmd = 1
    while d <= fin:
        fj = facteur_jour(d)
        n_cmd = rng.poisson(26 * fj)
        # ANOMALIE 1: Marjane (C201) commande régulièrement lun/mer/ven,
        # puis décroche de ~45% à partir de sept 2025 (fréquence et volumes réduits)
        if d.weekday() in (0, 2, 4):
            decroche = d >= date(2025, 9, 1)
            if not (decroche and rng.random() < 0.40):
                c201 = df_cli[df_cli["id_client"] == "C201"].iloc[0]
                vol_factor = 0.62 if decroche else 1.0
                for _ in range(int(rng.poisson(5)) + 3):
                    p = df_prod.iloc[int(rng.integers(0, len(df_prod)))]
                    qte = max(1, int(rng.poisson(3.5 * poids_taille["tres_gros"] * vol_factor)))
                    prix = round(float(p["prix"]) * 0.95, 2)
                    cout = float(p["cout"])
                    if p["ref"] == "P001" and d >= date(2025, 3, 1):
                        cout = round(cout * 1.28, 2)
                    rows.append({
                        "num_commande": f"CMD{annee}-{num_cmd:05d}",
                        "date": d, "id_client": "C201",
                        "nom_client": c201["nom_client"], "depot": "Casablanca",
                        "ref_produit": p["ref"], "produit": p["nom"],
                        "categorie": p["categorie"], "quantite": qte,
                        "prix_unitaire": prix, "cout_unitaire": cout,
                        "montant": round(qte * prix, 2),
                    })
                num_cmd += 1
        for _ in range(n_cmd):
            c = df_cli.iloc[int(rng.integers(0, len(df_cli)))]
            if c["id_client"] == "C201":
                continue  # géré ci-dessus
            w = poids_taille[c["taille"]]
            n_lignes = max(1, int(rng.poisson(2.2 + (1.5 if w > 5 else 0))))
            for _ in range(n_lignes):
                p = df_prod.iloc[int(rng.integers(0, len(df_prod)))]
                boost = cat_ramadan.get(p["categorie"], 1.0) if any(
                    deb - timedelta(days=14) <= d <= fin_r for deb, fin_r in ramadan) else 1.0
                qte = max(1, int(rng.poisson(3.5 * w * boost)))
                prix = float(p["prix"])
                cout = float(p["cout"])
                # ANOMALIE 2: coût de l'huile tournesol +28% dès mars 2025, prix inchangé -> marge négative
                if p["ref"] == "P001" and d >= date(2025, 3, 1):
                    cout = round(cout * 1.28, 2)
                # remise volume pour les gros
                if w >= 6.5 and rng.random() < 0.6:
                    prix = round(prix * 0.95, 2)
                rows.append({
                    "num_commande": f"CMD{annee}-{num_cmd:05d}",
                    "date": d, "id_client": c["id_client"],
                    "nom_client": c["nom_client"], "depot": c["depot"],
                    "ref_produit": p["ref"], "produit": p["nom"],
                    "categorie": p["categorie"], "quantite": qte,
                    "prix_unitaire": prix, "cout_unitaire": cout,
                    "montant": round(qte * prix, 2),
                })
            num_cmd += 1
        d += timedelta(days=1)
    return pd.DataFrame(rows)

v2024 = gen_ventes(2024)
v2025 = gen_ventes(2025)

# ---------------- Injection du bordel réaliste ----------------
def casser_accents(s: str) -> str:
    return (s.replace("é", "Ã©").replace("è", "Ã¨").replace("ô", "Ã´")
             .replace("â", "Ã¢").replace("É", "Ã‰"))

def salir_ventes(df: pd.DataFrame, annee: int) -> pd.DataFrame:
    df = df.copy()
    n = len(df)
    idx = np.arange(n)

    # 1) Formats de dates mélangés (colonne -> object)
    fmt_choice = rng.random(n)
    dates_str = []
    for i, d in enumerate(df["date"]):
        if fmt_choice[i] < 0.55:
            dates_str.append(d.strftime("%d/%m/%Y"))
        elif fmt_choice[i] < 0.85:
            dates_str.append(d.strftime("%Y-%m-%d"))
        elif fmt_choice[i] < 0.95:
            dates_str.append(d.strftime("%d-%m-%y"))
        else:
            dates_str.append(d.strftime("%d/%m/%Y") + " ")   # espace traître
    df["date"] = dates_str

    # 2) Montants en texte: virgule décimale ou suffixe MAD (~8%)
    sel = rng.choice(idx, size=int(0.08 * n), replace=False)
    df["montant"] = df["montant"].astype(object)
    for i in sel[: len(sel) // 2]:
        df.iat[i, df.columns.get_loc("montant")] = str(df.iat[i, df.columns.get_loc("montant")]).replace(".", ",")
    for i in sel[len(sel) // 2:]:
        df.iat[i, df.columns.get_loc("montant")] = f"{df.iat[i, df.columns.get_loc('montant')]} MAD"

    # 3) Variantes de noms clients (~6%) : SARL déplacé, casse, espaces
    sel = rng.choice(idx, size=int(0.06 * n), replace=False)
    col = df.columns.get_loc("nom_client")
    for i in sel:
        nomc = df.iat[i, col]
        r = rng.random()
        if "SARL" in nomc and r < 0.4:
            df.iat[i, col] = "SARL " + nomc.replace(" SARL", "")
        elif r < 0.6:
            df.iat[i, col] = nomc.upper()
        elif r < 0.8:
            df.iat[i, col] = "  " + nomc + " "
        else:
            df.iat[i, col] = casser_accents(nomc)

    # 4) Quantités manquantes (~1.5%)
    sel = rng.choice(idx, size=int(0.015 * n), replace=False)
    df.loc[sel, "quantite"] = np.nan

    # 5) Doublons exacts (~0.8%)
    dups = df.sample(n=int(0.008 * n), random_state=annee)
    df = pd.concat([df, dups], ignore_index=True)

    # 6) Lignes entièrement vides dispersées
    for _ in range(12):
        pos = int(rng.integers(0, len(df)))
        empty = pd.DataFrame([{c: np.nan for c in df.columns}])
        df = pd.concat([df.iloc[:pos], empty, df.iloc[pos:]], ignore_index=True)

    return df

v2024_sale = salir_ventes(v2024, 2024)
v2025_sale = salir_ventes(v2025, 2025)

# 7) 2025: colonnes renommées + colonne en plus (export "nouveau logiciel")
v2025_sale = v2025_sale.rename(columns={
    "num_commande": "N° Commande", "date": "date_commande",
    "nom_client": "client", "montant": "montant_ttc",
    "prix_unitaire": "pu_ht", "quantite": "qte",
})
v2025_sale["mode_paiement"] = rng.choice(
    ["Espèces", "Chèque", "Virement", "Traite", ""], size=len(v2025_sale),
    p=[0.35, 0.3, 0.2, 0.1, 0.05])

# ---------------- Fichier clients (avec ses propres défauts) ----------------
df_cli_out = df_cli.drop(columns=["taille"]).copy()
# doublons quasi-identiques (8 clients dupliqués avec variantes)
dup_rows = df_cli_out.sample(n=8, random_state=7).copy()
dup_rows["id_client"] = [f"C{300+i}" for i in range(8)]
dup_rows["nom_client"] = dup_rows["nom_client"].apply(
    lambda s: ("SARL " + s.replace(" SARL", "")) if "SARL" in s else s.upper())
df_cli_out = pd.concat([df_cli_out, dup_rows], ignore_index=True)
# accents cassés sur ~10 lignes, téléphones formats variés
sel = rng.choice(len(df_cli_out), size=10, replace=False)
df_cli_out.loc[sel, "nom_client"] = df_cli_out.loc[sel, "nom_client"].apply(casser_accents)
sel = rng.choice(len(df_cli_out), size=30, replace=False)
df_cli_out.loc[sel, "tel"] = df_cli_out.loc[sel, "tel"].apply(
    lambda t: f"+212 {t[1:2]} {t[2:4]} {t[4:6]} {t[6:8]} {t[8:]}" if isinstance(t, str) else t)
# colonne email à moitié vide
emails = []
for _, r in df_cli_out.iterrows():
    if rng.random() < 0.45:
        base = r["nom_client"].lower().replace(" ", ".").replace("é", "e")[:20]
        emails.append(f"{base}@gmail.com")
    else:
        emails.append("")
df_cli_out["email"] = emails

# ---------------- Fichier stock (3 dépôts x 35 produits) ----------------
stock_rows = []
for depot in villes_depots:
    for _, p in df_prod.iterrows():
        ventes_depot_prod = v2025[(v2025["depot"] == depot) & (v2025["ref_produit"] == p["ref"])]["quantite"].sum()
        moy_mens = ventes_depot_prod / 12
        stock = int(moy_mens * rng.uniform(0.8, 2.2))
        # ANOMALIE 3: stock mort — P030 (Miel) surstocké à Marrakech, ventes quasi nulles
        if p["ref"] == "P030" and depot == "Marrakech":
            stock = 1450
        # ANOMALIE 4: rupture imminente — P007 (Thé) à Casablanca
        if p["ref"] == "P007" and depot == "Casablanca":
            stock = int(moy_mens * 0.15)
        stock_rows.append({
            "Dépôt": depot, "Référence": p["ref"], "Désignation": p["nom"],
            "Catégorie": p["categorie"], "Stock actuel (unités)": stock,
            "Coût unitaire (MAD)": p["cout"],
            "Date dernier inventaire": rng.choice(["15/12/2025", "2025-12-20", "18/12/25"]),
        })
df_stock = pd.DataFrame(stock_rows)

# ANOMALIE 3 bis: ventes de miel à Marrakech quasi nulles en 2025 (cohérence)
# (déjà faible naturellement, le surstock fait le travail)

# ---------------- Export Excel ----------------
out = "/home/claude/distrimaroc/"
import os; os.makedirs(out, exist_ok=True)

with pd.ExcelWriter(out + "ventes_2024.xlsx", engine="openpyxl") as w:
    v2024_sale.to_excel(w, sheet_name="Ventes", index=False)
with pd.ExcelWriter(out + "ventes_2025.xlsx", engine="openpyxl") as w:
    v2025_sale.to_excel(w, sheet_name="Export ventes", index=False)
with pd.ExcelWriter(out + "clients.xlsx", engine="openpyxl") as w:
    df_cli_out.to_excel(w, sheet_name="Clients", index=False)
with pd.ExcelWriter(out + "stock_depots.xlsx", engine="openpyxl") as w:
    df_stock.to_excel(w, sheet_name="Inventaire", index=False)

print("Lignes ventes 2024:", len(v2024_sale))
print("Lignes ventes 2025:", len(v2025_sale))
print("Clients:", len(df_cli_out))
print("Stock:", len(df_stock))
print("CA brut 2024 (avant salissure):", round(v2024["montant"].sum()))
print("CA brut 2025:", round(v2025["montant"].sum()))
# vérif anomalie Marjane
m = v2025[v2025["id_client"] == "C201"].copy()
m["mois"] = pd.to_datetime(m["date"]).dt.month
print("Marjane 2025 par mois:", m.groupby("mois")["montant"].sum().round(0).to_dict())
