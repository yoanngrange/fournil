"""Pipeline settings: frozen vintages, source URLs and scoring constants.

Change a vintage here and nowhere else. Every source listed in SOURCES ends up in public/data/meta.json.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "pipeline" / "raw"
OUT = ROOT / "public" / "data"

# One COG (Code officiel géographique) vintage per run. Every commune is keyed on its code in this vintage.
COG_YEAR = 2026

MELODI = "https://api.insee.fr/melodi/file"
IGN = (
    "https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS-COG-CARTO/"
    "ADMIN-EXPRESS-COG-CARTO_4-0__GEOPARQUET_WGS84G_FRA_2026-01-01"
)

# id -> source description. `url` is fixed; `datagouv` resolves the latest matching resource of a
# data.gouv.fr dataset at fetch time (for sources republished monthly under a new URL).
SOURCES = {
    "cog": {
        "name": "Code officiel géographique — communes",
        "producer": "Insee",
        "vintage": "2026",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8740222/v_commune_2026.csv",
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.insee.fr/fr/information/8740218",
    },
    "cog_mvt": {
        "name": "Code officiel géographique — événements sur les communes",
        "producer": "Insee",
        "vintage": "2026",
        "url": "https://www.insee.fr/fr/statistiques/fichier/8740222/v_mvt_commune_2026.csv",
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.insee.fr/fr/information/8740218",
    },
    "admin_express_communes": {
        "name": "ADMIN EXPRESS COG CARTO — communes",
        "producer": "IGN",
        "vintage": "2026",
        "url": f"{IGN}/commune.parquet",
        "licence": "Licence Ouverte 2.0",
        "page": "https://geoservices.ign.fr/adminexpress",
    },
    "admin_express_chefs_lieux": {
        "name": "ADMIN EXPRESS COG CARTO — chefs-lieux de commune",
        "producer": "IGN",
        "vintage": "2026",
        "url": f"{IGN}/chef_lieu_de_commune.parquet",
        "licence": "Licence Ouverte 2.0",
        "page": "https://geoservices.ign.fr/adminexpress",
    },
    "admin_express_departements": {
        "name": "ADMIN EXPRESS COG CARTO — départements",
        "producer": "IGN",
        "vintage": "2026",
        "url": f"{IGN}/departement.parquet",
        "licence": "Licence Ouverte 2.0",
        "page": "https://geoservices.ign.fr/adminexpress",
    },
    "populations": {
        "name": "Populations de référence (populations légales)",
        "producer": "Insee",
        "vintage": "2023 (en vigueur au 1er janvier 2026)",
        "url": f"{MELODI}/DS_POPULATIONS_REFERENCE/DS_POPULATIONS_REFERENCE_2023_CSV_FR",
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/populations-de-reference",
    },
    "rp_history": {
        "name": "Recensement — série historique 1968-2023",
        "producer": "Insee",
        "vintage": "RP 2023",
        "url": f"{MELODI}/DS_RP_SERIE_HISTORIQUE/DS_RP_SERIE_HISTORIQUE_2023_CSV_FR",
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/serie-historique-du-recensement-de-la-population",
    },
    "rp_age_sex": {
        "name": "Recensement — population par sexe et âge",
        "producer": "Insee",
        "vintage": "RP 2023",
        "url": f"{MELODI}/DS_RP_POPULATION_PRINC/DS_RP_POPULATION_PRINC_2023_CSV_FR",
        "licence": "Licence Ouverte 2.0",
        "page": "https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_POPULATION_PRINC",
    },
    "filosofi": {
        "name": "Filosofi — niveau de vie et pauvreté",
        "producer": "Insee",
        "vintage": "2023",
        "url": f"{MELODI}/DS_FILOSOFI_CC/DS_FILOSOFI_CC_2023_CSV_FR",
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/niveau-de-vie-taux-de-pauvrete-decomposition-du-revenu-disponible-en-2023",
    },
    "bpe": {
        "name": "Base permanente des équipements (BPE)",
        "producer": "Insee",
        "vintage": "2025",
        "url": f"{MELODI}/DS_BPE/DS_BPE_2025_CSV_FR",
        "licence": "Licence Ouverte 2.0",
        "page": "https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_BPE",
    },
    "ssmsi": {
        "name": "Délinquance enregistrée par la police et la gendarmerie — base communale",
        "producer": "Ministère de l'Intérieur (SSMSI)",
        "vintage": "2025",
        "datagouv": {
            "dataset": "bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales",
            "title_startswith": "COM - Base statistique communale",
            "format": "parquet",
        },
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales",
    },
    "sirene": {
        "name": "Base Sirene des établissements",
        "producer": "Insee",
        "vintage": "stock mensuel",
        "datagouv": {
            "dataset": "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret",
            "title_startswith": "Sirene : Fichier StockEtablissement -",
            "format": "parquet",
        },
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret",
    },
}

# --- Bakeries and amenities (BPE 2025 nomenclature; codes changed since the 2020 list in DATA.md) ---
BPE_BAKERY = "B207"  # Boulangerie-pâtisserie
BPE_CODES = {
    "supermarkets": ["B104", "B105"],  # hypermarché, supermarché
    "small_grocers": ["B201", "B202"],  # supérette, épicerie
    "butchers": ["B204"],
    "fishmongers": ["B206"],
    "restaurants": ["A504"],
    "pharmacies": ["D307"],
    "doctors": ["D265"],  # médecin généraliste
    "primary_schools": ["C107", "C108", "C109"],
    "secondary_schools": ["C201", "C301", "C302", "C303"],
    "post": ["A206", "A207", "A208"],
    "stations": ["E107", "E108", "E109"],
}

# --- SIRENE (cross-check and local economy only; BPE is the bakery count used for scoring) ---
NAF_BAKERY = "10.71C"
NAF_PASTRY = "10.71D"  # BPE "boulangerie-pâtisserie" is compared with SIRENE 10.71C + 10.71D
NAF_BREAD_RETAIL = "47.24Z"
NAF_CAFES = "56.30Z"

# --- Crime (SSMSI): sum of these indicators per 1,000 inhabitants ---
# SSMSI publishes 0 and counts ≥ 5, and withholds counts of 1 to 4. A withheld indicator is counted
# as the midpoint (2.5); the commune's value is dropped when the resulting uncertainty
# (3 offences per withheld indicator, per 1,000 inhabitants) exceeds CRIME_MAX_UNCERTAINTY.
CRIME_YEAR = 2025
CRIME_WITHHELD = (1, 4)
CRIME_MAX_UNCERTAINTY = 5.0
CRIME_INDICATORS = [
    "Cambriolages de logement",
    "Violences physiques hors cadre familial",
    "Vols avec armes",
    "Vols violents sans arme",
    "Vols sans violence contre des personnes",
]

# --- Scoring (docs/SPEC.md §4) ---
GROWTH_FROM, GROWTH_TO = 2017, 2023  # census years compared for the yearly growth rate
NO_BAKERY_BOOST = 1.5  # communes without a bakery are ranked on per_bakery × this factor
CRITERIA = ["per_bakery", "income", "growth", "crime", "sell_soon"]
LOWER_IS_BETTER = {"crime"}

# Overseas départements are out of the MVP (codes 971-976 have three-digit département codes).
def in_scope(dep_code: str) -> bool:
    return len(dep_code) == 2
