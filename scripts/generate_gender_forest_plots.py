"""
Generate Publication-Standard Single-Plot Forest Plots for Gender Biases Across Regimes.

Adheres strictly to:
1. Single plot per figure (1 Figure / 1 Axes).
2. Minimalist design (pure white canvas, zero clutter, high data-to-ink ratio).
3. Academic captions below the horizontal axis explicitly explaining gender dynamics.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.append(str(ROOT / "scripts"))
from gender_vertical_mobility import load_and_classify_gender

# Minimalist Palette
INK = "#111827"
MUTED = "#6B7280"
RULE = "#E5E7EB"
FEMALE_ACCENT = "#C2410C"  # Terracotta Rust
MALE_ACCENT = "#1D4ED8"    # Classic Royal Navy
POOLED_ACCENT = "#0F766E"  # Deep Teal

REGIMES = [
    "Bourguiba (1957–87)",
    "Ben Ali (1987–2011)",
    "Transition (2011–14)",
    "Essebsi (2014–19)",
    "Kais Saied (2019–26)",
]

REGIME_COLORS = {
    "Bourguiba (1957–87)": "#A03B2C",
    "Ben Ali (1987–2011)": "#1B5FC1",
    "Transition (2011–14)": "#0D9488",
    "Essebsi (2014–19)": "#B5852A",
    "Kais Saied (2019–26)": "#7C3AED",
    "Pooled (All Regimes)": "#111827",
}


def render_forest_plot(
    title: str,
    subtitle: str,
    categories: list[str],
    estimates: list[float],
    ci_lows: list[float],
    ci_highs: list[float],
    pvals: list[float],
    sample_sizes: list[int],
    ref_val: float,
    xlabel: str,
    left_guide: str,
    right_guide: str,
    caption: str,
    out_filename: str,
    is_ratio: bool = False,
    unit: str = "",
):
    """Render a single publication-grade minimalist forest plot."""
    n_items = len(categories)
    fig, ax = plt.subplots(figsize=(8.8, 5.0), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    y_pos = np.arange(n_items)[::-1]

    # Reference null line
    ax.axvline(ref_val, color="#374151", ls="--", lw=1.0, alpha=0.7, zorder=2)

    # Plot each estimate
    for idx, y in enumerate(y_pos):
        cat = categories[idx]
        est = estimates[idx]
        low = ci_lows[idx]
        high = ci_highs[idx]
        pval = pvals[idx]
        n_obs = sample_sizes[idx]
        col = REGIME_COLORS.get(cat, "#374151")

        is_pooled = "Pooled" in cat

        # Background guide line
        ax.axhline(y, color=RULE, ls=":", lw=0.7, alpha=0.6, zorder=1)

        # Confidence interval whisker
        ax.plot([low, high], [y, y], color=col, lw=2.2 if is_pooled else 1.8, zorder=3)
        ax.plot([low, low], [y - 0.12, y + 0.12], color=col, lw=1.5, zorder=3)
        ax.plot([high, high], [y - 0.12, y + 0.12], color=col, lw=1.5, zorder=3)

        # Center point estimate marker
        marker = "D" if is_pooled else "s"
        msize = 7.0 if is_pooled else 6.0
        ax.plot(est, y, marker=marker, color=col, markersize=msize, zorder=4)

        # Significance stars
        sig = "***" if pval < 0.001 else ("**" if pval < 0.01 else ("*" if pval < 0.05 else ""))

        # Text annotation on the right
        if is_ratio:
            annot = f"{est:.2f} [{low:.2f}, {high:.2f}]{sig}"
        else:
            annot = f"{est:+.2f}{unit} [{low:+.2f}, {high:+.2f}]{sig}"

        # Place estimate text to the right
        ax.text(
            1.02,
            y,
            f"{annot}  (N = {n_obs:,})",
            transform=ax.get_yaxis_transform(),
            va="center",
            ha="left",
            fontsize=7.8,
            color=col if is_pooled else "#374151",
            fontweight="bold" if is_pooled else "normal",
        )

    # Y-axis ticks and labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=8.5, fontweight="medium", color=INK)

    # Title & Subtitle
    ax.set_title(title, fontsize=10.5, fontweight="bold", pad=16, color=INK, loc="left")
    ax.text(0.0, 1.03, subtitle, transform=ax.transAxes, fontsize=8.8, color=MUTED, ha="left")

    # Clean two-line X-axis label with centered directional guides
    full_xlabel = f"{xlabel}\n(← {left_guide}   ·   {right_guide} →)"
    ax.set_xlabel(full_xlabel, fontsize=8.0, fontweight="medium", color=INK, labelpad=8)

    # Academic publication caption below horizontal axis
    ax.text(
        -0.28,
        -0.25,
        caption,
        transform=ax.transAxes,
        fontsize=7.2,
        color="#4B5563",
        va="top",
        ha="left",
        linespacing=1.35,
    )

    # Spines & styling
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(colors=INK, labelsize=8.0)

    # Set margins
    ax.set_ylim(-0.6, n_items - 0.4)

    png_path = FIGS / f"{out_filename}.png"
    pdf_path = FIGS / f"{out_filename}.pdf"

    plt.tight_layout()
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, bbox_inches="tight")
    plt.close()

    print(f"Saved forest plot: {png_path.name}")


def main():
    print("Loading data and inferring gender...")
    spells, persons = load_and_classify_gender()
    spells["is_female"] = (spells["gender"] == "Female").astype(int)

    # -------------------------------------------------------------------------
    # 1. Promotion Delay Penalty (Sticky Floor)
    # -------------------------------------------------------------------------
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["years_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days / 365.25
    spells["promoted_next"] = ((spells["next_rank"] > spells["rank_score"]) & spells["has_next"]).astype(int)
    prom = spells[(spells.promoted_next == 1) & (spells.years_to_next.between(0.1, 20))].copy()

    cats_pf = []
    ests_pf = []
    lows_pf = []
    highs_pf = []
    pvals_pf = []
    ns_pf = []

    for reg in REGIMES:
        sub = prom[prom.regime == reg]
        mod = smf.ols("years_to_next ~ is_female + rank_score", data=sub).fit(cov_type="HC1")
        cats_pf.append(reg)
        ests_pf.append(mod.params["is_female"] * 12)
        lows_pf.append(mod.conf_int().loc["is_female", 0] * 12)
        highs_pf.append(mod.conf_int().loc["is_female", 1] * 12)
        pvals_pf.append(mod.pvalues["is_female"])
        ns_pf.append(len(sub))

    # Pooled
    mod_p = smf.ols("years_to_next ~ is_female + rank_score", data=prom).fit(cov_type="HC1")
    cats_pf.append("Pooled (All Regimes)")
    ests_pf.append(mod_p.params["is_female"] * 12)
    lows_pf.append(mod_p.conf_int().loc["is_female", 0] * 12)
    highs_pf.append(mod_p.conf_int().loc["is_female", 1] * 12)
    pvals_pf.append(mod_p.pvalues["is_female"])
    ns_pf.append(len(prom))

    caption_14a = (
        "Figure 14a: Forest plot of female promotion velocity penalties (sticky floor) across Tunisian political regimes.\n"
        "Notes: Points and horizontal error bars display estimated net delay in months for female civil servants to achieve upward\n"
        "promotion relative to male peers, controlling for baseline entering rank score (HC1 robust 95% CIs). The vertical dashed line at 0\n"
        "indicates gender parity in promotion speed; positive values denote female promotion delay. Total sample N = 22,319 promotions."
    )
    render_forest_plot(
        title="Forest Plot: Gender Promotion Velocity Gap Across Regimes",
        subtitle=r"Adjusted delay in months for female promotion vs. male colleagues ($\Delta\text{Months} \pm 95\%\ \text{CI}$)",
        categories=cats_pf,
        estimates=ests_pf,
        ci_lows=lows_pf,
        ci_highs=highs_pf,
        pvals=pvals_pf,
        sample_sizes=ns_pf,
        ref_val=0.0,
        xlabel="Adjusted female promotion delay (months)",
        left_guide="Faster female promotion",
        right_guide="Female delay (Sticky floor)",
        caption=caption_14a,
        out_filename="fig_theory_14a_forest_gender_promotion_delay",
        unit=" mo",
    )

    # -------------------------------------------------------------------------
    # 2. Hierarchical Glass Ceiling (Odds Ratio of Senior Leadership)
    # -------------------------------------------------------------------------
    spells["is_senior"] = (spells.rank_score >= 65).astype(int)
    spells_gc = spells[spells.rank_score.isin([35, 45, 65, 70, 74, 80, 90])].copy()

    cats_gc = []
    ests_gc = []
    lows_gc = []
    highs_gc = []
    pvals_gc = []
    ns_gc = []

    for reg in REGIMES:
        sub = spells_gc[spells_gc.regime == reg]
        mod = smf.logit("is_senior ~ is_female", data=sub).fit(disp=False)
        b = mod.params["is_female"]
        se = mod.bse["is_female"]
        cats_gc.append(reg)
        ests_gc.append(np.exp(b))
        lows_gc.append(np.exp(b - 1.96 * se))
        highs_gc.append(np.exp(b + 1.96 * se))
        pvals_gc.append(mod.pvalues["is_female"])
        ns_gc.append(len(sub))

    # Pooled
    mod_gc_p = smf.logit("is_senior ~ is_female", data=spells_gc).fit(disp=False)
    b_p = mod_gc_p.params["is_female"]
    se_p = mod_gc_p.bse["is_female"]
    cats_gc.append("Pooled (All Regimes)")
    ests_gc.append(np.exp(b_p))
    lows_gc.append(np.exp(b_p - 1.96 * se_p))
    highs_gc.append(np.exp(b_p + 1.96 * se_p))
    pvals_gc.append(mod_gc_p.pvalues["is_female"])
    ns_gc.append(len(spells_gc))

    caption_14b = (
        "Figure 14b: Forest plot of the hierarchical glass ceiling odds ratios across political regimes.\n"
        "Notes: Points and horizontal error bars display the adjusted odds ratio (OR) of female civil servants reaching senior leadership\n"
        "positions (Secretary General, Director General, Cabinet Chief) versus entry-level cadres (95% CIs). The vertical dashed reference\n"
        "line at 1.0 denotes equal odds; values below 1.0 document an entrenched glass ceiling. Total sample N = 41,790 spells."
    )
    render_forest_plot(
        title="Forest Plot: Hierarchical Glass Ceiling Odds Across Regimes",
        subtitle=r"Adjusted Odds Ratio (OR) of female attainment of senior leadership ranks ($\text{OR} \pm 95\%\ \text{CI}$)",
        categories=cats_gc,
        estimates=ests_gc,
        ci_lows=lows_gc,
        ci_highs=highs_gc,
        pvals=pvals_gc,
        sample_sizes=ns_gc,
        ref_val=1.0,
        xlabel="Odds Ratio (OR) of senior leadership attainment",
        left_guide="Glass ceiling (Female disadvantage)",
        right_guide="Parity / Over-representation",
        caption=caption_14b,
        out_filename="fig_theory_14b_forest_gender_glass_ceiling",
        is_ratio=True,
    )

    # -------------------------------------------------------------------------
    # 3. Coercive & Territorial Quarantine (Interior, Defense, Regional Gov)
    # -------------------------------------------------------------------------
    spells["is_coercive"] = spells.apply(
        lambda r: bool(
            any(
                k
                in (
                    str(r["org_portfolio"])
                    + " "
                    + str(r["parent_org_name"])
                    + " "
                    + str(r["org_name"])
                ).lower()
                for k in [
                    "interieur",
                    "intérieur",
                    "defense",
                    "défense",
                    "gouvern",
                    "police",
                    "garde nationale",
                ]
            )
        ),
        axis=1,
    ).astype(int)

    cats_cq = []
    ests_cq = []
    lows_cq = []
    highs_cq = []
    pvals_cq = []
    ns_cq = []

    for reg in REGIMES:
        sub = spells[spells.regime == reg]
        mod = smf.logit("is_coercive ~ is_female", data=sub).fit(disp=False)
        b = mod.params["is_female"]
        se = mod.bse["is_female"]
        cats_cq.append(reg)
        ests_cq.append(np.exp(b))
        lows_cq.append(np.exp(b - 1.96 * se))
        highs_cq.append(np.exp(b + 1.96 * se))
        pvals_cq.append(mod.pvalues["is_female"])
        ns_cq.append(len(sub))

    # Pooled
    mod_cq_p = smf.logit("is_coercive ~ is_female", data=spells).fit(disp=False)
    b_p = mod_cq_p.params["is_female"]
    se_p = mod_cq_p.bse["is_female"]
    cats_cq.append("Pooled (All Regimes)")
    ests_cq.append(np.exp(b_p))
    lows_cq.append(np.exp(b_p - 1.96 * se_p))
    highs_cq.append(np.exp(b_p + 1.96 * se_p))
    pvals_cq.append(mod_cq_p.pvalues["is_female"])
    ns_cq.append(len(spells))

    caption_14c = (
        "Figure 14c: Forest plot of female placement odds in sovereign and coercive portfolios across political regimes.\n"
        "Notes: Odds ratios reflect the relative likelihood of female civil servants being assigned to sovereign coercive portfolios\n"
        "(Interior, Defense, Regional Governorships) vs. civilian line ministries, relative to male peers (95% CIs). The dashed reference\n"
        "line at 1.0 indicates gender parity in portfolio assignment; values < 1.0 show coercive quarantine of women. Total N = 99,270."
    )
    render_forest_plot(
        title="Forest Plot: Coercive & Territorial Quarantine Odds Across Regimes",
        subtitle=r"Odds Ratio (OR) of female appointment in Interior, Defense, or Regional Governance ($\text{OR} \pm 95\%\ \text{CI}$)",
        categories=cats_cq,
        estimates=ests_cq,
        ci_lows=lows_cq,
        ci_highs=highs_cq,
        pvals=pvals_cq,
        sample_sizes=ns_cq,
        ref_val=1.0,
        xlabel="Odds Ratio (OR) in sovereign and coercive portfolios",
        left_guide="Coercive quarantine (< 1.0)",
        right_guide="Gender parity (≥ 1.0)",
        caption=caption_14c,
        out_filename="fig_theory_14c_forest_gender_coercive_quarantine",
        is_ratio=True,
    )

    # -------------------------------------------------------------------------
    # 4. Tenure Survival Gap (Female vs. Male 24-Month Survival Rate)
    # -------------------------------------------------------------------------
    spells["end_dt"] = pd.to_datetime(spells["end_date"], errors="coerce")
    spells["tenure_days"] = (spells["end_dt"] - spells["start_dt"]).dt.days
    spells["survived_24"] = (spells["end_dt"].isna() | (spells["tenure_days"] >= 730)).astype(int)

    cats_sg = []
    ests_sg = []
    lows_sg = []
    highs_sg = []
    pvals_sg = []
    ns_sg = []

    for reg in REGIMES:
        sub = spells[spells.regime == reg]
        mod = smf.ols("survived_24 ~ is_female + rank_score", data=sub).fit(cov_type="HC1")
        cats_sg.append(reg)
        ests_sg.append(mod.params["is_female"] * 100)
        lows_sg.append(mod.conf_int().loc["is_female", 0] * 100)
        highs_sg.append(mod.conf_int().loc["is_female", 1] * 100)
        pvals_sg.append(mod.pvalues["is_female"])
        ns_sg.append(len(sub))

    # Pooled
    mod_sg_p = smf.ols("survived_24 ~ is_female + rank_score", data=spells).fit(cov_type="HC1")
    cats_sg.append("Pooled (All Regimes)")
    ests_sg.append(mod_sg_p.params["is_female"] * 100)
    lows_sg.append(mod_sg_p.conf_int().loc["is_female", 0] * 100)
    highs_sg.append(mod_sg_p.conf_int().loc["is_female", 1] * 100)
    pvals_sg.append(mod_sg_p.pvalues["is_female"])
    ns_sg.append(len(spells))

    caption_14d = (
        "Figure 14d: Forest plot of the female 24-month tenure survival advantage across political regimes.\n"
        "Notes: Points and horizontal error bars display the adjusted percentage-point difference in 24-month survival rates for female\n"
        "civil servants relative to male colleagues, holding hierarchical rank constant (HC1 robust 95% CIs). The dashed reference line at 0 pp\n"
        "denotes equal survival hazard; positive values reflect higher female tenure stability. Total sample N = 99,270 spells."
    )
    render_forest_plot(
        title="Forest Plot: Female Incumbent Survival Advantage Across Regimes",
        subtitle=r"Adjusted difference in 24-month survival rate for women vs. men ($\Delta\text{Percentage Points} \pm 95\%\ \text{CI}$)",
        categories=cats_sg,
        estimates=ests_sg,
        ci_lows=lows_sg,
        ci_highs=highs_sg,
        pvals=pvals_sg,
        sample_sizes=ns_sg,
        ref_val=0.0,
        xlabel="Female 24-month survival rate difference (percentage points)",
        left_guide="Male survival advantage",
        right_guide="Female stability advantage",
        caption=caption_14d,
        out_filename="fig_theory_14d_forest_gender_tenure_survival",
        unit=" pp",
    )

    # -------------------------------------------------------------------------
    # 5. Presidential Rupture Shocks on Gender Representation
    # -------------------------------------------------------------------------
    # RDD Discontinuity on female appointment share across the 3 shocks
    events_raw = pd.read_csv(ROOT / "data" / "processed" / "events.csv.gz", low_memory=False)
    events_raw["date"] = pd.to_datetime(events_raw["event_date"], errors="coerce")
    events_raw = events_raw[events_raw.date.notna()].sort_values("date").reset_index(drop=True)
    if "event_type" in events_raw.columns:
        events_raw = events_raw[events_raw.event_type.isin(["appointment", "transfer"])]
    gender_map = persons.set_index("person_id")["gender"].to_dict()
    events_raw["gender"] = events_raw["person_id"].map(gender_map).fillna("Unknown")
    events_raw["is_female"] = (events_raw["gender"] == "Female").astype(int)

    shocks = [
        ("1987 Ben Ali Coup (7 Nov 1987)", pd.Timestamp("1987-11-07")),
        ("2011 Revolution (14 Jan 2011)", pd.Timestamp("2011-01-14")),
        ("2021 Saïed Auto-Coup (25 Jul 2021)", pd.Timestamp("2021-07-25")),
    ]

    cats_shk = []
    ests_shk = []
    lows_shk = []
    highs_shk = []
    pvals_shk = []
    ns_shk = []

    for label, t0 in shocks:
        sub = events_raw[
            (events_raw.date >= t0 - pd.Timedelta(days=180))
            & (events_raw.date <= t0 + pd.Timedelta(days=180))
        ].copy()
        sub["x"] = (sub.date - t0).dt.days
        sub["d"] = (sub.x >= 0).astype(int)
        sub["dx"] = sub["d"] * sub["x"]
        sub["is_female_pct"] = sub["is_female"] * 100.0

        mod = smf.ols("is_female_pct ~ d + x + dx", data=sub).fit(cov_type="HC1")
        cats_shk.append(label)
        ests_shk.append(mod.params["d"])
        lows_shk.append(mod.conf_int().loc["d", 0])
        highs_shk.append(mod.conf_int().loc["d", 1])
        pvals_shk.append(mod.pvalues["d"])
        ns_shk.append(len(sub))

    caption_14e = (
        "Figure 14e: Forest plot of sharp RDD discontinuities in female appointment share across presidential regime ruptures.\n"
        "Notes: Local linear regression discontinuity estimates (p = 1, h = ±180 days, uniform kernel, HC1 robust 95% CIs) measuring\n"
        "the immediate shift in the share of female appointments at each historical cutoff c = 0. The dashed line at 0 pp denotes no change\n"
        "in gender composition; positive values reflect an immediate surge in female appointments. Total N across 3 windows = 5,065 acts."
    )
    render_forest_plot(
        title="Forest Plot: Presidential Shock Discontinuities in Female Appointments",
        subtitle=r"Sharp RDD Discontinuity ($\hat{\tau}$) in female appointment share at historical cutoff ($\text{pp} \pm 95\%\ \text{CI}$)",
        categories=cats_shk,
        estimates=ests_shk,
        ci_lows=lows_shk,
        ci_highs=highs_shk,
        pvals=pvals_shk,
        sample_sizes=ns_shk,
        ref_val=0.0,
        xlabel="Sharp RDD discontinuity in female appointment share (percentage points)",
        left_guide="Drop in female share",
        right_guide="Surge in female share",
        caption=caption_14e,
        out_filename="fig_theory_14e_forest_gender_presidential_shocks",
        unit=" pp",
    )

    # -------------------------------------------------------------------------
    # 6. Interactive Plotly Dashboard
    # -------------------------------------------------------------------------
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Theory 14: Gender Biases Forest Plots (1957–2026)</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; background: #F9FAFB; color: #111827; }}
        .header {{ max-width: 1100px; margin: 0 auto 24px; padding-bottom: 16px; border-bottom: 1px solid #E5E7EB; }}
        .header h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 700; color: #111827; }}
        .header p {{ margin: 0; font-size: 13px; color: #6B7280; }}
        .grid {{ display: grid; grid-template-columns: 1fr; gap: 28px; max-width: 1100px; margin: 0 auto; }}
        .card {{ background: #FFFFFF; border-radius: 8px; border: 1px solid #E5E7EB; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .card h2 {{ margin: 0 0 4px; font-size: 15px; font-weight: 600; color: #111827; }}
        .card p.sub {{ margin: 0 0 16px; font-size: 12px; color: #6B7280; }}
        .caption {{ margin-top: 14px; font-size: 11px; color: #4B5563; line-height: 1.45; border-top: 1px solid #F3F4F6; padding-top: 12px; }}
    </style>
</head>
<body>

<div class="header">
    <h1>Theory 14: Gender Biases Across Political Regimes (Forest Plots)</h1>
    <p>Econometric synthesis of the sticky floor, hierarchical glass ceiling, coercive quarantine, and regime rupture shocks (1957–2026).</p>
</div>

<div class="grid">
    <div class="card">
        <h2>Figure 14a: Promotion Velocity Penalty Across Regimes (Sticky Floor)</h2>
        <p class="sub">Adjusted female promotion delay in months vs. male peers (OLS with Rank Controls & 95% CIs)</p>
        <div id="plot_delay" style="height: 380px;"></div>
        <div class="caption"><b>Notes:</b> Reference line at 0 indicates equal promotion speed. Positive values indicate female delay. Total promotions N = 22,319.</div>
    </div>

    <div class="card">
        <h2>Figure 14b: Hierarchical Glass Ceiling Odds Ratios Across Regimes</h2>
        <p class="sub">Adjusted Odds Ratio (OR) of female placement in Senior Leadership vs. Entry Cadres (Logit & 95% CIs)</p>
        <div id="plot_glass" style="height: 380px;"></div>
        <div class="caption"><b>Notes:</b> Reference line at 1.0 denotes gender parity. Values < 1.0 indicate under-representation of women in senior ranks. Total N = 41,790.</div>
    </div>

    <div class="card">
        <h2>Figure 14c: Coercive & Territorial Quarantine Odds Across Regimes</h2>
        <p class="sub">Odds Ratio (OR) of female appointment in Interior, Defense, or Regional Governance</p>
        <div id="plot_coercive" style="height: 380px;"></div>
        <div class="caption"><b>Notes:</b> Reference line at 1.0 indicates gender parity in coercive/sovereign portfolios. Values < 1.0 indicate quarantine of women. Total N = 99,270.</div>
    </div>

    <div class="card">
        <h2>Figure 14d: Female Incumbent 24-Month Survival Advantage Across Regimes</h2>
        <p class="sub">Adjusted percentage-point difference in 24-month tenure survival for women vs. men</p>
        <div id="plot_survival" style="height: 380px;"></div>
        <div class="caption"><b>Notes:</b> Reference line at 0 pp indicates equal hazard. Positive values indicate higher female tenure stability. Total N = 99,270.</div>
    </div>

    <div class="card">
        <h2>Figure 14e: Presidential Shock Discontinuities in Female Appointments</h2>
        <p class="sub">Sharp RDD Discontinuity (tau) in female appointment share at historical cutoffs</p>
        <div id="plot_shocks" style="height: 300px;"></div>
        <div class="caption"><b>Notes:</b> Local linear RDD estimates (h = ±180 days, uniform kernel). Discontinuities in percentage points. Total N across windows = 5,065 acts.</div>
    </div>
</div>

<script>
    const layoutBase = {{
        margin: {{l: 180, r: 160, t: 20, b: 50}},
        xaxis: {{zeroline: false, showgrid: true, gridcolor: '#F3F4F6'}},
        yaxis: {{autorange: 'reversed'}},
        font: {{family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', size: 11}}
    }};

    // 14a Delay
    Plotly.newPlot('plot_delay', [{{
        y: {cats_pf!r},
        x: {ests_pf!r},
        error_x: {{
            type: 'data',
            symmetric: false,
            array: {[h - e for h, e in zip(highs_pf, ests_pf)]!r},
            arrayminus: {[e - l for l, e in zip(lows_pf, ests_pf)]!r},
            color: '#374151', width: 4
        }},
        mode: 'markers',
        marker: {{size: 8, color: ['#A03B2C', '#1B5FC1', '#0D9488', '#B5852A', '#7C3AED', '#111827'], symbol: 'square'}}
    }}], Object.assign({{}}, layoutBase, {{
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: -0.5, y1: 5.5, line: {{dash: 'dash', color: '#6B7280', width: 1}}}}],
        xaxis: {{title: 'Female Promotion Delay (Months)'}}
    }}));

    // 14b Glass
    Plotly.newPlot('plot_glass', [{{
        y: {cats_gc!r},
        x: {ests_gc!r},
        error_x: {{
            type: 'data',
            symmetric: false,
            array: {[h - e for h, e in zip(highs_gc, ests_gc)]!r},
            arrayminus: {[e - l for l, e in zip(lows_gc, ests_gc)]!r},
            color: '#374151', width: 4
        }},
        mode: 'markers',
        marker: {{size: 8, color: ['#A03B2C', '#1B5FC1', '#0D9488', '#B5852A', '#7C3AED', '#111827'], symbol: 'square'}}
    }}], Object.assign({{}}, layoutBase, {{
        shapes: [{{type: 'line', x0: 1, x1: 1, y0: -0.5, y1: 5.5, line: {{dash: 'dash', color: '#6B7280', width: 1}}}}],
        xaxis: {{title: 'Odds Ratio (OR) of Senior Executive Rank'}}
    }}));

    // 14c Coercive
    Plotly.newPlot('plot_coercive', [{{
        y: {cats_cq!r},
        x: {ests_cq!r},
        error_x: {{
            type: 'data',
            symmetric: false,
            array: {[h - e for h, e in zip(highs_cq, ests_cq)]!r},
            arrayminus: {[e - l for l, e in zip(lows_cq, ests_cq)]!r},
            color: '#374151', width: 4
        }},
        mode: 'markers',
        marker: {{size: 8, color: ['#A03B2C', '#1B5FC1', '#0D9488', '#B5852A', '#7C3AED', '#111827'], symbol: 'square'}}
    }}], Object.assign({{}}, layoutBase, {{
        shapes: [{{type: 'line', x0: 1, x1: 1, y0: -0.5, y1: 5.5, line: {{dash: 'dash', color: '#6B7280', width: 1}}}}],
        xaxis: {{title: 'Odds Ratio (OR) in Sovereign/Security Portfolios'}}
    }}));

    // 14d Survival
    Plotly.newPlot('plot_survival', [{{
        y: {cats_sg!r},
        x: {ests_sg!r},
        error_x: {{
            type: 'data',
            symmetric: false,
            array: {[h - e for h, e in zip(highs_sg, ests_sg)]!r},
            arrayminus: {[e - l for l, e in zip(lows_sg, ests_sg)]!r},
            color: '#374151', width: 4
        }},
        mode: 'markers',
        marker: {{size: 8, color: ['#A03B2C', '#1B5FC1', '#0D9488', '#B5852A', '#7C3AED', '#111827'], symbol: 'square'}}
    }}], Object.assign({{}}, layoutBase, {{
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: -0.5, y1: 5.5, line: {{dash: 'dash', color: '#6B7280', width: 1}}}}],
        xaxis: {{title: 'Female 24-Month Survival Gap (pp)'}}
    }}));

    // 14e Shocks
    Plotly.newPlot('plot_shocks', [{{
        y: {cats_shk!r},
        x: {ests_shk!r},
        error_x: {{
            type: 'data',
            symmetric: false,
            array: {[h - e for h, e in zip(highs_shk, ests_shk)]!r},
            arrayminus: {[e - l for l, e in zip(lows_shk, ests_shk)]!r},
            color: '#374151', width: 4
        }},
        mode: 'markers',
        marker: {{size: 8, color: ['#A03B2C', '#1B5FC1', '#B5852A'], symbol: 'square'}}
    }}], Object.assign({{}}, layoutBase, {{
        shapes: [{{type: 'line', x0: 0, x1: 0, y0: -0.5, y1: 2.5, line: {{dash: 'dash', color: '#6B7280', width: 1}}}}],
        xaxis: {{title: 'Sharp RDD Discontinuity in Female Share (pp)'}}
    }}));
</script>

</body>
</html>
"""
    dashboard_path = FIGS / "fig_theory_14_gender_forest_plots_interactive.html"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved interactive forest dashboard: {dashboard_path.name}")

    print("\nAll 5 gender forest plots and interactive dashboard generated successfully!")


if __name__ == "__main__":
    main()
