# -*- coding: utf-8 -*-
"""
app.py — Dashboard de pilotage DistriMaroc
Lancement : streamlit run app.py
Prérequis : python pipeline.py (génère data/clean/*.parquet)
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import subprocess
from pathlib import Path
import sys

st.set_page_config(page_title="DistriMaroc — Pilotage", page_icon="📦",
                   layout="wide", initial_sidebar_state="expanded")

ACCENT = "#0F766E"      # teal profond
ALERTE = "#DC2626"      # rouge alerte
OK = "#16A34A"
PALETTE_DEPOTS = {"Casablanca": "#0F766E", "Rabat": "#D97706", "Marrakech": "#7C3AED"}

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stTabs [data-baseweb="tab"] { font-size: 1.05rem; }
    div[data-testid="stMetricDelta"] svg { display: inline; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Chargement
# ----------------------------------------------------------------------
@st.cache_data
def charger():
    base = Path("data/clean")
    ventes = pd.read_parquet(base / "ventes.parquet")
    clients = pd.read_parquet(base / "clients.parquet")
    stock = pd.read_parquet(base / "stock.parquet")
    ventes["date"] = pd.to_datetime(ventes["date"])
    return ventes, clients, stock



if not Path("data/clean/ventes.parquet").exists():
    with st.spinner("Préparation des données en cours..."):
        subprocess.run([sys.executable, "pipeline.py"], check=True)

try:
    ventes, clients, stock = charger()
except Exception as e:
    st.error(f"Erreur au chargement : {e}")
    st.stop()

date_ref = ventes["date"].max()

def fmt_mad(v, court=True):
    if court and abs(v) >= 1_000_000:
        return f"{v/1_000_000:,.1f} M MAD".replace(",", " ")
    if court and abs(v) >= 10_000:
        return f"{v/1_000:,.0f} K MAD".replace(",", " ")
    return f"{v:,.0f} MAD".replace(",", " ")

# ----------------------------------------------------------------------
# Sidebar : filtres
# ----------------------------------------------------------------------
with st.sidebar:
    st.title("  DistriMaroc")
    depots = st.multiselect("Dépôts", sorted(ventes["depot"].unique()),
                            default=sorted(ventes["depot"].unique()))
    periode = st.select_slider(
        "Période", options=sorted(ventes["mois"].unique()),
        value=(sorted(ventes["mois"].unique())[0], sorted(ventes["mois"].unique())[-1]))
    st.divider()
    st.caption("\n\n"
               "Réalisé par **T. Ulrich David** — Data Science & IA")

df = ventes[(ventes["depot"].isin(depots))
            & (ventes["mois"] >= periode[0]) & (ventes["mois"] <= periode[1])]
if df.empty:
    st.warning("Aucune donnée pour ces filtres.")
    st.stop()

# ----------------------------------------------------------------------
# Calculs d'alertes (le cœur de la valeur)
# ----------------------------------------------------------------------
@st.cache_data
def clients_en_decrochage(ventes: pd.DataFrame, date_ref) -> pd.DataFrame:
    """Compare le CA mensuel moyen des 3 derniers mois aux 6 mois précédents."""
    fin_recent = date_ref.to_period("M")
    recent = [str(fin_recent - i) for i in range(3)]
    avant = [str(fin_recent - i) for i in range(3, 9)]
    ca = ventes.groupby(["id_client", "nom_client", "mois"])["montant"].sum().reset_index()
    ca_recent = ca[ca["mois"].isin(recent)].groupby(["id_client", "nom_client"])["montant"].sum() / 3
    ca_avant = ca[ca["mois"].isin(avant)].groupby(["id_client", "nom_client"])["montant"].sum() / 6
    comp = pd.DataFrame({"ca_mensuel_recent": ca_recent, "ca_mensuel_avant": ca_avant}).fillna(0)
    comp = comp[comp["ca_mensuel_avant"] > 20_000]          # clients significatifs
    comp["variation"] = (comp["ca_mensuel_recent"] / comp["ca_mensuel_avant"] - 1)
    comp["manque_a_gagner_mensuel"] = comp["ca_mensuel_avant"] - comp["ca_mensuel_recent"]
    return (comp[comp["variation"] < -0.30]
            .sort_values("manque_a_gagner_mensuel", ascending=False).reset_index())

@st.cache_data
def produits_marge_negative(ventes: pd.DataFrame, date_ref) -> pd.DataFrame:
    """Produits vendus à perte sur les 6 derniers mois."""
    debut = date_ref - pd.DateOffset(months=6)
    v = ventes[ventes["date"] >= debut]
    g = v.groupby(["ref_produit", "produit"]).agg(
        marge_totale=("marge_totale", "sum"), ca=("montant", "sum"),
        lignes=("montant", "size")).reset_index()
    return g[g["marge_totale"] < 0].sort_values("marge_totale")

@st.cache_data
def alertes_stock(ventes: pd.DataFrame, stock: pd.DataFrame, date_ref) -> pd.DataFrame:
    """Couverture de stock en jours = stock / vélocité de vente (90 derniers jours)."""
    debut = date_ref - pd.Timedelta(days=90)
    velo = (ventes[ventes["date"] >= debut]
            .groupby(["depot", "ref_produit"])["quantite"].sum() / 90)
    s = stock.set_index(["depot", "ref_produit"]).copy()
    s["ventes_jour"] = velo
    s["ventes_jour"] = s["ventes_jour"].fillna(0)
    s["couverture_jours"] = (s["stock_unites"] / s["ventes_jour"].replace(0, pd.NA)).astype(float)
    s["statut"] = "OK"
    s.loc[s["couverture_jours"] < 20, "statut"] = "🔴 Rupture imminente"
    s.loc[(s["couverture_jours"] > 180) | s["couverture_jours"].isna(), "statut"] = "🟠 Stock dormant"
    return s.reset_index()

decro = clients_en_decrochage(ventes[ventes["depot"].isin(depots)], date_ref)
pertes = produits_marge_negative(ventes[ventes["depot"].isin(depots)], date_ref)
stk = alertes_stock(ventes, stock[stock["depot"].isin(depots)], date_ref)
alertes_stk = stk[stk["statut"] != "OK"]

# ----------------------------------------------------------------------
# En-tête : KPI + bandeau d'alertes
# ----------------------------------------------------------------------
st.title("Tableau de bord de pilotage")

mois_courant = df["mois"].max()
mois_prec = str(pd.Period(mois_courant) - 1)
ca_courant = df[df["mois"] == mois_courant]["montant"].sum()
ca_prec = df[df["mois"] == mois_prec]["montant"].sum()
delta = (ca_courant / ca_prec - 1) * 100 if ca_prec else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("CA période", fmt_mad(df["montant"].sum()))
c2.metric(f"CA {mois_courant}", fmt_mad(ca_courant), f"{delta:+.1f}% vs mois préc.")
c3.metric("Marge brute", fmt_mad(df["marge_totale"].sum()),
          f"{df['marge_totale'].sum()/df['montant'].sum()*100:.1f}% du CA")
c4.metric("Commandes", f"{df['num_commande'].nunique():,}".replace(",", " "))
c5.metric("Clients actifs", df["id_client"].nunique())

n_alertes = len(decro) + len(pertes) + len(alertes_stk)
if n_alertes:
    st.error(f"**{n_alertes} alertes nécessitent une action** : "
             f"{len(decro)} client(s) en décrochage · {len(pertes)} produit(s) vendu(s) à perte · "
             f"{len(alertes_stk)} alerte(s) stock")

# ----------------------------------------------------------------------
# Onglets
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([" Activité", "Clients", " Marges produits", "Stock"])

with tab1:
    ca_mois = df.groupby(["mois", "depot"])["montant"].sum().reset_index()
    fig = px.bar(ca_mois, x="mois", y="montant", color="depot",
                 color_discrete_map=PALETTE_DEPOTS,
                 labels={"montant": "CA (MAD)", "mois": "", "depot": "Dépôt"},
                 title="Chiffre d'affaires mensuel par dépôt")
    fig.update_layout(legend=dict(orientation="h", y=1.12), bargap=0.25)
    st.plotly_chart(fig, width="stretch")

    g, d = st.columns(2)
    with g:
        cat = df.groupby("categorie")["montant"].sum().sort_values()
        fig = px.bar(cat, orientation="h", labels={"value": "CA (MAD)", "categorie": ""},
                     title="CA par catégorie", color_discrete_sequence=[ACCENT])
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with d:
        top_p = df.groupby("produit")["montant"].sum().nlargest(10).sort_values()
        fig = px.bar(top_p, orientation="h", labels={"value": "CA (MAD)", "produit": ""},
                     title="Top 10 produits", color_discrete_sequence=[ACCENT])
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")

with tab2:
    if len(decro):
        st.subheader("🔴 Clients en décrochage (−30% et plus)")
        st.caption("CA mensuel moyen des 3 derniers mois comparé aux 6 mois précédents.")
        aff = decro.copy()
        aff["CA avant"] = aff["ca_mensuel_avant"].map(fmt_mad)
        aff["CA récent"] = aff["ca_mensuel_recent"].map(fmt_mad)
        aff["Variation"] = (aff["variation"] * 100).map("{:+.0f}%".format)
        aff["Manque à gagner / mois"] = aff["manque_a_gagner_mensuel"].map(fmt_mad)
        st.dataframe(aff[["nom_client", "CA avant", "CA récent", "Variation",
                          "Manque à gagner / mois"]],
                     width="stretch", hide_index=True)

        choix = st.selectbox("Voir l'historique d'un client en alerte",
                             decro["nom_client"].tolist())
        hist = (ventes[ventes["nom_client"] == choix]
                .groupby("mois")["montant"].sum().reset_index())
        fig = go.Figure(go.Scatter(x=hist["mois"], y=hist["montant"], mode="lines+markers",
                                   line=dict(color=ALERTE, width=2.5)))
        fig.update_layout(title=f"CA mensuel — {choix}",
                          yaxis_title="CA (MAD)", xaxis_title="")
        st.plotly_chart(fig, width="stretch")
    else:
        st.success("Aucun client en décrochage sur la période.")

    st.subheader("Top 10 clients")
    top_c = (df.groupby("nom_client")["montant"].sum().nlargest(10).sort_values())
    fig = px.bar(top_c, orientation="h", labels={"value": "CA (MAD)", "nom_client": ""},
                 color_discrete_sequence=[ACCENT])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")
    part_top10 = top_c.sum() / df["montant"].sum() * 100
    st.caption(f"Les 10 premiers clients représentent **{part_top10:.0f}% du CA** — "
               "concentration à surveiller.")

with tab3:
    if len(pertes):
        st.subheader("🔴 Produits vendus à perte (6 derniers mois)")
        aff = pertes.copy()
        aff["Perte cumulée"] = aff["marge_totale"].map(fmt_mad)
        aff["CA concerné"] = aff["ca"].map(fmt_mad)
        st.dataframe(aff[["produit", "Perte cumulée", "CA concerné", "lignes"]]
                     .rename(columns={"lignes": "Nb ventes"}),
                     width="stretch", hide_index=True)
        p_ref = pertes.iloc[0]["ref_produit"]
        evo = (ventes[ventes["ref_produit"] == p_ref]
               .groupby("mois")[["marge_totale"]].sum().reset_index())
        fig = px.bar(evo, x="mois", y="marge_totale",
                     color=(evo["marge_totale"] < 0).map({True: "Perte", False: "Marge"}),
                     color_discrete_map={"Perte": ALERTE, "Marge": OK},
                     labels={"marge_totale": "Marge (MAD)", "mois": "", "color": ""},
                     title=f"Marge mensuelle — {pertes.iloc[0]['produit']}")
        st.plotly_chart(fig, width="stretch")
        st.info("💡 Cause typique : hausse du coût d'achat non répercutée sur le prix de vente.")
    else:
        st.success("Aucun produit vendu à perte sur les 6 derniers mois.")

    marge_cat = (df.groupby("categorie")
                 .apply(lambda g: g["marge_totale"].sum() / g["montant"].sum() * 100,
                        include_groups=False)
                 .sort_values())
    fig = px.bar(marge_cat, orientation="h",
                 labels={"value": "Taux de marge (%)", "categorie": ""},
                 title="Taux de marge par catégorie", color_discrete_sequence=[ACCENT])
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")

with tab4:
    valeur_totale = stk["valeur_stock"].sum()
    valeur_morte = stk[stk["statut"] == "🟠 Stock dormant"]["valeur_stock"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Valeur du stock", fmt_mad(valeur_totale))
    c2.metric("Capital immobilisé (stock dormant)", fmt_mad(valeur_morte),
              f"{valeur_morte/valeur_totale*100:.0f}% du stock", delta_color="inverse")
    c3.metric("Références en alerte", len(alertes_stk))

    if len(alertes_stk):
        st.subheader("Alertes stock")
        aff = alertes_stk.copy()
        aff["Couverture"] = aff["couverture_jours"].map(
            lambda x: "∞ (aucune vente)" if pd.isna(x) else f"{x:.0f} j")
        aff["Valeur"] = aff["valeur_stock"].map(fmt_mad)
        st.dataframe(aff[["statut", "depot", "produit", "stock_unites", "Couverture", "Valeur"]]
                     .rename(columns={"statut": "Statut", "depot": "Dépôt",
                                      "produit": "Produit", "stock_unites": "Unités"}),
                     width="stretch", hide_index=True)

    st.subheader("Couverture de stock par référence")
    s_ok = stk.dropna(subset=["couverture_jours"]).copy()
    # Plafonner à 400j pour l'affichage (valeurs infinies = stock sans ventes récentes)
    MAX_COUV = 400
    s_ok["couverture_aff"] = s_ok["couverture_jours"].clip(upper=MAX_COUV)
    s_ok["label_couv"] = s_ok["couverture_jours"].apply(
        lambda x: f"{x:.0f} j" if x < MAX_COUV else f">{MAX_COUV} j (stock dormant)")
    fig = px.scatter(s_ok, x="couverture_aff", y="valeur_stock", color="depot",
                     hover_name="produit", hover_data={"label_couv": True,
                     "couverture_aff": False, "valeur_stock": True},
                     color_discrete_map=PALETTE_DEPOTS,
                     labels={"couverture_aff": "Couverture (jours)",
                             "valeur_stock": "Valeur du stock (MAD)", "depot": "Dépôt"})
    fig.add_vline(x=20, line_dash="dash", line_color=ALERTE,
                  annotation_text="seuil rupture")
    fig.add_vline(x=180, line_dash="dash", line_color="#D97706",
                  annotation_text="seuil stock dormant (6 mois)")
    fig.update_xaxes(range=[0, MAX_COUV + 10])
    st.plotly_chart(fig, width="stretch")