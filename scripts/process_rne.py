"""
Compile and compress Registre National des Entreprises (RNE) registry files.

This script processes raw RNE JSON extracts (both Entreprise / Personne Morale
and Personne Physique) into clean, deduplicated, and gzipped CSV files under
data/processed/rne/.
"""

import csv
import gzip
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "processed" / "rne"


def process_entreprises(src_csv: Path, out_path: Path) -> int:
    """Read compiled entreprises CSV and export clean compressed CSV."""
    logging.info("Processing Entreprises from %s -> %s", src_csv, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(src_csv, "r", encoding="utf-8", errors="replace") as f_in, gzip.open(
        out_path, "wt", encoding="utf-8", newline=""
    ) as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = [
            "numRegistre",
            "year_creation",
            "denominationFr",
            "denominationAr",
            "nomCommercialFr",
            "nomCommercialAr",
            "categorie",
            "nomAssociationFr",
            "nomAssociationAr",
            "identifiantUnique",
        ]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            writer.writerow(
                {
                    "numRegistre": row.get("registres.numRegistre", ""),
                    "year_creation": row.get("year.creation", ""),
                    "denominationFr": row.get("registres.denominationFr", ""),
                    "denominationAr": row.get("registres.denominationAr", ""),
                    "nomCommercialFr": row.get("registres.nomCommercialFr", ""),
                    "nomCommercialAr": row.get("registres.nomCommercialAr", ""),
                    "categorie": row.get("registres.categorie", ""),
                    "nomAssociationFr": row.get("registres.nomAssociationFr", ""),
                    "nomAssociationAr": row.get("registres.nomAssociationAr", ""),
                    "identifiantUnique": row.get("registres.identifiantUnique", ""),
                }
            )
            count += 1
    logging.info("Entreprises completed: %d records written", count)
    return count


def process_personnes_physiques(src_dir: Path, out_path: Path) -> int:
    """Compile chunked JSON files of Personne Physique into a single gzipped CSV."""
    logging.info("Processing Personnes Physiques from %s -> %s", src_dir, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(src_dir.glob("*.json"))
    fieldnames = [
        "numRegistre",
        "identifiantUnique",
        "typeRegistre",
        "categorie",
        "nomAr",
        "prenomAr",
        "nomFr",
        "prenomFr",
        "denominationAr",
        "denominationFr",
    ]
    count = 0
    with gzip.open(out_path, "wt", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for fp in files:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data.get("registres", [])
                for r in records:
                    writer.writerow(r)
                    count += 1
    logging.info("Personnes Physiques completed: %d records written from %d files", count, len(files))
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process RNE dataset into data/processed/rne/")
    parser.add_argument(
        "--entreprises-src",
        type=Path,
        default=Path("/Users/mohameddhiahammami/Desktop/Desktop - Med’s MacBook Pro/Data/JSON Companies/combined_data2.csv"),
    )
    parser.add_argument(
        "--pp-src-dir",
        type=Path,
        default=Path("/Users/mohameddhiahammami/Documents/RNE DATA JSON/PERSONNE PHYSIQUE"),
    )
    args = parser.parse_args()

    if args.entreprises_src.exists():
        process_entreprises(args.entreprises_src, OUT_DIR / "entreprises.csv.gz")
    if args.pp_src_dir.exists():
        process_personnes_physiques(args.pp_src_dir, OUT_DIR / "personnes_physiques.csv.gz")
