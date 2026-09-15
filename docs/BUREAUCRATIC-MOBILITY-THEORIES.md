# Bureaucratic Mobility, Political Patronage, and State Colonization in Tunisia (1957–2026)
*Empirical Tests of Political Science Theories Using 70 Years of Gazetted State Decrees (JORT)*

---

## Executive Summary

Using the longitudinal record of the *Journal Officiel de la République Tunisienne* (1957–2026) from [`MedDhia/EliteNetworksTN`](https://github.com/MedDhia/EliteNetworksTN), this research program evaluates foundational theories of bureaucratic politics, elite mobility, civil-military relations, and security apparatus autonomy.

Across **53,475 observed bureaucratic transitions**, **40,642 career entrants**, and **100,582 total appointment spells**, we test:
1. **Network Brokerage vs. Formal Bureaucracy** (Franziska Keller 2014)
2. **Behavioral Retinues vs. Legal Signatures of Patronage**
3. **The Loyalty–Competence Trade-off Across Regimes** (Egorov & Sonin 2011; Gailmard & Patty 2007)
4. **Bureaucratic Autonomy and Turf Protection** (Daniel Carpenter 2001; James Q. Wilson 1989)
5. **Ministerial Instability, Cascading Churn & Bureaucratic Entrenchment** (Terry Moe 1985; Huber & Shipan 2002)
6. **Representative Bureaucracy & The Gender Glass Ceiling** (Kingsley 1944; Mosher 1968)
7. **Technocracy & Grand Corps Hegemony** (Pierre Bourdieu 1989; Ezra Suleiman 1974)
8. **Security Apparatus Autonomy, Asymmetry & Hegemony** (Alfred Stepan 1988; Eva Bellin 2002)
9. **Civil-Military Boundaries Across Five Regimes** (1957–2026)
10. **Colonization of the Civilian State by Former Interior Employees** (1957–2026)

---

## 1. Network Brokerage & Upward Mobility (Franziska Keller Framework)

Testing Franziska Keller's structural hole / brokerage theory (*Moving Beyond Factions*, 2014):
* Officials bridging structural holes across disconnected ministerial clusters (higher betweenness centrality) experience significantly higher odds of upward promotion ($z = +6.65, p < 10^{-10}$).
* Having an appointment signed directly by an apex executive patron (President or Prime Minister) provides an odds multiplier of **+34.3%** ($OR = 1.34, p < 0.0001$).
* Conversely, holding betweenness constant, dense local clustering in a single line agency reduces upward promotion odds ($OR = 0.92$), confirming that intra-departmental lock-in impedes advancement.

```
==================================================================================================
Predictor                                  Odds Ratio    95% Conf. Int.       z-score      p-value
--------------------------------------------------------------------------------------------------
Apex Patron Signatory (President/PM)          1.343       [1.19, 1.51]         +4.87       < 0.001
Network Brokerage (Betweenness +1 SD)         1.076       [1.05, 1.10]         +6.65       < 0.001
Cross-Portfolio Boundary Spanner              1.078       [1.02, 1.14]         +2.55         0.011
Sovereign Ministry Assignment                 1.071       [1.02, 1.13]         +2.56         0.011
Enterprise Board Directorships (+1 SD)        1.031       [1.01, 1.06]         +2.55         0.011
Career Age in State Apparatus (+1 SD)         0.967       [0.94, 0.99]         -2.32         0.020
Local Colleague Degree (+1 SD)                0.921       [0.90, 0.94]         -6.88       < 0.001
Baseline Rank Score (Tournament Constriction) 0.961       [0.96, 0.96]        -75.52       < 0.001
--------------------------------------------------------------------------------------------------
N = 53,475 transitions · Pseudo R² = 0.0943 · Log-Likelihood Ratio p < 10⁻³⁰⁰
==================================================================================================
```

---

## 2. Testing Patronage: Formal Legal Signature vs. Behavioral Retinues

```
====================================================================================================
Patronage Metric                              Pre-2011 OR [95% CI]          Post-2011 OR [95% CI]
----------------------------------------------------------------------------------------------------
Formal Legal Metric (Apex Signatory)          5.12*** [4.41, 5.94]          2.94 (n.s.) [0.79, 10.98]
Behavioral Metric 1: Arrival Sweep (<120d)    3.87*** [3.46, 4.33]          5.30*** [3.45, 8.13]
Behavioral Metric 2: Mobile Retinue Follower  4.52*** [3.75, 5.46]          5.96**  [1.56, 22.79]
====================================================================================================
```
* Post-2011 legal decentralization made apex signatory status a legal artifact ($p = 0.108$).
* In contrast, sociological patronage—co-movement with ministers across portfolios (retinues) and arrival sweeps—intensified post-2011, with retinue odds ratios rising to **5.96** ($p = 0.009$).

---

## 3. Civil-Military Boundaries Across Five Regimes (1957–2026)

Forensic audit separating military armed forces officers from interior police commissioners, customs colonels, prison commandants, and civilian military justice magistrates:

```
========================================================================================================================
Presidency / Regime Period               Total Spells    Mil. Spells    Mil. % State    Defense Spells    Defense % State
------------------------------------------------------------------------------------------------------------------------
1. Bourguiba (1957–1987)                       15,532            10           0.06%               231              1.49%
2. Ben Ali (1987–2011)                         39,080            46           0.12%               352              0.90%
3. Transition / Marzouki (2011–2014)           15,008            20           0.13%               142              0.95%
4. Essebsi / Ennaceur (2014–2019)              15,635            34           0.22%               165              1.06%
5. Kais Saied (2019–2026)                      14,683            46           0.31%               316              2.15%
========================================================================================================================
```
* **Structural Military Quarantine under Bourguiba and Ben Ali**: Under Ben Ali, Defense Ministry decrees reached a historical low (**0.90%** of state activity).
* **Kais Saied's Presidential Penetration Peak**: Military officer appointments surged to **7.7/year**, with **30.4%** placed directly in the Carthage Presidency, and functional deployment concentrated in Health (13.0%) and Social Affairs (15.2%).
* **The 70-Year Territorial Cordon Sanitaire**: Across all five regimes, **0.0% of regional governors were active military officers**.

---

## 4. Colonization of the State by Former Interior Employees (1957–2026)

Tracking $N = 11,255$ outbound civilian appointments held by **3,449 unique former Interior personnel**:

```
========================================================================================================================
Presidency / Regime Period               Total Civilian Spells    Interior Outbound Spells    Colonization %    Unique Persons
------------------------------------------------------------------------------------------------------------------------
1. Bourguiba (1957–1987)                         12,217                       748                 6.12%               369
2. Ben Ali (1987–2011)                           34,013                     4,220                12.41%             1,503
3. Transition / Marzouki (2011–2014)             12,674                     1,783                14.07%             1,077
4. Essebsi / Ennaceur (2014–2019)                14,277                     2,366                16.57%             1,456
5. Kais Saied (2019–2026)                        12,263                     2,138                17.43%             1,283
========================================================================================================================
All Regimes (1957–2026)                          85,444                    11,255                13.17%             3,449
========================================================================================================================
```

### Power Levers Captured
* **Central Directors General ($N = 3,470$)**: 31–36% of all outbound interior personnel ran line directorates in civilian ministries.
* **Political Apex & Cabinets ($N = 916$)**: 7–13% served as Ministers, Chefs de cabinet, and Chargés de mission.
* **Administrative Gatekeepers ($N = 756$)**: SGs and DAFs peaked at **10.4%** under Essebsi, controlling personnel and budget allocations.
* **State Enterprise Boards & CEOs ($N = 824$)**: 8–9% served on public enterprise boards.
* **The Governor-to-Center Trampoline**: Under Ben Ali, **145 former regional governors held 564 senior central state positions** (13.4% of all interior outbound spells).

---

## 5. Vertical Mobility of Women in the State Apparatus (1957–2026)

Tracking $N = 100,582$ career spells across **45,634 individual officials** using legal gazette honorifics (`Madame`/`Mademoiselle` vs. `Monsieur`/`M.`) cross-referenced with an empirical first-name Bayesian classifier (98.1% clean coverage).

### The Glass Ceiling Gradient Across Regimes
```
========================================================================================================================
Administrative Rank Tier       Bourguiba (1957–87)  Ben Ali (1987–11)  Transition (2011–14)  Essebsi (2014–19)  Saied (2019–26)
------------------------------------------------------------------------------------------------------------------------
Chef de service (Rank 35)                    3.5%             18.4%                 30.0%             38.5%            40.6%
Sous-directeur (Rank 45)                     4.4%             21.7%                 31.4%             37.3%            43.0%
Directeur (Rank 55)                          3.6%             13.6%                 22.5%             26.4%            29.9%
Directeur Général (Rank 65)                  1.9%              8.0%                 15.4%             19.4%            26.5%
SG & Cabinet (Rank 70–74)                    2.1%              3.7%                 15.0%             15.8%            14.8%
Apex: Gov/Ministers (Rank 80–90)             1.4%              3.8%                  0.0%              9.3%            13.2%
========================================================================================================================
Total Appointments Under Regime              3.5%             16.3%                 26.5%             33.7%            37.0%
========================================================================================================================
```

### Empirical Findings: The "Scissor Effect" and Career Tournament Penalties
1. **The Modern Divergence (Saied Era: 43.0% Entry vs. 13.2% Apex)**:
   - While female representation reaches historical highs at entry and middle management (43.0% of Sous-directeurs), the glass ceiling steepens sharply at Director General (26.5%), Cabinet (14.8%), and Apex leadership (13.2%)—a **–29.8 percentage point plunge** from entry to apex.
2. **Career Tournament Promotion Penalties (Rank $\le 45$ Entrants)**:
   - For officials entering at administrative baseline ranks (Chef de service/Sous-directeur), tracking cumulative promotion over 20 career years reveals that **men enjoy more than double the promotion probability to Director General**:
     - Cumulative promotion to Director ($\ge 55$): **18.2% (Men) vs. 13.6% (Women)** (gap of –4.6%).
     - Cumulative promotion to Director General ($\ge 65$): **8.1% (Men) vs. 3.9% (Women)** (**2.07× advantage for men**, $p < 10^{-16}$).
   - In multivariate logistic regression controlling for entry rank score and entry cohort year:
     - Promotion to Director ($\ge 55$): $OR = 0.865, p < 0.001$
     - Promotion to Director General ($\ge 65$): $OR = 0.651, p < 10^{-15}$
     - Promotion to Political Apex ($\ge 70$): $OR = 0.476, p < 10^{-26}$ (Women face a **52.4% penalty** in reaching political cabinets/governorships).
3. **Sectoral Glass Ceilings at Senior Ranks (Rank $\ge 55$, Post-2011)**:
   - Women's representation at Director and DG levels remains heavily stratified by ministry:
     - **Higher Female Inclusion**: Ministry of Women & Family (**31.4%**), Higher Education (**26.3%**), Equipment & Works (**24.5%**), Finance & Economy (**24.2%**), Social Affairs (**24.1%**).
     - **Sovereign & Technical Fortresses**: Health (**20.1%**), Defense (**19.9%**), Prime Ministry (**19.4%**), Education (**17.7%**), Justice (**17.7%**), Interior (**17.2%**), Transport (**15.4%**), Agriculture (**14.0%**).

---

---

## 6. Empirical Tests of Institutional Gender Bias (1957–2026)

Testing six formal political science and sociological hypotheses of gender bias across $N = 100,582$ career spells and $N = 56,716$ observed career transitions:

```
========================================================================================================================
Empirical Hypothesis / Dimension                   Metric / Test                           Female OR / Diff      p-value
------------------------------------------------------------------------------------------------------------------------
1. "Sticky Floor" Wait-Time Penalty                 Mean Time in Rank to Promotion          +12.1 months delay    < 10⁻⁴⁸
   • Chef de service → Sous-directeur (35 → 45)     Mean Wait Time Difference               +1.9 months delay       0.091
   • Sous-directeur → Directeur (45 → 55)           Mean Wait Time Difference               +6.4 months delay     < 0.001
   • Directeur → Directeur Général (55 → 65)        Mean Wait Time Difference               +8.9 months delay       0.060
2. Ministerial Personal Retinue Exclusion           Multivariate Logit on Retinue Spells    OR = 0.539 [0.45, 0.65] 1.2 × 10⁻¹¹
3. Ministerial Arrival Sweep Bypassing (<120d)      Multivariate Logit on Turnover Sweeps   OR = 0.862 [0.79, 0.94] 4.6 × 10⁻⁴
4. Departmental Silo Trap (Network Clustering)      Betweenness × Colleague Degree Model    OR = 0.919 [0.87, 0.97]     0.002
5. Career Tournament Apex Funnel                    Logit on Lifetime DG Attainment         OR = 0.651 [0.59, 0.72] 7.2 × 10⁻¹⁶
   • Political Executive Cabinets / Governors       Logit on Lifetime Apex (Rank ≥ 70)      OR = 0.476 [0.41, 0.55] 1.0 × 10⁻²⁷
6. Territorial Command Quarantine                   Regional Governors & Delegates Share    OR = 0.052 [0.02, 0.12] < 10⁻³⁰
========================================================================================================================
```

### Substantive Findings:
1. **The "Sticky Floor" Velocity Penalty**: While female officials who stay in the system eventually receive lateral reappointments, their promotion clock is severely retarded (+12.1 months overall; +6.4 months from Sous-directeur to Director; +8.9 months from Director to DG).
2. **Exclusion from Informal Patronage Retinues**: Women face a **46.1% discount** ($OR = 0.539$) in being recruited into ministers' mobile personal entourages, cutting them off from the highest-velocity advancement tracks in the state.
3. **The Local Silo Trap**: While high local degree inside a single department hurts mobility for both genders, women suffer **more than double the clustering penalty** ($\beta = -0.0843, p = 0.002$), remaining locked in departmental dead-ends without boundary-spanning mobility.
4. **Territorial Quarantine**: Across the entire 70-year history of the Tunisian republic, regional governorships and delegacies remained a **98.55% male monopoly** (only 6 women appointed out of 413 recorded territorial executives).
5. **Refuting the "Glass Cliff" via Super-Survivor Selection**: Women who successfully breach the glass ceiling to reach Director General or Cabinet do not suffer premature removal; instead, their mean tenure is **+0.49 years longer** ($p = 0.001$), reflecting a heavy filter where only indispensable technocratic super-specialists survive to the top.

---

## 7. Causal Identification & Robustness Verification: Matching Techniques and High-Dimensional Fixed Effects (1957–2026)

To test whether the documented gender biases are causal or driven by unobserved selection (such as sorting into slower-promoting ministries, cohort entry clustering in modern decades, or differential starting rank), we implemented a multi-method causal inference framework:
1. **Coarsened Exact Matching (CEM)**: Matching female officials to male peers on identical strata of starting rank, 5-year cohort window, and line ministry portfolio.
2. **Propensity Score Matching (PSM)**: 1:1 nearest-neighbor caliper matching (caliper $\le 0.2$ SD logit) with covariate balance diagnostics (Love plot).
3. **Multi-Way & High-Dimensional Fixed Effects**: Within-Ministry-Cohort estimators ($\mu_{\text{ministry} \times \text{cohort}} + \delta_{\text{rank\_step}}$) absorbing all unobserved ministry expansion rates, budget shocks, and temporal dynamics.

```
========================================================================================================================
Econometric Specification / Estimator             Metric / Outcome                        Female Estimate [95% CI]  p-value
------------------------------------------------------------------------------------------------------------------------
Promotion Velocity ("Sticky Floor" Delay)
• Raw Unadjusted Difference                       Two-Sample t-test                       +5.50 mo [4.06, 6.94]     6.9 × 10⁻¹⁴
• Pooled OLS (Rank + Year Controls)               Covariate-adjusted OLS                  +12.94 mo [11.47, 14.41]  1.2 × 10⁻⁶⁶
• Multi-Way Fixed Effects                         Step FE + Ministry FE + Cohort FE       +9.78 mo [8.35, 11.21]    1.0 × 10⁻⁴⁰
• High-Dimensional Ministry × Cohort FE           Within-Ministry-Cohort Estimator        +9.71 mo [8.27, 11.14]    7.1 × 10⁻⁴⁰
• Coarsened Exact Matching (CEM)                  Weighted Matched ATT (915 Strata)       +8.94 mo [7.52, 10.35]    7.1 × 10⁻³⁵
• Propensity Score Matching (PSM)                 1:1 Caliper Matched ATT (4,611 Pairs)   +5.31 mo [3.67, 6.95]     2.5 × 10⁻¹⁰
------------------------------------------------------------------------------------------------------------------------
Step-Specific Monotonic Escalation (Within-Ministry-Cohort FE)
• Chef de service → Sous-directeur (35 → 45)      N = 4,709 promotions                    +6.65 mo [4.47, 8.83]     2.2 × 10⁻⁹
• Sous-directeur → Directeur (45 → 55)            N = 2,161 promotions                    +9.89 mo [6.66, 13.12]    2.2 × 10⁻⁹
• Directeur → Directeur Général (55 → 65)         N = 521 promotions                      +12.71 mo [3.77, 21.65]   0.0055
------------------------------------------------------------------------------------------------------------------------
Career Tournament Progression (Administrative Entrants Rank ≤ 45, N = 37,156)
• Director (≥ 55): Raw Gap = -5.93 pp            Within-Ministry-Cohort FE / CEM ATT     -1.62 pp / -2.20 pp       < 0.001
• Director General (≥ 65): Raw Gap = -5.39 pp     Within-Ministry-Cohort FE / CEM ATT     -2.35 pp / -2.33 pp       < 10⁻¹⁰
• Apex Cabinet (≥ 70): Raw Gap = -5.15 pp         Within-Ministry-Cohort FE / CEM ATT     -2.85 pp / -2.81 pp       < 10⁻²⁰
------------------------------------------------------------------------------------------------------------------------
Patronage & Executive Tenure Robustness
• Ministerial Retinue Recruitment (LPM FE)        Within-Portfolio & Cohort FE            -0.537 pp (t = -6.63)     3.3 × 10⁻¹¹
• Senior Executive Tenure Duration (Rank ≥ 65)    Within-Ministry & Rank FE               +0.419 yrs (+5.0 mo)      0.013
========================================================================================================================
```

### Core Causal Inferences:
1. **The Sticky Floor Is Invariant to Sorting & Cohort Composition**: The wait-time delay for women (+8.9 to +9.8 months under CEM and High-Dim FE) is entirely immune to ministerial sorting and cohort entry differences. Even when comparing a woman and a man in the *exact same ministry, promoted in the exact same 5-year period across the exact same rank step*, women wait nearly 10 months longer.
2. **Strict Monotonic Escalation**: The promotion velocity penalty widens monotonically up the ladder: +6.7 months at the entry tier, +9.9 months at the middle director tier, and +12.7 months (over a year) at the apex Director General tier.
3. **PSM Covariate Balance**: Propensity score matching on 4,611 female-male pairs completely eliminated baseline imbalances in entry cohort and portfolio assignments, reducing standardized mean differences (SMD) from $> 0.66$ down to $< 0.02$.
4. **Permanent Tournament Apex Deficit**: In both within-ministry-cohort LPM and CEM exact matching, women face statistically overwhelming lifetime discounts in reaching Director General ($-2.33\text{ pp}, p < 10^{-13}$) and Cabinet/Minister ($-2.81\text{ pp}, p < 10^{-26}$).

---

## 8. Figures & Scripts Index

### Python Pipeline Scripts (`scripts/`)
1. `mobility_model.py`: Multivariate logit model & machine learning feature attribution (Keller framework).
2. `behavioral_patronage_test.py`: Retinues vs. legal signatures of patronage test suite.
3. `bureaucratic_politics_theories.py`: Theories 1–3 (Parachuting, Autonomy/Turf, Ministerial Instability).
4. `representative_and_corps_theories.py`: Theories 4–5 (Gender Glass Ceiling & Grand Corps Hegemony).
5. `security_apparatus_autonomy.py`: Theory 6 (Security Sector Autonomy, Intra-Security Hegemony & Civilian Penalty).
6. `military_appointments_presidencies.py`: Theory 7 (Civil-Military Boundaries Across Five Regimes).
7. `interior_colonization_state.py`: Theory 8 (Longitudinal Colonization of Civilian State by Interior Personnel).
8. `generate_interior_sankey.py`: High-resolution Bézier Sankey visualizations and interactive Plotly dashboard.
9. `gender_vertical_mobility.py`: Theory 9 (Vertical Mobility of Women, Tournament Penalties & Sectoral Ceilings).
10. `test_gender_biases.py`: Theory 10 (Formal Tests of Gender Bias: Sticky Floors, Retinues, Silo Traps & Quarantines).
11. `test_matching_and_fe_publication.py`: Theory 11 (Causal Verification: Coarsened Exact Matching, PSM, and High-Dimensional Fixed Effects).

### Publication Figures (`figures/`)
* `fig_mobility_01_odds_ratios.png` & `.pdf`: Multivariate Logit Model of Upward Mobility.
* `fig_mobility_02_feature_importance.png` & `.pdf`: Machine Learning Feature Importance (Gini attribution).
* `fig_mobility_03_marginal_effects.png` & `.pdf`: Marginal Effects of Brokerage × Apex Patronage.
* `fig_mobility_04_historical_regimes.png` & `.pdf`: 70-Year Trajectory of State Mobility Regimes.
* `fig_mobility_05_behavioral_patronage.png` & `.pdf`: Behavioral Retinue Movement vs. Legal Signatures.
* `fig_theory_01_loyalty_competence.png` & `.pdf`: Parachuting Rates and Executive Decapitations Across Crises.
* `fig_theory_02_bureaucratic_autonomy.png` & `.pdf`: Internal Sourcing Gradient, Cross-Domain Hegemony, and Outsider Penalty.
* `fig_theory_03_ministerial_instability.png` & `.pdf`: Ministerial Volatility, Cascading Churn, and Entrenchment.
* `fig_theory_04_gender_glass_ceiling.png` & `.pdf`: Passive Representation Expansion vs. Hierarchical Glass Ceiling.
* `fig_theory_05_grand_corps_hegemony.png` & `.pdf`: ENA Elite Mandarin Hegemony vs. Technical Infrastructure Feudalism.
* `fig_theory_06_security_apparatus_autonomy.png` & `.pdf`: Security Apparatus Autonomy, Hegemony, and Civilian Penalty.
* `fig_theory_07_military_presidencies.png` & `.pdf`: Civil-Military Boundaries Across Five Regimes (1957–2026).
* `fig_theory_08_interior_colonization.png` & `.pdf`: Colonization of the Civilian State by Former Interior Employees.
* `fig_theory_08_interior_sankey.png` & `.pdf`: Multi-Stage Sankey Diagrams of Interior Infiltration Pipeline.
* `fig_theory_08_interior_sankey_interactive.html`: Interactive 4-View Plotly Sankey Dashboard.
* `fig_theory_09_gender_vertical_mobility.png` & `.pdf`: Vertical Mobility of Women, Scissor Effect & Tournament Curves.
* `fig_theory_09_gender_vertical_mobility_interactive.html`: Interactive Plotly Dashboard of Gender Mobility Across Regimes.
* `fig_theory_10_gender_biases.png` & `.pdf`: Empirical Tests of Institutional Gender Bias (Sticky Floors, Retinues, Silo Traps & Quarantines).
* `fig_theory_10_gender_biases_interactive.html`: Interactive Plotly Forest Plot and Sticky Floor Dashboard.
* `fig_theory_11_matching_fixed_effects.png` & `.pdf`: Causal Identification of Gender Biases (Matching & High-Dimensional Fixed Effects).
* `fig_theory_11_matching_fixed_effects_interactive.html`: Interactive Plotly Dashboard of Matching & Fixed Effects Models.

