"""Canonical PNAD preparation and design exports; no causal estimation is run."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd


KEYS = ["year", "quarter"]
STATES = ["study_only", "study_formal", "study_informal", "work_only", "neither"]
NUMERIC = [
    "year", "quarter", "age", "household_size", "household_income",
    "monthly_earnings", "minimum_wage", "weight", "schooling", "employed",
    "formal", "weekly_hours",
]
REQUIRED = ["observation_id", "household_id", "state", *NUMERIC]
OUTCOMES = [
    "schooling", "employed", "hours_unconditional", "monthly_earnings",
    "formal_employment", "informal_employment", *[f"activity_{s}" for s in STATES],
]


@dataclass(frozen=True)
class SampleSpec:
    age_min: int = 15
    age_max: int = 19
    eligible_cutoff: float = 0.5
    comparison_upper: float = 1.0
    donut_width: float = 0.0
    income_definition: str = "excluding_focal"

    def validate(self) -> None:
        if not (0 <= self.age_min <= self.age_max):
            raise ValueError("Age bounds must be non-negative and ordered.")
        if not (0 < self.eligible_cutoff < self.comparison_upper):
            raise ValueError("Require 0 < eligibility cutoff < comparison upper bound.")
        if not (0 <= self.donut_width < self.eligible_cutoff):
            raise ValueError("Donut width must be non-negative and below the cutoff.")
        if self.income_definition not in {"excluding_focal", "conventional"}:
            raise ValueError("Unknown income definition.")


def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype={k: "string" for k in [
        "observation_id", "household_id", "state", "activity_state",
    ]})


def require_columns(frame: pd.DataFrame, names: list[str]) -> None:
    missing = sorted(set(names) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")


def write_csv(frame: pd.DataFrame, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)


def write_json(value: dict, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def check_periods(frame: pd.DataFrame) -> None:
    require_columns(frame, KEYS)
    for field in KEYS:
        frame[field] = pd.to_numeric(frame[field], errors="raise")
        if frame[field].isna().any() or not np.isfinite(frame[field]).all():
            raise ValueError(f"{field} must be observed and finite.")
        if (frame[field] % 1 != 0).any():
            raise ValueError(f"{field} must be an integer.")
        frame[field] = frame[field].astype(int)
    if not frame["quarter"].between(1, 4).all():
        raise ValueError("Quarter must be between 1 and 4.")
    if not frame["year"].between(1900, 2200).all():
        raise ValueError("Year must be a four-digit survey year between 1900 and 2200.")


def prepare(frame: pd.DataFrame, spec: SampleSpec) -> tuple[pd.DataFrame, dict]:
    spec.validate()
    require_columns(frame, REQUIRED)
    data = frame[REQUIRED].copy()
    if data.empty:
        raise ValueError("Input contains no observations.")
    for field in ["observation_id", "household_id", "state"]:
        if data[field].isna().any() or data[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"{field} cannot be missing or blank.")
    if data["observation_id"].duplicated().any():
        raise ValueError("observation_id must identify a unique person-interview.")
    for field in NUMERIC:
        data[field] = pd.to_numeric(data[field], errors="raise")
        if np.isinf(data[field]).any():
            raise ValueError(f"{field} contains infinite values.")
    check_periods(data)
    for field in ["age", "household_size"]:
        if (data[field].dropna() % 1 != 0).any():
            raise ValueError(f"{field} must be integer-valued when observed.")
    for field in ["schooling", "employed", "formal"]:
        if not data[field].dropna().isin([0, 1]).all():
            raise ValueError(f"{field} must be 0, 1 or missing; decode survey sentinels first.")
    for field in ["household_income", "monthly_earnings", "weekly_hours"]:
        if (data[field].dropna() < 0).any():
            raise ValueError(f"{field} has negative values; resolve their meaning upstream.")
    nonworker = data["employed"].eq(0)
    if (nonworker & (data["weekly_hours"].gt(0) | data["formal"].eq(1))).any():
        raise ValueError("Non-employed observations have positive hours or formal status.")
    household = data.groupby(["household_id", *KEYS], dropna=False)
    for field in ["household_income", "household_size", "state"]:
        if household[field].nunique(dropna=True).gt(1).any():
            raise ValueError(f"{field} differs within a household-quarter.")

    denominator = data["household_size"] * data["minimum_wage"]
    valid_denominator = data["household_size"].gt(0) & data["minimum_wage"].gt(0)
    data["income_ratio_conventional"] = data["household_income"].div(
        denominator.where(valid_denominator)
    )
    residual = data["household_income"] - data["monthly_earnings"]
    data["income_ratio_excluding_focal"] = residual.where(residual.ge(0)).div(
        denominator.where(valid_denominator)
    )
    for name in ["conventional", "excluding_focal"]:
        ratio = data[f"income_ratio_{name}"]
        data[f"eligible_{name}"] = ratio.le(spec.eligible_cutoff).astype(float).where(ratio.notna())
    data["income_ratio"] = data[f"income_ratio_{spec.income_definition}"]

    checks = [
        ("age_outside_range_or_missing", data["age"].between(spec.age_min, spec.age_max)),
        ("invalid_or_missing_weight", data["weight"].gt(0)),
        ("invalid_or_missing_income_denominator", valid_denominator),
        ("missing_or_inconsistent_selected_income", data["income_ratio"].notna()),
        ("income_above_comparison_band", data["income_ratio"].le(spec.comparison_upper)),
    ]
    if spec.donut_width > 0:
        checks.append(("inside_donut", (data["income_ratio"] - spec.eligible_cutoff).abs().gt(spec.donut_width)))
    keep = pd.Series(True, index=data.index)
    exclusions = {}
    for reason, valid in checks:
        valid = valid.fillna(False)
        exclusions[reason] = int((keep & ~valid).sum())
        keep &= valid
    sample = data.loc[keep].copy()
    if sample.empty:
        raise ValueError("No observations remain under this sample specification.")
    sample["age"] = sample["age"].astype(int)
    sample["eligible_proxy"] = sample["income_ratio"].le(spec.eligible_cutoff).astype(int)
    if sample["eligible_proxy"].nunique() != 2:
        raise ValueError("Both eligible-proxy and comparison observations are required.")
    sample["quarter_id"] = sample["year"] * 4 + sample["quarter"] - 1
    sample["period"] = sample["year"].astype(str) + "Q" + sample["quarter"].astype(str)
    school, work, formal = (sample[x] for x in ["schooling", "employed", "formal"])
    sample["hours_unconditional"] = sample["weekly_hours"].where(work.eq(1))
    sample.loc[work.eq(0), "hours_unconditional"] = 0.0
    for name, code in [("formal_employment", 1), ("informal_employment", 0)]:
        sample[name] = np.nan
        sample.loc[work.eq(0), name] = 0.0
        known = work.eq(1) & formal.notna()
        sample.loc[known, name] = formal.loc[known].eq(code).astype(float)
    conditions = {
        "study_only": school.eq(1) & work.eq(0),
        "study_formal": school.eq(1) & work.eq(1) & formal.eq(1),
        "study_informal": school.eq(1) & work.eq(1) & formal.eq(0),
        "work_only": school.eq(0) & work.eq(1),
        "neither": school.eq(0) & work.eq(0),
    }
    sample["activity_state"] = pd.Series(pd.NA, index=sample.index, dtype="string")
    for name, condition in conditions.items():
        sample.loc[condition, "activity_state"] = name
    for name in STATES:
        sample[f"activity_{name}"] = sample["activity_state"].eq(name).astype("Float64")
    audit = {
        "specification": asdict(spec),
        "input_rows": len(data),
        "sample_rows": len(sample),
        "sequential_exclusions": exclusions,
        "negative_residual_household_income_rows_before_selection": int(residual.lt(0).sum()),
        "sample_counts_by_eligible_proxy": {str(k): int(v) for k, v in sample["eligible_proxy"].value_counts().items()},
        "sample_missing_outcomes": {name: int(sample[name].isna().sum()) for name in OUTCOMES},
        "sample_unknown_activity_state": int(sample["activity_state"].isna().sum()),
        "income_classifications_disagree_in_sample": int((
            sample["eligible_conventional"].notna()
            & sample["eligible_excluding_focal"].notna()
            & sample["eligible_conventional"].ne(sample["eligible_excluding_focal"])
        ).sum()),
        "interpretation": "Income-group proxy; neither verified eligibility nor programme receipt.",
    }
    return sample, audit


def describe(data: pd.DataFrame) -> pd.DataFrame:
    require_columns(data, [*KEYS, "eligible_proxy", "weight", *OUTCOMES])
    records = []
    for (year, quarter, eligible), group in data.groupby([*KEYS, "eligible_proxy"], sort=True):
        for outcome in OUTCOMES:
            observed = group[outcome].notna()
            values = group.loc[observed, outcome].astype(float)
            weights = group.loc[observed, "weight"].astype(float)
            total = float(weights.sum())
            records.append({
                "year": year, "quarter": quarter, "eligible_proxy": eligible,
                "outcome": outcome, "n_total": len(group), "n_observed": int(observed.sum()),
                "n_missing": int((~observed).sum()), "observed_weight": total,
                "weighted_mean": float(np.average(values, weights=weights)) if total > 0 else np.nan,
                "effective_n": total ** 2 / float((weights ** 2).sum()) if total > 0 else np.nan,
            })
    return pd.DataFrame.from_records(records)


def merge_calendar(data: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    calendar = calendar.copy()
    check_periods(calendar)
    require_columns(calendar, ["post"])
    if calendar.duplicated(KEYS).any() or not calendar["post"].isin([0, 1]).all():
        raise ValueError("Calendar requires unique quarters and post coded 0/1 without missing values.")
    calendar = calendar.sort_values(KEYS)
    if calendar["post"].diff().lt(0).any():
        raise ValueError("This baseline requires a single, irreversible common post transition.")
    merged = data.merge(calendar[[*KEYS, "post"]], on=KEYS, how="left", validate="many_to_one")
    if merged["post"].isna().any():
        raise ValueError("Policy calendar does not cover every analysis quarter.")
    return merged


def design(data: pd.DataFrame, calendar: pd.DataFrame, reference: str,
           outside: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    require_columns(data, ["observation_id", "state", "age", *KEYS, "eligible_proxy", "weight", *OUTCOMES])
    merged = merge_calendar(data, calendar)
    if merged["post"].nunique() != 2:
        raise ValueError("Design needs observations in both pre-policy and post-policy periods.")
    if not re.fullmatch(r"\d{4}Q[1-4]", reference):
        raise ValueError("Reference quarter must have YYYYQn format.")
    merged["period"] = merged["year"].astype(int).astype(str) + "Q" + merged["quarter"].astype(int).astype(str)
    ref_rows = merged["period"].eq(reference)
    if not ref_rows.any() or not merged.loc[ref_rows, "post"].eq(0).all():
        raise ValueError("Reference quarter must be observed and pre-policy.")
    support = merged.groupby("period")["eligible_proxy"].nunique()
    if support.lt(2).any():
        raise ValueError("Each quarter needs both groups; unsupported: " + ", ".join(support[support.lt(2)].index))
    merged["did"] = merged["eligible_proxy"] * merged["post"]
    merged["state_time"] = merged["state"].astype(str) + ":" + merged["period"]
    merged["age_time"] = merged["age"].astype(int).astype(str) + ":" + merged["period"]
    event_terms = []
    for period in sorted(merged["period"].unique()):
        if period != reference:
            name = f"eligible_q{period}"
            merged[name] = merged["eligible_proxy"] * merged["period"].eq(period).astype(int)
            event_terms.append(name)
    base = "eligible_proxy + did + C(state_time) + C(age_time)"
    manifest = {
        "reference_quarter": reference,
        "baseline_rhs": base,
        "event_study_rhs": "eligible_proxy + " + " + ".join(event_terms) + " + C(state_time) + C(age_time)",
        "event_terms": event_terms,
        "outcomes": OUTCOMES,
        "weight_column": "weight",
        "proposed_cluster_column": "state",
        "state_count": int(merged["state"].nunique()),
        "fixed_effect_keys": ["state_time", "age_time"],
        "estimation_performed": False,
        "inference_performed": False,
        "calendar_interpretation": "User-supplied common policy calendar; not individual receipt.",
    }
    if outside is not None:
        require_columns(outside, ["state", "relative_incentive"])
        if outside["state"].isna().any() or outside["state"].duplicated().any():
            raise ValueError("Outside-earnings table requires one non-missing row per state.")
        valid_values = pd.to_numeric(outside["relative_incentive"], errors="raise").dropna()
        if (valid_values <= 0).any() or not np.isfinite(valid_values).all():
            raise ValueError("Observed relative incentives must be positive and finite.")
        merged = merged.merge(outside[["state", "relative_incentive"]], on="state", how="left", validate="many_to_one")
        merged["eligible_x_relative"] = merged["eligible_proxy"] * merged["relative_incentive"]
        merged["did_x_relative"] = merged["did"] * merged["relative_incentive"]
        manifest["heterogeneity_rhs"] = base + " + eligible_x_relative + did_x_relative"
        manifest["rows_without_outside_benchmark"] = int(merged["relative_incentive"].isna().sum())
    return merged, manifest


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    ordered = pd.DataFrame({"value": values, "weight": weights}).sort_values("value")
    threshold = ordered["weight"].sum() / 2
    return float(ordered.loc[ordered["weight"].cumsum().ge(threshold), "value"].iloc[0])


def outside_earnings(data: pd.DataFrame, calendar: pd.DataFrame, deflators: pd.DataFrame,
                     years: list[int], incentive: float, price_base: str,
                     minimum_workers: int) -> pd.DataFrame:
    require_columns(data, ["state", *KEYS, "eligible_proxy", "employed", "monthly_earnings", "weight"])
    if not np.isfinite(incentive) or incentive <= 0 or minimum_workers < 1:
        raise ValueError("Incentive must be finite and positive; minimum workers must be at least one.")
    selected = merge_calendar(data, calendar)
    selected = selected.loc[selected["year"].isin(years)].copy()
    if selected.empty or set(years) - set(selected["year"].unique()):
        raise ValueError("Every requested benchmark year must appear in the sample.")
    if selected["post"].ne(0).any():
        raise ValueError("Outside-earnings years must be entirely pre-policy in the supplied calendar.")
    check_periods(deflators)
    require_columns(deflators, ["multiplier"])
    deflators["multiplier"] = pd.to_numeric(deflators["multiplier"], errors="raise")
    if deflators.duplicated(KEYS).any() or not (
        deflators["multiplier"].gt(0) & np.isfinite(deflators["multiplier"])
    ).all():
        raise ValueError("Deflators require unique quarters and positive finite multipliers.")
    selected = selected.merge(deflators[[*KEYS, "multiplier"]], on=KEYS, how="left", validate="many_to_one")
    if selected["multiplier"].isna().any():
        raise ValueError("Deflators do not cover all requested benchmark quarters.")
    selected["real_earnings"] = selected["monthly_earnings"] * selected["multiplier"]
    records = []
    for state, group in selected.groupby("state", sort=True):
        workers = group.loc[group["eligible_proxy"].eq(1) & group["employed"].eq(1)
                            & group["real_earnings"].gt(0)]
        adequate = len(workers) >= minimum_workers
        median = weighted_median(workers["real_earnings"], workers["weight"]) if adequate else np.nan
        records.append({
            "state": state, "worker_interviews": len(workers),
            "weighted_worker_interviews": float(workers["weight"].sum()),
            "median_real_monthly_earnings": median,
            "monthly_incentive": incentive,
            "relative_incentive": incentive / median if adequate else np.nan,
            "price_base": price_base, "benchmark_years": ";".join(map(str, sorted(set(years)))),
            "minimum_workers": minimum_workers,
            "status": "available" if adequate else "insufficient_workers",
        })
    return pd.DataFrame.from_records(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Build the age/income sample and outcome definitions.")
    desc = commands.add_parser("describe", help="Export survey-weighted group-quarter summaries.")
    des = commands.add_parser("design", help="Export analysis terms; does not fit a model.")
    outside = commands.add_parser("outside", help="Build pre-policy state earnings benchmarks.")
    for subparser in [prep, desc, des, outside]:
        subparser.add_argument("--input", required=True)
        subparser.add_argument("--output", required=True)
    prep.add_argument("--audit", required=True)
    prep.add_argument("--age-min", type=int, default=15)
    prep.add_argument("--age-max", type=int, default=19)
    prep.add_argument("--eligible-cutoff", type=float, default=0.5)
    prep.add_argument("--comparison-upper", type=float, default=1.0)
    prep.add_argument("--donut-width", type=float, default=0.0)
    prep.add_argument("--income-definition", choices=["excluding_focal", "conventional"], default="excluding_focal")
    for subparser in [des, outside]:
        subparser.add_argument("--calendar", required=True)
    des.add_argument("--reference-quarter", required=True)
    des.add_argument("--manifest", required=True)
    des.add_argument("--outside")
    outside.add_argument("--deflators", required=True)
    outside.add_argument("--pre-years", type=int, nargs="+", required=True)
    outside.add_argument("--monthly-incentive", type=float, required=True)
    outside.add_argument("--price-base", required=True)
    outside.add_argument("--minimum-workers", type=int, default=30)
    args = parser.parse_args()
    data = read_csv(args.input)
    if args.command == "prepare":
        spec = SampleSpec(args.age_min, args.age_max, args.eligible_cutoff,
                          args.comparison_upper, args.donut_width, args.income_definition)
        result, audit = prepare(data, spec)
        write_csv(result, args.output)
        write_json(audit, args.audit)
    elif args.command == "describe":
        write_csv(describe(data), args.output)
    elif args.command == "design":
        benchmark = read_csv(args.outside) if args.outside else None
        result, manifest = design(data, read_csv(args.calendar), args.reference_quarter, benchmark)
        write_csv(result, args.output)
        write_json(manifest, args.manifest)
    else:
        result = outside_earnings(data, read_csv(args.calendar), read_csv(args.deflators),
                                  args.pre_years, args.monthly_incentive, args.price_base,
                                  args.minimum_workers)
        write_csv(result, args.output)


if __name__ == "__main__":
    main()
