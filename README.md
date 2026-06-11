# DistriMaroc — Pilotage automatisé pour PME de distribution

> Étude de cas : transformer 4 exports Excel bruts en un système de pilotage complet —
> pipeline de nettoyage, dashboard interactif et rapport PDF hebdomadaire automatique.
> 
> 🔗 **[Démo live du dashboard](https://distrimaroc.streamlit.app)**
> 
> 🌐 **[Présentation du projet](https://davlamelo.github.io/distrimaroc)**
## Le problème

Un grossiste alimentaire (3 dépôts, 200+ clients B2B, ~50M MAD de CA annuel) pilote son
activité avec des exports Excel hétérogènes : formats de dates incohérents, colonnes
renommées d’un logiciel à l’autre, doublons, encodage cassé. Conséquences : ~8h de
consolidation manuelle par semaine, et des signaux critiques invisibles.

*Données simulées reproduisant fidèlement les défauts rencontrés en entreprise
(`generate_distrimaroc.py`, seed fixe).*

## Ce que le système a détecté

|Signal                                                                        |Impact                               |
|------------------------------------------------------------------------------|-------------------------------------|
|1er client du portefeuille en décrochage de **−63%**                          |~755 K MAD de manque à gagner mensuel|
|Produit vendu **à perte** depuis 10 mois (coût fournisseur +28% non répercuté)|−34 K MAD sur 6 mois                 |
|Rupture imminente sur un best-seller (6 jours de stock)                       |CA à risque sur la catégorie n°1     |
|Stock dormant (203 jours de couverture)                                       |391 K MAD immobilisés                |

## Architecture

```
data/raw/*.xlsx ──> pipeline.py ──> data/clean/ (Parquet + SQLite)
                                      ├──> app.py (dashboard Streamlit)
                                      └──> rapport_hebdo.py (PDF + email)
                                             ▲
                            GitHub Actions (cron lundi 07h00)
```

- **`pipeline.py`** — ingestion et nettoyage : harmonisation de schémas, parsing de dates
  multi-formats, réparation d’encodage (mojibake), dédoublonnage flou des clients,
  imputation des quantités, rapport qualité automatique (12 types de problèmes traités
  sur 48 320 lignes).
- **`app.py`** — dashboard Streamlit : KPI, CA par dépôt/catégorie, détection automatique
  des clients en décrochage, marges par produit, couverture de stock avec seuils métier.
- **`rapport_hebdo.py`** — rapport PDF de 2 pages (synthèse + alertes actionnables),
  envoyé par email chaque lundi via GitHub Actions. Aucun serveur nécessaire.

## Lancer en local

```bash
pip install -r requirements.txt
python generate_distrimaroc.py          # génère les données brutes dans data/raw/
python pipeline.py                      # nettoie vers data/clean/
streamlit run app.py                    # dashboard sur http://localhost:8501
python rapport_hebdo.py                 # PDF dans rapports/
```

Envoi email (optionnel) : définir `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`,
`RAPPORT_DESTINATAIRE` (en local ou dans les secrets GitHub Actions).

## Stack

Python · pandas · Streamlit · Plotly · ReportLab · SQLite/Parquet · GitHub Actions

-----

**Tassembedo Ulrich David** — Data Science & IA · [GitHub](https://github.com/Davlamelo) · [Portfolio](https://davlamelo.github.io/distrimaroc)
