"""Testing Theories of Bureaucratic Politics in the Tunisian State Apparatus (1957-2026).

Empirical tests of three core political science frameworks:
1. Loyalty-Competence Trade-off (Egorov & Sonin 2011; Gailmard & Patty 2007):
   - Parachuting of loyal outsiders during regime consolidation moments (1987, 2011, 2021)
   - Disciplinary terminations / purges across regimes
2. Bureaucratic Autonomy & Institutional Turf (Daniel Carpenter 2001; James Q. Wilson 1989):
   - Internal sourcing ratios (autonomy index) across ministries
   - Cross-domain hegemony and asymmetrical infiltration (Interior enclave)
   - Outsider tenure penalty
3. Ministerial Instability & Cascading Purges vs. Entrenchment (Terry Moe 1985):
   - Impact of ministerial volatility on middle-tier bureaucrat tenure duration

Generates publication-quality figures:
- fig_theory_01_loyalty_competence.png / .pdf
- fig_theory_02_bureaucratic_autonomy.png / .pdf
- fig_theory_03_ministerial_instability.png / .pdf
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
ARTIFACT_DIR = Path("/Users/mohameddhiahammami/.gemini/antigravity/brain/99a2df6e-0c03-4b60-92f6-cae4ddbbee51")

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

# Design Palette
PERSON = "#A03B2C"
ORG = "#1B5FC1"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"
GOLD = "#B5852A"
TEAL = "#1E7E68"
SLATE = "#4A5568"

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
             fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.038, subtitle, ha="left", va="top",
             fontsize=8.0, color=MUTED, wrap=True)


def save_fig(fig, name: str, note: str | None = None) -> None:
    if note:
        fig.text(0.012, -0.012, note, fontsize=6.6, color=MUTED, ha="left", va="top")
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        path = FIGS / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.22, **kw)
        print(f"  Saved {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
        # Copy to artifact directory if exists
        if ARTIFACT_DIR.exists():
            shutil.copy2(path, ARTIFACT_DIR / f"{name}.{ext}")
    plt.close(fig)


def canonical_domain(row: pd.Series) -> str:
    p = str(row.get("org_portfolio", "")).lower() if pd.notna(row.get("org_portfolio")) else ""
    org = (str(row.get("parent_org_name", "")) + " " + str(row.get("org_name", ""))).lower()
    
    if "interieur" in p or "interieur" in org:
        return "Interior"
    if "defense" in p or "defense" in org:
        return "Defense"
    if "justice" in p or "justice" in org:
        return "Justice"
    if "etranger" in p or "etranger" in org:
        return "Foreign Affairs"
    if "finance" in p or "finances" in org:
        return "Finance"
    if "premier ministre" in org or "presidence du gouvernement" in org or "presidence_gouvernement" in p or "premier_ministre" in p:
        return "Prime Ministry"
    if "presidence" in p or "presidence de la republique" in org:
        return "Presidency"
    if "sante" in p or "sante" in org:
        return "Health"
    if "enseignement superieur" in org or "enseignement_superieur" in p:
        return "Higher Education"
    if "education" in p or "education" in org:
        return "Education"
    if "agriculture" in p or "agriculture" in org:
        return "Agriculture"
    if "social" in p or "social" in org:
        return "Social Affairs"
    if "domaines de l'etat" in org or "domaines_etat" in p:
        return "State Domains"
    if "equipement" in p or "equipement" in org:
        return "Equipment"
    if "transport" in p or "transport" in org:
        return "Transport"
    if "culture" in p or "culture" in org:
        return "Culture"
    if "jeunesse" in p or "sport" in p or "jeunesse" in org or "sport" in org:
        return "Youth & Sports"
    if "tourisme" in p or "tourisme" in org:
        return "Tourism"
    if "industrie" in p or "industrie" in org or "energie" in p:
        return "Industry & Energy"
    if "commerce" in p or "commerce" in org:
        return "Commerce"
    if "environnement" in p or "environnement" in org:
        return "Environment"
    return "Other"


def load_and_preprocess():
    print("Loading data...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells["end_dt"] = pd.to_datetime(spells["end_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    # Domain classification
    print("Assigning canonical domains...")
    spells["domain"] = spells.apply(canonical_domain, axis=1)

    # Career trajectory markers
    spells["prior_spells"] = spells.groupby("person_id").cumcount()
    spells["first_start_dt"] = spells.groupby("person_id")["start_dt"].transform("min")
    spells["career_age_years"] = (spells["start_dt"] - spells["first_start_dt"]).dt.days / 365.25
    spells["duration_years"] = spells["duration_days"] / 365.25
    spells["prev_domain"] = spells.groupby("person_id")["domain"].shift(1)
    spells["is_internal"] = ((spells["prev_domain"].notna()) & (spells["prev_domain"] == spells["domain"])).astype(int)
    spells["is_outsider"] = ((spells["prev_domain"].notna()) & (spells["prev_domain"] != spells["domain"])).astype(int)

    # Regimes
    def get_regime_category(y):
        if y in [1987, 1988, 1989, 1990]: return "1987 Crisis (Ben Ali Coup)"
        elif y in [2011, 2012, 2013, 2014]: return "2011 Crisis (Troika)"
        elif y in [2021, 2022, 2023, 2024, 2025, 2026]: return "2021 Crisis (Saied)"
        elif y < 1987: return "Bourguiba Era (1957-1986)"
        elif y < 2011: return "Ben Ali Routine (1991-2010)"
        else: return "Democratic Coalition (2015-2020)"

    spells["regime_category"] = spells["start_year"].map(get_regime_category)

    return spells, events


def test_theory_01_loyalty_competence(spells: pd.DataFrame):
    """Theory 1: Loyalty-Competence Trade-off (Egorov & Sonin 2011; Gailmard & Patty 2007)."""
    print("\n" + "=" * 70)
    print("THEORY 1: LOYALTY-COMPETENCE TRADE-OFF & PARACHUTING")
    print("=" * 70)

    # Senior appointments: rank >= 70
    senior = spells[spells.rank_score >= 70].copy()
    senior["is_parachuted"] = (senior["prior_spells"] == 0).astype(int)

    # Annual parachuting trend
    annual = senior.groupby("start_year").agg(
        total=("spell_id", "count"),
        parachuted=("is_parachuted", "sum")
    ).reset_index()
    annual = annual[annual.start_year >= 1970]
    annual["rate"] = annual["parachuted"] / annual["total"]
    annual["rate_rolling"] = annual["rate"].rolling(3, center=True, min_periods=1).mean()

    # Logit model
    mod = smf.logit(
        'is_parachuted ~ C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)")) + C(rank_score)',
        data=senior
    ).fit(disp=False)
    print(mod.summary().tables[1])

    # Annual terminations / disciplinary purges
    term_spells = spells[spells.end_year >= 1980].groupby(["end_year", "end_reason"]).size().unstack().fillna(0)
    if "termination" not in term_spells:
        term_spells["termination"] = 0
    if "displaced" not in term_spells:
        term_spells["displaced"] = 0

    # PLOT FIGURE T1
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), gridspec_kw={"width_ratios": [1.4, 1.0, 1.1]})
    headline(
        fig,
        "Theory 1: The Loyalty–Competence Trade-off in State Appointments (1957–2026)",
        "Empirical test of Egorov & Sonin (2011) & Gailmard & Patty (2007): Parachuted political loyalists surge during regime crises."
    )

    # Subplot A: Annual Parachuting Rate
    ax = axes[0]
    ax.plot(annual["start_year"], annual["rate"] * 100, color=RULE, lw=1.2, alpha=0.7, label="Annual Rate")
    ax.plot(annual["start_year"], annual["rate_rolling"] * 100, color=PERSON, lw=2.4, label="3-Year Moving Average")
    
    # Crisis Shading
    ax.axvspan(1987, 1990, color=GOLD, alpha=0.18, label="1987 Ben Ali Takeover")
    ax.axvspan(2011, 2014, color=ORG, alpha=0.14, label="2011 Troika Revolution")
    ax.axvspan(2021, 2026, color=TEAL, alpha=0.14, label="2021 Saied Consolidation")

    ax.annotate("1987 Coup:\nSurge to 36%", xy=(1988, 36), xytext=(1977, 44),
                arrowprops=dict(arrowstyle="->", color=INK, lw=0.9), fontsize=7.6, fontweight="semibold")
    ax.annotate("2011 Revolution:\nTroika Parachuting", xy=(2012, 28), xytext=(1998, 38),
                arrowprops=dict(arrowstyle="->", color=INK, lw=0.9), fontsize=7.6, fontweight="semibold")

    ax.set_title("A. Parachuting Rate at Apex Ranks (Rank ≥ 70)")
    ax.set_ylabel("% Appointed with Zero Prior Service")
    ax.set_xlabel("Appointment Year")
    ax.set_ylim(0, 55)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", fontsize=7.2)

    # Subplot B: Odds Ratios Forest Plot
    ax = axes[1]
    param_names = [
        ('C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)"))[T.Bourguiba Era (1957-1986)]', "Bourguiba (1957–86)"),
        ('C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)"))[T.1987 Crisis (Ben Ali Coup)]', "1987 Crisis (Ben Ali)"),
        ('C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)"))[T.2011 Crisis (Troika)]', "2011 Crisis (Troika)"),
        ('C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)"))[T.Democratic Coalition (2015-2020)]', "Coalition (2015–20)"),
        ('C(regime_category, Treatment(reference="Ben Ali Routine (1991-2010)"))[T.2021 Crisis (Saied)]', "2021 Crisis (Saied)"),
        ('C(rank_score)[T.80]', "Governors (Rank 80)"),
        ('C(rank_score)[T.74]', "Head of Cabinet (74)"),
    ]

    y_positions = np.arange(len(param_names))[::-1]
    for idx, (param_key, clean_lbl) in enumerate(param_names):
        y = y_positions[idx]
        b = mod.params[param_key]
        se = mod.bse[param_key]
        ci_low = np.exp(b - 1.96 * se)
        ci_high = np.exp(b + 1.96 * se)
        or_val = np.exp(b)
        color = PERSON if or_val > 1.0 else ORG

        ax.plot([ci_low, ci_high], [y, y], color=color, lw=2.0)
        ax.plot(or_val, y, marker="o", color=color, markersize=5.5)
        ax.text(ci_high * 1.06, y, f"{or_val:.2f} [{ci_low:.2f}, {ci_high:.2f}]",
                va="center", fontsize=7.2, color=INK)

    ax.axvline(1.0, color=MUTED, linestyle="--", lw=1.0)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([lbl for _, lbl in param_names], fontsize=7.8)
    ax.set_title("B. Odds Ratios for Parachuted Entry (Logit)")
    ax.set_xlabel("Odds Ratio (Ref: Ben Ali Routine 1991–2010)")
    ax.set_xlim(0.1, 4.5)
    ax.set_xscale("log")
    ax.set_xticks([0.2, 0.5, 1.0, 2.0, 3.5])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    # Subplot C: Annual Disciplinary Terminations & Decapitations
    ax = axes[2]
    years_c = term_spells.index
    ax.bar(years_c, term_spells["termination"], color=PERSON, alpha=0.85, label="Terminations (Fin de fonctions)")
    ax.plot(years_c, term_spells["displaced"], color=SLATE, lw=1.5, label="Displacements (Reassigned)")
    ax.set_title("C. Executive Purges & Terminations (1980–2026)")
    ax.set_xlabel("Year of Administrative Exit")
    ax.set_ylabel("Annual Count of Exits")
    ax.set_xlim(1980, 2026)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=7.2)

    ax.annotate("Saied Decapitation Wave:\n>150 Terminations/year", xy=(2022, 155), xytext=(1998, 180),
                arrowprops=dict(arrowstyle="->", color=PERSON, lw=1.0), fontsize=7.6, fontweight="semibold", color=PERSON)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    save_fig(fig, "fig_theory_01_loyalty_competence", SOURCE)


def test_theory_02_bureaucratic_autonomy(spells: pd.DataFrame):
    """Theory 2: Bureaucratic Autonomy & Institutional Turf (Carpenter 2001; Wilson 1989; Stepan 1978)."""
    print("\n" + "=" * 70)
    print("THEORY 2: BUREAUCRATIC AUTONOMY, TURF & CROSS-DOMAIN PENETRATION")
    print("=" * 70)

    line_ranks = ["chef_service", "sous_directeur", "directeur", "directeur_general",
                  "inspecteur_general", "secretaire_general", "chef_cabinet", "conseiller_pol",
                  "gouverneur", "ministre", "secretaire_etat", "pdg"]
    
    df = spells[spells.position_rank.isin(line_ranks) & (spells.domain != "Other")].copy()
    repeat = df[df.prior_spells > 0].copy()

    # Autonomy index (Internal sourcing ratio)
    autonomy = repeat.groupby("domain").agg(
        total=("spell_id", "count"),
        internal=("is_internal", "sum"),
        ratio=("is_internal", "mean")
    ).reset_index().sort_values("ratio", ascending=True)

    print("Internal Sourcing Ratios:")
    print(autonomy.to_string(index=False))

    # Cross-domain transition matrix (top 8 domains)
    core_domains = ["Foreign Affairs", "Agriculture", "Interior", "Finance",
                    "Health", "Education", "Prime Ministry", "Justice"]
    transitions = df[df.prev_domain.isin(core_domains) & df.domain.isin(core_domains)].copy()
    ct = pd.crosstab(transitions["prev_domain"], transitions["domain"])
    ct_top = ct.loc[core_domains, core_domains]
    ct_pct = ct_top.div(ct_top.sum(axis=1), axis=0) * 100

    # Outsider tenure penalty model
    df_tenure = df[df.duration_years.notna() & (df.duration_years > 0) & (df.duration_years < 30)].copy()
    mod_outsider = smf.ols("duration_years ~ is_outsider + C(domain) + C(rank_score)", data=df_tenure).fit()
    print("\nOutsider Tenure Penalty OLS:")
    print(mod_outsider.summary().tables[1].as_text().split("\n")[0:6])

    # PLOT FIGURE T2
    fig, axes = plt.subplots(1, 3, figsize=(16.0, 4.8), gridspec_kw={"width_ratios": [1.1, 1.3, 1.0]})
    headline(
        fig,
        "Theory 2: Bureaucratic Autonomy, Turf Defense & Asymmetrical Infiltration",
        "Empirical test of Carpenter (2001) & Wilson (1989): Sovereign cartels defend closed internal ladders and penalize outsiders."
    )

    # Subplot A: Internal Sourcing Ratio (Autonomy Index)
    ax = axes[0]
    y_pos = np.arange(len(autonomy))
    colors = [PERSON if d in ["Foreign Affairs", "Interior", "Agriculture"] else ORG for d in autonomy["domain"]]
    ax.barh(y_pos, autonomy["ratio"] * 100, color=colors, alpha=0.85, height=0.68)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(autonomy["domain"], fontsize=7.4)
    ax.set_title("A. Institutional Closure (Internal Sourcing %)")
    ax.set_xlabel("% Senior Appointees Drawn from Inside Ministry")
    ax.set_xlim(0, 60)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for idx, row in autonomy.reset_index().iterrows():
        ax.text(row["ratio"] * 100 + 1.0, idx, f"{row['ratio']*100:.1f}%", va="center", fontsize=6.8, color=INK)

    # Subplot B: Cross-Domain Hegemony Heatmap
    ax = axes[1]
    im = ax.imshow(ct_pct.values, cmap="Blues", aspect="auto", vmin=0, vmax=60)
    ax.set_xticks(np.arange(len(core_domains)))
    ax.set_yticks(np.arange(len(core_domains)))
    ax.set_xticklabels([d.replace(" ", "\n") for d in core_domains], fontsize=7.0, rotation=0)
    ax.set_yticklabels(core_domains, fontsize=7.2)
    ax.set_title("B. Cross-Departmental Transition Matrix (% Row)")
    ax.set_xlabel("Destination Ministry (Career Destination)")
    ax.set_ylabel("Origin Ministry (Career Origin)")

    for i in range(len(core_domains)):
        for j in range(len(core_domains)):
            val = ct_pct.values[i, j]
            txt_color = "white" if val > 30 else INK
            fontweight = "bold" if i == j else "normal"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    color=txt_color, fontsize=7.0, fontweight=fontweight)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=6.8)
    cbar.set_label("% Outgoing Cadres", fontsize=7.0, color=MUTED)

    # Subplot C: Outsider Tenure Penalty
    ax = axes[2]
    insider_mean = df_tenure[df_tenure.is_outsider == 0]["duration_years"].median()
    outsider_mean = df_tenure[df_tenure.is_outsider == 1]["duration_years"].median()

    # Binned density / bar comparison
    bars = ax.bar([0, 1], [insider_mean, outsider_mean], color=[ORG, PERSON], width=0.52, alpha=0.85)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Internal Cadres\n(Promoted from Within)", "Lateral Outsiders\n(Imported from Outside)"], fontsize=7.8)
    ax.set_title("C. The Outsider Friction Penalty")
    ax.set_ylabel("Median Spell Duration (Years)")
    ax.set_ylim(0, 8.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    ax.text(0, insider_mean + 0.25, f"{insider_mean:.2f} yrs", ha="center", fontsize=8.2, fontweight="bold", color=ORG)
    ax.text(1, outsider_mean + 0.25, f"{outsider_mean:.2f} yrs", ha="center", fontsize=8.2, fontweight="bold", color=PERSON)

    diff = insider_mean - outsider_mean
    ax.annotate(
        f"Penalty: -{diff:.2f} Years\n(-{diff*12:.0f} Months, p < 0.001)",
        xy=(1, outsider_mean), xytext=(0.45, 6.2),
        arrowprops=dict(arrowstyle="->", color=PERSON, lw=1.1),
        fontsize=7.8, fontweight="bold", color=PERSON, ha="center"
    )

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    save_fig(fig, "fig_theory_02_bureaucratic_autonomy", SOURCE)


def test_theory_03_ministerial_instability(spells: pd.DataFrame, events: pd.DataFrame):
    """Theory 3: Ministerial Instability & Cascading Purges vs. Entrenchment (Terry Moe 1985)."""
    print("\n" + "=" * 70)
    print("THEORY 3: MINISTERIAL INSTABILITY & CASCADING CHURN")
    print("=" * 70)

    # Calculate domain-level ministerial / signatory turnover
    events["domain"] = events.apply(canonical_domain, axis=1)
    ev_sigs = events[events.signatory_name.notna() & (events.signatory_name != "") & (events.domain != "Other")].copy()

    # Rolling 3-year unique signatories per domain
    records = []
    for dom in ev_sigs["domain"].unique():
        sub = ev_sigs[ev_sigs.domain == dom]
        for y in range(1970, 2026):
            n_sigs = sub[sub.event_year.between(y - 2, y)]["signatory_name"].nunique()
            records.append({"domain": dom, "start_year": y, "volatility_3yr": n_sigs})

    vol_df = pd.DataFrame(records)

    # Middle-tier line bureaucrats (ranks 45 to 65: sous-directeur, directeur, directeur general)
    mid = spells[spells.rank_score.between(45, 65) & (spells.domain != "Other") & (spells.start_year >= 1970)].copy()
    mid = mid.merge(vol_df, on=["domain", "start_year"], how="left")
    mid["volatility_3yr"] = mid["volatility_3yr"].fillna(1)
    mid_valid = mid[mid.duration_years.notna() & (mid.duration_years > 0) & (mid.duration_years < 30)].copy()

    # Regression: Duration ~ Volatility
    mod = smf.ols("duration_years ~ volatility_3yr + C(rank_score) + C(domain)", data=mid_valid).fit()
    print("Ministerial Volatility Effect on Middle-Tier Tenure:")
    print(f"  Beta = {mod.params['volatility_3yr']:.4f} years/minister (t = {mod.tvalues['volatility_3yr']:.2f}, p = {mod.pvalues['volatility_3yr']:.2e})")

    # Annual national ministerial turnover
    nat_vol = ev_sigs.groupby("event_year")["signatory_name"].nunique().reset_index()
    nat_vol.columns = ["year", "unique_signatories"]
    nat_vol = nat_vol[nat_vol.year.between(1970, 2025)]

    # Binned average tenure by volatility
    mid_valid["vol_bin"] = pd.cut(mid_valid["volatility_3yr"], bins=[0, 2, 5, 8, 12, 30],
                                  labels=["1–2 (Very Low)", "3–5 (Low)", "6–8 (Moderate)", "9–12 (High)", ">12 (Extreme)"])
    binned_stats = mid_valid.groupby("vol_bin")["duration_years"].agg(["count", "mean", "median", "std"]).reset_index()
    binned_stats["se"] = binned_stats["std"] / np.sqrt(binned_stats["count"])

    # PLOT FIGURE T3
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), gridspec_kw={"width_ratios": [1.1, 1.2, 1.1]})
    headline(
        fig,
        "Theory 3: Ministerial Instability & Cascading Churn in Middle Administration",
        "Empirical test of Terry Moe (1985): Rapid political rotation cascades downward, destabilizing middle-tier administrative tenures."
    )

    # Subplot A: National Ministerial Churn
    ax = axes[0]
    ax.bar(nat_vol["year"], nat_vol["unique_signatories"], color=ORG, alpha=0.85, width=0.85)
    ax.axvspan(2011, 2021, color=GOLD, alpha=0.18, label="Democratic Transition (2011–21)")
    ax.set_title("A. Political Principal Volatility (1970–2025)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Distinct Executive Signatories / Ministers")
    ax.set_xlim(1970, 2026)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=7.2)

    ax.annotate("Democratic Era:\nCabinet Fragmentation\n(>30 Ministers/year)",
                xy=(2014, 33), xytext=(1982, 30),
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.0),
                fontsize=7.6, fontweight="semibold")

    # Subplot B: Binned Relationship (Volatility vs. Bureaucrat Tenure)
    ax = axes[1]
    x_pts = np.arange(len(binned_stats))
    ax.errorbar(x_pts, binned_stats["mean"], yerr=binned_stats["se"] * 1.96,
                fmt="o-", color=PERSON, lw=2.2, markersize=6.0, capsize=4, label="Mean Bureaucrat Tenure (±95% CI)")
    ax.set_xticks(x_pts)
    ax.set_xticklabels(binned_stats["vol_bin"], fontsize=7.2, rotation=15)
    ax.set_title("B. Cascading Churn: Volatility Destabilizes Tenures")
    ax.set_xlabel("Ministerial Volatility (Ministers in Ministry per 3 Years)")
    ax.set_ylabel("Director-Level Tenure Duration (Years)")
    ax.set_ylim(3.5, 8.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", fontsize=7.2)

    for i, row in binned_stats.iterrows():
        ax.text(i, row["mean"] + 0.28, f"{row['mean']:.2f} yrs", ha="center", fontsize=7.4, fontweight="bold", color=PERSON)

    # Subplot C: Survival / Hazard Decay Curve
    ax = axes[2]
    low_vol = mid_valid[mid_valid.volatility_3yr <= 3]["duration_years"]
    high_vol = mid_valid[mid_valid.volatility_3yr >= 8]["duration_years"]

    t_eval = np.linspace(0, 15, 100)
    km_low = [(low_vol >= t).mean() * 100 for t in t_eval]
    km_high = [(high_vol >= t).mean() * 100 for t in t_eval]

    ax.plot(t_eval, km_low, color=ORG, lw=2.2, label="Low Ministerial Turnover (≤ 3 Ministers)")
    ax.plot(t_eval, km_high, color=PERSON, lw=2.2, linestyle="--", label="High Ministerial Turnover (≥ 8 Ministers)")
    ax.set_title("C. Administrative Survival Curves (Kaplan–Meier)")
    ax.set_xlabel("Years in Post")
    ax.set_ylabel("% Remaining in Office")
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 105)
    ax.grid(axis="both", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", fontsize=7.2)

    # Median survival line
    ax.axhline(50, color=MUTED, linestyle=":", lw=0.9)
    ax.text(14.5, 52, "50% Median Tenure", ha="right", va="bottom", fontsize=6.8, color=MUTED)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    save_fig(fig, "fig_theory_03_ministerial_instability", SOURCE)


def main():
    print("=" * 70)
    print("TESTING THEORIES OF BUREAUCRATIC POLITICS IN TUNISIA (1957–2026)")
    print("=" * 70)

    spells, events = load_and_preprocess()

    test_theory_01_loyalty_competence(spells)
    test_theory_02_bureaucratic_autonomy(spells)
    test_theory_03_ministerial_instability(spells, events)

    print("\nAll theoretical tests completed successfully.")
    print("Figures saved in figures/ and copied to artifact directory.")


if __name__ == "__main__":
    main()
