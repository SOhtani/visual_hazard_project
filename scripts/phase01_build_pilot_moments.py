#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Build the Phase 01 pilot index-moment sample (v0.2 audit-provenance fix).

This script implements the sampling design in:
    docs/PHASE_01_PILOT_SAMPLING.md

Important:
- READS the existing per-frame metric CSVs.
- DOES NOT modify historical CSVs.
- DOES NOT generate still images or video clips.
- Writes only sampling/audit outputs under reports/phase01_pilot_sampling/.
- Uses metric-driven enrichment only to construct the pilot sample.
  Sampling strata are NOT human reference labels.

Default audited cohort invariants:
    raw rows      = 519,199
    eligible rows = 519,198
    cases         = 68

The script fails explicitly if the current cohort no longer matches these
invariants unless --allow-count-mismatch is provided.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_METRICS_DIR = (
    PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "reports" / "phase01_pilot_sampling"
)

DEFAULT_SEED = 20260917

EXPECTED_RAW_ROWS = 519_199
EXPECTED_ELIGIBLE_ROWS = 519_198
EXPECTED_CASES = 68

KEY_COLS = ["case_id", "sample_time_sec"]

VALIDITY_COLS = [
    "near_uniform_frame_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
    "photometric_failure_candidate_v1",
    "image_validity_problem_candidate_v1",
    "component_review_valid_candidate_v1",
]

PROVENANCE_OPTIONAL_COLS = [
    "frame_idx_1based",
    "sample_ordinal",
    "segment_id",
    "image_file",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
]

# One metric is resolved from each synonym family.
METRIC_FAMILIES = {
    "structural": [
        "structural_visibility_loss_v1",
        "focus_badness_v1",
    ],
    "veil": [
        "veil_low_contrast_score_v1",
        "veil_smoke_mean",
    ],
    "whiteout": [
        "whiteout_ratio_v1",
        "saturation_ratio",
    ],
    "specular": [
        "specular_like_ratio_v1",
        "specular_ratio",
    ],
    "low_light": [
        "low_light_or_blackout_ratio_v1",
    ],
    "obstruction_proxy": [
        "local_obstruction_ratio",
        "center_low_structure_area_v1",
        "focus_lost_center_weighted_ratio",
    ],
}

STRATUM_TARGETS = {
    "H_confirmed_technical_failure": 1,
    "I_ambiguous_validity_challenge": 1,
    "G_metric_discordant": 4,
    "F_obstruction_or_near_contact_proxy": 3,
    "E_whiteout_or_specular": 3,
    "D_low_light_or_blackout": 4,
    "C_veil_or_low_contrast": 4,
    "B_structural_visibility_loss": 5,
    "A_clear_low_degradation": 5,
}

SELECTION_PRIORITY = list(STRATUM_TARGETS.keys())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    p.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )
    p.add_argument(
        "--max-per-case",
        type=int,
        default=2,
    )
    p.add_argument(
        "--min-separation-sec",
        type=float,
        default=60.0,
    )
    p.add_argument(
        "--expected-raw-rows",
        type=int,
        default=EXPECTED_RAW_ROWS,
    )
    p.add_argument(
        "--expected-eligible-rows",
        type=int,
        default=EXPECTED_ELIGIBLE_ROWS,
    )
    p.add_argument(
        "--expected-cases",
        type=int,
        default=EXPECTED_CASES,
    )
    p.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="Continue even if audited cohort row/case counts differ.",
    )

    return p.parse_args()


def normalize_case_id(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip()


def normalize_time(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").round(6)


def flag_bool(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).ge(0.5)


def metric_status_ok(s: pd.Series) -> pd.Series:
    # Historical Phase 09 behavior:
    # retain metric_status missing OR exactly "ok".
    raw = s.copy()
    is_missing = raw.isna()
    txt = raw.astype(str).str.strip()
    return is_missing | txt.eq("ok")


def deterministic_key(
    seed: int,
    stratum: str,
    slot_name: str,
    case_id: str,
    sample_time_sec: float,
) -> int:
    payload = (
        f"{seed}|{stratum}|{slot_name}|"
        f"{case_id}|{sample_time_sec:.6f}"
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def load_metric_frames(metrics_dir: Path) -> pd.DataFrame:
    paths = sorted(metrics_dir.glob("CASE*_frame_scores.csv"))

    if not paths:
        raise FileNotFoundError(
            f"No CASE*_frame_scores.csv files found in: {metrics_dir}"
        )

    parts: list[pd.DataFrame] = []

    for path in paths:
        df = pd.read_csv(path, low_memory=False)

        missing = [c for c in ["case_id", "sample_time_sec"] if c not in df.columns]
        if missing:
            raise ValueError(
                f"{path.name}: missing required key column(s): {missing}"
            )

        if "metric_status" not in df.columns:
            raise ValueError(
                f"{path.name}: metric_status is required for Phase 01 sampling"
            )

        if "image_path" not in df.columns:
            raise ValueError(
                f"{path.name}: image_path is required for Phase 01 sampling"
            )

        df = df.copy()
        df["case_id"] = normalize_case_id(df["case_id"])
        df["sample_time_sec"] = normalize_time(df["sample_time_sec"])
        df["source_metric_csv"] = path.name
        df["source_row"] = np.arange(len(df), dtype=np.int64)

        if df["sample_time_sec"].isna().any():
            n_bad = int(df["sample_time_sec"].isna().sum())
            raise ValueError(
                f"{path.name}: {n_bad} rows have invalid sample_time_sec"
            )

        parts.append(df)

    out = pd.concat(parts, ignore_index=True, sort=False)

    dup = int(out.duplicated(KEY_COLS).sum())
    if dup:
        raise ValueError(
            f"Raw metric source has {dup} duplicate case/time keys"
        )

    return out


def resolve_metric_columns(df: pd.DataFrame) -> dict[str, str]:
    resolved: dict[str, str] = {}

    for family, candidates in METRIC_FAMILIES.items():
        chosen = next((c for c in candidates if c in df.columns), None)
        if chosen is None:
            raise ValueError(
                f"No usable metric column found for family '{family}'. "
                f"Tried: {candidates}"
            )
        resolved[family] = chosen

    return resolved


def compute_thresholds(
    eligible: pd.DataFrame,
    resolved: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    rows = []
    lookup: dict[str, dict[str, float]] = {}

    for family, col in resolved.items():
        x = pd.to_numeric(eligible[col], errors="coerce").dropna()

        if x.empty:
            raise ValueError(
                f"Resolved metric column has no nonmissing values: {col}"
            )

        stats = {
            "min": float(x.min()),
            "p50": float(x.quantile(0.50)),
            "p90": float(x.quantile(0.90)),
            "p95": float(x.quantile(0.95)),
            "p97_5": float(x.quantile(0.975)),
            "p99": float(x.quantile(0.99)),
            "p99_5": float(x.quantile(0.995)),
            "max": float(x.max()),
        }

        lookup[family] = stats

        rows.append(
            {
                "metric_family": family,
                "metric": col,
                "n_nonmissing": int(len(x)),
                **stats,
            }
        )

    return pd.DataFrame(rows), lookup


def numeric_col(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def ge_thr(
    df: pd.DataFrame,
    col: str,
    value: float,
) -> pd.Series:
    return numeric_col(df, col).ge(value)


def lt_thr(
    df: pd.DataFrame,
    col: str,
    value: float,
) -> pd.Series:
    return numeric_col(df, col).lt(value)


def le_thr(
    df: pd.DataFrame,
    col: str,
    value: float,
) -> pd.Series:
    return numeric_col(df, col).le(value)


def between_band(
    df: pd.DataFrame,
    col: str,
    lo: float,
    hi: float,
) -> pd.Series:
    x = numeric_col(df, col)
    return x.ge(lo) & x.lt(hi)


def build_candidate_membership(
    raw: pd.DataFrame,
    eligible_mask: pd.Series,
    resolved: dict[str, str],
    thr: dict[str, dict[str, float]],
) -> tuple[pd.DataFrame, dict[str, pd.Series], pd.Series]:
    eligible = raw.loc[eligible_mask].copy()
    non_ok = raw.loc[~eligible_mask].copy()

    # Base metric series.
    m = {
        family: numeric_col(eligible, col)
        for family, col in resolved.items()
    }

    # A: all major metrics <= median.
    clear_mask = pd.Series(True, index=eligible.index)
    for family, col in resolved.items():
        clear_mask &= le_thr(
            eligible,
            col,
            thr[family]["p50"],
        )

    # B/C/D/F: >= p95 primary component.
    structural_mask = ge_thr(
        eligible,
        resolved["structural"],
        thr["structural"]["p95"],
    )
    veil_mask = ge_thr(
        eligible,
        resolved["veil"],
        thr["veil"]["p95"],
    )
    low_light_mask = ge_thr(
        eligible,
        resolved["low_light"],
        thr["low_light"]["p95"],
    )
    obstruction_mask = ge_thr(
        eligible,
        resolved["obstruction_proxy"],
        thr["obstruction_proxy"]["p95"],
    )

    # E: whiteout OR specular >= p95.
    whiteout_mask = ge_thr(
        eligible,
        resolved["whiteout"],
        thr["whiteout"]["p95"],
    )
    specular_mask = ge_thr(
        eligible,
        resolved["specular"],
        thr["specular"]["p95"],
    )
    white_spec_mask = whiteout_mask | specular_mask

    # I: current metric_status-eligible image with legacy validity problem flag.
    if "image_validity_problem_candidate_v1" in eligible.columns:
        ambiguous_validity_mask = flag_bool(
            eligible["image_validity_problem_candidate_v1"]
        )
    else:
        # We deliberately fail later if I cannot be constructed.
        ambiguous_validity_mask = pd.Series(False, index=eligible.index)

    # G: discordance patterns.
    # G1: exactly one non-structural family >= p99 while structural < p95
    #     and no more than two total metric families are >= p95.
    p95_flags = pd.DataFrame(index=eligible.index)
    p99_flags = pd.DataFrame(index=eligible.index)

    for family, col in resolved.items():
        p95_flags[family] = ge_thr(
            eligible,
            col,
            thr[family]["p95"],
        )
        p99_flags[family] = ge_thr(
            eligible,
            col,
            thr[family]["p99"],
        )

    other_families = [
        f for f in resolved.keys()
        if f != "structural"
    ]

    other_p99_count = p99_flags[other_families].sum(axis=1)
    total_p95_count = p95_flags.sum(axis=1)

    g1 = (
        other_p99_count.eq(1)
        & (~p95_flags["structural"])
        & total_p95_count.le(2)
    )

    # G2: structural extreme while every other family stays below p95.
    g2 = (
        p99_flags["structural"]
        & (~p95_flags[other_families]).all(axis=1)
    )

    discordant_mask = g1 | g2

    membership: dict[str, pd.Series] = {
        "A_clear_low_degradation": clear_mask,
        "B_structural_visibility_loss": structural_mask,
        "C_veil_or_low_contrast": veil_mask,
        "D_low_light_or_blackout": low_light_mask,
        "E_whiteout_or_specular": white_spec_mask,
        "F_obstruction_or_near_contact_proxy": obstruction_mask,
        "G_metric_discordant": discordant_mask,
        "I_ambiguous_validity_challenge": ambiguous_validity_mask,
    }

    # Add explanatory discordance reason.
    discordance_reason = pd.Series("", index=eligible.index, dtype=object)

    discordance_reason.loc[g1] = (
        "one_nonstructural_metric_ge_p99;"
        "structural_below_p95;"
        "total_p95_count_le_2"
    )
    discordance_reason.loc[g2] = (
        "structural_ge_p99;"
        "all_other_metric_families_below_p95"
    )

    # Build candidate pool: all eligible rows qualifying for >=1 visibility stratum.
    any_candidate = pd.Series(False, index=eligible.index)
    for mask in membership.values():
        any_candidate |= mask

    candidate = eligible.loc[any_candidate].copy()

    eligible_strata_map = defaultdict(list)
    for stratum, mask in membership.items():
        for idx in eligible.index[mask]:
            eligible_strata_map[idx].append(stratum)

    candidate["eligible_strata"] = [
        ";".join(eligible_strata_map[idx])
        for idx in candidate.index
    ]

    candidate["discordance_reason"] = discordance_reason.loc[
        candidate.index
    ]

    # Add per-family percentile-band labels.
    for family, col in resolved.items():
        x = numeric_col(candidate, col)
        p50 = thr[family]["p50"]
        p95 = thr[family]["p95"]
        p99 = thr[family]["p99"]

        band = np.select(
            [
                x.isna(),
                x.lt(p50),
                x.lt(p95),
                x.lt(p99),
            ],
            [
                "missing",
                "lt_p50",
                "p50_to_lt_p95",
                "p95_to_lt_p99",
            ],
            default="ge_p99",
        )
        candidate[f"{family}_percentile_band"] = band

    # Append non-ok technical-failure rows as H candidates.
    technical = non_ok.copy()
    technical["eligible_strata"] = "H_confirmed_technical_failure"
    technical["discordance_reason"] = ""

    for family in resolved:
        technical[f"{family}_percentile_band"] = "not_applicable"

    candidate = pd.concat(
        [candidate, technical],
        axis=0,
        ignore_index=False,
        sort=False,
    )

    return candidate, membership, discordance_reason


def within_case_temporal_ok(
    case_id: str,
    t: float,
    selected_times: dict[str, list[float]],
    min_separation_sec: float,
) -> bool:
    prior = selected_times.get(case_id, [])
    return all(
        abs(float(t) - float(prev)) >= min_separation_sec
        for prev in prior
    )


def candidate_sort(
    df: pd.DataFrame,
    seed: int,
    stratum: str,
    slot_name: str,
) -> pd.DataFrame:
    out = df.copy()
    out["_random_key"] = [
        deterministic_key(
            seed,
            stratum,
            slot_name,
            str(case_id),
            float(t),
        )
        for case_id, t in zip(
            out["case_id"],
            out["sample_time_sec"],
        )
    ]

    return out.sort_values(
        ["_random_key", "case_id", "sample_time_sec"],
        kind="mergesort",
    )


def choose_one(
    pool: pd.DataFrame,
    *,
    seed: int,
    stratum: str,
    slot_name: str,
    selected_keys: set[tuple[str, float]],
    case_counts: Counter,
    selected_times: dict[str, list[float]],
    max_per_case: int,
    min_separation_sec: float,
    allow_temporal_override: bool,
) -> tuple[pd.Series | None, bool]:
    if pool.empty:
        return None, False

    ordered = candidate_sort(
        pool,
        seed,
        stratum,
        slot_name,
    )

    # First pass: full constraints.
    for _, row in ordered.iterrows():
        key = (str(row["case_id"]), float(row["sample_time_sec"]))
        if key in selected_keys:
            continue

        case_id = str(row["case_id"])
        t = float(row["sample_time_sec"])

        if case_counts[case_id] >= max_per_case:
            continue

        if not within_case_temporal_ok(
            case_id,
            t,
            selected_times,
            min_separation_sec,
        ):
            continue

        return row, False

    if not allow_temporal_override:
        return None, False

    # Second pass: keep case cap hard, relax only temporal separation.
    for _, row in ordered.iterrows():
        key = (str(row["case_id"]), float(row["sample_time_sec"]))
        if key in selected_keys:
            continue

        case_id = str(row["case_id"])

        if case_counts[case_id] >= max_per_case:
            continue

        return row, True

    return None, False


def selection_value_from_row(
    row: pd.Series,
    selection_metric: str,
) -> object:
    """Return an audit-friendly value for the metric/rule used for selection."""
    if selection_metric in row.index:
        value = row.get(selection_metric)
        if pd.isna(value):
            return np.nan
        return value

    if "|" in selection_metric:
        parts = [p for p in selection_metric.split("|") if p]
        values = []
        for col in parts:
            if col in row.index:
                value = row.get(col)
                if pd.isna(value):
                    values.append(f"{col}=NA")
                else:
                    values.append(f"{col}={value}")
        return ";".join(values) if values else np.nan

    # Rule-based selectors (e.g. multi_metric_low / multi_metric_discordance)
    # do not have a single scalar selection value.
    return np.nan


def record_selection(
    row: pd.Series,
    *,
    stratum: str,
    slot_name: str,
    selection_metric: str,
    percentile_band: str,
    selection_reason: str,
    temporal_override: bool,
    selected_rows: list[dict],
    selected_keys: set[tuple[str, float]],
    case_counts: Counter,
    selected_times: dict[str, list[float]],
) -> None:
    case_id = str(row["case_id"])
    t = float(row["sample_time_sec"])
    key = (case_id, t)

    selected_keys.add(key)
    case_counts[case_id] += 1
    selected_times[case_id].append(t)

    rec = row.to_dict()

    rec.update(
        {
            "selection_stratum": stratum,
            "selection_slot": slot_name,
            "selection_metric": selection_metric,
            "selection_value": selection_value_from_row(
                row,
                selection_metric,
            ),
            "selection_percentile_band": percentile_band,
            "selection_reason": selection_reason,
            "temporal_separation_override": int(
                temporal_override
            ),
            "temporal_separation_override_reason": (
                "no_candidate_satisfied_preferred_"
                "within_case_separation_but_case_cap_preserved"
                if temporal_override
                else ""
            ),
        }
    )

    rec.pop("_random_key", None)
    selected_rows.append(rec)


def make_pool(
    eligible: pd.DataFrame,
    membership: dict[str, pd.Series],
    stratum: str,
) -> pd.DataFrame:
    if stratum not in membership:
        return eligible.iloc[0:0].copy()
    return eligible.loc[membership[stratum]].copy()


def select_sample(
    raw: pd.DataFrame,
    eligible_mask: pd.Series,
    candidate_pool: pd.DataFrame,
    membership: dict[str, pd.Series],
    resolved: dict[str, str],
    thr: dict[str, dict[str, float]],
    *,
    seed: int,
    max_per_case: int,
    min_separation_sec: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = raw.loc[eligible_mask].copy()
    non_ok = raw.loc[~eligible_mask].copy()

    selected_rows: list[dict] = []
    selected_keys: set[tuple[str, float]] = set()
    case_counts: Counter = Counter()
    selected_times: dict[str, list[float]] = defaultdict(list)

    failures: list[dict] = []

    def select_slot(
        pool: pd.DataFrame,
        *,
        stratum: str,
        slot_name: str,
        selection_metric: str,
        percentile_band: str,
        selection_reason: str,
        allow_temporal_override: bool = True,
    ) -> bool:
        row, override = choose_one(
            pool,
            seed=seed,
            stratum=stratum,
            slot_name=slot_name,
            selected_keys=selected_keys,
            case_counts=case_counts,
            selected_times=selected_times,
            max_per_case=max_per_case,
            min_separation_sec=min_separation_sec,
            allow_temporal_override=allow_temporal_override,
        )

        if row is None:
            failures.append(
                {
                    "selection_stratum": stratum,
                    "selection_slot": slot_name,
                    "reason": "no_candidate_available_under_constraints",
                }
            )
            return False

        record_selection(
            row,
            stratum=stratum,
            slot_name=slot_name,
            selection_metric=selection_metric,
            percentile_band=percentile_band,
            selection_reason=selection_reason,
            temporal_override=override,
            selected_rows=selected_rows,
            selected_keys=selected_keys,
            case_counts=case_counts,
            selected_times=selected_times,
        )
        return True

    # ---------------------------------------------------------
    # H. Confirmed technical failure - 1
    # ---------------------------------------------------------
    h_pool = non_ok.copy()

    select_slot(
        h_pool,
        stratum="H_confirmed_technical_failure",
        slot_name="H1_non_ok_metric_status",
        selection_metric="metric_status",
        percentile_band="not_applicable",
        selection_reason="metric_status_nonmissing_and_not_ok",
        allow_temporal_override=True,
    )

    # ---------------------------------------------------------
    # I. Ambiguous validity challenge - 1
    # ---------------------------------------------------------
    if "image_validity_problem_candidate_v1" in eligible.columns:
        i_pool = eligible.loc[
            flag_bool(
                eligible["image_validity_problem_candidate_v1"]
            )
        ].copy()
    else:
        i_pool = eligible.iloc[0:0].copy()

    select_slot(
        i_pool,
        stratum="I_ambiguous_validity_challenge",
        slot_name="I1_status_ok_validity_problem",
        selection_metric="image_validity_problem_candidate_v1",
        percentile_band="not_applicable",
        selection_reason=(
            "metric_status_eligible_but_legacy_"
            "image_validity_problem_candidate_v1_equals_1"
        ),
    )

    # ---------------------------------------------------------
    # G. Metric-discordant - 4
    # ---------------------------------------------------------
    g_pool = make_pool(
        eligible,
        membership,
        "G_metric_discordant",
    )

    for i in range(1, 5):
        select_slot(
            g_pool,
            stratum="G_metric_discordant",
            slot_name=f"G{i}_discordant",
            selection_metric="multi_metric_discordance",
            percentile_band="discordant",
            selection_reason="predefined_metric_discordance_rule",
        )

    # ---------------------------------------------------------
    # F. Obstruction / near-contact proxy - 3
    #    1 >=p99 + 2 p95-<p99
    # ---------------------------------------------------------
    f_col = resolved["obstruction_proxy"]
    f_extreme = eligible.loc[
        ge_thr(
            eligible,
            f_col,
            thr["obstruction_proxy"]["p99"],
        )
    ].copy()
    f_mid = eligible.loc[
        between_band(
            eligible,
            f_col,
            thr["obstruction_proxy"]["p95"],
            thr["obstruction_proxy"]["p99"],
        )
    ].copy()

    select_slot(
        f_extreme,
        stratum="F_obstruction_or_near_contact_proxy",
        slot_name="F1_ge_p99",
        selection_metric=f_col,
        percentile_band="ge_p99",
        selection_reason=(
            "obstruction_proxy_ge_p99;"
            "proxy_not_validated_as_true_physical_obstruction"
        ),
    )

    for i in range(2, 4):
        select_slot(
            f_mid,
            stratum="F_obstruction_or_near_contact_proxy",
            slot_name=f"F{i}_p95_to_lt_p99",
            selection_metric=f_col,
            percentile_band="p95_to_lt_p99",
            selection_reason=(
                "obstruction_proxy_p95_to_lt_p99;"
                "proxy_not_validated_as_true_physical_obstruction"
            ),
        )

    # ---------------------------------------------------------
    # E. Whiteout / specular - 3
    # ---------------------------------------------------------
    w_col = resolved["whiteout"]
    s_col = resolved["specular"]

    e_white_extreme = eligible.loc[
        ge_thr(
            eligible,
            w_col,
            thr["whiteout"]["p99"],
        )
    ].copy()

    e_spec_extreme = eligible.loc[
        ge_thr(
            eligible,
            s_col,
            thr["specular"]["p99"],
        )
    ].copy()

    e_mid = eligible.loc[
        between_band(
            eligible,
            w_col,
            thr["whiteout"]["p95"],
            thr["whiteout"]["p99"],
        )
        |
        between_band(
            eligible,
            s_col,
            thr["specular"]["p95"],
            thr["specular"]["p99"],
        )
    ].copy()

    select_slot(
        e_white_extreme,
        stratum="E_whiteout_or_specular",
        slot_name="E1_whiteout_ge_p99",
        selection_metric=w_col,
        percentile_band="ge_p99",
        selection_reason="whiteout_candidate_ge_p99",
    )

    select_slot(
        e_spec_extreme,
        stratum="E_whiteout_or_specular",
        slot_name="E2_specular_ge_p99",
        selection_metric=s_col,
        percentile_band="ge_p99",
        selection_reason="specular_candidate_ge_p99",
    )

    select_slot(
        e_mid,
        stratum="E_whiteout_or_specular",
        slot_name="E3_p95_to_lt_p99",
        selection_metric=f"{w_col}|{s_col}",
        percentile_band="p95_to_lt_p99",
        selection_reason=(
            "whiteout_or_specular_candidate_p95_to_lt_p99"
        ),
    )

    # ---------------------------------------------------------
    # D. Low-light / blackout - 4
    #    2 >=p99 + 2 p95-<p99
    # ---------------------------------------------------------
    d_col = resolved["low_light"]
    d_extreme = eligible.loc[
        ge_thr(
            eligible,
            d_col,
            thr["low_light"]["p99"],
        )
    ].copy()
    d_mid = eligible.loc[
        between_band(
            eligible,
            d_col,
            thr["low_light"]["p95"],
            thr["low_light"]["p99"],
        )
    ].copy()

    for i in range(1, 3):
        select_slot(
            d_extreme,
            stratum="D_low_light_or_blackout",
            slot_name=f"D{i}_ge_p99",
            selection_metric=d_col,
            percentile_band="ge_p99",
            selection_reason="low_light_or_blackout_ge_p99",
        )

    for i in range(3, 5):
        select_slot(
            d_mid,
            stratum="D_low_light_or_blackout",
            slot_name=f"D{i}_p95_to_lt_p99",
            selection_metric=d_col,
            percentile_band="p95_to_lt_p99",
            selection_reason="low_light_or_blackout_p95_to_lt_p99",
        )

    # ---------------------------------------------------------
    # C. Veil / low contrast - 4
    #    2 >=p99 + 2 p95-<p99
    # ---------------------------------------------------------
    c_col = resolved["veil"]
    c_extreme = eligible.loc[
        ge_thr(
            eligible,
            c_col,
            thr["veil"]["p99"],
        )
    ].copy()
    c_mid = eligible.loc[
        between_band(
            eligible,
            c_col,
            thr["veil"]["p95"],
            thr["veil"]["p99"],
        )
    ].copy()

    for i in range(1, 3):
        select_slot(
            c_extreme,
            stratum="C_veil_or_low_contrast",
            slot_name=f"C{i}_ge_p99",
            selection_metric=c_col,
            percentile_band="ge_p99",
            selection_reason="veil_or_low_contrast_ge_p99",
        )

    for i in range(3, 5):
        select_slot(
            c_mid,
            stratum="C_veil_or_low_contrast",
            slot_name=f"C{i}_p95_to_lt_p99",
            selection_metric=c_col,
            percentile_band="p95_to_lt_p99",
            selection_reason="veil_or_low_contrast_p95_to_lt_p99",
        )

    # ---------------------------------------------------------
    # B. Structural visibility loss - 5
    #    2 >=p99 + 3 p95-<p99
    # ---------------------------------------------------------
    b_col = resolved["structural"]
    b_extreme = eligible.loc[
        ge_thr(
            eligible,
            b_col,
            thr["structural"]["p99"],
        )
    ].copy()
    b_mid = eligible.loc[
        between_band(
            eligible,
            b_col,
            thr["structural"]["p95"],
            thr["structural"]["p99"],
        )
    ].copy()

    for i in range(1, 3):
        select_slot(
            b_extreme,
            stratum="B_structural_visibility_loss",
            slot_name=f"B{i}_ge_p99",
            selection_metric=b_col,
            percentile_band="ge_p99",
            selection_reason="structural_visibility_loss_ge_p99",
        )

    for i in range(3, 6):
        select_slot(
            b_mid,
            stratum="B_structural_visibility_loss",
            slot_name=f"B{i}_p95_to_lt_p99",
            selection_metric=b_col,
            percentile_band="p95_to_lt_p99",
            selection_reason="structural_visibility_loss_p95_to_lt_p99",
        )

    # ---------------------------------------------------------
    # A. Clear / low degradation - 5
    # ---------------------------------------------------------
    a_pool = make_pool(
        eligible,
        membership,
        "A_clear_low_degradation",
    )

    for i in range(1, 6):
        select_slot(
            a_pool,
            stratum="A_clear_low_degradation",
            slot_name=f"A{i}_all_major_metrics_le_p50",
            selection_metric="multi_metric_low",
            percentile_band="all_major_metrics_le_p50",
            selection_reason=(
                "all_resolved_major_component_metrics_le_p50"
            ),
        )

    selected = pd.DataFrame(selected_rows)
    failure_df = pd.DataFrame(failures)

    if not selected.empty:
        # Recover candidate-pool audit fields that are not present in the
        # raw eligible dataframe used by the constrained selector.
        audit_cols = [
            "case_id",
            "sample_time_sec",
            "eligible_strata",
            "discordance_reason",
        ]
        audit_cols = [
            c for c in audit_cols
            if c in candidate_pool.columns
        ]

        if {
            "case_id",
            "sample_time_sec",
        }.issubset(audit_cols):
            audit_lookup = (
                candidate_pool[audit_cols]
                .drop_duplicates(KEY_COLS)
                .copy()
            )

            selected = selected.merge(
                audit_lookup,
                on=KEY_COLS,
                how="left",
                validate="one_to_one",
                suffixes=("", "_candidate_pool"),
            )

            # If a future source table already carries these names, prefer
            # the candidate-pool audit version for sampling provenance.
            for col in [
                "eligible_strata",
                "discordance_reason",
            ]:
                pool_col = f"{col}_candidate_pool"
                if pool_col in selected.columns:
                    selected[col] = selected[pool_col]
                    selected = selected.drop(columns=[pool_col])

    if not selected.empty:
        # Stable moment IDs in sampling-spec stratum order.
        order_map = {
            s: i
            for i, s in enumerate(SELECTION_PRIORITY)
        }

        selected["_stratum_order"] = selected[
            "selection_stratum"
        ].map(order_map)

        selected = selected.sort_values(
            [
                "_stratum_order",
                "selection_slot",
                "case_id",
                "sample_time_sec",
            ],
            kind="mergesort",
        ).reset_index(drop=True)

        selected["moment_id"] = [
            f"P01M{i:03d}"
            for i in range(1, len(selected) + 1)
        ]

        selected = selected.drop(
            columns=["_stratum_order"]
        )

        # Put primary identifiers and selection audit columns first.
        first = [
            "moment_id",
            "case_id",
            "sample_time_sec",
            "image_path",
            "frame_idx_1based",
            "metric_status",
            "selection_stratum",
            "selection_slot",
            "selection_metric",
            "selection_value",
            "selection_percentile_band",
            "selection_reason",
            "temporal_separation_override",
            "temporal_separation_override_reason",
            "eligible_strata",
            "discordance_reason",
            "source_metric_csv",
            "source_row",
        ]

        first = [
            c for c in first
            if c in selected.columns
        ]

        rest = [
            c for c in selected.columns
            if c not in first
        ]

        selected = selected[first + rest]

    return selected, failure_df


def build_sampling_summary(
    selected: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for stratum in SELECTION_PRIORITY:
        g = selected.loc[
            selected["selection_stratum"].eq(stratum)
        ] if not selected.empty else pd.DataFrame()

        rows.append(
            {
                "selection_stratum": stratum,
                "target_n": STRATUM_TARGETS[stratum],
                "selected_n": int(len(g)),
                "n_unique_cases": (
                    int(g["case_id"].nunique())
                    if not g.empty
                    else 0
                ),
                "n_with_temporal_override": (
                    int(
                        pd.to_numeric(
                            g["temporal_separation_override"],
                            errors="coerce",
                        )
                        .fillna(0)
                        .ge(0.5)
                        .sum()
                    )
                    if not g.empty
                    else 0
                ),
            }
        )

    return pd.DataFrame(rows)


def write_readme(
    output_dir: Path,
    *,
    raw_n: int,
    eligible_n: int,
    non_ok_n: int,
    cases_n: int,
    selected_n: int,
    unique_selected_cases: int,
    seed: int,
    max_per_case: int,
    min_separation_sec: float,
    resolved: dict[str, str],
    failures_n: int,
) -> None:
    lines = [
        "# Phase 01 pilot sampling run",
        "",
        "This directory contains sampling/audit outputs only.",
        "No still images or video clips are generated by this script.",
        "",
        "## Cohort",
        "",
        f"- Raw frame rows: {raw_n}",
        f"- Metric-status eligible rows: {eligible_n}",
        f"- Non-ok technical rows: {non_ok_n}",
        f"- Cases: {cases_n}",
        "",
        "## Selection",
        "",
        f"- Selected index moments: {selected_n}",
        f"- Unique selected cases: {unique_selected_cases}",
        f"- Random seed: {seed}",
        f"- Maximum moments per case: {max_per_case}",
        f"- Preferred within-case separation: {min_separation_sec:g} sec",
        f"- Unfilled selection slots: {failures_n}",
        "",
        "## Resolved metric columns",
        "",
    ]

    for family, col in resolved.items():
        lines.append(f"- {family}: `{col}`")

    lines += [
        "",
        "## Interpretation",
        "",
        "Sampling strata are enrichment labels only.",
        "They are not surgeon reference labels and must not be shown to reviewers.",
        "",
    ]

    (output_dir / "README.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    args = parse_args()

    metrics_dir = args.metrics_dir.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== PHASE 01 PILOT MOMENT SAMPLING ===")
    print(f"metrics dir: {metrics_dir}")
    print(f"output dir:  {output_dir}")
    print(f"seed:        {args.seed}")
    print()

    raw = load_metric_frames(metrics_dir)

    raw_n = len(raw)
    cases_n = raw["case_id"].nunique()

    eligible_mask = metric_status_ok(raw["metric_status"])
    eligible_n = int(eligible_mask.sum())
    non_ok_n = int((~eligible_mask).sum())

    print(f"raw rows:      {raw_n}")
    print(f"eligible rows: {eligible_n}")
    print(f"non-ok rows:   {non_ok_n}")
    print(f"cases:         {cases_n}")
    print()

    count_problems = []

    if raw_n != args.expected_raw_rows:
        count_problems.append(
            f"raw rows {raw_n} != expected {args.expected_raw_rows}"
        )

    if eligible_n != args.expected_eligible_rows:
        count_problems.append(
            f"eligible rows {eligible_n} != expected "
            f"{args.expected_eligible_rows}"
        )

    if cases_n != args.expected_cases:
        count_problems.append(
            f"cases {cases_n} != expected {args.expected_cases}"
        )

    if count_problems and not args.allow_count_mismatch:
        msg = "\n".join(
            ["AUDITED COHORT INVARIANT FAILURE:"]
            + [f"- {x}" for x in count_problems]
            + [
                "",
                "No sampling outputs were generated.",
                "Use --allow-count-mismatch only after reviewing the cause.",
            ]
        )
        raise SystemExit(msg)

    if count_problems:
        print("WARNING: cohort count mismatch allowed:")
        for x in count_problems:
            print(f"  - {x}")
        print()

    resolved = resolve_metric_columns(raw)

    print("Resolved metric columns:")
    for family, col in resolved.items():
        print(f"  {family:20s} -> {col}")
    print()

    eligible = raw.loc[eligible_mask].copy()

    thresholds, threshold_lookup = compute_thresholds(
        eligible,
        resolved,
    )

    candidate_pool, membership, discordance_reason = (
        build_candidate_membership(
            raw,
            eligible_mask,
            resolved,
            threshold_lookup,
        )
    )

    selected, failures = select_sample(
        raw,
        eligible_mask,
        candidate_pool,
        membership,
        resolved,
        threshold_lookup,
        seed=args.seed,
        max_per_case=args.max_per_case,
        min_separation_sec=args.min_separation_sec,
    )

    summary = build_sampling_summary(selected)

    # ---------------------------------------------------------
    # Candidate-pool output column order / subset
    # ---------------------------------------------------------
    candidate_keep = [
        "case_id",
        "sample_time_sec",
        "image_path",
        "frame_idx_1based",
        "sample_ordinal",
        "segment_id",
        "metric_status",
        "eligible_strata",
        "discordance_reason",
        "source_metric_csv",
        "source_row",
    ]

    candidate_keep += list(resolved.values())
    candidate_keep += VALIDITY_COLS
    candidate_keep += [
        f"{family}_percentile_band"
        for family in resolved
    ]

    candidate_keep = list(
        dict.fromkeys(
            c for c in candidate_keep
            if c in candidate_pool.columns
        )
    )

    candidate_out = candidate_pool[
        candidate_keep
    ].copy()

    candidate_out = candidate_out.sort_values(
        ["case_id", "sample_time_sec"],
        kind="mergesort",
    )

    # ---------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------
    thresholds.to_csv(
        output_dir / "phase01_pilot_sampling_thresholds.csv",
        index=False,
    )

    candidate_out.to_csv(
        output_dir / "phase01_pilot_candidate_pool.csv",
        index=False,
    )

    selected.to_csv(
        output_dir / "phase01_pilot_moments.csv",
        index=False,
    )

    summary.to_csv(
        output_dir / "phase01_pilot_sampling_summary.csv",
        index=False,
    )

    failures.to_csv(
        output_dir / "phase01_pilot_sampling_failures.csv",
        index=False,
    )

    write_readme(
        output_dir,
        raw_n=raw_n,
        eligible_n=eligible_n,
        non_ok_n=non_ok_n,
        cases_n=cases_n,
        selected_n=len(selected),
        unique_selected_cases=(
            selected["case_id"].nunique()
            if not selected.empty
            else 0
        ),
        seed=args.seed,
        max_per_case=args.max_per_case,
        min_separation_sec=args.min_separation_sec,
        resolved=resolved,
        failures_n=len(failures),
    )

    print("Selected stratum counts:")
    print(
        summary.to_string(
            index=False
        )
    )
    print()

    print(
        "selected moments: "
        f"{len(selected)}"
    )
    print(
        "unique selected cases: "
        f"{selected['case_id'].nunique() if not selected.empty else 0}"
    )
    print(
        "temporal overrides: "
        f"{int(pd.to_numeric(selected.get('temporal_separation_override', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()) if not selected.empty else 0}"
    )
    print(
        "unfilled slots: "
        f"{len(failures)}"
    )
    print()

    if not selected.empty:
        print("Selected moments:")
        preview_cols = [
            "moment_id",
            "case_id",
            "sample_time_sec",
            "selection_stratum",
            "selection_slot",
            "selection_metric",
            "selection_value",
            "selection_percentile_band",
            "temporal_separation_override",
        ]

        preview_cols = [
            c for c in preview_cols
            if c in selected.columns
        ]

        print(
            selected[preview_cols].to_string(
                index=False
            )
        )
        print()

    print("Outputs:")
    for name in [
        "phase01_pilot_sampling_thresholds.csv",
        "phase01_pilot_candidate_pool.csv",
        "phase01_pilot_moments.csv",
        "phase01_pilot_sampling_summary.csv",
        "phase01_pilot_sampling_failures.csv",
        "README.md",
    ]:
        print(f"  {output_dir / name}")

    if len(selected) != sum(STRATUM_TARGETS.values()) or len(failures) > 0:
        raise SystemExit(
            "\nSampling did not fill all 30 planned slots. "
            "Audit the generated outputs before changing constraints."
        )


if __name__ == "__main__":
    main()
