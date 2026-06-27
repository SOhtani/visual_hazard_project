#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build analyzable-frame sets from visual-hazard frame flags.

This script repositions the Phase 04 visual-hazard gate as a preprocessing
filter for downstream field-phenotype analyses. It does not treat hazard burden
as a final clinical endpoint.

Default interpretation:
- primary analyzable set: frames that are not severe visual-hazard frames (p99)
  and are not known technical/image-validity failures.
- conservative clean set: frames that are not broad visual-hazard frames (p95)
  and are not known technical/image-validity failures.

Expected input:
  reports/visual_hazard_burden/visual_hazard_frame_flags.csv

Expected outputs:
  data/annotations/analyzable_frames_primary_p99.csv
  data/annotations/clean_reference_frames_p95.csv
  data/annotations/excluded_visual_hazard_frames_p99.csv
  reports/analyzable_frame_sets/*.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRAME_FLAGS = PROJECT_ROOT / "reports" / "visual_hazard_burden" / "visual_hazard_frame_flags.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "analyzable_frame_sets"
DEFAULT_ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build analyzable-frame manifests from Phase 04 visual-hazard flags.")
    parser.add_argument("--frame-flags", type=Path, default=DEFAULT_FRAME_FLAGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--annotation-output-dir", type=Path, default=DEFAULT_ANNOTATION_DIR)
    parser.add_argument("--primary-threshold", default="p99", help="Severe-hazard threshold to exclude from primary phenotype analysis. Default: p99.")
    parser.add_argument("--clean-threshold", default="p95", help="Broad-hazard threshold to exclude from conservative clean reference. Default: p95.")
    parser.add_argument("--time-col", default="sample_time_sec")
    parser.add_argument("--case-col", default="case_id")
    parser.add_argument("--write-frame-manifests", action="store_true", help="Write frame-level manifest CSVs under data/annotations.")
    parser.add_argument("--max-rows-per-manifest", type=int, default=0, help="Optional cap for written frame manifests. 0 means no cap.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    x = s.astype(str).str.strip().str.lower()
    return x.isin(["1", "true", "t", "yes", "y"])


def maybe_bool(df: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index)
    return as_bool(df[col])


def sample_interval_by_case(df: pd.DataFrame, case_col: str, time_col: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if case_col not in df.columns or time_col not in df.columns:
        return {}
    for case_id, g in df.groupby(case_col):
        t = pd.to_numeric(g[time_col], errors="coerce").dropna().sort_values().to_numpy()
        if len(t) >= 2:
            d = np.diff(t)
            d = d[np.isfinite(d) & (d > 0)]
            out[str(case_id)] = float(np.median(d)) if len(d) else 1.0
        else:
            out[str(case_id)] = 1.0
    return out


def summarize_flags(df: pd.DataFrame, case_col: str, time_col: str, flag_cols: List[str]) -> pd.DataFrame:
    interval = sample_interval_by_case(df, case_col, time_col)
    rows = []
    for case_id, g in df.groupby(case_col):
        dt = interval.get(str(case_id), 1.0)
        row = {
            "case_id": case_id,
            "n_frames": int(len(g)),
            "estimated_duration_sec": float(len(g) * dt),
            "sample_interval_sec": float(dt),
        }
        for col in flag_cols:
            if col not in g.columns:
                continue
            f = maybe_bool(g, col)
            row[f"n_{col}"] = int(f.sum())
            row[f"frac_{col}"] = float(f.mean()) if len(f) else np.nan
            row[f"seconds_{col}"] = float(f.sum() * dt)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_phase_flags(df: pd.DataFrame, case_col: str, time_col: str, flag_cols: List[str]) -> pd.DataFrame:
    interval = sample_interval_by_case(df, case_col, time_col)
    phase_cols = [c for c in df.columns if c.startswith("workflow_level") and c.endswith("_label")]
    rows = []
    for phase_col in phase_cols:
        level = phase_col.replace("workflow_", "").replace("_label", "")
        tmp = df.copy()
        tmp["_phase_label"] = tmp[phase_col].fillna("").replace("", "NoLabel")
        for (case_id, phase_label), g in tmp.groupby([case_col, "_phase_label"], dropna=False):
            dt = interval.get(str(case_id), 1.0)
            row = {
                "case_id": case_id,
                "phase_level": level,
                "phase_label": phase_label,
                "n_frames": int(len(g)),
                "estimated_duration_sec": float(len(g) * dt),
                "sample_interval_sec": float(dt),
            }
            for col in flag_cols:
                if col not in g.columns:
                    continue
                f = maybe_bool(g, col)
                row[f"n_{col}"] = int(f.sum())
                row[f"frac_{col}"] = float(f.mean()) if len(f) else np.nan
                row[f"seconds_{col}"] = float(f.sum() * dt)
            rows.append(row)
    return pd.DataFrame(rows)


def add_analyzable_flags(df: pd.DataFrame, primary_threshold: str, clean_threshold: str) -> pd.DataFrame:
    df = df.copy()
    primary_hazard_col = f"visual_hazard_any_{primary_threshold}"
    clean_hazard_col = f"visual_hazard_any_{clean_threshold}"
    primary_clean_col = f"clean_reference_candidate_{primary_threshold}"
    clean_reference_col = f"clean_reference_candidate_{clean_threshold}"

    # If Phase 04 wrote clean_reference_candidate_p99/p95, prefer those because
    # they already exclude image-validity failures. Otherwise fall back to
    # not visual_hazard_any_* and explicitly exclude validity if present.
    validity_problem = maybe_bool(df, "image_validity_problem_candidate_v1", default=False)

    if primary_clean_col in df.columns:
        primary = maybe_bool(df, primary_clean_col)
    else:
        primary = ~maybe_bool(df, primary_hazard_col) & ~validity_problem

    if clean_reference_col in df.columns:
        clean = maybe_bool(df, clean_reference_col)
    else:
        clean = ~maybe_bool(df, clean_hazard_col) & ~validity_problem

    df[f"analyzable_frame_primary_{primary_threshold}"] = primary
    df[f"clean_reference_frame_{clean_threshold}"] = clean
    df[f"excluded_from_primary_by_hazard_{primary_threshold}"] = maybe_bool(df, primary_hazard_col)
    df[f"excluded_from_clean_by_hazard_{clean_threshold}"] = maybe_bool(df, clean_hazard_col)

    reasons = []
    for idx, row in df.iterrows():
        r = []
        if bool(validity_problem.loc[idx]):
            r.append("image_validity_problem")
        if bool(df.loc[idx, f"excluded_from_primary_by_hazard_{primary_threshold}"]):
            r.append(f"visual_hazard_any_{primary_threshold}")
        if not r:
            r.append("primary_analyzable")
        reasons.append(";".join(r))
    df[f"primary_exclusion_reason_{primary_threshold}"] = reasons
    return df


def select_manifest_columns(df: pd.DataFrame) -> List[str]:
    preferred = [
        "case_id",
        "sample_time_sec",
        "frame_index",
        "image_path",
        "roi_x0",
        "roi_y0",
        "roi_x1",
        "roi_y1",
    ]
    flags = [
        c for c in df.columns
        if c.startswith("analyzable_frame_")
        or c.startswith("clean_reference_frame_")
        or c.startswith("excluded_from_")
        or c.startswith("primary_exclusion_reason_")
        or c.startswith("visual_hazard_any_")
        or c.startswith("clean_reference_candidate_")
        or c.startswith("workflow_level")
    ]
    score_like = [
        c for c in df.columns
        if c.endswith("_v1") and (
            "whiteout" in c
            or "blackout" in c
            or "structure" in c
            or "visibility" in c
            or "blackness" in c
        )
    ]
    cols = []
    for col in preferred + flags + score_like:
        if col in df.columns and col not in cols:
            cols.append(col)
    return cols


def write_manifest(df: pd.DataFrame, path: Path, max_rows: int) -> None:
    out = df.copy()
    if max_rows and len(out) > max_rows:
        out = out.head(max_rows).copy()
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def main() -> None:
    args = parse_args()
    if not args.frame_flags.exists():
        raise FileNotFoundError(f"Frame flags not found: {args.frame_flags}")
    df = pd.read_csv(args.frame_flags, low_memory=False)
    if args.case_col not in df.columns:
        raise ValueError(f"case column not found: {args.case_col}")
    df = add_analyzable_flags(df, args.primary_threshold, args.clean_threshold)

    primary_col = f"analyzable_frame_primary_{args.primary_threshold}"
    clean_col = f"clean_reference_frame_{args.clean_threshold}"
    exclude_primary_col = f"excluded_from_primary_by_hazard_{args.primary_threshold}"
    exclude_clean_col = f"excluded_from_clean_by_hazard_{args.clean_threshold}"
    flag_cols = [primary_col, clean_col, exclude_primary_col, exclude_clean_col]

    case_summary = summarize_flags(df, args.case_col, args.time_col, flag_cols)
    phase_summary = summarize_phase_flags(df, args.case_col, args.time_col, flag_cols)

    overall = []
    n = len(df)
    for col in flag_cols:
        f = maybe_bool(df, col)
        overall.append({"flag": col, "n_frames": int(f.sum()), "frac_frames": float(f.mean()) if n else np.nan, "total_frames": int(n)})
    overall_summary = pd.DataFrame(overall)

    manifest_cols = select_manifest_columns(df)
    primary_df = df[maybe_bool(df, primary_col)][manifest_cols].copy()
    clean_df = df[maybe_bool(df, clean_col)][manifest_cols].copy()
    excluded_primary_df = df[~maybe_bool(df, primary_col)][manifest_cols].copy()

    print(f"[OK] loaded frame flags rows={len(df)} cases={df[args.case_col].nunique()}")
    print(f"[OK] primary analyzable set: {primary_col} n={len(primary_df)} frac={len(primary_df)/len(df):.4f}")
    print(f"[OK] conservative clean set: {clean_col} n={len(clean_df)} frac={len(clean_df)/len(df):.4f}")
    print(f"[OK] excluded from primary n={len(excluded_primary_df)} frac={len(excluded_primary_df)/len(df):.4f}")

    if args.dry_run:
        print(overall_summary.to_string(index=False))
        print(case_summary.head().to_string(index=False))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overall_summary.to_csv(args.output_dir / "analyzable_frame_overall_summary.csv", index=False)
    case_summary.to_csv(args.output_dir / "case_analyzable_frame_summary.csv", index=False)
    phase_summary.to_csv(args.output_dir / "case_phase_analyzable_frame_summary.csv", index=False)

    if args.write_frame_manifests:
        args.annotation_output_dir.mkdir(parents=True, exist_ok=True)
        write_manifest(primary_df, args.annotation_output_dir / f"analyzable_frames_primary_{args.primary_threshold}.csv", args.max_rows_per_manifest)
        write_manifest(clean_df, args.annotation_output_dir / f"clean_reference_frames_{args.clean_threshold}.csv", args.max_rows_per_manifest)
        write_manifest(excluded_primary_df, args.annotation_output_dir / f"excluded_from_primary_analyzable_{args.primary_threshold}.csv", args.max_rows_per_manifest)
        print(f"[OK] wrote {args.annotation_output_dir / f'analyzable_frames_primary_{args.primary_threshold}.csv'} rows={len(primary_df)}")
        print(f"[OK] wrote {args.annotation_output_dir / f'clean_reference_frames_{args.clean_threshold}.csv'} rows={len(clean_df)}")
        print(f"[OK] wrote {args.annotation_output_dir / f'excluded_from_primary_analyzable_{args.primary_threshold}.csv'} rows={len(excluded_primary_df)}")

    print(f"[OK] wrote {args.output_dir / 'analyzable_frame_overall_summary.csv'} rows={len(overall_summary)}")
    print(f"[OK] wrote {args.output_dir / 'case_analyzable_frame_summary.csv'} rows={len(case_summary)}")
    print(f"[OK] wrote {args.output_dir / 'case_phase_analyzable_frame_summary.csv'} rows={len(phase_summary)}")


if __name__ == "__main__":
    main()
