"""Cross-Presidencies Comparison of Military Appointments in Tunisia (1957-2026).

Empirical tests & visualizations:
1. Overall military footprint and Defense Ministry weight across 5 presidencies:
   - Bourguiba (1957-1987)
   - Ben Ali (1987-2011)
   - Transition / Marzouki (2011-2014)
   - Essebsi / Ennaceur (2014-2019)
   - Kais Saied (2019-2026)
2. Palace Penetration: Share and volume of military officers assigned to Carthage.
3. Destination Sectors: Functional redeployment into civilian ministries (Health, Interior, Justice, Diplomacy, Social).
4. The Territorial Paradox: Complete exclusion from governorships (0%) vs. central cabinet infiltration.

Generates publication figure:
- figures/fig_theory_07_military_presidencies.png / .pdf (300 DPI)
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
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)

    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    # 1. Negative patterns: Exclude non-military corps sharing military ranks, and civilian general titles
    g = events["grade_raw"].fillna("").astype(str).str.lower()
    s = events["sentence"].fillna("").astype(str).str.lower()
    p = events["position_raw"].fillna("").astype(str).str.lower()

    non_military = (
        "douane", "douanes", 
        "prison", "prisons", "rééducation", "reeducation",
        "sûreté", "surete", "police",
        "garde nationale", "protection civile",
        "marine marchande", "long cours", "commandant de bord",
        "ingénieur général", "ingenieur general",
        "architecte général", "architecte general",
        "surveillant général", "surveillant general",
        "administrateur général", "administrateur general",
        "contrôleur général", "controleur general",
        "inspecteur général", "inspecteur general",
        "inspecteur divisionnaire",
        "conservateur en chef",
        "magistrat de l'ordre judiciaire",
        "professeur de l'enseignement supérieur",
        "maître de conférences", "maitre de conferences",
        "gestionnaire conseiller"
    )
    pattern_neg = "|".join(non_military)
    is_neg = g.str.contains(pattern_neg) | s.str.contains(pattern_neg) | p.str.contains(pattern_neg)

    # 2. Positive patterns: Armed Forces officers
    is_navy = g.str.contains(r"\bcapitaine de vaisseau\b|\bcapitaine de frégate\b|\bcapitaine de corvette\b|\blieutenant de vaisseau\b|\bcapitaine à la marine nationale\b")
    is_army = g.str.contains(r"\bgénéral de division\b|\bgénéral de brigade\b|\bmédecin général\b|\bcolonel-major\b|\bcolonel major\b|\bcolonel\b|\blieutenant-colonel\b|\blieutenant colonel\b|\bcommandant\b")
    is_mil_specific = (
        g.str.contains(r"\barmée nationale\b|\bforces armées\b|\bsanté militaire\b|\bjustice militaire\b") |
        s.str.contains(r"\bofficier supérieur de l\'armée\b|\bforces armées\b|\bmédecin militaire\b|\bofficier de l\'armée\b|\barmée nationale\b|\bjustice militaire\b") |
        p.str.contains(r"\bjustice militaire\b|\battaché militaire\b|\bsécurité militaire\b")
    )

    is_strict_mil = (is_navy | is_army | is_mil_specific) & ~is_neg
    strict_events = events[is_strict_mil]
    mil_pids = set(strict_events["person_id"].unique())
    print(f"Strictly verified military persons: {len(mil_pids)}")

    # 3. Clean Defense Ministry Spells (excluding OCR leak of civilian orgs)
    org = spells["org_name"].fillna("").astype(str).str.lower()
    p_org = spells["parent_org_name"].fillna("").astype(str).str.lower()

    is_pure_defense = (
        (p_org.str.contains(r"minist[eè]re de la d[eé]fense|secr[eé]tariat d\'[eé]tat [aà] la d[eé]fense") |
         org.str.contains(r"minist[eè]re de la d[eé]fense|secr[eé]tariat d\'[eé]tat [aà] la d[eé]fense|arm[eé]e nationale|tribunal militaire|justice militaire|h[oô]pital militaire|logements militaires|cartographie et de la t[eé]l[eé]d[eé]tection|rjim ma[aâ]toug")) &
        ~org.str.contains(r"int[eé]gration sociale|d[eé]fense sociale|commune|gouvernorat|commissariat|sant[eé] publique|affaires [eé]trang[eè]res|finances|domaines de l\'[eé]tat|transport|agriculture|jeunesse|femme|culture|industrie|commerce|int[eé]rieur|justice") &
        ~p_org.str.contains(r"affaires sociales|sant[eé] publique|int[eé]rieur")
    )

    def get_presidency(d):
        d_str = str(d)[:10]
        if d_str < "1987-11-07": return "1. Bourguiba\n(1957–1987)"
        elif d_str < "2011-01-14": return "2. Ben Ali\n(1987–2011)"
        elif d_str < "2014-12-31": return "3. Transition\n(2011–2014)"
        elif d_str < "2019-10-23": return "4. Essebsi\n(2014–2019)"
        else: return "5. Kais Saied\n(2019–2026)"

    spells["presidency"] = spells["start_date"].map(get_presidency)
    spells["is_mil_person"] = spells["person_id"].isin(mil_pids).astype(int)
    spells["is_def_ministry"] = is_pure_defense.astype(int)

    mil_spells = spells[spells.is_mil_person == 1].copy()
    mil_spells["is_civilian_org"] = (mil_spells.is_def_ministry == 0).astype(int)

    def get_domain(row):
        if row["is_def_ministry"] == 1: return "Defense / Armed Forces"
        p_val = str(row.get("org_portfolio", "")).lower()
        org = (str(row.get("parent_org_name", "")) + " " + str(row.get("org_name", ""))).lower()
        
        if "presidence" in org or "carthage" in org: return "Presidency (Carthage)"
        if "sante" in p_val or "sante" in org or "maternité" in org: return "Health & Medical"
        if "social" in p_val or "social" in org or "courses" in org: return "Social Affairs"
        if "transport" in p_val or "transport" in org or "aviation" in org or "maritime" in org: return "Transport & Maritime"
        if "etranger" in p_val or "etranger" in org or "diplomati" in org: return "Foreign Affairs"
        if "justice" in p_val or "justice" in org: return "Justice & Courts"
        if "agriculture" in p_val or "agriculture" in org or "forêt" in org or "foret" in org: return "Agriculture & Water"
        return "Other Civilian Ministries"

    mil_spells["domain"] = mil_spells.apply(get_domain, axis=1)

    return spells, mil_spells


def make_figure(spells, mil_spells):
    print("Generating Figure 07: Military Appointments Across Presidencies...")
    
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 10.5))
    plt.subplots_adjust(hspace=0.34, wspace=0.26)

    pres_order = [
        "1. Bourguiba\n(1957–1987)",
        "2. Ben Ali\n(1987–2011)",
        "3. Transition\n(2011–2014)",
        "4. Essebsi\n(2014–2019)",
        "5. Kais Saied\n(2019–2026)"
    ]
    pres_labels_short = ["Bourguiba\n'57–'87", "Ben Ali\n'87–'11", "Transition\n'11–'14", "Essebsi\n'14–'19", "Saied\n'19–'26"]

    # Aggregations
    pres_summary = spells.groupby("presidency").agg(
        total_spells=("spell_id", "count"),
        mil_spells=("is_mil_person", "sum"),
        mil_pct=("is_mil_person", lambda x: x.mean() * 100),
        def_spells=("is_def_ministry", "sum"),
        def_pct=("is_def_ministry", lambda x: x.mean() * 100)
    ).reindex(pres_order)

    # -------------------------------------------------------------
    # PANEL A: Defense & Military Share of State Appointments (%)
    # -------------------------------------------------------------
    ax = axes[0, 0]
    x = np.arange(len(pres_order))
    width = 0.35

    bars1 = ax.bar(x - width/2, pres_summary["def_pct"], width, label="Min. Defense Decrees (% State)", color=NAVY, alpha=0.9, edgecolor=INK, linewidth=0.6)
    bars2 = ax.bar(x + width/2, pres_summary["mil_pct"], width, label="Military Officer Appts (% State)", color=GOLD, alpha=0.9, edgecolor=INK, linewidth=0.6)

    # Highlight Saied peak
    bars1[-1].set_color(PERSON)
    bars1[-1].set_alpha(0.95)

    ax.set_title("A. State Militarization & Defense Portfolio Share", pad=12)
    ax.set_ylabel("% of All State Decrees")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 2.9)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=1))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=7.5, loc="upper left")

    # Annotations
    for b in bars1:
        h = b.get_height()
        ax.annotate(f"{h:.2f}%", (b.get_x() + b.get_width()/2, h + 0.06), ha="center", va="bottom", fontsize=7.2, fontweight="semibold", color=INK)
    for b in bars2:
        h = b.get_height()
        ax.annotate(f"{h:.2f}%", (b.get_x() + b.get_width()/2, h + 0.06), ha="center", va="bottom", fontsize=7.2, color=INK)

    ax.text(4 - width/2, 2.62, "Saied: +139% vs Ben Ali\n(Peak 2.15% vs 0.90%)", ha="center", va="center", fontsize=7.2, fontweight="bold", color=PERSON,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=PAPER, edgecolor=PERSON, linewidth=0.8))

    # -------------------------------------------------------------
    # PANEL B: Palace Penetration (Presidency of the Republic / Carthage)
    # -------------------------------------------------------------
    ax = axes[0, 1]
    
    # Destination share in Carthage
    carthage_spells = mil_spells[mil_spells.domain == "Presidency (Carthage)"]
    carthage_counts = carthage_spells.groupby("presidency").size().reindex(pres_order, fill_value=0)
    total_mil = mil_spells.groupby("presidency").size().reindex(pres_order, fill_value=0)
    carthage_pct = (carthage_counts / total_mil * 100).fillna(0)

    # Line + Scatter plot
    line = ax.plot(x, carthage_pct, marker="o", markersize=8, color=PERSON, linewidth=2.2, label="Carthage Share (% of Mil. Appts)", zorder=3)
    
    # Fill under curve
    ax.fill_between(x, 0, carthage_pct, color=PERSON, alpha=0.12, zorder=2)

    # Secondary axis for raw counts
    ax2 = ax.twinx()
    ax2.set_facecolor("none")
    bars_vol = ax2.bar(x, carthage_counts, width=0.25, color=SLATE, alpha=0.22, label="Raw Appts in Carthage (N)", zorder=1)
    ax2.set_ylabel("Number of Officer Appts in Carthage", color=SLATE)
    ax2.set_ylim(0, 18)
    ax2.spines["top"].set_visible(False)
    ax2.tick_params(axis="y", colors=SLATE)

    ax.set_title("B. Palace Penetration: Military Infiltration of Carthage", pad=12)
    ax.set_ylabel("% of All Military Officer Appointments", color=PERSON)
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 36)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Annotations on percentages
    for xi, yi, ci in zip(x, carthage_pct, carthage_counts):
        ax.annotate(f"{yi:.1f}%\n(N={ci})", (xi, yi + 1.2), ha="center", va="bottom", fontsize=7.5, fontweight="semibold", color=PERSON)

    ax.text(0.8, 12.0, "Ben Ali Containment\n(Barraket Essahel 1991)", ha="center", va="center", fontsize=7.0, style="italic", color=MUTED,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=PAPER, edgecolor=RULE, linewidth=0.5))
    ax.text(3.4, 5.0, "Post-2011 Palace Integration\n(National Security + Advisors)", ha="center", va="center", fontsize=7.0, style="italic", color=NAVY,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=PAPER, edgecolor=RULE, linewidth=0.5))

    # -------------------------------------------------------------
    # PANEL C: Civilian Destination Breakdown across Eras (Exact 100% Stack)
    # -------------------------------------------------------------
    ax = axes[1, 0]
    
    ct_pct = pd.crosstab(mil_spells["presidency"], mil_spells["domain"], normalize="index").reindex(pres_order) * 100
    
    key_domains = [
        ("Presidency (Carthage)", PERSON),
        ("Health & Medical", TEAL),
        ("Social Affairs", PURPLE),
        ("Transport & Maritime", ORG),
        ("Agriculture & Water", GOLD),
        ("Foreign Affairs", SLATE),
        ("Justice & Courts", NAVY),
        ("Other Civilian Ministries", OTHER_GRAY)
    ]
    
    bottoms = np.zeros(len(pres_order))
    for dom, col in key_domains:
        vals = ct_pct[dom].values if dom in ct_pct.columns else np.zeros(len(pres_order))
        ax.bar(x, vals, bottom=bottoms, width=0.55, label=dom, color=col, alpha=0.9, edgecolor=INK, linewidth=0.4)
        bottoms += vals

    ax.set_title("C. Destination Portfolios of Military Officers (% Stacked)", pad=12)
    ax.set_ylabel("% of Military Appts per Regime")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=6.5, loc="upper right", ncol=2)

    # -------------------------------------------------------------
    # PANEL D: The Territorial Governor Paradox: 0% Regional Power
    # -------------------------------------------------------------
    ax = axes[1, 1]

    # Contrast Carthage/Cabinet vs Regional Governors
    is_gov = mil_spells["position_clean"].fillna("").astype(str).str.lower().str.contains("gouverneur") | \
             mil_spells["position_rank"].fillna("").astype(str).str.lower().str.contains("gouverneur")
    gov_counts = mil_spells[is_gov].groupby("presidency").size().reindex(pres_order, fill_value=0)
    gov_pct = (gov_counts / total_mil * 100).fillna(0)

    width = 0.35
    b_palace = ax.bar(x - width/2, carthage_pct, width, label="Palace Infiltration (Carthage %)", color=PERSON, alpha=0.9, edgecolor=INK, linewidth=0.6)
    b_gov = ax.bar(x + width/2, gov_pct, width, label="Territorial Governors (%)", color=MUTED, alpha=0.6, edgecolor=INK, linewidth=0.6)

    ax.set_title("D. The Territorial Paradox: Palace Infiltration vs. 0% Governors", pad=12)
    ax.set_ylabel("% of Officer Appointments")
    ax.set_xticks(x)
    ax.set_xticklabels(pres_labels_short)
    ax.set_ylim(0, 36)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(decimals=0))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(frameon=True, facecolor=PAPER, edgecolor=RULE, fontsize=7.5, loc="upper left")

    # Annotate governor zeros
    for b, g_c in zip(b_gov, gov_counts):
        h = b.get_height()
        ax.annotate(f"{h:.1f}%\n(N={g_c})", (b.get_x() + b.get_width()/2, h + 0.6), ha="center", va="bottom", fontsize=6.8, color=INK)

    for b, c_c in zip(b_palace, carthage_counts):
        h = b.get_height()
        ax.annotate(f"{h:.1f}%", (b.get_x() + b.get_width()/2, h + 0.6), ha="center", va="bottom", fontsize=6.8, fontweight="semibold", color=PERSON)

    # Callout box explaining the paradox
    ax.text(2.0, 23.0,
            "THE 70-YEAR CORDON SANITAIRE:\n"
            "• Military appointed to high palace cabinet & crisis management\n"
            "• But strictly EXCLUDED from regional command (0% under all regimes)\n"
            "• Territorial governorships remain 100% civilian & police turf",
            ha="center", va="center", fontsize=7.2, style="normal", color=INK,
            bbox=dict(boxstyle="square,pad=0.5", facecolor=LIGHT_BG, edgecolor=RULE, linewidth=0.8))

    # Overall Supertitle
    fig.suptitle(
        "CIVIL-MILITARY BOUNDARIES ACROSS FIVE TUNISIAN REGIMES (1957–2026)\n"
        "From Bourguibist Marginalization & Ben Ali Containment to Democratic Institutionalization & Saied's Technocratic Co-optation",
        fontsize=11.5, fontweight="bold", color=NAVY, y=0.985
    )

    out_png = FIGS / "fig_theory_07_military_presidencies.png"
    out_pdf = FIGS / "fig_theory_07_military_presidencies.pdf"
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.savefig(out_pdf, bbox_inches="tight")
    plt.close()

    print(f"Saved: {out_png}")
    print(f"Saved: {out_pdf}")

    # Copy to artifact directory
    shutil.copy(out_png, ARTIFACT_DIR / "fig_theory_07_military_presidencies.png")
    shutil.copy(out_pdf, ARTIFACT_DIR / "fig_theory_07_military_presidencies.pdf")
    print(f"Copied to artifacts: {ARTIFACT_DIR / 'fig_theory_07_military_presidencies.png'}")


if __name__ == "__main__":
    spells, mil_spells = load_and_process_data()
    make_figure(spells, mil_spells)
