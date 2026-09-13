"""Whether officials sharing a surname end up in the same place.

Two questions, one on each panel, and the second is what makes the first
readable.

**Left — is a ministry's staff more surname-concentrated than chance?** The
comparison is a permutation: every person keeps their ministries and is dealt
somebody else's surname, so ministry sizes and the surname frequency
distribution survive intact and only the association between family name and
ministry is destroyed. Shuffling happens *within entry decade*, because
transliteration conventions moved over seventy years and a ministry whose
record sits mostly in the 1960s would otherwise look concentrated for a reason
that has nothing to do with families.

**Right — does a namesake already inside predict arrival, and does it depend on
how rare the name is?** This is the panel that carries the interpretation. The
main rival explanation for anything on the left panel is regional recruitment:
Tunisian surnames are regionally patterned, so a body that hires locally
concentrates surnames with no family tie anywhere in it. The two explanations
make opposite predictions about rarity. A shared *rare* surname is good
evidence of kinship and poor evidence of region; a shared *common* one is the
reverse. If the excess is largest for the rarest names and decays toward the
commonest, family is doing work that region cannot explain away.

**What is deliberately absent.** No ranking of surnames, here or anywhere in
this build. See the note in ``scripts/surnames.py``: on the commonest names —
precisely the ones that would head such a list — the instrument is at its
weakest, and publishing it would read as an accusation the data cannot support
against named living families. The structural result needs no list.

Two defects in the proxy are load-bearing and stated on the figure rather than
buried: 77% of people recorded under several spellings disagree with
themselves about their own surname, which hides real kin behind different
spellings; and the commonest surnames in the table are the commonest surnames
in the country, which puts strangers under one name. The first biases the
measured effect *down*, the second biases it *down* as well — unrelated people
sharing a name add to the null as readily as to the observation, which is why
the rarity gradient rather than the overall level is the result worth having.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apparatus import ministry_of, MINISTRY_ENGLISH  # noqa: E402
from surnames import (  # noqa: E402
    BANDS, namesake_hits, rarity_band, same_surname_probability, split_name,
    usable,
)
from figstyle import (  # noqa: E402
    CAT4, INK, MUTED, PROC, RULE, SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402

MAIN = CAT4[1]
EXCEPT = CAT4[0]

SEED = 20260913
N_PERM_MINISTRY = 200
# The namesake scan walks all ~99,000 spells in date order and cannot be
# vectorised, so its null costs far more per draw than the ministry one. Thirty
# draws put the standard error on the null well under a tenth of the gap being
# measured, which is all it has to do.
N_PERM_NAMESAKE = 30

# Below this a ministry's concentration is being read off a few dozen people.
MIN_STAFF = 200


def prepare(spells: pd.DataFrame, persons: pd.DataFrame) -> dict:
    """Attach surnames and ministries; drop what the proxy cannot carry."""
    persons = persons.copy()
    persons["name"] = persons.name.fillna("")
    gs = [split_name(n) for n in persons.name]
    persons["surname"] = [s for _, s in gs]
    persons["given"] = [g for g, _ in gs]
    persons = persons[[usable(s) for s in persons.surname]]

    sn = dict(zip(persons.person_id, persons.surname))
    fy = dict(zip(persons.person_id, persons.first_year))

    s = spells.copy()
    s["org_name"] = s.org_name.fillna("")
    s["ministry"] = [ministry_of(p, o) for p, o in
                     zip(s.org_portfolio, s.org_name)]
    s["surname"] = s.person_id.map(sn)
    s["entry"] = s.person_id.map(fy)
    s = s.dropna(subset=["surname", "entry"])
    return {"spells": s, "persons": persons}


# --------------------------------------------------------------------------
# left panel: concentration within a ministry
# --------------------------------------------------------------------------

def ministry_concentration(s: pd.DataFrame, rng) -> list[dict]:
    staff = (s.dropna(subset=["ministry"])[["person_id", "surname", "ministry"]]
             .drop_duplicates())
    # "autre" is the portfolio value for a post whose ministry the record does
    # not name. It is a residue of heterogeneous small bodies, not a ministry,
    # and it is dropped rather than drawn: its concentration is high, which on
    # a row labelled like the others would read as a finding about a
    # department that does not exist.
    staff = staff[staff.ministry.isin(MINISTRY_ENGLISH)]
    big = [m for m, g in staff.groupby("ministry") if len(g) >= MIN_STAFF]
    staff = staff[staff.ministry.isin(big)]

    obs = {m: same_surname_probability(g.surname.tolist())
           for m, g in staff.groupby("ministry")}

    people = staff.drop_duplicates("person_id")[["person_id", "surname"]]
    people = people.merge(
        s.drop_duplicates("person_id")[["person_id", "entry"]], on="person_id")
    codes, _ = pd.factorize(people.surname)
    decade = (people.entry // 10 * 10).values
    pos = {q: i for i, q in enumerate(people.person_id.values)}
    row = staff.person_id.map(pos).values
    mcol = staff.ministry.values
    strata = [np.where(decade == d)[0] for d in np.unique(decade)]

    null = {m: [] for m in big}
    for _ in range(N_PERM_MINISTRY):
        perm = codes.copy()
        for g in strata:
            perm[g] = rng.permutation(codes[g])
        dealt = perm[row]
        for m in big:
            sel = dealt[mcol == m]
            null[m].append(same_surname_probability(sel.tolist()))

    out = []
    for m in big:
        nl = np.array(null[m])
        out.append({
            "ministry": m,
            "label": MINISTRY_ENGLISH.get(m, m.replace("_", " ").title()),
            "n": int((staff.ministry == m).sum()),
            "obs": obs[m],
            "null": float(nl.mean()),
            "ratio": obs[m] / nl.mean(),
            # Filled where no permutation in the whole run reached the observed
            # value; open where at least one did.
            "clears": bool((nl >= obs[m]).sum() == 0),
        })
    out.sort(key=lambda r: r["ratio"])
    return out


# --------------------------------------------------------------------------
# right panel: a namesake already inside, by how rare the name is
# --------------------------------------------------------------------------

def namesake_by_rarity(s: pd.DataFrame, persons: pd.DataFrame, rng) -> list[dict]:
    d = s.dropna(subset=["org_id"]).copy()
    d["start"] = pd.to_datetime(d.start_date, errors="coerce")
    d = d.dropna(subset=["start"]).sort_values("start")

    freq = Counter(persons.surname)
    org = d.org_id.values
    pid = d.person_id.values

    def scan(mapping):
        sn = d.person_id.map(mapping).values
        hits = np.array(namesake_hits(zip(org, pid, sn)))
        band = np.array([rarity_band(freq[x]) for x in sn])
        return hits, band

    obs_hits, obs_band = scan(dict(zip(persons.person_id, persons.surname)))

    people = persons[["person_id", "surname", "first_year"]].copy()
    people["decade"] = people.first_year // 10 * 10
    acc = {b: [] for b in BANDS}
    for _ in range(N_PERM_NAMESAKE):
        sh = people.surname.values.copy()
        for dv in people.decade.unique():
            g = np.where(people.decade.values == dv)[0]
            sh[g] = rng.permutation(sh[g])
        h, b = scan(dict(zip(people.person_id, sh)))
        for band in BANDS:
            acc[band].append(h[b == band].mean() * 100)

    out = []
    for band in BANDS:
        m = obs_band == band
        o = obs_hits[m].mean() * 100
        nl = np.array(acc[band])
        out.append({"band": band, "n": int(m.sum()), "obs": o,
                    "null": float(nl.mean()), "ratio": o / nl.mean(),
                    "clears": bool((nl >= o).sum() == 0)})
    overall = {"obs": obs_hits.mean() * 100,
               "n": len(obs_hits)}
    return out, overall


# --------------------------------------------------------------------------

def draw_left(ax, rows) -> None:
    for i, r in enumerate(rows):
        colour = EXCEPT if r["ratio"] < 1.0 else MAIN
        ax.plot([1.0, r["ratio"]], [i, i], color=RULE, lw=1.5, zorder=2,
                solid_capstyle="round")
        if r["clears"]:
            ax.plot([r["ratio"]], [i], "o", ms=7, color=colour, zorder=4)
        else:
            ax.plot([r["ratio"]], [i], "o", ms=7, mfc="white", mec=colour,
                    mew=1.5, zorder=4)
        ax.annotate(f"{r['ratio']:.2f}×", xy=(r["ratio"] + 0.05, i),
                    va="center", ha="left", fontsize=7.0,
                    color=INK if r["clears"] else MUTED)
        # The staff count sits in the clear strip left of the chance line, not
        # under the tick labels, which it used to overlap.
        ax.annotate(f"{r['n']:,}", xy=(0.975, i), va="center", ha="right",
                    fontsize=6.6, color=MUTED)

    ax.axvline(1.0, color=INK, lw=1.0, zorder=3)
    # Axes coordinates, not data: at the top of the data range this sat above
    # ylim and was clipped away entirely.
    ax.annotate("chance", xy=(1.0, 1.0), xycoords=("data", "axes fraction"),
                xytext=(3, -2), textcoords="offset points", ha="left",
                va="top", fontsize=7.2, color=INK, style="italic")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=7.6, color=INK)
    # Half a row of headroom so the "chance" label sits above the top bar
    # rather than across it.
    ax.set_ylim(-0.7, len(rows) + 0.15)
    ax.set_xlim(0.80, 3.80)
    ax.set_xticks([1, 1.5, 2, 2.5, 3, 3.5])
    ax.set_xlabel("surname concentration ÷ concentration under the permutation",
                  fontsize=8.0)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Within a ministry", fontsize=9.6)


def draw_right(ax, rows) -> None:
    # Log scale, because the five bands sit two orders of magnitude apart in
    # level: on a linear axis the rarest band's pair is a single dot against a
    # 40% band and the comparison the panel exists to make is invisible. On a
    # log axis equal ratios are equal lengths, so the finding — the excess
    # shrinking as the name gets commoner — is the bar lengths shortening.
    ax.set_xscale("log")
    y = np.arange(len(rows))[::-1]
    for i, r in zip(y, rows):
        ax.plot([r["null"], r["obs"]], [i, i], color=RULE, lw=2.4, zorder=2,
                solid_capstyle="round")
        ax.plot([r["null"]], [i], "o", ms=7, mfc="white", mec=MUTED, mew=1.5,
                zorder=4)
        ax.plot([r["obs"]], [i], "o", ms=8, color=MAIN, zorder=5)
        ax.annotate(f"{r['ratio']:.2f}×", xy=(r["obs"], i), xytext=(11, 0),
                    textcoords="offset points", va="center", ha="left",
                    fontsize=8.6, color=INK, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['band']}\n{r['n']:,} arrivals" for r in rows],
                       fontsize=8.4, color=INK, linespacing=1.5)
    ax.set_ylabel("people in the register carrying that surname", fontsize=8.0)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0.16, 95)
    ax.set_xticks([0.3, 1, 3, 10, 30])
    ax.set_xticklabels(["0.3", "1", "3", "10", "30"])
    ax.minorticks_off()
    ax.set_xlabel("arrivals finding a namesake already in the body (%)",
                  fontsize=8.0)
    ax.xaxis.grid(True, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("On arrival at any body", fontsize=9.6)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="", ms=8, color=MAIN, label="observed"),
        Line2D([], [], marker="o", ls="", ms=7, mfc="white", mec=MUTED,
               mew=1.5, label="surnames shuffled within entry decade"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)


def fig_surnames(spells: pd.DataFrame, persons: pd.DataFrame) -> None:
    rng = np.random.default_rng(SEED)
    prep = prepare(spells, persons)
    left = ministry_concentration(prep["spells"], rng)
    right, overall = namesake_by_rarity(prep["spells"], prep["persons"], rng)

    fig, axes = plt.subplots(1, 2, figsize=(13.6, 8.8),
                             gridspec_kw={"width_ratios": [1.35, 1.0]})
    fig.subplots_adjust(top=0.775, bottom=0.135, left=0.145, right=0.965,
                        wspace=0.42)
    draw_left(axes[0], left)
    draw_right(axes[1], right)

    clear = [r for r in left if r["clears"]]
    n_above = len([r for r in left if r["ratio"] > 1])
    above_phrase = (f"All {len(left)}" if n_above == len(left)
                    else f"{n_above} of the {len(left)}")
    lowest, highest = left[0], left[-1]
    rare, common = right[0], right[-1]
    headline(
        fig,
        "Officials cluster with their namesakes, and the rarer the name the more they cluster",
        f"Left: how much more surname-concentrated each ministry's staff is "
        f"than the same people would be if surnames were dealt out at random "
        f"within entry decade. {above_phrase} "
        f"ministries sit above chance, {len(clear)} of them by more than any "
        f"of {N_PERM_MINISTRY} permutations reached; the spread runs from "
        f"{highest['label'].lower()} at {highest['ratio']:.2f}× down to "
        f"{lowest['label'].lower()} at {lowest['ratio']:.2f}×, which is not "
        f"separable from chance. Right: how often someone arriving at a body "
        f"finds a namesake already there — {overall['obs']:.1f}% of "
        f"{overall['n']:,} arrivals — split by how many people in the register "
        f"carry the surname. The excess over chance runs from "
        f"{rare['ratio']:.2f}× for a surname held by one or two people to "
        f"{common['ratio']:.2f}× for one held by more than sixty. A shared "
        f"rare name is evidence of a shared family; a shared common one mostly "
        f"is not, and that is where the effect goes.",
        width=150,
    )
    save(fig, "fig33_surnames",
         SOURCE + "  A surname is read as everything from a particle to the "
                  "end of the name, so Ben Abdallah is not filed under "
                  "Abdallah. Which particle takes two rules, because the two "
                  "kinds behave differently in the record: ben, bin and ould "
                  "chain, and 1,078 names run 'X ben Y ben Z', where Tunisian "
                  "usage makes the terminal patronymic the family name, so the "
                  "last of them opens the surname; el, bel, bou, hadj, caïd "
                  "and the rest also occur inside compound given names — el is "
                  "followed by a later ben in 117 names — so one of these "
                  "opens the surname only when no ben, bin or ould is present, "
                  "and then it is the first. Taking the first particle "
                  "regardless files Zine El Abidine Ben Ali, the "
                  "most-recorded name in the corpus, under 'el abidine ben "
                  "ali'. Where there is no particle the surname is the final "
                  "token. People whose final token is a bare given name are "
                  "left out, because the record does not say whether it is a "
                  "family name or a second given name. So are the rows where "
                  "the extractor took French running text from the surrounding "
                  "act for a name. Posts whose portfolio names no ministry are "
                  "not a ministry and are not drawn. The proxy "
                  "is weak in both directions and the weakness is not "
                  "symmetric in its consequences: 77% of the 11,850 people "
                  "recorded under more than one spelling have variants that "
                  "disagree about their own surname, which files real kin "
                  "under different names; and the commonest surnames here — "
                  "Trabelsi, Cherif, Dridi, Hammami, Gharbi — are the "
                  "commonest surnames in Tunisia, which files strangers under "
                  "one name. Both push the measured effect towards chance "
                  "rather than away from it, so these ratios are floors. The "
                  "rival explanation for the left panel is regional rather "
                  "than familial recruitment, since Tunisian surnames are "
                  "regionally patterned; the right panel is what separates "
                  "them, because region predicts clustering in common "
                  "surnames and kinship predicts it in rare ones, and the "
                  "gradient runs the way kinship predicts. It does not rule "
                  "region out. No ranking of surnames is drawn or computed "
                  "anywhere in this build: on the common names that would head "
                  "such a list the instrument is weakest, and the structural "
                  "result does not need one. A body is an organisation as the "
                  "register identifies it, not a ministry, so the right panel "
                  "counts arrival at a directorate as well as at a ministry; a "
                  "person returning to a body they already served in is not "
                  "counted as their own namesake.")


def main() -> None:
    print("loading tables…")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    persons = pd.read_csv(PROC / "persons.csv.gz", low_memory=False)
    print("drawing…")
    fig_surnames(spells, persons)
    print("done")


if __name__ == "__main__":
    main()
