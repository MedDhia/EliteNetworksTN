"""What three ruptures did to the composition of the Tunisian state apparatus.

Three moments are compared: Ben Ali's removal of Bourguiba on 7 November 1987,
the flight of Ben Ali on 14 January 2011, and Kaïs Saïed's suspension of
parliament on 25 July 2021. Each is read through the same source - the acts of
appointment, transfer and termination published in the Journal Officiel - so
that whatever differences appear between them are differences in what the
rupture did, not in how it was observed.

Two measurement problems shape every figure here, and both have to be handled
before any of these series mean anything.

**The gazette is not of constant size.** It carried some 1,200 personnel acts
in 1987 and some 4,500 in 2011. Counting appointments would therefore make 2011
look like the larger upheaval whatever actually happened. Every rate below is
either divided by the number of issues published in the same month, or
expressed as a ratio to its own pre-rupture baseline, so that the unit is
always intensity rather than volume.

**Exits are recorded far less reliably than entries.** An appointment is an act;
a departure frequently is not, and is known only because someone else was
later appointed to the same post. The share of spells closed by an act that
states the exit varies from era to era - 27% of spells begun in the 1990s are
still open in the record against 71% of those begun in the 2020s - so survival
curves from different decades cannot be laid on the same axis and read off.
Every survival comparison here is therefore against a placebo cohort drawn from
the *same* era, which carries the same recording regime; the quantity being
read is the gap between the two curves, not the height of either.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from figstyle import (  # noqa: E402
    CAT4, FIGS, INK, MUTED, PAPER, PROC, RANK_RAMP, RULE, RUPTURE_COLOUR,
    SOURCE, headline, plt, save,
)
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import (  # noqa: E402
    FixedFormatter, FixedLocator, NullLocator,
)

# --- the three ruptures ----------------------------------------------------
# Each is dated to the act that changed who governed, not to the wider episode.
RUPTURES = [
    ("1987", pd.Timestamp("1987-11-07"),
     "7 Nov 1987", "Ben Ali displaces Bourguiba"),
    ("2011", pd.Timestamp("2011-01-14"),
     "14 Jan 2011", "Ben Ali flees; revolution"),
    ("2021", pd.Timestamp("2021-07-25"),
     "25 Jul 2021", "Saïed suspends parliament"),
]

# Placebo dates are the same calendar day three to seven years earlier. Pooling
# five of them keeps a single unusual year from standing as "ordinary time".
PLACEBO_LAGS = (3, 4, 5, 6, 7)

# Acts that move a person into a post. Terminations are excluded: they are
# recorded much more patchily than appointments, and mixing them in would make
# the series partly a measure of record-keeping.
ENTRY_TYPES = ("appointment", "transfer")

# The mirror runs out during 2026. An act dated in one month is published in an
# issue that may appear months later, so the final months of the record are
# missing acts that simply have not been gazetted yet. Everything after this is
# dropped rather than plotted as a fall.
#
# The cut is not cosmetic. Read to the last month held, the 2021 series peaks at
# 1.37x baseline at +60 months; read to three months earlier, at 1.15x at +31.
# A statistic that moves that much with the cut is an artefact of the cut. The
# yearly means below shift by at most 0.05 between the two, which is why they
# are what the figure reports.
RECORD_ENDS = pd.Timestamp("2026-05-31")


# The security apparatus is not a portfolio in this data: the interior ministry
# carries one, but its field administration is filed by organisational form and
# defence bodies by name. It is therefore assembled from the organisation's own
# name and form.
#
# "commerce interieur" - domestic trade - is the trap here, and the interior
# pattern is anchored on the ministry's full title to avoid it.
_INTERIOR = re.compile(
    r"minist[eè]re de l'int[ée]rieur|secr[ée]tariat d'etat [aà] l'int[ée]rieur|"
    r"s[uû]ret[ée] nationale|garde nationale|protection civile", re.I)
_DEFENCE = re.compile(r"d[ée]fense nationale|tribunal militaire|arm[ée]e", re.I)

SECURITY_BRANCHES = [
    ("interior", "Interior ministry\nand its directorates"),
    ("territorial", "Governorates\n(the prefectoral corps)"),
    ("municipal", "Municipalities"),
    ("defence", "Defence and\nmilitary justice"),
]


def security_branch(org: str, form: str) -> str | None:
    if _INTERIOR.search(org):
        return "interior"
    if _DEFENCE.search(org):
        return "defence"
    if form == "gouvernorat":
        return "territorial"
    if form == "commune":
        return "municipal"
    return None



# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
print("loading tables…")
events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)

events["date"] = pd.to_datetime(events.event_date, errors="coerce")
events = events.dropna(subset=["date"])
events["month"] = events.date.values.astype("datetime64[M]")

spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
spells = spells.dropna(subset=["start"])
spells["is_security"] = [
    security_branch(o, f) in ("interior", "territorial", "defence")
    for o, f in zip(spells.org_name.fillna(""), spells.org_form.fillna(""))
]

entries = events[events.event_type.isin(ENTRY_TYPES)]

# Gazette throughput: distinct issues carrying any personnel act in the month.
# This is the denominator that turns a count of appointments into a rate.
issues_per_month = events.groupby("month").issue_key.nunique()
entries_per_month = entries.groupby("month").size()
MONTHS = issues_per_month.index


def month_index(t0: pd.Timestamp, lo: int, hi: int) -> pd.DatetimeIndex:
    """Calendar months at offsets ``lo``..``hi`` from ``t0``'s month."""
    base = pd.Timestamp(t0.year, t0.month, 1)
    return pd.DatetimeIndex([base + pd.DateOffset(months=k) for k in range(lo, hi + 1)])


def entry_rate(months: pd.DatetimeIndex) -> pd.Series:
    """Entries per gazette issue, month by month.

    A month in which nothing at all was published is left missing rather than
    set to zero: no issues means no observation, not an observation of none.
    Months past the end of the record are dropped for the same reason.
    """
    num = entries_per_month.reindex(months)
    den = issues_per_month.reindex(months)
    out = (num / den.where(den > 0)).astype(float)
    return out.where(pd.Series(months <= RECORD_ENDS, index=months))


# ---------------------------------------------------------------------------
# figure 10 - appointment intensity in event time
# ---------------------------------------------------------------------------
def fig_intensity() -> None:
    lo, hi = -24, 60
    n_base = -13 - lo + 1                 # baseline ends a year before the event

    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.2), sharey=True)
    fig.subplots_adjust(top=0.60, wspace=0.10, bottom=0.16)

    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        months = month_index(t0, lo, hi)
        rate = entry_rate(months)
        x = np.arange(lo, hi + 1)
        base = rate.iloc[:n_base].mean()
        smooth = rate.rolling(3, center=True, min_periods=2).mean()
        colour = RUPTURE_COLOUR[key]

        ax.axhline(base, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=2)
        ax.axvline(0, color=INK, lw=1.1, zorder=3)
        ax.plot(x, smooth.values, color=colour, lw=1.3, alpha=0.45, zorder=4)

        # The yearly mean, drawn as a step. A peak is one observation sitting
        # wherever the record happens to stop; the mean of a year either side of
        # it barely moves when the cut does, so that is what carries the reading.
        for y in range(5):
            seg = rate.iloc[(12 * y - lo):(12 * (y + 1) - lo)]
            if seg.notna().sum() < 6:
                continue
            m = seg.mean()
            ax.plot([12 * y, 12 * (y + 1)], [m, m], color=colour, lw=3.0,
                    solid_capstyle="butt", zorder=6)
            ax.annotate(f"{m / base:.2f}", xy=(12 * y + 6, m), xytext=(0, 6),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=7.6, color=colour, fontweight="bold", zorder=8)

        # Where the record itself stops, rather than the state.
        last = rate.last_valid_index()
        if last is not None:
            edge = int(round((last - months[0]).days / 30.44)) + lo
            if edge < hi:
                ax.axvspan(edge, hi, color=RULE, alpha=0.55, lw=0, zorder=1)
                ax.annotate("beyond\nthe record", xy=((edge + hi) / 2, 15.4),
                            ha="center", va="top", fontsize=6.8, color=MUTED,
                            linespacing=1.3, zorder=8)

        ax.set_title(f"{key}  ·  {datestr}\n{gloss}", color=INK, fontsize=9.5,
                     linespacing=1.5)
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, 16.5)
        ax.set_xticks([-12, 0, 12, 24, 36, 48, 60])
        ax.set_xlabel("months from the rupture")
        ax.grid(axis="y", zorder=0)
        ax.set_axisbelow(True)

    axes[0].set_ylabel("appointments per gazette issue")
    axes[0].annotate("- -  pre-rupture baseline\nbars: mean of each year after,\n"
                     "labelled as a multiple of baseline",
                     xy=(0.025, 0.985), xycoords="axes fraction", fontsize=7.0,
                     color=MUTED, ha="left", va="top", linespacing=1.5)

    headline(
        fig,
        "Ben Ali replaced the apparatus slowly; the revolution did it at once; Saïed has not",
        "Personnel acts per issue of the Journal Officiel around three changes of "
        "regime, over the five years after each. Dividing by issues published "
        "removes the fourfold growth of the gazette between 1987 and 2011. All three "
        "begin with a freeze, and then diverge. 1987 climbs year on year to half "
        "again above its baseline by year five. 2011 spends its replacement in one "
        "burst at nine months and subsides below baseline. 2021 returns to its "
        "baseline and stops there: no year of the five reaches 1.02 times it.",
    )
    save(fig, "fig10_rupture_appointment_intensity",
         SOURCE + "  Baseline is the mean rate over months \u221224 to \u221213. The "
                  "record is cut at May 2026: an act dated in one month appears in "
                  "an issue published later, so the last months held are missing "
                  "acts not yet gazetted. The cut matters - read to the final month "
                  "held, the 2021 series peaks at 1.37\u00d7 baseline at +60 months, "
                  "and read three months earlier at 1.15\u00d7 at +31. The yearly "
                  "means move by at most 0.05 between those two readings, which is "
                  "why they, and not a peak, are what the figure states. In 1987 "
                  "the sharpest single month precedes the rupture: Ben Ali was "
                  "interior minister from April and prime minister from October of "
                  "that year.")


# ---------------------------------------------------------------------------
# figure 11 - survival of the incumbents
# ---------------------------------------------------------------------------
def cohort_survival(t0: pd.Timestamp, horizon: int) -> tuple[int, np.ndarray]:
    """Share of the people in post at ``t0`` still in post month by month.

    Right-censored spells count as still in post, which is what the record
    supports and no more. Because exits are under-recorded, the level of this
    curve overstates persistence; the comparison it is used for below holds
    that bias constant on both sides.
    """
    inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
    ends = inpost.end
    out = np.empty(horizon + 1)
    for h in range(horizon + 1):
        tt = t0 + pd.DateOffset(months=h)
        out[h] = float((ends.isna() | (ends > tt)).mean())
    return len(inpost), out


def fig_survival() -> None:
    horizon = 36
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 4.0), sharey=True)
    fig.subplots_adjust(top=0.62, wspace=0.12, bottom=0.16)
    x = np.arange(horizon + 1)

    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        n_rup, s_rup = cohort_survival(t0, horizon)
        placebos = [cohort_survival(t0 - pd.DateOffset(years=k), horizon)[1]
                    for k in PLACEBO_LAGS]
        s_plc = np.mean(placebos, axis=0)
        lo_plc, hi_plc = np.min(placebos, axis=0), np.max(placebos, axis=0)
        colour = RUPTURE_COLOUR[key]

        ax.fill_between(x, lo_plc, hi_plc, color=MUTED, alpha=0.16, lw=0)
        ax.plot(x, s_plc, color=MUTED, lw=1.3, ls=(0, (4, 3)))
        ax.plot(x, s_rup, color=colour, lw=1.8)

        gap = (s_rup[-1] - s_plc[-1]) * 100
        ax.fill_between(x, s_plc, s_rup, color=colour, alpha=0.13, lw=0)
        ax.annotate(f"{gap:+.1f} pp\nat 3 years",
                    xy=(0.96, 0.96), xycoords="axes fraction",
                    ha="right", va="top", fontsize=8.6,
                    color=colour, fontweight="bold", linespacing=1.4)
        ax.set_title(f"{key}  ·  {datestr}\n{gloss}", color=INK, fontsize=9.5,
                     linespacing=1.5)
        # Cohort size goes inside the panel: appended to the title it ran into
        # the neighbouring one.
        ax.annotate(f"n = {n_rup:,} in post", xy=(0.035, 0.04),
                    xycoords="axes fraction", fontsize=7.4, color=MUTED,
                    ha="left", va="bottom")
        ax.set_xlim(0, horizon)
        ax.set_xticks([0, 12, 24, 36])
        ax.set_xlabel("months after the rupture")
        ax.grid(axis="y", zorder=0)
        ax.set_axisbelow(True)

    axes[0].set_ylabel("share of incumbents still in post")
    axes[1].legend(handles=[
        Line2D([], [], color=INK, lw=1.8, label="cohort in post at the rupture"),
        Line2D([], [], color=MUTED, lw=1.3, ls=(0, (4, 3)),
               label="same-era cohorts, 3–7 years earlier (range shaded)"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)

    headline(
        fig,
        "After 2021 officials stayed in post longer than in ordinary times",
        "Of those holding an office on the eve of each rupture, the share still "
        "holding it over the following three years, against the average of five "
        "cohorts from the same era. The grey band spans those five. Reading the "
        "gap rather than the level is what makes the three panels comparable: "
        "exits are recorded differently from decade to decade, and both curves in "
        "a panel share whatever regime applied to them.",
    )
    save(fig, "fig11_incumbent_survival",
         SOURCE + "  Placebo cohorts are those in post on the same calendar day "
                  "3, 4, 5, 6 and 7 years before each rupture. Spells with no "
                  "recorded exit are treated as continuing, so every curve "
                  "overstates persistence; the bias applies equally to both "
                  "curves in a panel.")


# ---------------------------------------------------------------------------
# composition indices
# ---------------------------------------------------------------------------
def composition_index(column: str, categories: list[str], min_pre: float = 8.0
                      ) -> pd.DataFrame:
    """How far each part of the apparatus moved *relative to the whole*.

    For one rupture, a category's turnover multiple is its mean annual number
    of entries in the three years after, over the mean in the four years before.
    Dividing that by the same multiple computed over every category leaves a
    number that is 1.0 when a category moved exactly in step with the state as
    a whole, above 1 when it was reshaped harder, below 1 when it was spared.

    Taking the ratio of ratios is what makes the ruptures comparable. The
    absolute multiple at 2021 is dragged down by a gazette that was shrinking
    for reasons of its own; dividing it out leaves the question this figure is
    actually about, which is where within the apparatus the churn fell.

    Categories thinner than ``min_pre`` entries a year before the rupture are
    dropped: a multiple computed on three or four acts is noise.
    """
    rows = []
    for key, t0, _, _ in RUPTURES:
        pre = (t0 - pd.DateOffset(years=4), t0)
        post = (t0, t0 + pd.DateOffset(years=3))

        def rate(frame, span, years):
            sel = frame[(frame.date >= span[0]) & (frame.date < span[1])]
            return len(sel) / years

        whole = rate(entries, post, 3) / max(rate(entries, pre, 4), 1e-9)
        for cat in categories:
            sub = entries[entries[column] == cat]
            pre_rate = rate(sub, pre, 4)
            if pre_rate < min_pre:
                rows.append({"rupture": key, "category": cat, "index": np.nan,
                             "pre_rate": pre_rate})
                continue
            rows.append({"rupture": key, "category": cat,
                         "index": (rate(sub, post, 3) / pre_rate) / whole,
                         "pre_rate": pre_rate})
    return pd.DataFrame(rows)


def _rupture_handles():
    return [
        Line2D([], [], marker="o", ls="", markersize=7.5,
               markerfacecolor=RUPTURE_COLOUR[k], markeredgecolor=PAPER,
               label=f"{k}   {g}")
        for k, _, _, g in RUPTURES
    ]


def _dot_panel(ax, table, categories, labels):
    """Shared drawing for the two composition figures.

    The three ruptures are dodged off the category line rather than drawn on
    it. Two of them often land on almost the same value, and a hidden point
    reads as an absent one.
    """
    ax.axvline(1.0, color=INK, lw=1.1, zorder=3)
    dodge = {k: (j - 1) * 0.22 for j, (k, _, _, _) in enumerate(RUPTURES)}
    for i, cat in enumerate(categories):
        y = len(categories) - 1 - i
        if cat is None:          # blank row, used to separate groups
            continue
        ax.axhline(y, color=RULE, lw=0.6, zorder=0)
        vals = table[table.category == cat]
        for key, _, _, _ in RUPTURES:
            v = vals[vals.rupture == key]["index"]
            if v.empty or not np.isfinite(v.iloc[0]):
                continue
            ax.scatter(v.iloc[0], y + dodge[key], s=52,
                       color=RUPTURE_COLOUR[key], zorder=4,
                       edgecolor=PAPER, linewidth=0.9)
    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels(labels[::-1], color=INK)
    ax.set_ylim(-0.7, len(categories) - 0.3)
    ax.set_xscale("log")
    ax.set_xlim(0.2, 5.2)
    # Matplotlib's log locator would otherwise add its own decade labels
    # alongside these and print both.
    ax.xaxis.set_major_locator(FixedLocator([0.25, 0.5, 1, 2, 4]))
    ax.xaxis.set_major_formatter(
        FixedFormatter(["¼×", "½×", "same as\nthe state", "2×", "4×"]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def fig_where() -> None:
    forms = ["presidence", "ministere", "gouvernorat", "juridiction",
             "entreprise_publique", "commune", "direction", "universite"]
    labels = ["Presidency", "Ministries", "Governorates", "Courts",
              "State-owned enterprises", "Municipalities",
              "Directorates", "Universities"]
    table = composition_index("org_form", forms)

    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    fig.subplots_adjust(top=0.72, left=0.23, bottom=0.17)
    _dot_panel(ax, table, forms, labels)
    ax.set_xlabel("churn relative to the state apparatus as a whole  (log scale)",
                  labelpad=18)
    # Legend above the plot: the "same as the state" tick runs to two lines and
    # the axis label sits under that, so the band below is already spoken for.
    ax.legend(handles=_rupture_handles(), loc="lower center",
              bbox_to_anchor=(0.5, 1.01), ncol=3)

    headline(
        fig,
        "Each rupture reached into a different part of the state",
        "Appointments in the three years after each rupture against the four "
        "years before, divided by the same ratio for the apparatus as a whole. "
        "A point to the right of the line marks a part of the state reshaped "
        "harder than the rest; to the left, one left comparatively alone. "
        "Expressing it as a ratio to the whole removes the differing size of the "
        "gazette in each period.",
    )
    save(fig, "fig12_where_the_apparatus_was_remade",
         SOURCE + "  Categories with fewer than 8 appointments a year before a "
                  "rupture are not plotted for that rupture.")


def fig_depth() -> None:
    ranks = ["secretaire_general", "directeur_general", "conseiller_pol",
             "inspecteur_general", "directeur", "sous_directeur",
             "chef_service", "cadre", "administrateur_ca"]
    labels = ["Secretary-general", "Director-general", "Political adviser",
              "Inspector-general", "Director", "Deputy director",
              "Head of service", "Cadre", "Board member"]
    table = composition_index("position_rank", ranks)

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    fig.subplots_adjust(top=0.74, left=0.23, bottom=0.16)
    _dot_panel(ax, table, ranks, labels)
    ax.set_xlabel("churn relative to the state apparatus as a whole  (log scale)",
                  labelpad=18)
    ax.annotate("more senior", xy=(-0.215, 0.995), xycoords="axes fraction",
                fontsize=7.4, color=MUTED, ha="center", va="top")
    ax.annotate("less senior", xy=(-0.215, -0.035), xycoords="axes fraction",
                fontsize=7.4, color=MUTED, ha="center", va="top")
    ax.legend(handles=_rupture_handles(), loc="lower center",
              bbox_to_anchor=(0.5, 1.03), ncol=3)

    headline(
        fig,
        "How far down the hierarchy each rupture reached",
        "The same ratio as the previous figure, cut by the seniority of the post "
        "rather than the body holding it. A rupture confined to the top of the "
        "state shows points to the right only among the senior ranks; one that "
        "reached into the administration shows them further down as well.",
    )
    save(fig, "fig13_depth_of_each_rupture",
         SOURCE + "  Ranks with fewer than 8 appointments a year before a "
                  "rupture are not plotted for that rupture. Ministers, "
                  "secretaries of state and governors are too few per year to "
                  "carry this statistic and are omitted.")



# ---------------------------------------------------------------------------
# figure 15 - ministry by ministry
# ---------------------------------------------------------------------------
def portfolio_domains(label: str) -> tuple[str, ...]:
    """The policy domains a portfolio label covers.

    Ministries are renamed, merged and split constantly, and the portfolio key
    follows the name, so a series keyed on it breaks silently at every
    reorganisation. Between 2007 and 2010 the interior ministry was the
    "ministere de l'Interieur et du Developpement Local" and its appointments
    were filed under a compound key; in 2011 it reverted. Read literally, the
    interior ministry therefore appears to make 43 appointments a year before
    1987, **1.5** before 2011, and 70 before 2021 - which is a fact about its
    letterhead, not about the state.

    Splitting a compound label onto each of its domains repairs the series: the
    same three figures become 45, 60 and 69. An appointment to a merged ministry
    counts toward each domain it merged, which is what the act itself means, and
    the same expansion is applied on both sides of every ratio.

    Presidency keys are atomic: "presidence_republique" and
    "presidence_gouvernement" are two different institutions, not a merger.
    """
    if not label:
        return ()
    if label.startswith("min_"):
        return tuple(d for d in label[4:].split("+") if d)
    return (label,)


# Ministries grouped by what they are for. The grouping is the analytical point
# of the figure: whether a rupture fell on the ministries that hold power or on
# the ministries that deliver services.
MINISTRY_BLOCS = [
    ("Sovereignty and security", [
        ("interieur", "Interior"),
        ("justice", "Justice"),
        ("affaires_etrangeres", "Foreign Affairs"),
    ]),
    ("Centre of government", [
        ("presidence_republique", "Presidency of the Republic"),
        ("presidence_gouvernement", "Prime Minister's Office"),
    ]),
    ("Economic", [
        ("finances", "Finance"),
        ("agriculture", "Agriculture"),
        ("equipement", "Public Works"),
        ("transport", "Transport"),
    ]),
    ("Social and cultural", [
        ("affaires_sociales", "Social Affairs"),
        ("sante", "Health"),
        ("education", "Education"),
        ("enseignement_superieur", "Higher Education"),
        ("culture", "Culture"),
        ("jeunesse_sport", "Youth and Sport"),
    ]),
]


def ministry_index(min_pre: float = 12.0) -> pd.DataFrame:
    """The composition index of figure 12, per policy domain and per window.

    Two windows: the three years after a rupture, and the two that follow them.
    Each is divided by the apparatus-wide ratio computed over the *same* window,
    so a domain is always being compared with the state as it was at that moment
    rather than with the state three years earlier.

    The late window of 2021 runs into the end of the record and covers 1.85 of
    its 2 years. Rates are per year throughout, so a short window is not a small
    one; it is only noisier.
    """
    exploded = []
    for label, when in zip(entries.org_portfolio.fillna(""), entries.date):
        for dom in portfolio_domains(label):
            exploded.append((dom, when))
    ex = pd.DataFrame(exploded, columns=["domain", "date"])

    rows = []
    for key, t0, _, _ in RUPTURES:
        pre_a, pre_b = t0 - pd.DateOffset(years=4), t0
        pre = ex[(ex.date >= pre_a) & (ex.date < pre_b)].domain.value_counts() / 4
        pre_whole = ((entries.date >= pre_a) & (entries.date < pre_b)).sum() / 4

        windows = {
            "early": (t0, t0 + pd.DateOffset(years=3)),
            "late": (t0 + pd.DateOffset(years=3),
                     min(t0 + pd.DateOffset(years=5), RECORD_ENDS)),
        }
        for wname, (qa, qb) in windows.items():
            years = (qb - qa).days / 365.25
            if years <= 0.5:
                continue
            whole = (((entries.date >= qa) & (entries.date < qb)).sum() / years
                     ) / max(pre_whole, 1e-9)
            post = ex[(ex.date >= qa) & (ex.date < qb)].domain.value_counts() / years
            for _, members in MINISTRY_BLOCS:
                for dom, _label in members:
                    p = float(pre.get(dom, 0.0))
                    rows.append({
                        "rupture": key, "window": wname, "category": dom,
                        "pre_rate": p,
                        "index": (float(post.get(dom, 0.0)) / p) / whole
                                 if p >= min_pre else np.nan,
                    })
    return pd.DataFrame(rows)


def fig_ministries() -> None:
    table = ministry_index()
    order, labels, rules = [], [], []
    for n_bloc, (bloc, members) in enumerate(MINISTRY_BLOCS):
        if n_bloc:
            order.append(None)
            labels.append("")
        rules.append((len(order), bloc))
        for dom, label in members:
            order.append(dom)
            labels.append(label)
    n = len(order)

    fig, axes = plt.subplots(1, 3, figsize=(13.0, 6.9), sharey=True)
    fig.subplots_adjust(top=0.74, left=0.20, bottom=0.13, wspace=0.08)

    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        colour = RUPTURE_COLOUR[key]
        ax.axvline(1.0, color=INK, lw=1.1, zorder=3)
        sub = table[table.rupture == key]
        for i, cat in enumerate(order):
            y = n - 1 - i
            if cat is None:
                continue
            ax.axhline(y, color=RULE, lw=0.6, zorder=0)
            row = sub[sub.category == cat]
            e = row[row.window == "early"]["index"]
            l = row[row.window == "late"]["index"]
            e = float(e.iloc[0]) if len(e) and np.isfinite(e.iloc[0]) else np.nan
            l = float(l.iloc[0]) if len(l) and np.isfinite(l.iloc[0]) else np.nan
            if np.isfinite(e) and np.isfinite(l):
                ax.annotate("", xy=(l, y), xytext=(e, y),
                            arrowprops=dict(arrowstyle="-|>", color=colour,
                                            lw=1.4, alpha=0.75,
                                            shrinkA=4.5, shrinkB=0,
                                            mutation_scale=9), zorder=4)
            if np.isfinite(e):
                # Hollow for the first window, solid for the second, so the
                # two are told apart by shape as well as by where the arrow
                # points - neither depends on colour.
                ax.scatter([e], [y], s=42, facecolor=PAPER, edgecolor=colour,
                           linewidth=1.5, zorder=5)
            if np.isfinite(l):
                ax.scatter([l], [y], s=30, color=colour, zorder=6,
                           edgecolor=PAPER, linewidth=0.8)

        for start, bloc in rules:
            yb = n - 1 - start
            if start:
                ax.axhline(yb + 1.0, color=RULE, lw=0.9, zorder=1)

        ax.set_title(f"{key}  ·  {datestr}\n{gloss}", color=INK, fontsize=9.5,
                     linespacing=1.5)
        ax.set_xscale("log")
        ax.set_xlim(0.13, 6.0)
        ax.xaxis.set_major_locator(FixedLocator([0.25, 1, 4]))
        ax.xaxis.set_major_formatter(FixedFormatter(["¼×", "same", "4×"]))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_ylim(-0.7, n - 0.3)
        ax.grid(axis="x", zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)

    axes[0].set_yticks(range(n))
    axes[0].set_yticklabels(labels[::-1], color=INK)
    for start, bloc in rules:
        axes[0].annotate(bloc.upper(), xy=(-0.46, n - 1 - start + 0.72),
                         xycoords=("axes fraction", "data"), fontsize=7.0,
                         color=MUTED, fontweight="bold", ha="left", va="center")
    axes[1].set_xlabel("churn relative to the state apparatus as a whole  (log scale)",
                       labelpad=10)
    axes[1].legend(handles=[
        Line2D([], [], marker="o", ls="", markersize=7.5, markerfacecolor=PAPER,
               markeredgecolor=INK, markeredgewidth=1.5, label="years 0–3 after"),
        Line2D([], [], marker="o", ls="", markersize=6.5, markerfacecolor=INK,
               markeredgecolor=PAPER, label="years 3–5 after (arrow points here)"),
    ], loc="lower center", bbox_to_anchor=(0.5, 1.16), ncol=2)

    headline(
        fig,
        "What each rupture did first, and what it went on doing",
        "The previous figure's ratio computed twice: over the three years after "
        "each rupture, and over the two that follow. An arrow pointing left marks "
        "a ministry the rupture reached early and then let alone; one pointing "
        "right marks an effect that arrived late. Both windows are measured "
        "against the apparatus as a whole at the same moment.",
    )
    save(fig, "fig15_ministry_early_and_late",
         SOURCE + "  Merged ministries are counted toward each domain they merge, "
                  "because the portfolio key follows the ministry's name and would "
                  "otherwise break at every rename: read literally, the interior "
                  "ministry makes 1.5 appointments a year before 2011 and 70 before "
                  "2021, an artefact of its having been the ministry of the Interior "
                  "and Local Development until 2011. Domains with fewer than 12 "
                  "appointments a year before a rupture are not plotted for it. The "
                  "late window of 2021 ends with the record and covers 1.85 of its "
                  "two years; rates are per year throughout, so it is noisier rather "
                  "than smaller. Governorates and municipalities are the interior "
                  "ministry's field administration but are filed under their own "
                  "form, so its reach is understated.")



# ---------------------------------------------------------------------------
# figures 16 and 17 - the security apparatus, and demotion
# ---------------------------------------------------------------------------
def _branch_series(frame):
    org = frame.org_name.fillna("")
    form = frame.org_form.fillna("")
    return [security_branch(o, f) for o, f in zip(org, form)]


def fig_security() -> None:
    ent = entries.copy()
    ent["branch"] = _branch_series(ent)

    rows = []
    for key, t0, _, _ in RUPTURES:
        pre_a, pre_b = t0 - pd.DateOffset(years=4), t0
        pre_all = ((ent.date >= pre_a) & (ent.date < pre_b)).sum() / 4
        for wname, (qa, qb) in {
            "early": (t0, t0 + pd.DateOffset(years=3)),
            "late": (t0 + pd.DateOffset(years=3),
                     min(t0 + pd.DateOffset(years=5), RECORD_ENDS)),
        }.items():
            years = (qb - qa).days / 365.25
            whole = (((ent.date >= qa) & (ent.date < qb)).sum() / years
                     ) / max(pre_all, 1e-9)
            for br, _label in SECURITY_BRANCHES:
                sel = ent.branch == br
                pre = (sel & (ent.date >= pre_a) & (ent.date < pre_b)).sum() / 4
                post = (sel & (ent.date >= qa) & (ent.date < qb)).sum() / years
                rows.append({"rupture": key, "window": wname, "category": br,
                             "index": (post / pre) / whole if pre >= 8 else np.nan})
    table = pd.DataFrame(rows)

    order = [b for b, _ in SECURITY_BRANCHES]
    labels = [l for _, l in SECURITY_BRANCHES]
    n = len(order)

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 4.3), sharey=True)
    fig.subplots_adjust(top=0.63, left=0.20, bottom=0.20, wspace=0.08)

    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        colour = RUPTURE_COLOUR[key]
        ax.axvline(1.0, color=INK, lw=1.1, zorder=3)
        sub = table[table.rupture == key]
        for i, cat in enumerate(order):
            y = n - 1 - i
            ax.axhline(y, color=RULE, lw=0.6, zorder=0)
            row = sub[sub.category == cat]
            e = row[row.window == "early"]["index"]
            l = row[row.window == "late"]["index"]
            e = float(e.iloc[0]) if len(e) and np.isfinite(e.iloc[0]) else np.nan
            l = float(l.iloc[0]) if len(l) and np.isfinite(l.iloc[0]) else np.nan
            if np.isfinite(e) and np.isfinite(l):
                ax.annotate("", xy=(l, y), xytext=(e, y),
                            arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.6,
                                            alpha=0.75, shrinkA=5, shrinkB=0,
                                            mutation_scale=10), zorder=4)
            if np.isfinite(e):
                ax.scatter([e], [y], s=52, facecolor=PAPER, edgecolor=colour,
                           linewidth=1.6, zorder=5)
            if np.isfinite(l):
                ax.scatter([l], [y], s=38, color=colour, zorder=6,
                           edgecolor=PAPER, linewidth=0.8)
        ax.set_title(f"{key}  ·  {datestr}\n{gloss}", color=INK, fontsize=9.5,
                     linespacing=1.5)
        ax.set_xscale("log")
        ax.set_xlim(0.3, 3.4)
        ax.xaxis.set_major_locator(FixedLocator([0.5, 1, 2]))
        ax.xaxis.set_major_formatter(FixedFormatter(["½×", "same", "2×"]))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_ylim(-0.6, n - 0.4)
        ax.grid(axis="x", zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)

    axes[0].set_yticks(range(n))
    axes[0].set_yticklabels(labels[::-1], color=INK, linespacing=1.4)
    axes[1].set_xlabel("churn relative to the state apparatus as a whole  (log scale)",
                       labelpad=10)
    axes[1].legend(handles=[
        Line2D([], [], marker="o", ls="", markersize=7.5, markerfacecolor=PAPER,
               markeredgecolor=INK, markeredgewidth=1.6, label="years 0–3 after"),
        Line2D([], [], marker="o", ls="", markersize=6.5, markerfacecolor=INK,
               markeredgecolor=PAPER, label="years 3–5 after (arrow points here)"),
    ], loc="lower center", bbox_to_anchor=(0.5, 1.24), ncol=2)

    headline(
        fig,
        "Only one of the three ruptures went on reshaping the interior ministry",
        "The coercive and territorial administration, on the same measure as the "
        "ministry figure. 1987 fell on the governorates, the prefectoral corps a "
        "ruler appoints to hold the country, and barely touched the interior "
        "ministry itself. 2011 reached the ministry and then let go. 2021 is the "
        "only case that is still above twice the state's rate three to five years "
        "on.",
    )
    save(fig, "fig16_security_apparatus",
         SOURCE + "  Branches are identified from the organisation's own name and "
                  "form, since the interior ministry's field administration is not "
                  "filed under its portfolio. Customs is excluded: at one to six "
                  "appointments a year it cannot carry a ratio. Governorates and "
                  "municipalities include their secretaries-general and delegates, "
                  "not only the governor or mayor.")



# Promotion, a sideways move and demotion are an ordered, two-sided quantity, so
# they take a diverging treatment: two hues with a neutral grey between them,
# never three unrelated colours. The poles are validated against each other
# (dE 27.9 normal, 23.6 protan) and each against the paper.
MOVE_COLOUR = {"up": "#1B5FC1", "lateral": "#B9B5A8", "down": "#A03B2C"}


def move_outcomes(t0: pd.Timestamp, years: int = 3, security: bool = False) -> dict | None:
    """What became of the people holding office on a given day.

    A person's standing is the highest rank they hold at ``t0``; their next
    standing is the highest rank of any post they take in the window after it.
    The comparison is therefore between the top of their position before and
    after, which is what "demoted" has to mean for someone holding several
    posts at once.

    Two quantities come out, and they must be read separately. The share who
    take *any* recorded post afterwards mixes real departure with the gazette's
    poor recording of exits. The split of that group into up, sideways and down
    does not: everyone in it was observed twice, so nothing about it depends on
    whether departures are gazetted.
    """
    t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
    if t1 <= t0:
        return None
    frame = spells[spells.is_security] if security else spells
    inpost = frame[(frame.start < t0) & (frame.end.isna() | (frame.end > t0))]
    if inpost.empty:
        return None
    before = inpost.groupby("person_id").rank_score.max()
    after = spells[(spells.start >= t0) & (spells.start < t1)] \
        .groupby("person_id").rank_score.max()
    j = before.to_frame("b").join(after.rename("a"), how="left")
    moved = j.dropna()
    if len(moved) < 30:
        return None
    return {"n": len(j), "seen": len(moved) / len(j), "n_seen": len(moved),
            "up": float((moved.a > moved.b).mean()),
            "lateral": float((moved.a == moved.b).mean()),
            "down": float((moved.a < moved.b).mean())}


def fig_demotion() -> None:
    scopes = [(False, "The state as a whole"),
              (True, "The security apparatus alone")]
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6), sharex=True)
    fig.subplots_adjust(top=0.58, bottom=0.20, left=0.16, wspace=0.07)

    for ax, (sec, scope_label) in zip(axes, scopes):
        ypos, ylabels = [], []
        y = 0.0
        for key, t0, _, _ in reversed(RUPTURES):
            rup = move_outcomes(t0, security=sec)
            plc = [move_outcomes(t0 - pd.DateOffset(years=k), security=sec)
                   for k in PLACEBO_LAGS]
            plc = [p for p in plc if p]
            if not rup or not plc:
                continue
            base = {k: float(np.mean([p[k] for p in plc]))
                    for k in ("up", "lateral", "down", "seen")}
            for row, res, label in ((0, base, "ordinary times"),
                                    (1, rup, f"after {key}")):
                yy = y + row * 0.62
                left = 0.0
                for part in ("up", "lateral", "down"):
                    ax.barh(yy, res[part] * 100, left=left * 100, height=0.52,
                            color=MOVE_COLOUR[part], zorder=3,
                            edgecolor=PAPER, linewidth=1.2)
                    left += res[part]
                ypos.append(yy)
                ylabels.append(label)
                # The demotion share is the quantity the figure exists for, so
                # it is written on the bar rather than left to the axis.
                ax.annotate(f"{res['down'] * 100:.0f}%",
                            xy=(100 - res["down"] * 100 / 2, yy),
                            ha="center", va="center", fontsize=7.8,
                            color=PAPER, fontweight="bold", zorder=6)
            # The difference goes in the group's own heading rather than beyond
            # the axis, where it landed on the next panel's labels.
            gap = (rup["down"] - base["down"]) * 100
            ax.annotate(f"{key}   ·   {rup['n_seen']:,} of {rup['n']:,} took a further post",
                        xy=(0, y + 1.02), ha="left", va="bottom",
                        fontsize=7.4, color=MUTED)
            ax.annotate(f"{gap:+.1f} pp demoted",
                        xy=(100, y + 1.02), ha="right", va="bottom",
                        fontsize=8.2, fontweight="bold",
                        color=MOVE_COLOUR["down"] if gap > 0 else MUTED)
            y += 2.0

        ax.set_yticks(ypos)
        # Both panels carry the same rows, so only the left one is labelled.
        ax.set_yticklabels(ylabels if ax is axes[0] else [""] * len(ypos),
                           color=INK)
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.5, y - 0.5)
        ax.set_title(scope_label, color=INK, fontsize=9.5)
        ax.set_xlabel("share of those who took a further post (%)")
        ax.grid(axis="x", zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)

    axes[0].legend(handles=[
        Patch(facecolor=MOVE_COLOUR["up"], label="moved up"),
        Patch(facecolor=MOVE_COLOUR["lateral"], label="same rank"),
        Patch(facecolor=MOVE_COLOUR["down"], label="moved down"),
    ], loc="lower left", bbox_to_anchor=(0.0, -0.34), ncol=3)

    headline(
        fig,
        "After 2021 officials were not removed so much as moved down",
        "Of those holding office on the eve of each rupture who took a further "
        "post within three years, the share whose new post ranked above, level "
        "with, or below the one they held. Each rupture is set against the "
        "average of five cohorts from the same era. 1987 and 2011 promoted their "
        "survivors; 2021 demoted them, and did so across the state rather than "
        "only in the security apparatus.",
    )
    save(fig, "fig17_demotion_or_exclusion",
         SOURCE + "  Rank is the ordinal scale documented in the codebook, from "
                  "head of service through director to minister; a person holding "
                  "several posts is placed at the highest. The figure deliberately "
                  "reports only those observed twice. The share taking any further "
                  "post at all fell after 2021 as well (8.5% against 13.1% in "
                  "ordinary times), but that quantity mixes genuine departure with "
                  "the gazette's patchy recording of exits and cannot be read as a "
                  "purge rate. Board memberships are included; excluding them "
                  "leaves the 2021 gap at +7.0 pp rather than +9.9.")


# ---------------------------------------------------------------------------
# figure 14 - elite renewal
# ---------------------------------------------------------------------------
def fig_renewal() -> None:
    first_seen = entries.groupby("person_id").date.min()
    ent = entries.dropna(subset=["person_id"]).copy()
    ent["year"] = ent.date.dt.year
    ent["first_year"] = ent.person_id.map(first_seen).dt.year

    per = ent.drop_duplicates(["person_id", "year"])
    grouped = per.groupby("year")
    share = grouped.apply(lambda g: (g.first_year == g.name).mean())
    counts = grouped.size()

    # The record begins in 1957, so everybody appointed in the first years looks
    # new for want of an earlier gazette to have appeared in. The series is only
    # meaningful once that burn-in has passed.
    lo, hi = 1970, 2025
    share = share.loc[lo:hi]
    counts = counts.loc[lo:hi]

    fig, ax = plt.subplots(figsize=(9.8, 4.3))
    fig.subplots_adjust(top=0.66, bottom=0.14)

    # The series is drawn in ink, not in a palette colour: the three palette
    # colours are spoken for by the ruptures, and reusing one of them here
    # would read as if the line belonged to that rupture.
    ax.plot(share.index, share.values * 100, color=INK, lw=1.5, zorder=4)
    ax.scatter(share.index, share.values * 100, s=np.clip(counts.values / 22, 4, 46),
               color=INK, zorder=5, edgecolor=PAPER, linewidth=0.6)

    # 2011 and 2021 are close enough on this axis that stacked labels would
    # overlap, so they are set at different heights and the 2021 one reads
    # rightwards from its rule.
    label_y = {"1987": 99, "2011": 99, "2021": 80}
    for key, t0, datestr, gloss in RUPTURES:
        ax.axvline(t0.year, color=RUPTURE_COLOUR[key], lw=1.1, zorder=2,
                   ls=(0, (3, 2)))
        ax.annotate(f"{datestr}\n{gloss}", xy=(t0.year, label_y[key]),
                    xytext=(4, 0), textcoords="offset points",
                    fontsize=7.4, color=RUPTURE_COLOUR[key],
                    ha="left", va="top", fontweight="bold", linespacing=1.4)

    ax.set_ylabel("newcomers as a share of those appointed (%)")
    ax.set_xlabel("year")
    ax.set_xlim(lo - 1, hi + 1)
    ax.set_ylim(0, 102)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.text(0.012, 0.045, "point size ∝ people appointed that year",
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=7.2, color=MUTED)

    headline(
        fig,
        "Renewal of the administrative elite, 1970–2025",
        "The share of people receiving an appointment in a given year who had "
        "never appeared in the gazette before. High values mark years in which "
        "the state recruited from outside its own ranks; low values, years in "
        "which it promoted and rotated the people it already had.",
    )
    save(fig, "fig14_elite_renewal",
         SOURCE + "  A person counts as a newcomer in the year of their first "
                  "recorded appointment. The series starts in 1970 because the "
                  "gazette's own beginning in 1957 makes everyone a newcomer at "
                  "first. 2026 is omitted as incomplete.")


if __name__ == "__main__":
    print("drawing…")
    fig_intensity()
    fig_survival()
    fig_where()
    fig_depth()
    fig_ministries()
    fig_security()
    fig_demotion()
    fig_renewal()
    print("done")
