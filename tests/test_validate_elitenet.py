"""The validator must be runnable from a fresh clone.

Three of its checks read `data/interim/`, which is git-ignored: the block
corpus is a large intermediate rebuilt from the gazette mirror. A clone --
or CI -- therefore has the committed tables but not those inputs, and the
validator has to degrade rather than crash. It also must not report a
vacuous pass: the negative control finding "0 officer events" is meaningful
only if it actually read the blocks, so an unrunnable check is recorded as a
WARN naming the stage that would make it runnable.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIPPABLE = {"quotes verbatim", "negative control", "act citation graph"}


def _run(root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "ELITENET_ROOT": str(root), "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run([sys.executable, "-m", "elitenet.validate", "--strict"],
                          capture_output=True, text=True, env=env, cwd=ROOT)


def test_strict_validation_survives_a_missing_interim_tree(tmp_path):
    # A tree with the committed tables and config but no data/interim/,
    # which is exactly what a fresh clone and a CI checkout look like.
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "processed").symlink_to(ROOT / "data" / "processed")
    (tmp_path / "config").symlink_to(ROOT / "config")

    proc = _run(tmp_path)

    # Deliberately not asserting a zero exit. This test is about the validator
    # degrading rather than crashing when its inputs are absent; whether the
    # dataset itself passes `--strict` is a different question, gated by the
    # `multiplex dataset is self-consistent` job. Conflating them made a stale
    # committed table read as a broken test suite, which points at the wrong
    # thing.
    assert "Traceback" not in proc.stderr
    assert "# Validation report" in proc.stdout

    # Every interim-dependent check says it was skipped and how to run it,
    # and none of them reports a number it could not have computed.
    for check in SKIPPABLE:
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith(f"- **{check}**")), None)
        assert line is not None, f"{check} absent from the report"
        assert "not checked" in line, line
        assert "make mirror" in line, line

    # The skips are WARN, not buried in INFO where a reader would take the
    # report as a clean bill of health.
    warn = proc.stdout.split("## WARN", 1)[1].split("## INFO", 1)[0]
    for check in SKIPPABLE:
        assert f"- **{check}**" in warn, f"{check} was not reported at WARN level"

    # Checks that need only the committed tables must still have run.
    assert "- **spells**" in proc.stdout
    assert "- **no negative durations**" in proc.stdout


# --- the gate itself --------------------------------------------------------
# The large derived tables are committed only gzipped, so a CI checkout has
# `events.csv.gz` and no `events.csv`. `_read` used to return [] for the
# missing plain name *silently*, which meant every ERROR-level check over
# events, spells and resolution passed on an empty list: CI reported a clean
# build while `validate --strict` refused the same dataset locally. The bug
# was invisible because an empty table produces no errors, so it is pinned by
# deletion -- build the tree CI actually has and assert the numbers are real.

def _ci_shaped_tree(tmp_path: Path) -> Path:
    """A checkout carrying only what git tracks: no uncompressed twins."""
    src = ROOT / "data" / "processed"
    (tmp_path / "config").symlink_to(ROOT / "config")
    tracked = subprocess.run(["git", "ls-files", "data/processed"],
                             capture_output=True, text=True, cwd=ROOT, check=True)
    for rel in tracked.stdout.split():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        origin = ROOT / rel
        if origin.exists():
            dest.symlink_to(origin)
    assert (tmp_path / "data/processed/multiplex/events.csv.gz").exists()
    assert not (tmp_path / "data/processed/multiplex/events.csv").exists()
    return tmp_path


def _count(stdout: str, check: str) -> int:
    line = next(l for l in stdout.splitlines() if l.startswith(f"- **{check}**"))
    return int(line.split("—", 1)[1].split()[0])


def test_ci_shaped_tree_validates_real_row_counts(tmp_path):
    root = _ci_shaped_tree(tmp_path)
    proc = _run(root)

    assert "Traceback" not in proc.stderr, proc.stderr

    # These are the three tables every ERROR check depends on. A zero here is
    # the vacuous pass: the check ran, read nothing, and found nothing wrong.
    assert _count(proc.stdout, "events") > 0, (
        "events read as empty from a gzip-only tree -- the gate is vacuous")
    assert _count(proc.stdout, "spells") > 0, proc.stdout
    assert "resolution status — \n" not in proc.stdout + "\n"

    status = next(l for l in proc.stdout.splitlines()
                  if l.startswith("- **resolution status**"))
    assert "resolved=" in status, status

    # The seed-elite coverage line reported "0 (0%)" in CI for the same
    # reason, and that number is one of the dataset's headline claims.
    seed = next(l for l in proc.stdout.splitlines()
                if l.startswith("- **seed elites with a dated gazette event**"))
    assert "top 100: 0 (0%)" not in seed, seed
