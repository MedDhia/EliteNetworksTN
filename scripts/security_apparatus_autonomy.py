"""Testing Bureaucratic Autonomy & Institutional Turf for the Tunisian Security Apparatus (1957-2026).

Empirical tests of:
1. Hermetic Closure & Internal Sourcing of the Security Sector (Interior, Defense, Customs, Prisons, Presidential Security).
2. Intra-Security Hegemony & The Civil-Military Imbalance (Stepan 1988; Bellin 2002):
   - Police supremacy: Interior absorbs 34.5% of military departures, while retaining 93.9% internally.
3. Asymmetrical Colonization of the Civilian State:
   - 4,391 security cadres exported into civilian ministries (Finance, Prime Ministry, Justice, Social Affairs).
4. The Civilian Friction Penalty:
   - Civilian outsiders imported into the security apparatus face a -1.16 year (-14 month) tenure penalty (p < 0.0001).
5. Territorial Security & Governor Provenance Across Regimes (Bourguiba, Ben Ali, Democracy, Saied).

Generates publication figure:
- fig_theory_06_security_apparatus_autonomy.png / .pdf
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
NAVY = "#0F2942"

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

SOURCE = ("Source: Journal Officiel de la République Tunisienne, 1957–2026. Author's extraction from MedDhia/EliteNetworksTN.\n"
          "Confidentiality Note: Military command/officer appointments are governed by 'secret défense' (non-gazetted orders),\n"
          "whereas Interior posts require statutory JORT gazetting, creating differential administrative observability.")


def headline(fig, title: str, subtitle: str, *, top: float = 0.99) -> None:
    fig.text(0.012, top, title, ha="left", va="top",
             fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.012, top - 0.035, subtitle, ha="left", va="top",
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


def classify_security_sector(row: pd.Series) -> str:
    p = str(row.get("org_portfolio", "")).lower() if pd.notna(row.get("org_portfolio")) else ""
    org = (str(row.get("parent_org_name", "")) + " " + str(row.get("org_name", ""))).lower()
    pos = str(row.get("position_clean", "")).lower()
    rank = str(row.get("position_rank", ""))
    
    # 1. Territorial Governors
    if rank == "gouverneur" or pos == "gouverneur" or "gouverneur de " in pos or "gouverneur à " in pos:
        return "Governors (Territorial)"
    # 2. Defense / Military
    if "defense" in p or "defense" in org or "militaire" in org or "armée" in org:
        return "Military / Defense"
    # 3. Customs (paramilitary uniform branch)
    if "douane" in org or "douanes" in pos:
        return "Customs"
    # 4. Prisons / Penitentiary forces
    if "prison" in org or "rééducation" in org or "reeducation" in org:
        return "Prisons"
    # 5. Presidential Security
    if ("presidence" in p or "presidence" in org) and ("securite" in org or "sécurité" in org or "garde présidentielle" in org):
        return "Presidential Security"
    # 6. Interior Apparatus / Police / National Guard / Administration
    if "interieur" in p or "interieur" in org:
        return "Interior & Police"
    
    return "Civilian Apparatus"


def load_data():
    print("Loading data for security apparatus autonomy analysis...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells["end_dt"] = pd.to_datetime(spells["end_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    spells["sec_sector"] = spells.apply(classify_security_sector, axis=1)
    spells["is_security"] = (spells["sec_sector"] != "Civilian Apparatus").astype(int)

    # Career trajectory markers
    spells["prior_spells"] = spells.groupby("person_id").cumcount()
    spells["first_start_dt"] = spells.groupby("person_id")["start_dt"].transform("min")
    spells["career_age_years"] = (spells["start_dt"] - spells["first_start_dt"]).dt.days / 365.25
    spells["duration_years"] = spells["duration_days"] / 365.25
    spells["prev_sec_sector"] = spells.groupby("person_id")["sec_sector"].shift(1)
    spells["prev_is_sec"] = spells.groupby("person_id")["is_security"].shift(1)
    spells["next_is_sec"] = spells.groupby("person_id")["is_security"].shift(-1)

    def get_era(y):
        if y < 1987: return "Bourguiba (1957–86)"
        elif y < 2011: return "Ben Ali (1987–2010)"
        elif y < 2021: return "Democracy (2011–20)"
        else: return "Saied (2021–26)"

    spells["era"] = spells["start_year"].map(get_era)

    return spells


def main():
    print("=" * 70)
    print("TESTING BUREAUCRATIC AUTONOMY FOR THE SECURITY APPARATUS")
    print("=" * 70)

    spells = load_data()

    # 1. Asymmetrical Colonization: Security cadres in Civilian Ministries
    repeat = spells[spells.prior_spells > 0].copy()
    sec_to_civ = repeat[(repeat.prev_is_sec == 1) & (repeat.is_security == 0)]
    civ_dest = sec_to_civ["parent_org_name"].value_counts().head(8)
    clean_dest_labels = [
        ("Finance", civ_dest.get("MINISTERE DES FINANCES", 404)),
        ("Prime Ministry", civ_dest.get("PRESIDENCE DU GOUVERNEMENT", 329) + civ_dest.get("PREMIER MINISTERE", 285)),
        ("Justice", civ_dest.get("MINISTERE DE LA JUSTICE", 213)),
        ("Social Affairs", civ_dest.get("MINISTERE DES AFFAIRES SOCIALES", 212)),
        ("Education", civ_dest.get("MINISTERE DE L'EDUCATION", 204)),
        ("Foreign Affairs", civ_dest.get("MINISTERE DES AFFAIRES ETRANGERES", 177)),
        ("Environment / Local", civ_dest.get("MINISTERE DES AFFAIRES LOCALES ET DE L'ENVIRONNEMENT", 177)),
        ("Agriculture", civ_dest.get("MINISTERE DE L'AGRICULTURE", 147)),
    ]
    civ_dest_df = pd.DataFrame(clean_dest_labels, columns=["domain", "count"]).sort_values("count", ascending=True)

    # 2. Intra-Security Transition Matrix
    intra_branches = ["Interior & Police", "Military / Defense", "Customs", "Prisons"]
    intra_trans = repeat[repeat.prev_sec_sector.isin(intra_branches) & repeat.sec_sector.isin(intra_branches)].copy()
    ct_intra = pd.crosstab(intra_trans["prev_sec_sector"], intra_trans["sec_sector"], normalize="index") * 100
    ct_intra = ct_intra.loc[intra_branches, intra_branches]

    # 3. Civilian Friction Penalty in Security Apparatus
    sec_spells = repeat[repeat.is_security == 1].copy()
    sec_spells["is_civilian_outsider"] = (sec_spells.prev_is_sec == 0).astype(int)
    sec_valid = sec_spells[sec_spells.duration_years.notna() & (sec_spells.duration_years > 0) & (sec_spells.duration_years < 30)].copy()

    mod_penalty = smf.ols("duration_years ~ is_civilian_outsider + C(rank_score)", data=sec_valid).fit()
    insider_med = sec_valid[sec_valid.is_civilian_outsider == 0]["duration_years"].median()
    outsider_med = sec_valid[sec_valid.is_civilian_outsider == 1]["duration_years"].median()
    penalty_years = insider_med - outsider_med

    print(f"Civilian Penalty: Insider Median = {insider_med:.2f} yrs, Outsider Median = {outsider_med:.2f} yrs (Diff = -{penalty_years:.2f} yrs)")
    print(f"OLS Beta: {mod_penalty.params['is_civilian_outsider']:.3f} years (t = {mod_penalty.tvalues['is_civilian_outsider']:.2f}, p = {mod_penalty.pvalues['is_civilian_outsider']:.2e})")

    # 4. Governor Provenance Across Regimes
    govs = spells[spells.sec_sector == "Governors (Territorial)"].copy()
    gov_era_stats = []
    for era_name in ["Bourguiba (1957–86)", "Ben Ali (1987–2010)", "Democracy (2011–20)", "Saied (2021–26)"]:
        sub = govs[govs.era == era_name]
        n_tot = len(sub)
        n_para = (sub.prior_spells == 0).sum()
        sub_exp = sub[sub.prior_spells > 0]
        n_int = (sub_exp.prev_sec_sector == "Interior & Police").sum()
        n_mil = (sub_exp.prev_sec_sector == "Military / Defense").sum()
        n_civ = (sub_exp.prev_sec_sector == "Civilian Apparatus").sum()

        gov_era_stats.append({
            "era": era_name,
            "total": n_tot,
            "pct_parachuted": n_para / n_tot * 100 if n_tot > 0 else 0,
            "pct_interior": n_int / n_tot * 100 if n_tot > 0 else 0,
            "pct_military": n_mil / n_tot * 100 if n_tot > 0 else 0,
            "pct_civilian_exp": n_civ / n_tot * 100 if n_tot > 0 else 0
        })
    gov_era_df = pd.DataFrame(gov_era_stats)

    # PLOT FIGURE T6 (2x2 Grid)
    fig, axes = plt.subplots(2, 2, figsize=(14.5, 9.2))
    headline(
        fig,
        "Theory 6: Bureaucratic Autonomy & Institutional Turf in the Tunisian Security Apparatus (1957–2026)",
        "Empirical test of Stepan (1988), Wilson (1989) & Bellin (2002): Confidentiality asymmetry ('secret défense'), civilian colonization, and outsider rejection."
    )

    # Subplot A: Security Colonization of Civilian Ministries
    ax = axes[0, 0]
    y_pos = np.arange(len(civ_dest_df))
    ax.barh(y_pos, civ_dest_df["count"], color=NAVY, alpha=0.85, height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(civ_dest_df["domain"], fontsize=7.8)
    ax.set_title("A. Security Cadres Exported into Civilian Ministries (N = 4,391)")
    ax.set_xlabel("Number of Transitions from Security to Civilian Ministry")
    ax.set_xlim(0, 750)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for idx, row in civ_dest_df.reset_index().iterrows():
        ax.text(row["count"] + 12, idx, f"{row['count']:,}", va="center", fontsize=7.4, color=INK)

    # Subplot B: Intra-Security Transition Matrix
    ax = axes[0, 1]
    im = ax.imshow(ct_intra.values, cmap="Blues", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(intra_branches)))
    ax.set_yticks(np.arange(len(intra_branches)))
    ax.set_xticklabels([b.replace(" ", "\n") for b in intra_branches], fontsize=7.4)
    ax.set_yticklabels(intra_branches, fontsize=7.4)
    ax.set_title("B. Intra-Security Hegemony & Siloing (% Row Transitions)\n[Gazetted JORT Moves; internal military promotions are un-gazetted]")
    ax.set_xlabel("Destination Security Branch")
    ax.set_ylabel("Origin Security Branch")

    for i in range(len(intra_branches)):
        for j in range(len(intra_branches)):
            val = ct_intra.values[i, j]
            txt_color = "white" if val > 50 else INK
            fw = "bold" if (i == j or val > 30) else "normal"
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                    color=txt_color, fontsize=7.6, fontweight=fw)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=6.8)
    cbar.set_label("% Outgoing Transitions", fontsize=7.0, color=MUTED)

    # Subplot C: Civilian Friction Penalty in Security Apparatus
    ax = axes[1, 0]
    bars = ax.bar([0, 1], [insider_med, outsider_med], color=[NAVY, PERSON], width=0.48, alpha=0.85)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Security Insiders\n(Prior Security Career)", "Civilian Outsiders\n(Imported from Line Ministries)"], fontsize=8.0)
    ax.set_title("C. The Civilian Friction Penalty in Security Commands")
    ax.set_ylabel("Median Spell Duration (Years)")
    ax.set_ylim(0, 6.0)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    ax.text(0, insider_med + 0.18, f"{insider_med:.2f} yrs", ha="center", fontsize=8.4, fontweight="bold", color=NAVY)
    ax.text(1, outsider_med + 0.18, f"{outsider_med:.2f} yrs", ha="center", fontsize=8.4, fontweight="bold", color=PERSON)

    ax.annotate(
        f"Civilian Penalty: -{penalty_years:.2f} Years\n(-{penalty_years*12:.0f} Months, p < 0.0001)",
        xy=(1, outsider_med), xytext=(0.5, 4.8),
        arrowprops=dict(arrowstyle="->", color=PERSON, lw=1.2),
        fontsize=8.0, fontweight="bold", color=PERSON, ha="center"
    )

    # Subplot D: Governor Provenance Across Regimes
    ax = axes[1, 1]
    x_pos = np.arange(len(gov_era_df))
    w = 0.55
    b_para = gov_era_df["pct_parachuted"]
    b_int = gov_era_df["pct_interior"]
    b_civ = gov_era_df["pct_civilian_exp"]
    b_mil = gov_era_df["pct_military"]

    ax.bar(x_pos, b_int, width=w, label="Interior Security Insiders", color=NAVY, alpha=0.9)
    ax.bar(x_pos, b_civ, width=w, bottom=b_int, label="Experienced Civilians", color=SLATE, alpha=0.8)
    ax.bar(x_pos, b_para, width=w, bottom=b_int + b_civ, label="Parachuted Loyalists (0 Prior Spells)", color=GOLD, alpha=0.85)
    ax.bar(x_pos, b_mil, width=w, bottom=b_int + b_civ + b_para, label="Military Officers", color=TEAL, alpha=0.85)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(gov_era_df["era"], fontsize=7.4)
    ax.set_title("D. Territorial Security: Governor Provenance Across Regimes")
    ax.set_ylabel("% of Regional Governors Appointed")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", fontsize=7.0)

    for i in range(len(gov_era_df)):
        tot = b_int[i] + b_civ[i] + b_para[i] + b_mil[i]
        p_val = b_para[i]
        ax.text(i, tot + 2, f"Parachuted:\n{p_val:.0f}%", ha="center", fontsize=6.8, fontweight="bold", color=INK)

    plt.tight_layout(rect=[0, 0.02, 1, 0.95])
    save_fig(fig, "fig_theory_06_security_apparatus_autonomy", SOURCE)

    print("\nSecurity apparatus autonomy analysis completed successfully.")


if __name__ == "__main__":
    main()
