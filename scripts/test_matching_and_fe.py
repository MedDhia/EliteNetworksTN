"""
Verification of Institutional Gender Biases Using Matching Techniques and Fixed Effects.
Methods:
1. Coarsened Exact Matching (CEM) on Rank x Cohort x Ministry.
2. Propensity Score Matching (PSM, 1:1 Nearest-Neighbor with caliper & covariate balance diagnostics).
3. Multi-Way Fixed Effects:
   - Rank-Step FE + Ministry FE + Cohort FE
   - High-Dimensional Ministry x Cohort Fixed Effects (Within-Ministry-Cohort Estimator)
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

ROOT = Path("/Users/mohameddhiahammami/.gemini/antigravity/scratch/repo")
sys.path.append(str(ROOT / "scripts"))
from gender_vertical_mobility import load_and_classify_gender

def main():
    print("Loading data...")
    spells, persons = load_and_classify_gender()
    spells["is_female"] = (spells["gender"] == "Female").astype(int)

    # 1. Career transitions & wait times
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["days_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days
    spells["years_to_next"] = spells["days_to_next"] / 365.25
    spells["promoted_next"] = ((spells["next_rank"] > spells["rank_score"]) & spells["has_next"]).astype(int)

    # Cohort 5-year bins
    spells["cohort_5yr"] = pd.cut(
        spells["start_year"],
        bins=list(range(1955, 2031, 5)),
        labels=[f"{y}-{y+4}" for y in range(1955, 2026, 5)],
        right=False
    ).astype(str)

    spells["portfolio_clean"] = spells["org_portfolio"].fillna("OTHER").astype(str)
    # Group rare portfolios
    top_ports = spells["portfolio_clean"].value_counts().nlargest(20).index
    spells["port_group"] = spells["portfolio_clean"].where(spells["portfolio_clean"].isin(top_ports), "OTHER")

    # Filter promoted subset
    prom = spells[(spells.promoted_next == 1) & (spells.years_to_next.between(0.1, 20))].copy()
    prom["rank_step"] = prom["rank_score"].astype(int).astype(str) + " -> " + prom["next_rank"].astype(int).astype(str)
    # Specific single-step transitions
    step_dict = {
        "35 -> 45": "35 -> 45 (Chef to Sous-dir)",
        "45 -> 55": "45 -> 55 (Sous-dir to Dir)",
        "55 -> 65": "55 -> 65 (Dir to DG)"
    }
    prom["step_type"] = prom["rank_step"].map(step_dict).fillna("Other Promotion")

    print(f"\n========================================================")
    print(f"PART 1: FIXED EFFECTS REGRESSIONS ON PROMOTION VELOCITY")
    print(f"========================================================")
    print(f"Sample of upward promotions: N = {len(prom):,}")
    print(f"Male: {(prom.gender == 'Male').sum():,}, Female: {(prom.gender == 'Female').sum():,}")

    # Model 1: Pooled OLS
    m1 = smf.ols("years_to_next ~ is_female + rank_score + start_year", data=prom).fit()
    print("\n--- Model 1: Pooled OLS ---")
    print(f"Female coef: {m1.params['is_female']:+.4f} years ({m1.params['is_female']*12:+.2f} mo), SE: {m1.bse['is_female']:.4f}, t: {m1.tvalues['is_female']:.2f}, p: {m1.pvalues['is_female']:.4e}")

    # Model 2: Two-Way Fixed Effects (Step FE + Ministry FE + Cohort FE)
    m2 = smf.ols("years_to_next ~ is_female + C(rank_step) + C(port_group) + C(cohort_5yr)", data=prom).fit()
    print("\n--- Model 2: Multi-Way Fixed Effects (Step FE + Ministry FE + 5yr Cohort FE) ---")
    print(f"Female coef: {m2.params['is_female']:+.4f} years ({m2.params['is_female']*12:+.2f} mo), SE: {m2.bse['is_female']:.4f}, t: {m2.tvalues['is_female']:.2f}, p: {m2.pvalues['is_female']:.4e}")

    # Model 3: High-Dimensional Ministry x Cohort Fixed Effects
    prom["port_x_cohort"] = prom["port_group"] + "_" + prom["cohort_5yr"]
    # Drop singletons
    valid_strata = prom["port_x_cohort"].value_counts()[prom["port_x_cohort"].value_counts() > 5].index
    prom_hd = prom[prom["port_x_cohort"].isin(valid_strata)].copy()
    m3 = smf.ols("years_to_next ~ is_female + C(rank_step) + C(port_x_cohort)", data=prom_hd).fit()
    print("\n--- Model 3: High-Dimensional (Ministry x Cohort FE + Rank-Step FE) ---")
    print(f"Female coef: {m3.params['is_female']:+.4f} years ({m3.params['is_female']*12:+.2f} mo), SE: {m3.bse['is_female']:.4f}, t: {m3.tvalues['is_female']:.2f}, p: {m3.pvalues['is_female']:.4e}")

    print(f"\n========================================================")
    print(f"PART 2: COARSENED EXACT MATCHING (CEM) ON PROMOTION VELOCITY")
    print(f"========================================================")
    # Stratify by: rank_step x port_group x cohort_5yr
    prom["cem_stratum"] = prom["rank_step"] + " | " + prom["port_group"] + " | " + prom["cohort_5yr"]
    strata_counts = prom.groupby(["cem_stratum", "is_female"]).size().unstack(fill_value=0)
    # Keep only strata with BOTH male (>0) and female (>0)
    matched_strata = strata_counts[(strata_counts[0] > 0) & (strata_counts[1] > 0)].index
    cem_df = prom[prom.cem_stratum.isin(matched_strata)].copy()

    n_f_total = (prom.is_female == 1).sum()
    n_f_matched = (cem_df.is_female == 1).sum()
    n_m_matched = (cem_df.is_female == 0).sum()
    print(f"CEM Strata with common support: {len(matched_strata):,}")
    print(f"Matched Females: {n_f_matched:,} / {n_f_total:,} ({n_f_matched/n_f_total*100:.1f}% on support)")
    print(f"Matched Males: {n_m_matched:,}")

    # Compute CEM weights for ATT
    strata_n = cem_df.groupby("cem_stratum")["is_female"].agg(N_T=lambda x: (x==1).sum(), N_C=lambda x: (x==0).sum())
    total_T = (cem_df.is_female == 1).sum()
    total_C = (cem_df.is_female == 0).sum()

    cem_df = cem_df.merge(strata_n, on="cem_stratum")
    # Weight = 1 for treated, (N_T / total_T) / (N_C / total_C) for control
    cem_df["weight"] = np.where(
        cem_df["is_female"] == 1,
        1.0,
        (cem_df["N_T"] / total_T) / (cem_df["N_C"] / total_C)
    )

    # Weighted OLS under CEM
    wls_cem = smf.wls("years_to_next ~ is_female", data=cem_df, weights=cem_df["weight"]).fit()
    print("\n--- CEM Weighted Average Treatment Effect on the Treated (ATT) ---")
    print(f"Female ATT: {wls_cem.params['is_female']:+.4f} years ({wls_cem.params['is_female']*12:+.2f} months delay)")
    print(f"SE: {wls_cem.bse['is_female']:.4f}, t: {wls_cem.tvalues['is_female']:.2f}, p: {wls_cem.pvalues['is_female']:.4e}")
    print(f"95% CI: [{wls_cem.conf_int().loc['is_female', 0]*12:+.2f}, {wls_cem.conf_int().loc['is_female', 1]*12:+.2f}] months")

    print(f"\n========================================================")
    print(f"PART 3: PROPENSITY SCORE MATCHING (PSM) ON PROMOTION VELOCITY")
    print(f"========================================================")
    # Estimate propensity score
    port_dummies = pd.get_dummies(prom["port_group"], prefix="port", drop_first=True, dtype=float)
    X_psm = pd.concat([prom[["rank_score", "start_year"]], port_dummies], axis=1)
    y_psm = prom["is_female"]

    ps_model = LogisticRegression(max_iter=1000, penalty=None)
    ps_model.fit(X_psm, y_psm)
    prom["p_score"] = ps_model.predict_proba(X_psm)[:, 1]
    prom["logit_ps"] = np.log(prom["p_score"] / (1 - prom["p_score"]))

    treated = prom[prom.is_female == 1].copy()
    control = prom[prom.is_female == 0].copy()

    # Caliper matching (0.2 SD of logit_ps)
    caliper = 0.2 * prom["logit_ps"].std()
    nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
    nn.fit(control[["logit_ps"]])
    distances, indices = nn.kneighbors(treated[["logit_ps"]])

    matched_treated = []
    matched_control = []
    for t_idx, (d, c_idx) in enumerate(zip(distances, indices)):
        if d[0] <= caliper:
            matched_treated.append(treated.iloc[t_idx])
            matched_control.append(control.iloc[c_idx[0]])

    df_t = pd.DataFrame(matched_treated)
    df_c = pd.DataFrame(matched_control)
    print(f"PSM Matched Pairs (within caliper {caliper:.3f}): {len(df_t):,} pairs")

    print("\nCovariate Balance (Standardized Mean Differences):")
    for var in ["start_year", "rank_score"]:
        mean_t_raw = treated[var].mean()
        mean_c_raw = control[var].mean()
        pooled_sd_raw = np.sqrt((treated[var].var() + control[var].var()) / 2)
        smd_raw = (mean_t_raw - mean_c_raw) / pooled_sd_raw

        mean_t_match = df_t[var].mean()
        mean_c_match = df_c[var].mean()
        pooled_sd_match = np.sqrt((df_t[var].var() + df_c[var].var()) / 2)
        smd_match = (mean_t_match - mean_c_match) / pooled_sd_match
        print(f"  {var:12s} | Raw SMD: {smd_raw:+.4f}  --->  Matched SMD: {smd_match:+.4f} (Balanced: {abs(smd_match)<0.05})")

    wait_t = df_t["years_to_next"].values
    wait_c = df_c["years_to_next"].values
    paired_diff = (wait_t - wait_c) * 12
    t_stat, p_val = stats.ttest_rel(wait_t, wait_c)
    print("\n--- PSM Paired Treatment Effect (ATT) ---")
    print(f"Mean Promotion Wait-Time Delay: {paired_diff.mean():+.2f} months")
    print(f"Median Promotion Wait-Time Delay: {np.median(paired_diff):+.2f} months")
    print(f"Paired t-statistic: {t_stat:.2f}, p-value: {p_val:.4e}")

    print(f"\n========================================================")
    print(f"PART 4: CAREER TOURNAMENT MATCHING & FIXED EFFECTS")
    print(f"========================================================")
    entrants = spells.groupby("person_id").first().reset_index()
    entrants = entrants[entrants.rank_score <= 45].copy()
    entrants["is_female"] = (entrants.gender == "Female").astype(int)

    max_rank = spells.groupby("person_id")["rank_score"].max().to_dict()
    entrants["max_rank"] = entrants["person_id"].map(max_rank)
    entrants["reached_dir"] = (entrants["max_rank"] >= 55).astype(int)
    entrants["reached_dg"] = (entrants["max_rank"] >= 65).astype(int)
    entrants["reached_apex"] = (entrants["max_rank"] >= 70).astype(int)

    entrants["cohort_5yr"] = pd.cut(
        entrants["start_year"],
        bins=list(range(1955, 2031, 5)),
        labels=[f"{y}-{y+4}" for y in range(1955, 2026, 5)],
        right=False
    ).astype(str)
    entrants["port_group"] = entrants["org_portfolio"].fillna("OTHER").where(
        entrants["org_portfolio"].isin(top_ports), "OTHER"
    )

    print(f"Total administrative entrants (Rank <= 45): N = {len(entrants):,}")
    print(f"Male entrants: {(entrants.is_female==0).sum():,}, Female entrants: {(entrants.is_female==1).sum():,}")

    entrants["stratum"] = entrants["port_group"] + "_" + entrants["cohort_5yr"]
    valid_e_strata = entrants["stratum"].value_counts()[entrants["stratum"].value_counts() > 10].index
    e_hd = entrants[entrants["stratum"].isin(valid_e_strata)].copy()

    for out, lbl in [("reached_dir", "Director (>=55)"), ("reached_dg", "Director General (>=65)"), ("reached_apex", "Apex Cabinet (>=70)")]:
        lpm = smf.ols(f"{out} ~ is_female + rank_score + C(stratum)", data=e_hd).fit()
        raw_m = entrants[entrants.is_female==0][out].mean() * 100
        raw_f = entrants[entrants.is_female==1][out].mean() * 100
        print(f"\n--- Attainment: {lbl} ---")
        print(f"Raw rates: Male = {raw_m:.1f}%, Female = {raw_f:.1f}% (Raw Gap: {raw_f - raw_m:+.1f} pp)")
        print(f"Within-Ministry-Cohort Fixed Effects LPM:")
        print(f"  Female coef: {lpm.params['is_female']*100:+.2f} percentage points, SE: {lpm.bse['is_female']*100:.2f} pp, t: {lpm.tvalues['is_female']:.2f}, p: {lpm.pvalues['is_female']:.4e}")

    entrants["cem_stratum"] = entrants["rank_score"].astype(str) + " | " + entrants["port_group"] + " | " + entrants["cohort_5yr"]
    e_strata_counts = entrants.groupby(["cem_stratum", "is_female"]).size().unstack(fill_value=0)
    e_matched_strata = e_strata_counts[(e_strata_counts[0] > 0) & (e_strata_counts[1] > 0)].index
    e_cem = entrants[entrants.cem_stratum.isin(e_matched_strata)].copy()

    e_strata_n = e_cem.groupby("cem_stratum")["is_female"].agg(N_T=lambda x: (x==1).sum(), N_C=lambda x: (x==0).sum())
    tot_T = (e_cem.is_female == 1).sum()
    tot_C = (e_cem.is_female == 0).sum()
    e_cem = e_cem.merge(e_strata_n, on="cem_stratum")
    e_cem["weight"] = np.where(e_cem["is_female"] == 1, 1.0, (e_cem["N_T"] / tot_T) / (e_cem["N_C"] / tot_C))

    print("\n--- CEM Estimates for Lifetime Apex Attainment (Exact Matched on Rank x Ministry x Cohort) ---")
    for out, lbl in [("reached_dir", "Director (>=55)"), ("reached_dg", "Director General (>=65)"), ("reached_apex", "Apex Cabinet (>=70)")]:
        w_res = smf.wls(f"{out} ~ is_female", data=e_cem, weights=e_cem["weight"]).fit()
        print(f"  {lbl:28s} | Female ATT: {w_res.params['is_female']*100:+.2f} pp (t = {w_res.tvalues['is_female']:.2f}, p = {w_res.pvalues['is_female']:.4e})")

if __name__ == "__main__":
    main()
