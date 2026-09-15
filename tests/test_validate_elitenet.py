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


# --- a stale stage is not a broken dataset ------------------------------- #

def test_a_resolution_table_predating_the_snowball_is_a_stale_stage(tmp_path, monkeypatch):
    """The mistake this pins is one this pipeline has now made twice: reading
    an absent thing as a broken thing. A resolution.csv built before the tier
    existed has no resolve_pass column and no snowballed links, which is a
    stage that has not re-run -- and failing CI on it says "broken dataset"
    where the truth is "stale stage"."""
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    # _skip_stage renders the path relative to ROOT, so both must move.
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,person_mention,org_mention,resolved_person_id,link_status\n"
        "a||b,A Ben Ali,Societe B,P_A,resolved\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 0
    assert any(lv == "WARN" and "snowball passes" in c for lv, c, _d in rep.rows)


def test_snowballed_links_with_no_pass_column_stay_an_error(tmp_path, monkeypatch):
    """The genuine defect the check was written for: links that cannot be told
    apart from first-pass ones."""
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    # _skip_stage renders the path relative to ROOT, so both must move.
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,person_mention,org_mention,resolved_person_id,link_status\n"
        "a||b,A Ben Ali,Societe B,P_A,snowball\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 1
    assert any("snowball passes are recorded" in c for _lv, c, _d in rep.rows)


def test_snowball_reports_its_passes_when_the_column_is_there(tmp_path, monkeypatch):
    """The fixture has to be internally coherent, which the first version of
    it was not: it paired `person_names_org` -- a rule that names an
    ORGANISATION -- with link_status=snowball and no resolved_org_id, and the
    three-part invariant rightly rejected it. The rules split two ways and a
    row must satisfy whichever it claims."""
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    # _skip_stage renders the path relative to ROOT, so both must move.
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,link_status,resolve_pass,snowball_basis,resolved_org_id\n"
        "a||b,resolved,0,,CO_1\n"
        # A person-naming rule: link_status must be snowball.
        "c||d,snowball,1,org_names_person,CO_1\n"
        "e||f,snowball,2,colleagues_name_person,\n"
        # An organisation-naming rule: the organisation must be named, and the
        # person may legitimately stay unresolved.
        "g||h,unresolved,1,identifier_names_org,CO_2\n"
        "i||j,ambiguous,2,person_names_org,CO_3\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 0
    detail = next(d for _lv, c, d in rep.rows if c == "snowball links")
    assert "2 of 5" in detail and "pass 1=1" in detail and "pass 2=1" in detail


def test_an_organisation_rule_must_leave_an_organisation_named(tmp_path, monkeypatch):
    """The branch that caught the stale fixture. A row claiming its pass was
    earned by naming a firm, with no firm named, is mislabelled."""
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,link_status,resolve_pass,snowball_basis,resolved_org_id\n"
        "a||b,unresolved,1,identifier_names_org,\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 1
    assert any("leaves an organisation named" in c for _lv, c, _d in rep.rows)


def test_an_organisation_naming_pass_need_not_name_a_person(tmp_path, monkeypatch):
    """The 878 rows the first version of the check wrongly failed on. Rules 0
    and 1 name a FIRM on a row whose person is still unresolved, and that is
    the intended behaviour, not a labelling error."""
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,link_status,resolve_pass,snowball_basis,resolved_org_id\n"
        "a||b,unresolved,1,identifier_names_org,CO_1\n"
        "c||d,ambiguous,2,person_names_org,CO_2\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 0


def test_an_unlabelled_snowball_row_is_an_error(tmp_path, monkeypatch):
    from elitenet import validate as V
    monkeypatch.setattr(V, "PROCESSED", tmp_path)
    # _skip_stage renders the path relative to ROOT, so both must move.
    monkeypatch.setattr(V, "ROOT", tmp_path)
    (tmp_path / "resolution.csv").write_text(
        "mention_key,link_status,resolve_pass,snowball_basis\n"
        "a||b,snowball,0,\n", encoding="utf-8")
    rep = V.Report()
    V.check_snowball(rep)
    assert rep.errors == 1
    assert any("names its pass and rule" in c for _lv, c, _d in rep.rows)
