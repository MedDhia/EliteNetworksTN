"""
Diagnostic script to test formal political science and sociological hypotheses
of gender bias in the Tunisian state apparatus (1957–2026).
"""
import gzip
import re
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
import sys
from pathlib import Path

# Paths
ROOT = Path("/Users/mohameddhiahammami/.gemini/antigravity/scratch/repo")
sys.path.append(str(ROOT / "scripts"))
from gender_vertical_mobility import load_and_classify_gender

DATA = ROOT / "data" / "processed"

def run_tests():
    spells, persons = load_and_classify_gender()
    events = pd.read_csv(DATA / "events.csv.gz", low_memory=False)

    print("Engineering features for gender bias tests...")
    spells["is_female"] = (spells["gender"] == "Female").astype(int)

    # Add signatory / apex patron
    ev_cols = ["event_id", "signatory_id", "signatory_office", "replaces_id"]
    ev_map = events[ev_cols].drop_duplicates("event_id").set_index("event_id")
    spells["signatory_office"] = spells["start_event_id"].map(ev_map["signatory_office"]).fillna("")
    is_pm = spells["signatory_office"].str.contains("Premier Ministre|Chef du gouvernement", case=False, regex=True)
    is_pres = spells["signatory_office"].str.contains("Président de la République", case=False, regex=True)
    spells["patron_apex"] = (is_pm | is_pres).astype(int)

    # Board appointments
    spells["is_board"] = (spells["position_rank"] == "administrateur_ca").astype(int)
    spells["cum_board_prior"] = spells.groupby("person_id")["is_board"].cumsum() - spells["is_board"]

    # Career age & breadth
    first_yr = spells.groupby("person_id")["year"].min().to_dict()
    spells["career_age"] = spells["year"] - spells["person_id"].map(first_yr)
    spells["prior_spells"] = spells.groupby("person_id").cumcount()

    has_port = spells["org_portfolio"].notna() & (spells["org_portfolio"] != "")
    spells["_new_port"] = (~spells.duplicated(["person_id", "org_portfolio"]) & has_port).astype(int)
    spells["cum_portfolios_prior"] = spells.groupby("person_id")["_new_port"].cumsum() - spells["_new_port"]

    # Sovereign
    sovereign_keywords = ["interieur", "defense", "justice", "finances", "affaires_etrangeres", "presidence"]
    spells["is_sovereign"] = spells["org_portfolio"].fillna("").apply(
        lambda p: int(any(k in str(p) for k in sovereign_keywords))
    )

    # Era
    spells["era"] = pd.cut(
        spells["year"],
        bins=[1956, 1987, 2010, 2021, 2030],
        labels=["Bourguiba", "Ben_Ali", "Transition", "Saied"]
    )

    # Transitions
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["promoted_next"] = ((spells["next_rank"] > spells["rank_score"]) & spells["has_next"]).astype(int)
    spells["rank_jump_10"] = (((spells["next_rank"] - spells["rank_score"]) >= 10) & spells["has_next"]).astype(int)
    spells["days_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days

    # Filter to valid transitions
    trans = spells[spells.has_next == 1].copy()
    print(f"Total valid transitions: {len(trans):,} (Female: {(trans.gender == 'Female').sum():,}, Male: {(trans.gender == 'Male').sum():,})")

    # =========================================================================
    # TEST 1: Multivariate Logistic Regression on Upward Promotion
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 1: PROMOTION PROBABILITY PENALTY")
    print("="*80)
    mod1 = smf.logit(
        "promoted_next ~ is_female + rank_score + career_age + cum_portfolios_prior + patron_apex + is_sovereign + C(era)",
        data=trans
    ).fit(disp=False)
    print(mod1.summary().tables[1])
    or_female = np.exp(mod1.params["is_female"])
    ci_lower = np.exp(mod1.conf_int().loc["is_female", 0])
    ci_upper = np.exp(mod1.conf_int().loc["is_female", 1])
    p_val = mod1.pvalues["is_female"]
    print(f"\nFemale Odds Ratio: {or_female:.4f} [95% CI: {ci_lower:.4f}, {ci_upper:.4f}], z = {mod1.tvalues['is_female']:.2f}, p = {p_val:.4e}")

    # =========================================================================
    # TEST 1B: Big Jump Promotion (Delta >= 10 points)
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 1B: FAST-TRACK / BIG JUMP PROMOTION (Rank Jump >= 10)")
    print("="*80)
    mod1b = smf.logit(
        "rank_jump_10 ~ is_female + rank_score + career_age + cum_portfolios_prior + patron_apex + is_sovereign + C(era)",
        data=trans
    ).fit(disp=False)
    print(mod1b.summary().tables[1])
    or_jump = np.exp(mod1b.params["is_female"])
    ci_l_jump = np.exp(mod1b.conf_int().loc["is_female", 0])
    ci_u_jump = np.exp(mod1b.conf_int().loc["is_female", 1])
    print(f"\nFemale Odds Ratio (Big Jump): {or_jump:.4f} [95% CI: {ci_l_jump:.4f}, {ci_u_jump:.4f}], p = {mod1b.pvalues['is_female']:.4e}")

    # =========================================================================
    # TEST 2: Gender × Apex Patronage Interaction
    # Does apex patronage benefit women as much as men?
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 2: GENDER x APEX PATRONAGE INTERACTION")
    print("="*80)
    mod2 = smf.logit(
        "promoted_next ~ is_female * patron_apex + rank_score + career_age + cum_portfolios_prior + is_sovereign + C(era)",
        data=trans
    ).fit(disp=False)
    print(mod2.summary().tables[1])

    # Calculate marginal rates
    rates = trans.groupby(["is_female", "patron_apex"])["promoted_next"].agg(total="count", rate="mean")
    print("\nEmpirical Promotion Rates by Gender & Apex Patron:")
    print(rates)

    # =========================================================================
    # TEST 3: Wait-Time Penalty ("Sticky Floors")
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 3: WAIT TIME TO PROMOTION ('STICKY FLOORS')")
    print("="*80)
    promoted = trans[(trans.promoted_next == 1) & (trans.days_to_next > 30) & (trans.days_to_next < 365.25 * 25)].copy()
    promoted["years_to_next"] = promoted["days_to_next"] / 365.25
    mean_wait_m = promoted[promoted.gender == "Male"]["years_to_next"].mean()
    median_wait_m = promoted[promoted.gender == "Male"]["years_to_next"].median()
    mean_wait_f = promoted[promoted.gender == "Female"]["years_to_next"].mean()
    median_wait_f = promoted[promoted.gender == "Female"]["years_to_next"].median()
    print(f"Male wait time (years): Mean = {mean_wait_m:.2f}, Median = {median_wait_m:.2f} (N = {(promoted.gender == 'Male').sum():,})")
    print(f"Female wait time (years): Mean = {mean_wait_f:.2f}, Median = {median_wait_f:.2f} (N = {(promoted.gender == 'Female').sum():,})")

    # t-test & Wilcoxon
    ttest = stats.ttest_ind(
        promoted[promoted.gender == "Female"]["years_to_next"],
        promoted[promoted.gender == "Male"]["years_to_next"],
        equal_var=False
    )
    print(f"Welch's t-test: t = {ttest.statistic:.3f}, p = {ttest.pvalue:.4e}")

    mod3 = smf.ols("years_to_next ~ is_female + rank_score + C(era) + is_sovereign", data=promoted).fit()
    print(mod3.summary().tables[1])

    # =========================================================================
    # TEST 4: Discretionary SOE Board Appointments
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 4: DISCRETIONARY STATE-OWNED ENTERPRISE (SOE) BOARD SEATS")
    print("="*80)
    senior = spells[spells.rank_score >= 55].copy()
    tot_senior = len(senior)
    tot_fem_senior = (senior.gender == "Female").sum()
    board_senior = senior[senior.is_board == 1]
    fem_board_pct = (board_senior.gender == "Female").mean() * 100
    fem_overall_senior_pct = (senior.gender == "Female").mean() * 100
    print(f"Senior Spells (Rank >= 55): {tot_senior:,} (Female: {tot_fem_senior:,}, {fem_overall_senior_pct:.1f}%)")
    print(f"Senior Board Spells: {len(board_senior):,} (Female: {(board_senior.gender == 'Female').sum():,}, {fem_board_pct:.1f}%)")

    # Person-level model for holding board seats
    person_senior = spells.groupby("person_id").agg(
        is_female=("is_female", "first"),
        max_rank=("rank_score", "max"),
        total_board_seats=("is_board", "sum"),
        total_spells=("spell_id", "count"),
        first_year=("year", "min")
    ).reset_index()
    person_senior = person_senior[person_senior.max_rank >= 55]
    person_senior["has_board"] = (person_senior["total_board_seats"] > 0).astype(int)

    mod4 = smf.logit("has_board ~ is_female + max_rank + total_spells + first_year", data=person_senior).fit(disp=False)
    print("Probability of Ever Holding a Board Seat (Rank >= 55):")
    print(mod4.summary().tables[1])
    or_board = np.exp(mod4.params['is_female'])
    print(f"Female Odds Ratio for Board Seat: {or_board:.4f}, p = {mod4.pvalues['is_female']:.4e}")

    # =========================================================================
    # TEST 5: Executive Tenure Fragility ("Glass Cliff")
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 5: EXECUTIVE TENURE FRAGILITY (Rank >= 65: DG, SG, Min)")
    print("="*80)
    apex = spells[(spells.rank_score >= 65) & (spells.end_date.notna())].copy()
    apex["end_dt"] = pd.to_datetime(apex["end_date"], errors="coerce")
    apex["tenure_years"] = (apex["end_dt"] - apex["start_dt"]).dt.days / 365.25
    apex = apex[(apex.tenure_years > 0.05) & (apex.tenure_years < 20)]

    mean_tenure_m = apex[apex.gender == "Male"]["tenure_years"].mean()
    median_tenure_m = apex[apex.gender == "Male"]["tenure_years"].median()
    mean_tenure_f = apex[apex.gender == "Female"]["tenure_years"].mean()
    median_tenure_f = apex[apex.gender == "Female"]["tenure_years"].median()
    print(f"Executive Tenure - Male (years): Mean = {mean_tenure_m:.2f}, Median = {median_tenure_m:.2f} (N = {(apex.gender == 'Male').sum():,})")
    print(f"Executive Tenure - Female (years): Mean = {mean_tenure_f:.2f}, Median = {median_tenure_f:.2f} (N = {(apex.gender == 'Female').sum():,})")

    mod5 = smf.ols("tenure_years ~ is_female + rank_score + C(era) + is_sovereign", data=apex).fit()
    print(mod5.summary().tables[1])

    # =========================================================================
    # TEST 6: Sovereign & Territorial Quarantine (Coercive State Exclusion)
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 6: SOVEREIGN & TERRITORIAL QUARANTINE")
    print("="*80)
    # Territorial command positions: Gouverneur (80), Premier Délégué (50), Délégué (40)
    is_territorial = spells["position_rank"].isin(["gouverneur", "premier_delegue", "delegue"])
    tot_terr = is_territorial.sum()
    fem_terr = (is_territorial & (spells.gender == "Female")).sum()
    print(f"Territorial Command Appointments (Governors & Delegates): {tot_terr:,}")
    print(f"Female Territorial Appointments: {fem_terr:,} ({fem_terr/tot_terr*100:.2f}%)")
    print(f"Male Territorial Appointments: {tot_terr - fem_terr:,} ({(tot_terr - fem_terr)/tot_terr*100:.2f}%)")

    # Interior ministry appointments
    is_interior = spells["sector"] == "Interior"
    tot_int = is_interior.sum()
    fem_int = (is_interior & (spells.gender == "Female")).sum()
    print(f"Interior Ministry Appointments: {tot_int:,} (Female: {fem_int:,}, {fem_int/tot_int*100:.2f}%)")

if __name__ == "__main__":
    run_tests()
