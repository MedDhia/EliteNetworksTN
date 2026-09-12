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
    """
    num = entries_per_month.reindex(months)
    den = issues_per_month.reindex(months)
    return (num / den.where(den > 0)).astype(float)


# ---------------------------------------------------------------------------
# figure 10 - appointment intensity in event time
# ---------------------------------------------------------------------------
def fig_intensity() -> None:
    lo, hi = -30, 30
    n_base = -13 - lo + 1                 # baseline ends a year before the event

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.0), sharey=True)
    fig.subplots_adjust(top=0.60, wspace=0.12, bottom=0.16)

    for ax, (key, t0, datestr, gloss) in zip(axes, RUPTURES):
        months = month_index(t0, lo, hi)
        rate = entry_rate(months)
        x = np.arange(lo, hi + 1)
        base = rate.iloc[:n_base].mean()
        # A quarterly mean carries the trend; the monthly series is noisy
        # enough that a reader would otherwise be following sampling error.
        smooth = rate.rolling(3, center=True, min_periods=2).mean()
        colour = RUPTURE_COLOUR[key]

        ax.axhline(base, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=2)
        ax.axvline(0, color=INK, lw=1.1, zorder=3)
        ax.plot(x, rate.values, color=colour, lw=0.7, alpha=0.32, zorder=4)
        ax.plot(x, smooth.values, color=colour, lw=2.1, zorder=5,
                solid_joinstyle="round")

        # Two moments are marked, because the shape after every one of these
        # ruptures is the same: the gazette stops, and then it either resumes
        # in a burst of replacement or it does not. A single summary number
        # over the first year averages those two phases into nothing.
        post = smooth.iloc[(0 - lo):]
        trough_at = int(np.nanargmin(post.iloc[:13].values))
        peak_at = int(np.nanargmax(post.values))
        # Labels go in two corners that are empty in all three panels and are
        # tied to their points by leader lines. Offsetting them from the points
        # instead puts them on the series, which is what a reader is trying to
        # follow.
        for off, val, lab, xy_text, ha, va in (
            (trough_at, post.iloc[trough_at], "freeze", (0.035, 0.04), "left", "bottom"),
            (peak_at, post.iloc[peak_at], "replacement", (0.975, 0.98), "right", "top"),
        ):
            ax.scatter([off], [val], s=32, color=colour, zorder=7,
                       edgecolor=PAPER, linewidth=1.0)
            ax.annotate(f"{lab}\n{val / base:.2f}× baseline\n+{off} months",
                        xy=(off, val), xycoords="data",
                        xytext=xy_text, textcoords="axes fraction",
                        ha=ha, va=va, fontsize=7.4, color=colour,
                        fontweight="bold", linespacing=1.35, zorder=8,
                        arrowprops=dict(arrowstyle="-", color=colour,
                                        lw=0.7, alpha=0.55,
                                        shrinkA=3, shrinkB=4))

        ax.set_title(f"{key}  ·  {datestr}\n{gloss}", color=INK, fontsize=9.5,
                     linespacing=1.5)
        ax.set_xlim(lo, hi)
        ax.set_ylim(0, 18.6)
        ax.set_xticks([-24, -12, 0, 12, 24])
        ax.set_xlabel("months from the rupture")
        ax.grid(axis="y", zorder=0)
        ax.set_axisbelow(True)

    axes[0].set_ylabel("appointments per gazette issue")
    # Named in the top-left of the first panel, which is empty in all three,
    # rather than beside the rule itself, where it sat on the series.
    axes[0].annotate("- -  pre-rupture baseline", xy=(0.035, 0.96),
                     xycoords="axes fraction", fontsize=7.2, color=MUTED,
                     ha="left", va="top")

    headline(
        fig,
        "Every rupture froze the state; only two of them then replaced its personnel",
        "Personnel acts per issue of the Journal Officiel, by month, around three "
        "changes of regime. Dividing by issues published removes the fourfold growth "
        "of the gazette between 1987 and 2011, so the panels are comparable. All "
        "three ruptures are followed within two months by a collapse in appointments. "
        "1987 and 2011 then recover into a burst of replacement; 2021 never does.",
    )
    save(fig, "fig10_rupture_appointment_intensity",
         SOURCE + "  Baseline is the mean rate over months \u221230 to \u221213. "
                  "Freeze and replacement are the lowest point of the three-month "
                  "mean within twelve months of the rupture, and its highest point "
                  "within thirty. Appointment and transfer acts only. In 1987 the "
                  "sharpest single month precedes the rupture: Ben Ali was interior "
                  "minister from April and prime minister from October of that year.")


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
    """The composition index of figure 12, computed per policy domain."""
    exploded = []
    for label, when in zip(entries.org_portfolio.fillna(""), entries.date):
        for dom in portfolio_domains(label):
            exploded.append((dom, when))
    ex = pd.DataFrame(exploded, columns=["domain", "date"])

    rows = []
    for key, t0, _, _ in RUPTURES:
        pre_a, pre_b = t0 - pd.DateOffset(years=4), t0
        post_a, post_b = t0, t0 + pd.DateOffset(years=3)
        whole = ((entries.date >= post_a) & (entries.date < post_b)).sum() / 3 / (
            max(((entries.date >= pre_a) & (entries.date < pre_b)).sum() / 4, 1e-9))
        pre = ex[(ex.date >= pre_a) & (ex.date < pre_b)].domain.value_counts() / 4
        post = ex[(ex.date >= post_a) & (ex.date < post_b)].domain.value_counts() / 3
        for _, members in MINISTRY_BLOCS:
            for dom, _label in members:
                p = float(pre.get(dom, 0.0))
                rows.append({
                    "rupture": key, "category": dom, "pre_rate": p,
                    "index": (float(post.get(dom, 0.0)) / p) / whole
                             if p >= min_pre else np.nan,
                })
    return pd.DataFrame(rows)


def fig_ministries() -> None:
    table = ministry_index()
    order, labels, rules = [], [], []
    for n_bloc, (bloc, members) in enumerate(MINISTRY_BLOCS):
        if n_bloc:               # a blank row carries the heading clear of the
            order.append(None)   # ministry above and below it
            labels.append("")
        rules.append((len(order), bloc))
        for dom, label in members:
            order.append(dom)
            labels.append(label)

    fig, ax = plt.subplots(figsize=(9.8, 7.2))
    fig.subplots_adjust(top=0.81, left=0.30, bottom=0.13)
    _dot_panel(ax, table, order, labels)
    ax.set_xlabel("churn relative to the state apparatus as a whole  (log scale)",
                  labelpad=18)

    # Bloc headings sit in the left margin, above the first ministry of each
    # bloc, with a rule across the panel to separate one from the next.
    n = len(order)
    for start, bloc in rules:
        y = n - 1 - start
        if start:
            ax.axhline(y + 1.0, color=RULE, lw=0.9, zorder=1)
        ax.annotate(bloc.upper(), xy=(-0.285, y + 0.72),
                    xycoords=("axes fraction", "data"),
                    fontsize=7.0, color=MUTED, fontweight="bold",
                    ha="left", va="center")
    ax.legend(handles=_rupture_handles(), loc="lower center",
              bbox_to_anchor=(0.5, 1.02), ncol=3)

    headline(
        fig,
        "The revolution fell on the courts and the treasury; 2021 fell on the interior ministry",
        "Appointments in the three years after each rupture against the four years "
        "before, divided by the same ratio for the apparatus as a whole, by policy "
        "domain. A point to the right of the line marks a ministry reshaped harder "
        "than the rest of the state; to the left, one left comparatively alone.",
    )
    save(fig, "fig15_ministry_by_ministry",
         SOURCE + "  Merged ministries are counted toward each domain they merge, "
                  "because the portfolio key follows the ministry's name and would "
                  "otherwise break at every rename: read literally, the interior "
                  "ministry makes 1.5 appointments a year before 2011 and 70 "
                  "before 2021, an artefact of its having been the ministry of the "
                  "Interior and Local Development until 2011. Domains with fewer "
                  "than 12 appointments a year before a rupture are not plotted "
                  "for it; defence, trade and women's affairs fall below that "
                  "throughout. Governorates and municipalities are the interior "
                  "ministry's field administration but are filed under their own "
                  "form, not its portfolio, so this understates its reach.")


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
    fig_renewal()
    print("done")
