#!/usr/bin/env python
"""Build per-component cutoff audit summaries and frame review sets.

This script is intended for method-development review before downstream field
phenotype analysis. It answers, for each score column and threshold quantile:

- How many frames are above the p95/p99 cutoff?
- What fraction of frames would be excluded?
- How are excluded frames distributed across level-1 phases?
- Which frames are top, bottom, just above cutoff, and just below cutoff?

The output review CSV keeps all source columns from the input frame table when
possible, so existing montage/export scripts can reuse frame/video metadata.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

DEFAULT_TIER1_SCORE_COLS = [
    "structural_visibility_loss_v1",
    "center_low_structure_area_v1",
    "whiteout_ratio_v1",
    "low_light_or_blackout_ratio_v1",
]

COMMON_COMPONENT_SCORE_COLS = [
    "structural_visibility_loss_v1",
    "center_low_structure_area_v1",
    "whiteout_ratio_v1",
    "low_light_or_blackout_ratio_v1",
    "reblur_response_loss_v1",
    "veil_low_contrast_score_v1",
    "blackness_raw_ratio_v1",
    "blackness_corrected_ratio_v1",
    "specular_like_ratio_v1",
]

SCORE_COL_TO_COMPONENT = {
    "structural_visibility_loss_v1": "structural_visibility_loss",
    "center_low_structure_area_v1": "center_low_structure_area",
    "whiteout_ratio_v1": "whiteout",
    "low_light_or_blackout_ratio_v1": "low_light_or_blackout",
    "reblur_response_loss_v1": "reblur_response_loss",
    "veil_low_contrast_score_v1": "veil_low_contrast",
    "blackness_raw_ratio_v1": "raw_blackness",
    "blackness_corrected_ratio_v1": "corrected_blackness",
    "specular_like_ratio_v1": "specular_like_reflection",
    "composite_degradation_score": "legacy_badness_alias",
}

PHASE_COL_CANDIDATES = [
    "level1_phase",
    "level1",
    "phase",
    "phase_label",
    "level1_label",
    "label_level1",
    "annotation_level1",
]

CASE_COL_CANDIDATES = ["case_id", "case", "original_case_id", "case_uid"]

TIME_COL_CANDIDATES = [
    "sample_interval_sec",
    "frame_interval_sec",
    "interval_sec",
    "seconds_per_frame",
]

PHASE_SUMMARY_COLUMNS = [
    "group_col",
    "group_value",
    "score_col",
    "component",
    "threshold_name",
    "cutoff_value",
    "total_frames",
    "n_evaluable",
    "n_excluded_ge_cutoff",
    "frac_excluded_of_evaluable",
    "total_duration_sec",
    "excluded_duration_sec",
    "frac_excluded_duration",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build component p95/p99 cutoff audit summaries and review frame sets."
    )
    parser.add_argument(
        "--frame-table",
        required=True,
        help="Frame-level CSV containing score columns, e.g. visual_hazard_frame_flags.csv.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for audit summary outputs.",
    )
    parser.add_argument(
        "--annotation-output-dir",
        default=None,
        help="Optional directory to also write the review-frame CSV for montage export.",
    )
    parser.add_argument(
        "--score-col",
        nargs="*",
        default=None,
        help=(
            "Score columns to audit. If omitted, the script uses known Tier-1 columns "
            "that are present in the frame table."
        ),
    )
    parser.add_argument(
        "--score-col-mode",
        choices=["tier1", "common", "auto"],
        default="tier1",
        help=(
            "How to select score columns when --score-col is omitted. "
            "tier1: four primary gate metrics; common: known component metrics; "
            "auto: numeric *_v1 columns excluding flags."
        ),
    )
    parser.add_argument(
        "--quantile",
        nargs="*",
        default=["p95", "p99"],
        help="Quantile cutoffs to evaluate, e.g. p95 p99.",
    )
    parser.add_argument(
        "--phase-col",
        default=None,
        help="Level-1 phase column. If omitted, common column names are auto-detected.",
    )
    parser.add_argument(
        "--phase-distribution-csv",
        default=None,
        help=(
            "Optional Phase 03 case_phase_component_distribution_summary.csv. "
            "Use this when the frame table has no frame-level phase label. "
            "The script will build Level-1 phase summaries from the existing distribution table."
        ),
    )
    parser.add_argument(
        "--case-col",
        default=None,
        help="Case column. If omitted, common column names are auto-detected.",
    )
    parser.add_argument(
        "--duration-col",
        default=None,
        help=(
            "Optional per-frame duration/weight column. If omitted, the script uses "
            "sample_interval_sec if present; otherwise 1.0 second per frame."
        ),
    )
    parser.add_argument(
        "--n-review",
        type=int,
        default=10,
        help="Number of frames per selection bucket: top, bottom, just above, just below.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional development-only limit for debugging.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print concise overall summary to stdout.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    column_set = set(columns)
    for c in candidates:
        if c in column_set:
            return c
    return None


def quantile_name_to_float(name: str) -> float:
    text = str(name).strip().lower()
    if text.startswith("p"):
        value = float(text[1:]) / 100.0
    else:
        value = float(text)
        if value > 1.0:
            value = value / 100.0
    if not (0.0 < value < 1.0):
        raise ValueError(f"Invalid quantile: {name}")
    return value


def normalize_quantile_name(name: str) -> str:
    q = quantile_name_to_float(name)
    pct = int(round(q * 100))
    if abs(q * 100 - pct) < 1e-9:
        return f"p{pct}"
    return f"p{q * 100:g}"


def component_name_for_score(score_col: str) -> str:
    if score_col in SCORE_COL_TO_COMPONENT:
        return SCORE_COL_TO_COMPONENT[score_col]
    name = score_col
    if name.endswith("_v1"):
        name = name[:-3]
    name = name.replace("_ratio", "")
    name = name.replace("_score", "")
    return name


def display_component_name(score_col: str) -> str:
    if score_col.endswith("_v1"):
        return score_col[:-3]
    return score_col


def detect_score_columns(df: pd.DataFrame, mode: str) -> list[str]:
    if mode == "tier1":
        cols = [c for c in DEFAULT_TIER1_SCORE_COLS if c in df.columns]
    elif mode == "common":
        cols = [c for c in COMMON_COMPONENT_SCORE_COLS if c in df.columns]
    else:
        cols = []
        for c in df.columns:
            if not c.endswith("_v1"):
                continue
            lc = c.lower()
            if any(token in lc for token in ["flag", "candidate", "valid", "problem"]):
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > 0:
                cols.append(c)
    return cols


def as_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def get_duration_series(df: pd.DataFrame, duration_col: str | None) -> tuple[pd.Series, str]:
    col = duration_col
    if col is None:
        col = find_first_existing(df.columns, TIME_COL_CANDIDATES)
    if col and col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce").fillna(1.0)
        s = s.where(s > 0, 1.0)
        return s.astype(float), col
    return pd.Series(np.ones(len(df), dtype=float), index=df.index), "constant_1_sec"


def summarize_overall(
    df: pd.DataFrame,
    score_cols: list[str],
    quantiles: list[tuple[str, float]],
    duration: pd.Series,
) -> tuple[pd.DataFrame, dict[tuple[str, str], float]]:
    rows = []
    cutoffs: dict[tuple[str, str], float] = {}
    total_frames = int(len(df))
    total_duration = float(duration.sum())
    for score_col in score_cols:
        score = as_numeric_series(df, score_col)
        valid = score.notna()
        n_evaluable = int(valid.sum())
        n_missing = int((~valid).sum())
        valid_score = score[valid]
        for qname, qvalue in quantiles:
            cutoff = float(valid_score.quantile(qvalue)) if n_evaluable > 0 else math.nan
            cutoffs[(score_col, qname)] = cutoff
            excluded = valid & (score >= cutoff)
            n_excluded = int(excluded.sum())
            n_kept = int((valid & ~excluded).sum())
            excluded_duration = float(duration[excluded].sum())
            rows.append(
                {
                    "score_col": score_col,
                    "component": component_name_for_score(score_col),
                    "threshold_name": qname,
                    "quantile": qvalue,
                    "cutoff_value": cutoff,
                    "total_frames": total_frames,
                    "n_missing": n_missing,
                    "n_evaluable": n_evaluable,
                    "n_excluded_ge_cutoff": n_excluded,
                    "n_kept_lt_cutoff": n_kept,
                    "frac_excluded_of_evaluable": n_excluded / n_evaluable if n_evaluable else math.nan,
                    "frac_excluded_of_total": n_excluded / total_frames if total_frames else math.nan,
                    "total_duration_sec": total_duration,
                    "excluded_duration_sec": excluded_duration,
                    "frac_excluded_duration": excluded_duration / total_duration if total_duration else math.nan,
                }
            )
    return pd.DataFrame(rows), cutoffs


def summarize_by_group(
    df: pd.DataFrame,
    group_col: str,
    score_cols: list[str],
    quantiles: list[tuple[str, float]],
    cutoffs: dict[tuple[str, str], float],
    duration: pd.Series,
) -> pd.DataFrame:
    rows = []
    if group_col not in df.columns:
        return pd.DataFrame(columns=PHASE_SUMMARY_COLUMNS)
    group_values = df[group_col].fillna("NoLabel").astype(str)
    for score_col in score_cols:
        score = as_numeric_series(df, score_col)
        valid = score.notna()
        for qname, _qvalue in quantiles:
            cutoff = cutoffs[(score_col, qname)]
            excluded = valid & (score >= cutoff)
            tmp = pd.DataFrame(
                {
                    "group_value": group_values,
                    "valid": valid.astype(int),
                    "excluded": excluded.astype(int),
                    "duration": duration,
                    "excluded_duration": duration.where(excluded, 0.0),
                }
            )
            grouped = tmp.groupby("group_value", dropna=False, sort=True)
            for group_value, g in grouped:
                total = int(len(g))
                n_evaluable = int(g["valid"].sum())
                n_excluded = int(g["excluded"].sum())
                total_duration = float(g["duration"].sum())
                excluded_duration = float(g["excluded_duration"].sum())
                rows.append(
                    {
                        "group_col": group_col,
                        "group_value": group_value,
                        "score_col": score_col,
                        "component": component_name_for_score(score_col),
                        "threshold_name": qname,
                        "cutoff_value": cutoff,
                        "total_frames": total,
                        "n_evaluable": n_evaluable,
                        "n_excluded_ge_cutoff": n_excluded,
                        "frac_excluded_of_evaluable": n_excluded / n_evaluable if n_evaluable else math.nan,
                        "total_duration_sec": total_duration,
                        "excluded_duration_sec": excluded_duration,
                        "frac_excluded_duration": excluded_duration / total_duration if total_duration else math.nan,
                    }
                )
    return pd.DataFrame(rows)


def summarize_phase_from_distribution_csv(
    phase_distribution_csv: Path,
    score_cols: list[str],
    quantiles: list[tuple[str, float]],
    cutoffs: dict[tuple[str, str], float],
) -> pd.DataFrame:
    src = pd.read_csv(phase_distribution_csv, low_memory=False)
    if src.empty:
        return pd.DataFrame(columns=PHASE_SUMMARY_COLUMNS)

    if "phase_level" in src.columns:
        src = src[src["phase_level"].astype(str).eq("Level-1")].copy()

    component_col = "component" if "component" in src.columns else None
    phase_col = "phase_label" if "phase_label" in src.columns else find_first_existing(src.columns, PHASE_COL_CANDIDATES)
    n_col = "n_frames" if "n_frames" in src.columns else None
    if component_col is None or phase_col is None or n_col is None:
        print(
            "[WARN] phase distribution CSV did not contain required columns "
            "component/phase_label/n_frames; writing header-only phase summary."
        )
        return pd.DataFrame(columns=PHASE_SUMMARY_COLUMNS)

    rows = []
    for score_col in score_cols:
        comp = component_name_for_score(score_col)
        comp_src = src[src[component_col].astype(str).eq(comp)].copy()
        if comp_src.empty:
            print(f"[WARN] no phase distribution rows found for component={comp}")
            continue
        comp_src[n_col] = pd.to_numeric(comp_src[n_col], errors="coerce").fillna(0.0)
        for qname, _qvalue in quantiles:
            cutoff = cutoffs.get((score_col, qname), math.nan)
            frac_col = f"frac_ge_global_{qname}"
            seconds_col = f"seconds_ge_global_{qname}"
            if seconds_col not in comp_src.columns and frac_col not in comp_src.columns:
                print(
                    f"[WARN] phase distribution CSV lacks {seconds_col} or {frac_col}; "
                    f"skipping {score_col} {qname}."
                )
                continue

            tmp = comp_src[[phase_col, n_col]].copy()
            tmp[phase_col] = tmp[phase_col].fillna("NoLabel").astype(str)
            tmp["n_frames"] = pd.to_numeric(tmp[n_col], errors="coerce").fillna(0.0)
            if seconds_col in comp_src.columns:
                tmp["excluded"] = pd.to_numeric(comp_src[seconds_col], errors="coerce").fillna(0.0)
            else:
                tmp["excluded"] = tmp["n_frames"] * pd.to_numeric(
                    comp_src[frac_col], errors="coerce"
                ).fillna(0.0)

            grouped = tmp.groupby(phase_col, dropna=False, sort=True).agg(
                total_frames=("n_frames", "sum"),
                n_excluded_ge_cutoff=("excluded", "sum"),
            )
            grouped = grouped.reset_index()
            for _, r in grouped.iterrows():
                total = float(r["total_frames"])
                n_excluded = float(r["n_excluded_ge_cutoff"])
                rows.append(
                    {
                        "group_col": "phase_label",
                        "group_value": r[phase_col],
                        "score_col": score_col,
                        "component": comp,
                        "threshold_name": qname,
                        "cutoff_value": cutoff,
                        "total_frames": int(round(total)),
                        "n_evaluable": int(round(total)),
                        "n_excluded_ge_cutoff": int(round(n_excluded)),
                        "frac_excluded_of_evaluable": n_excluded / total if total else math.nan,
                        "total_duration_sec": total,
                        "excluded_duration_sec": n_excluded,
                        "frac_excluded_duration": n_excluded / total if total else math.nan,
                    }
                )
    return pd.DataFrame(rows, columns=PHASE_SUMMARY_COLUMNS)


def select_unique_rows(
    df: pd.DataFrame,
    sort_col: str,
    ascending: bool,
    n: int,
    used_indices: set[int] | None = None,
) -> pd.DataFrame:
    if used_indices is None:
        used_indices = set()
    candidates = df.loc[~df.index.isin(used_indices)].sort_values(sort_col, ascending=ascending)
    out = candidates.head(n).copy()
    used_indices.update(int(i) for i in out.index)
    return out


def build_review_frames(
    df: pd.DataFrame,
    score_cols: list[str],
    quantiles: list[tuple[str, float]],
    cutoffs: dict[tuple[str, str], float],
    n: int,
) -> pd.DataFrame:
    review_parts = []
    source_cols = list(df.columns)
    for score_col in score_cols:
        work = df.copy()
        work["score_value"] = as_numeric_series(work, score_col)
        work = work[work["score_value"].notna()].copy()
        if work.empty:
            continue
        used_global: set[int] = set()

        top = select_unique_rows(work, "score_value", ascending=False, n=n, used_indices=used_global)
        top["target_component"] = display_component_name(score_col)
        top["score_col"] = score_col
        top["threshold_name"] = "global"
        top["cutoff_value"] = np.nan
        top["selection_type"] = "top10_highest"
        top["rank_in_selection"] = np.arange(1, len(top) + 1)
        review_parts.append(top)

        bottom = select_unique_rows(work, "score_value", ascending=True, n=n, used_indices=used_global)
        bottom["target_component"] = display_component_name(score_col)
        bottom["score_col"] = score_col
        bottom["threshold_name"] = "global"
        bottom["cutoff_value"] = np.nan
        bottom["selection_type"] = "bottom10_lowest"
        bottom["rank_in_selection"] = np.arange(1, len(bottom) + 1)
        review_parts.append(bottom)

        for qname, _qvalue in quantiles:
            cutoff = cutoffs[(score_col, qname)]
            if not np.isfinite(cutoff):
                continue
            near = work.copy()
            near["cutoff_distance"] = near["score_value"] - cutoff

            above = near[near["score_value"] >= cutoff].sort_values(
                ["cutoff_distance", "score_value"], ascending=[True, True]
            )
            above = above.head(n).copy()
            above["target_component"] = display_component_name(score_col)
            above["score_col"] = score_col
            above["threshold_name"] = qname
            above["cutoff_value"] = cutoff
            above["selection_type"] = f"just_above_{qname}"
            above["rank_in_selection"] = np.arange(1, len(above) + 1)
            review_parts.append(above)

            below = near[near["score_value"] < cutoff].sort_values(
                ["cutoff_distance", "score_value"], ascending=[False, False]
            )
            below = below.head(n).copy()
            below["target_component"] = display_component_name(score_col)
            below["score_col"] = score_col
            below["threshold_name"] = qname
            below["cutoff_value"] = cutoff
            below["selection_type"] = f"just_below_{qname}"
            below["rank_in_selection"] = np.arange(1, len(below) + 1)
            review_parts.append(below)

    if not review_parts:
        return pd.DataFrame()
    review = pd.concat(review_parts, ignore_index=True, sort=False)
    review.insert(0, "review_id", [f"CUTAUDIT_{i:05d}" for i in range(1, len(review) + 1)])
    extra_cols = [
        "review_id",
        "target_component",
        "score_col",
        "score_value",
        "threshold_name",
        "cutoff_value",
        "cutoff_distance",
        "selection_type",
        "rank_in_selection",
    ]
    ordered = extra_cols + [c for c in source_cols if c not in extra_cols]
    return review[[c for c in ordered if c in review.columns]]


def write_csv(df: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if df.empty and columns is not None:
        df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False)
    print(f"[OK] wrote {path} rows={len(df)}")


def main() -> None:
    args = parse_args()
    output_dir = ensure_dir(Path(args.output_dir))
    annotation_output_dir = ensure_dir(Path(args.annotation_output_dir)) if args.annotation_output_dir else None

    df = pd.read_csv(args.frame_table, low_memory=False)
    if args.max_rows:
        df = df.head(args.max_rows).copy()
    print(f"[OK] loaded frame table rows={len(df)} cols={len(df.columns)}")

    if args.score_col:
        score_cols = [c for c in args.score_col if c in df.columns]
        missing = [c for c in args.score_col if c not in df.columns]
        if missing:
            print(f"[WARN] missing score columns ignored: {', '.join(missing)}")
    else:
        score_cols = detect_score_columns(df, args.score_col_mode)
    if not score_cols:
        raise SystemExit("No score columns found. Use --score-col to specify them explicitly.")
    print(f"[OK] score columns used: {', '.join(score_cols)}")

    quantiles = [(normalize_quantile_name(q), quantile_name_to_float(q)) for q in args.quantile]
    print(f"[OK] quantiles used: {', '.join(q for q, _ in quantiles)}")

    phase_col = args.phase_col or find_first_existing(df.columns, PHASE_COL_CANDIDATES)
    case_col = args.case_col or find_first_existing(df.columns, CASE_COL_CANDIDATES)
    duration, duration_source = get_duration_series(df, args.duration_col)
    print(f"[OK] phase column: {phase_col if phase_col else 'not_found'}")
    if args.phase_distribution_csv:
        print(f"[OK] phase distribution csv: {args.phase_distribution_csv}")
    print(f"[OK] case column: {case_col if case_col else 'not_found'}")
    print(f"[OK] duration source: {duration_source}")

    overall, cutoffs = summarize_overall(df, score_cols, quantiles, duration)
    write_csv(overall, output_dir / "component_cutoff_overall_summary.csv")

    if phase_col:
        phase_summary = summarize_by_group(df, phase_col, score_cols, quantiles, cutoffs, duration)
        write_csv(phase_summary, output_dir / "component_cutoff_level1_phase_summary.csv", PHASE_SUMMARY_COLUMNS)
    elif args.phase_distribution_csv:
        phase_summary = summarize_phase_from_distribution_csv(
            Path(args.phase_distribution_csv), score_cols, quantiles, cutoffs
        )
        write_csv(phase_summary, output_dir / "component_cutoff_level1_phase_summary.csv", PHASE_SUMMARY_COLUMNS)
    else:
        phase_summary = pd.DataFrame(columns=PHASE_SUMMARY_COLUMNS)
        write_csv(phase_summary, output_dir / "component_cutoff_level1_phase_summary.csv", PHASE_SUMMARY_COLUMNS)

    if case_col:
        case_summary = summarize_by_group(df, case_col, score_cols, quantiles, cutoffs, duration)
        write_csv(case_summary, output_dir / "component_cutoff_case_summary.csv")

    review = build_review_frames(df, score_cols, quantiles, cutoffs, args.n_review)
    review_path = output_dir / "component_cutoff_review_frames.csv"
    write_csv(review, review_path)
    if annotation_output_dir:
        write_csv(review, annotation_output_dir / "component_cutoff_review_frames.csv")

    inventory = pd.DataFrame(
        {
            "item": [
                "frame_table",
                "score_columns",
                "quantiles",
                "phase_column",
                "phase_distribution_csv",
                "case_column",
                "duration_source",
                "n_review_per_bucket",
                "review_id_added",
            ],
            "value": [
                str(args.frame_table),
                ";".join(score_cols),
                ";".join(q for q, _ in quantiles),
                phase_col or "",
                str(args.phase_distribution_csv or ""),
                case_col or "",
                duration_source,
                str(args.n_review),
                "true",
            ],
        }
    )
    write_csv(inventory, output_dir / "component_cutoff_audit_inventory.csv")

    if args.print_summary:
        cols = [
            "score_col",
            "threshold_name",
            "cutoff_value",
            "n_evaluable",
            "n_excluded_ge_cutoff",
            "frac_excluded_of_evaluable",
        ]
        print(overall[cols].to_string(index=False))


if __name__ == "__main__":
    main()
