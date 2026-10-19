# Pé-de-Meia: schooling, work and outside earnings

Research design and data preparation for studying how Brazil’s Pé-de-Meia programme changes the schooling–work tradeoff among adolescents. The project follows the October 2026 proposal *Paying Students to Stay: Schooling, Work and the Hidden Margins of Brazil’s Pé de Meia*.

The central question is whether increased schooling comes from leaving work, reducing hours, combining school and work, changing employment formality, or returning to school from neither activity. The implementation turns these channels into a common sample, outcome definitions, weighted descriptive tables and difference-in-differences design terms.

## Motivation: what changes when staying in school pays?

A payment intended to support continued schooling can change several decisions at once. An adolescent may stop working, reduce hours, keep a job while attending school, or return to school after being outside both education and employment. Looking only at school attendance would miss these differences, even though they matter for household resources and the opportunity cost of studying.

This proposal therefore treats schooling and work as a joint allocation of time. Its question is not only whether attendance rises, but **which schooling–work combinations become more or less common, and whether the response varies with the earnings available outside school**. An incentive of the same monetary value could represent a larger share of forgone earnings in one labour market than another. That motivates the comparison between the payment and pre-policy youth earnings.

## Design in plain language

The proposed baseline compares changes over time for lower-income adolescents classified as likely eligible with changes for adolescents in a nearby, higher-income comparison band. Difference-in-differences asks whether the gap between these groups changes after the relevant programme date. State-by-quarter and age-by-quarter effects are intended to account for local shocks and age-specific changes shared by the income groups. Calendar-quarter interactions prepare an event study so a later analysis can examine how those gaps evolve before and after the policy.

Two sample choices follow directly from the research question. First, school attendance is an outcome, so the sample includes adolescents regardless of whether they currently attend school. Restricting it to enrolled students would remove the return-to-school margin. Second, the preferred income measure excludes the focal adolescent's earnings: otherwise, working more could itself move someone across the income classification used to compare labour outcomes.

The survey income measure is a proxy for eligibility, not a record of registration or payment. A fitted design would consequently target differences associated with predicted eligibility rather than the effect of actually receiving a payment. The code currently prepares that design and its descriptive inputs; it does not estimate a completed programme effect or identify individual transitions between activity states.

## What the code does

- Builds an age-and-income sample without selecting on current school attendance.
- Defines predicted eligibility using household income excluding the focal adolescent’s earnings; retains a conventional-income classification for sensitivity analysis.
- Constructs employment, hours, earnings, formal/informal employment and five mutually exclusive activity states.
- Produces quarter-specific weighted summaries with outcome-specific missingness and effective sample sizes.
- Creates baseline DiD and calendar-quarter event-study terms, with state-by-quarter and age-by-quarter fixed-effect keys.
- Measures the monthly incentive relative to weighted median pre-policy youth earnings, then creates the corresponding heterogeneity terms.

This repository implements the preparation and design stages of the research proposal. Empirical estimation requires harmonised PNAD data and verified programme timing.

## Data contract

Supply a CSV containing one row per person-interview, harmonised from the relevant PNAD Contínua release. The code deliberately requires a documented mapping from the release-specific dictionary to the [canonical fields](docs/data_dictionary.md). It does not guess raw PNAD variable names or assume schooling items exist in every quarterly interview.

Actual receipt and CadÚnico registration are not inferred. `eligible_proxy` means membership in a survey-income group, not verified programme eligibility. Programme dates and minimum wages must be supplied from verified sources. Do not commit person-level extracts or administrative payment records.

## Usage

Python 3.10 or later is required. Run commands from the repository root.

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt

python -m src.pipeline prepare \
  --input data/private/pnad_canonical.csv \
  --output outputs/sample.csv \
  --audit outputs/sample_audit.json

python -m src.pipeline describe \
  --input outputs/sample.csv \
  --output outputs/descriptive_outcomes.csv

python -m src.pipeline design \
  --input outputs/sample.csv \
  --calendar data/private/verified_policy_calendar.csv \
  --reference-quarter YOUR_VERIFIED_REFERENCE_QUARTER \
  --output outputs/design_terms.csv \
  --manifest outputs/design_manifest.json
```

The reference quarter must use `YYYYQn` format and be a pre-policy quarter in your supplied calendar. A single common policy calendar is required for this baseline. Separate launch cohorts or the later expansion require separately justified analysis samples and calendars; this script is not a staggered-adoption estimator.

The proposal’s starting sample is ages 15–19, with an eligible-proxy cutoff of 0.5 minimum wages per capita and a comparison band above 0.5 through 1.0. These are configurable, including the income definition:

```bash
python -m src.pipeline prepare \
  --input data/private/pnad_canonical.csv \
  --comparison-upper 0.75 --income-definition conventional \
  --donut-width 0.025 \
  --output outputs/sensitivity_sample.csv \
  --audit outputs/sensitivity_audit.json
```

`--donut-width` excludes observations within that distance of the eligibility threshold, measured in minimum wages per capita. A value of zero applies no exclusion. The default income definition is `excluding_focal`.

For outside-earnings heterogeneity, supply a deflator table and an incentive amount expressed in the same price base:

```bash
python -m src.pipeline outside \
  --input outputs/sample.csv \
  --calendar data/private/verified_policy_calendar.csv \
  --deflators data/private/earnings_deflators.csv \
  --pre-years 2022 2023 --monthly-incentive 200 \
  --price-base "2024 BRL" --minimum-workers 30 \
  --output outputs/state_outside_earnings.csv

python -m src.pipeline design \
  --input outputs/sample.csv \
  --calendar data/private/verified_policy_calendar.csv \
  --reference-quarter YOUR_VERIFIED_REFERENCE_QUARTER \
  --outside outputs/state_outside_earnings.csv \
  --output outputs/design_with_outside_earnings.csv \
  --manifest outputs/heterogeneity_manifest.json
```

The amount and price base above illustrate the proposal’s monthly-incentive comparison. Confirm their suitability for the particular periods you analyse. The outside-earnings measure covers employed adolescents with positive earnings in the eligible-proxy group; it is a selected-worker benchmark.

## Repository layout

```text
src/pipeline.py                 CLI, sample construction, audit and design terms
docs/data_dictionary.md         Canonical input and output definitions
docs/design.md                  Estimands, formulas and interpretation limits
templates/                     Header-only input schemas
requirements.txt               Python dependencies
```

The [design note](docs/design.md) describes what remains between these outputs and a defensible causal estimate: verification of rollout and variable availability, balance and pre-trend analysis, model fitting, and appropriate inference. Survey-weighted means here are descriptive; their effective sample sizes are not survey-design standard errors. Wild cluster bootstrap inference and linkage to Censo Escolar, payment data, RAIS or Novo CAGED are proposed extensions, not implemented features.
