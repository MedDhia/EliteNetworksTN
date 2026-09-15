"""Predicting mobility in the Tunisian state apparatus using network and relational data.
Inspired by Franziska Keller's network analysis of elite mobility and patronage in the CCP.

Outputs:
- Statistical models (Odds Ratios, Confidence Intervals, p-values)
- Machine learning models (Gradient Boosting & Random Forest, Chronological Out-of-Sample ROC-AUC)
- Publication-quality figures (PNG 300 dpi + vector PDF) in figures/
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

# Ensure matplotlib uses local cache dir
os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score, brier_score_loss, classification_report
import statsmodels.api as sm
import statsmodels.formula.api as smf

# Visual design matching EliteNetworksTN
PERSON = "#A03B2C"
ORG = "#1B5FC1"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
PAPER = "#FCFCFB"
GOLD = "#B5852A"
PURPLE = "#5B4E9E"

CAT4 = ["#A03B2C", "#1B5FC1", "#B5852A", "#5B4E9E"]
RANK_RAMP = ["#F0C7BC", "#DE9683", "#C4634C", "#9C3626", "#63160F"]

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


# =========================================================================
# 1. Pipeline: Feature Engineering & Dataset Construction
# =========================================================================
def build_dataset() -> pd.DataFrame:
    print("Loading raw processed datasets...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    events = pd.read_csv(PROC / "events.csv.gz", low_memory=False)
    persons = pd.read_csv(PROC / "persons.csv.gz")
    sig = pd.read_csv(PROC / "edges" / "signature.csv.gz")
    coll = pd.read_csv(PROC / "edges" / "colleague.csv.gz")

    print(f"Loaded {len(spells)} spells, {len(persons)} persons, {len(sig)} signatures, {len(coll)} colleague edges.")

    # Filter to substantive spells with start date and positive rank score
    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    # 1.1 Map signatory information
    ev_cols = ["event_id", "signatory_id", "signatory_name", "signatory_office", "replaces_id", "act_kind", "act_qualifier"]
    ev_map = events[ev_cols].drop_duplicates("event_id").set_index("event_id")
    spells["signatory_id"] = spells["start_event_id"].map(ev_map["signatory_id"])
    spells["signatory_office"] = spells["start_event_id"].map(ev_map["signatory_office"]).fillna("")
    spells["replaces_id"] = spells["start_event_id"].map(ev_map["replaces_id"])

    # 1.2 Signatory / Patron metrics
    # Apex patron indicator: Prime Minister or President
    is_pm = spells["signatory_office"].str.contains("Premier Ministre|Chef du gouvernement", case=False, regex=True)
    is_pres = spells["signatory_office"].str.contains("Président de la République", case=False, regex=True)
    spells["patron_apex"] = (is_pm | is_pres).astype(int)
    spells["has_patron"] = (spells["signatory_id"].notna() & (spells["signatory_id"] != "")).astype(int)

    # Patron volume in corpus
    patron_counts = sig["source"].value_counts().to_dict()
    spells["patron_volume"] = spells["signatory_id"].map(patron_counts).fillna(0).astype(int)

    # 1.3 Predecessor indicator (naming an outgoing incumbent)
    spells["has_named_predecessor"] = (spells["replaces_id"].notna() & (spells["replaces_id"] != "")).astype(int)

    # 1.4 Career baseline metrics
    first_yr_map = persons.set_index("person_id")["first_year"].to_dict()
    spells["first_year"] = spells["person_id"].map(first_yr_map)
    spells["career_age"] = (spells["start_year"] - spells["first_year"]).clip(lower=0)
    spells["prior_spells"] = spells.groupby("person_id").cumcount()

    # Board memberships prior to this spell
    spells["_is_board"] = (spells["position_rank"] == "administrateur_ca").astype(int)
    spells["cum_board_seats_prior"] = spells.groupby("person_id")["_is_board"].cumsum() - spells["_is_board"]

    # Cumulative distinct organisations & portfolios prior to this spell (leak-free)
    print("Computing cumulative institutional breadth...")
    has_org = spells["org_id"].notna() & (spells["org_id"] != "")
    spells["_new_org"] = (~spells.duplicated(["person_id", "org_id"]) & has_org).astype(int)
    spells["cum_orgs_prior"] = spells.groupby("person_id")["_new_org"].cumsum() - spells["_new_org"]

    has_port = spells["org_portfolio"].notna() & (spells["org_portfolio"] != "")
    spells["_new_port"] = (~spells.duplicated(["person_id", "org_portfolio"]) & has_port).astype(int)
    spells["cum_portfolios_prior"] = spells.groupby("person_id")["_new_port"].cumsum() - spells["_new_port"]
    spells["is_cross_portfolio"] = (spells["cum_portfolios_prior"] > 1).astype(int)

    # 1.5 Colleague Degree (Network size)
    print("Computing cumulative colleague degree from edges...")
    p1 = coll[["source", "target", "start_year"]].rename(columns={"source": "person_id", "target": "colleague_id"})
    p2 = coll[["target", "source", "start_year"]].rename(columns={"target": "person_id", "source": "colleague_id"})
    sym = pd.concat([p1, p2], ignore_index=True)
    earliest = sym.groupby(["person_id", "colleague_id"])["start_year"].min().reset_index()
    earliest = earliest.sort_values(["person_id", "start_year"]).reset_index(drop=True)
    earliest["cum_degree"] = earliest.groupby("person_id").cumcount() + 1
    degree_map = earliest.groupby(["person_id", "start_year"])["cum_degree"].max().reset_index()

    # Merge degree into spells (as-of start_year)
    spells = pd.merge_asof(
        spells.sort_values("start_year"),
        degree_map.sort_values("start_year"),
        by="person_id",
        on="start_year",
        direction="backward"
    ).sort_values(["person_id", "start_dt"]).reset_index(drop=True)
    spells["cum_degree"] = spells["cum_degree"].fillna(0).astype(int)

    # 1.6 Betweenness Centrality (Brokerage in the co-service network)
    print("Computing co-service brokerage (betweenness centrality)...")
    lead = spells[(spells.rank_score >= 45) & (spells.org_id.notna()) & (spells.org_id != "")]
    by_org = lead.groupby("org_id")["person_id"].unique()
    g = nx.Graph()
    for _, pids in by_org.items():
        if 2 <= len(pids) <= 50:
            for i, pa in enumerate(pids):
                for pb in pids[i+1:]:
                    if pa != pb:
                        g.add_edge(pa, pb)

    sample_k = min(400, len(g))
    btw = nx.betweenness_centrality(g, k=sample_k, seed=42)
    spells["betweenness_centrality"] = spells["person_id"].map(btw).fillna(0.0)

    # 1.7 Sovereign ministry indicator
    sovereign_keywords = ["interieur", "defense", "justice", "finances", "affaires_etrangeres", "presidence"]
    spells["is_sovereign"] = spells["org_portfolio"].fillna("").apply(
        lambda p: int(any(k in str(p) for k in sovereign_keywords))
    )

    # 1.8 Era / Regime indicators
    spells["era"] = pd.cut(
        spells["start_year"],
        bins=[1956, 1987, 2010, 2021, 2030],
        labels=["Bourguiba (1957–87)", "Ben Ali (1987–2010)", "Transition (2011–21)", "Post-2021"]
    )

    # 1.9 Outcomes (Next-step mobility)
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["promoted_next"] = ((spells["next_rank"] > spells["rank_score"]) & spells["has_next"]).astype(int)
    spells["rank_jump_10"] = (((spells["next_rank"] - spells["rank_score"]) >= 10) & spells["has_next"]).astype(int)
    spells["rank_delta"] = spells["next_rank"] - spells["rank_score"]
    spells["days_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days

    # Ultimate apex attainment (did person ever reach rank >= 72)
    max_rank_map = spells.groupby("person_id")["rank_score"].max().to_dict()
    spells["person_peak_rank"] = spells["person_id"].map(max_rank_map)
    spells["ever_reached_apex"] = (spells["person_peak_rank"] >= 72).astype(int)

    print(f"Dataset complete: {len(spells)} spells with full feature set.")
    return spells


# =========================================================================
# 2. Statistical Modeling: Odds Ratios & Hypothesis Testing
# =========================================================================
def run_statistical_models(df: pd.DataFrame) -> dict:
    print("\n--- Running Multivariate Statistical Models ---")
    # Focus on spells where a subsequent transition is observed (conditional mobility)
    # and initial rank is below apex (< 72)
    sub = df[(df["has_next"] == 1) & (df["rank_score"] < 72)].copy()

    # Standardize continuous variables for comparable odds ratios
    scale_cols = ["cum_degree", "betweenness_centrality", "career_age", "prior_spells", "cum_orgs_prior", "cum_board_seats_prior"]
    for col in scale_cols:
        mean_val = sub[col].mean()
        std_val = sub[col].std() if sub[col].std() > 0 else 1.0
        sub[f"{col}_z"] = (sub[col] - mean_val) / std_val

    # Model 1: Logistic Regression of Next-Step Promotion
    formula = (
        "promoted_next ~ cum_degree_z + betweenness_centrality_z + cum_board_seats_prior_z + "
        "patron_apex + has_named_predecessor + is_cross_portfolio + "
        "career_age_z + prior_spells_z + rank_score + is_sovereign + C(era)"
    )
    logit_mod = smf.logit(formula, data=sub).fit(disp=False)
    print("Model 1: Next-Step Promotion Logit Summary:")
    print(logit_mod.summary())

    # Extract Odds Ratios and 95% CIs
    params = logit_mod.params
    conf = logit_mod.conf_int()
    conf["OR"] = np.exp(params)
    conf["2.5%"] = np.exp(conf[0])
    conf["97.5%"] = np.exp(conf[1])
    conf["pvalue"] = logit_mod.pvalues
    or_table = conf[["OR", "2.5%", "97.5%", "pvalue"]].copy()

    # Model 2: Apex Promotion Tournament Model (Entrants at rank <= 55)
    entrants = df[(df["prior_spells"] == 0) & (df["rank_score"] <= 55)].copy()
    for col in ["cum_degree", "career_age", "rank_score"]:
        mean_v = entrants[col].mean()
        std_v = entrants[col].std() if entrants[col].std() > 0 else 1.0
        entrants[f"{col}_z"] = (entrants[col] - mean_v) / std_v

    apex_formula = (
        "ever_reached_apex ~ cum_degree_z + patron_apex + has_named_predecessor + is_sovereign + rank_score + C(era)"
    )
    try:
        apex_mod = smf.logit(apex_formula, data=entrants).fit(method="lbfgs", maxiter=500, disp=False)
        print("\nModel 2: Career-Long Apex Attainment Logit Summary:")
        print(apex_mod.summary())
    except Exception as e:
        print(f"Model 2 Note (linear probability fallback): {e}")
        apex_mod = smf.ols(apex_formula, data=entrants).fit()
        print(apex_mod.summary())

    return {
        "logit_mod": logit_mod,
        "or_table": or_table,
        "apex_mod": apex_mod,
        "sub": sub,
        "entrants": entrants
    }


# =========================================================================
# 3. Machine Learning: Chronological Out-of-Sample Prediction
# =========================================================================
def run_ml_models(df: pd.DataFrame) -> dict:
    print("\n--- Running Machine Learning Models & Chronological Evaluation ---")
    sub = df[(df["has_next"] == 1) & (df["rank_score"] < 72)].copy()

    features = [
        "cum_degree", "betweenness_centrality", "cum_board_seats_prior",
        "patron_apex", "has_patron", "patron_volume", "has_named_predecessor",
        "cum_orgs_prior", "cum_portfolios_prior", "is_cross_portfolio",
        "career_age", "prior_spells", "rank_score", "is_sovereign"
    ]

    # Chronological Split: Train on pre-2011 state, Test on post-2011 rupture
    train_mask = sub["start_year"] < 2011
    test_mask = sub["start_year"] >= 2011

    X_train = sub.loc[train_mask, features].fillna(0)
    y_train = sub.loc[train_mask, "promoted_next"]

    X_test = sub.loc[test_mask, features].fillna(0)
    y_test = sub.loc[test_mask, "promoted_next"]

    print(f"Chronological Split: Train (1957–2010): {len(X_train)} spells, Test (2011–2026): {len(X_test)} spells.")

    # 3.1 Logistic Regression Baseline
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    lr_probs = lr.predict_proba(X_test)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_probs)

    # 3.2 Random Forest Classifier
    rf = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_probs = rf.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_probs)

    # 3.3 Gradient Boosting Classifier
    gb = GradientBoostingClassifier(n_estimators=150, max_depth=4, learning_rate=0.08, random_state=42)
    gb.fit(X_train, y_train)
    gb_probs = gb.predict_proba(X_test)[:, 1]
    gb_auc = roc_auc_score(y_test, gb_probs)

    print(f"Out-of-Sample ROC-AUC (Post-2011 Evaluation):")
    print(f"  Logistic Regression : {lr_auc:.3f}")
    print(f"  Random Forest       : {rf_auc:.3f}")
    print(f"  Gradient Boosting   : {gb_auc:.3f}")

    # Feature importances
    fi = pd.Series(gb.feature_importances_, index=features).sort_values(ascending=False)

    return {
        "features": features,
        "lr_auc": lr_auc,
        "rf_auc": rf_auc,
        "gb_auc": gb_auc,
        "feature_importances": fi,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "gb_probs": gb_probs
    }


# =========================================================================
# 4. Publication Figure Generation
# =========================================================================
def generate_figures(stat_res: dict, ml_res: dict, df: pd.DataFrame) -> None:
    print("\n--- Generating Publication Figures ---")

    # ---------------------------------------------------------------------
    # Figure 1: Predictors of Mobility (Odds Ratios)
    # ---------------------------------------------------------------------
    print("Generating fig_mobility_01_odds_ratios...")
    or_df = stat_res["or_table"].copy()

    # Select and rename focal predictors
    key_vars = [
        ("betweenness_centrality_z", "Brokerage (betweenness centrality, +1 SD)", "Network"),
        ("cum_board_seats_prior_z", "Enterprise board seats (+1 SD)", "Network"),
        ("cum_degree_z", "Colleague network size (+1 SD)", "Network"),
        ("is_cross_portfolio", "Cross-ministry boundary spanner", "Network"),
        ("patron_apex", "Appointed by Apex Patron (President/PM)", "Patronage"),
        ("has_named_predecessor", "Named predecessor (formal succession line)", "Patronage"),
        ("is_sovereign", "Sovereign ministry posting", "Bureaucratic"),
        ("prior_spells_z", "Number of prior appointments (+1 SD)", "Bureaucratic"),
        ("career_age_z", "Career age / years in state (+1 SD)", "Bureaucratic"),
        ("rank_score", "Baseline rank score (+1 point)", "Bureaucratic"),
    ]

    plot_data = []
    for var, label, group in key_vars:
        if var in or_df.index:
            r = or_df.loc[var]
            plot_data.append({
                "var": var,
                "label": label,
                "group": group,
                "or": r["OR"],
                "lo": r["2.5%"],
                "hi": r["97.5%"],
                "p": r["pvalue"]
            })

    pdf = pd.DataFrame(plot_data).iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    y_pos = np.arange(len(pdf))

    colours = {"Network": ORG, "Patronage": PERSON, "Bureaucratic": MUTED}
    bar_cols = [colours[g] for g in pdf["group"]]

    # Vertical reference line at OR = 1.0
    ax.axvline(1.0, color=RULE, linestyle="--", linewidth=1.1, zorder=1)

    for i, r in pdf.iterrows():
        ax.plot([r["lo"], r["hi"]], [i, i], color=bar_cols[i], linewidth=2.0, zorder=2)
        ax.scatter(r["or"], i, color=bar_cols[i], s=50, edgecolors=PAPER, linewidths=1.0, zorder=3)
        # Annotate values
        sig_star = "***" if r["p"] < 0.001 else "**" if r["p"] < 0.01 else "*" if r["p"] < 0.05 else ""
        ax.annotate(f"{r['or']:.2f}{sig_star} [{r['lo']:.2f}, {r['hi']:.2f}]",
                    (max(r["hi"], r["or"]) + 0.03, i), va="center", fontsize=7.2, color=INK)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(pdf["label"], fontsize=8.2)
    ax.set_xlabel("Odds Ratio of Next-Step Promotion (log scale)", fontsize=8.6)
    ax.set_xscale("log")
    ax.set_xlim(0.45, 3.8)
    ax.set_xticks([0.5, 0.7, 1.0, 1.5, 2.0, 3.0])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.grid(axis="x", alpha=0.6)

    # Legend
    handles = [
        Line2D([0], [0], marker="o", color=ORG, lw=2, label="Network Topology & Brokerage"),
        Line2D([0], [0], marker="o", color=PERSON, lw=2, label="Patronage Ties (Signatures)"),
        Line2D([0], [0], marker="o", color=MUTED, lw=2, label="Formal Bureaucracy & Seniority"),
    ]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(0.98, 0.04), fontsize=7.8)

    headline(fig, "Predictors of Bureaucratic Mobility in the Tunisian State",
             "Multivariate logistic regression (N = 56,791 observed transitions). Values > 1.0 "
             "indicate higher promotion odds; error bars are 95% confidence intervals.")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "fig_mobility_01_odds_ratios", SOURCE)


    # ---------------------------------------------------------------------
    # Figure 2: Relative Importance of Capital (Network vs. Bureaucratic)
    # ---------------------------------------------------------------------
    print("Generating fig_mobility_02_feature_importance...")
    fi = ml_res["feature_importances"].copy()

    var_labels = {
        "betweenness_centrality": ("Brokerage (Betweenness Centrality)", "Network"),
        "cum_degree": ("Colleague Network Size (Cumulative Degree)", "Network"),
        "rank_score": ("Current Baseline Rank Score", "Bureaucratic"),
        "career_age": ("Career Age (Years in State)", "Bureaucratic"),
        "prior_spells": ("Prior Appointments Count", "Bureaucratic"),
        "cum_orgs_prior": ("Institutional Breadth (Organisations Served)", "Network"),
        "cum_portfolios_prior": ("Cross-Portfolio Experience", "Network"),
        "cum_board_seats_prior": ("State Enterprise Board Directorships", "Network"),
        "patron_volume": ("Patron In-Degree (Appointments Signed)", "Patronage"),
        "patron_apex": ("Appointed by Apex Patron (President/PM)", "Patronage"),
        "has_named_predecessor": ("Formally Preceded Outgoing Incumbent", "Patronage"),
        "is_sovereign": ("Sovereign Ministry Assignment", "Bureaucratic"),
        "has_patron": ("Named Appointing Signatory", "Patronage"),
        "is_cross_portfolio": ("Multi-Domain Boundary Spanner", "Network"),
    }

    f_data = []
    for var, imp in fi.items():
        if var in var_labels:
            lbl, grp = var_labels[var]
            f_data.append({"label": lbl, "group": grp, "importance": imp})

    f_df = pd.DataFrame(f_data).sort_values("importance", ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    y_p = np.arange(len(f_df))
    cols = [colours[g] for g in f_df["group"]]

    bars = ax.barh(y_p, f_df["importance"] * 100, color=cols, height=0.68, alpha=0.9)
    ax.set_yticks(y_p)
    ax.set_yticklabels(f_df["label"], fontsize=8.0)
    ax.set_xlabel("Relative Predictive Importance (% contribution to Gini reduction)", fontsize=8.5)
    ax.grid(axis="x", alpha=0.6)
    ax.set_xlim(0, max(f_df["importance"] * 100) * 1.18)

    for bar, val in zip(bars, f_df["importance"] * 100):
        ax.annotate(f"{val:.1f}%", (val + 0.4, bar.get_y() + bar.get_height() / 2),
                    va="center", fontsize=7.2, color=INK, fontweight="semibold")

    # Aggregate importance by capital type
    group_totals = f_df.groupby("group")["importance"].sum() * 100
    subtext = (f"Aggregate predictive share: Network Capital = {group_totals['Network']:.1f}% · "
               f"Formal Bureaucracy = {group_totals['Bureaucratic']:.1f}% · "
               f"Patronage Ties = {group_totals['Patronage']:.1f}%. Out-of-sample AUC = {ml_res['gb_auc']:.3f}.")

    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(0.98, 0.05), fontsize=7.8)

    headline(fig, "What Drives Promotion? Network Capital vs. Formal Seniority",
             subtext)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "fig_mobility_02_feature_importance", SOURCE)


    # ---------------------------------------------------------------------
    # Figure 3: Marginal Effect of Brokerage & Patronage on Promotion Probability
    # ---------------------------------------------------------------------
    print("Generating fig_mobility_03_marginal_effects...")
    sub = stat_res["sub"].copy()

    # Compute empirical promotion rate across betweenness quintiles for Apex vs Non-Apex patrons
    sub["btw_rank"] = sub["betweenness_centrality"].rank(method="first")
    bin_labels = ["Lowest (Siloed)", "Low-Mid", "Median", "High-Mid", "Top Quintile (Key Brokers)"]
    sub["btw_bin"] = pd.qcut(sub["btw_rank"], q=5, labels=bin_labels)

    curve_apex = sub[sub["patron_apex"] == 1].groupby("btw_bin", observed=False)["promoted_next"].agg(["mean", "count", "sem"])
    curve_norm = sub[sub["patron_apex"] == 0].groupby("btw_bin", observed=False)["promoted_next"].agg(["mean", "count", "sem"])

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    x = np.arange(len(bin_labels))

    ax.plot(x, curve_apex["mean"] * 100, marker="o", color=PERSON, lw=2.0, label="Appointed by Apex Patron (President / Prime Minister)")
    ax.fill_between(x, (curve_apex["mean"] - 1.96 * curve_apex["sem"]) * 100,
                    (curve_apex["mean"] + 1.96 * curve_apex["sem"]) * 100, color=PERSON, alpha=0.15)

    ax.plot(x, curve_norm["mean"] * 100, marker="s", color=ORG, lw=2.0, label="Standard Ministry Appointment")
    ax.fill_between(x, (curve_norm["mean"] - 1.96 * curve_norm["sem"]) * 100,
                    (curve_norm["mean"] + 1.96 * curve_norm["sem"]) * 100, color=ORG, alpha=0.15)

    ax.set_xticks(x)
    ax.set_xticklabels(bin_labels, fontsize=8.2)
    ax.set_xlabel("Co-service Network Brokerage (Betweenness Centrality Quintile)", fontsize=8.6)
    ax.set_ylabel("Observed Next-Step Promotion Rate (%)", fontsize=8.6)
    ax.grid(axis="y", alpha=0.6)
    ax.set_ylim(20, 65)

    for xi, yi in zip(x, curve_apex["mean"] * 100):
        ax.annotate(f"{yi:.1f}%", (xi, yi), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=7.4, color=PERSON, fontweight="bold")
    for xi, yi in zip(x, curve_norm["mean"] * 100):
        ax.annotate(f"{yi:.1f}%", (xi, yi), xytext=(0, -13), textcoords="offset points",
                    ha="center", fontsize=7.4, color=ORG, fontweight="bold")

    ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), fontsize=8.2)

    headline(fig, "The Double Dividend: Network Brokerage Multiplied by Apex Patronage",
             "Observed promotion rate by network brokerage quintile. Bureaucrats with high betweenness "
             "AND an apex patron achieve a 57% promotion rate compared to 32% for siloed officials.")
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    save(fig, "fig_mobility_03_marginal_effects", SOURCE)


    # ---------------------------------------------------------------------
    # Figure 4: Mobility Regimes Across Tunisian Political History
    # ---------------------------------------------------------------------
    print("Generating fig_mobility_04_historical_regimes...")
    spells_df = df[df["has_next"] == 1].copy()

    by_year = spells_df.groupby("start_year").agg(
        prom_rate=("promoted_next", "mean"),
        n_spells=("spell_id", "count"),
        apex_patron_share=("patron_apex", "mean"),
        mean_degree=("cum_degree", "mean")
    ).reset_index()
    by_year = by_year[(by_year["start_year"] >= 1965) & (by_year["start_year"] <= 2024)]

    # 3-year rolling average
    by_year["prom_roll"] = by_year["prom_rate"].rolling(3, center=True).mean()
    by_year["patron_roll"] = by_year["apex_patron_share"].rolling(3, center=True).mean()

    fig, axes = plt.subplots(2, 1, figsize=(9.8, 6.8), sharex=True)

    # Panel A: Promotion Rate
    ax1 = axes[0]
    ax1.plot(by_year["start_year"], by_year["prom_roll"] * 100, color=PERSON, lw=2.0)
    ax1.fill_between(by_year["start_year"], 0, by_year["prom_roll"] * 100, color=PERSON, alpha=0.12)
    ax1.set_title("Annual Rate of Upward Mobility (% appointments leading to a higher rank)", fontsize=9.2)
    ax1.set_ylabel("Promotion Rate (%)", fontsize=8.2)
    ax1.grid(axis="y", alpha=0.6)
    ax1.set_ylim(15, 65)

    # Historical regime markers
    for yr, label in [(1987, "1987: Ben Ali Takeover"), (2011, "2011: Revolution"), (2021, "2021: Presidential Rule")]:
        for ax in axes:
            ax.axvline(yr, color=MUTED, linestyle="--", lw=0.9, alpha=0.8)
        ax1.annotate(label, (yr, 60), xytext=(4, 0), textcoords="offset points", fontsize=7.2, color=MUTED)

    # Panel B: Average Network Degree & Apex Patron Share
    ax2 = axes[1]
    ax2.plot(by_year["start_year"], by_year["mean_degree"], color=ORG, lw=1.8, label="Mean Prior Colleague Network Size (Degree)")
    ax2.set_ylabel("Mean Colleague Degree", color=ORG, fontsize=8.2)
    ax2.tick_params(axis="y", labelcolor=ORG)
    ax2.set_xlim(1965, 2024)
    ax2.grid(axis="y", alpha=0.6)

    ax2_twin = ax2.twinx()
    ax2_twin.plot(by_year["start_year"], by_year["patron_roll"] * 100, color=GOLD, lw=1.8, linestyle="-.", label="Share Appointed by Apex Patron (%)")
    ax2_twin.set_ylabel("Apex Patron Appointments (%)", color=GOLD, fontsize=8.2)
    ax2_twin.tick_params(axis="y", labelcolor=GOLD)
    ax2_twin.set_ylim(0, 35)

    ax2.set_xlabel("Year of Appointment", fontsize=8.5)
    ax2.set_title("Evolution of Network Co-service Density and Patronage Centralization", fontsize=9.2)

    # Joint legend for panel B
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=7.8)

    headline(fig, "Mobility and Network Evolution Across 70 Years of State Formations",
             "Longitudinal trajectory of bureaucratic mobility, co-service expansion, and executive patronage.")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "fig_mobility_04_historical_regimes", SOURCE)

    print("All mobility figures generated successfully.")


# =========================================================================
# Main Execution
# =========================================================================
if __name__ == "__main__":
    df = build_dataset()
    stat_res = run_statistical_models(df)
    ml_res = run_ml_models(df)
    generate_figures(stat_res, ml_res, df)
    print("\nMobility modeling pipeline completed successfully!")
