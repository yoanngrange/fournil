"""Pipeline settings: frozen vintages, source URLs and scoring constants.

Change a vintage here and nowhere else. Every source listed in SOURCES ends up in public/data/meta.json.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "pipeline" / "raw"
OUT = ROOT / "public" / "data"

# Public address of the site (canonical URLs, sitemap).
SITE_URL = "https://yoanngrange.github.io/fournil/"

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
    "bodacc": {
        "name": "BODACC — ventes de fonds de boulangerie",
        "producer": "DILA",
        "vintage": "annonces depuis 2008",
        "url": (
            "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/"
            "exports/json?where=familleavis%3D%27vente%27%20and%20search(listeetablissements%2C%20%22boulangerie%22)"
            "&select=dateparution%2Ctypeavis%2Cnumerodepartement%2Ccp%2Clisteetablissements%2Cacte"
        ),
        "suffix": ".json",
        "licence": "Licence Ouverte 2.0",
        "page": "https://bodacc-datadila.opendatasoft.com/explore/dataset/annonces-commerciales/",
    },
    "sirene_ul": {
        "name": "Base Sirene des unités légales (noms des entreprises)",
        "producer": "Insee",
        "vintage": "stock mensuel",
        "datagouv": {
            "dataset": "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret",
            "title_startswith": "Sirene : Fichier StockUniteLegale -",
            "format": "parquet",
        },
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret",
    },
    "elus_maires": {
        "name": "Répertoire national des élus — maires",
        "producer": "Ministère de l'Intérieur",
        "vintage": "2026",
        "datagouv": {"dataset": "repertoire-national-des-elus-1", "title_startswith": "elus-maires", "format": "csv"},
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1",
    },
    "municipales_t1": {
        "name": "Élections municipales 2026 — résultats du 1er tour par commune",
        "producer": "Ministère de l'Intérieur",
        "vintage": "15 mars 2026",
        "datagouv": {
            "dataset": "elections-municipales-2026-resultats-du-premier-tour",
            "title_startswith": "Municipales 2026 - Résultats - Communes",
            "format": "csv",
        },
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/elections-municipales-2026-resultats-du-premier-tour",
    },
    "municipales_t2": {
        "name": "Élections municipales 2026 — résultats du 2nd tour par commune",
        "producer": "Ministère de l'Intérieur",
        "vintage": "22 mars 2026",
        "datagouv": {
            "dataset": "elections-municipales-2026-resultats-du-second-tour",
            "title_startswith": "Municipales 2026 - Résultats - Communes",
            "format": "csv",
        },
        "licence": "Licence Ouverte 2.0",
        "page": "https://www.data.gouv.fr/datasets/elections-municipales-2026-resultats-du-second-tour",
    },
    "wikidata": {
        "name": "Wikidata — photo (Wikimedia Commons) et article Wikipédia des communes",
        "producer": "Wikimedia",
        "vintage": "mensuel",
        "url": "https://query.wikidata.org/sparql",
        "custom": "wikidata",
        "licence": "CC0 (données) ; photos sous leur propre licence, créditées sur la page",
        "page": "https://www.wikidata.org/",
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

# --- Bakery history (SIRENE): openings, closures and takeovers of 10.71C establishments ---
HISTORY_FROM = "2016-01-01"
TAKEOVER_WINDOW_DAYS = 180  # a closure and an opening by another company this close = a takeover

# --- Price of a bakery business (BODACC sale notices) ---
FONDS_YEARS = 5  # sales published in the last N years
FONDS_MIN_SALES = 20  # below this, no département figure is shown (national only)
FONDS_PRICE_RANGE = (5_000, 3_000_000)  # outside: bundled sales or typing errors

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
NO_BAKERY_BOOST = 3  # a commune without a bakery ranks as if it had this × its population per bakery…
NO_BAKERY_BOOST_FROM = 500  # …but not below this population (ranked as if it had one bakery: too small to sustain one)
NO_BAKERY_BOOST_FULL = 1000  # full boost from this population, linear in between
CRITERIA = ["per_bakery", "income", "growth", "crime", "sell_soon"]
LOWER_IS_BETTER = {"crime"}

# Overseas départements are out of the MVP (codes 971-976 have three-digit département codes).
def in_scope(dep_code: str) -> bool:
    return len(dep_code) == 2
