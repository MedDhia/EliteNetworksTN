import logging, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eltn.pipeline import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
root = Path(__file__).resolve().parents[1]
t0 = time.time()
stats = run(
    root / "data" / "raw" / "catalog_journal-officiel_fr.json",
    root / "data" / "raw" / "jort",
    root / "data" / "interim" / "events_raw.csv",
    workers=int(sys.argv[1]) if len(sys.argv) > 1 else 8,
)
logging.info("DONE %s in %.1fs", stats, time.time() - t0)
