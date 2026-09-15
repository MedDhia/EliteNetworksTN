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

## 6. Figures & Scripts Index

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
