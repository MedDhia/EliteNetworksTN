import logging, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eltn.harvest import build_catalog, download_corpus, save_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
root = Path(__file__).resolve().parents[1]
cat_path = root / "data" / "raw" / "catalog_journal-officiel_fr.json"
t0 = time.time()
issues = build_catalog()
save_catalog(issues, cat_path)
logging.info("catalog: %s issues, %.1fs", len(issues), time.time() - t0)
stats = download_corpus(issues, root / "data" / "raw" / "jort", workers=16)
logging.info("DONE %s in %.1fs", stats, time.time() - t0)
