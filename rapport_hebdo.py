# -*- coding: utf-8 -*-
"""
rapport_hebdo.py — DistriMaroc
Génère le rapport hebdomadaire PDF (2 pages) et l'envoie par email si configuré.

Usage : python rapport_hebdo.py [--output rapports/]
Email (optionnel) : variables d'environnement SMTP_HOST, SMTP_PORT, SMTP_USER,
                    SMTP_PASS, RAPPORT_DESTINATAIRE
"""
import argparse
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

TEAL = colors.HexColor("#0F766E")
ROUGE = colors.HexColor("#DC2626")
ORANGE = colors.HexColor("#D97706")
GRIS = colors.HexColor("#F1F5F4")
ENCRE = colors.HexColor("#1C2B2A")

def mad(v):
    return f"{v:,.0f} MAD".replace(",", " ")

# ----------------------------------------------------------------------
# Calculs de la semaine
# ----------------------------------------------------------------------
def calculer(ventes: pd.DataFrame, stock: pd.DataFrame) -> dict:
    date_ref = ventes["date"].max()
    # dernière semaine complète lundi -> dimanche
    fin = date_ref - pd.Timedelta(days=(date_ref.weekday() + 1) % 7 or 7)
    fin = date_ref if date_ref.weekday() == 6 else fin
    deb = fin - pd.Timedelta(days=6)
    sem = ventes[(ventes["date"] >= deb) & (ventes["date"] <= fin)]
    sem_prec = ventes[(ventes["date"] >= deb - pd.Timedelta(days=7))
                      & (ventes["date"] <= fin - pd.Timedelta(days=7))]
    sem_n1 = ventes[(ventes["date"] >= deb - pd.Timedelta(days=364))
                    & (ventes["date"] <= fin - pd.Timedelta(days=364))]

    # clients en décrochage (3 derniers mois vs 6 précédents)
    p = date_ref.to_period("M")
    recent, avant = [str(p - i) for i in range(3)], [str(p - i) for i in range(3, 9)]
    ca = ventes.groupby(["nom_client", "mois"])["montant"].sum().reset_index()
    r = ca[ca["mois"].isin(recent)].groupby("nom_client")["montant"].sum() / 3
    a = ca[ca["mois"].isin(avant)].groupby("nom_client")["montant"].sum() / 6
    comp = pd.DataFrame({"recent": r, "avant": a}).fillna(0)
    comp = comp[comp["avant"] > 20_000]
    comp["variation"] = comp["recent"] / comp["avant"] - 1
    decro = comp[comp["variation"] < -0.30].sort_values("variation")

    # produits à perte (6 mois)
    six_mois = ventes[ventes["date"] >= date_ref - pd.DateOffset(months=6)]
    marges = six_mois.groupby("produit")["marge_totale"].sum()
    pertes = marges[marges < 0].sort_values()

    # stock : couverture
    velo = (ventes[ventes["date"] >= date_ref - pd.Timedelta(days=90)]
            .groupby(["depot", "ref_produit"])["quantite"].sum() / 90)
    s = stock.set_index(["depot", "ref_produit"]).copy()
    s["couv"] = (s["stock_unites"] / velo).astype(float)
    ruptures = s[s["couv"] < 20].reset_index()
    dormant = s[(s["couv"] > 180) | s["couv"].isna()].reset_index()

    # CA 8 dernières semaines pour le graphique
    v8 = ventes[ventes["date"] > fin - pd.Timedelta(weeks=8)].copy()
    v8["semaine"] = v8["date"].dt.to_period("W").apply(lambda x: x.start_time)
    ca_sem = v8[v8["date"] <= fin].groupby("semaine")["montant"].sum()

    return dict(deb=deb, fin=fin, sem=sem, sem_prec=sem_prec, sem_n1=sem_n1,
                decro=decro, pertes=pertes, ruptures=ruptures, dormant=dormant,
                ca_sem=ca_sem)

# ----------------------------------------------------------------------
# Graphique CA hebdo (PNG temporaire intégré au PDF)
# ----------------------------------------------------------------------
def graphique_ca(ca_sem: pd.Series, chemin: Path):
    fig, ax = plt.subplots(figsize=(7.2, 2.4), dpi=150)
    barres = ax.bar([d.strftime("%d/%m") for d in ca_sem.index], ca_sem.values / 1000,
                    color="#0F766E", width=0.6)
    barres[-1].set_color("#134E4A")
    ax.set_ylabel("CA (K MAD)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Chiffre d'affaires — 8 dernières semaines", loc="left",
                 fontsize=11, fontweight="bold", color="#1C2B2A")
    fig.tight_layout()
    fig.savefig(chemin, bbox_inches="tight")
    plt.close(fig)

# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def generer_pdf(d: dict, sortie: Path) -> Path:
    deb, fin, sem = d["deb"], d["fin"], d["sem"]
    fichier = sortie / f"rapport_{fin:%Y-%m-%d}.pdf"
    doc = SimpleDocTemplate(str(fichier), pagesize=A4,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            title=f"DistriMaroc — Rapport hebdo {fin:%d/%m/%Y}")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=18, textColor=ENCRE,
                        alignment=0, spaceAfter=2)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, textColor=TEAL,
                        spaceBefore=14, spaceAfter=6)
    H2R = ParagraphStyle("H2R", parent=H2, textColor=ROUGE)
    N = ParagraphStyle("N", parent=ss["Normal"], fontSize=9.5, textColor=ENCRE)
    PETIT = ParagraphStyle("PETIT", parent=N, fontSize=8, textColor=colors.grey)

    story = [Paragraph("DistriMaroc — Rapport hebdomadaire", H1),
             Paragraph(f"Semaine du {deb:%d/%m/%Y} au {fin:%d/%m/%Y}", N),
             Spacer(1, 12)]

    # KPI
    ca, ca_p, ca_n1 = sem["montant"].sum(), d["sem_prec"]["montant"].sum(), d["sem_n1"]["montant"].sum()
    var_p = f"{(ca/ca_p-1)*100:+.1f}%" if ca_p else "—"
    var_n1 = f"{(ca/ca_n1-1)*100:+.1f}%" if ca_n1 else "—"
    marge = sem["marge_totale"].sum()
    kpi = [["CA de la semaine", "vs sem. précédente", "vs même sem. N-1",
            "Marge brute", "Commandes", "Clients servis"],
           [mad(ca), var_p, var_n1, f"{mad(marge)}\n({marge/ca*100:.1f}%)",
            f"{sem['num_commande'].nunique()}", f"{sem['id_client'].nunique()}"]]
    t = Table(kpi, colWidths=[3.4 * cm] * 6)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5), ("FONTSIZE", (0, 1), (-1, 1), 9.5),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [GRIS]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 14)]

    # graphique
    png = sortie / "_ca_hebdo.png"
    graphique_ca(d["ca_sem"], png)
    story += [Image(str(png), width=17.2 * cm, height=5.7 * cm), Spacer(1, 8)]

    # top clients / produits de la semaine
    def mini_table(serie, titre):
        rows = [[titre, "CA"]] + [[k[:42], mad(v)] for k, v in serie.items()]
        t = Table(rows, colWidths=[6.2 * cm, 2.4 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, TEAL),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t
    top_c = sem.groupby("nom_client")["montant"].sum().nlargest(5)
    top_p = sem.groupby("produit")["montant"].sum().nlargest(5)
    duo = Table([[mini_table(top_c, "Top 5 clients de la semaine"),
                  mini_table(top_p, "Top 5 produits de la semaine")]],
                colWidths=[8.9 * cm, 8.9 * cm])
    duo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [duo, PageBreak()]

    # ---------------- Page 2 : alertes ----------------
    n_alertes = len(d["decro"]) + len(d["pertes"]) + len(d["ruptures"]) + len(d["dormant"])
    story += [Paragraph(f"Alertes — {n_alertes} points d'action", H1), Spacer(1, 6)]

    if len(d["decro"]):
        story.append(Paragraph("Clients en décrochage (−30% et plus sur 3 mois)", H2R))
        rows = [["Client", "CA mensuel avant", "CA mensuel récent", "Variation"]]
        for nom, r in d["decro"].iterrows():
            rows.append([nom[:40], mad(r["avant"]), mad(r["recent"]),
                         f"{r['variation']*100:+.0f}%"])
        t = Table(rows, colWidths=[7.2 * cm, 3.6 * cm, 3.6 * cm, 2.4 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, ROUGE),
            ("TEXTCOLOR", (3, 1), (3, -1), ROUGE),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ]))
        story += [t, Paragraph("→ Action : appel commercial sous 48h pour les 3 premiers.", N),
                  Spacer(1, 6)]

    if len(d["pertes"]):
        story.append(Paragraph("Produits vendus à perte (cumul 6 mois)", H2R))
        for prod, v in d["pertes"].items():
            story.append(Paragraph(f"• <b>{prod}</b> : <font color='#DC2626'><b>{mad(v)}</b></font> "
                                   "de marge négative", N))
        story += [Paragraph("→ Action : revoir le prix de vente ou renégocier le coût d'achat.", N),
                  Spacer(1, 6)]

    if len(d["ruptures"]):
        story.append(Paragraph("Ruptures imminentes (moins de 20 jours de stock)", H2R))
        rows = [["Dépôt", "Produit", "Stock", "Couverture"]]
        for _, r in d["ruptures"].iterrows():
            rows.append([r["depot"], r["produit"][:38], int(r["stock_unites"]),
                         f"{r['couv']:.0f} j"])
        t = Table(rows, colWidths=[3 * cm, 8.2 * cm, 2.4 * cm, 2.6 * cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, ROUGE),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ]))
        story += [t, Paragraph("→ Action : commande fournisseur immédiate.", N), Spacer(1, 6)]

    if len(d["dormant"]):
        story.append(Paragraph("Stock dormant (plus de 6 mois de couverture)", H2))
        for _, r in d["dormant"].iterrows():
            couv = "aucune vente" if pd.isna(r["couv"]) else f"{r['couv']:.0f} jours de couverture"
            story.append(Paragraph(
                f"• <b>{r['produit']}</b> ({r['depot']}) : {int(r['stock_unites'])} unités, "
                f"{couv} — <b>{mad(r['valeur_stock'])} immobilisés</b>", N))
        story.append(Paragraph("→ Action : promotion de déstockage ou transfert inter-dépôts.", N))

    story += [Spacer(1, 18),
              Paragraph("Rapport généré automatiquement. Démonstration sur données simulées — "
                        "T. Ulrich David, Data Science & IA.", PETIT)]
    doc.build(story)
    png.unlink(missing_ok=True)
    return fichier

# ----------------------------------------------------------------------
# Email (optionnel — ne bloque jamais la génération)
# ----------------------------------------------------------------------
def envoyer(fichier: Path, fin) -> bool:
    hote = os.getenv("SMTP_HOST")
    dest = os.getenv("RAPPORT_DESTINATAIRE")
    if not (hote and dest):
        print("Email non configuré (SMTP_HOST / RAPPORT_DESTINATAIRE absents) — envoi ignoré.")
        return False
    msg = EmailMessage()
    msg["Subject"] = f"DistriMaroc — Rapport hebdomadaire au {fin:%d/%m/%Y}"
    msg["From"] = os.getenv("SMTP_USER")
    msg["To"] = dest
    msg.set_content("Bonjour,\n\nVeuillez trouver ci-joint le rapport hebdomadaire.\n\n"
                    "Ce message est généré automatiquement.")
    msg.add_attachment(fichier.read_bytes(), maintype="application", subtype="pdf",
                       filename=fichier.name)
    with smtplib.SMTP(hote, int(os.getenv("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        s.send_message(msg)
    print(f"Rapport envoyé à {dest}.")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/clean")
    ap.add_argument("--output", default="rapports")
    args = ap.parse_args()
    sortie = Path(args.output)
    sortie.mkdir(parents=True, exist_ok=True)

    ventes = pd.read_parquet(Path(args.data) / "ventes.parquet")
    stock = pd.read_parquet(Path(args.data) / "stock.parquet")
    ventes["date"] = pd.to_datetime(ventes["date"])

    d = calculer(ventes, stock)
    fichier = generer_pdf(d, sortie)
    print(f"Rapport généré : {fichier}")
    envoyer(fichier, d["fin"])

if __name__ == "__main__":
    main()
