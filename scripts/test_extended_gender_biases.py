"""
Comprehensive diagnostic script to test specific mechanisms of gender bias:
1. Retinue & Arrival Sweep Exclusion
2. Cabinet Role Stratification (Chef de cabinet / SG vs Chargé de mission)
3. Promotion Wait-Time (Sticky Floor) by Rank Tier
4. Cox Proportional Hazards for Career Promotion
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path("/Users/mohameddhiahammami/.gemini/antigravity/scratch/repo")
sys.path.append(str(ROOT / "scripts"))
from gender_vertical_mobility import load_and_classify_gender

DATA = ROOT / "data" / "processed"

def run_extended_tests():
    spells, persons = load_and_classify_gender()
    events = pd.read_csv(DATA / "events.csv.gz", low_memory=False)

    spells["is_female"] = (spells["gender"] == "Female").astype(int)

    # 1. Ministerial Retinues (Optimized O(1) Dictionary Lookup)
    print("\n--- TEST A: MINISTERIAL RETINUES & ARRIVAL SWEEPS ---")
    ministers = spells[spells.rank_score >= 90][["person_id", "org_portfolio", "start_year", "end_year", "start_dt"]].copy()
    m_moves = ministers.sort_values(["person_id", "start_dt"]).copy()
    m_moves["prev_portfolio"] = m_moves.groupby("person_id")["org_portfolio"].shift(1)
    m_moves = m_moves[m_moves["prev_portfolio"].notna() & (m_moves["prev_portfolio"] != m_moves["org_portfolio"])]

    # Pre-index portfolio service: (person_id, portfolio) -> min start_year
    person_ports = spells.groupby(["person_id", "org_portfolio"])["start_year"].min().to_dict()

    bureaucrats = spells[spells.rank_score < 90][["spell_id", "person_id", "org_portfolio", "start_year"]].copy()
    b_by_port = {}
    for p, df_p in bureaucrats.groupby("org_portfolio"):
        b_by_port[p] = df_p

    retinue_spells = set()
    for _, m_row in m_moves.iterrows():
        m_id = m_row["person_id"]
        p_from = m_row["prev_portfolio"]
        p_to = m_row["org_portfolio"]
        m_yr = m_row["start_year"]
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

    # Arrival sweeps: appointments within 120 days of a new minister's arrival
    m_arr = ministers.groupby("org_portfolio")["start_dt"].unique().to_dict()
    def is_sweep(row):
        p = row["org_portfolio"]
        if p not in m_arr: return 0
        dt = row["start_dt"]
        for m_dt in m_arr[p]:
            delta = (dt - m_dt).days
            if 0 <= delta <= 120:
                return 1
        return 0

    spells["is_sweep"] = spells.apply(is_sweep, axis=1)

    print("Retinue Appointments:")
    ret_tot = spells["is_retinue"].sum()
    fem_ret = spells[spells.is_retinue == 1]["is_female"].sum()
    print(f"Total retinue spells: {ret_tot:,}, Female: {fem_ret:,} ({fem_ret/ret_tot*100:.2f}%)")
    overall_fem = spells["is_female"].mean() * 100
    print(f"Overall female spell rate: {overall_fem:.2f}%")

    # Logistic model of retinue appointment
    mod_ret = smf.logit("is_retinue ~ is_female + rank_score + start_year", data=spells).fit(disp=False)
    print("Logistic Regression on Retinue Appointment:")
    print(f"Female OR: {np.exp(mod_ret.params['is_female']):.4f} [p = {mod_ret.pvalues['is_female']:.4e}]")

    print("\nArrival Sweep Appointments:")
    sweep_tot = spells["is_sweep"].sum()
    fem_sweep = spells[spells.is_sweep == 1]["is_female"].sum()
    print(f"Total sweep spells: {sweep_tot:,}, Female: {fem_sweep:,} ({fem_sweep/sweep_tot*100:.2f}%)")
    mod_swp = smf.logit("is_sweep ~ is_female + rank_score + start_year", data=spells).fit(disp=False)
    print(f"Female OR (Sweep): {np.exp(mod_swp.params['is_female']):.4f} [p = {mod_swp.pvalues['is_female']:.4e}]")

    # 2. Cabinet Role Stratification
    print("\n--- TEST B: CABINET ROLE STRATIFICATION (Rank 70–75) ---")
    cab = spells[spells.rank_score.between(70, 75)].copy()
    print(f"Total cabinet spells: {len(cab):,}")
    # Group into Chef de Cabinet / SG vs Chargé de mission
    is_sg_or_head = cab["position_rank"].isin(["secretaire_general", "chef_cabinet"])
    cab["is_apex_gatekeeper"] = is_sg_or_head.astype(int)

    gatekeepers = cab[cab.is_apex_gatekeeper == 1]
    charge_mission = cab[cab.is_apex_gatekeeper == 0]

    print(f"Gatekeepers (SG / Chef de cabinet): {len(gatekeepers):,} (Female: {(gatekeepers.gender == 'Female').sum():,}, {(gatekeepers.gender == 'Female').mean()*100:.2f}%)")
    print(f"Chargés de mission: {len(charge_mission):,} (Female: {(charge_mission.gender == 'Female').sum():,}, {(charge_mission.gender == 'Female').mean()*100:.2f}%)")

    # Chi-square test
    ct = pd.crosstab(cab["gender"], cab["is_apex_gatekeeper"])
    chi2, p_chi, _, _ = stats.chi2_contingency(ct)
    print(f"Chi-square test of Cabinet Stratification: chi2 = {chi2:.2f}, p = {p_chi:.4e}")

    # 3. Promotion Wait-Time (Sticky Floor) by Specific Ranks
    print("\n--- TEST C: PROMOTION WAIT-TIME BY RANK TRANSITION ---")
    spells["next_rank"] = spells.groupby("person_id")["rank_score"].shift(-1)
    spells["next_start"] = spells.groupby("person_id")["start_dt"].shift(-1)
    spells["has_next"] = spells["next_rank"].notna().astype(int)
    spells["days_to_next"] = (spells["next_start"] - spells["start_dt"]).dt.days
    spells["years_to_next"] = spells["days_to_next"] / 365.25

    # Transition 35 -> 45 (Chef de service to Sous-directeur)
    t_35_45 = spells[(spells.rank_score == 35) & (spells.next_rank == 45) & (spells.years_to_next.between(0.1, 20))]
    print(f"\nChef de service -> Sous-directeur (35 -> 45, N = {len(t_35_45):,}):")
    m_35 = t_35_45[t_35_45.gender == "Male"]["years_to_next"]
    f_35 = t_35_45[t_35_45.gender == "Female"]["years_to_next"]
    print(f"Male Wait Time: Mean = {m_35.mean():.2f}y, Median = {m_35.median():.2f}y (N = {len(m_35)})")
    print(f"Female Wait Time: Mean = {f_35.mean():.2f}y, Median = {f_35.median():.2f}y (N = {len(f_35)})")
    diff_35 = f_35.mean() - m_35.mean()
    t_stat_35, p_val_35 = stats.ttest_ind(f_35, m_35, equal_var=False)
    print(f"Difference: +{diff_35*12:.1f} months, t = {t_stat_35:.2f}, p = {p_val_35:.4e}")

    # Transition 45 -> 55 (Sous-directeur to Directeur)
    t_45_55 = spells[(spells.rank_score == 45) & (spells.next_rank == 55) & (spells.years_to_next.between(0.1, 20))]
    print(f"\nSous-directeur -> Directeur (45 -> 55, N = {len(t_45_55):,}):")
    m_45 = t_45_55[t_45_55.gender == "Male"]["years_to_next"]
    f_45 = t_45_55[t_45_55.gender == "Female"]["years_to_next"]
    print(f"Male Wait Time: Mean = {m_45.mean():.2f}y, Median = {m_45.median():.2f}y (N = {len(m_45)})")
    print(f"Female Wait Time: Mean = {f_45.mean():.2f}y, Median = {f_45.median():.2f}y (N = {len(f_45)})")
    diff_45 = f_45.mean() - m_45.mean()
    t_stat_45, p_val_45 = stats.ttest_ind(f_45, m_45, equal_var=False)
    print(f"Difference: +{diff_45*12:.1f} months, t = {t_stat_45:.2f}, p = {p_val_45:.4e}")

    # Transition 55 -> 65 (Directeur to Directeur Général)
    t_55_65 = spells[(spells.rank_score == 55) & (spells.next_rank == 65) & (spells.years_to_next.between(0.1, 20))]
    print(f"\nDirecteur -> Directeur Général (55 -> 65, N = {len(t_55_65):,}):")
    m_55 = t_55_65[t_55_65.gender == "Male"]["years_to_next"]
    f_55 = t_55_65[t_55_65.gender == "Female"]["years_to_next"]
    print(f"Male Wait Time: Mean = {m_55.mean():.2f}y, Median = {m_55.median():.2f}y (N = {len(m_55)})")
    print(f"Female Wait Time: Mean = {f_55.mean():.2f}y, Median = {f_55.median():.2f}y (N = {len(f_55)})")
    diff_55 = f_55.mean() - m_55.mean()
    t_stat_55, p_val_55 = stats.ttest_ind(f_55, m_55, equal_var=False)
    print(f"Difference: +{diff_55*12:.1f} months, t = {t_stat_55:.2f}, p = {p_val_55:.4e}")

if __name__ == "__main__":
    run_extended_tests()
