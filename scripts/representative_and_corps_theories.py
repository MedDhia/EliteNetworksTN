"""Testing Representative Bureaucracy (Gender) and Grand Corps Hegemony in Tunisia (1957-2026).

Empirical tests of:
1. Representative Bureaucracy & The Gender Glass Ceiling (Kingsley 1944; Mosher 1968):
   - Passive representation growth from 5.9% in 1970s to 41.9% in 2020s
   - Hierarchical attrition and the glass ceiling gradient (39.3% in service head vs. 3.7% in governors)
   - Career tournament penalty: Female odds of reaching apex posts (OR = 0.49 pre-2011, OR = 0.35 post-2011)
2. Technocracy and Grand Corps Rivalry (Pierre Bourdieu 1989; Ezra Suleiman 1974):
   - Apex attainment rates by bureaucratic corps (ENA CSP elite 25.1% vs. Engineers 10.7%)
   - Institutional domain colonization (Engineers monopolize Equipment/Agriculture; ENA captures Prime Ministry/Finance)

Generates publication figures:
- fig_theory_04_gender_glass_ceiling.png / .pdf
- fig_theory_05_grand_corps_hegemony.png / .pdf
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
PURPLE = "#6B46C1"
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
        if ARTIFACT_DIR.exists():
            shutil.copy2(path, ARTIFACT_DIR / f"{name}.{ext}")
    plt.close(fig)


def canonical_domain(row: pd.Series) -> str:
    p = str(row.get("org_portfolio", "")).lower() if pd.notna(row.get("org_portfolio")) else ""
    org = (str(row.get("parent_org_name", "")) + " " + str(row.get("org_name", ""))).lower()
    
    if "interieur" in p or "interieur" in org: return "Interior"
    if "defense" in p or "defense" in org: return "Defense"
    if "justice" in p or "justice" in org: return "Justice"
    if "etranger" in p or "etranger" in org: return "Foreign Affairs"
    if "finance" in p or "finances" in org: return "Finance"
    if "premier ministre" in org or "presidence du gouvernement" in org or "presidence_gouvernement" in p or "premier_ministre" in p:
        return "Prime Ministry"
    if "sante" in p or "sante" in org: return "Health"
    if "enseignement superieur" in org or "enseignement_superieur" in p: return "Higher Education"
    if "education" in p or "education" in org: return "Education"
    if "agriculture" in p or "agriculture" in org: return "Agriculture"
    if "social" in p or "social" in org: return "Social Affairs"
    if "equipement" in p or "equipement" in org: return "Equipment"
    if "transport" in p or "transport" in org: return "Transport"
    if "culture" in p or "culture" in org: return "Culture"
    if "jeunesse" in p or "sport" in p: return "Youth & Sports"
    return "Other"


def classify_corps(grade: str | None) -> str:
    if pd.isna(grade): return "Unspecified / Other"
    g = str(grade).lower()
    if "conseiller des services publics" in g: return "ENA (CSP Elite)"
    if "administrateur" in g: return "Civil Administrators"
    if "ingénieur" in g: return "Engineers"
    if "inspecteur" in g and ("financ" in g or "fisc" in g or "comptab" in g): return "Finance Inspectors"
    if "inspecteur" in g: return "General Inspectors"
    if "professeur" in g or "maître" in g or "assistant" in g or "chercheur" in g: return "Academics"
    if "médecin" in g or "santé" in g or "pharmacien" in g: return "Medical / Health"
    if "magistrat" in g or "juge" in g: return "Judges"
    if "diplomat" in g or "affaires étrangères" in g: return "Diplomats"
    return "Other Line Grades"


def load_data():
    print("Loading data for representative bureaucracy & corps analysis...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)
    spells["domain"] = spells.apply(canonical_domain, axis=1)

    # Disambiguate gender from events
    fem_counts = events[events.honorific.isin(["Madame", "Mademoiselle"])].groupby("person_id").size()
    masc_counts = events[events.honorific.isin(["Monsieur", "M.", "Cheikh", "Hadj", "Général"])].groupby("person_id").size()

    def assign_gender(pid):
        f = fem_counts.get(pid, 0)
        m = masc_counts.get(pid, 0)
        if f > m: return "Female"
        elif m > f: return "Male"
        return "Unknown"

    spells["gender"] = spells["person_id"].map(assign_gender)

    # Corps classification
    corps_priority = {
        "ENA (CSP Elite)": 10, "Finance Inspectors": 9, "Judges": 8, "Diplomats": 7,
        "Engineers": 6, "Academics": 5, "Medical / Health": 4, "General Inspectors": 3,
        "Civil Administrators": 2, "Other Line Grades": 1, "Unspecified / Other": 0
    }
    events["corps"] = events["grade_raw"].map(classify_corps)
    events["corps_prio"] = events["corps"].map(corps_priority)
    person_corps = events.sort_values("corps_prio", ascending=False).drop_duplicates("person_id").set_index("person_id")["corps"]
    spells["corps"] = spells["person_id"].map(person_corps).fillna("Unspecified / Other")

    # Career trajectory metrics
    spells["prior_spells"] = spells.groupby("person_id").cumcount()
    spells["first_start_dt"] = spells.groupby("person_id")["start_dt"].transform("min")
    spells["career_age_years"] = (spells["start_dt"] - spells["first_start_dt"]).dt.days / 365.25

    return spells, events


def test_theory_04_gender(spells: pd.DataFrame):
    """Theory 4: Representative Bureaucracy & The Gender Glass Ceiling."""
    print("\n" + "=" * 70)
    print("THEORY 4: REPRESENTATIVE BUREAUCRACY & THE GENDER GLASS CEILING")
    print("=" * 70)

    # 1. Historical passive representation trend
    annual_gender = spells[spells.gender.isin(["Female", "Male"]) & (spells.start_year.between(1970, 2025))].groupby(
        ["start_year", "gender"]
    ).size().unstack().fillna(0)
    annual_gender["pct_female"] = annual_gender["Female"] / (annual_gender["Female"] + annual_gender["Male"]) * 100
    annual_gender["pct_female_ma"] = annual_gender["pct_female"].rolling(3, center=True, min_periods=1).mean()

    # 2. Modern rank hierarchy gradient (2010-2026)
    modern = spells[(spells.start_year >= 2010) & (spells.gender.isin(["Female", "Male"]))].copy()
    rank_order = [
        ("chef_service", "Head of Service (35)"),
        ("sous_directeur", "Deputy Director (45)"),
        ("directeur", "Director (55)"),
        ("directeur_general", "Director General (65)"),
        ("secretaire_general", "Secretary General (70)"),
        ("conseiller_pol", "Political Adviser (72)"),
        ("chef_cabinet", "Chief of Cabinet (74)"),
        ("pdg", "State CEO / PDG (68)"),
        ("ministre", "Minister (90)"),
        ("gouverneur", "Governor (80)")
    ]

    rank_data = []
    for r_code, r_lbl in rank_order:
        sub = modern[modern.position_rank == r_code]
        pct_f = (sub.gender == "Female").mean() * 100 if len(sub) > 0 else 0
        rank_data.append({"rank_code": r_code, "label": r_lbl, "pct_female": pct_f, "n": len(sub)})
    rank_df = pd.DataFrame(rank_data)

    # 3. Tournament model: Lifetime apex attainment by gender
    peak_map = spells.groupby("person_id")["rank_score"].max()
    first_spells = spells[spells.groupby("person_id").cumcount() == 0].copy()
    first_spells = first_spells[first_spells.rank_score <= 55].copy()
    first_spells["reaches_apex"] = (first_spells["person_id"].map(peak_map) >= 70).astype(int)
    first_spells = first_spells[first_spells.gender.isin(["Female", "Male"])].copy()
    first_spells["is_female"] = (first_spells.gender == "Female").astype(int)
    first_spells["is_post2011"] = (first_spells.start_year >= 2011).astype(int)

    mod_pre = smf.logit("reaches_apex ~ is_female + rank_score", data=first_spells[first_spells.is_post2011 == 0]).fit(disp=False)
    mod_post = smf.logit("reaches_apex ~ is_female + rank_score", data=first_spells[first_spells.is_post2011 == 1]).fit(disp=False)

    print("Pre-2011 Gender Apex Attainment OR:", np.exp(mod_pre.params["is_female"]), "p-val:", mod_pre.pvalues["is_female"])
    print("Post-2011 Gender Apex Attainment OR:", np.exp(mod_post.params["is_female"]), "p-val:", mod_post.pvalues["is_female"])

    # PLOT FIGURE T4
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), gridspec_kw={"width_ratios": [1.1, 1.2, 1.0]})
    headline(
        fig,
        "Theory 4: Representative Bureaucracy & The Gender Glass Ceiling (1957–2026)",
        "Empirical test of Kingsley (1944) & Mosher (1968): Passive representation expands rapidly, but apex offices remain heavily barricaded."
    )

    # Subplot A: Historical Expansion of Female Appointments
    ax = axes[0]
    ax.plot(annual_gender.index, annual_gender["pct_female"], color=RULE, lw=1.2, alpha=0.7)
    ax.plot(annual_gender.index, annual_gender["pct_female_ma"], color=PURPLE, lw=2.4, label="Female Share (3-Yr MA)")
    ax.axhline(50, color=MUTED, linestyle=":", lw=0.9, label="Gender Parity (50%)")
    ax.set_title("A. Passive Representation (1970–2025)")
    ax.set_xlabel("Appointment Year")
    ax.set_ylabel("% Female Appointees")
    ax.set_xlim(1970, 2026)
    ax.set_ylim(0, 55)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=7.2)

    ax.annotate("Expansion to 42%\nin 2020s", xy=(2023, 42), xytext=(1998, 46),
                arrowprops=dict(arrowstyle="->", color=PURPLE, lw=1.0),
                fontsize=7.6, fontweight="bold", color=PURPLE)

    # Subplot B: The Glass Ceiling Gradient
    ax = axes[1]
    y_pos = np.arange(len(rank_df))[::-1]
    colors = [PURPLE if p > 30 else (ORG if p > 15 else PERSON) for p in rank_df["pct_female"]]
    ax.barh(y_pos, rank_df["pct_female"], color=colors, alpha=0.85, height=0.68)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rank_df["label"], fontsize=7.4)
    ax.set_title("B. The Glass Ceiling Hierarchy (2010–2026)")
    ax.set_xlabel("% Female Appointees in Rank")
    ax.set_xlim(0, 50)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for idx, row in rank_df.iterrows():
        y = y_pos[idx]
        ax.text(row["pct_female"] + 1.0, y, f"{row['pct_female']:.1f}%", va="center", fontsize=7.0, color=INK)

    ax.axvline(39.3, color=PURPLE, linestyle="--", alpha=0.5, lw=0.9)
    ax.text(39.8, 1, "Service Head Baseline (39.3%)", rotation=90, fontsize=6.6, color=PURPLE)

    # Subplot C: Tournament Odds Ratios
    ax = axes[2]
    eras = [("Pre-2011 State\n(1957–2010)", mod_pre), ("Post-2011 State\n(2011–2026)", mod_post)]
    y_c = [1, 0]
    for idx, (era_lbl, m) in enumerate(eras):
        b = m.params["is_female"]
        se = m.bse["is_female"]
        or_val = np.exp(b)
        ci_low = np.exp(b - 1.96 * se)
        ci_high = np.exp(b + 1.96 * se)

        ax.plot([ci_low, ci_high], [y_c[idx], y_c[idx]], color=PERSON, lw=2.2)
        ax.plot(or_val, y_c[idx], marker="o", color=PERSON, markersize=6.0)
        ax.text(ci_high + 0.04, y_c[idx], f"{or_val:.2f}\n[{ci_low:.2f}, {ci_high:.2f}]",
                va="center", fontsize=7.4, fontweight="bold", color=PERSON)

    ax.axvline(1.0, color=MUTED, linestyle="--", lw=1.0)
    ax.set_yticks(y_c)
    ax.set_yticklabels([lbl for lbl, _ in eras], fontsize=7.8)
    ax.set_title("C. Female Odds Ratio for Apex Attainment")
    ax.set_xlabel("Odds Ratio Relative to Men (Ref = 1.0)")
    ax.set_xlim(0.1, 1.3)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    save_fig(fig, "fig_theory_04_gender_glass_ceiling", SOURCE)


def test_theory_05_grand_corps(spells: pd.DataFrame, events: pd.DataFrame):
    """Theory 5: Technocracy & Grand Corps Rivalry (Bourdieu 1989; Suleiman 1974)."""
    print("\n" + "=" * 70)
    print("THEORY 5: TECHNOCRACY & GRAND CORPS HEGEMONY")
    print("=" * 70)

    person_peak = spells.groupby("person_id")["rank_score"].max()
    person_corps = spells.drop_duplicates("person_id").set_index("person_id")["corps"]
    corps_df = pd.DataFrame({"corps": person_corps, "peak_rank": person_peak}).dropna()

    top_corps_list = [
        "ENA (CSP Elite)", "Judges", "Diplomats", "Civil Administrators",
        "Academics", "Engineers", "Finance Inspectors", "General Inspectors"
    ]
    corps_df = corps_df[corps_df.corps.isin(top_corps_list)]

    stats = corps_df.groupby("corps").agg(
        n_persons=("peak_rank", "count"),
        pct_apex=("peak_rank", lambda s: (s >= 70).mean() * 100),
        pct_dg=("peak_rank", lambda s: (s >= 65).mean() * 100)
    ).loc[top_corps_list].sort_values("pct_apex", ascending=True)

    # Domain composition heatmap
    senior = spells[(spells.rank_score >= 55) & (spells.corps.isin(top_corps_list))].copy()
    core_domains = ["Prime Ministry", "Finance", "Interior", "Foreign Affairs",
                    "Equipment", "Transport", "Agriculture", "Higher Education", "Health"]
    ct = pd.crosstab(senior["domain"], senior["corps"], normalize="index") * 100
    ct_sub = ct.loc[core_domains, ["ENA (CSP Elite)", "Engineers", "Civil Administrators", "Academics", "Diplomats", "Finance Inspectors"]]

    # PLOT FIGURE T5
    fig, axes = plt.subplots(1, 3, figsize=(16.0, 4.8), gridspec_kw={"width_ratios": [1.1, 1.4, 1.0]})
    headline(
        fig,
        "Theory 5: Technocracy, Grand Corps Hegemony & Domain Colonization",
        "Empirical test of Bourdieu (1989) & Suleiman (1974): Generalist state elites (ENA) capture apex posts; engineers dominate infrastructure."
    )

    # Subplot A: Apex Attainment by Corps
    ax = axes[0]
    y_pos = np.arange(len(stats))
    colors = [PERSON if c == "ENA (CSP Elite)" else (ORG if c == "Engineers" else SLATE) for c in stats.index]
    ax.barh(y_pos, stats["pct_apex"], color=colors, alpha=0.85, height=0.68)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stats.index, fontsize=7.4)
    ax.set_title("A. Apex Attainment Rate (Rank ≥ 70)")
    ax.set_xlabel("% Entrants Ever Reaching Apex Posts")
    ax.set_xlim(0, 32)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for idx, (c_name, row) in enumerate(stats.iterrows()):
        ax.text(row["pct_apex"] + 0.8, idx, f"{row['pct_apex']:.1f}%", va="center", fontsize=7.2, color=INK)

    # Subplot B: Domain Colonization Heatmap
    ax = axes[1]
    im = ax.imshow(ct_sub.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=60)
    ax.set_xticks(np.arange(len(ct_sub.columns)))
    ax.set_yticks(np.arange(len(ct_sub.index)))
    ax.set_xticklabels([c.replace(" ", "\n") for c in ct_sub.columns], fontsize=6.8)
    ax.set_yticklabels(ct_sub.index, fontsize=7.2)
    ax.set_title("B. Domain Monopolies (% Senior Posts in Ministry)")
    ax.set_xlabel("Grand Administrative Corps")
    ax.set_ylabel("Ministry Domain")

    for i in range(len(ct_sub.index)):
        for j in range(len(ct_sub.columns)):
            val = ct_sub.values[i, j]
            txt_color = "white" if val > 35 else INK
            fontweight = "bold" if val > 20 else "normal"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    color=txt_color, fontsize=7.0, fontweight=fontweight)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=6.8)
    cbar.set_label("% Senior Officers in Ministry", fontsize=7.0, color=MUTED)

    # Subplot C: Career Velocity to Apex
    ax = axes[2]
    apex_spells = spells[spells.rank_score >= 70].groupby(["person_id", "corps"])["career_age_years"].min().reset_index()
    apex_spells = apex_spells[apex_spells.corps.isin(["ENA (CSP Elite)", "Engineers", "Civil Administrators", "Academics"])]
    vel = apex_spells.groupby("corps")["career_age_years"].median().loc[["ENA (CSP Elite)", "Civil Administrators", "Engineers", "Academics"]]

    y_v = np.arange(len(vel))
    ax.barh(y_v, vel.values, color=[PERSON, SLATE, ORG, GOLD], alpha=0.85, height=0.6)
    ax.set_yticks(y_v)
    ax.set_yticklabels(vel.index, fontsize=7.4)
    ax.set_title("C. Median Years of Service to Apex")
    ax.set_xlabel("Career Age at First Apex Appointment (Years)")
    ax.set_xlim(0, 18)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for idx, v in enumerate(vel.values):
        ax.text(v + 0.4, idx, f"{v:.1f} yrs", va="center", fontsize=7.2, fontweight="bold", color=INK)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    save_fig(fig, "fig_theory_05_grand_corps_hegemony", SOURCE)


def main():
    print("=" * 70)
    print("TESTING REPRESENTATIVE BUREAUCRACY & GRAND CORPS IN TUNISIA")
    print("=" * 70)

    spells, events = load_data()

    test_theory_04_gender(spells)
    test_theory_05_grand_corps(spells, events)

    print("\nAll tests completed. Figures saved and copied to artifact directory.")


if __name__ == "__main__":
    main()
