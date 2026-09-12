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

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr

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
