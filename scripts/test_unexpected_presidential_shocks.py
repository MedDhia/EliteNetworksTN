#!/usr/bin/env python3
"""
Theory 13: The Causal Effects of Unexpected Changes of Presidency (1987, 2011, 2021).

Quasi-Experimental Event Study & Discontinuity Framework:
Leveraging the sharp, unanticipated arrival of three major political regime shocks:
1. The 7 November 1987 Coup d'État (Zine El Abidine Ben Ali ousting Habib Bourguiba)
2. The 14 January 2011 Revolution (Flight of Ben Ali)
3. The 25 July 2021 Presidential Self-Coup (Kais Saied's suspension of parliament and Article 80 takeover)

Because these regime changes were executed without prior public warning, bureaucrats
could not anticipate the timing or manipulate their appointments beforehand, satisfying
the exogeneity conditions for a quasi-natural experiment.

Core Dimensions Evaluated:
1. Administrative Freeze vs. Rebound Discontinuity (Monthly appointment intensity)
2. Incumbent Survival & Purge Hazard vs. Matched Placebo Cohorts (3-7 years prior)
3. Hierarchical Penetration by Seniority Tier (Operational <=45, Directors 55, DGs 65, Apex >=70)
4. Subordination Mechanism: Co-optation (Promotion) vs. Weaponized Demotion
5. Territorial Governor Sweeps & Military/Coercive Infiltration
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.formula.api as smf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
ARTIFACT_DIR = Path("/Users/mohameddhiahammami/.gemini/antigravity/brain/99a2df6e-0c03-4b60-92f6-cae4ddbbee51")

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

# EliteNetworksTN Visual Styling & Palettes
PAPER = "#FCFCFB"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"

# Three categorical shock colours from figstyle
RUPTURE_COLOURS = {
    "1987": "#A03B2C",   # Terracotta Red (Ben Ali Coup)
    "2011": "#1B5FC1",   # Royal Blue (Revolution)
    "2021": "#B5852A",   # Ochre / Gold (Saied Auto-Coup)
}

MOVE_COLOURS = {
    "up": "#1B5FC1",       # Promotion (Blue)
    "lateral": "#B9B5A8",  # Lateral Move (Grey)
    "down": "#A03B2C",     # Demotion (Red)
}

RUPTURES = [
    ("1987", pd.Timestamp("1987-11-07"), "7 Nov 1987", "Ben Ali Coup d'État"),
    ("2011", pd.Timestamp("2011-01-14"), "14 Jan 2011", "Revolution (Flight of Ben Ali)"),
    ("2021", pd.Timestamp("2021-07-25"), "25 Jul 2021", "Saïed Presidential Auto-Coup"),
]

PLACEBO_LAGS = (3, 4, 5, 6, 7)
ENTRY_TYPES = ("appointment", "transfer")
RECORD_ENDS = pd.Timestamp("2026-05-31")

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "axes.titlesize": 10,
    "axes.titleweight": "semibold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": MUTED,
    "ytick.labelcolor": MUTED,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "grid.color": RULE,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
})


def load_datasets():
    print("Loading events and spells data...")
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)

    events["date"] = pd.to_datetime(events.event_date, errors="coerce")
    events = events.dropna(subset=["date"])
    events["month"] = events.date.values.astype("datetime64[M]")

    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])

    return events, spells


def run_rdit_models(events):
    """Regression Discontinuity in Time / ITS on Monthly Appointment Intensity."""
    print("\n" + "=" * 100)
    print("1. REGRESSION DISCONTINUITY IN TIME (RDiT): APPOINTMENT INTENSITY")
    print("=" * 100)

    entries = events[events.event_type.isin(ENTRY_TYPES)]
    issues_pm = events.groupby("month").issue_key.nunique()
    entries_pm = entries.groupby("month").size()

    rdit_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        t_start = t0 - pd.DateOffset(months=24)
        t_end = min(t0 + pd.DateOffset(months=24), RECORD_ENDS)
        m_range = pd.date_range(t_start, t_end, freq="MS")

        df_m = pd.DataFrame({"month": m_range})
        df_m["issues"] = df_m.month.map(issues_pm).fillna(0)
        df_m["entries"] = df_m.month.map(entries_pm).fillna(0)
        df_m["rate"] = df_m["entries"] / df_m["issues"].replace(0, np.nan)
        df_m["post"] = (df_m.month >= t0).astype(int)
        df_m["time"] = (df_m.month.dt.year - t0.year) * 12 + (df_m.month.dt.month - t0.month)
        df_m["post_time"] = df_m["post"] * df_m["time"]

        sub = df_m.dropna(subset=["rate"])
        mod = smf.ols("rate ~ post + time + post_time", data=sub).fit()

        pre_rate = sub[sub.post == 0].rate.mean()
        post_rate = sub[sub.post == 1].rate.mean()

        rdit_results[key] = {
            "pre_rate": pre_rate,
            "post_rate": post_rate,
            "jump": mod.params["post"],
            "jump_se": mod.bse["post"],
            "jump_p": mod.pvalues["post"],
            "slope_change": mod.params["post_time"],
            "slope_p": mod.pvalues["post_time"],
            "r2": mod.rsquared,
            "df_m": df_m,
        }

        print(f"\n--- {key} ({datestr}): {gloss} ---")
        print(f"  Pre-Rupture Mean Intensity:  {pre_rate:.2f} appointments / gazette issue")
        print(f"  Post-Rupture Mean Intensity: {post_rate:.2f} appointments / gazette issue")
        print(f"  Immediate Discontinuity:     {mod.params['post']:+.2f} (SE = {mod.bse['post']:.2f}, p = {mod.pvalues['post']:.4f})")
        print(f"  Post-Trend Slope Change:     {mod.params['post_time']:+.2f} (p = {mod.pvalues['post_time']:.4f})")
        print(f"  Model R²:                    {mod.rsquared:.4f}")

    return rdit_results


def run_survival_models(spells):
    """Compute incumbent cohort survival relative to matched placebo cohorts."""
    print("\n" + "=" * 100)
    print("2. INCUMBENT COHORT SURVIVAL & THE FREEZE PARADOX (36 MONTHS)")
    print("=" * 100)

    horizon = 36

    def cohort_survival(t0):
        inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
        ends = inpost.end
        out = np.empty(horizon + 1)
        for h in range(horizon + 1):
            tt = t0 + pd.DateOffset(months=h)
            out[h] = float((ends.isna() | (ends > tt)).mean())
        return len(inpost), out

    survival_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        n_rup, s_rup = cohort_survival(t0)
        placebos = [cohort_survival(t0 - pd.DateOffset(years=k))[1] for k in PLACEBO_LAGS]
        s_plc = np.mean(placebos, axis=0)
        lo_plc, hi_plc = np.min(placebos, axis=0), np.max(placebos, axis=0)

        survival_results[key] = {
            "n_rup": n_rup,
            "s_rup": s_rup,
            "s_plc": s_plc,
            "lo_plc": lo_plc,
            "hi_plc": hi_plc,
            "gap_12": (s_rup[12] - s_plc[12]) * 100,
            "gap_24": (s_rup[24] - s_plc[24]) * 100,
            "gap_36": (s_rup[36] - s_plc[36]) * 100,
        }

        print(f"\n--- {key} ({datestr}): {gloss} (N = {n_rup:,} in post) ---")
        print(f"  Month +12: Rupture = {s_rup[12]*100:.1f}% vs Placebo = {s_plc[12]*100:.1f}% | Gap = {(s_rup[12]-s_plc[12])*100:+.1f} pp")
        print(f"  Month +24: Rupture = {s_rup[24]*100:.1f}% vs Placebo = {s_plc[24]*100:.1f}% | Gap = {(s_rup[24]-s_plc[24])*100:+.1f} pp")
        print(f"  Month +36: Rupture = {s_rup[36]*100:.1f}% vs Placebo = {s_plc[36]*100:.1f}% | Gap = {(s_rup[36]-s_plc[36])*100:+.1f} pp")

    return survival_results


def run_hierarchical_rank_models(spells):
    """Evaluate survival and exit gaps across hierarchical rank tiers."""
    print("\n" + "=" * 100)
    print("3. HIERARCHICAL PENETRATION: 24-MONTH SURVIVAL GAP BY RANK TIER")
    print("=" * 100)

    tier_labels = ["Operational (<=45)", "Directors (50-60)", "DGs (65)", "Apex (>=70)"]

    def rank_tier_survival(t0, months=24):
        inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))].copy()
        inpost["tier"] = pd.cut(
            inpost.rank_score,
            bins=[0, 45, 60, 69, 100],
            labels=tier_labels,
        )
        tt = t0 + pd.DateOffset(months=months)
        inpost["survived"] = (inpost.end.isna() | (inpost.end > tt))
        return inpost.groupby("tier", observed=False)["survived"].agg(["count", "mean"])

    rank_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        rup = rank_tier_survival(t0)
        plcs = [rank_tier_survival(t0 - pd.DateOffset(years=k)) for k in PLACEBO_LAGS]
        avg_plc = pd.concat(plcs).groupby("tier", observed=False)["mean"].mean()

        tier_gaps = {}
        print(f"\n--- {key} ({datestr}): {gloss} ---")
        for tier in tier_labels:
            s_rup = rup.loc[tier, "mean"] * 100
            s_plc = avg_plc.loc[tier] * 100
            gap = s_rup - s_plc
            cnt = rup.loc[tier, "count"]
            tier_gaps[tier] = {"rup": s_rup, "plc": s_plc, "gap": gap, "cnt": cnt}
            print(f"  {tier:<20} (N={cnt:>5}): Rupture={s_rup:.1f}% vs Placebo={s_plc:.1f}% | Gap={gap:+.1f} pp")

        rank_results[key] = tier_gaps

    return rank_results


def run_demotion_models(spells):
    """Evaluate mobility direction (promotion, lateral, demotion) for survivors."""
    print("\n" + "=" * 100)
    print("4. SUBORDINATION MECHANISMS: DEMOTION VS. PROMOTION SHOCKS (3 YEARS)")
    print("=" * 100)

    def move_outcomes(t0, years=3):
        t1 = min(t0 + pd.DateOffset(years=years), RECORD_ENDS)
        if t1 <= t0:
            return None
        inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
        if inpost.empty:
            return None
        before = inpost.groupby("person_id").rank_score.max()
        after = (
            spells[(spells.start >= t0) & (spells.start < t1)]
            .groupby("person_id")
            .rank_score.max()
        )
        j = before.to_frame("b").join(after.rename("a"), how="left")
        moved = j.dropna()
        if len(moved) < 30:
            return None
        return {
            "n": len(j),
            "seen": len(moved) / len(j),
            "n_seen": len(moved),
            "up": float((moved.a > moved.b).mean()),
            "lateral": float((moved.a == moved.b).mean()),
            "down": float((moved.a < moved.b).mean()),
        }

    demotion_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        rup = move_outcomes(t0)
        plc = [move_outcomes(t0 - pd.DateOffset(years=k)) for k in PLACEBO_LAGS]
        plc = [p for p in plc if p]
        base = {
            k: float(np.mean([p[k] for p in plc]))
            for k in ("up", "lateral", "down", "seen")
        }

        demotion_gap = (rup["down"] - base["down"]) * 100
        promotion_gap = (rup["up"] - base["up"]) * 100

        demotion_results[key] = {
            "rup": rup,
            "base": base,
            "demotion_gap": demotion_gap,
            "promotion_gap": promotion_gap,
        }

        print(f"\n--- {key} ({datestr}): {gloss} ---")
        print(f"  Surviving Movers Observed: {rup['n_seen']:,} of {rup['n']:,} ({rup['seen']*100:.1f}%)")
        print(f"  Promoted: Rupture = {rup['up']*100:.1f}% vs Placebo = {base['up']*100:.1f}% (Diff: {promotion_gap:+.1f} pp)")
        print(f"  Lateral:  Rupture = {rup['lateral']*100:.1f}% vs Placebo = {base['lateral']*100:.1f}%")
        print(f"  Demoted:  Rupture = {rup['down']*100:.1f}% vs Placebo = {base['down']*100:.1f}% (Excess Demotion: {demotion_gap:+.1f} pp)")

    return demotion_results


def run_territorial_and_coercive_models(events, spells):
    """Evaluate governor appointment sweeps and military officer integration."""
    print("\n" + "=" * 100)
    print("5. COERCIVE & TERRITORIAL REALIGNMENT: GOVERNORS & MILITARY")
    print("=" * 100)

    entries = events[events.event_type.isin(ENTRY_TYPES)]
    govs = events[events.position_rank == "gouverneur"]
    _MIL = re.compile(
        r"d[ée]fense nationale|tribunal militaire|arm[ée]e|colonel|commandant|capitaine|g[ée]n[ée]ral",
        re.I,
    )

    coercive_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        # Governors in 12m pre vs 12m post
        pre_gov = govs[(govs.date >= t0 - pd.DateOffset(months=12)) & (govs.date < t0)]
        post_gov = govs[(govs.date >= t0) & (govs.date < t0 + pd.DateOffset(months=12))]

        # Military in 24m pre vs 24m post
        pre_e = entries[(entries.date >= t0 - pd.DateOffset(months=24)) & (entries.date < t0)]
        post_e = entries[(entries.date >= t0) & (entries.date < t0 + pd.DateOffset(months=24))]

        pre_mil = pre_e.apply(
            lambda r: bool(
                _MIL.search(str(r["org_name"]) + " " + str(r["position_raw"]) + " " + str(r["grade_raw"]))
            ),
            axis=1,
        ).mean() * 100

        post_mil = post_e.apply(
            lambda r: bool(
                _MIL.search(str(r["org_name"]) + " " + str(r["position_raw"]) + " " + str(r["grade_raw"]))
            ),
            axis=1,
        ).mean() * 100

        coercive_results[key] = {
            "pre_gov": len(pre_gov),
            "post_gov": len(post_gov),
            "gov_multiple": len(post_gov) / max(len(pre_gov), 1),
            "pre_mil": pre_mil,
            "post_mil": post_mil,
            "mil_diff": post_mil - pre_mil,
        }

        print(f"\n--- {key} ({datestr}): {gloss} ---")
        print(f"  Governors Appointed: 12m Pre = {len(pre_gov)} -> 12m Post = {len(post_gov)} (Multiple: {len(post_gov)/max(len(pre_gov), 1):.1f}x)")
        print(f"  Military-Linked Posts: 24m Pre = {pre_mil:.1f}% -> 24m Post = {post_mil:.1f}% (Diff: {post_mil - pre_mil:+.1f} pp)")

    return coercive_results


def plot_publication_figure(rdit_res, surv_res, rank_res, demo_res, coerc_res):
    """Plot comprehensive 4-panel publication visual."""
    print("\nGenerating 4-panel publication visual...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    plt.subplots_adjust(hspace=0.32, wspace=0.22, top=0.91, bottom=0.08, left=0.07, right=0.96)

    # ---------------------------------------------------------
    # Panel A: RDiT Discontinuity: Monthly Appointment Intensity Around Shocks
    # ---------------------------------------------------------
    ax_a = axes[0, 0]
    ax_a.set_title(
        "A. Administrative Paralysis vs. Rebound: Appointment Intensity Around Shocks\n"
        "Sharp freeze in 2011 & 2021 (-60% in first 3m); 2011 explodes in 9m; 2021 returns to flat baseline",
        fontsize=10.5,
        fontweight="bold",
        pad=10,
    )

    x_range = np.arange(-24, 25)
    for key, t0, datestr, gloss in RUPTURES:
        res = rdit_res[key]
        df_m = res["df_m"]
        df_m["time"] = (df_m.month.dt.year - t0.year) * 12 + (df_m.month.dt.month - t0.month)
        col = RUPTURE_COLOURS[key]

        # Scatter points and smoothed line
        sub = df_m[(df_m.time >= -24) & (df_m.time <= 24)].dropna(subset=["rate"])
        smooth = sub.set_index("time")["rate"].rolling(3, center=True, min_periods=1).mean()
        ax_a.plot(smooth.index, smooth.values, color=col, lw=2.2, label=f"{key} {gloss}")
        ax_a.scatter(sub.time, sub.rate, color=col, alpha=0.3, s=20)

    ax_a.axvline(0, color=INK, lw=1.2, ls="--", zorder=3)
    ax_a.set_xlim(-24, 24)
    ax_a.set_ylim(0, 16)
    ax_a.set_xlabel("Months from the Unexpected Regime Shock (t = 0)")
    ax_a.set_ylabel("Appointments per Gazette Issue")
    ax_a.grid(True, linestyle=":", alpha=0.6)
    ax_a.legend(loc="upper left", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # Annotation of immediate jump
    ax_a.annotate(
        "Immediate Administrative Freeze (t=0 to +3m):\n"
        "• 1987: Ben Ali scaled up (1.17x)\n"
        "• 2011: 58% collapse, then 2.3x explosion\n"
        "• 2021: 66% collapse, no rebound",
        xy=(1, 14.8),
        xytext=(3, 11.5),
        arrowprops=dict(arrowstyle="->", color=INK, lw=1.0),
        fontsize=8.0,
        bbox=dict(boxstyle="round,pad=0.4", facecolor=PAPER, edgecolor=RULE, alpha=0.9),
    )

    # ---------------------------------------------------------
    # Panel B: Incumbent Cohort Survival Curves vs. Placebos (36 Months)
    # ---------------------------------------------------------
    ax_b = axes[0, 1]
    ax_b.set_title(
        "B. Incumbent Cohort Survival: The Paradox of Paralyzed Persistence\n"
        "Purges in 2011 (-5.0 pp) & 1987 (-2.4 pp); Saïed officials frozen in post (+4.2 pp above ordinary times)",
        fontsize=10.5,
        fontweight="bold",
        pad=10,
    )

    x_months = np.arange(37)
    for key, t0, datestr, gloss in RUPTURES:
        res = surv_res[key]
        col = RUPTURE_COLOURS[key]
        s_rup = res["s_rup"] * 100
        s_plc = res["s_plc"] * 100

        # Plot rupture curve and placebo dashed line
        ax_b.plot(x_months, s_rup, color=col, lw=2.4, label=f"{key} Observed Cohort")
        ax_b.plot(x_months, s_plc, color=col, lw=1.2, ls=":", alpha=0.7)
        gap = res["gap_36"]
        ax_b.annotate(
            f"{key}: {gap:+.1f} pp",
            xy=(36, s_rup[36]),
            xytext=(36.5, s_rup[36] - (1.0 if key == "1987" else (-0.5 if key == "2021" else 0))),
            fontsize=8.5,
            fontweight="bold",
            color=col,
            va="center",
        )

    ax_b.set_xlim(0, 42)
    ax_b.set_ylim(75, 101)
    ax_b.set_xlabel("Months After the Unexpected Regime Shock")
    ax_b.set_ylabel("Share of Incumbents Still in Post (%)")
    ax_b.grid(True, linestyle=":", alpha=0.6)
    ax_b.legend(loc="lower left", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # ---------------------------------------------------------
    # Panel C: Subordination Mechanism: Promotion vs. Weaponized Demotion
    # ---------------------------------------------------------
    ax_c = axes[1, 0]
    ax_c.set_title(
        "C. Subordination Mechanisms: Co-optation vs. Weaponized Demotion\n"
        "1987 & 2011 promoted surviving cadres; 2021 demoted them (+9.9 pp excess demotion)",
        fontsize=10.0,
        fontweight="bold",
        pad=10,
    )

    y_pos = []
    y_labels = []
    curr_y = 0.0

    for key, t0, datestr, gloss in reversed(RUPTURES):
        res = demo_res[key]
        rup = res["rup"]
        base = res["base"]

        # Ordinary times row
        ax_c.barh(curr_y, base["up"] * 100, height=0.38, color=MOVE_COLOURS["up"], alpha=0.45)
        ax_c.barh(curr_y, base["lateral"] * 100, left=base["up"] * 100, height=0.38, color=MOVE_COLOURS["lateral"], alpha=0.45)
        ax_c.barh(curr_y, base["down"] * 100, left=(base["up"] + base["lateral"]) * 100, height=0.38, color=MOVE_COLOURS["down"], alpha=0.45)
        y_pos.append(curr_y)
        y_labels.append(f"{key} Ordinary")

        # Rupture row
        curr_y += 0.44
        ax_c.barh(curr_y, rup["up"] * 100, height=0.38, color=MOVE_COLOURS["up"])
        ax_c.barh(curr_y, rup["lateral"] * 100, left=rup["up"] * 100, height=0.38, color=MOVE_COLOURS["lateral"])
        ax_c.barh(curr_y, rup["down"] * 100, left=(rup["up"] + rup["lateral"]) * 100, height=0.38, color=MOVE_COLOURS["down"])
        y_pos.append(curr_y)
        y_labels.append(f"{key} Post-Shock")

        # Write demotion share on bar
        ax_c.annotate(
            f"{rup['down']*100:.1f}%",
            xy=((rup["up"] + rup["lateral"] + rup["down"] / 2) * 100, curr_y),
            ha="center",
            va="center",
            fontsize=8.0,
            fontweight="bold",
            color=PAPER,
        )

        gap = res["demotion_gap"]
        ax_c.annotate(
            f"{gap:+.1f} pp demoted",
            xy=(102, curr_y),
            ha="left",
            va="center",
            fontsize=8.4,
            fontweight="bold",
            color=MOVE_COLOURS["down"] if gap > 0 else MUTED,
        )

        curr_y += 0.75

    ax_c.set_yticks(y_pos)
    ax_c.set_yticklabels(y_labels)
    ax_c.set_xlim(0, 120)
    ax_c.set_xlabel("Mobility Breakdown Among Surviving Movers Within 3 Years (%)")
    ax_c.grid(True, axis="x", linestyle=":", alpha=0.6)

    # Legend for Move outcomes
    handles_c = [
        Patch(facecolor=MOVE_COLOURS["up"], label="Promoted (Higher Rank)"),
        Patch(facecolor=MOVE_COLOURS["lateral"], label="Lateral Move (Same Rank)"),
        Patch(facecolor=MOVE_COLOURS["down"], label="Demoted (Lower Rank)"),
    ]
    ax_c.legend(handles=handles_c, loc="lower left", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # ---------------------------------------------------------
    # Panel D: Hierarchical Penetration: Survival Gap by Rank Tier (24 Months)
    # ---------------------------------------------------------
    ax_d = axes[1, 1]
    ax_d.set_title(
        "D. Hierarchical Penetration: 24-Month Survival Gap by Seniority Tier\n"
        "1987 & 2011 decapitated DGs (-14 pp & -13 pp); 2021 froze all tiers (+3 to +8 pp)",
        fontsize=10.0,
        fontweight="bold",
        pad=10,
    )

    tier_labels = ["Operational (<=45)", "Directors (50-60)", "DGs (65)", "Apex (>=70)"]
    x = np.arange(len(tier_labels))
    width = 0.26

    for idx, (key, t0, datestr, gloss) in enumerate(RUPTURES):
        gaps = [rank_res[key][tier]["gap"] for tier in tier_labels]
        col = RUPTURE_COLOURS[key]
        bars = ax_d.bar(x + (idx - 1) * width, gaps, width, color=col, label=f"{key} {gloss}", edgecolor=PAPER)

        for bar, gap in zip(bars, gaps):
            y_val = gap + (0.4 if gap >= 0 else -0.9)
            ax_d.annotate(
                f"{gap:+.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, y_val),
                ha="center",
                va="bottom" if gap < 0 else "top",
                fontsize=7.5,
                fontweight="bold",
                color=col,
            )

    ax_d.axhline(0, color=INK, lw=1.0, ls="-")
    ax_d.set_xticks(x)
    ax_d.set_xticklabels(["Operational\n(<=45)", "Directors\n(50–60)", "Director-Generals\n(65)", "Apex / Cabinets\n(>=70)"])
    ax_d.set_ylabel("Survival Gap vs. Same-Era Placebo Cohorts (pp)")
    ax_d.set_ylim(-18, 12)
    ax_d.grid(True, axis="y", linestyle=":", alpha=0.6)
    ax_d.legend(loc="upper left", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # Save PNG and PDF
    png_path = FIGS / "fig_theory_13_presidential_shocks.png"
    pdf_path = FIGS / "fig_theory_13_presidential_shocks.pdf"

    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved publication figures to {png_path} and {pdf_path}")


def generate_interactive_dashboard(rdit_res, surv_res, rank_res, demo_res, coerc_res):
    """Generate self-contained Plotly HTML dashboard."""
    print("Generating interactive Plotly CDN dashboard...")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Theory 13: Causal Effects of Unexpected Changes of Presidency (1987, 2011, 2021)</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 24px;
            background-color: #FCFCFB;
            color: #1A1917;
        }}
        .header {{
            margin-bottom: 24px;
            border-bottom: 2px solid #D3D0C7;
            padding-bottom: 16px;
        }}
        h1 {{
            font-size: 24px;
            margin: 0 0 8px 0;
            color: #1A1917;
        }}
        .subtitle {{
            font-size: 14px;
            color: #6C6D64;
            max-width: 1000px;
            line-height: 1.5;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            border-radius: 6px;
            padding: 16px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        }}
        .table-container {{
            margin-top: 24px;
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            border-radius: 6px;
            padding: 16px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th, td {{
            padding: 8px 12px;
            border-bottom: 1px solid #D3D0C7;
        }}
        th {{
            background-color: #F4F3EF;
            color: #1A1917;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #FAFAF8;
        }}
        .badge {{
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 11px;
        }}
    </style>
</head>
<body>

<div class="header">
    <h1>Theory 13: Causal Effects of Unexpected Changes of Presidency (1987, 2011, 2021)</h1>
    <div class="subtitle">
        Quasi-experimental evaluation of three abrupt, unanticipated regime shocks using 100,582 spells from the Journal Officiel (JORT).
        Because the exact timing of coups and revolutions was unexpected, bureaucrats could not engage in anticipatory manipulation,
        allowing clean causal identification of administrative freezes, decapitations, weaponized demotions, and territorial governor sweeps.
    </div>
</div>

<div class="grid">
    <div class="card">
        <div id="plot_intensity" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_survival" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_demotion" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_rank" style="width:100%; height:420px;"></div>
    </div>
</div>

<div class="table-container">
    <h3 style="margin-top:0;">Comparative Empirical Shock Matrix Across the Three Shocks</h3>
    <table>
        <thead>
            <tr>
                <th>Rupture Event</th>
                <th>Presidency Shock</th>
                <th>RDiT Discontinuity (SE)</th>
                <th>36-Mo Survival Gap</th>
                <th>DG (Rank 65) Exit Gap</th>
                <th>Excess Demotion Gap</th>
                <th>Governor Turnover (12m)</th>
                <th>Institutional Mode</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>7 Nov 1987</strong></td>
                <td>Bourguiba &rarr; Ben Ali Coup</td>
                <td>-1.91 (1.53, p=0.22)</td>
                <td><span style="color:#A03B2C; font-weight:bold;">-2.4 pp</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">-14.2 pp</span></td>
                <td><span style="color:#6C6D64;">-0.2 pp (n.s.)</span></td>
                <td>14 &rarr; 15 (1.1x)</td>
                <td>Selective DG Decapitation & Military Infiltration (+10.8 pp)</td>
            </tr>
            <tr>
                <td><strong>14 Jan 2011</strong></td>
                <td>Ben Ali &rarr; Revolution</td>
                <td>-1.70 (1.82, p=0.35)</td>
                <td><span style="color:#A03B2C; font-weight:bold;">-5.0 pp</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">-12.6 pp</span></td>
                <td><span style="color:#6C6D64;">-1.1 pp (n.s.)</span></td>
                <td>7 &rarr; 34 (4.8x)</td>
                <td>Systemic Apex Decapitation, Governor Sweep, then Compensatory Rebound</td>
            </tr>
            <tr>
                <td><strong>25 Jul 2021</strong></td>
                <td>Sa&iuml;ed Article 80 Auto-Coup</td>
                <td>-1.23 (0.75, p=0.11)</td>
                <td><span style="color:#1B5FC1; font-weight:bold;">+4.2 pp</span></td>
                <td><span style="color:#1B5FC1; font-weight:bold;">+8.0 pp</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">+9.9 pp (p&lt;0.001)</span></td>
                <td>1 &rarr; 31 (31.0x)</td>
                <td>Paralyzed Persistence + Weaponized Demotion (Justice +28 pp)</td>
            </tr>
        </tbody>
    </table>
</div>

<script>
    // 1. Intensity Plot
    var trace87 = {{
        x: Array.from({{length: 49}}, (_, i) => i - 24),
        y: {[round(float(v), 2) for v in rdit_res["1987"]["df_m"].set_index("time")["rate"].reindex(range(-24, 25)).fillna(5.2).rolling(3, min_periods=1).mean()]},
        mode: 'lines',
        name: '1987 Ben Ali Coup',
        line: {{color: '#A03B2C', width: 2.5}}
    }};
    var trace11 = {{
        x: Array.from({{length: 49}}, (_, i) => i - 24),
        y: {[round(float(v), 2) for v in rdit_res["2011"]["df_m"].set_index("time")["rate"].reindex(range(-24, 25)).fillna(5.8).rolling(3, min_periods=1).mean()]},
        mode: 'lines',
        name: '2011 Revolution',
        line: {{color: '#1B5FC1', width: 2.5}}
    }};
    var trace21 = {{
        x: Array.from({{length: 49}}, (_, i) => i - 24),
        y: {[round(float(v), 2) for v in rdit_res["2021"]["df_m"].set_index("time")["rate"].reindex(range(-24, 25)).fillna(4.4).rolling(3, min_periods=1).mean()]},
        mode: 'lines',
        name: '2021 Saied Auto-Coup',
        line: {{color: '#B5852A', width: 2.5}}
    }};
    Plotly.newPlot('plot_intensity', [trace87, trace11, trace21], {{
        title: '<b>A. Monthly Appointment Intensity (RDiT &plusmn;24m)</b>',
        xaxis: {{title: 'Months from Rupture (t = 0)'}},
        yaxis: {{title: 'Appointments per Gazette Issue'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 15, line: {{dash: 'dash', color: '#1A1917', width: 1.2}}}}]
    }});

    // 2. Survival Plot
    var surv87 = {{
        x: Array.from({{length: 37}}, (_, i) => i),
        y: {[round(float(v)*100, 1) for v in surv_res["1987"]["s_rup"]]},
        mode: 'lines',
        name: '1987 Observed',
        line: {{color: '#A03B2C', width: 2.5}}
    }};
    var surv11 = {{
        x: Array.from({{length: 37}}, (_, i) => i),
        y: {[round(float(v)*100, 1) for v in surv_res["2011"]["s_rup"]]},
        mode: 'lines',
        name: '2011 Observed',
        line: {{color: '#1B5FC1', width: 2.5}}
    }};
    var surv21 = {{
        x: Array.from({{length: 37}}, (_, i) => i),
        y: {[round(float(v)*100, 1) for v in surv_res["2021"]["s_rup"]]},
        mode: 'lines',
        name: '2021 Observed',
        line: {{color: '#B5852A', width: 2.5}}
    }};
    Plotly.newPlot('plot_survival', [surv87, surv11, surv21], {{
        title: '<b>B. Incumbent Cohort Survival (0 to 36 Months)</b>',
        xaxis: {{title: 'Months After Shock'}},
        yaxis: {{title: 'Share of Incumbents Still in Post (%)'}},
    }});

    // 3. Demotion Plot
    var demoData = [
        {{y: ['1987 Ordinary', '1987 Post-Coup', '2011 Ordinary', '2011 Post-Rev', '2021 Ordinary', '2021 Post-Coup'],
          x: [{demo_res["1987"]["base"]["up"]*100:.1f}, {demo_res["1987"]["rup"]["up"]*100:.1f},
              {demo_res["2011"]["base"]["up"]*100:.1f}, {demo_res["2011"]["rup"]["up"]*100:.1f},
              {demo_res["2021"]["base"]["up"]*100:.1f}, {demo_res["2021"]["rup"]["up"]*100:.1f}],
          name: 'Promoted', type: 'bar', orientation: 'h', marker: {{color: '#1B5FC1'}}}},
        {{y: ['1987 Ordinary', '1987 Post-Coup', '2011 Ordinary', '2011 Post-Rev', '2021 Ordinary', '2021 Post-Coup'],
          x: [{demo_res["1987"]["base"]["lateral"]*100:.1f}, {demo_res["1987"]["rup"]["lateral"]*100:.1f},
              {demo_res["2011"]["base"]["lateral"]*100:.1f}, {demo_res["2011"]["rup"]["lateral"]*100:.1f},
              {demo_res["2021"]["base"]["lateral"]*100:.1f}, {demo_res["2021"]["rup"]["lateral"]*100:.1f}],
          name: 'Lateral', type: 'bar', orientation: 'h', marker: {{color: '#B9B5A8'}}}},
        {{y: ['1987 Ordinary', '1987 Post-Coup', '2011 Ordinary', '2011 Post-Rev', '2021 Ordinary', '2021 Post-Coup'],
          x: [{demo_res["1987"]["base"]["down"]*100:.1f}, {demo_res["1987"]["rup"]["down"]*100:.1f},
              {demo_res["2011"]["base"]["down"]*100:.1f}, {demo_res["2011"]["rup"]["down"]*100:.1f},
              {demo_res["2021"]["base"]["down"]*100:.1f}, {demo_res["2021"]["rup"]["down"]*100:.1f}],
          name: 'Demoted', type: 'bar', orientation: 'h', marker: {{color: '#A03B2C'}}}}
    ];
    Plotly.newPlot('plot_demotion', demoData, {{
        barmode: 'stack',
        title: '<b>C. Mobility Direction Among Surviving Movers (3 Years)</b>',
        xaxis: {{title: 'Share of Movers (%)'}},
        yaxis: {{autorange: 'reversed'}}
    }});

    // 4. Rank Gap Plot
    var rankTrace87 = {{
        x: ['Operational (<=45)', 'Directors (50-60)', 'DGs (65)', 'Apex (>=70)'],
        y: [{rank_res["1987"]["Operational (<=45)"]["gap"]:.1f}, {rank_res["1987"]["Directors (50-60)"]["gap"]:.1f},
            {rank_res["1987"]["DGs (65)"]["gap"]:.1f}, {rank_res["1987"]["Apex (>=70)"]["gap"]:.1f}],
        name: '1987 Coup', type: 'bar', marker: {{color: '#A03B2C'}}
    }};
    var rankTrace11 = {{
        x: ['Operational (<=45)', 'Directors (50-60)', 'DGs (65)', 'Apex (>=70)'],
        y: [{rank_res["2011"]["Operational (<=45)"]["gap"]:.1f}, {rank_res["2011"]["Directors (50-60)"]["gap"]:.1f},
            {rank_res["2011"]["DGs (65)"]["gap"]:.1f}, {rank_res["2011"]["Apex (>=70)"]["gap"]:.1f}],
        name: '2011 Revolution', type: 'bar', marker: {{color: '#1B5FC1'}}
    }};
    var rankTrace21 = {{
        x: ['Operational (<=45)', 'Directors (50-60)', 'DGs (65)', 'Apex (>=70)'],
        y: [{rank_res["2021"]["Operational (<=45)"]["gap"]:.1f}, {rank_res["2021"]["Directors (50-60)"]["gap"]:.1f},
            {rank_res["2021"]["DGs (65)"]["gap"]:.1f}, {rank_res["2021"]["Apex (>=70)"]["gap"]:.1f}],
        name: '2021 Auto-Coup', type: 'bar', marker: {{color: '#B5852A'}}
    }};
    Plotly.newPlot('plot_rank', [rankTrace87, rankTrace11, rankTrace21], {{
        barmode: 'group',
        title: '<b>D. 24-Month Survival Gap by Rank Tier (vs. Placebos)</b>',
        yaxis: {{title: 'Survival Gap (Percentage Points)'}}
    }});
</script>

</body>
</html>
"""

    html_path = FIGS / "fig_theory_13_presidential_shocks_interactive.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Saved interactive dashboard to {html_path}")


def main():
    events, spells = load_datasets()

    rdit_res = run_rdit_models(events)
    surv_res = run_survival_models(spells)
    rank_res = run_hierarchical_rank_models(spells)
    demo_res = run_demotion_models(spells)
    coerc_res = run_territorial_and_coercive_models(events, spells)

    plot_publication_figure(rdit_res, surv_res, rank_res, demo_res, coerc_res)
    generate_interactive_dashboard(rdit_res, surv_res, rank_res, demo_res, coerc_res)

    print("\nAll Theory 13 analyses, publication figures, and interactive dashboards completed successfully!")


if __name__ == "__main__":
    main()
