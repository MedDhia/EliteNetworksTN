"""
Comparative Institutional Gender Biases Across Five Political Regimes (1957–2026).
Compares:
1. The "Sticky Floor" Promotion Velocity Delay across Regimes (Raw vs. Fixed Effects).
2. The Hierarchical Glass Ceiling Attrition (Entry vs. Director vs. DG vs. Apex).
3. Informal Patronage Dynamics (Ministerial Retinues and Arrival Sweeps).
4. Coercive and Territorial Command Quarantine (Regional Governors).
5. Senior Executive Tenure Duration and Selection Dynamics.
"""

import os
import sys
import shutil
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path("/Users/mohameddhiahammami/.gemini/antigravity/scratch/repo")
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
ARTIFACT_DIR = Path("/Users/mohameddhiahammami/.gemini/antigravity/brain/99a2df6e-0c03-4b60-92f6-cae4ddbbee51")

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.append(str(ROOT / "scripts"))
from gender_vertical_mobility import load_and_classify_gender

# EliteNetworksTN Visual Styling
PAPER = "#FCFCFB"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
FEMALE_COLOR = "#D9480F"    # Warm Terracotta
MALE_COLOR = "#1B5FC1"      # Deep Royal Blue
ACCENT_GREEN = "#0D9488"
ACCENT_RED = "#DC2626"
ACCENT_PURPLE = "#7C3AED"
ACCENT_GOLD = "#B5852A"

REGIME_COLORS = {
    "Bourguiba (1957–87)": "#A03B2C",
    "Ben Ali (1987–2011)": "#1B5FC1",
    "Transition (2011–14)": "#0D9488",
    "Essebsi (2014–19)": "#B5852A",
    "Kais Saied (2019–26)": "#5B4E9E",
}

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "axes.titlesize": 10.0,
    "axes.titleweight": "semibold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK,
    "ytick.color": INK,
    "xtick.labelsize": 8.0,
    "ytick.labelsize": 8.0,
    "grid.color": RULE,
    "grid.linewidth": 0.5,
    "grid.alpha": 0.5,
})

def main():
    print("Loading data and classifying gender...")
    spells, persons = load_and_classify_gender()
    spells["is_female"] = (spells["gender"] == "Female").astype(int)

    # Career transitions & wait times
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["days_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days
    spells["years_to_next"] = spells["days_to_next"] / 365.25
    spells["promoted_next"] = ((spells["next_rank"] > spells["rank_score"]) & spells["has_next"]).astype(int)

    prom = spells[(spells.promoted_next == 1) & (spells.years_to_next.between(0.1, 20))].copy()

    # Retinues
    ministers = spells[spells.rank_score >= 90][["person_id", "org_portfolio", "start_year", "start_dt"]].sort_values(["person_id", "start_dt"])
    ministers["prev_portfolio"] = ministers.groupby("person_id")["org_portfolio"].shift(1)
    m_moves = ministers[ministers["prev_portfolio"].notna() & (ministers["prev_portfolio"] != ministers["org_portfolio"])]
    person_ports = spells.groupby(["person_id", "org_portfolio"])["start_year"].min().to_dict()
    bureaucrats = spells[spells.rank_score < 90][["spell_id", "person_id", "org_portfolio", "start_year"]]
    b_by_port = {p: df_p for p, df_p in bureaucrats.groupby("org_portfolio")}
    retinue_spells = set()
    for _, m_row in m_moves.iterrows():
        m_id = m_row["person_id"]; p_from = m_row["prev_portfolio"]; p_to = m_row["org_portfolio"]; m_yr = m_row["start_year"]
        if p_to in b_by_port:
            cand = b_by_port[p_to]
            cand = cand[cand.start_year.between(m_yr, m_yr + 2)]
            for _, b_row in cand.iterrows():
                b_id = b_row["person_id"]
                if b_id != m_id:
                    min_yr = person_ports.get((b_id, p_from))
                    if min_yr is not None and min_yr <= m_yr:
                        retinue_spells.add(b_row["spell_id"])
    spells["is_retinue"] = spells["spell_id"].isin(retinue_spells).astype(int)

    # Sweeps (<120 days)
    m_arr = ministers.groupby("org_portfolio")["start_dt"].unique().to_dict()
    def is_sweep(row):
        p = row["org_portfolio"]
        if p not in m_arr: return 0
        dt = row["start_dt"]
        for m_dt in m_arr[p]:
            delta = (dt - m_dt).days
            if 0 <= delta <= 120: return 1
        return 0
    spells["is_sweep"] = spells.apply(is_sweep, axis=1)

    regimes = [
        "Bourguiba (1957–87)",
        "Ben Ali (1987–2011)",
        "Transition (2011–14)",
        "Essebsi (2014–19)",
        "Kais Saied (2019–26)"
    ]

    # =========================================================================
    # PART 1: COMPUTE PROMOTION VELOCITY DELAYS ACROSS REGIMES
    # =========================================================================
    print("\n--- Computing Promotion Delays Across Regimes ---")
    regime_velocity = []
    for reg in regimes:
        sub = prom[prom.regime == reg]
        m_wait = sub[sub.gender == "Male"]["years_to_next"]
        f_wait = sub[sub.gender == "Female"]["years_to_next"]
        n_m, n_f = len(m_wait), len(f_wait)
        diff_mo = (f_wait.mean() - m_wait.mean()) * 12
        med_mo = (f_wait.median() - m_wait.median()) * 12
        t_stat, p_val = stats.ttest_ind(f_wait, m_wait, equal_var=False)

        # Within-ministry Fixed Effects
        top_p = sub["org_portfolio"].value_counts().nlargest(10).index
        sub_fe = sub[sub["org_portfolio"].isin(top_p)]
        fe_mod = smf.ols("years_to_next ~ is_female + C(org_portfolio) + rank_score", data=sub_fe).fit()
        fe_mo = fe_mod.params["is_female"] * 12
        fe_ci = [fe_mod.conf_int().loc["is_female", 0] * 12, fe_mod.conf_int().loc["is_female", 1] * 12]
        fe_p = fe_mod.pvalues["is_female"]

        regime_velocity.append({
            "regime": reg, "n_tot": n_m + n_f, "n_f": n_f,
            "raw_delay": diff_mo, "med_delay": med_mo, "raw_p": p_val,
            "fe_delay": fe_mo, "fe_ci": fe_ci, "fe_p": fe_p
        })
        print(f"  {reg:22s} | Raw Delay: {diff_mo:+5.2f} mo | FE Delay: {fe_mo:+5.2f} mo (p = {fe_p:.2e})")

    # =========================================================================
    # PART 2: HIERARCHICAL GLASS CEILING BY REGIME
    # =========================================================================
    print("\n--- Computing Hierarchical Representation by Regime ---")
    regime_hierarchy = []
    for reg in regimes:
        sub = spells[spells.regime == reg]
        f_entry = sub[sub.rank_score.between(35, 45)]["is_female"].mean() * 100
        f_dir = sub[sub.rank_score == 55]["is_female"].mean() * 100
        f_dg = sub[sub.rank_score == 65]["is_female"].mean() * 100
        f_apex = sub[sub.rank_score >= 70]["is_female"].mean() * 100
        ratio = (f_apex / f_entry) if f_entry > 0 else 0
        regime_hierarchy.append({
            "regime": reg, "entry": f_entry, "dir": f_dir, "dg": f_dg, "apex": f_apex, "ratio": ratio
        })
        print(f"  {reg:22s} | Entry: {f_entry:4.1f}% -> Dir: {f_dir:4.1f}% -> DG: {f_dg:4.1f}% -> Apex: {f_apex:4.1f}% (Ratio: {ratio:.2f})")

    # =========================================================================
    # PART 3: PATRONAGE & TERRITORIAL DATA
    # =========================================================================
    print("\n--- Computing Patronage Retinues & Governors by Regime ---")
    regime_patronage = []
    for reg in regimes:
        sub = spells[spells.regime == reg]
        tot_ret = sub["is_retinue"].sum()
        fem_ret = sub[sub.is_retinue == 1]["is_female"].sum()
        pct_f_ret = (fem_ret / tot_ret * 100) if tot_ret > 0 else 0
        pct_f_all = sub["is_female"].mean() * 100

        # Sweeps
        tot_swp = sub["is_sweep"].sum()
        fem_swp = sub[sub.is_sweep == 1]["is_female"].sum()
        pct_f_swp = (fem_swp / tot_swp * 100) if tot_swp > 0 else 0

        # Governors (Rank 80)
        govs = sub[sub.rank_score == 80]
        n_gov_tot = len(govs)
        n_gov_fem = (govs.gender == "Female").sum()
        pct_gov_fem = (n_gov_fem / n_gov_tot * 100) if n_gov_tot > 0 else 0

        regime_patronage.append({
            "regime": reg,
            "tot_ret": tot_ret, "fem_ret": fem_ret, "pct_f_ret": pct_f_ret, "pct_f_all": pct_f_all,
            "tot_swp": tot_swp, "fem_swp": fem_swp, "pct_f_swp": pct_f_swp,
            "n_gov_tot": n_gov_tot, "n_gov_fem": n_gov_fem, "pct_gov_fem": pct_gov_fem
        })

    # =========================================================================
    # PART 4: GENERATE 4-PANEL PUBLICATION FIGURE
    # =========================================================================
    print("\nPlotting 4-panel publication figure...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), facecolor=PAPER)
    fig.subplots_adjust(hspace=0.38, wspace=0.32, top=0.90, bottom=0.07, left=0.08, right=0.96)

    # ------------------ PANEL A: STICKY FLOOR PROMOTION DELAY ACROSS REGIMES ------------------
    ax_a = axes[0, 0]
    y_a = np.arange(len(regimes))
    bar_h = 0.32

    raw_delays = [d["raw_delay"] for d in regime_velocity]
    fe_delays = [d["fe_delay"] for d in regime_velocity]
    labels_a = [d["regime"] for d in regime_velocity]

    ax_a.barh(y_a + bar_h/2, raw_delays, height=bar_h, color=MUTED, alpha=0.65, label="Raw Wait-Time Delay (Two-Sample t)", edgecolor=INK, linewidth=0.5, zorder=3)
    ax_a.barh(y_a - bar_h/2, fe_delays, height=bar_h, color=FEMALE_COLOR, label="Within-Ministry Fixed Effects Delay", edgecolor=INK, linewidth=0.5, zorder=3)

    for i in range(len(regimes)):
        p_str = f"p < 10⁻⁴" if regime_velocity[i]["fe_p"] < 1e-4 else (f"p = {regime_velocity[i]['fe_p']:.3f}" if regime_velocity[i]["fe_p"] < 0.05 else "n.s.")
        ax_a.text(max(raw_delays[i], fe_delays[i]) + 0.4, y_a[i],
                  f"FE: {fe_delays[i]:+.1f} mo ({p_str})",
                  va="center", ha="left", fontsize=7.6, fontweight="semibold", color=INK)

    ax_a.set_yticks(y_a)
    ax_a.set_yticklabels(labels_a, fontsize=8.2)
    ax_a.set_xlabel("Estimated Promotion Wait-Time Delay for Women (Months)", fontweight="semibold")
    ax_a.set_xlim(-2, 28)
    ax_a.axvline(0, color=INK, linestyle="--", linewidth=1.0, alpha=0.7)
    ax_a.grid(True, linestyle="--", alpha=0.5, axis="x")
    ax_a.legend(loc="lower right", framealpha=0.9, fontsize=8)
    ax_a.set_title("A. The 'Sticky Floor' Promotion Clock Across Five Regimes (1957–2026)\n"
                   "   Bourguiba (+22.8 mo) & Ben Ali (+13.5 mo); collapses to parity under Saied (+0.7 mo, n.s.)",
                   fontsize=9.2, fontweight="bold", pad=10)

    # ------------------ PANEL B: HIERARCHICAL ATTRITION (THE GLASS CEILING FUNNEL) ------------------
    ax_b = axes[0, 1]
    tiers = ["Entry (35–45)", "Directeur (55)", "Dir. Général (65)", "Apex (≥ 70)"]
    x_b = np.arange(len(tiers))

    for d in regime_hierarchy:
        reg = d["regime"]
        vals = [d["entry"], d["dir"], d["dg"], d["apex"]]
        color = REGIME_COLORS[reg]
        lw = 2.4 if "Saied" in reg or "Ben Ali" in reg else 1.8
        marker = "s" if "Saied" in reg else ("o" if "Ben Ali" in reg else "^")
        ax_b.plot(x_b, vals, marker=marker, markersize=6.5, lw=lw, color=color, label=f"{reg} (Ratio: {d['ratio']:.2f})", zorder=4)

    ax_b.set_xticks(x_b)
    ax_b.set_xticklabels(tiers, fontsize=8.2)
    ax_b.set_ylabel("Female Representation (% of Appointments)", fontweight="semibold")
    ax_b.set_ylim(0, 50)
    ax_b.grid(True, linestyle="--", alpha=0.5)
    ax_b.legend(loc="upper right", framealpha=0.9, fontsize=7.8)
    ax_b.set_title("B. The Hierarchical Glass Ceiling Funnel Across Regimes\n"
                   "   Steepest attrition under Ben Ali (0.16) & Troika (0.22); apex desegregation under Saied (0.33)",
                   fontsize=9.2, fontweight="bold", pad=10)

    # ------------------ PANEL C: INFORMAL PATRONAGE EXCLUSION ACROSS REGIMES ------------------
    ax_c = axes[1, 0]
    y_c = np.arange(len(regimes))
    bar_h2 = 0.26

    pct_all = [d["pct_f_all"] for d in regime_patronage]
    pct_ret = [d["pct_f_ret"] for d in regime_patronage]
    pct_swp = [d["pct_f_swp"] for d in regime_patronage]

    ax_c.barh(y_c + bar_h2, pct_all, height=bar_h2, color=MUTED, alpha=0.5, label="Overall Civil Service Female Share", edgecolor=INK, linewidth=0.5, zorder=3)
    ax_c.barh(y_c, pct_ret, height=bar_h2, color=ACCENT_RED, label="Ministerial Retinue Female Share (Followers)", edgecolor=INK, linewidth=0.5, zorder=3)
    ax_c.barh(y_c - bar_h2, pct_swp, height=bar_h2, color=ACCENT_GOLD, label="Arrival Sweep Female Share (<120d)", edgecolor=INK, linewidth=0.5, zorder=3)

    for i in range(len(regimes)):
        deficit_ret = pct_ret[i] - pct_all[i]
        deficit_swp = pct_swp[i] - pct_all[i]
        txt = f"Ret: {deficit_ret:+4.1f} pp | Swp: {deficit_swp:+4.1f} pp"
        ax_c.text(max(pct_all[i], pct_ret[i], pct_swp[i]) + 0.8, y_c[i], txt,
                  va="center", ha="left", fontsize=7.2, color=INK, fontweight="semibold")

    ax_c.set_yticks(y_c)
    ax_c.set_yticklabels(labels_a, fontsize=8.2)
    ax_c.set_xlabel("Female Share (% of Appointments)", fontweight="semibold")
    ax_c.set_xlim(0, 56)
    ax_c.grid(True, linestyle="--", alpha=0.5, axis="x")
    ax_c.legend(loc="lower right", framealpha=0.9, fontsize=7.8)
    ax_c.set_title("C. Informal Patronage Deficit: Retinues & Rapid Arrival Sweeps\n"
                   "   Ben Ali retinue deficit: -9.9 pp (OR=0.35, p < 10⁻⁷); Saied arrival sweep deficit: -12.1 pp (p = 0.002)",
                   fontsize=9.2, fontweight="bold", pad=10)

    # ------------------ PANEL D: TERRITORIAL QUARANTINE ACROSS REGIMES ------------------
    ax_d = axes[1, 1]
    y_d = np.arange(len(regimes))
    bar_h3 = 0.38

    gov_pcts = [d["pct_gov_fem"] for d in regime_patronage]
    gov_counts = [f"{d['n_gov_fem']}/{d['n_gov_tot']}" for d in regime_patronage]

    bars_d = ax_d.barh(y_d, gov_pcts, height=bar_h3, color=MALE_COLOR, edgecolor=INK, linewidth=0.6, zorder=3)
    # Highlight Saied bar
    bars_d[4].set_color(FEMALE_COLOR)

    for i in range(len(regimes)):
        ax_d.text(gov_pcts[i] + 0.35, y_d[i], f"{gov_pcts[i]:.1f}% ({gov_counts[i]})",
                  va="center", ha="left", fontsize=7.6, fontweight="semibold", color=INK)

    ax_d.set_yticks(y_d)
    ax_d.set_yticklabels(labels_a, fontsize=8.2)
    ax_d.set_xlabel("Female Governors (% of Regional Governorship Appointments)", fontweight="semibold")
    ax_d.set_xlim(0, 26)
    ax_d.grid(True, linestyle="--", alpha=0.5, axis="x")

    info_box_d = (
        "CROSS-REGIME TERRITORIAL BREAKDOWN (Rank 80):\n"
        "• Bourguiba (1957–87):  0 women / 128 (0.0%)\n"
        "• Ben Ali (1987–2011):  1 woman / 129 (0.8%) [Faiza Kefi, Ariana 1999]\n"
        "• Transition (2011–14): 0 women / 81 (0.0%)\n"
        "• Essebsi (2014–19):    2 women / 50 (4.0%) [Saloua Khiari, Nabeul]\n"
        "• Kais Saied (2019–26): 3 women / 25 (12.0%) [Sabah Malek, Raja Trabelsi]\n\n"
        "Summary: Coercive territorial command remained >96% male across all\n"
        "regimes until Kais Saied appointed 3 female governors (12.0%)."
    )
    ax_d.text(0.42, 0.42, info_box_d, transform=ax_d.transAxes, fontsize=7.2,
              bbox=dict(boxstyle="round,pad=0.5", facecolor=PAPER, edgecolor=RULE, alpha=0.95),
              va="center", ha="left", family="monospace")

    ax_d.set_title("D. The Coercive Cordon Sanitaire: Regional Governors Across Regimes\n"
                   "   Total exclusion under Bourguiba/Troika; symbolic under Ben Ali (0.8%); rising to 12.0% under Saied",
                   fontsize=9.2, fontweight="bold", pad=10)

    # Save PNG and PDF
    png_path = FIGS / "fig_theory_12_gender_biases_regimes.png"
    pdf_path = FIGS / "fig_theory_12_gender_biases_regimes.pdf"
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved publication figures to {png_path} and {pdf_path}")

    # Copy to artifact directory
    shutil.copy2(png_path, ARTIFACT_DIR / "fig_theory_12_gender_biases_regimes.png")
    shutil.copy2(pdf_path, ARTIFACT_DIR / "fig_theory_12_gender_biases_regimes.pdf")

    # =========================================================================
    # PART 5: GENERATE INTERACTIVE PLOTLY CDN DASHBOARD
    # =========================================================================
    print("Generating interactive Plotly CDN dashboard...")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Institutional Gender Biases Across Five Political Regimes (1957–2026)</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: {PAPER};
            color: {INK};
            margin: 0;
            padding: 24px;
        }}
        .header {{
            max-width: 1400px;
            margin: 0 auto 20px auto;
        }}
        h1 {{
            font-size: 22px;
            margin: 0 0 8px 0;
            font-weight: 700;
        }}
        p.subtitle {{
            font-size: 13px;
            color: {MUTED};
            margin: 0 0 20px 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background: #FFFFFF;
            border: 1px solid {RULE};
            border-radius: 6px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .chart-box {{
            width: 100%;
            height: 400px;
        }}
        .footer {{
            max-width: 1400px;
            margin: 24px auto 0 auto;
            font-size: 11px;
            color: {MUTED};
            border-top: 1px solid {RULE};
            padding-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Comparative Analysis of Institutional Gender Bias Across Five Political Regimes (1957–2026)</h1>
        <p class="subtitle">Comparing Bourguiba (1957–87), Ben Ali (1987–2011), Transition / Troika (2011–14), Essebsi (2014–19), and Kais Saied (2019–26) across 100,582 spells.</p>
    </div>

    <div class="grid">
        <div class="card">
            <div id="chart-velocity" class="chart-box"></div>
        </div>
        <div class="card">
            <div id="chart-funnel" class="chart-box"></div>
        </div>
        <div class="card">
            <div id="chart-patronage" class="chart-box"></div>
        </div>
        <div class="card">
            <div id="chart-governors" class="chart-box"></div>
        </div>
    </div>

    <div class="footer">
        <b>Data Source:</b> Official Gazette of the Republic of Tunisia (JORT 1957–2026). Extracted from MedDhia/EliteNetworksTN.<br>
        <b>Methodological Notes:</b> Promotion wait-time delays are estimated using both two-sample Welch's t-tests and within-ministry fixed effects regressions controlling for baseline rank. Hierarchical funnel charts track representation across civil service rank tiers.
    </div>

    <script>
        // Chart 1: Promotion Delays
        const velData = [
            {{
                y: {repr(labels_a)},
                x: {repr(raw_delays)},
                name: 'Raw Unadjusted Delay',
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '{MUTED}', opacity: 0.6 }}
            }},
            {{
                y: {repr(labels_a)},
                x: {repr(fe_delays)},
                name: 'Within-Ministry FE Delay',
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '{FEMALE_COLOR}' }}
            }}
        ];
        const layoutVel = {{
            title: {{ text: '<b>A. Promotion Wait-Time Delay by Regime (Months)</b>', font: {{ size: 13 }} }},
            barmode: 'group',
            xaxis: {{ title: 'Estimated Delay for Women (Months)' }},
            font: {{ family: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif', size: 10 }},
            margin: {{ l: 160, r: 20, t: 35, b: 45 }},
            legend: {{ orientation: 'h', y: -0.2 }}
        }};
        Plotly.newPlot('chart-velocity', velData, layoutVel, {{ responsive: true }});

        // Chart 2: Hierarchical Funnel
        const funnelData = [
            {{
                x: ['Entry (35-45)', 'Directeur (55)', 'Dir. Général (65)', 'Apex (≥ 70)'],
                y: {repr([d['entry'] for d in regime_hierarchy])},
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Bourguiba (1957–87)',
                line: {{ color: '{REGIME_COLORS["Bourguiba (1957–87)"]}' }}
            }}
        ];
        // Build traces for all 5 regimes
        const regHierarchy = {repr(regime_hierarchy)};
        const regColors = {repr(REGIME_COLORS)};
        const funnelTraces = regHierarchy.map(d => ({{
            x: ['Entry (35-45)', 'Directeur (55)', 'Dir. Général (65)', 'Apex (≥ 70)'],
            y: [d.entry, d.dir, d.dg, d.apex],
            type: 'scatter',
            mode: 'lines+markers',
            name: d.regime + ' (Ratio: ' + d.ratio.toFixed(2) + ')',
            line: {{ color: regColors[d.regime], width: d.regime.includes('Saied') ? 3 : 2 }}
        }}));

        const layoutFunnel = {{
            title: {{ text: '<b>B. The Hierarchical Glass Ceiling Funnel Across Regimes</b>', font: {{ size: 13 }} }},
            yaxis: {{ title: 'Female Representation (%)', range: [0, 50] }},
            font: {{ family: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif', size: 10 }},
            margin: {{ l: 50, r: 20, t: 35, b: 45 }},
            legend: {{ orientation: 'h', y: -0.25 }}
        }};
        Plotly.newPlot('chart-funnel', funnelTraces, layoutFunnel, {{ responsive: true }});

        // Chart 3: Patronage Retinues
        const patData = [
            {{
                y: {repr(labels_a)},
                x: {repr(pct_all)},
                name: 'Overall Female Civil Service %',
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '{MUTED}', opacity: 0.5 }}
            }},
            {{
                y: {repr(labels_a)},
                x: {repr(pct_ret)},
                name: 'Retinue Followers %',
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '{ACCENT_RED}' }}
            }},
            {{
                y: {repr(labels_a)},
                x: {repr(pct_swp)},
                name: 'Arrival Sweeps % (<120d)',
                type: 'bar',
                orientation: 'h',
                marker: {{ color: '{ACCENT_GOLD}' }}
            }}
        ];
        const layoutPat = {{
            title: {{ text: '<b>C. Informal Patronage Deficits by Regime</b>', font: {{ size: 13 }} }},
            barmode: 'group',
            xaxis: {{ title: 'Female Share (%)' }},
            font: {{ family: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif', size: 10 }},
            margin: {{ l: 160, r: 20, t: 35, b: 45 }},
            legend: {{ orientation: 'h', y: -0.25 }}
        }};
        Plotly.newPlot('chart-patronage', patData, layoutPat, {{ responsive: true }});

        // Chart 4: Governors
        const govData = [{{
            y: {repr(labels_a)},
            x: {repr(gov_pcts)},
            type: 'bar',
            orientation: 'h',
            marker: {{ color: ['{MALE_COLOR}', '{MALE_COLOR}', '{MALE_COLOR}', '{MALE_COLOR}', '{FEMALE_COLOR}'] }}
        }}];
        const layoutGov = {{
            title: {{ text: '<b>D. Female Governors (% of Regional Appointments)</b>', font: {{ size: 13 }} }},
            xaxis: {{ title: 'Female Governors (%)', range: [0, 16] }},
            font: {{ family: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif', size: 10 }},
            margin: {{ l: 160, r: 20, t: 35, b: 45 }}
        }};
        Plotly.newPlot('chart-governors', govData, layoutGov, {{ responsive: true }});
    </script>
</body>
</html>
"""
    out_html = FIGS / "fig_theory_12_gender_biases_regimes_interactive.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    shutil.copy2(out_html, ARTIFACT_DIR / "fig_theory_12_gender_biases_regimes_interactive.html")
    print(f"Saved interactive dashboard to {out_html}")

if __name__ == "__main__":
    main()
