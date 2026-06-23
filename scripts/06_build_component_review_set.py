#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build a component-specific frame review set from per-frame visual hazard metrics.

This script does not validate a metric. It only creates candidate positive and
negative examples for visual review. The generated CSV may contain image paths
and case identifiers, so it should generally remain local and should not be
committed to GitHub.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_DIR = PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "annotations" / "component_review_frames.csv"
SUMMARY_CSV_NAME = "_frame_score_summary.csv"


@dataclass(frozen=True)
class ScoreSpec:
    target_component: str
    score_col: str
    high_label: str
    low_label: str
    interpretation: str


DEFAULT_SCORE_SPECS: List[ScoreSpec] = [
    ScoreSpec(
        target_component="structural_visibility_loss",
        score_col="structural_visibility_loss_v1",
        high_label="candidate_structural_visibility_loss_high",
        low_label="candidate_structural_visibility_loss_low",
        interpretation="Higher values suggest loss of usable local structure; validate against surgeon review.",
    ),
    ScoreSpec(
        target_component="reblur_response_loss",
        score_col="reblur_response_loss_v1",
        high_label="candidate_reblur_response_loss_high",
        low_label="candidate_reblur_response_loss_low",
        interpretation="Higher values suggest weak response to additional Gaussian reblur, a high-frequency loss proxy.",
    ),
    ScoreSpec(
        target_component="veil_low_contrast",
        score_col="veil_low_contrast_score_v1",
        high_label="candidate_veil_low_contrast_high",
        low_label="candidate_veil_low_contrast_low",
        interpretation="Higher values suggest low-contrast / low-edge veil-like appearance, not validated smoke/fog.",
    ),
    ScoreSpec(
        target_component="whiteout",
        score_col="whiteout_ratio_v1",
        high_label="candidate_whiteout_high",
        low_label="candidate_whiteout_low",
        interpretation="Higher values suggest raw-image saturation / whiteout burden.",
    ),
    ScoreSpec(
        target_component="specular_like_reflection",
        score_col="specular_like_ratio_v1",
        high_label="candidate_specular_like_high",
        low_label="candidate_specular_like_low",
        interpretation="Higher values suggest high-value low-saturation specular-like pixels.",
    ),
    ScoreSpec(
        target_component="center_low_structure_area",
        score_col="center_low_structure_area_v1",
        high_label="candidate_center_low_structure_high",
        low_label="candidate_center_low_structure_low",
        interpretation="Higher values suggest center-weighted low-focus / low-structure patches, not validated obstruction.",
    ),
    ScoreSpec(
        target_component="low_light_or_blackout",
        score_col="low_light_or_blackout_ratio_v1",
        high_label="candidate_low_light_blackout_high",
        low_label="candidate_low_light_blackout_low",
        interpretation="Higher values suggest raw low-light / blackout photometric hazard.",
    ),
    ScoreSpec(
        target_component="raw_blackness",
        score_col="blackness_raw_ratio_v1",
        high_label="candidate_raw_blackness_high",
        low_label="candidate_raw_blackness_low",
        interpretation="Higher values suggest raw blackness; may be shadow, instrument, border, or material blackness.",
    ),
    ScoreSpec(
        target_component="corrected_blackness",
        score_col="blackness_corrected_ratio_v1",
        high_label="candidate_corrected_blackness_high",
        low_label="candidate_corrected_blackness_low",
        interpretation="Higher values suggest blackness after illumination normalization; still not validated anthracosis.",
    ),
    ScoreSpec(
        target_component="anthracosis_like_blackness_candidate",
        score_col="anthracosis_like_blackness_candidate_v1",
        high_label="candidate_anthracosis_like_blackness_high",
        low_label="candidate_anthracosis_like_blackness_low",
        interpretation="Higher values suggest blackness retained after simple raw/corrected filtering; manual validation required.",
    ),
]


CORE_OUTPUT_COLUMNS = [
    "review_id",
    "review_set_version",
    "case_id",
    "sample_time_sec",
    "frame_index",
    "image_path",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
    "target_component",
    "candidate_label",
    "selection_type",
    "source_score_col",
    "source_score_value",
    "source_rank_within_score",
    "selection_reason",
    "metric_status",
    "component_interpretation",
    "manual_include",
    "manual_primary_label",
    "manual_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build candidate frames for component-specific visual hazard review."
    )
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
        help=f"Directory containing per-case metric CSVs. Default: {DEFAULT_METRICS_DIR}",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output component review frame CSV. Default: {DEFAULT_OUTPUT_CSV}",
    )
    parser.add_argument(
        "--n-high",
        type=int,
        default=24,
        help="Number of high-scoring candidate frames per score column. Default: 24",
    )
    parser.add_argument(
        "--n-low",
        type=int,
        default=8,
        help="Number of low-scoring negative-control frames per score column. Default: 8",
    )
    parser.add_argument(
        "--per-case-cap",
        type=int,
        default=3,
        help="Maximum frames selected from one case for one score/direction. Default: 3",
    )
    parser.add_argument(
        "--case",
        nargs="*",
        default=None,
        help="Optional case_id filters, e.g. --case CASE003 CASE010",
    )
    parser.add_argument(
        "--score-col",
        nargs="*",
        default=None,
        help="Optional score columns to use. Defaults to built-in component score list.",
    )
    parser.add_argument(
        "--manual-seed-csv",
        type=Path,
        default=None,
        help="Optional manually curated CSV to append. It may contain any subset of output columns.",
    )
    parser.add_argument(
        "--review-set-version",
        default="phase02_v1",
        help="Version tag stored in output. Default: phase02_v1",
    )
    parser.add_argument(
        "--deduplicate-image-component",
        action="store_true",
        help="Drop duplicate image_path + target_component rows after selection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing output CSV.",
    )
    return parser.parse_args()


def list_metric_csvs(metrics_dir: Path, case_filter: Optional[set[str]]) -> List[Path]:
    paths = sorted(p for p in metrics_dir.glob("*.csv") if p.name != SUMMARY_CSV_NAME)
    if case_filter:
        out = []
        for p in paths:
            case_id = infer_case_id_from_path(p)
            if case_id in case_filter:
                out.append(p)
        return out
    return paths


def infer_case_id_from_path(path: Path) -> str:
    stem = path.stem
    for suffix in ["_frame_scores", "_metrics", "_visual_hazard_components"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def normalize_case_id(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    df = df.copy()
    if "case_id" not in df.columns:
        df["case_id"] = infer_case_id_from_path(path)
    else:
        df["case_id"] = df["case_id"].fillna(infer_case_id_from_path(path)).astype(str)
    return df


def load_metric_frames(metrics_dir: Path, case_filter: Optional[set[str]]) -> pd.DataFrame:
    csvs = list_metric_csvs(metrics_dir, case_filter)
    if not csvs:
        raise FileNotFoundError(f"No metric CSVs found in {metrics_dir}")

    dfs = []
    for path in csvs:
        df = pd.read_csv(path)
        df = normalize_case_id(df, path)
        df["source_metric_csv"] = str(path)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True, sort=False)


def select_with_per_case_cap(
    df: pd.DataFrame,
    score_col: str,
    n: int,
    ascending: bool,
    per_case_cap: int,
) -> pd.DataFrame:
    if n <= 0:
        return df.iloc[0:0].copy()
    valid = df[np.isfinite(pd.to_numeric(df[score_col], errors="coerce"))].copy()
    valid[score_col] = pd.to_numeric(valid[score_col], errors="coerce")
    valid = valid.sort_values(score_col, ascending=ascending)

    selected_idx = []
    case_counts: dict[str, int] = {}
    for idx, row in valid.iterrows():
        case_id = str(row.get("case_id", ""))
        if case_counts.get(case_id, 0) >= per_case_cap:
            continue
        selected_idx.append(idx)
        case_counts[case_id] = case_counts.get(case_id, 0) + 1
        if len(selected_idx) >= n:
            break
    return valid.loc[selected_idx].copy()


def stable_review_id(row: pd.Series, spec: ScoreSpec, selection_type: str, version: str, rank: int) -> str:
    key = "|".join(
        [
            str(version),
            str(row.get("case_id", "")),
            str(row.get("sample_time_sec", row.get("frame_index", ""))),
            str(row.get("image_path", "")),
            spec.target_component,
            spec.score_col,
            selection_type,
            str(rank),
        ]
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"RVW_{digest}"


def get_value(row: pd.Series, col: str, default=""):
    return row[col] if col in row.index else default


def frame_index_value(row: pd.Series):
    for col in ["frame_index", "frame_idx", "frame_id", "frame_no"]:
        if col in row.index:
            return row[col]
    return ""


def build_output_rows(
    selected: pd.DataFrame,
    spec: ScoreSpec,
    selection_type: str,
    candidate_label: str,
    review_set_version: str,
) -> List[dict]:
    rows: List[dict] = []
    for rank, (_, row) in enumerate(selected.iterrows(), start=1):
        out = {
            "review_id": stable_review_id(row, spec, selection_type, review_set_version, rank),
            "review_set_version": review_set_version,
            "case_id": get_value(row, "case_id"),
            "sample_time_sec": get_value(row, "sample_time_sec"),
            "frame_index": frame_index_value(row),
            "image_path": get_value(row, "image_path"),
            "roi_x0": get_value(row, "roi_x0"),
            "roi_y0": get_value(row, "roi_y0"),
            "roi_x1": get_value(row, "roi_x1"),
            "roi_y1": get_value(row, "roi_y1"),
            "target_component": spec.target_component,
            "candidate_label": candidate_label,
            "selection_type": selection_type,
            "source_score_col": spec.score_col,
            "source_score_value": float(row[spec.score_col]),
            "source_rank_within_score": rank,
            "selection_reason": f"auto_{selection_type}_by_{spec.score_col}",
            "metric_status": get_value(row, "metric_status"),
            "component_interpretation": spec.interpretation,
            "manual_include": "",
            "manual_primary_label": "",
            "manual_notes": "",
        }
        rows.append(out)
    return rows


def specs_from_args(score_cols: Optional[Iterable[str]]) -> List[ScoreSpec]:
    if not score_cols:
        return DEFAULT_SCORE_SPECS
    builtins = {s.score_col: s for s in DEFAULT_SCORE_SPECS}
    specs = []
    for col in score_cols:
        if col in builtins:
            specs.append(builtins[col])
        else:
            specs.append(
                ScoreSpec(
                    target_component=col.replace("_v1", ""),
                    score_col=col,
                    high_label=f"candidate_{col}_high",
                    low_label=f"candidate_{col}_low",
                    interpretation="Custom score column selected by user; manual validation required.",
                )
            )
    return specs


def append_manual_seed(out_df: pd.DataFrame, manual_seed_csv: Optional[Path], version: str) -> pd.DataFrame:
    if manual_seed_csv is None:
        return out_df
    if not manual_seed_csv.exists():
        raise FileNotFoundError(f"Manual seed CSV not found: {manual_seed_csv}")
    seed = pd.read_csv(manual_seed_csv)
    for col in CORE_OUTPUT_COLUMNS:
        if col not in seed.columns:
            seed[col] = ""
    seed = seed[CORE_OUTPUT_COLUMNS].copy()
    seed["review_set_version"] = seed["review_set_version"].replace("", version).fillna(version)
    seed.loc[seed["selection_reason"].astype(str).str.len() == 0, "selection_reason"] = "manual_seed"
    seed.loc[seed["selection_type"].astype(str).str.len() == 0, "selection_type"] = "manual"
    seed.loc[seed["candidate_label"].astype(str).str.len() == 0, "candidate_label"] = "manual_candidate"
    missing_id = seed["review_id"].astype(str).str.len() == 0
    for idx in seed[missing_id].index:
        key = f"{version}|manual|{idx}|{seed.at[idx, 'image_path']}|{seed.at[idx, 'target_component']}"
        seed.at[idx, "review_id"] = f"RVW_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]}"
    return pd.concat([out_df, seed], ignore_index=True, sort=False)


def main() -> None:
    args = parse_args()
    case_filter = set(args.case) if args.case else None
    df = load_metric_frames(args.metrics_dir, case_filter)

    if "metric_status" in df.columns:
        df = df[(df["metric_status"].isna()) | (df["metric_status"].astype(str) == "ok")].copy()

    specs = specs_from_args(args.score_col)
    rows: List[dict] = []
    skipped = []
    for spec in specs:
        if spec.score_col not in df.columns:
            skipped.append(spec.score_col)
            continue
        high = select_with_per_case_cap(df, spec.score_col, args.n_high, ascending=False, per_case_cap=args.per_case_cap)
        low = select_with_per_case_cap(df, spec.score_col, args.n_low, ascending=True, per_case_cap=args.per_case_cap)
        rows.extend(build_output_rows(high, spec, "high", spec.high_label, args.review_set_version))
        rows.extend(build_output_rows(low, spec, "low", spec.low_label, args.review_set_version))

    out_df = pd.DataFrame(rows, columns=CORE_OUTPUT_COLUMNS)
    out_df = append_manual_seed(out_df, args.manual_seed_csv, args.review_set_version)

    if args.deduplicate_image_component and not out_df.empty:
        out_df = out_df.drop_duplicates(subset=["image_path", "target_component"], keep="first").reset_index(drop=True)

    print(f"Loaded frames: {len(df)}")
    print(f"Selected review rows: {len(out_df)}")
    if skipped:
        print("Skipped missing score columns:", ", ".join(skipped))
    if not out_df.empty:
        print(out_df.groupby(["target_component", "selection_type"]).size().to_string())

    if args.dry_run:
        return

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output_csv, index=False)
    print(f"Wrote: {args.output_csv}")


if __name__ == "__main__":
    main()
