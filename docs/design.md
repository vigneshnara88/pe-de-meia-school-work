# Design and interpretation

## Sample and estimand

The starting specification compares adolescents aged 15–19 with per-capita household income at or below 0.5 minimum wages to adolescents above that threshold and at or below 1.0. The upper band is an analysis choice. Income excludes the focal adolescent’s earnings in the preferred labour specification to reduce the mechanical link between working and income classification. This does not remove all policy-induced income changes, measurement error or household selection.

School attendance is an outcome. Conditioning the analysis sample on current attendance would remove part of the intended margin and is not done here. No field identifies CadÚnico registration or benefit receipt. The intended coefficient is therefore a predicted-eligibility reduced form, not a treatment-on-the-treated estimate and not necessarily a fixed proportional attenuation of it.

## Baseline specification

```text
Y_i,s,a,t = beta * eligible_i * post_t + gamma * eligible_i
            + state_by_quarter_s,t + age_by_quarter_a,t + X_i' delta + error
```

`design` produces `eligible_proxy`, `did`, `state_time`, `age_time` and survey weights. It exports fixed-effect keys rather than expanding a potentially enormous dense dummy matrix. The manifest records intended formulas; a downstream estimator must absorb the fixed effects or encode them as categorical factors, handle redundant columns, and document any added controls. Control selection is not automated.

The supplied calendar defines a **common** post indicator. It must be justified for the analysis sample. The programme’s potentially different rollout dates across eligible groups cannot be resolved by silently assigning one national date. Cohort-specific designs require separate institutional verification and implementation.

## Event study

The exporter creates `eligible_qYYYYQn` for every observed quarter except the explicitly selected reference quarter. The model includes `eligible_proxy`, the quarter interactions and the same two sets of fixed effects. These are calendar-time differences relative to the reference period, not an estimator for staggered treatment timing.

The reference must be observed and pre-policy. Each observed quarter must contain both income groups. This support check is necessary but does not establish parallel trends. Plotting and joint testing of pre-policy coefficients require an actual fitted model and appropriate inference.

## Activity margins

The five activity states connect the schooling result to possible mechanisms. Their weighted shares use one common complete-activity denominator and sum to one within each group-quarter. Individual schooling, work, hours and formality outcomes can have different denominators because missingness differs. Changes in these shares describe marginal distributions; they are not individual transition estimates. A transition analysis would require validated longitudinal person linkage.

## Outside earnings

For an explicitly selected set of pre-policy years, the code calculates the survey-weighted median of positive monthly earnings among employed eligible-proxy adolescents within each state. Earnings are converted using a supplied deflator. States below a configurable worker count retain diagnostics but receive no relative-incentive value.

```text
relative_incentive_s = monthly_incentive / median_real_monthly_earnings_s
```

The design adds `eligible_x_relative` and `did_x_relative` when a benchmark file is supplied. State-by-quarter effects absorb state-level relative incentives and their common post interactions. The eligible main effect is retained. Observations without a valid benchmark keep missing interaction terms; a downstream heterogeneity fit must state its complete-case sample and compare it with the baseline.

This implementation covers the monthly-earnings comparison. Hourly-wage and deferred-annual-payment variants are not implemented. Pooling pre-period person-interviews gives a weighted distribution of interviews, not distinct workers. The estimate is conditional on positive observed earnings, and state variation can reflect worker selection as well as opportunity costs.

## Before estimating effects

1. Verify PNAD quarterly variable availability, interview coverage, survey weights and the household-income definition.
2. Verify policy rules, rollout and the supplied minimum-wage/deflator series; record sources and retrieval dates.
3. Inspect exclusions, missing outcomes, within-quarter support, income distributions and group balance.
4. Assess sensitivity to ages, income definitions, comparison-band widths and donut exclusions.
5. Fit and assess the event study before interpreting a baseline coefficient.
6. Implement inference appropriate to state clustering and the survey design. The proposal calls for a wild cluster bootstrap because state clusters are few; this repository does not implement that procedure.

Censo Escolar, payment files, RAIS and Novo CAGED could triangulate outcomes and implementation. No administrative linkage, coverage estimator or completed empirical result is included here.
