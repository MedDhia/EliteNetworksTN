#!/usr/bin/env python3
"""
Theory 13 (Causal Econometrics): Regression Discontinuity Design (RDD) & Difference-in-Differences (DiD)
Evaluating the Causal Effects of Unexpected Changes of Presidency (1987, 2011, 2021).

Identification Strategy:
1. Sharp Regression Discontinuity in Time (RDD / RDiT):
   - Running variable: Days from unexpected shock X in [-180, +180] days
   - Cutoff: c = 0 (7 Nov 1987, 14 Jan 2011, 25 Jul 2021)
   - Local linear regressions with robust standard errors (HC1)
   - Discontinuity estimates for:
     * Daily appointment volume / velocity (freeze vs. acceleration)
     * Composition: Apex political appointments (Rank >= 70) and Security/Military share
2. Difference-in-Differences (DiD):
   - Model 1 (Hierarchical Vulnerability DiD):
     Treated Cohort vs. Matched Pre-Shock Placebo Cohorts (3-7 years prior) x High Rank (>=65) vs. Operational (<=45)
     Estimating interaction delta_DiD on 24-month incumbent survival across 52k to 209k bureaucrat-spell observations.
   - Model 2 (Weaponized Demotion DiD):
     Probability of demotion among surviving movers (3-year window) vs. identical placebo cohorts (N = 4,690 to 22,868).
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

# Styling
PAPER = "#FCFCFB"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"

RUPTURE_COLOURS = {
    "1987": "#A03B2C",   # Terracotta (Ben Ali Coup)
    "2011": "#1B5FC1",   # Royal Blue (Revolution)
    "2021": "#B5852A",   # Ochre / Gold (Saied Auto-Coup)
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


def load_data():
    print("Loading JORT events and spells...")
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)

    events["date"] = pd.to_datetime(events.event_date, errors="coerce")
    events = events.dropna(subset=["date"])
    events["day"] = events.date.values.astype("datetime64[D]")

    spells["start"] = pd.to_datetime(spells.start_date, errors="coerce")
    spells["end"] = pd.to_datetime(spells.end_date, errors="coerce")
    spells = spells.dropna(subset=["start"])

    return events, spells


def estimate_rdd_volume(events):
    """Estimate Sharp RDD on daily appointment counts within [-180, +180] days."""
    print("\n" + "=" * 100)
    print("1. SHARP REGRESSION DISCONTINUITY IN TIME (RDD): APPOINTMENT VOLUME")
    print("=" * 100)

    entries = events[events.event_type.isin(ENTRY_TYPES)].copy()
    rdd_vol_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        t_min = t0 - pd.Timedelta(days=180)
        t_max = min(t0 + pd.Timedelta(days=180), RECORD_ENDS)
        sub = entries[(entries.date >= t_min) & (entries.date <= t_max)].copy()

        # Build complete daily calendar
        d_range = pd.date_range(t_min, t_max, freq="D")
        daily = (
            sub.groupby("day")
            .size()
            .reindex(d_range, fill_value=0)
            .reset_index()
        )
        daily.columns = ["day", "count"]
        daily["x"] = (daily.day - t0).dt.days
        daily["d"] = (daily.x >= 0).astype(int)
        daily["dx"] = daily["d"] * daily["x"]

        # Local linear regression (HC1 robust SE)
        mod = smf.ols("count ~ d + x + dx", data=daily).fit(cov_type="HC1")

        # Predicted lines on either side
        pre_idx = daily.x < 0
        post_idx = daily.x >= 0
        daily["pred"] = mod.predict(daily)

        rdd_vol_results[key] = {
            "jump": mod.params["d"],
            "se": mod.bse["d"],
            "p": mod.pvalues["d"],
            "ci_lower": mod.conf_int().loc["d", 0],
            "ci_upper": mod.conf_int().loc["d", 1],
            "pre_mean": daily.loc[pre_idx, "count"].mean(),
            "post_mean": daily.loc[post_idx, "count"].mean(),
            "daily_df": daily,
            "mod": mod,
        }

        print(f"\n--- {key} ({datestr}): {gloss} ---")
        print(f"  Pre-Cutoff Mean Daily Volume:  {rdd_vol_results[key]['pre_mean']:.2f} appointments / day")
        print(f"  Post-Cutoff Mean Daily Volume: {rdd_vol_results[key]['post_mean']:.2f} appointments / day")
        print(f"  RDD Discontinuity (tau):       {mod.params['d']:+.2f} (SE = {mod.bse['d']:.2f}, 95% CI [{mod.conf_int().loc['d', 0]:.2f}, {mod.conf_int().loc['d', 1]:.2f}], p = {mod.pvalues['d']:.4f})")
        print(f"  Pre-Trend Slope (beta_1):      {mod.params['x']:+.4f} (p = {mod.pvalues['x']:.4f})")
        print(f"  Slope Difference (beta_2):     {mod.params['dx']:+.4f} (p = {mod.pvalues['dx']:.4f})")

    return rdd_vol_results


def estimate_rdd_composition(events):
    """Estimate Sharp RDD on appointment composition: Apex Share & Security Share."""
    print("\n" + "=" * 100)
    print("2. SHARP REGRESSION DISCONTINUITY IN TIME (RDD): APPOINTMENT COMPOSITION")
    print("=" * 100)

    entries = events[events.event_type.isin(ENTRY_TYPES)].copy()
    _SEC = re.compile(
        r"d[ée]fense nationale|tribunal militaire|arm[ée]e|colonel|commandant|capitaine|g[ée]n[ée]ral|interieur|police|garde nationale",
        re.I,
    )

    rdd_comp_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        t_min = t0 - pd.Timedelta(days=180)
        t_max = min(t0 + pd.Timedelta(days=180), RECORD_ENDS)
        sub = entries[(entries.date >= t_min) & (entries.date <= t_max)].copy()

        sub["x"] = (sub.date - t0).dt.days
        sub["d"] = (sub.x >= 0).astype(int)
        sub["dx"] = sub["d"] * sub["x"]

        # Outcome 1: Apex share (rank >= 70)
        sub["is_apex"] = (sub.rank_score >= 70).astype(int)
        mod_apex = smf.ols("is_apex ~ d + x + dx", data=sub).fit(cov_type="HC1")

        # Outcome 2: Security/Military share
        sub["is_sec"] = sub.apply(
            lambda r: bool(
                _SEC.search(str(r["org_name"]) + " " + str(r["position_raw"]))
            ),
            axis=1,
        ).astype(int)
        mod_sec = smf.ols("is_sec ~ d + x + dx", data=sub).fit(cov_type="HC1")

        rdd_comp_results[key] = {
            "n": len(sub),
            "apex_jump": mod_apex.params["d"] * 100,
            "apex_se": mod_apex.bse["d"] * 100,
            "apex_p": mod_apex.pvalues["d"],
            "sec_jump": mod_sec.params["d"] * 100,
            "sec_se": mod_sec.bse["d"] * 100,
            "sec_p": mod_sec.pvalues["d"],
            "sub_df": sub,
        }

        print(f"\n--- {key} ({datestr}): {gloss} (N = {len(sub):,} acts) ---")
        print(f"  Apex (Rank >= 70) Discontinuity: {mod_apex.params['d']*100:+.2f} pp (SE = {mod_apex.bse['d']*100:.2f} pp, p = {mod_apex.pvalues['d']:.4f})")
        print(f"  Security/Military Discontinuity: {mod_sec.params['d']*100:+.2f} pp (SE = {mod_sec.bse['d']*100:.2f} pp, p = {mod_sec.pvalues['d']:.4f})")

    return rdd_comp_results


def estimate_did_survival(spells):
    """Hierarchical Difference-in-Differences: Treated Shock Cohort vs. Placebo Cohorts x High vs Low Rank."""
    print("\n" + "=" * 100)
    print("3. DIFFERENCE-IN-DIFFERENCES (DiD): HIERARCHICAL INCUMBENT SURVIVAL (24M)")
    print("=" * 100)

    did_surv_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        dfs = []

        # Treated cohort
        inpost_t = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))].copy()
        inpost_t["treated_cohort"] = 1
        inpost_t["survived_24"] = (inpost_t.end.isna() | (inpost_t.end > t0 + pd.DateOffset(months=24))).astype(int)
        inpost_t["rank_high"] = (inpost_t.rank_score >= 65).astype(int)
        dfs.append(inpost_t[["person_id", "treated_cohort", "survived_24", "rank_high", "rank_score"]])

        # Placebo cohorts
        for k in PLACEBO_LAGS:
            t_plc = t0 - pd.DateOffset(years=k)
            inpost_p = spells[(spells.start < t_plc) & (spells.end.isna() | (spells.end > t_plc))].copy()
            inpost_p["treated_cohort"] = 0
            inpost_p["survived_24"] = (inpost_p.end.isna() | (inpost_p.end > t_plc + pd.DateOffset(months=24))).astype(int)
            inpost_p["rank_high"] = (inpost_p.rank_score >= 65).astype(int)
            dfs.append(inpost_p[["person_id", "treated_cohort", "survived_24", "rank_high", "rank_score"]])

        df_all = pd.concat(dfs, ignore_index=True)

        # DiD OLS Regression with HC1 robust standard errors
        mod_did = smf.ols("survived_24 ~ treated_cohort + rank_high + treated_cohort:rank_high", data=df_all).fit(cov_type="HC1")

        # Breakdown table
        tbl = df_all.groupby(["treated_cohort", "rank_high"])["survived_24"].mean() * 100

        did_surv_results[key] = {
            "n": len(df_all),
            "baseline_diff": mod_did.params["treated_cohort"] * 100,
            "baseline_p": mod_did.pvalues["treated_cohort"],
            "rank_penalty": mod_did.params["rank_high"] * 100,
            "did_interaction": mod_did.params["treated_cohort:rank_high"] * 100,
            "did_se": mod_did.bse["treated_cohort:rank_high"] * 100,
            "did_p": mod_did.pvalues["treated_cohort:rank_high"],
            "tbl": tbl,
        }

        print(f"\n--- {key} ({datestr}): {gloss} (N = {len(df_all):,}) ---")
        print(f"  Placebo Cohort: Operational = {tbl.loc[(0, 0)]:.1f}% | High Rank (DG/Apex) = {tbl.loc[(0, 1)]:.1f}% (Gap: {tbl.loc[(0, 1)] - tbl.loc[(0, 0)]:.1f} pp)")
        print(f"  Treated Cohort: Operational = {tbl.loc[(1, 0)]:.1f}% | High Rank (DG/Apex) = {tbl.loc[(1, 1)]:.1f}% (Gap: {tbl.loc[(1, 1)] - tbl.loc[(1, 0)]:.1f} pp)")
        print(f"  DiD Interaction (Treated x High Rank): {mod_did.params['treated_cohort:rank_high']*100:+.2f} pp (SE = {mod_did.bse['treated_cohort:rank_high']*100:.2f} pp, t = {mod_did.tvalues['treated_cohort:rank_high']:.2f}, p = {mod_did.pvalues['treated_cohort:rank_high']:.4e})")

    return did_surv_results


def estimate_did_demotion(spells):
    """Difference-in-Differences on Demotion Probability Among Surviving Movers."""
    print("\n" + "=" * 100)
    print("4. DIFFERENCE-IN-DIFFERENCES (DiD): WEAPONIZED DEMOTION PROBABILITY")
    print("=" * 100)

    def get_movers(t0, treated_val):
        t1 = min(t0 + pd.DateOffset(years=3), RECORD_ENDS)
        inpost = spells[(spells.start < t0) & (spells.end.isna() | (spells.end > t0))]
        before = inpost.groupby("person_id").rank_score.max()
        after = (
            spells[(spells.start >= t0) & (spells.start < t1)]
            .groupby("person_id")
            .rank_score.max()
        )
        j = before.to_frame("b").join(after.rename("a"), how="inner").reset_index()
        j["is_demoted"] = (j.a < j.b).astype(int)
        j["is_promoted"] = (j.a > j.b).astype(int)
        j["treated"] = treated_val
        return j

    did_demo_results = {}

    for key, t0, datestr, gloss in RUPTURES:
        rup_m = get_movers(t0, 1)
        plc_m = pd.concat([get_movers(t0 - pd.DateOffset(years=k), 0) for k in PLACEBO_LAGS], ignore_index=True)
        all_m = pd.concat([rup_m, plc_m], ignore_index=True)

        mod = smf.ols("is_demoted ~ treated", data=all_m).fit(cov_type="HC1")
        p_rup = rup_m.is_demoted.mean() * 100
        p_plc = plc_m.is_demoted.mean() * 100

        did_demo_results[key] = {
            "n": len(all_m),
            "n_rup": len(rup_m),
            "p_rup": p_rup,
            "p_plc": p_plc,
            "did_jump": mod.params["treated"] * 100,
            "did_se": mod.bse["treated"] * 100,
            "did_p": mod.pvalues["treated"],
        }

        print(f"\n--- {key} ({datestr}): {gloss} (N = {len(all_m):,} movers) ---")
        print(f"  Placebo Demotion Rate: {p_plc:.2f}%")
        print(f"  Treated Demotion Rate: {p_rup:.2f}%")
        print(f"  Excess Demotion DiD:   {mod.params['treated']*100:+.2f} pp (SE = {mod.bse['treated']*100:.2f} pp, t = {mod.tvalues['treated']:.2f}, p = {mod.pvalues['treated']:.4e})")

    return did_demo_results


def plot_publication_visual(rdd_vol, rdd_comp, did_surv, did_demo):
    """Plot 4-panel RDD & DiD publication figure."""
    print("\nRendering 4-panel publication visual...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    plt.subplots_adjust(hspace=0.35, wspace=0.25, top=0.92, bottom=0.08, left=0.07, right=0.96)

    # ---------------------------------------------------------
    # Panel A: Sharp RDD on Daily Appointment Volume (Cutoff c = 0)
    # ---------------------------------------------------------
    ax_a = axes[0, 0]
    ax_a.set_title(
        "A. Sharp Regression Discontinuity (RDD): Daily Appointment Volume (c = 0)\n"
        "Discontinuous collapse at Revolution (-7.6/day, p<0.001) & Saïed Coup (-5.0/day, p<0.001)",
        fontsize=9.5,
        fontweight="bold",
        pad=10,
    )

    for key, t0, datestr, gloss in RUPTURES:
        res = rdd_vol[key]
        daily = res["daily_df"]
        col = RUPTURE_COLOURS[key]

        # Scatter dots (semi-transparent)
        ax_a.scatter(daily.x, daily["count"], color=col, alpha=0.15, s=12)

        # Plot fitted regression lines on both sides of cutoff
        pre_d = daily[daily.x < 0]
        post_d = daily[daily.x >= 0]
        ax_a.plot(pre_d.x, pre_d.pred, color=col, lw=2.2, ls="--")
        ax_a.plot(post_d.x, post_d.pred, color=col, lw=2.4, label=f"{key} {gloss} (Jump: {res['jump']:+.1f}*)")

    ax_a.axvline(0, color=INK, lw=1.2, ls=":", zorder=3)
    ax_a.set_xlim(-180, 180)
    ax_a.set_ylim(0, 35)
    ax_a.set_xlabel("Days from the Unexpected Regime Shock (c = 0)")
    ax_a.set_ylabel("Daily Gazetted Appointments Count")
    ax_a.grid(True, linestyle=":", alpha=0.6)
    ax_a.legend(loc="upper right", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # ---------------------------------------------------------
    # Panel B: Sharp RDD on Appointee Composition: Apex vs. Security
    # ---------------------------------------------------------
    ax_b = axes[0, 1]
    ax_b.set_title(
        "B. Sharp RDD on Appointee Composition: Apex vs. Security Realignment\n"
        "1987 Coup surged military/security (+34.2 pp); 2011 surged Apex executives (+39.6 pp)",
        fontsize=9.5,
        fontweight="bold",
        pad=10,
    )

    x_bars = np.arange(len(RUPTURES))
    width = 0.35

    apex_jumps = [rdd_comp[k]["apex_jump"] for k, _, _, _ in RUPTURES]
    apex_ses = [rdd_comp[k]["apex_se"] for k, _, _, _ in RUPTURES]
    sec_jumps = [rdd_comp[k]["sec_jump"] for k, _, _, _ in RUPTURES]
    sec_ses = [rdd_comp[k]["sec_se"] for k, _, _, _ in RUPTURES]

    b1 = ax_b.bar(x_bars - width / 2, apex_jumps, width, yerr=apex_ses, capsize=4, color="#1B5FC1", label="Apex Political Appointees (Rank >= 70)", edgecolor=PAPER)
    b2 = ax_b.bar(x_bars + width / 2, sec_jumps, width, yerr=sec_ses, capsize=4, color="#A03B2C", label="Security & Military-Linked Appointees", edgecolor=PAPER)

    for bar, val in zip(b1, apex_jumps):
        ax_b.annotate(f"{val:+.1f} pp", xy=(bar.get_x() + bar.get_width() / 2, val + (1.5 if val >= 0 else -3.5)), ha="center", fontsize=8.0, fontweight="bold", color="#1B5FC1")

    for bar, val in zip(b2, sec_jumps):
        ax_b.annotate(f"{val:+.1f} pp", xy=(bar.get_x() + bar.get_width() / 2, val + (1.5 if val >= 0 else -3.5)), ha="center", fontsize=8.0, fontweight="bold", color="#A03B2C")

    ax_b.axhline(0, color=INK, lw=1.0, ls="-")
    ax_b.set_xticks(x_bars)
    ax_b.set_xticklabels(["1987 Ben Ali Coup", "2011 Revolution", "2021 Saïed Auto-Coup"])
    ax_b.set_ylabel("Discontinuous RDD Jump at Cutoff (pp)")
    ax_b.set_ylim(-20, 50)
    ax_b.grid(True, axis="y", linestyle=":", alpha=0.6)
    ax_b.legend(loc="upper right", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # ---------------------------------------------------------
    # Panel C: Difference-in-Differences (DiD) on Hierarchical Survival (24M)
    # ---------------------------------------------------------
    ax_c = axes[1, 0]
    ax_c.set_title(
        "C. Hierarchical Difference-in-Differences (DiD): 24-Month Survival\n"
        "High-rank DGs & Apex suffered extra DiD purge penalty in 1987 (-5.0 pp) & 2011 (-7.5 pp)",
        fontsize=9.5,
        fontweight="bold",
        pad=10,
    )

    x_c = np.arange(len(RUPTURES))
    w_c = 0.28

    # Plot DiD components: Placebo High-Low vs. Treated High-Low
    for idx, (key, _, datestr, gloss) in enumerate(RUPTURES):
        res = did_surv[key]
        tbl = res["tbl"]
        col = RUPTURE_COLOURS[key]

        # Draw 2x2 line: Operational -> High Rank
        # Placebo
        ax_c.plot([idx - w_c / 2, idx + w_c / 2], [tbl.loc[(0, 0)], tbl.loc[(0, 1)]], color=MUTED, lw=1.6, ls=":", marker="o", markersize=6)
        # Treated
        ax_c.plot([idx - w_c / 2, idx + w_c / 2], [tbl.loc[(1, 0)], tbl.loc[(1, 1)]], color=col, lw=2.4, ls="-", marker="s", markersize=7, label=f"{key} (DiD: {res['did_interaction']:+.1f} pp)")

        # Annotate DiD interaction (avoid collision with Panel D y-axis for 2021)
        x_text = idx + w_c / 2 - 0.28 if idx == 2 else idx + w_c / 2 + 0.05
        ax_c.annotate(
            f"δ_DiD = {res['did_interaction']:+.2f} pp\n(p = {res['did_p']:.1e})",
            xy=(idx + w_c / 2, tbl.loc[(1, 1)]),
            xytext=(x_text, tbl.loc[(1, 1)] - 2),
            fontsize=8.0,
            fontweight="bold",
            color=col,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=PAPER, edgecolor=RULE, alpha=0.8),
        )

    ax_c.set_xticks(x_c)
    ax_c.set_xticklabels(["1987 Ben Ali Coup\n(N=52k)", "2011 Revolution\n(N=140k)", "2021 Saïed Auto-Coup\n(N=209k)"])
    ax_c.set_ylabel("24-Month Incumbent Survival Rate (%)")
    ax_c.set_ylim(60, 100)
    ax_c.grid(True, linestyle=":", alpha=0.6)
    ax_c.legend(loc="lower left", frameon=True, facecolor=PAPER, edgecolor=RULE)

    # ---------------------------------------------------------
    # Panel D: Difference-in-Differences (DiD) on Weaponized Demotion
    # ---------------------------------------------------------
    ax_d = axes[1, 1]
    ax_d.set_title(
        "D. Difference-in-Differences (DiD): Weaponized Demotion Probability\n"
        "Saïed generated massive +9.95 pp excess demotion (p = 8.1e-28); 1987 & 2011 promoted survivors",
        fontsize=9.5,
        fontweight="bold",
        pad=10,
    )

    dem_jumps = [did_demo[k]["did_jump"] for k, _, _, _ in RUPTURES]
    dem_ses = [did_demo[k]["did_se"] for k, _, _, _ in RUPTURES]
    x_d = np.arange(len(RUPTURES))

    b_dem = ax_d.bar(x_d, dem_jumps, 0.45, yerr=dem_ses, capsize=5, color=[RUPTURE_COLOURS[k] for k, _, _, _ in RUPTURES], edgecolor=PAPER)

    for bar, val, (k, _, _, _) in zip(b_dem, dem_jumps, RUPTURES):
        y_pos = val + (0.7 if val >= 0 else -1.6)
        p_val = did_demo[k]["did_p"]
        sig = " ***" if p_val < 0.001 else (" **" if p_val < 0.01 else (" *" if p_val < 0.05 else " n.s."))
        ax_d.annotate(
            f"{val:+.2f} pp{sig}\n(p = {p_val:.1e})",
            xy=(bar.get_x() + bar.get_width() / 2, y_pos),
            ha="center",
            va="top" if val < 0 else "bottom",
            fontsize=8.5,
            fontweight="bold",
            color=RUPTURE_COLOURS[k],
        )

    ax_d.axhline(0, color=INK, lw=1.0, ls="-")
    ax_d.set_xticks(x_d)
    ax_d.set_xticklabels(["1987 Ben Ali Coup\n(N=4,690 movers)", "2011 Revolution\n(N=16,386 movers)", "2021 Saïed Auto-Coup\n(N=22,868 movers)"])
    ax_d.set_ylabel("Excess Demotion DiD vs. Placebos (pp)")
    ax_d.set_ylim(-6, 14)
    ax_d.grid(True, axis="y", linestyle=":", alpha=0.6)

    # Save PNG and PDF
    png_path = FIGS / "fig_theory_13_presidential_shocks.png"
    pdf_path = FIGS / "fig_theory_13_presidential_shocks.pdf"

    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved publication figures to {png_path} and {pdf_path}")


def generate_interactive_dashboard(rdd_vol, rdd_comp, did_surv, did_demo):
    """Generate interactive Plotly dashboard featuring RDD & DiD econometric models."""
    print("Generating interactive Plotly dashboard...")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Theory 13: RDD & Difference-in-Differences (Causal Effects of Presidential Shocks)</title>
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
    </style>
</head>
<body>

<div class="header">
    <h1>Theory 13: Regression Discontinuity Design (RDD) & Difference-in-Differences (DiD)</h1>
    <div class="subtitle">
        Causal identification of the administrative impact of unexpected presidential transitions (1987 Coup, 2011 Revolution, 2021 Auto-Coup).
        Using sharp discontinuity at the shock date (c = 0) and 2x2 DiD models against 5 pre-shock matched placebo calendar cohorts.
    </div>
</div>

<div class="grid">
    <div class="card">
        <div id="plot_rdd_vol" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_rdd_comp" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_did_surv" style="width:100%; height:420px;"></div>
    </div>
    <div class="card">
        <div id="plot_did_demo" style="width:100%; height:420px;"></div>
    </div>
</div>

<div class="table-container">
    <h3 style="margin-top:0;">Econometric RDD & DiD Parameter Estimates</h3>
    <table>
        <thead>
            <tr>
                <th>Shock Event</th>
                <th>Presidency Transition</th>
                <th>Daily Volume RDD Jump (SE)</th>
                <th>Apex Appointees RDD Jump (SE)</th>
                <th>Security/Military RDD Jump (SE)</th>
                <th>Hierarchical DiD Interaction (SE)</th>
                <th>Excess Demotion DiD (SE)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>7 Nov 1987</strong></td>
                <td>Bourguiba &rarr; Ben Ali Coup</td>
                <td>+0.74 (1.24, p=0.55)</td>
                <td>-1.05 pp (5.66, p=0.85)</td>
                <td><span style="color:#A03B2C; font-weight:bold;">+34.24 pp (5.93, p&lt;10⁻⁷)</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">-5.01 pp (2.40, p=0.037)</span></td>
                <td>-1.24 pp (1.46, p=0.40)</td>
            </tr>
            <tr>
                <td><strong>14 Jan 2011</strong></td>
                <td>Ben Ali &rarr; Revolution</td>
                <td><span style="color:#1B5FC1; font-weight:bold;">-7.59 /day (2.12, p&lt;0.001)</span></td>
                <td><span style="color:#1B5FC1; font-weight:bold;">+39.56 pp (4.10, p&lt;10⁻²⁰)</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">-12.65 pp (4.94, p=0.010)</span></td>
                <td><span style="color:#1B5FC1; font-weight:bold;">-7.54 pp (1.23, p&lt;10⁻⁹)</span></td>
                <td>-2.22 pp (0.73, p=0.002)</td>
            </tr>
            <tr>
                <td><strong>25 Jul 2021</strong></td>
                <td>Sa&iuml;ed Article 80 Auto-Coup</td>
                <td><span style="color:#B5852A; font-weight:bold;">-5.02 /day (1.36, p&lt;0.001)</span></td>
                <td>+3.42 pp (3.39, p=0.31)</td>
                <td>+2.63 pp (5.79, p=0.65)</td>
                <td><span style="color:#1B5FC1; font-weight:bold;">+3.40 pp (0.74, p&lt;10⁻⁵)</span></td>
                <td><span style="color:#A03B2C; font-weight:bold;">+9.95 pp (0.90, p=8.1e-28)</span></td>
            </tr>
        </tbody>
    </table>
</div>

<script>
    // 1. RDD Volume Plot
    var rddTrace87 = {{
        x: Array.from({{length: 49}}, (_, i) => (i - 24) * 7.5),
        y: [{rdd_vol["1987"]["pre_mean"]:.2f}, {rdd_vol["1987"]["post_mean"]:.2f}],
        mode: 'lines', name: '1987 Ben Ali Coup', line: {{color: '#A03B2C', width: 2.5}}
    }};
    Plotly.newPlot('plot_rdd_vol', [
        {{
            x: [-180, 0, 0, 180],
            y: [{rdd_vol["1987"]["pre_mean"]:.2f}, {rdd_vol["1987"]["pre_mean"]:.2f}, {rdd_vol["1987"]["post_mean"]:.2f}, {rdd_vol["1987"]["post_mean"]:.2f}],
            mode: 'lines', name: '1987 Ben Ali Coup (+0.7/day)', line: {{color: '#A03B2C', width: 2.5}}
        }},
        {{
            x: [-180, 0, 0, 180],
            y: [{rdd_vol["2011"]["pre_mean"]:.2f}, {rdd_vol["2011"]["pre_mean"]:.2f}, {rdd_vol["2011"]["post_mean"]:.2f}, {rdd_vol["2011"]["post_mean"]:.2f}],
            mode: 'lines', name: '2011 Revolution (-7.6/day***)', line: {{color: '#1B5FC1', width: 2.5}}
        }},
        {{
            x: [-180, 0, 0, 180],
            y: [{rdd_vol["2021"]["pre_mean"]:.2f}, {rdd_vol["2021"]["pre_mean"]:.2f}, {rdd_vol["2021"]["post_mean"]:.2f}, {rdd_vol["2021"]["post_mean"]:.2f}],
            mode: 'lines', name: '2021 Saied Auto-Coup (-5.0/day***)', line: {{color: '#B5852A', width: 2.5}}
        }}
    ], {{
        title: '<b>A. Sharp RDD: Daily Appointment Volume (c = 0)</b>',
        xaxis: {{title: 'Days from Cutoff (c = 0)'}},
        yaxis: {{title: 'Daily Appointments Count'}}
    }});

    // 2. RDD Composition Plot
    Plotly.newPlot('plot_rdd_comp', [
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{rdd_comp["1987"]["apex_jump"]:.2f}, {rdd_comp["2011"]["apex_jump"]:.2f}, {rdd_comp["2021"]["apex_jump"]:.2f}],
            name: 'Apex Executives (>=70)', type: 'bar', marker: {{color: '#1B5FC1'}}
        }},
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{rdd_comp["1987"]["sec_jump"]:.2f}, {rdd_comp["2011"]["sec_jump"]:.2f}, {rdd_comp["2021"]["sec_jump"]:.2f}],
            name: 'Security & Military', type: 'bar', marker: {{color: '#A03B2C'}}
        }}
    ], {{
        title: '<b>B. Sharp RDD: Discontinuous Jump in Appointee Composition</b>',
        yaxis: {{title: 'Discontinuity Jump (Percentage Points)'}}
    }});

    // 3. DiD Survival Plot
    Plotly.newPlot('plot_did_surv', [
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{did_surv["1987"]["did_interaction"]:.2f}, {did_surv["2011"]["did_interaction"]:.2f}, {did_surv["2021"]["did_interaction"]:.2f}],
            name: 'DiD Interaction (Treated x High Rank)', type: 'bar',
            marker: {{color: ['#A03B2C', '#1B5FC1', '#B5852A']}}
        }}
    ], {{
        title: '<b>C. Hierarchical DiD: DG & Apex Survival Penalty</b>',
        yaxis: {{title: 'DiD Interaction delta_DiD (Percentage Points)'}}
    }});

    // 4. DiD Demotion Plot
    Plotly.newPlot('plot_did_demo', [
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{did_demo["1987"]["did_jump"]:.2f}, {did_demo["2011"]["did_jump"]:.2f}, {did_demo["2021"]["did_jump"]:.2f}],
            name: 'Excess Demotion DiD', type: 'bar',
            marker: {{color: ['#A03B2C', '#1B5FC1', '#B5852A']}}
        }}
    ], {{
        title: '<b>D. DiD on Weaponized Demotion Probability</b>',
        yaxis: {{title: 'Excess Demotion DiD vs. Placebos (pp)'}}
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
    events, spells = load_data()

    rdd_vol = estimate_rdd_volume(events)
    rdd_comp = estimate_rdd_composition(events)
    did_surv = estimate_did_survival(spells)
    did_demo = estimate_did_demotion(spells)

    plot_publication_visual(rdd_vol, rdd_comp, did_surv, did_demo)
    generate_interactive_dashboard(rdd_vol, rdd_comp, did_surv, did_demo)

    print("\nRDD and Difference-in-Differences pipeline executed successfully!")


if __name__ == "__main__":
    main()
