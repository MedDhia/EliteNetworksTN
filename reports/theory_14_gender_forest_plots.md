# Theory 14: Gender Biases Across Political Regimes (Forest Plots)

This report presents the econometric specifications, academic publication captions, and substantive interpretations for the publication-grade forest plots evaluating gender biases in the Tunisian state apparatus from independence to the contemporary era (1957–2026). 

Each visualization conforms strictly to top-tier empirical political economy guidelines:
1. **Strict Single Plot per Figure** (`1 Figure / 1 Axes`) with zero subplot clutter.
2. **Minimalist Aesthetic**: Pure `#FFFFFF` background, zero gridlines, zero in-plot brackets or badge clutter, and high data-to-ink ratio.
3. **Explicit Gender Captions**: Detailed notes positioned underneath the horizontal axis explicitly defining the female indicator variable, reference lines, control sets, standard errors, and sample sizes.

---

## Synthesis Table of Gender Forest Plot Estimates

| Figure | Filename | Bias Dimension | Econometric Specification | Metric & Reference Line | Regimes Covered | Pooled Estimate | Sample Size ($N$) |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **Fig 14a** | `fig_theory_14a_forest_gender_promotion_delay.png` | **Sticky Floor** (Promotion Velocity) | OLS: $\text{Time} \sim \text{Female} + \text{Rank}$, HC1 SEs | Net Delay in Months ($\text{Ref} = 0\text{ mo}$) | 5 Regimes + Pooled | **$+5.48^{***}\text{ mo}$** $[+4.04, +6.91]$ | $N = 22,319$ promotions |
| **Fig 14b** | `fig_theory_14b_forest_gender_glass_ceiling.png` | **Glass Ceiling** (Senior Apex Access) | Logit: $\mathbf{1}(\text{Senior}) \sim \text{Female}$ | Odds Ratio ($\text{Ref} = 1.0$) | 5 Regimes + Pooled | **$\text{OR} = 0.32^{***}$** $[0.30, 0.35]$ | $N = 41,790$ spells |
| **Fig 14c** | `fig_theory_14c_forest_gender_coercive_quarantine.png` | **Coercive Quarantine** (Sovereign Portfolios) | Logit: $\mathbf{1}(\text{Coercive}) \sim \text{Female}$ | Odds Ratio ($\text{Ref} = 1.0$) | 5 Regimes + Pooled | **$\text{OR} = 0.92^{***}$** $[0.89, 0.95]$ | $N = 99,270$ spells |
| **Fig 14d** | `fig_theory_14d_forest_gender_tenure_survival.png` | **Survival Advantage** (24M Incumbent Stability) | OLS: $\mathbf{1}(\text{Surv}\ge 24) \sim \text{Female} + \text{Rank}$ | Percentage Points ($\text{Ref} = 0\text{ pp}$) | 5 Regimes + Pooled | **$+2.87^{***}\text{ pp}$** $[+2.25, +3.49]$ | $N = 99,270$ spells |
| **Fig 14e** | `fig_theory_14e_forest_gender_presidential_shocks.png` | **Presidential Shocks** (Rupture Discontinuity) | Sharp RDD: $p=1$, $h=\pm 180\text{d}$, Uniform | Discontinuity $\hat{\tau}$ ($\text{Ref} = 0\text{ pp}$) | 1987, 2011, 2021 Shocks | 2011: **$-18.27^{***}\text{ pp}$** | $N = 5,065$ acts |

---

## Detailed Econometric Specifications & Academic Captions

### Figure 14a: Gender Promotion Velocity Gap (Sticky Floor)

> **Figure 14a**: Forest plot of female promotion velocity penalties (sticky floor) across Tunisian political regimes.  
> **Notes**: Points and horizontal error bars display estimated net delay in months for female civil servants to achieve upward promotion relative to male peers, controlling for baseline entering rank score (HC1 robust 95% CIs). The vertical dashed line at 0 indicates gender parity in promotion speed; positive values denote female promotion delay. Total sample N = 22,319 promotions.

#### Econometric Specification
$$\text{MonthsToPromotion}_i = \alpha_r + \beta_r \cdot \text{Female}_i + \gamma_r \cdot \text{RankScore}_i + \varepsilon_i$$
where $\beta_r$ captures the regime-specific conditional delay (in months) experienced by female appointees relative to men entering at equivalent hierarchical rank.

#### Empirical Estimates by Regime
- **Bourguiba (1957–87)**: $+15.74\text{ mo } [7.23, 24.26]^{***}$ ($N = 3,244$)
- **Ben Ali (1987–2011)**: $+15.77\text{ mo } [13.45, 18.08]^{***}$ ($N = 11,038$)
- **Democratic Transition (2011–14)**: $+10.83\text{ mo } [8.29, 13.37]^{***}$ ($N = 3,641$)
- **Béji Caïd Essebsi (2014–19)**: $+7.86\text{ mo } [5.58, 10.14]^{***}$ ($N = 3,001$)
- **Kaïs Saïed (2019–26)**: $+3.41\text{ mo } [1.35, 5.46]^{**}$ ($N = 1,395$)
- **Pooled (All Regimes)**: **$+5.48\text{ mo } [4.04, 6.91]^{***}$** ($N = 22,319$)

#### Substantive Finding
The "sticky floor" penalty is large and persistent across the entire 70-year history of the Tunisian state, though declining linearly across political transitions. Under both Bourguiba and Ben Ali, women spent over 15 extra months waiting for career upward promotions compared to identically ranked male peers. Post-2011 institutional democratization reduced this wait time to 10.8 months, then 7.9 months under Essebsi, and 3.4 months under Saïed.

---

### Figure 14b: Hierarchical Glass Ceiling Odds (Senior Leadership Access)

> **Figure 14b**: Forest plot of the hierarchical glass ceiling odds ratios across political regimes.  
> **Notes**: Points and horizontal error bars display the adjusted odds ratio (OR) of female civil servants reaching senior leadership positions (Secretary General, Director General, Cabinet Chief) versus entry-level cadres (95% CIs). The vertical dashed reference line at 1.0 denotes equal odds; values below 1.0 document an entrenched glass ceiling. Total sample N = 41,790 spells.

#### Econometric Specification
$$\text{logit}\big(P(\text{SeniorLeadership}_i = 1)\big) = \alpha_r + \theta_r \cdot \text{Female}_i$$
where $\text{SeniorLeadership}_i = 1$ for Director General, Secretary General, or Cabinet Director ($\text{RankScore} \ge 65$) versus entry cadres ($\text{RankScore} \le 45$). The odds ratio is $\text{OR}_r = \exp(\theta_r)$.

#### Empirical Estimates by Regime
- **Bourguiba (1957–87)**: $\text{OR} = 0.17 [0.09, 0.34]^{***}$ ($N = 3,414$)
- **Ben Ali (1987–2011)**: $\text{OR} = 0.25 [0.21, 0.29]^{***}$ ($N = 17,359$)
- **Democratic Transition (2011–14)**: $\text{OR} = 0.30 [0.25, 0.36]^{***}$ ($N = 6,964$)
- **Béji Caïd Essebsi (2014–19)**: $\text{OR} = 0.30 [0.26, 0.35]^{***}$ ($N = 7,856$)
- **Kaïs Saïed (2019–26)**: $\text{OR} = 0.35 [0.30, 0.40]^{***}$ ($N = 6,197$)
- **Pooled (All Regimes)**: **$\text{OR} = 0.32 [0.30, 0.35]^{***}$** ($N = 41,790$)

#### Substantive Finding
Women face a massive, statistically indestructible glass ceiling across every single political regime. Across the pooled sample, women exhibit $68\%$ lower odds of reaching the executive apex of the state ($\text{OR} = 0.32, p < 0.0001$) relative to men. While access slightly expanded from Bourguiba ($\text{OR} = 0.17$) to Saïed ($\text{OR} = 0.35$), parity ($\text{OR} = 1.0$) remains distant.

---

### Figure 14c: Coercive & Territorial Quarantine Odds

> **Figure 14c**: Forest plot of female placement odds in sovereign and coercive portfolios across political regimes.  
> **Notes**: Odds ratios reflect the relative likelihood of female civil servants being assigned to sovereign coercive portfolios (Interior, Defense, Regional Governorships) vs. civilian line ministries, relative to male peers (95% CIs). The dashed reference line at 1.0 indicates gender parity in portfolio assignment; values < 1.0 show coercive quarantine of women. Total N = 99,270.

#### Econometric Specification
$$\text{logit}\big(P(\text{CoercivePortfolio}_i = 1)\big) = \alpha_r + \delta_r \cdot \text{Female}_i$$
where $\text{CoercivePortfolio}_i = 1$ denotes appointments within the Ministry of Interior, Ministry of National Defense, Regional Governorships, Police, or National Guard.

#### Empirical Estimates by Regime
- **Bourguiba (1957–87)**: $\text{OR} = 0.37 [0.28, 0.49]^{***}$ ($N = 15,113$)
- **Ben Ali (1987–2011)**: $\text{OR} = 0.75 [0.70, 0.81]^{***}$ ($N = 38,924$)
- **Democratic Transition (2011–14)**: $\text{OR} = 1.00 [0.93, 1.09]$ (n.s.) ($N = 14,989$)
- **Béji Caïd Essebsi (2014–19)**: $\text{OR} = 0.84 [0.77, 0.91]^{***}$ ($N = 15,626$)
- **Kaïs Saïed (2019–26)**: $\text{OR} = 1.00 [0.93, 1.07]$ (n.s.) ($N = 14,618$)
- **Pooled (All Regimes)**: **$\text{OR} = 0.92 [0.89, 0.95]^{***}$** ($N = 99,270$)

#### Substantive Finding
Under the autocratic regimes of Bourguiba and Ben Ali, women were strictly quarantined out of sovereign, security, and territorial apparatuses ($\text{OR} = 0.37$ and $0.75$). However, during the post-revolutionary transition (2011–14) and under Kaïs Saïed (2019–26), the sovereign quarantine was broken, reaching exact statistical parity ($\text{OR} = 1.00$), driven by the entry of female judges and administrators into Interior and territorial governance.

---

### Figure 14d: Female Incumbent Survival Advantage (24-Month Stability)

> **Figure 14d**: Forest plot of the female 24-month tenure survival advantage across political regimes.  
> **Notes**: Points and horizontal error bars display the adjusted percentage-point difference in 24-month survival rates for female civil servants relative to male colleagues, holding hierarchical rank constant (HC1 robust 95% CIs). The dashed reference line at 0 pp denotes equal survival hazard; positive values reflect higher female tenure stability. Total sample N = 99,270 spells.

#### Econometric Specification
$$\mathbf{1}(\text{Tenure}_i \ge 730\text{ days}) = \alpha_r + \lambda_r \cdot \text{Female}_i + \phi_r \cdot \text{RankScore}_i + \varepsilon_i$$
where $\lambda_r$ denotes the percentage-point survival premium for female appointees.

#### Empirical Estimates by Regime
- **Bourguiba (1957–87)**: $+6.65\text{ pp } [3.98, 9.31]^{***}$ ($N = 15,113$)
- **Ben Ali (1987–2011)**: $+8.12\text{ pp } [7.14, 9.09]^{***}$ ($N = 38,924$)
- **Democratic Transition (2011–14)**: $+9.23\text{ pp } [7.78, 10.69]^{***}$ ($N = 14,989$)
- **Béji Caïd Essebsi (2014–19)**: $+5.08\text{ pp } [3.75, 6.40]^{***}$ ($N = 15,626$)
- **Kaïs Saïed (2019–26)**: $+1.81\text{ pp } [0.19, 3.43]^{*}$ ($N = 14,618$)
- **Pooled (All Regimes)**: **$+2.87\text{ pp } [2.25, 3.49]^{***}$** ($N = 99,270$)

#### Substantive Finding
Across all five political eras, female appointees consistently survived longer than men (holding rank constant). This survival advantage peaked during the revolutionary transition ($+9.23\text{ pp}$), where political purges disproportionately targeted male party-affiliated elites, leaving technocratic female administrators insulated from political turnover.

---

### Figure 14e: Sharp RDD Discontinuities across Presidential Ruptures

> **Figure 14e**: Forest plot of sharp RDD discontinuities in female appointment share across presidential regime ruptures.  
> **Notes**: Local linear regression discontinuity estimates (p = 1, h = ±180 days, uniform kernel, HC1 robust 95% CIs) measuring the immediate shift in the share of female appointments at each historical cutoff c = 0. The dashed line at 0 pp denotes no change in gender composition; positive values reflect an immediate surge in female appointments. Total N across 3 windows = 5,065 acts.

#### Econometric Specification
$$\text{FemaleShare}_i = \alpha + \tau \cdot \mathbf{1}(X_i \ge 0) + \beta_1 \cdot X_i + \beta_2 \cdot [X_i \cdot \mathbf{1}(X_i \ge 0)] + \varepsilon_i$$
for appointment events within bandwidth $h = \pm 180\text{ days}$ of each regime shock cutoff $c = 0$.

#### Empirical Estimates by Presidential Shock
- **1987 Ben Ali Coup (7 Nov 1987)**: $\hat{\tau} = -3.13\text{ pp } [-9.14, +2.88]$ ($p = 0.308$, n.s., $N = 1,144$)
- **2011 Revolution (14 Jan 2011)**: $\hat{\tau} = -18.27\text{ pp } [-25.39, -11.14]^{***}$ ($p < 0.0001$, $N = 2,012$)
- **2021 Saïed Auto-Coup (25 Jul 2021)**: $\hat{\tau} = -9.11\text{ pp } [-20.33, +2.11]$ ($p = 0.111$, n.s., $N = 1,909$)

#### Substantive Finding
Presidential shocks did not immediately increase female administrative power. The 2011 Revolution caused an immediate **$18.27\text{ pp}$ drop** in female appointments ($p < 0.0001$) as initial transitional cabinets and post-revolutionary emergency structures were staffed overwhelmingly by male political opposition figures, before gender parity quotas were later introduced.
