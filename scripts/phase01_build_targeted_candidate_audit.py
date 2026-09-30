#!/usr/bin/env python
"""
phase01_build_targeted_candidate_audit.py

Build a construct-specific candidate-pool audit for the next Phase-01 targeted
calibration study. This script DOES NOT select the final review set.

Design principles
-----------------
1. Historical per-frame CSVs are read-only.
2. Known exact aliases are canonicalized; aliases are never treated as
   independent predictors.
3. Technical invalidity is separated from poor clinical visibility.
4. Existing 30-frame pilot moments are excluded from candidate counts/pools,
   but remain available as temporal neighbours.
5. Temporal features are retrieval heuristics only. They are not ground truth.
6. Smoke, lens contamination, near-contact, and blood flags are explicitly
   named as proxies/preselectors where semantic ground truth is not available.

Outputs
-------
phase01_targeted_candidate_thresholds.csv
phase01_targeted_candidate_summary.csv
phase01_targeted_candidate_by_case.csv
phase01_targeted_candidate_overlap.csv
phase01_targeted_candidate_pool.csv
phase01_targeted_metric_inventory.csv
phase01_targeted_file_inventory.csv
phase01_targeted_pilot_exclusion_audit.csv
README.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


ID_CANDIDATES = {
    "case_id": ["case_id", "case", "case_name", "caseid"],
    "sample_time_sec": [
        "sample_time_sec",
        "time_sec",
        "timestamp_sec",
        "elapsed_sec",
        "second",
        "sec",
    ],
    "frame_index": ["frame_index", "frame_idx", "frame_number", "frame_no"],
    "image_path": [
        "image_path",
        "frame_path",
        "frame_file",
        "image_file",
        "filepath",
        "file_path",
    ],
    "metric_status": ["metric_status", "status", "frame_status"],
}

METRIC_CANDIDATES = {
    "focus_badness_v1": [
        "focus_badness_v1",
        "structural_visibility_loss_v1",
        "composite_badness_v4",
    ],
    "veil_low_contrast_score_v1": [
        "veil_low_contrast_score_v1",
        "veil_smoke_mean",
    ],
    "specular_ratio": [
        "specular_ratio",
        "specular_like_ratio_v1",
    ],
    "saturation_ratio": [
        "saturation_ratio",
        "whiteout_ratio_v1",
    ],
    "low_light_metric": [
        "low_light_ratio_v1",
        "low_light_ratio",
        "low_light_score_v1",
        "low_light_score",
        "blackout_ratio_v1",
        "blackout_ratio",
        "low_light_mean",
    ],
    "center_low_structure_area_v1": [
        "center_low_structure_area_v1",
        "local_obstruction_ratio",
    ],
    "local_obstruction_max_component_ratio": [
        "local_obstruction_max_component_ratio",
        "max_low_structure_component_ratio_v1",
        "max_low_structure_component_ratio",
    ],
    "roi_edge_density_v1": [
        "roi_edge_density_v1",
        "roi_edge_density",
        "edge_density_v1",
        "edge_density",
    ],
    "roi_gray_entropy_bits_v1": [
        "roi_gray_entropy_bits_v1",
        "roi_gray_entropy_bits",
        "gray_entropy_bits_v1",
        "gray_entropy_bits",
    ],
}

BLOOD_EXACT_CANDIDATES = [
    "blood_like_ratio_v1",
    "blood_like_redness_v1",
    "blood_ratio_v1",
    "blood_ratio",
    "blood_like_mean",
    "red_blood_ratio",
    "redness_ratio_v1",
    "redness_score_v1",
    "blood_redness_score_v1",
]

TECHNICAL_INVALID_PATTERNS = [
    "all_zero",
    "all-zero",
    "corrupt",
    "decode_error",
    "decoder_error",
    "read_error",
    "missing_image",
    "missing frame",
    "test_pattern",
    "no_signal",
    "no-signal",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Audit targeted candidate pools for Phase-01 calibration."
    )
    p.add_argument("--metrics-dir", required=True, type=Path)
    p.add_argument("--pilot-moments", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument(
        "--temporal-window",
        type=int,
        default=3,
        help="Number of preceding/following sampled frames for temporal medians (default: 3).",
    )
    p.add_argument(
        "--min-neighbor",
        type=int,
        default=2,
        help="Minimum neighbour frames required for temporal median (default: 2).",
    )
    p.add_argument(
        "--high-quantile",
        type=float,
        default=0.95,
        help="High candidate threshold quantile (default: 0.95).",
    )
    p.add_argument(
        "--extreme-quantile",
        type=float,
        default=0.99,
        help="Extreme candidate threshold quantile (default: 0.99).",
    )
    p.add_argument(
        "--low-quantile",
        type=float,
        default=0.05,
        help="Low threshold for edge/entropy candidate logic (default: 0.05).",
    )
    p.add_argument(
        "--expected-rows",
        type=int,
        default=519198,
        help="Expected total per-frame rows before pilot exclusion; warning only (default: 519198).",
    )
    p.add_argument(
        "--blood-metric",
        type=str,
        default=None,
        help="Optional exact per-frame column to use as blood/redness PRESELECTOR.",
    )
    return p.parse_args()


def ensure_valid_args(args: argparse.Namespace) -> None:
    if not args.metrics_dir.exists():
        raise FileNotFoundError(f"metrics-dir not found: {args.metrics_dir}")
    if not args.pilot_moments.exists():
        raise FileNotFoundError(f"pilot-moments not found: {args.pilot_moments}")
    if args.temporal_window < 1:
        raise ValueError("--temporal-window must be >= 1")
    if args.min_neighbor < 1 or args.min_neighbor > args.temporal_window:
        raise ValueError("--min-neighbor must be between 1 and --temporal-window")
    if not (0 < args.low_quantile < 0.5):
        raise ValueError("--low-quantile must be between 0 and 0.5")
    if not (0.5 < args.high_quantile < args.extreme_quantile < 1):
        raise ValueError(
            "Require 0.5 < --high-quantile < --extreme-quantile < 1"
        )


def first_present(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    colset = set(columns)
    for c in candidates:
        if c in colset:
            return c
    return None


def infer_case_from_filename(path: Path) -> Optional[str]:
    m = re.search(r"(CASE\d+)", path.stem, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def choose_blood_column(columns: Sequence[str], override: Optional[str]) -> Optional[str]:
    if override:
        return override if override in set(columns) else None

    colset = set(columns)
    for c in BLOOD_EXACT_CANDIDATES:
        if c in colset:
            return c

    blocked = {"blood_loss", "estimated_blood_loss", "ebl"}
    candidates = []
    for c in columns:
        lc = c.lower()
        if lc in blocked:
            continue
        if ("blood" in lc or "redness" in lc) and any(
            token in lc
            for token in ["ratio", "score", "mean", "pixel", "area", "fraction"]
        ):
            candidates.append(c)

    if len(candidates) == 1:
        return candidates[0]
    return None


def normalise_case_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper()


def safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def is_technical_invalid(status: pd.Series) -> pd.Series:
    x = status.fillna("").astype(str).str.lower()
    out = pd.Series(False, index=status.index)
    for pat in TECHNICAL_INVALID_PATTERNS:
        out |= x.str.contains(re.escape(pat), regex=True)
    return out


def neighbour_medians(
    values: pd.Series, window: int, min_neighbor: int
) -> Tuple[pd.Series, pd.Series]:
    prev = values.shift(1).rolling(window, min_periods=min_neighbor).median()
    rev = values.iloc[::-1]
    nxt = rev.shift(1).rolling(window, min_periods=min_neighbor).median().iloc[::-1]
    nxt = nxt.reindex(values.index)
    return prev, nxt


def quantile(series: pd.Series, value: float) -> float:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return np.nan
    return float(x.quantile(value))


def bool_count(s: pd.Series) -> int:
    return int(s.fillna(False).astype(bool).sum())


def load_per_frame_data(
    metrics_dir: Path, blood_override: Optional[str]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    csvs = sorted(metrics_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {metrics_dir}")

    frames: List[pd.DataFrame] = []
    file_inventory: List[dict] = []
    metric_inventory_rows: List[dict] = []

    for path in csvs:
        try:
            header = pd.read_csv(path, nrows=0)
            cols = list(header.columns)
        except Exception as e:
            file_inventory.append(
                {
                    "file": str(path),
                    "included": False,
                    "reason": f"header_read_error: {type(e).__name__}: {e}",
                    "rows": np.nan,
                    "case_inferred": infer_case_from_filename(path),
                }
            )
            continue

        id_map = {
            key: first_present(cols, candidates)
            for key, candidates in ID_CANDIDATES.items()
        }
        inferred_case = infer_case_from_filename(path)

        if id_map["sample_time_sec"] is None or (
            id_map["case_id"] is None and inferred_case is None
        ):
            file_inventory.append(
                {
                    "file": str(path),
                    "included": False,
                    "reason": "not_per_frame_case_file",
                    "rows": np.nan,
                    "case_inferred": inferred_case,
                }
            )
            continue

        metric_map = {
            canonical: first_present(cols, candidates)
            for canonical, candidates in METRIC_CANDIDATES.items()
        }
        metric_map["blood_preselector_metric"] = choose_blood_column(
            cols, blood_override
        )

        selected = {
            c
            for c in list(id_map.values()) + list(metric_map.values())
            if c is not None
        }

        try:
            df = pd.read_csv(path, usecols=sorted(selected))
        except Exception as e:
            file_inventory.append(
                {
                    "file": str(path),
                    "included": False,
                    "reason": f"data_read_error: {type(e).__name__}: {e}",
                    "rows": np.nan,
                    "case_inferred": inferred_case,
                }
            )
            continue

        out = pd.DataFrame(index=df.index)

        if id_map["case_id"] is not None:
            out["case_id"] = normalise_case_series(df[id_map["case_id"]])
        else:
            out["case_id"] = inferred_case

        out["sample_time_sec"] = safe_numeric(df[id_map["sample_time_sec"]])

        if id_map["frame_index"] is not None:
            out["frame_index"] = safe_numeric(df[id_map["frame_index"]])
        else:
            out["frame_index"] = np.nan

        if id_map["image_path"] is not None:
            out["image_path"] = df[id_map["image_path"]].astype(str)
        else:
            out["image_path"] = ""

        if id_map["metric_status"] is not None:
            out["metric_status"] = df[id_map["metric_status"]].astype(str)
        else:
            out["metric_status"] = ""

        for canonical, source_col in metric_map.items():
            if source_col is None:
                out[canonical] = np.nan
            else:
                out[canonical] = safe_numeric(df[source_col])

            metric_inventory_rows.append(
                {
                    "file": str(path),
                    "case_inferred": inferred_case,
                    "canonical_metric": canonical,
                    "source_column": source_col if source_col is not None else "",
                    "available": source_col is not None,
                }
            )

        out["_source_file"] = str(path)
        frames.append(out)

        file_inventory.append(
            {
                "file": str(path),
                "included": True,
                "reason": "included",
                "rows": len(out),
                "case_inferred": inferred_case,
            }
        )

    if not frames:
        raise RuntimeError("No per-frame case CSVs could be loaded.")

    data = pd.concat(frames, ignore_index=True, sort=False)
    file_inv = pd.DataFrame(file_inventory)
    metric_inv_raw = pd.DataFrame(metric_inventory_rows)

    if metric_inv_raw.empty:
        metric_inv = pd.DataFrame(
            columns=[
                "canonical_metric",
                "files_available",
                "files_total",
                "source_columns_observed",
            ]
        )
    else:
        total_included = int(file_inv["included"].fillna(False).sum())
        rows = []
        for metric, g in metric_inv_raw.groupby("canonical_metric", sort=True):
            sources = sorted({x for x in g["source_column"].astype(str) if x.strip()})
            rows.append(
                {
                    "canonical_metric": metric,
                    "files_available": int(g["available"].sum()),
                    "files_total": total_included,
                    "source_columns_observed": ";".join(sources),
                }
            )
        metric_inv = pd.DataFrame(rows)

    return data, file_inv, metric_inv


def load_pilot_keys(path: Path) -> pd.DataFrame:
    pilot = pd.read_csv(path)
    case_col = first_present(pilot.columns, ID_CANDIDATES["case_id"])
    time_col = first_present(pilot.columns, ID_CANDIDATES["sample_time_sec"])

    if case_col is None or time_col is None:
        raise ValueError(
            "pilot-moments must contain case and time columns. "
            f"Found columns: {list(pilot.columns)}"
        )

    out = pd.DataFrame(
        {
            "case_id": normalise_case_series(pilot[case_col]),
            "sample_time_sec": safe_numeric(pilot[time_col]),
        }
    ).dropna()

    out["_pilot_key"] = (
        out["case_id"]
        + "|"
        + out["sample_time_sec"].round(3).map(lambda x: f"{x:.3f}")
    )
    return out.drop_duplicates("_pilot_key")


def add_temporal_features(
    data: pd.DataFrame, window: int, min_neighbor: int
) -> pd.DataFrame:
    data = data.sort_values(["case_id", "sample_time_sec"], kind="mergesort").copy()

    temporal_metrics = [
        "veil_low_contrast_score_v1",
        "focus_badness_v1",
        "center_low_structure_area_v1",
    ]

    for metric in temporal_metrics:
        data[f"{metric}__prev_median"] = np.nan
        data[f"{metric}__next_median"] = np.nan

    for _, g in data.groupby("case_id", sort=False):
        g = g.sort_values("sample_time_sec")
        for metric in temporal_metrics:
            s = pd.to_numeric(g[metric], errors="coerce")
            prev, nxt = neighbour_medians(s, window, min_neighbor)
            data.loc[g.index, f"{metric}__prev_median"] = prev
            data.loc[g.index, f"{metric}__next_median"] = nxt

    for metric in temporal_metrics:
        prev = f"{metric}__prev_median"
        nxt = f"{metric}__next_median"
        data[f"{metric}__delta_prev"] = data[metric] - data[prev]
        data[f"{metric}__delta_next"] = data[metric] - data[nxt]
        data[f"{metric}__abruptness"] = data[
            [f"{metric}__delta_prev", f"{metric}__delta_next"]
        ].max(axis=1, skipna=True)

    return data


def build_threshold_table(
    data: pd.DataFrame,
    eligible: pd.Series,
    low_q: float,
    high_q: float,
    extreme_q: float,
) -> pd.DataFrame:
    specs = [
        ("focus_badness_v1", "high"),
        ("veil_low_contrast_score_v1", "high"),
        ("specular_ratio", "high"),
        ("saturation_ratio", "high"),
        ("low_light_metric", "high"),
        ("center_low_structure_area_v1", "high"),
        ("local_obstruction_max_component_ratio", "high"),
        ("roi_edge_density_v1", "low"),
        ("roi_gray_entropy_bits_v1", "low"),
        ("blood_preselector_metric", "high"),
        ("veil_low_contrast_score_v1__delta_prev", "high"),
        ("veil_low_contrast_score_v1__abruptness", "high"),
        ("center_low_structure_area_v1__abruptness", "high"),
    ]

    rows = []
    for metric, direction in specs:
        s = pd.to_numeric(data.loc[eligible, metric], errors="coerce").dropna()
        rows.append(
            {
                "metric": metric,
                "direction": direction,
                "n_valid": len(s),
                "q01": quantile(s, 0.01),
                "q05": quantile(s, low_q),
                "q50": quantile(s, 0.50),
                "q95": quantile(s, high_q),
                "q99": quantile(s, extreme_q),
            }
        )
    return pd.DataFrame(rows)


def threshold_lookup(thresholds: pd.DataFrame) -> Dict[str, dict]:
    return {r["metric"]: r.to_dict() for _, r in thresholds.iterrows()}


def ge(data: pd.DataFrame, col: str, value: float) -> pd.Series:
    if col not in data.columns or pd.isna(value):
        return pd.Series(False, index=data.index)
    return pd.to_numeric(data[col], errors="coerce").ge(value).fillna(False)


def le(data: pd.DataFrame, col: str, value: float) -> pd.Series:
    if col not in data.columns or pd.isna(value):
        return pd.Series(False, index=data.index)
    return pd.to_numeric(data[col], errors="coerce").le(value).fillna(False)


def add_candidate_flags(
    data: pd.DataFrame,
    eligible: pd.Series,
    thresholds: pd.DataFrame,
) -> Tuple[pd.DataFrame, List[str]]:
    t = threshold_lookup(thresholds)

    def tv(metric: str, key: str) -> float:
        return t.get(metric, {}).get(key, np.nan)

    data["cand_blur_high"] = eligible & ge(
        data, "focus_badness_v1", tv("focus_badness_v1", "q95")
    )
    data["cand_blur_extreme"] = eligible & ge(
        data, "focus_badness_v1", tv("focus_badness_v1", "q99")
    )

    veil_high = ge(
        data,
        "veil_low_contrast_score_v1",
        tv("veil_low_contrast_score_v1", "q95"),
    )
    veil_extreme = ge(
        data,
        "veil_low_contrast_score_v1",
        tv("veil_low_contrast_score_v1", "q99"),
    )
    veil_abrupt = ge(
        data,
        "veil_low_contrast_score_v1__abruptness",
        tv("veil_low_contrast_score_v1__abruptness", "q95"),
    )
    data["cand_smoke_temporal_proxy"] = eligible & veil_high & veil_abrupt
    data["cand_smoke_extreme_temporal_proxy"] = eligible & veil_extreme & veil_abrupt

    focus_high = ge(data, "focus_badness_v1", tv("focus_badness_v1", "q95"))
    veil_prev_high = ge(
        data,
        "veil_low_contrast_score_v1__prev_median",
        tv("veil_low_contrast_score_v1", "q95"),
    )
    veil_next_high = ge(
        data,
        "veil_low_contrast_score_v1__next_median",
        tv("veil_low_contrast_score_v1", "q95"),
    )
    focus_prev_high = ge(
        data,
        "focus_badness_v1__prev_median",
        tv("focus_badness_v1", "q95"),
    )
    focus_next_high = ge(
        data,
        "focus_badness_v1__next_median",
        tv("focus_badness_v1", "q95"),
    )
    persistent_veil = veil_high & veil_prev_high & veil_next_high
    persistent_focus = focus_high & focus_prev_high & focus_next_high
    data["cand_lens_persistent_degradation_proxy"] = eligible & (
        persistent_veil | persistent_focus
    )

    data["cand_glare_high"] = eligible & ge(
        data, "specular_ratio", tv("specular_ratio", "q95")
    )
    data["cand_glare_extreme"] = eligible & ge(
        data, "specular_ratio", tv("specular_ratio", "q99")
    )
    data["cand_whiteout_high"] = eligible & ge(
        data, "saturation_ratio", tv("saturation_ratio", "q95")
    )
    data["cand_whiteout_extreme"] = eligible & ge(
        data, "saturation_ratio", tv("saturation_ratio", "q99")
    )
    data["cand_lowlight_high"] = eligible & ge(
        data, "low_light_metric", tv("low_light_metric", "q95")
    )
    data["cand_lowlight_extreme"] = eligible & ge(
        data, "low_light_metric", tv("low_light_metric", "q99")
    )

    structure_high = ge(
        data,
        "center_low_structure_area_v1",
        tv("center_low_structure_area_v1", "q95"),
    )
    structure_extreme = ge(
        data,
        "center_low_structure_area_v1",
        tv("center_low_structure_area_v1", "q99"),
    )
    maxcomp_high = ge(
        data,
        "local_obstruction_max_component_ratio",
        tv("local_obstruction_max_component_ratio", "q95"),
    )
    maxcomp_extreme = ge(
        data,
        "local_obstruction_max_component_ratio",
        tv("local_obstruction_max_component_ratio", "q99"),
    )
    data["cand_obstruction_high"] = eligible & (structure_high | maxcomp_high)
    data["cand_obstruction_extreme"] = eligible & (structure_extreme | maxcomp_extreme)

    edge_low = le(data, "roi_edge_density_v1", tv("roi_edge_density_v1", "q05"))
    entropy_low = le(
        data,
        "roi_gray_entropy_bits_v1",
        tv("roi_gray_entropy_bits_v1", "q05"),
    )
    structure_abrupt = ge(
        data,
        "center_low_structure_area_v1__abruptness",
        tv("center_low_structure_area_v1__abruptness", "q95"),
    )

    edge_available = int(t.get("roi_edge_density_v1", {}).get("n_valid", 0)) > 0
    entropy_available = int(t.get("roi_gray_entropy_bits_v1", {}).get("n_valid", 0)) > 0

    if edge_available or entropy_available:
        local_low_any = pd.Series(False, index=data.index)
        if edge_available:
            local_low_any |= edge_low
        if entropy_available:
            local_low_any |= entropy_low
        data["cand_near_contact_relaxed_proxy"] = (
            eligible & structure_high & structure_abrupt & local_low_any
        )
        if edge_available and entropy_available:
            data["cand_near_contact_strict_proxy"] = (
                eligible & structure_high & structure_abrupt & edge_low & entropy_low
            )
        else:
            data["cand_near_contact_strict_proxy"] = False
    else:
        data["cand_near_contact_relaxed_proxy"] = False
        data["cand_near_contact_strict_proxy"] = False

    data["cand_blood_preselector_high"] = eligible & ge(
        data,
        "blood_preselector_metric",
        tv("blood_preselector_metric", "q95"),
    )
    data["cand_blood_preselector_extreme"] = eligible & ge(
        data,
        "blood_preselector_metric",
        tv("blood_preselector_metric", "q99"),
    )

    flags = [c for c in data.columns if c.startswith("cand_")]
    return data, flags


PRIMARY_FLAGS = [
    ("blur", "cand_blur_high"),
    ("smoke", "cand_smoke_temporal_proxy"),
    ("lens_contamination", "cand_lens_persistent_degradation_proxy"),
    ("glare", "cand_glare_high"),
    ("whiteout", "cand_whiteout_high"),
    ("lowlight", "cand_lowlight_high"),
    ("physical_obstruction", "cand_obstruction_high"),
    ("near_contact", "cand_near_contact_relaxed_proxy"),
    ("blood", "cand_blood_preselector_high"),
]


def build_summary(
    data: pd.DataFrame, flags: Sequence[str], eligible: pd.Series
) -> pd.DataFrame:
    rows = []
    denom = int(eligible.sum())
    for flag in flags:
        mask = data[flag].fillna(False).astype(bool)
        counts = data.loc[mask].groupby("case_id", sort=False).size().astype(int)
        rows.append(
            {
                "candidate_flag": flag,
                "candidate_count": int(mask.sum()),
                "candidate_percent_of_eligible": (
                    100.0 * mask.sum() / denom if denom else np.nan
                ),
                "unique_cases": int(data.loc[mask, "case_id"].nunique()),
                "per_case_min": int(counts.min()) if len(counts) else 0,
                "per_case_median": float(counts.median()) if len(counts) else 0.0,
                "per_case_max": int(counts.max()) if len(counts) else 0,
            }
        )
    return pd.DataFrame(rows).sort_values("candidate_flag")


def build_by_case(data: pd.DataFrame, flags: Sequence[str]) -> pd.DataFrame:
    rows = []
    for case in sorted(data["case_id"].dropna().unique()):
        g = data[data["case_id"] == case]
        for flag in flags:
            rows.append(
                {
                    "case_id": case,
                    "candidate_flag": flag,
                    "count": bool_count(g[flag]),
                }
            )
    return pd.DataFrame(rows)


def build_overlap(data: pd.DataFrame) -> pd.DataFrame:
    available = [(name, flag) for name, flag in PRIMARY_FLAGS if flag in data.columns]
    rows = []
    for i, (name_a, flag_a) in enumerate(available):
        a = data[flag_a].fillna(False).astype(bool)
        for name_b, flag_b in available[i:]:
            b = data[flag_b].fillna(False).astype(bool)
            inter = int((a & b).sum())
            union = int((a | b).sum())
            rows.append(
                {
                    "construct_a": name_a,
                    "construct_b": name_b,
                    "flag_a": flag_a,
                    "flag_b": flag_b,
                    "intersection_count": inter,
                    "union_count": union,
                    "jaccard": inter / union if union else np.nan,
                }
            )
    return pd.DataFrame(rows)


def build_candidate_reasons(data: pd.DataFrame, flags: Sequence[str]) -> pd.Series:
    arr = data[list(flags)].fillna(False).to_numpy(dtype=bool)
    names = np.array(flags, dtype=object)
    reasons = []
    for row in arr:
        reasons.append(";".join(names[row]))
    return pd.Series(reasons, index=data.index)


def write_readme(
    outdir: Path,
    args: argparse.Namespace,
    data: pd.DataFrame,
    eligible: pd.Series,
    file_inv: pd.DataFrame,
    summary: pd.DataFrame,
    metric_inv: pd.DataFrame,
    pilot_total: int,
    pilot_matched: int,
    pilot_unmatched: int,
    technical_invalid: int,
) -> None:
    included_files = int(file_inv["included"].fillna(False).sum())
    excluded_files = int((~file_inv["included"].fillna(False)).sum())
    any_candidates = int(data["candidate_any"].sum())

    metric_lines = []
    for _, r in metric_inv.iterrows():
        metric_lines.append(
            f"- `{r['canonical_metric']}`: "
            f"{int(r['files_available'])}/{int(r['files_total'])} files; "
            f"source(s): {r['source_columns_observed'] or 'not found'}"
        )

    summary_lines = []
    for _, r in summary.iterrows():
        summary_lines.append(
            f"- `{r['candidate_flag']}`: {int(r['candidate_count']):,} frames, "
            f"{int(r['unique_cases'])} cases"
        )

    txt = f"""# Phase 01 targeted candidate audit

This directory contains a **candidate-pool audit**, not a final review-set selection.

## Inputs

- metrics directory: `{args.metrics_dir}`
- pilot moments: `{args.pilot_moments}`
- temporal window: {args.temporal_window} sampled frames
- high quantile: {args.high_quantile}
- extreme quantile: {args.extreme_quantile}
- low quantile: {args.low_quantile}

## Lineage

- per-frame rows loaded: {len(data):,}
- included case CSVs: {included_files}
- excluded/non-per-frame CSVs: {excluded_files}
- technical-invalid rows flagged: {technical_invalid:,}
- pilot moments listed in input: {pilot_total:,}
- pilot moments matched/excluded from candidate eligibility: {pilot_matched:,}
- pilot moments not present in this metric directory: {pilot_unmatched:,}
- eligible rows: {int(eligible.sum()):,}
- rows in union of candidate pools: {any_candidates:,}

Expected raw analyzable row count supplied to the script: {args.expected_rows:,}

## Important interpretation rules

- These flags are **retrieval heuristics**, not clinical labels.
- Smoke temporal flags do not constitute smoke ground truth.
- Persistent degradation is only a lens-contamination **enrichment proxy**.
- Blood/redness is only a **preselector** and must not be interpreted as blood ground truth.
- Near-contact flags are local/temporal proxies and require surgeon review.
- Known exact aliases are canonicalized and never counted as independent metrics.
- The existing 30-frame pilot is excluded from candidate pools.
- Historical per-frame files are never modified.

## Metric availability

{chr(10).join(metric_lines)}

## Candidate counts

{chr(10).join(summary_lines)}

## Files

- `phase01_targeted_candidate_thresholds.csv`
- `phase01_targeted_candidate_summary.csv`
- `phase01_targeted_candidate_by_case.csv`
- `phase01_targeted_candidate_overlap.csv`
- `phase01_targeted_candidate_pool.csv`
- `phase01_targeted_metric_inventory.csv`
- `phase01_targeted_file_inventory.csv`
- `phase01_targeted_pilot_exclusion_audit.csv`

## Next decision

Inspect candidate counts, case concentration, overlaps, and representative images.
Only after this audit should the final targeted-calibration allocation be fixed.
"""
    (outdir / "README.md").write_text(txt, encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    ensure_valid_args(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/7] Loading per-frame metric CSVs...")
    data, file_inv, metric_inv = load_per_frame_data(
        args.metrics_dir, args.blood_metric
    )

    loaded_rows = len(data)
    print(f"      Loaded rows: {loaded_rows:,}")

    if args.expected_rows and loaded_rows != args.expected_rows:
        print(
            f"WARNING: loaded {loaded_rows:,} rows, expected "
            f"{args.expected_rows:,}. See file inventory.",
            file=sys.stderr,
        )

    data["_technical_invalid"] = is_technical_invalid(data["metric_status"])
    technical_invalid_n = int(data["_technical_invalid"].sum())

    print("[2/7] Loading existing pilot moments...")
    pilot = load_pilot_keys(args.pilot_moments)
    data["_pilot_key"] = (
        normalise_case_series(data["case_id"])
        + "|"
        + data["sample_time_sec"].round(3).map(
            lambda x: f"{x:.3f}" if pd.notna(x) else "NA"
        )
    )
    pilot_keys = set(pilot["_pilot_key"])
    observed_keys = set(data["_pilot_key"])
    pilot["matched_in_metrics"] = pilot["_pilot_key"].isin(observed_keys)
    pilot_audit = pilot[["case_id", "sample_time_sec", "_pilot_key", "matched_in_metrics"]].copy()
    pilot_audit["note"] = np.where(
        pilot_audit["matched_in_metrics"],
        "excluded_from_candidate_eligibility",
        "not_present_in_metric_directory",
    )
    data["_existing_pilot"] = data["_pilot_key"].isin(pilot_keys)
    pilot_removed_n = int(data["_existing_pilot"].sum())
    pilot_total_n = int(len(pilot_audit))
    pilot_unmatched_n = int((~pilot_audit["matched_in_metrics"]).sum())

    print("[3/7] Computing temporal retrieval features...")
    data = add_temporal_features(data, args.temporal_window, args.min_neighbor)

    eligible = (
        (~data["_technical_invalid"])
        & (~data["_existing_pilot"])
        & data["sample_time_sec"].notna()
    )

    print("[4/7] Computing thresholds...")
    thresholds = build_threshold_table(
        data,
        eligible,
        args.low_quantile,
        args.high_quantile,
        args.extreme_quantile,
    )

    print("[5/7] Building construct-specific candidate flags...")
    data, flags = add_candidate_flags(data, eligible, thresholds)

    data["candidate_any"] = data[flags].fillna(False).any(axis=1) if flags else False
    data["candidate_reason"] = build_candidate_reasons(data, flags)

    summary = build_summary(data, flags, eligible)
    by_case = build_by_case(data, flags)
    overlap = build_overlap(data)

    print("[6/7] Writing audit outputs...")
    outdir = args.output_dir

    thresholds.to_csv(
        outdir / "phase01_targeted_candidate_thresholds.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary.to_csv(
        outdir / "phase01_targeted_candidate_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    by_case.to_csv(
        outdir / "phase01_targeted_candidate_by_case.csv",
        index=False,
        encoding="utf-8-sig",
    )
    overlap.to_csv(
        outdir / "phase01_targeted_candidate_overlap.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metric_inv.to_csv(
        outdir / "phase01_targeted_metric_inventory.csv",
        index=False,
        encoding="utf-8-sig",
    )
    file_inv.to_csv(
        outdir / "phase01_targeted_file_inventory.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pilot_audit.to_csv(
        outdir / "phase01_targeted_pilot_exclusion_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    candidate_cols = [
        "case_id",
        "sample_time_sec",
        "frame_index",
        "image_path",
        "metric_status",
        "_source_file",
        "focus_badness_v1",
        "veil_low_contrast_score_v1",
        "specular_ratio",
        "saturation_ratio",
        "low_light_metric",
        "center_low_structure_area_v1",
        "local_obstruction_max_component_ratio",
        "roi_edge_density_v1",
        "roi_gray_entropy_bits_v1",
        "blood_preselector_metric",
        "veil_low_contrast_score_v1__prev_median",
        "veil_low_contrast_score_v1__next_median",
        "veil_low_contrast_score_v1__delta_prev",
        "veil_low_contrast_score_v1__delta_next",
        "veil_low_contrast_score_v1__abruptness",
        "focus_badness_v1__prev_median",
        "focus_badness_v1__next_median",
        "center_low_structure_area_v1__prev_median",
        "center_low_structure_area_v1__next_median",
        "center_low_structure_area_v1__abruptness",
        *flags,
        "candidate_any",
        "candidate_reason",
    ]
    candidate_cols = [c for c in candidate_cols if c in data.columns]

    pool = data.loc[data["candidate_any"], candidate_cols].copy()
    pool = pool.sort_values(["case_id", "sample_time_sec"], kind="mergesort")
    pool.to_csv(
        outdir / "phase01_targeted_candidate_pool.csv",
        index=False,
        encoding="utf-8-sig",
    )

    write_readme(
        outdir,
        args,
        data,
        eligible,
        file_inv,
        summary,
        metric_inv,
        pilot_total_n,
        pilot_removed_n,
        pilot_unmatched_n,
        technical_invalid_n,
    )

    print("[7/7] Done.")
    print()
    print(f"Rows loaded:                {len(data):,}")
    print(f"Technical invalid:          {technical_invalid_n:,}")
    print(f"Pilot moments listed:       {pilot_total_n:,}")
    print(f"Pilot moments matched:      {pilot_removed_n:,}")
    print(f"Pilot moments unmatched:    {pilot_unmatched_n:,}")
    print(f"Eligible rows:              {int(eligible.sum()):,}")
    print(f"Candidate-pool union:       {int(data['candidate_any'].sum()):,}")
    print()
    print("Candidate counts:")
    for _, r in summary.iterrows():
        print(
            f"  {r['candidate_flag']:<45} "
            f"{int(r['candidate_count']):>8,} "
            f"({int(r['unique_cases'])} cases)"
        )
    print()
    print(f"Saved to: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
