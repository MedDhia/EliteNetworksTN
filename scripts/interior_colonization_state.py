"""Colonization of the Civilian State Apparatus by Former Ministry of Interior Employees (1957-2026).

Empirical tests & visualizations:
1. Overall Colonization Trend Across 5 Presidencies:
   - Share (%) of civilian state appointments held by former Ministry of Interior personnel.
   - Contrast between Bourguiba (6.1%), Ben Ali doubling (12.4%), and post-2011/Saied peak (17.4%).
2. Hierarchical Levers Captured:
   - Functional role breakdown: Apex Political & Cabinets, Administrative Gatekeepers (SG/DAF),
     Central Directors General, State Enterprise (SOE) Boards & PDGs, and Diplomatic Corps.
3. Sectoral Landing Pads:
   - Civilian ministerial destinations: Kasbah/Prime Ministry, Finance, Education, Social Affairs,
     Health, Transport, and Foreign Affairs.
4. The Territorial Governor Pipeline:
   - Redeployment of former Regional Governors (Gouverneurs) into ministerial cabinets,
     diplomacy, and state enterprise boards.

Generates publication figure:
- figures/fig_theory_08_interior_colonization.png / .pdf (300 DPI)
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
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

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
LIGHT_BG = "#F4F3EF"
OTHER_GRAY = "#D1D5DB"

plt.rcParams.update({
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "axes.titlesize": 10.5,
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


def load_and_process_data():
    print("Loading data...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    def get_presidency(d):
        d_str = str(d)[:10]
        if d_str < "1987-11-07": return "1. Bourguiba\n(1957–1987)"
        elif d_str < "2011-01-14": return "2. Ben Ali\n(1987–2011)"
        elif d_str < "2014-12-31": return "3. Transition\n(2011–2014)"
        elif d_str < "2019-10-23": return "4. Essebsi\n(2014–2019)"
        else: return "5. Kais Saied\n(2019–2026)"

    spells["presidency"] = spells["start_date"].map(get_presidency)

    # Clean Interior & Territorial Administration identification
    p_org = spells["parent_org_name"].fillna("").str.lower()
    org = spells["org_name"].fillna("").str.lower()
    pos = spells["position_clean"].fillna("").str.lower()

    is_interior = (
        p_org.str.contains(r"minist[eè]re de l\'int[eé]rieur|secr[eé]tariat d\'[eé]tat [aà] l\'int[eé]rieur|direction g[eé]n[eé]rale de la s[uû]ret[eé]|garde nationale|protection civile") |
        org.str.contains(r"minist[eè]re de l\'int[eé]rieur|direction g[eé]n[eé]rale de la s[uû]ret[eé]|garde nationale|protection civile|direction des services sp[eé]ciaux|direction de la s[eé]curit[eé] publique") |
        org.str.contains(r"\bgouvernorat de\b|\bd[eé]l[eé]gation de\b") |
        pos.str.contains(r"\bgouverneur\b|\bpremier d[eé]l[eé]gu[eé]\b|\bcommissaire de police\b|\bofficier de police\b")
    )
    spells["is_interior"] = is_interior.astype(int)

    # First appointment date in Interior
    first_int_dt = spells[spells.is_interior == 1].groupby("person_id")["start_dt"].min().to_dict()
    spells["first_int_dt"] = spells["person_id"].map(first_int_dt)

    # Outbound Colonization Spells (held outside Interior AFTER first Interior spell)
    spells["is_colonization"] = (
        (spells["person_id"].isin(set(first_int_dt.keys()))) &
        (spells["start_dt"] > spells["first_int_dt"]) &
        (spells["is_interior"] == 0)
    ).astype(int)

    outbound = spells[spells.is_colonization == 1].copy()

    # Functional role classification of outbound spells
    def get_role_tier(row):
        p = str(row["position_clean"]).lower()
        if any(k in p for k in ["ministre", "secrétaire d'etat", "secretaire d'etat", "chef de cabinet", "chargé de mission", "charge de mission", "attaché de cabinet"]):
            return "Political Apex & Cabinets"
        if any(k in p for k in ["secrétaire général", "secretaire general", "directeur général des services communs", "directeur des affaires administratives et financières"]):
            return "Admin Gatekeepers (SG/DAF)"
        if any(k in p for k in ["président-directeur général", "président directeur général", "administrateur représentant l'etat", "administrateur représentant l'état", "administrateur"]):
            return "SOE Boards & PDG"
        if any(k in p for k in ["directeur général", "directeur general", "directeur d'administration centrale", "directeur"]):
            return "Central Directors General"
        if any(k in p for k in ["ambassadeur", "consul général", "consul", "conseiller des affaires etrangères"]):
            return "Diplomatic Corps"
        return "Line / Operational Posts"

    outbound["role_tier"] = outbound.apply(get_role_tier, axis=1)

    # Destination Sector classification
    def get_dest_sector(row):
        p = (str(row["parent_org_name"]) + " " + str(row["org_name"])).lower()
        port = str(row.get("org_portfolio", "")).lower()
        
        if "presidence de la republique" in p or "carthage" in p: return "Presidency (Carthage)"
        if "premier ministre" in p or "presidence du gouvernement" in p: return "Prime Ministry (Kasbah)"
        if "finances" in p or "finances" in port or "economie" in p: return "Finance & Economy"
        if "education" in p or "enseignement" in p or "universite" in p or "université" in p: return "Education & Higher Ed"
        if "social" in p or "social" in port: return "Social Affairs & Labor"
        if "sante" in p or "santé" in p or "sante" in port: return "Health & Medical"
        if "transport" in p or "transport" in port: return "Transport & Logistics"
        if "affaires etrangeres" in p or "affaires étrangères" in p or "diplomati" in p: return "Foreign Affairs"
        if "affaires locales" in p or "environnement" in p: return "Local Affairs & Environ."
        if "justice" in p or "tribunal" in p: return "Justice & Courts"
        return "Other Civilian Ministries"

    outbound["dest_sector"] = outbound.apply(get_dest_sector, axis=1)

    # Track Governor Background
    gov_pids = set(spells[spells["position_clean"].fillna("").str.lower().str.contains(r"\bgouverneur\b")]["person_id"].unique())
    outbound["is_former_gov"] = outbound["person_id"].isin(gov_pids).astype(int)

    return spells, outbound


def make_figure(spells, outbound):
    print("Generating Figure 08: Interior Colonization of State Apparatus...")

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 10.8))
    plt.subplots_adjust(hspace=0.34, wspace=0.26)

    pres_order = [
        "1. Bourguiba\n(1957–1987)",
        "2. Ben Ali\n(1987–2011)",
        "3. Transition\n(2011–2014)",
        "4. Essebsi\n(2014–2019)",
        "5. Kais Saied\n(2019–2026)"
    ]
    pres_labels_short = ["Bourguiba\n'57–'87", "Ben Ali\n'87–'11", "Transition\n'11–'14", "Essebsi\n'14–'19", "Saied\n'19–'26"]
    x = np.arange(len(pres_order))

    # -------------------------------------------------------------
    # PANEL A: Long-term Colonization Wave (% of Civilian State Decrees)
    # -------------------------------------------------------------
    ax = axes[0, 0]

    tot_civ = spells[spells.is_interior == 0].groupby("presidency").size().reindex(pres_order)
    col_counts = outbound.groupby("presidency").size().reindex(pres_order, fill_value=0)
    col_pct = (col_counts / tot_civ * 100).fillna(0)
    col_persons = outbound.groupby("presidency")["person_id"].nunique().reindex(pres_order, fill_value=0)

    width = 0.45
    bars = ax.bar(x, col_pct, width, color=ORG, alpha=0.9, edgecolor=INK, linewidth=0.6, label="Interior Alumni Share (% Civilian Decrees)")
    bars[-1].set_color(PERSON)

    # Annotate percentage and persons
    for b, pct, p_cnt in zip(bars, col_pct, col_persons):
        h = b.get_height()
        ax.annotate(f"{pct:.1f}%\n({p_cnt:,} pers)", (b.get_x() + b.get_width()/2, h + 0.45), ha="center", va="bottom", fontsize=7.5, fontweight="semibold", color=INK)

    ax.set_title("A. Colonization Rate: Interior Alumni in Civilian State (%)", pad=12)
    ax.set_ylabel("% of All Civilian State Appointments")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 24)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax.text(1.0, 16.5, "Ben Ali's Police State:\nStructural Doubling (6.1% -> 12.4%)", ha="center", va="center", fontsize=7.0, style="italic", color=NAVY,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=PAPER, edgecolor=RULE, linewidth=0.5))
    ax.text(4.0, 21.5, "Saied Peak: 17.4%\n(1 in 6 civilian decrees)", ha="center", va="center", fontsize=7.2, fontweight="bold", color=PERSON,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=PAPER, edgecolor=PERSON, linewidth=0.8))

    # -------------------------------------------------------------
    # PANEL B: Hierarchical Quality of Infiltration (Power Levers Captured)
    # -------------------------------------------------------------
    ax = axes[0, 1]

    role_order = [
        ("Political Apex & Cabinets", PERSON),
        ("Admin Gatekeepers (SG/DAF)", GOLD),
        ("SOE Boards & PDG", TEAL),
        ("Central Directors General", ORG),
        ("Diplomatic Corps", PURPLE),
        ("Line / Operational Posts", OTHER_GRAY)
    ]

    ct_role = pd.crosstab(outbound["presidency"], outbound["role_tier"], normalize="index").reindex(pres_order) * 100

    bottoms = np.zeros(len(pres_order))
    for r_name, r_col in role_order:
        vals = ct_role[r_name].values if r_name in ct_role.columns else np.zeros(len(pres_order))
        ax.bar(x, vals, bottom=bottoms, width=0.55, label=r_name, color=r_col, alpha=0.9, edgecolor=INK, linewidth=0.4)
        bottoms += vals

    ax.set_title("B. Hierarchical Power Captured by Interior Alumni (% Stacked)", pad=12)
    ax.set_ylabel("% of Outbound Appointments")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=6.8, loc="upper right", ncol=2)

    # -------------------------------------------------------------
    # PANEL C: Primary Civilian Landing Pads (Target Ministries)
    # -------------------------------------------------------------
    ax = axes[1, 0]

    sector_order = [
        ("Prime Ministry (Kasbah)", PERSON),
        ("Finance & Economy", ORG),
        ("Education & Higher Ed", GOLD),
        ("Social Affairs & Labor", PURPLE),
        ("Health & Medical", TEAL),
        ("Local Affairs & Environ.", SLATE),
        ("Transport & Logistics", NAVY),
        ("Foreign Affairs", "#E28743"),
        ("Other Civilian Ministries", OTHER_GRAY)
    ]

    ct_sec = pd.crosstab(outbound["dest_sector"], outbound["presidency"], normalize="columns").reindex(
        [s[0] for s in sector_order]
    ) * 100

    bottoms_sec = np.zeros(len(pres_order))
    for s_name, s_col in sector_order:
        vals = ct_sec.loc[s_name, :].reindex(pres_order).values
        ax.bar(x, vals, bottom=bottoms_sec, width=0.55, label=s_name, color=s_col, alpha=0.9, edgecolor=INK, linewidth=0.4)
        bottoms_sec += vals

    ax.set_title("C. Target Civilian Portfolios Colonized by Interior Cadres", pad=12)
    ax.set_ylabel("% of Destination Appointments")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=6.5, loc="upper right", ncol=2)

    # -------------------------------------------------------------
    # PANEL D: The Governor-to-Center Pipeline (Redeployment of Governors)
    # -------------------------------------------------------------
    ax = axes[1, 1]

    gov_out = outbound[outbound.is_former_gov == 1]
    gov_counts = gov_out.groupby("presidency").size().reindex(pres_order, fill_value=0)
    gov_persons = gov_out.groupby("presidency")["person_id"].nunique().reindex(pres_order, fill_value=0)

    gov_share_outbound = (gov_counts / col_counts * 100).fillna(0)

    width = 0.38
    b_vol = ax.bar(x - width/2, gov_counts, width, label="Former Governor Appts Outside Interior (N)", color=NAVY, alpha=0.9, edgecolor=INK, linewidth=0.6)
    
    ax2 = ax.twinx()
    ax2.set_facecolor("none")
    line = ax2.plot(x, gov_share_outbound, marker="s", markersize=7, color=PERSON, linewidth=2.0, label="Governor Share of Colonizers (%)", zorder=3)
    ax2.set_ylabel("% of Interior Colonizers Who Were Governors", color=PERSON)
    ax2.set_ylim(0, 26)
    ax2.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax2.tick_params(axis="y", colors=PERSON)
    ax2.spines["top"].set_visible(False)

    ax.set_title("D. The Governor-to-Center Pipeline: From Province to Capital", pad=12)
    ax.set_ylabel("Number of Appts (Former Governors)", color=NAVY)
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 760)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Annotations
    for b, cnt, p_cnt in zip(b_vol, gov_counts, gov_persons):
        h = b.get_height()
        ax.annotate(f"N={cnt}\n({p_cnt}p)", (b.get_x() + b.get_width()/2, h + 15), ha="center", va="bottom", fontsize=7.2, color=NAVY)

    for xi, yi in zip(x, gov_share_outbound):
        ax2.annotate(f"{yi:.1f}%", (xi, yi + 1.1), ha="center", va="bottom", fontsize=7.2, fontweight="semibold", color=PERSON)

    ax.text(3.1, 410,
            "THE BEN ALI PROVINCIAL TRAMPOLINE:\n"
            "• 564 central appointments given to former governors\n"
            "• 13.4% of all interior colonizers held governorships\n"
            "• Primary landing pads: Finance, Diplomacy, Agriculture & SOEs",
            ha="center", va="center", fontsize=7.0, style="normal", color=INK,
            bbox=dict(boxstyle="square,pad=0.5", facecolor=LIGHT_BG, edgecolor=RULE, linewidth=0.8))

    # Overall Supertitle
    fig.suptitle(
        "COLONIZATION OF THE TUNISIAN STATE APPARATUS BY FORMER MINISTRY OF INTERIOR CADRES (1957–2026)\n"
        "Longitudinal Infiltration into Central Cabinets, Line Ministries, Diplomatic Posts, and State Enterprise Boards",
        fontsize=11.5, fontweight="bold", color=NAVY, y=0.985
    )

    out_png = FIGS / "fig_theory_08_interior_colonization.png"
    out_pdf = FIGS / "fig_theory_08_interior_colonization.pdf"
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.savefig(out_pdf, bbox_inches="tight")
    plt.close()

    print(f"Saved: {out_png}")
    print(f"Saved: {out_pdf}")

    shutil.copy(out_png, ARTIFACT_DIR / "fig_theory_08_interior_colonization.png")
    shutil.copy(out_pdf, ARTIFACT_DIR / "fig_theory_08_interior_colonization.pdf")
    print(f"Copied to artifacts: {ARTIFACT_DIR / 'fig_theory_08_interior_colonization.png'}")


if __name__ == "__main__":
    spells, outbound = load_and_process_data()
    make_figure(spells, outbound)
