# Canonical data contract

All CSVs use UTF-8, comma separators and a header. Blank cells mean missing; negative survey sentinel values must be decoded before import. Monetary fields must have the same reference period and currency. Preserve a separate, versioned record of the original release, interview eligibility, variable mapping and transformations.

## Person-interview input

| Field | Meaning and constraints |
| --- | --- |
| `observation_id` | Unique non-empty person-interview identifier. A recurring person needs a different ID in each interview. |
| `household_id` | Non-empty household identifier; used with year and quarter for consistency checks. |
| `state` | Non-empty state identifier; no municipality inference is made. |
| `year`, `quarter` | Integer survey year and quarter (1–4). |
| `age` | Completed years; integer. Default analysis range is 15–19. |
| `household_size` | Positive integer denominator consistent with the supplied income aggregate. |
| `household_income` | Non-negative monthly income of that household, **including** the focal person’s supplied earnings. No automatic subtraction of benefits. |
| `monthly_earnings` | Non-negative monthly earnings of the focal adolescent. Supply zero when earnings are known to be zero. Missing values remain missing. |
| `minimum_wage` | Positive monthly minimum wage applicable to the survey period, verified upstream. |
| `weight` | Positive finite person-level survey weight appropriate to this analysis. |
| `schooling` | 1 = currently attending education under the documented definition; 0 = not attending; blank = unknown. Do not condition the input on attendance. |
| `employed` | 1/0 employment status under the documented reference-period definition; blank = unknown. |
| `formal` | 1 = formal, 0 = informal, among employed people. May be blank for non-employed people. Document the PNAD employment-category mapping. |
| `weekly_hours` | Non-negative hours under one consistent usual/actual-hours definition. Non-employed people must have zero or blank. Unknown employed hours stay missing. |

The input should contain a broad age range if age-range sensitivity analyses are planned. It may already be restricted to adolescents; it must not be restricted to current students or current workers. Household totals and sizes must come from the household roster, not from summing only the adolescent extract.

The pipeline rejects duplicate observation IDs, inconsistent within-household income/size, invalid binary coding and contradictory non-employment hours/formality. Missing required sampling variables cause observation exclusion recorded in the audit. Rows with missing outcomes can remain in the sample; the descriptive table uses outcome-specific denominators.

The preferred ratio is:

```text
income_ratio_excluding_focal =
    (household_income - monthly_earnings) / household_size / minimum_wage
```

The focal adolescent remains in the household-size denominator. Negative residual household income is treated as inconsistent and excluded from the preferred sample, not clipped to zero. Missing earnings therefore prevent preferred-income classification even when employment is observed. The conventional ratio uses total household income and can retain those observations. This distinction is recorded in the audit.

## Supplied policy calendar

One unique row per `year,quarter`, with `post` equal to 0 or 1. Every analysis period must be covered. For this baseline, `post` can switch from 0 to 1 only once and the analysis must include both periods. A calendar is an analyst-supplied design choice, not evidence of individual payment receipt. Record the supporting institutional sources alongside the private input.

## Supplied deflators

One unique row per `year,quarter`, with a positive finite `multiplier`. Real earnings equal nominal monthly earnings multiplied by this factor. All selected benchmark periods must be covered. `--price-base` documents the price unit, and `--monthly-incentive` must be in that same unit. No price index is bundled.

## Selected prepared outputs

| Field | Interpretation |
| --- | --- |
| `eligible_proxy` | 1 below or at the selected cutoff; 0 above it and within the comparison band. |
| `eligible_conventional` | Classification at the same cutoff using total household income. |
| `eligible_excluding_focal` | Classification using income net of focal earnings; missing when unavailable. |
| `income_ratio` | Income ratio actually used to select the sample. |
| `hours_unconditional` | Weekly hours for employed people; zero for known non-employed people; missing for unknown employment. |
| `formal_employment`, `informal_employment` | Population-level indicators, zero for known non-employed people. Missing formality among workers stays missing. |
| `activity_state` | `study_only`, `study_formal`, `study_informal`, `work_only`, or `neither`. Missing school/employment status remains unknown; studying workers with missing formality are also unknown. |
| `activity_*` | Five mutually exclusive indicators. All are missing when activity-state classification is unknown. |
| `quarter_id` | Numeric year-quarter index, used for ordering. |
| `state_time`, `age_time` | Categorical keys for fixed effects; these are not numeric covariates. |

Activity states distinguish formality only for students who work. `work_only` intentionally includes formal and informal workers who are not studying. Earnings are not mechanically zeroed for the non-employed, since income and labour-status reference periods must be resolved in the upstream mapping.

Prepared samples and design exports remain person-level data. Keep them in ignored `outputs/` or another private location.
