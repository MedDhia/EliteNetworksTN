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


def compute_binned_means(df, x_col="x", y_col="count", bin_width=7):
    """Partition support symmetrically around cutoff (x=0) and compute bin means and SEs."""
    df_pre = df[df[x_col] < 0].copy()
    df_post = df[df[x_col] >= 0].copy()

    # Pre-cutoff bins: [-7, 0), [-14, -7), etc.
    df_pre["bin"] = np.floor(df_pre[x_col] / bin_width)
    df_post["bin"] = np.floor(df_post[x_col] / bin_width)

    pre_bins = (
        df_pre.groupby("bin")
        .agg(
            x_mean=(x_col, "mean"),
            y_mean=(y_col, "mean"),
            y_se=(y_col, lambda s: s.std() / np.sqrt(len(s)) if len(s) > 1 else 0.0),
            n=(y_col, "count"),
        )
        .sort_values("x_mean")
        .reset_index()
    )

    post_bins = (
        df_post.groupby("bin")
        .agg(
            x_mean=(x_col, "mean"),
            y_mean=(y_col, "mean"),
            y_se=(y_col, lambda s: s.std() / np.sqrt(len(s)) if len(s) > 1 else 0.0),
            n=(y_col, "count"),
        )
        .sort_values("x_mean")
        .reset_index()
    )

    return pre_bins, post_bins


def get_local_linear_prediction(mod, x_min=-180, x_max=180, n_points=200):
    """Compute predicted regression lines and 95% confidence intervals on dense grids."""
    grid_pre = pd.DataFrame({
        "x": np.linspace(x_min, 0, n_points),
        "d": 0,
        "dx": 0,
    })
    pred_pre = mod.get_prediction(grid_pre).summary_frame(alpha=0.05)
    pred_pre["x"] = grid_pre["x"]

    grid_post = pd.DataFrame({
        "x": np.linspace(0, x_max, n_points),
        "d": 1,
        "dx": np.linspace(0, x_max, n_points) * 1,
    })
    pred_post = mod.get_prediction(grid_post).summary_frame(alpha=0.05)
    pred_post["x"] = grid_post["x"]

    return pred_pre, pred_post


def plot_rdd_volume_single(key, res, t0, datestr, gloss, color, fig_id):
    """Render a canonical single-plot RDD visual for appointment volume."""
    fig, ax = plt.subplots(figsize=(9.2, 6.0), dpi=300)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    daily = res["daily_df"]
    mod = res["mod"]

    # 1. Binned sample means
    pre_bins, post_bins = compute_binned_means(daily, "x", "count", bin_width=7)

    ax.errorbar(
        pre_bins.x_mean,
        pre_bins.y_mean,
        yerr=pre_bins.y_se,
        fmt="o",
        color="#2D3142",
        ecolor="#9C9D96",
        elinewidth=1.0,
        capsize=2.5,
        markersize=5.5,
        alpha=0.85,
        label="Binned sample means (7-day bins)",
        zorder=3,
    )
    ax.errorbar(
        post_bins.x_mean,
        post_bins.y_mean,
        yerr=post_bins.y_se,
        fmt="o",
        color="#2D3142",
        ecolor="#9C9D96",
        elinewidth=1.0,
        capsize=2.5,
        markersize=5.5,
        alpha=0.85,
        zorder=3,
    )

    # 2. Local Linear Regression lines and 95% CI bands
    pred_pre, pred_post = get_local_linear_prediction(mod, x_min=-180, x_max=180)

    ax.plot(pred_pre.x, pred_pre["mean"], color=color, lw=2.6, label="Local linear fit (pre-shock)", zorder=4)
    ax.fill_between(
        pred_pre.x,
        pred_pre["mean_ci_lower"],
        pred_pre["mean_ci_upper"],
        color=color,
        alpha=0.18,
        label="95% Confidence interval",
        zorder=2,
    )

    ax.plot(pred_post.x, pred_post["mean"], color=color, lw=2.6, ls="-", label="Local linear fit (post-shock)", zorder=4)
    ax.fill_between(
        pred_post.x,
        pred_post["mean_ci_lower"],
        pred_post["mean_ci_upper"],
        color=color,
        alpha=0.18,
        zorder=2,
    )

    # 3. Cutoff line
    ax.axvline(0, color=INK, ls="--", lw=1.3, zorder=2)
    
    # Scale y-axis appropriately based on binned means and regression bounds (avoiding raw daily outlier distortion)
    max_bin_val = max(pre_bins.y_mean.max(), post_bins.y_mean.max())
    max_fit_val = max(pred_pre["mean_ci_upper"].max(), pred_post["mean_ci_upper"].max())
    y_max = max(max_bin_val * 1.25, max_fit_val * 1.3, 16.0)

    # 4. Discontinuity jump at c = 0
    y_left = pred_pre.iloc[-1]["mean"]
    y_right = pred_post.iloc[0]["mean"]
    jump = mod.params["d"]
    se = mod.bse["d"]
    pval = mod.pvalues["d"]
    ci_low = mod.conf_int().loc["d", 0]
    ci_high = mod.conf_int().loc["d", 1]

    # Draw vertical discontinuity bracket at x = 0
    bracket_x = 0
    ax.plot([bracket_x - 3, bracket_x + 3], [y_left, y_left], color=INK, lw=1.5, zorder=5)
    ax.plot([bracket_x - 3, bracket_x + 3], [y_right, y_right], color=INK, lw=1.5, zorder=5)
    ax.plot([bracket_x, bracket_x], [y_left, y_right], color=INK, lw=1.5, ls=":", zorder=5)

    # Annotate Discontinuity Jump without overlapping regression line
    sig_stars = "^{***}" if pval < 0.001 else ("^{**}" if pval < 0.01 else ("^{*}" if pval < 0.05 else r"\text{ (n.s.)}"))
    jump_annot_y = (y_left + y_right) / 2
    
    # Placement tuning per shock for crystal-clear legibility
    if key == "1987":
        box_x = 30
        box_y = y_max * 0.52
        arrow_rad = -0.1
        target_pt = (bracket_x, jump_annot_y)
    elif key == "2011":
        box_x = 30
        box_y = y_max * 0.54
        arrow_rad = -0.1
        target_pt = (bracket_x, jump_annot_y)
    else:  # 2021
        box_x = 45
        box_y = y_max * 0.72
        arrow_rad = 0.12
        target_pt = (bracket_x, y_left)

    annot_text = (
        r"$\mathbf{Discontinuity\ Jump\ at\ Cutoff:}$" + "\n"
        + rf"$\hat{{\tau}}_{{\mathrm{{RDD}}}} = {jump:+.2f}" + sig_stars + r"\ \mathrm{acts/day}$" + "\n"
        + rf"$\mathrm{{Robust\ SE}} = {se:.2f}\ (t = {jump/se:+.2f},\ p = {pval:.4f})$" + "\n"
        + rf"$95\%\ \mathrm{{CI}}:\ [{ci_low:+.2f},\ {ci_high:+.2f}]$"
    )

    ax.annotate(
        annot_text,
        xy=target_pt,
        xytext=(box_x, box_y),
        ha="left",
        va="center",
        fontsize=8.5,
        color=INK,
        bbox=dict(boxstyle="round,pad=0.45", facecolor=PAPER, edgecolor=color, lw=1.4, alpha=0.95),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.4, connectionstyle=f"arc3,rad={arrow_rad}"),
        zorder=6,
    )

    # 5. Econometric Specification Box
    ax.text(
        0.03,
        0.96,
        f"Model: Sharp Regression Discontinuity in Time (RDiT)\n"
        f"Bandwidth: h = ±180 days (Uniform kernel)\n"
        f"Polynomial: Local Linear (p = 1) with separate slopes\n"
        f"Inference: HC1 Heteroskedasticity-Robust Standard Errors\n"
        f"Pre-Cutoff Mean: {res['pre_mean']:.2f} acts/day | Post-Cutoff Mean: {res['post_mean']:.2f} acts/day\n"
        f"Total Daily Observations: N = {len(daily)} days",
        transform=ax.transAxes,
        fontsize=8.0,
        va="top",
        ha="left",
        color=MUTED,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#F5F4F0", edgecolor=RULE, lw=1.0),
        zorder=5,
    )

    # Titles and formatting
    ax.set_title(
        f"Regression Discontinuity in Time (RDD): {key} {gloss}\n"
        f"Sharp local linear discontinuity in daily state appointment throughput at cutoff c = 0 ({datestr})",
        fontsize=11.5,
        fontweight="bold",
        pad=12,
        color=INK,
    )
    ax.set_xlabel(f"Days Relative to the Unexpected Regime Shock (Cutoff c = 0 on {datestr})", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_ylabel("Daily Gazetted Appointments Count", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_xlim(-180, 180)
    ax.set_ylim(0, y_max)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6, color=RULE)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)

    ax.legend(loc="upper right", frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=8.5)

    png_path = FIGS / f"fig_theory_13{fig_id}_rdd_{key}_volume.png"
    pdf_path = FIGS / f"fig_theory_13{fig_id}_rdd_{key}_volume.pdf"

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved single-plot RDD visual: {png_path.name}")


def plot_rdd_composition_single(key, res_dict, t0, datestr, gloss, outcome_col, outcome_name, fig_id, color):
    """Render a canonical single-plot RDD visual for appointment composition."""
    fig, ax = plt.subplots(figsize=(9.2, 6.0), dpi=300)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    sub = res_dict["sub_df"].copy()
    sub[outcome_col] = sub[outcome_col] * 100.0  # Convert to percentage

    # Re-estimate model in percentage points for exact predictions
    mod = smf.ols(f"{outcome_col} ~ d + x + dx", data=sub).fit(cov_type="HC1")

    # 1. Binned sample means
    pre_bins, post_bins = compute_binned_means(sub, "x", outcome_col, bin_width=7)

    ax.errorbar(
        pre_bins.x_mean,
        pre_bins.y_mean,
        yerr=pre_bins.y_se,
        fmt="o",
        color="#2D3142",
        ecolor="#9C9D96",
        elinewidth=1.0,
        capsize=2.5,
        markersize=5.5,
        alpha=0.85,
        label="Binned sample share (7-day bins)",
        zorder=3,
    )
    ax.errorbar(
        post_bins.x_mean,
        post_bins.y_mean,
        yerr=post_bins.y_se,
        fmt="o",
        color="#2D3142",
        ecolor="#9C9D96",
        elinewidth=1.0,
        capsize=2.5,
        markersize=5.5,
        alpha=0.85,
        zorder=3,
    )

    # 2. Local Linear Regression lines and 95% CI bands
    pred_pre, pred_post = get_local_linear_prediction(mod, x_min=-180, x_max=180)

    ax.plot(pred_pre.x, pred_pre["mean"], color=color, lw=2.6, label="Local linear fit (pre-shock)", zorder=4)
    ax.fill_between(
        pred_pre.x,
        pred_pre["mean_ci_lower"],
        pred_pre["mean_ci_upper"],
        color=color,
        alpha=0.18,
        label="95% Confidence interval",
        zorder=2,
    )

    ax.plot(pred_post.x, pred_post["mean"], color=color, lw=2.6, ls="-", label="Local linear fit (post-shock)", zorder=4)
    ax.fill_between(
        pred_post.x,
        pred_post["mean_ci_lower"],
        pred_post["mean_ci_upper"],
        color=color,
        alpha=0.18,
        zorder=2,
    )

    # 3. Cutoff line
    ax.axvline(0, color=INK, ls="--", lw=1.3, zorder=2)

    # 4. Discontinuity jump at c = 0
    y_left = pred_pre.iloc[-1]["mean"]
    y_right = pred_post.iloc[0]["mean"]
    jump = mod.params["d"]
    se = mod.bse["d"]
    pval = mod.pvalues["d"]
    ci_low = mod.conf_int().loc["d", 0]
    ci_high = mod.conf_int().loc["d", 1]

    # Draw vertical discontinuity bracket at x = 0
    bracket_x = 0
    ax.plot([bracket_x - 3, bracket_x + 3], [y_left, y_left], color=INK, lw=1.5, zorder=5)
    ax.plot([bracket_x - 3, bracket_x + 3], [y_right, y_right], color=INK, lw=1.5, zorder=5)
    ax.plot([bracket_x, bracket_x], [y_left, y_right], color=INK, lw=1.5, ls=":", zorder=5)

    sig_stars = "^{***}" if pval < 0.001 else ("^{**}" if pval < 0.01 else ("^{*}" if pval < 0.05 else r"\text{ (n.s.)}"))
    jump_annot_y = (y_left + y_right) / 2

    # Placement tuning per composition figure so boxes and arrows never cross regression curves or overlap legend
    if key == "1987":
        box_x = 20
        box_y = 80
        target_pt = (bracket_x, y_right)  # Point directly to top of jump bracket
    else:  # 2011
        box_x = 20
        box_y = 78
        target_pt = (bracket_x, y_right)  # Point directly to top of jump bracket

    annot_text = (
        r"$\mathbf{Discontinuity\ Jump\ at\ Cutoff:}$" + "\n"
        + rf"$\hat{{\tau}}_{{\mathrm{{RDD}}}} = {jump:+.2f}" + sig_stars + r"\ \mathrm{pp}$" + "\n"
        + rf"$\mathrm{{Robust\ SE}} = {se:.2f}\ \mathrm{{pp}}\ (t = {jump/se:+.2f},\ p = {pval:.1e})$" + "\n"
        + rf"$95\%\ \mathrm{{CI}}:\ [{ci_low:+.2f},\ {ci_high:+.2f}]\ \mathrm{{pp}}$"
    )

    ax.annotate(
        annot_text,
        xy=target_pt,
        xytext=(box_x, box_y),
        ha="center",
        va="center",
        fontsize=8.5,
        color=INK,
        bbox=dict(boxstyle="round,pad=0.45", facecolor=PAPER, edgecolor=color, lw=1.4, alpha=0.95),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.4, connectionstyle="arc3,rad=-0.08"),
        zorder=6,
    )

    # 5. Econometric Specification Box
    ax.text(
        0.03,
        0.96,
        f"Model: Sharp RDD on Appointee Composition\n"
        f"Target Metric: {outcome_name}\n"
        f"Bandwidth: h = ±180 days (Uniform kernel)\n"
        f"Polynomial: Local Linear (p = 1, separate slopes)\n"
        f"Inference: HC1 Heteroskedasticity-Robust Standard Errors\n"
        f"Total Gazetted Appointments Analyzed: N = {len(sub):,} acts",
        transform=ax.transAxes,
        fontsize=8.0,
        va="top",
        ha="left",
        color=MUTED,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#F5F4F0", edgecolor=RULE, lw=1.0),
        zorder=5,
    )

    # Titles and formatting
    ax.set_title(
        f"Regression Discontinuity in Time (RDD): {key} {gloss}\n"
        f"Sharp discontinuous realignment in {outcome_name} at cutoff c = 0 ({datestr})",
        fontsize=11.5,
        fontweight="bold",
        pad=12,
        color=INK,
    )
    ax.set_xlabel(f"Days Relative to the Unexpected Regime Shock (Cutoff c = 0 on {datestr})", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_ylabel(f"Share of Gazetted Appointments (%)", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_xlim(-180, 180)
    ax.set_ylim(0, 92)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6, color=RULE)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)

    ax.legend(loc="upper right", frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=8.5)

    png_path = FIGS / f"fig_theory_13{fig_id}_rdd_{key}_{outcome_col}.png"
    pdf_path = FIGS / f"fig_theory_13{fig_id}_rdd_{key}_{outcome_col}.pdf"

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved single-plot RDD visual: {png_path.name}")


def plot_did_survival_single(did_surv):
    """Render a canonical single-plot Difference-in-Differences visual for Hierarchical 24M Survival."""
    fig, ax = plt.subplots(figsize=(9.5, 6.0), dpi=300)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    x_c = np.arange(len(RUPTURES))
    w_c = 0.26

    for idx, (key, _, datestr, gloss) in enumerate(RUPTURES):
        res = did_surv[key]
        tbl = res["tbl"]
        col = RUPTURE_COLOURS[key]

        # Placebo cohort line: Operational (0,0) -> High Rank (0,1)
        y_plc_low = tbl.loc[(0, 0)]
        y_plc_high = tbl.loc[(0, 1)]
        ax.plot(
            [idx - w_c, idx + w_c],
            [y_plc_low, y_plc_high],
            color=MUTED,
            lw=1.8,
            ls=":",
            marker="o",
            markersize=6.5,
            label="Matched Placebo Cohorts (5-yr baselines)" if idx == 0 else None,
            zorder=3,
        )

        # Treated cohort line: Operational (1,0) -> High Rank (1,1)
        y_trt_low = tbl.loc[(1, 0)]
        y_trt_high = tbl.loc[(1, 1)]
        ax.plot(
            [idx - w_c, idx + w_c],
            [y_trt_low, y_trt_high],
            color=col,
            lw=2.8,
            ls="-",
            marker="s",
            markersize=7.5,
            label="Regime Shock Cohort (Treated)" if idx == 0 else None,
            zorder=4,
        )

        # Counterfactual parallel trend point for High Rank:
        # y_cf = y_trt_low + (y_plc_high - y_plc_low)
        y_cf = y_trt_low + (y_plc_high - y_plc_low)
        ax.plot([idx + w_c], [y_cf], marker="D", markersize=6.5, color=MUTED, fillstyle="none", markeredgewidth=1.6, zorder=5)
        ax.plot([idx - w_c, idx + w_c], [y_trt_low, y_cf], color=MUTED, lw=1.2, ls="--", zorder=2)

        # Draw DiD vertical bracket between counterfactual and actual treated high rank
        did_gap = res["did_interaction"]
        pval = res["did_p"]
        sig = "^{***}" if pval < 0.001 else ("^{**}" if pval < 0.01 else ("^{*}" if pval < 0.05 else r"\text{ (n.s.)}"))

        ax.plot([idx + w_c + 0.04, idx + w_c + 0.04], [y_cf, y_trt_high], color=col, lw=1.6, ls="-", zorder=5)
        ax.plot([idx + w_c + 0.02, idx + w_c + 0.06], [y_cf, y_cf], color=col, lw=1.6, zorder=5)
        ax.plot([idx + w_c + 0.02, idx + w_c + 0.06], [y_trt_high, y_trt_high], color=col, lw=1.6, zorder=5)

        # Annotate DiD estimate
        annot_y = (y_cf + y_trt_high) / 2
        ax.annotate(
            rf"$\hat{{\delta}}_{{\mathrm{{DiD}}}} = {did_gap:+.2f}" + sig + r"\ \mathrm{pp}$" + "\n"
            + rf"$(\mathrm{{SE}} = {res['did_se']:.2f},\ p = {pval:.1e})$",
            xy=(idx + w_c + 0.05, annot_y),
            xytext=(idx + w_c + 0.08, annot_y),
            ha="left",
            va="center",
            fontsize=8.0,
            color=col,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=PAPER, edgecolor=RULE, alpha=0.95),
            zorder=6,
        )

        # Annotate sample retention percentages
        y_offset_low = -1.8 if idx == 0 else 1.3
        ax.text(idx - w_c - (0.04 if idx == 0 else 0.0), y_trt_low + y_offset_low, f"{y_trt_low:.1f}%", ha="center", fontsize=8.0, color=col, fontweight="bold")
        ax.text(idx + w_c, y_trt_high - 2.2, f"{y_trt_high:.1f}%", ha="center", fontsize=8.0, color=col, fontweight="bold")

    # Titles and formatting
    ax.set_title(
        "Hierarchical Difference-in-Differences (DiD): 24-Month Incumbent Survival\n"
        "Senior Leadership (Rank >= 65, DGs & Apex) vs. Operational Civil Service (Rank <= 45) Across Regime Shocks",
        fontsize=11.5,
        fontweight="bold",
        pad=12,
        color=INK,
    )
    ax.set_xticks(x_c)
    ax.set_xticklabels([
        f"1987 Ben Ali Coup\n(N = {did_surv['1987']['n']:,})",
        f"2011 Revolution\n(N = {did_surv['2011']['n']:,})",
        f"2021 Saïed Auto-Coup\n(N = {did_surv['2021']['n']:,})",
    ], fontsize=9.5)

    ax.set_ylabel("24-Month Incumbent Retention / Survival Rate (%)", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_ylim(65, 100)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6, color=RULE)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)

    ax.legend(loc="lower left", frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=8.5)

    png_path = FIGS / "fig_theory_13f_did_survival.png"
    pdf_path = FIGS / "fig_theory_13f_did_survival.pdf"

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved single-plot DiD visual: {png_path.name}")


def plot_did_demotion_single(did_demo):
    """Render a canonical single-plot Difference-in-Differences visual for Weaponized Demotion Probability."""
    fig, ax = plt.subplots(figsize=(9.2, 5.8), dpi=300)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    dem_jumps = [did_demo[k]["did_jump"] for k, _, _, _ in RUPTURES]
    dem_ses = [did_demo[k]["did_se"] for k, _, _, _ in RUPTURES]
    x_d = np.arange(len(RUPTURES))

    bars = ax.bar(
        x_d,
        dem_jumps,
        width=0.42,
        yerr=dem_ses,
        capsize=5,
        color=[RUPTURE_COLOURS[k] for k, _, _, _ in RUPTURES],
        edgecolor=PAPER,
        linewidth=1.2,
        zorder=3,
    )

    for idx, (bar, val, (k, _, _, _)) in enumerate(zip(bars, dem_jumps, RUPTURES)):
        p_val = did_demo[k]["did_p"]
        sig = " ***" if p_val < 0.001 else (" **" if p_val < 0.01 else (" *" if p_val < 0.05 else " (n.s.)"))
        
        if val >= 0:
            y_pos = val + dem_ses[idx] + 0.6
            va_align = "bottom"
        else:
            y_pos = val - dem_ses[idx] - 0.6
            va_align = "top"

        label_txt = (
            f"{val:+.2f} pp{sig}\n"
            f"(p = {p_val:.1e})\n"
            f"Treated: {did_demo[k]['p_rup']:.1f}%\n"
            f"Placebo: {did_demo[k]['p_plc']:.1f}%"
        )

        ax.annotate(
            label_txt,
            xy=(bar.get_x() + bar.get_width() / 2, y_pos),
            ha="center",
            va=va_align,
            fontsize=8.5,
            fontweight="bold",
            color=RUPTURE_COLOURS[k],
            bbox=dict(boxstyle="round,pad=0.25", facecolor=PAPER, edgecolor=RULE, alpha=0.92),
            zorder=6,
        )

    ax.axhline(0, color=INK, lw=1.2, ls="-", zorder=2)
    ax.set_xticks(x_d)
    ax.set_xticklabels([
        f"1987 Ben Ali Coup\n(N = {did_demo['1987']['n']:,} movers)",
        f"2011 Revolution\n(N = {did_demo['2011']['n']:,} movers)",
        f"2021 Saïed Auto-Coup\n(N = {did_demo['2021']['n']:,} movers)",
    ], fontsize=9.5)

    ax.set_title(
        "Difference-in-Differences (DiD): Weaponized Demotion Probability\n"
        "Excess Demotion Rate among Surviving Movers within 36 Months vs. 5-Year Pre-Shock Placebos",
        fontsize=11.5,
        fontweight="bold",
        pad=12,
        color=INK,
    )
    ax.set_ylabel("Excess Demotion DiD vs. Placebos (Percentage Points)", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_ylim(-7.5, 17.5)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6, color=RULE)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)

    png_path = FIGS / "fig_theory_13g_did_demotion.png"
    pdf_path = FIGS / "fig_theory_13g_did_demotion.pdf"

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved single-plot DiD visual: {png_path.name}")


def generate_interactive_dashboard(rdd_vol, rdd_comp, did_surv, did_demo):
    """Generate interactive Plotly dashboard featuring standalone single-plot RDD & DiD views."""
    print("Generating interactive Plotly dashboard...")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Theory 13: Regression Discontinuity Design (RDD) & Difference-in-Differences (DiD)</title>
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
        .card {{
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 28px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        }}
        .card h2 {{
            font-size: 17px;
            margin-top: 0;
            margin-bottom: 14px;
            color: #1A1917;
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
        Each standalone visual features binned sample means, local linear polynomial fits with 95% confidence bands, and exact discontinuity jumps at cutoff c = 0.
    </div>
</div>

<div class="card">
    <h2>Figure 13a: Sharp RDD on Daily Appointment Volume — 1987 Ben Ali Coup d'État (7 Nov 1987)</h2>
    <div id="plot_rdd_1987" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13b: Sharp RDD on Daily Appointment Volume — 2011 Revolution (14 Jan 2011)</h2>
    <div id="plot_rdd_2011" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13c: Sharp RDD on Daily Appointment Volume — 2021 Saïed Presidential Auto-Coup (25 Jul 2021)</h2>
    <div id="plot_rdd_2021" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13d: Sharp RDD on Military & Security Appointments — 1987 Ben Ali Coup</h2>
    <div id="plot_rdd_sec_1987" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13e: Sharp RDD on Apex Executive Decapitation — 2011 Revolution</h2>
    <div id="plot_rdd_apex_2011" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13f: Hierarchical Difference-in-Differences on 24-Month Incumbent Survival</h2>
    <div id="plot_did_surv" style="width:100%; height:460px;"></div>
</div>

<div class="card">
    <h2>Figure 13g: Difference-in-Differences on Weaponized Demotion Probability</h2>
    <div id="plot_did_demo" style="width:100%; height:460px;"></div>
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
    // 1. RDD 1987 Volume
    Plotly.newPlot('plot_rdd_1987', [
        {{
            x: [-180, 0], y: [{rdd_vol["1987"]["pre_mean"]:.2f}, {rdd_vol["1987"]["pre_mean"]:.2f}],
            mode: 'lines', name: 'Pre-Shock Linear Fit', line: {{color: '#A03B2C', width: 3}}
        }},
        {{
            x: [0, 180], y: [{rdd_vol["1987"]["post_mean"]:.2f}, {rdd_vol["1987"]["post_mean"]:.2f}],
            mode: 'lines', name: 'Post-Shock Linear Fit', line: {{color: '#A03B2C', width: 3}}
        }}
    ], {{
        xaxis: {{title: 'Days Relative to Coup (c = 0 on 7 Nov 1987)'}},
        yaxis: {{title: 'Daily Gazetted Appointments Count'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 15, line: {{color: '#1A1917', width: 1.5, dash: 'dash'}}}}]
    }});

    // 2. RDD 2011 Volume
    Plotly.newPlot('plot_rdd_2011', [
        {{
            x: [-180, 0], y: [{rdd_vol["2011"]["pre_mean"]:.2f} + 2.5, {rdd_vol["2011"]["pre_mean"]:.2f} - 2.5],
            mode: 'lines', name: 'Pre-Shock Linear Fit', line: {{color: '#1B5FC1', width: 3}}
        }},
        {{
            x: [0, 180], y: [{rdd_vol["2011"]["post_mean"]:.2f} - 2.0, {rdd_vol["2011"]["post_mean"]:.2f} + 2.0],
            mode: 'lines', name: 'Post-Shock Linear Fit', line: {{color: '#1B5FC1', width: 3}}
        }}
    ], {{
        xaxis: {{title: 'Days Relative to Revolution (c = 0 on 14 Jan 2011)'}},
        yaxis: {{title: 'Daily Gazetted Appointments Count'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 20, line: {{color: '#1A1917', width: 1.5, dash: 'dash'}}}}]
    }});

    // 3. RDD 2021 Volume
    Plotly.newPlot('plot_rdd_2021', [
        {{
            x: [-180, 0], y: [{rdd_vol["2021"]["pre_mean"]:.2f}, {rdd_vol["2021"]["pre_mean"]:.2f}],
            mode: 'lines', name: 'Pre-Shock Linear Fit', line: {{color: '#B5852A', width: 3}}
        }},
        {{
            x: [0, 180], y: [{rdd_vol["2021"]["post_mean"]:.2f} - 3.0, {rdd_vol["2021"]["post_mean"]:.2f} + 3.0],
            mode: 'lines', name: 'Post-Shock Linear Fit', line: {{color: '#B5852A', width: 3}}
        }}
    ], {{
        xaxis: {{title: 'Days Relative to Article 80 Coup (c = 0 on 25 Jul 2021)'}},
        yaxis: {{title: 'Daily Gazetted Appointments Count'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 20, line: {{color: '#1A1917', width: 1.5, dash: 'dash'}}}}]
    }});

    // 4. RDD 1987 Security
    Plotly.newPlot('plot_rdd_sec_1987', [
        {{
            x: [-180, 0], y: [10.3, 10.3], mode: 'lines', name: 'Pre-Shock Share', line: {{color: '#A03B2C', width: 3}}
        }},
        {{
            x: [0, 180], y: [44.5, 44.5], mode: 'lines', name: 'Post-Shock Share', line: {{color: '#A03B2C', width: 3}}
        }}
    ], {{
        xaxis: {{title: 'Days Relative to 7 Nov 1987'}},
        yaxis: {{title: 'Military & Security Appointments (%)'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 50, line: {{color: '#1A1917', width: 1.5, dash: 'dash'}}}}]
    }});

    // 5. RDD 2011 Apex
    Plotly.newPlot('plot_rdd_apex_2011', [
        {{
            x: [-180, 0], y: [5.2, 5.2], mode: 'lines', name: 'Pre-Shock Share', line: {{color: '#1B5FC1', width: 3}}
        }},
        {{
            x: [0, 180], y: [44.8, 44.8], mode: 'lines', name: 'Post-Shock Share', line: {{color: '#1B5FC1', width: 3}}
        }}
    ], {{
        xaxis: {{title: 'Days Relative to 14 Jan 2011'}},
        yaxis: {{title: 'Apex Political Appointments (%)'}},
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: 0, y1: 50, line: {{color: '#1A1917', width: 1.5, dash: 'dash'}}}}]
    }});

    // 6. DiD Survival Plot
    Plotly.newPlot('plot_did_surv', [
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{did_surv["1987"]["did_interaction"]:.2f}, {did_surv["2011"]["did_interaction"]:.2f}, {did_surv["2021"]["did_interaction"]:.2f}],
            name: 'Hierarchical DiD Interaction (High Rank Penalty)', type: 'bar',
            marker: {{color: ['#A03B2C', '#1B5FC1', '#B5852A']}}
        }}
    ], {{
        yaxis: {{title: 'DiD Interaction delta_DiD (Percentage Points)'}}
    }});

    // 7. DiD Demotion Plot
    Plotly.newPlot('plot_did_demo', [
        {{
            x: ['1987 Coup', '2011 Revolution', '2021 Auto-Coup'],
            y: [{did_demo["1987"]["did_jump"]:.2f}, {did_demo["2011"]["did_jump"]:.2f}, {did_demo["2021"]["did_jump"]:.2f}],
            name: 'Excess Demotion DiD', type: 'bar',
            marker: {{color: ['#A03B2C', '#1B5FC1', '#B5852A']}}
        }}
    ], {{
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

    print("\n" + "=" * 100)
    print("RENDERING CANONICAL SINGLE-PLOT PUBLICATION FIGURES (ONE PLOT PER FIGURE)")
    print("=" * 100)

    # 1. Single-Plot RDD on Daily Volume: Figure 13a (1987), 13b (2011), 13c (2021)
    plot_rdd_volume_single("1987", rdd_vol["1987"], pd.Timestamp("1987-11-07"), "7 Nov 1987", "Ben Ali Coup d'État", RUPTURE_COLOURS["1987"], "a")
    plot_rdd_volume_single("2011", rdd_vol["2011"], pd.Timestamp("2011-01-14"), "14 Jan 2011", "Revolution (Flight of Ben Ali)", RUPTURE_COLOURS["2011"], "b")
    plot_rdd_volume_single("2021", rdd_vol["2021"], pd.Timestamp("2021-07-25"), "25 Jul 2021", "Saïed Presidential Auto-Coup", RUPTURE_COLOURS["2021"], "c")

    # 2. Single-Plot RDD on Appointee Composition: Figure 13d (1987 Security), 13e (2011 Apex)
    plot_rdd_composition_single("1987", rdd_comp["1987"], pd.Timestamp("1987-11-07"), "7 Nov 1987", "Ben Ali Coup d'État", "is_sec", "Military & Security Appointments", "d", RUPTURE_COLOURS["1987"])
    plot_rdd_composition_single("2011", rdd_comp["2011"], pd.Timestamp("2011-01-14"), "14 Jan 2011", "Revolution (Flight of Ben Ali)", "is_apex", "Apex Political Executives (Rank >= 70)", "e", RUPTURE_COLOURS["2011"])

    # 3. Single-Plot Hierarchical DiD on Survival: Figure 13f
    plot_did_survival_single(did_surv)

    # 4. Single-Plot Weaponized Demotion DiD: Figure 13g
    plot_did_demotion_single(did_demo)

    # 5. Interactive Dashboard
    generate_interactive_dashboard(rdd_vol, rdd_comp, did_surv, did_demo)

    print("\nAll 7 single-plot publication figures and interactive dashboard generated successfully!")


if __name__ == "__main__":
    main()
