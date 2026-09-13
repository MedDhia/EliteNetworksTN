"""Whether a surname predicts how high in the state its holders get.

The companion to fig33. That one asked *where* officials go and found that
they cluster with their namesakes. This asks *how high* they rise, which is a
different question and gets a different answer: barely at all in the career
bureaucracy, and sharply at the political apex.

**The design.** For each rank threshold, the statistic is the chance that two
people sharing a surname *both* reached it. The null shuffles the outcome —
who reached the rank — within strata of entry decade × career span, which
leaves every surname group exactly as it is and destroys only the link between
name and attainment. Those two controls are not optional: the high-rank rate
runs from 5% for someone recorded in a single year to 44% for someone with a
career spanning twenty-one or more, and from 21% for the 1980s cohort to 7%
for the 2020s, so an unstratified null would credit families with the effects
of longevity and of when the record happens to stop.

**Why the outcome and not the surname is shuffled.** Shuffling surnames also
works for the headline — it gives 1.06×, 1.40×, 1.82× against the 1.06×,
1.38×, 1.86× here — but it breaks as soon as the sample is split by how common
a surname is, because the split is defined on a person's real surname while
the permutation hands them somebody else's. The group sizes inside the subset
then differ between observation and null and the ratio stops meaning anything.
Shuffling the outcome is immune to that, so it is what both panels use.

**What a rejected design looked like.** The first attempt asked whether a
person whose namesake had *already* reached high rank was more likely to get
there themselves — the transmission question, and the more interesting one.
It cannot be answered this way. Having a precedent is almost the same fact as
entering late: people with one enter in 2007 on average and people without in
1985, because a precedent is by construction someone who came first. Within
the rarest surnames only 168 people of 15,001 have a precedent at all.
Stratifying does not repair a confound that the conditioning itself creates,
and the resulting estimates were non-monotone in a way that should not be
drawn.

**No ranking of surnames**, here as in ``scripts/surnames.py``, and the reason
binds harder on this figure than on fig33: a named list of families that reach
ministerial rank is an accusation, and at the top of the scale it would rest
on 54 surnames and 114 pairs measured through a proxy that cannot tell two
families apart when they share a common name.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from surnames import (  # noqa: E402
    BANDS, rarity_band, shared_outcome_fast, split_name, usable,
)
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

MAIN = CAT4[1]

SEED = 20260913
N_PERM = 400

# The ordinal rank scale, by the lowest score that clears each threshold.
THRESHOLDS = [
    (45, "Sous-directeur\nand above"),
    (55, "Directeur\nand above"),
    (65, "Directeur général\nand above"),
    (70, "Secrétaire général\nand above"),
    (80, "Gouverneur\nand above"),
    (90, "Ministre\nand above"),
]

# The threshold the right panel splits by rarity. High enough that the effect
# is unambiguous, low enough that four of the five bands still hold pairs.
BAND_THRESHOLD = 80

SPAN_BINS = [-1, 0, 2, 5, 10, 20, 100]
SPAN_LABELS = ["0", "1-2", "3-5", "6-10", "11-20", "21+"]


def prepare(persons: pd.DataFrame) -> pd.DataFrame:
    p = persons.copy()
    p["name"] = p.name.fillna("")
    p["surname"] = [split_name(n)[1] for n in p.name]
    p = p[[usable(s) for s in p.surname]].copy()
    p["span"] = p.last_year - p.first_year
    p["spanband"] = pd.cut(p.span, SPAN_BINS, labels=SPAN_LABELS)
    p = p.dropna(subset=["spanband"]).copy()
    # Entry decade and career span together: the two things that move rank
    # without any family in the story.
    p["stratum"] = ((p.first_year // 10 * 10).astype(int).astype(str) + "|"
                    + p.spanband.astype(str))
    freq = Counter(p.surname)
    p["band"] = [rarity_band(freq[s]) for s in p.surname]
    return p


def _strata(p: pd.DataFrame) -> list[np.ndarray]:
    s = p.stratum.values
    return [np.where(s == u)[0] for u in np.unique(s)]


def test(p: pd.DataFrame, outcome: np.ndarray, strata, rng,
         mask: np.ndarray | None = None, n_perm: int = N_PERM) -> dict | None:
    names = p.surname.values
    codes, uniq = pd.factorize(names)
    n_codes = len(uniq)
    sel = slice(None) if mask is None else mask
    obs = shared_outcome_fast(codes[sel], outcome[sel], n_codes)
    if np.isnan(obs):
        return None
    draws = []
    for _ in range(n_perm):
        sh = outcome.copy()
        for g in strata:
            sh[g] = rng.permutation(outcome[g])
        v = shared_outcome_fast(codes[sel], sh[sel], n_codes)
        if not np.isnan(v):
            draws.append(v)
    nl = np.array(draws)
    if nl.std() == 0:
        return None
    # Conventional 5%, not "no draw reached it". With 400 draws the stricter
    # rule is p < 0.0025, which left gouverneur-and-above open at z = 3.2 —
    # an open marker there reads as "no effect", which is not what a one-in-
    # two-hundred result means.
    p_value = (1 + (nl >= obs).sum()) / (len(nl) + 1)
    return {"obs": obs, "null": float(nl.mean()), "sd": float(nl.std()),
            "ratio": obs / nl.mean() if nl.mean() else float("nan"),
            "z": (obs - nl.mean()) / nl.std(), "p": float(p_value),
            "clears": bool(p_value < 0.05),
            "n": int(len(names[sel]))}


def by_threshold(p: pd.DataFrame, strata, rng) -> list[dict]:
    out = []
    for score, label in THRESHOLDS:
        outcome = (p.peak_rank_score >= score).values
        r = test(p, outcome, strata, rng)
        if r is None:
            continue
        r |= {"score": score, "label": label, "base": outcome.mean() * 100,
              "reached": int(outcome.sum())}
        out.append(r)
    return out


def by_rarity(p: pd.DataFrame, strata, rng) -> list[dict]:
    outcome = (p.peak_rank_score >= BAND_THRESHOLD).values
    out = []
    for band in BANDS:
        mask = (p.band == band).values
        r = test(p, outcome, strata, rng, mask=mask, n_perm=200)
        # A band with no two people sharing a surname who both reached the
        # rank is kept and drawn as such: it is a real reading, not a gap.
        out.append({"band": band, "n": int(mask.sum()),
                    "empty": r is None or r["obs"] == 0,
                    **({} if r is None else r)})
    return out


def draw_left(ax, rows) -> None:
    y = np.arange(len(rows))[::-1]
    for i, r in zip(y, rows):
        ax.plot([1.0, r["ratio"]], [i, i], color=RULE, lw=1.8, zorder=2,
                solid_capstyle="round")
        if r["clears"]:
            ax.plot([r["ratio"]], [i], "o", ms=9, color=MAIN, zorder=4)
        else:
            ax.plot([r["ratio"]], [i], "o", ms=9, mfc="white", mec=MAIN,
                    mew=1.6, zorder=4)
        ax.annotate(f"{r['ratio']:.2f}×", xy=(r["ratio"], i), xytext=(12, 0),
                    textcoords="offset points", va="center", ha="left",
                    fontsize=8.6, fontweight="bold",
                    color=INK if r["clears"] else MUTED)
    ax.axvline(1.0, color=INK, lw=1.0, zorder=3)
    ax.annotate("chance", xy=(1.0, 1.0), xycoords=("data", "axes fraction"),
                xytext=(3, -2), textcoords="offset points", ha="left",
                va="top", fontsize=7.2, color=INK, style="italic")
    ax.set_yticks(y)
    # The base counts ride in the tick label. As a separate annotation inside
    # the axes they were wide enough in data units to run back under the rank
    # names and collide with them.
    ax.set_yticklabels([f"{r['label']}\n{r['reached']:,} reached it · "
                        f"{r['base']:.1f}%" for r in rows],
                       fontsize=8.2, color=INK, linespacing=1.45)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlim(0.62, 2.35)
    ax.set_xticks([0.75, 1.0, 1.25, 1.5, 1.75, 2.0])
    ax.set_xlabel("shared-fate rate ÷ rate under the permutation", fontsize=8.2)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("How high the rank", fontsize=9.8)


def draw_right(ax, rows) -> None:
    ax.set_xscale("log")
    y = np.arange(len(rows))[::-1]
    for i, r in zip(y, rows):
        if r["empty"]:
            ax.annotate("no two people sharing a surname\nthis rare both reached it",
                        xy=(1.6, i), va="center", ha="left", fontsize=7.2,
                        color=MUTED, style="italic", linespacing=1.5)
            continue
        # Per 10,000, matching the axis. Plotted raw, these sit around 9e-4 and
        # fall off the left of the scale entirely.
        obs, null = r["obs"] * 1e4, r["null"] * 1e4
        ax.plot([null, obs], [i, i], color=RULE, lw=2.4, zorder=2,
                solid_capstyle="round")
        ax.plot([null], [i], "o", ms=7, mfc="white", mec=MUTED, mew=1.5,
                zorder=4)
        ax.plot([obs], [i], "o", ms=8, color=MAIN, zorder=5)
        ax.annotate(f"{r['ratio']:.2f}×", xy=(obs, i), xytext=(11, 0),
                    textcoords="offset points", va="center", ha="left",
                    fontsize=8.6, fontweight="bold",
                    color=INK if r["clears"] else MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['band']}\n{r['n']:,} people" for r in rows],
                       fontsize=8.2, color=INK, linespacing=1.5)
    ax.set_ylabel("people in the register carrying that surname", fontsize=8.2)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(1.1, 60)
    ax.set_xticks([2, 5, 10, 20])
    ax.set_xticklabels(["2", "5", "10", "20"])
    ax.minorticks_off()
    ax.set_xlabel("pairs sharing a surname who both reached it (per 10,000)",
                  fontsize=8.2)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"At gouverneur and above, by how rare the name is",
                 fontsize=9.8)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", ms=8, color=MAIN, label="observed"),
        Line2D([], [], marker="o", ls="", ms=7, mfc="white", mec=MUTED,
               mew=1.5, label="outcome shuffled within decade × career span"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)


def fig_rank(persons: pd.DataFrame) -> None:
    rng = np.random.default_rng(SEED)
    p = prepare(persons)
    strata = _strata(p)
    left = by_threshold(p, strata, rng)
    right = by_rarity(p, strata, rng)

    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.6),
                             gridspec_kw={"width_ratios": [1.05, 1.0]})
    fig.subplots_adjust(top=0.70, bottom=0.175, left=0.155, right=0.965,
                        wspace=0.46)
    draw_left(axes[0], left)
    draw_right(axes[1], right)

    lo, hi = left[0], left[-1]
    drawn = [r for r in right if not r["empty"]]
    rare, common = drawn[0], drawn[-1]
    headline(
        fig,
        "A surname says little about becoming a director and a good deal about becoming a minister",
        f"Left: how much more often two people sharing a surname both reach a "
        f"rank than when the outcome is shuffled among people of the same "
        f"entry decade and career span. The effect climbs the scale — "
        f"{lo['ratio']:.2f}× at {lo['label'].replace(chr(10), ' ').lower()}, "
        f"where {lo['base']:.0f}% of the register arrives, and "
        f"{hi['ratio']:.2f}× at {hi['label'].replace(chr(10), ' ').lower()}, "
        f"where {hi['base']:.1f}% does. Right: the same statistic at "
        f"gouverneur and above, split by how many people carry the surname. It "
        f"runs from {rare['ratio']:.2f}× for a name held by "
        f"{rare['band'].replace('-', ' to ')} people down to "
        f"{common['ratio']:.2f}× for one held by more than sixty — the "
        f"direction kinship predicts, since a rare name shared is evidence of "
        f"a family and a common one shared is mostly not.",
        width=148,
    )
    save(fig, "fig34_surname_rank",
         SOURCE + "  Rank is the highest position a person is recorded "
                  "holding, on the ordinal scale the codebook sets out. The "
                  "null shuffles who reached the rank within strata of entry "
                  "decade and career span, leaving surname groups untouched; "
                  "both controls are needed, because the rate of reaching "
                  "directeur général and above runs from 5% for someone "
                  "recorded in a single year to 44% for someone whose career "
                  "spans twenty-one or more, and from 21% for the 1980s cohort "
                  "to 7% for the 2020s. Shuffling surnames instead gives the "
                  "same headline (1.06×, 1.40×, 1.82× against 1.06×, 1.38×, "
                  "1.86×) but cannot be split by rarity, because the split is "
                  "defined on a person's own surname while the permutation "
                  "gives them another. A filled marker means fewer than 5% of "
                  "permutations reached the observed value. The top of the "
                  "scale is "
                  "thin and the reader should hold it lightly: at ministre and "
                  "above, 459 people carry 381 distinct surnames, of which 54 "
                  "are held by two or more, giving 114 pairs; the largest such "
                  "group is six people. The surname proxy has the same two "
                  "defects fig33 sets out — 77% of people recorded under "
                  "several spellings disagree with themselves, and the "
                  "commonest surnames here are the commonest in Tunisia — and "
                  "both push these ratios towards chance, so they are floors. "
                  "A transmission design, asking whether a person whose "
                  "namesake had already reached high rank was likelier to get "
                  "there, is not drawn: having such a precedent is nearly the "
                  "same fact as entering late (2007 on average against 1985 "
                  "for those without), so the comparison is confounded by "
                  "construction rather than by anything stratification can "
                  "remove. No ranking of surnames is computed anywhere in this "
                  "build.")


def main() -> None:
    print("loading tables…")
    persons = pd.read_csv(PROC / "persons.csv.gz", low_memory=False)
    print("drawing…")
    fig_rank(persons)
    print("done")


if __name__ == "__main__":
    main()
