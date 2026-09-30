#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy.stats import wilcoxon
except Exception:
    wilcoxon = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"


@dataclass
class Config:
    score_csv: Path
    segments_csv: Optional[Path]
    out_event_csv: Path
    out_case_csv: Path
    out_summary_csv: Path
    score_col: str
    case_col: str
    time_col: str
    pre_window_sec: int
    post_window_sec: int
    pre_gap_sec: int
    post_gap_sec: int
    overwrite: bool
    quiet: bool


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze focus_badness_v1 delta before/after OOB events."
    )
    parser.add_argument(
        "--score-csv",
        type=Path,
        default=ANALYSIS_DIR / "all_frames_selected_scores.csv",
        help="Frame-level score CSV. Default: data/analysis/all_frames_selected_scores.csv",
    )
    parser.add_argument(
        "--segments-csv",
        type=Path,
        default=None,
        help="Optional OOB segment CSV. If omitted, the script searches likely paths automatically.",
    )
    parser.add_argument(
        "--out-event-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_event_delta.csv",
        help="Output event-level CSV.",
    )
    parser.add_argument(
        "--out-case-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_case_delta_summary.csv",
        help="Output case-level CSV.",
    )
    parser.add_argument(
        "--out-summary-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_overall_summary.csv",
        help="Output overall summary CSV.",
    )
    parser.add_argument(
        "--score-col",
        type=str,
        default="composite_degradation_score",
        help="Primary score column. Default: composite_degradation_score",
    )
    parser.add_argument(
        "--case-col",
        type=str,
        default="case_id",
        help="Case ID column. Default: case_id",
    )
    parser.add_argument(
        "--time-col",
        type=str,
        default="sample_time_sec",
        help="Time column in seconds. Default: sample_time_sec",
    )
    parser.add_argument(
        "--pre-window-sec",
        type=int,
        default=30,
        help="Seconds before OOB start used for pre-window. Default: 30",
    )
    parser.add_argument(
        "--post-window-sec",
        type=int,
        default=30,
        help="Seconds after OOB end used for post-window. Default: 30",
    )
    parser.add_argument(
        "--pre-gap-sec",
        type=int,
        default=0,
        help="Gap before OOB start excluded from pre-window. Default: 0",
    )
    parser.add_argument(
        "--post-gap-sec",
        type=int,
        default=0,
        help="Gap after OOB end excluded from post-window. Default: 0",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce logging.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        score_csv=args.score_csv,
        segments_csv=args.segments_csv,
        out_event_csv=args.out_event_csv,
        out_case_csv=args.out_case_csv,
        out_summary_csv=args.out_summary_csv,
        score_col=args.score_col,
        case_col=args.case_col,
        time_col=args.time_col,
        pre_window_sec=int(args.pre_window_sec),
        post_window_sec=int(args.post_window_sec),
        pre_gap_sec=int(args.pre_gap_sec),
        post_gap_sec=int(args.post_gap_sec),
        overwrite=bool(args.overwrite),
        quiet=bool(args.quiet),
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def require_columns(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def find_segments_csv(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"segments CSV not found: {explicit}")
        return explicit

    candidates = [
        ANALYSIS_DIR / "oob_segments.csv",
        ANALYSIS_DIR / "oob_event_segments.csv",
        ANALYSIS_DIR / "oob_events.csv",
        ANALYSIS_DIR / "oob_segment_table.csv",
        ANALYSIS_DIR / "intracavity_oob_segments.csv",
        PROJECT_ROOT / "data" / "derived" / "oob_segments.csv",
    ]
    for p in candidates:
        if p.exists():
            return p

    globbed = sorted(ANALYSIS_DIR.glob("*oob*segment*.csv")) + sorted(ANALYSIS_DIR.glob("*oob*event*.csv"))
    if globbed:
        return globbed[0]

    raise FileNotFoundError(
        "Could not find an OOB segment CSV automatically. "
        "Please pass --segments-csv explicitly."
    )


def infer_case_col(df: pd.DataFrame) -> str:
    for c in ["case_id", "case", "case_name", "caseid"]:
        if c in df.columns:
            return c
    raise ValueError("Could not infer case column in OOB segment CSV.")


def infer_start_col(df: pd.DataFrame) -> str:
    for c in [
        "oob_start_sec",
        "start_sec",
        "segment_start_sec",
        "start_time_sec",
        "start",
        "oob_start",
    ]:
        if c in df.columns:
            return c
    raise ValueError("Could not infer OOB start column in segment CSV.")


def infer_end_col(df: pd.DataFrame) -> str:
    for c in [
        "oob_end_sec",
        "end_sec",
        "segment_end_sec",
        "end_time_sec",
        "end",
        "oob_end",
    ]:
        if c in df.columns:
            return c
    raise ValueError("Could not infer OOB end column in segment CSV.")


def maybe_filter_oob_rows(df: pd.DataFrame) -> pd.DataFrame:
    text_cols = [c for c in ["segment_type", "label", "phase_type", "segment_label", "phase"] if c in df.columns]
    if not text_cols:
        return df

    mask = np.zeros(len(df), dtype=bool)
    for c in text_cols:
        vals = df[c].astype(str).str.lower().fillna("")
        mask = mask | vals.str.contains("oob")
    if mask.any():
        return df.loc[mask].copy()
    return df


def summarize_window(s: pd.Series) -> Dict[str, float]:
    x = pd.to_numeric(s, errors="coerce")
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {
            "n": 0,
            "mean": np.nan,
            "median": np.nan,
            "p90": np.nan,
            "min": np.nan,
            "max": np.nan,
        }
    return {
        "n": int(len(x)),
        "mean": float(x.mean()),
        "median": float(x.median()),
        "p90": float(x.quantile(0.90)),
        "min": float(x.min()),
        "max": float(x.max()),
    }


def nearest_row_before(df: pd.DataFrame, time_col: str, t: float) -> Optional[pd.Series]:
    z = df.loc[pd.to_numeric(df[time_col], errors="coerce") < t].copy()
    if len(z) == 0:
        return None
    z[time_col] = pd.to_numeric(z[time_col], errors="coerce")
    return z.sort_values(time_col).iloc[-1]


def nearest_row_after(df: pd.DataFrame, time_col: str, t: float) -> Optional[pd.Series]:
    z = df.loc[pd.to_numeric(df[time_col], errors="coerce") > t].copy()
    if len(z) == 0:
        return None
    z[time_col] = pd.to_numeric(z[time_col], errors="coerce")
    return z.sort_values(time_col).iloc[0]


def main() -> None:
    args = parse_args()
    config = build_config(args)

    if not config.score_csv.exists():
        raise FileNotFoundError(f"score CSV not found: {config.score_csv}")

    for p in [config.out_event_csv, config.out_case_csv, config.out_summary_csv]:
        if p.exists() and not config.overwrite:
            raise FileExistsError(f"Output exists: {p}. Use --overwrite to replace it.")

    segments_csv = find_segments_csv(config.segments_csv)

    scores = pd.read_csv(config.score_csv)
    require_columns(scores, [config.case_col, config.time_col, config.score_col])

    scores[config.time_col] = pd.to_numeric(scores[config.time_col], errors="coerce")
    scores[config.score_col] = pd.to_numeric(scores[config.score_col], errors="coerce")

    if "image_path" not in scores.columns:
        scores["image_path"] = np.nan

    seg = pd.read_csv(segments_csv)
    seg = maybe_filter_oob_rows(seg)

    seg_case_col = infer_case_col(seg)
    seg_start_col = infer_start_col(seg)
    seg_end_col = infer_end_col(seg)

    seg[seg_start_col] = pd.to_numeric(seg[seg_start_col], errors="coerce")
    seg[seg_end_col] = pd.to_numeric(seg[seg_end_col], errors="coerce")
    seg = seg.dropna(subset=[seg_case_col, seg_start_col, seg_end_col]).copy()

    # normalize column names
    seg = seg.rename(columns={
        seg_case_col: "case_id",
        seg_start_col: "oob_start_sec",
        seg_end_col: "oob_end_sec",
    })

    log(f"[INFO] score_csv={config.score_csv}", quiet=config.quiet)
    log(f"[INFO] segments_csv={segments_csv}", quiet=config.quiet)
    log(f"[INFO] n_score_rows={len(scores)}", quiet=config.quiet)
    log(f"[INFO] n_oob_segments={len(seg)}", quiet=config.quiet)

    rows: List[Dict[str, object]] = []

    grouped_scores = {
        case_id: sdf.sort_values(config.time_col).reset_index(drop=True)
        for case_id, sdf in scores.groupby(config.case_col, sort=False)
    }

    for idx, srow in seg.reset_index(drop=True).iterrows():
        case_id = str(srow["case_id"])
        start_sec = float(srow["oob_start_sec"])
        end_sec = float(srow["oob_end_sec"])
        if end_sec < start_sec:
            start_sec, end_sec = end_sec, start_sec

        case_df = grouped_scores.get(case_id)
        if case_df is None or len(case_df) == 0:
            continue

        pre_end = start_sec - config.pre_gap_sec
        pre_start = pre_end - config.pre_window_sec
        post_start = end_sec + config.post_gap_sec
        post_end = post_start + config.post_window_sec

        pre_df = case_df.loc[
            (case_df[config.time_col] >= pre_start) &
            (case_df[config.time_col] < pre_end)
        ].copy()

        post_df = case_df.loc[
            (case_df[config.time_col] > post_start) &
            (case_df[config.time_col] <= post_end)
        ].copy()

        pre_stats = summarize_window(pre_df[config.score_col])
        post_stats = summarize_window(post_df[config.score_col])

        pre_nearest = nearest_row_before(case_df, config.time_col, start_sec)
        post_nearest = nearest_row_after(case_df, config.time_col, end_sec)

        pre_nearest_score = float(pre_nearest[config.score_col]) if pre_nearest is not None else np.nan
        post_nearest_score = float(post_nearest[config.score_col]) if post_nearest is not None else np.nan

        row: Dict[str, object] = {
            "event_id": idx + 1,
            "case_id": case_id,
            "oob_start_sec": start_sec,
            "oob_end_sec": end_sec,
            "oob_duration_sec": float(end_sec - start_sec),

            "pre_window_start_sec": float(pre_start),
            "pre_window_end_sec": float(pre_end),
            "post_window_start_sec": float(post_start),
            "post_window_end_sec": float(post_end),

            "pre_n": pre_stats["n"],
            "pre_mean": pre_stats["mean"],
            "pre_median": pre_stats["median"],
            "pre_p90": pre_stats["p90"],
            "pre_min": pre_stats["min"],
            "pre_max": pre_stats["max"],

            "post_n": post_stats["n"],
            "post_mean": post_stats["mean"],
            "post_median": post_stats["median"],
            "post_p90": post_stats["p90"],
            "post_min": post_stats["min"],
            "post_max": post_stats["max"],

            "delta_post_minus_pre_mean": (
                float(post_stats["mean"] - pre_stats["mean"])
                if np.isfinite(post_stats["mean"]) and np.isfinite(pre_stats["mean"]) else np.nan
            ),
            "delta_post_minus_pre_median": (
                float(post_stats["median"] - pre_stats["median"])
                if np.isfinite(post_stats["median"]) and np.isfinite(pre_stats["median"]) else np.nan
            ),
            "improvement_mean": (
                float(pre_stats["mean"] - post_stats["mean"])
                if np.isfinite(post_stats["mean"]) and np.isfinite(pre_stats["mean"]) else np.nan
            ),
            "improvement_median": (
                float(pre_stats["median"] - post_stats["median"])
                if np.isfinite(post_stats["median"]) and np.isfinite(pre_stats["median"]) else np.nan
            ),

            "pre_nearest_time_sec": float(pre_nearest[config.time_col]) if pre_nearest is not None else np.nan,
            "pre_nearest_score": pre_nearest_score,
            "pre_nearest_image_path": str(pre_nearest["image_path"]) if pre_nearest is not None else "",

            "post_nearest_time_sec": float(post_nearest[config.time_col]) if post_nearest is not None else np.nan,
            "post_nearest_score": post_nearest_score,
            "post_nearest_image_path": str(post_nearest["image_path"]) if post_nearest is not None else "",

            "delta_post_minus_pre_nearest": (
                float(post_nearest_score - pre_nearest_score)
                if np.isfinite(post_nearest_score) and np.isfinite(pre_nearest_score) else np.nan
            ),
            "improvement_nearest": (
                float(pre_nearest_score - post_nearest_score)
                if np.isfinite(post_nearest_score) and np.isfinite(pre_nearest_score) else np.nan
            ),
        }

        row["improved_median"] = bool(np.isfinite(row["improvement_median"]) and row["improvement_median"] > 0)
        row["improved_nearest"] = bool(np.isfinite(row["improvement_nearest"]) and row["improvement_nearest"] > 0)

        rows.append(row)

    event_df = pd.DataFrame(rows)

    ensure_parent(config.out_event_csv)
    event_df.to_csv(config.out_event_csv, index=False, encoding="utf-8-sig")

    # case-level summary
    case_rows: List[Dict[str, object]] = []
    if len(event_df) > 0:
        for case_id, cdf in event_df.groupby("case_id", sort=True):
            case_rows.append({
                "case_id": case_id,
                "n_oob_events": int(len(cdf)),
                "median_pre_median": float(pd.to_numeric(cdf["pre_median"], errors="coerce").median()),
                "median_post_median": float(pd.to_numeric(cdf["post_median"], errors="coerce").median()),
                "median_delta_post_minus_pre_median": float(pd.to_numeric(cdf["delta_post_minus_pre_median"], errors="coerce").median()),
                "median_improvement_median": float(pd.to_numeric(cdf["improvement_median"], errors="coerce").median()),
                "improved_event_fraction_median": float(pd.to_numeric(cdf["improved_median"], errors="coerce").mean()),
                "median_delta_post_minus_pre_nearest": float(pd.to_numeric(cdf["delta_post_minus_pre_nearest"], errors="coerce").median()),
                "median_improvement_nearest": float(pd.to_numeric(cdf["improvement_nearest"], errors="coerce").median()),
                "improved_event_fraction_nearest": float(pd.to_numeric(cdf["improved_nearest"], errors="coerce").mean()),
            })

    case_df = pd.DataFrame(case_rows)
    ensure_parent(config.out_case_csv)
    case_df.to_csv(config.out_case_csv, index=False, encoding="utf-8-sig")

    # overall summary
    summary: Dict[str, object] = {
        "score_csv": str(config.score_csv),
        "segments_csv": str(segments_csv),
        "n_events_total": int(len(event_df)),
        "n_events_with_window_median": int(event_df["improvement_median"].notna().sum()) if len(event_df) > 0 else 0,
        "n_events_with_nearest": int(event_df["improvement_nearest"].notna().sum()) if len(event_df) > 0 else 0,
        "pre_window_sec": config.pre_window_sec,
        "post_window_sec": config.post_window_sec,
        "pre_gap_sec": config.pre_gap_sec,
        "post_gap_sec": config.post_gap_sec,
    }

    if len(event_df) > 0:
        imp_med = pd.to_numeric(event_df["improvement_median"], errors="coerce").dropna()
        imp_near = pd.to_numeric(event_df["improvement_nearest"], errors="coerce").dropna()
        pre_med = pd.to_numeric(event_df["pre_median"], errors="coerce").dropna()
        post_med = pd.to_numeric(event_df["post_median"], errors="coerce").dropna()

        summary.update({
            "median_improvement_median": float(imp_med.median()) if len(imp_med) else np.nan,
            "mean_improvement_median": float(imp_med.mean()) if len(imp_med) else np.nan,
            "improved_fraction_median": float((imp_med > 0).mean()) if len(imp_med) else np.nan,

            "median_improvement_nearest": float(imp_near.median()) if len(imp_near) else np.nan,
            "mean_improvement_nearest": float(imp_near.mean()) if len(imp_near) else np.nan,
            "improved_fraction_nearest": float((imp_near > 0).mean()) if len(imp_near) else np.nan,

            "median_pre_median": float(pre_med.median()) if len(pre_med) else np.nan,
            "median_post_median": float(post_med.median()) if len(post_med) else np.nan,
        })

        if wilcoxon is not None and len(pre_med) == len(post_med) and len(pre_med) >= 3:
            # alternative='greater' tests pre > post, i.e. improvement after OOB
            try:
                stat, pval = wilcoxon(pre_med, post_med, alternative="greater")
                summary["wilcoxon_pre_gt_post_stat"] = float(stat)
                summary["wilcoxon_pre_gt_post_p"] = float(pval)
            except Exception:
                summary["wilcoxon_pre_gt_post_stat"] = np.nan
                summary["wilcoxon_pre_gt_post_p"] = np.nan
        else:
            summary["wilcoxon_pre_gt_post_stat"] = np.nan
            summary["wilcoxon_pre_gt_post_p"] = np.nan

    summary_df = pd.DataFrame([summary])
    ensure_parent(config.out_summary_csv)
    summary_df.to_csv(config.out_summary_csv, index=False, encoding="utf-8-sig")

    log("[OK] OOB before/after focus_badness delta analysis complete", quiet=config.quiet)
    log(f"[INFO] event_csv={config.out_event_csv}", quiet=config.quiet)
    log(f"[INFO] case_csv={config.out_case_csv}", quiet=config.quiet)
    log(f"[INFO] summary_csv={config.out_summary_csv}", quiet=config.quiet)


if __name__ == "__main__":
    main()