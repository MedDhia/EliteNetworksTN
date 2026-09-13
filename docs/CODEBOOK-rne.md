# Registre National des Entreprises (RNE) — Codebook

This dataset compiles registry entries from the Tunisian **Registre National des Entreprises (RNE)** (formerly *Registre du Commerce*), covering legal entities and registered sole proprietors / natural persons.

---

## 1. Scope & Coverage

| Table | File | Rows | Compressed Size | Description |
|---|---|---|---|---|
| **Entreprises** | `data/processed/rne/entreprises.csv.gz` | **393,788** | ~12.4 MB | Legal entities (sociétés, SARL, SUARL, SA, associations, public institutions) |
| **Personnes Physiques** | `data/processed/rne/personnes_physiques.csv.gz` | **615,659** | ~12.3 MB | Natural persons registered as sole proprietors, merchants (commerçants), craftspeople |
| **Total** | | **1,009,447** | **~24.7 MB** | Complete consolidated business register |

All files are stored as UTF-8 encoded, compressed `csv.gz` tables readable directly with `pandas.read_csv(...)` or `readr::read_csv(...)`.

---

## 2. Variables

### `entreprises.csv.gz` (Personnes Morales)

| Column | Type | Description |
|---|---|---|
| `numRegistre` | String | Official commercial register / RNE number (e.g., `ج0173692008`, `B1103912001`) |
| `year_creation` | Integer | Estimated year of registration extracted from `numRegistre` |
| `denominationFr` | String | Legal company name in French |
| `denominationAr` | String | Legal company name in Arabic |
| `nomCommercialFr` | String | Trade name in French |
| `nomCommercialAr` | String | Trade name in Arabic |
| `categorie` | String | Legal entity type (`SOCIETE`, `ASSOCIATION`, `ENTREPRISE_PUBLIQUE`, etc.) |
| `nomAssociationFr` | String | Association name in French (where applicable) |
| `nomAssociationAr` | String | Association name in Arabic (where applicable) |
| `identifiantUnique` | String | Unique Tax/Business ID (*Matricule Fiscal* / *Identifiant Unique RNE*) |

### `personnes_physiques.csv.gz` (Natural Persons)

| Column | Type | Description |
|---|---|---|
| `numRegistre` | String | Commercial register number |
| `identifiantUnique` | String | Unique ID (*Identifiant Unique*) |
| `typeRegistre` | String | Register type indicator (`P` for Personne Physique) |
| `categorie` | String | Activity category (`COMMERCANT`, `ARTISAN`, `PROFESSION_LIBERALE`, etc.) |
| `nomAr` | String | Surname in Arabic |
| `prenomAr` | String | Given name in Arabic |
| `nomFr` | String | Surname in French |
| `prenomFr` | String | Given name in French |
| `denominationAr` | String | Business denomination in Arabic |
| `denominationFr` | String | Business denomination in French |

---

## 3. Linkage with other EliteNetworksTN layers

- **`identifiantUnique` & `numRegistre`**: Direct cross-referencing keys with the Bourse multiplex (`data/processed/bourse/`) and the JORT legal announcements series (*annonces légales*).
- **Names (`nomAr`, `prenomAr`, `denominationAr`)**: Can be joined with `data/processed/persons.csv.gz` and `data/processed/organisations.csv.gz` for cross-sector elite career and business interlock analysis.
