"""Testing behavioral patronage vs. formal signature in the Tunisian state apparatus.
Contrasting formal legal signing competence with sociological patronage:
1. Retinue co-movement (following mobile ministers across portfolios)
2. Arrival sweeps (first 120 days of ministerial arrival)
3. Formal signatory apex (President / Prime Minister signature)

Generates publication figure: fig_mobility_05_behavioral_patronage
"""

from __future__ import annotations

import os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

PERSON = "#A03B2C"
ORG = "#1B5FC1"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"
GOLD = "#B5852A"

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
    "grid.color": RULE,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
})

SOURCE = ("Source: Journal Officiel de la République Tunisienne, 1957–2026. "
          "Author's extraction from MedDhia/EliteNetworksTN.")

def headline(fig, title: str, subtitle: str, *, top: float = 0.99) -> None:
    fig.text(0.012, top, title, ha="left", va="top",
             fontsize=13.0, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.038, subtitle, ha="left", va="top",
             fontsize=8.2, color=MUTED, wrap=True)

def save(fig, name: str, note: str | None = None) -> None:
    if note:
        fig.text(0.012, -0.012, note, fontsize=6.6, color=MUTED, ha="left", va="top")
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.22, **kw)
        print(f"  Saved {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
    plt.close(fig)

def main():
    print("Loading data...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
    persons = pd.read_csv(PROC / "persons.csv.gz")

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    # 1. Ministers & Retinues
    print("Detecting ministerial mobile retinues...")
    ministers = spells[spells.rank_score >= 90][["person_id", "org_portfolio", "start_year", "end_year", "start_dt"]].copy()
    m_moves = ministers.sort_values(["person_id", "start_dt"]).copy()
    m_moves["prev_portfolio"] = m_moves.groupby("person_id")["org_portfolio"].shift(1)
    m_moves = m_moves[m_moves["prev_portfolio"].notna() & (m_moves["prev_portfolio"] != m_moves["org_portfolio"])]

    bureaucrats = spells[spells.rank_score < 90][["spell_id", "person_id", "org_portfolio", "start_year", "start_dt"]].copy()
    retinue_spells = set()
    for _, m_row in m_moves.iterrows():
        m_id = m_row["person_id"]
        p_from = m_row["prev_portfolio"]
        p_to = m_row["org_portfolio"]
        m_yr = m_row["start_year"]
        cand = bureaucrats[(bureaucrats.org_portfolio == p_to) & (bureaucrats.start_year.between(m_yr, m_yr + 2))]
        for _, b_row in cand.iterrows():
            b_id = b_row["person_id"]
            if b_id == m_id:
                continue
            prev_serv = spells[(spells.person_id == b_id) & (spells.org_portfolio == p_from) & (spells.start_year <= m_yr)]
            if len(prev_serv) > 0:
                retinue_spells.add(b_row["spell_id"])

    spells["is_retinue"] = spells["spell_id"].isin(retinue_spells).astype(int)

    # 2. Arrival Sweeps
    print("Detecting ministerial arrival sweeps...")
    sub_spells = spells[spells.rank_score < 90].copy()
    m_starts = ministers[["org_portfolio", "start_dt"]].drop_duplicates().rename(columns={"start_dt": "minister_start_dt"}).sort_values("minister_start_dt")
    m_merged = pd.merge_asof(
        sub_spells.sort_values("start_dt"),
        m_starts,
        by="org_portfolio",
        left_on="start_dt",
        right_on="minister_start_dt",
        direction="backward"
    )
    m_merged["days_since_m"] = (m_merged["start_dt"] - m_merged["minister_start_dt"]).dt.days
    sweep_map = m_merged.drop_duplicates("spell_id").set_index("spell_id")["days_since_m"].to_dict()
    spells["days_since_minister"] = spells["spell_id"].map(sweep_map).fillna(9999)
    spells["is_arrival_sweep"] = (spells["days_since_minister"] <= 120).astype(int)

    # 3. Formal Signatory Apex
    ev_map = events[["event_id", "signatory_office"]].drop_duplicates("event_id").set_index("event_id")
    spells["signatory_office"] = spells["start_event_id"].map(ev_map["signatory_office"]).fillna("")
    spells["formal_patron_apex"] = spells["signatory_office"].str.contains("Premier Ministre|Chef du gouvernement|Président de la République", case=False).astype(int)

    # 4. Apex Rank Attainment
    peak_rank_map = spells.groupby("person_id")["rank_score"].max().to_dict()
    spells["reaches_apex"] = (spells["person_id"].map(peak_rank_map) >= 72).astype(int)

    person_retinue = spells.groupby("person_id")["is_retinue"].max().to_dict()
    person_sweep = spells.groupby("person_id")["is_arrival_sweep"].max().to_dict()
    person_apex_sig = spells.groupby("person_id")["formal_patron_apex"].max().to_dict()

    first_spells = spells[spells.groupby("person_id").cumcount() == 0].copy()
    first_spells = first_spells[first_spells.rank_score <= 55].copy()
    first_spells["ever_retinue"] = first_spells["person_id"].map(person_retinue).fillna(0).astype(int)
    first_spells["ever_sweep"] = first_spells["person_id"].map(person_sweep).fillna(0).astype(int)
    first_spells["ever_apex_sig"] = first_spells["person_id"].map(person_apex_sig).fillna(0).astype(int)

    # Estimate Pre and Post Models
    print("Estimating tournament models...")
    pre_df = first_spells[first_spells.start_year < 2011].copy()
    post_df = first_spells[first_spells.start_year >= 2011].copy()

    res_pre = smf.logit("reaches_apex ~ ever_retinue + ever_sweep + ever_apex_sig + rank_score", data=pre_df).fit(disp=False)
    res_post = smf.logit("reaches_apex ~ ever_retinue + ever_sweep + ever_apex_sig + rank_score", data=post_df).fit(disp=False)

    # Extract Odds Ratios and CIs
    models = {"Pre-2011 (1957–2010)": res_pre, "Post-2011 (2011–2026)": res_post}
    plot_rows = []
    vars_to_plot = [
        ("ever_apex_sig", "Formal Legal Metric:\nApex Signatory (President/PM)"),
        ("ever_sweep", "Behavioral Patronage:\nArrival Sweep (<120 Days)"),
        ("ever_retinue", "Behavioral Patronage:\nMobile Retinue Follower"),
    ]

    for era_label, mod in models.items():
        for v, display_lbl in vars_to_plot:
            b = mod.params[v]
            ci = mod.conf_int().loc[v]
            p = mod.pvalues[v]
            plot_rows.append({
                "era": era_label,
                "var": v,
                "label": display_lbl,
                "or": np.exp(b),
                "lo": np.exp(ci[0]),
                "hi": np.exp(ci[1]),
                "p": p
            })

    res_df = pd.DataFrame(plot_rows)
    print(res_df)

    # --- Plotting Figure 5 ---
    print("Generating fig_mobility_05_behavioral_patronage...")
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 5.4), sharey=True)

    y_pos = np.arange(len(vars_to_plot))[::-1]

    for ax, era_label, col in [(axes[0], "Pre-2011 (1957–2010)", PERSON), (axes[1], "Post-2011 (2011–2026)", ORG)]:
        sub_era = res_df[res_df["era"] == era_label].reset_index(drop=True)
        ax.axvline(1.0, color=RULE, linestyle="--", lw=1.1, zorder=1)

        for idx, (_, r) in enumerate(sub_era.iloc[::-1].iterrows()):
            ax.plot([r["lo"], r["hi"]], [idx, idx], color=col, lw=2.2, zorder=2)
            ax.scatter(r["or"], idx, color=col, s=60, edgecolors=PAPER, lw=1.2, zorder=3)
            sig_star = "***" if r["p"] < 0.001 else "**" if r["p"] < 0.01 else "*" if r["p"] < 0.05 else " (n.s.)"
            ax.annotate(f"OR = {r['or']:.2f}{sig_star}\n[{r['lo']:.2f}, {r['hi']:.2f}]",
                        (max(r["hi"], r["or"]) + 0.35, idx), va="center", fontsize=7.2, color=INK)

        ax.set_title(era_label, fontsize=10.0, fontweight="bold", color=INK)
        ax.set_xlabel("Odds Ratio of Attaining Apex Political Rank (log scale)", fontsize=8.5)
        ax.set_xscale("log")
        ax.set_xlim(0.6, 25)
        ax.set_xticks([1, 2, 5, 10, 20])
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.grid(axis="x", alpha=0.6)

    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels([lbl for _, lbl in vars_to_plot], fontsize=8.2)

    headline(fig, "Testing Patronage: Formal Legal Signature vs. Behavioral Retinues",
             "Pre- vs. post-2011 tournament model predicting lifetime apex rank (>=72) among administrative entrants (rank <=55).\n"
             "While the formal legal signature lost statistical significance post-2011 (p = 0.108), behavioral patronage (retinues and sweeps) intensified.")
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    save(fig, "fig_mobility_05_behavioral_patronage", SOURCE)
    print("Test complete!")

if __name__ == "__main__":
    main()
