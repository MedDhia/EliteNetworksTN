# Theory 13: Single-Plot Figure Captions and Empirical Notes

This document provides the definitive academic publication captions, econometric specifications, and substantive notes for the seven standalone figures generated to evaluate regime change shocks in Tunisia (**Figure 13a** through **Figure 13g**). 

In accordance with top-tier political economy journal standards (e.g., *American Economic Review*, *Quarterly Journal of Economics*), each figure adheres to:
1. **Strict Single Plot per Figure** (`1 Figure / 1 Axes`) to maximize clarity and avoid cognitive crowding.
2. **Minimalist Aesthetic**: Zero gridlines, zero in-plot brackets or badge clutter, and a pure `#FFFFFF` background.
3. **Comprehensive External Captions**: Placed strictly below the horizontal axis, reporting the econometric model, bandwidth, kernel, standard errors, sample size, and substantive interpretation.

---

## Summary Table of Figure Captions

| Figure | Filename | Topic | Cutoff / Shock | Econometric Method | Discontinuity / DiD Penalty ($\hat{\tau}$ or $\hat{\delta}$) | Sample Size ($N$) |
|:---|:---|:---|:---|:---|:---|:---|
| **Fig 13a** | `fig_theory_13a_rdd_1987_volume.png` | Appointment Throughput | 7 Nov 1987 (Ben Ali Coup) | Sharp RDD ($p=1$, $h=\pm 180\text{d}$, Uniform) | $\hat{\tau} = +0.74$ acts/day ($p = 0.5488$, n.s.) | $N = 361$ days |
| **Fig 13b** | `fig_theory_13b_rdd_2011_volume.png` | Appointment Throughput | 14 Jan 2011 (Revolution) | Sharp RDD ($p=1$, $h=\pm 180\text{d}$, Uniform) | $\hat{\tau} = -7.59^{***}$ acts/day ($p = 0.0003$) | $N = 361$ days |
| **Fig 13c** | `fig_theory_13c_rdd_2021_volume.png` | Appointment Throughput | 25 Jul 2021 (Auto-Coup) | Sharp RDD ($p=1$, $h=\pm 180\text{d}$, Uniform) | $\hat{\tau} = -5.02^{***}$ acts/day ($p = 0.0002$) | $N = 361$ days |
| **Fig 13d** | `fig_theory_13d_rdd_1987_is_sec.png` | Security Appointee Share | 7 Nov 1987 (Ben Ali Coup) | Sharp RDD ($p=1$, $h=\pm 180\text{d}$, Uniform) | $\hat{\tau} = +34.24^{***}$ pp ($p < 0.0001$) | $N = 1,144$ acts |
| **Fig 13e** | `fig_theory_13e_rdd_2011_is_apex.png` | Apex Political Share | 14 Jan 2011 (Revolution) | Sharp RDD ($p=1$, $h=\pm 180\text{d}$, Uniform) | $\hat{\tau} = +39.56^{***}$ pp ($p < 0.0001$) | $N = 2,012$ acts |
| **Fig 13f** | `fig_theory_13f_did_survival.png` | Incumbent 24M Survival | 1987, 2011, 2021 Shocks | Hierarchical DiD (Senior vs. Ops vs. Placebos) | 1987: $-5.01^{*}$; 2011: $-7.54^{***}$; 2021: $+3.40^{***}$ | $N = 403,407$ spells |
| **Fig 13g** | `fig_theory_13g_did_demotion.png` | Weaponized Demotion Rate | 1987, 2011, 2021 Shocks | DiD LPM vs. 5-Year Pre-Shock Movers | 1987: $-1.24$ (n.s.); 2011: $-2.22^{**}$; 2021: $+9.95^{***}$ | $N = 43,944$ movers |

---

## Detailed Captions & Methodological Notes

### Figure 13a: Daily Appointment Volume around the 1987 Ben Ali Coup d'État

> **Figure 13a**: Daily appointment volume around the 1987 shock (Ben Ali Coup d'État).  
> **Notes**: Dots depict 7-day binned sample averages. Solid lines show local linear fit ($p = 1$, bandwidth $h = \pm 180$ days, uniform kernel) with 95% HC1 robust confidence intervals. Cutoff $c = 0$ corresponds to 7 November 1987. Discontinuity estimate $\hat{\tau} = +0.74$ acts/day ($\text{SE} = 1.24$, $t = 0.60$, $p = 0.5488$, not statistically significant). Daily $N = 361$.

- **Substantive Finding**: The 1987 medical coup d'état did not cause a bureaucratic administrative shutdown or freeze. The machinery of state appointments continued without aggregate quantitative interruption.
- **Specification**:
  $$\text{DailyAppointments}_t = \alpha + \beta_1 \cdot X_t + \tau \cdot \mathbf{1}(X_t \ge 0) + \beta_2 \cdot [X_t \cdot \mathbf{1}(X_t \ge 0)] + \varepsilon_t$$
  where $X_t$ is the running variable in days centered on 7 November 1987.

---

### Figure 13b: Daily Appointment Volume around the 2011 Revolution (Flight of Ben Ali)

> **Figure 13b**: Daily appointment volume around the 2011 shock (Revolution / Flight of Ben Ali).  
> **Notes**: Dots depict 7-day binned sample averages. Solid lines show local linear fit ($p = 1$, bandwidth $h = \pm 180$ days, uniform kernel) with 95% HC1 robust confidence intervals. Cutoff $c = 0$ corresponds to 14 January 2011. Discontinuity estimate $\hat{\tau} = -7.59^{***}$ acts/day ($\text{SE} = 2.12$, $t = -3.58$, $p = 0.0003$). Daily $N = 361$.

- **Substantive Finding**: The collapse and flight of the Ben Ali regime caused an immediate administrative freeze, dropping baseline throughput by over 7.5 acts per day, followed by a gradual post-revolutionary institutional rebuilding.

---

### Figure 13c: Daily Appointment Volume around the 2021 Saïed Presidential Auto-Coup

> **Figure 13c**: Daily appointment volume around the 2021 shock (Saïed Presidential Auto-Coup).  
> **Notes**: Dots depict 7-day binned sample averages. Solid lines show local linear fit ($p = 1$, bandwidth $h = \pm 180$ days, uniform kernel) with 95% HC1 robust confidence intervals. Cutoff $c = 0$ corresponds to 25 July 2021. Discontinuity estimate $\hat{\tau} = -5.02^{***}$ acts/day ($\text{SE} = 1.36$, $t = -3.70$, $p = 0.0002$). Daily $N = 361$.

- **Substantive Finding**: Invoking Article 80 froze cabinet and civil service administrative nominations, producing a discontinuous collapse of 5.02 acts per day at $c = 0$, followed by a sharp steep recovery ($\Delta \text{slope} = +0.055$, $p < 0.001$) as presidential decrees rapidly replaced parliamentary appointments.

---

### Figure 13d: Share of Military & Security Appointments around the 1987 Ben Ali Coup d'État

> **Figure 13d**: Share of military and security appointments around the 1987 shock (Ben Ali Coup d'État).  
> **Notes**: Dots depict 7-day binned shares. Solid lines show local linear fit ($p = 1$, bandwidth $h = \pm 180$ days, uniform kernel) with 95% HC1 robust confidence intervals. Cutoff $c = 0$ corresponds to 7 November 1987. Discontinuity estimate $\hat{\tau} = +34.24^{***}$ percentage points ($\text{SE} = 5.93$ pp, $t = 5.77$, $p < 0.0001$). Total sample $N = 1,144$ appointment acts.

- **Substantive Finding**: While overall volume remained stable, Ben Ali immediately restructured the state apparatus toward the coercive apparatus: security and military appointments surged discontinuously by 34.2 percentage points within days of taking power.

---

### Figure 13e: Share of Apex Political Executives (Rank $\ge$ 70) around the 2011 Revolution

> **Figure 13e**: Share of apex political executives (Rank $\ge$ 70) around the 2011 shock (Revolution / Flight of Ben Ali).  
> **Notes**: Dots depict 7-day binned shares. Solid lines show local linear fit ($p = 1$, bandwidth $h = \pm 180$ days, uniform kernel) with 95% HC1 robust confidence intervals. Cutoff $c = 0$ corresponds to 14 January 2011. Discontinuity estimate $\hat{\tau} = +39.56^{***}$ percentage points ($\text{SE} = 4.10$ pp, $t = 9.66$, $p < 0.0001$). Total sample $N = 2,012$ appointment acts.

- **Substantive Finding**: The 2011 democratic transition initiated a radical replacement of top bureaucratic and ministerial leadership: apex positions surged from 5.4% to 45.0% of all appointments (+39.6 pp discontinuity) immediately post-cutoff.

---

### Figure 13f: Difference-in-Differences Estimates of 24-Month Incumbent Civil Service Survival

> **Figure 13f**: Difference-in-Differences estimates of 24-month incumbent civil service survival.  
> **Notes**: Comparison of Senior Leadership ($\text{Rank} \ge 65$, Directors General and above) versus Operational Civil Service ($\text{Rank} \le 45$, Heads of Service and below) relative to 5-year pre-shock matched placebo cohorts ($t_0 - 1, \dots, t_0 - 5$). Solid colored lines indicate shock cohorts; dotted gray lines indicate placebo baselines; hollow diamonds indicate counterfactual parallel-trend outcomes. DiD interaction penalties: 1987 ($\hat{\delta} = -5.01^{*}$ pp, $\text{SE} = 2.40$, $p = 0.037$); 2011 ($\hat{\delta} = -7.54^{***}$ pp, $\text{SE} = 1.23$, $p < 0.0001$); 2021 ($\hat{\delta} = +3.40^{***}$ pp, $\text{SE} = 0.74$, $p < 0.0001$). Total sample $N = 403,407$ tenure spells.

- **Substantive Finding**: Both 1987 and 2011 exacted a severe purge penalty on senior bureaucrats ($-5.0$ pp and $-7.5$ pp excess hazard). In stark contrast, the 2021 auto-coup preserved incumbent senior civil servants ($+3.4$ pp survival premium) while targeting political appointees.
- **Specification**:
  $$\text{Survived24M}_{ijt} = \alpha + \beta_1 \cdot \text{ShockCohort}_{it} + \beta_2 \cdot \text{HighRank}_{ij} + \delta \cdot (\text{ShockCohort}_{it} \times \text{HighRank}_{ij}) + \varepsilon_{ijt}$$

---

### Figure 13g: Difference-in-Differences Estimates of Weaponized Downward Mobility (Demotions)

> **Figure 13g**: Difference-in-Differences estimates of weaponized downward mobility (demotions).  
> **Notes**: Linear probability model of demotion within 36 months of shock among surviving civil service movers relative to 5-year pre-shock moving cohorts. Error bars denote $\pm 1$ standard error. Excess demotion rates: 1987 ($-1.24$ pp, n.s., $\text{SE} = 1.34$, $p = 0.3959$); 2011 ($-2.22^{**}$ pp, $\text{SE} = 0.73$, $p = 0.0024$); 2021 ($+9.95^{***}$ pp, $\text{SE} = 0.90$, $p < 0.0001$). Total sample $N = 43,944$ movers.

- **Substantive Finding**: The 2021 Saïed regime introduced a qualitatively unique mechanism of bureaucratic control: rather than outright termination, surviving movers faced a $+9.95$ percentage point surge in demotions (e.g., reassignment from Director General or Secretary General to Advisor or Special Duty Officer). In 1987 and 2011, demotions were not weaponized (negative or insignificant DiD coefficients).
