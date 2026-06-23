#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"
DEFAULT_INPUT = ANALYSIS_DIR / "all_frames_selected_scores.csv"


@dataclass
class Config:
    input_csv: Path
    output_csv: Path
    thresholds_csv: Path
    score_col: str
    case_col: str
    time_col: str
    primary_q_mild: float
    primary_q_bad: float
    primary_q_severe: float
    aux_q_bad: float
    min_tail_frames: int
    tail_frac_primary_mean: float
    tail_frac_primary_p90: float
    overwrite: bool
    quiet: bool


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute case-level badness summary using focus_badness_v1 distribution-aware thresholds."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input frame-level score CSV. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ANALYSIS_DIR / "rule_based_badness_per_case.csv",
        help="Output case-level CSV. Default: data/analysis/rule_based_badness_per_case.csv",
    )
    parser.add_argument(
        "--thresholds-csv",
        type=Path,
        default=ANALYSIS_DIR / "rule_based_badness_thresholds.csv",
        help="Output thresholds CSV. Default: data/analysis/rule_based_badness_thresholds.csv",
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
        "--primary-q-mild",
        type=float,
        default=0.95,
        help="Global quantile for mild bad threshold. Default: 0.95",
    )
    parser.add_argument(
        "--primary-q-bad",
        type=float,
        default=0.99,
        help="Global quantile for bad threshold. Default: 0.99",
    )
    parser.add_argument(
        "--primary-q-severe",
        type=float,
        default=0.995,
        help="Global quantile for severe bad threshold. Default: 0.995",
    )
    parser.add_argument(
        "--aux-q-bad",
        type=float,
        default=0.99,
        help="Global quantile for auxiliary bad thresholds. Default: 0.99",
    )
    parser.add_argument(
        "--min-tail-frames",
        type=int,
        default=3,
        help="Minimum number of frames included in top-tail means. Default: 3",
    )
    parser.add_argument(
        "--tail-frac-primary-mean",
        type=float,
        default=0.01,
        help="Tail fraction for continuous_badness_primary_mean. Default: 0.01",
    )
    parser.add_argument(
        "--tail-frac-primary-p90",
        type=float,
        default=0.005,
        help="Tail fraction for continuous_badness_primary_p90. Default: 0.005",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite outputs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce logging.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        thresholds_csv=args.thresholds_csv,
        score_col=args.score_col,
        case_col=args.case_col,
        time_col=args.time_col,
        primary_q_mild=float(args.primary_q_mild),
        primary_q_bad=float(args.primary_q_bad),
        primary_q_severe=float(args.primary_q_severe),
        aux_q_bad=float(args.aux_q_bad),
        min_tail_frames=int(args.min_tail_frames),
        tail_frac_primary_mean=float(args.tail_frac_primary_mean),
        tail_frac_primary_p90=float(args.tail_frac_primary_p90),
        overwrite=bool(args.overwrite),
        quiet=bool(args.quiet),
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def require_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def to_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def safe_quantile(s: pd.Series, q: float) -> float:
    s = pd.to_numeric(s, errors="coerce")
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    return float(s.quantile(q))


def safe_mean(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce")
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    return float(s.mean())


def safe_median(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce")
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    return float(s.median())


def safe_max(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce")
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    return float(s.max())


def safe_min(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce")
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    return float(s.min())


def top_tail_mean(s: pd.Series, frac: float, min_n: int) -> float:
    x = pd.to_numeric(s, errors="coerce")
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    n = max(int(np.ceil(len(x) * frac)), int(min_n))
    n = min(n, len(x))
    vals = np.sort(x.to_numpy())[::-1][:n]
    return float(np.mean(vals))


def frac_ge(s: pd.Series, thr: float) -> float:
    x = pd.to_numeric(s, errors="coerce")
    x = x[np.isfinite(x)]
    if len(x) == 0 or not np.isfinite(thr):
        return float("nan")
    return float((x >= thr).mean())


def n_ge(s: pd.Series, thr: float) -> int:
    x = pd.to_numeric(s, errors="coerce")
    x = x[np.isfinite(x)]
    if len(x) == 0 or not np.isfinite(thr):
        return 0
    return int((x >= thr).sum())


def segment_stats_from_threshold(
    case_df: pd.DataFrame,
    time_col: str,
    score_col: str,
    thr: float,
) -> Tuple[int, float]:
    """
    Returns:
        n_segments
        max_consecutive_bad_sec

    Assumes sample_time_sec is integer-ish seconds. Consecutive frames are counted
    when time increments by exactly 1 second.
    """
    if not np.isfinite(thr):
        return 0, float("nan")

    work = case_df[[time_col, score_col]].copy()
    work[time_col] = pd.to_numeric(work[time_col], errors="coerce")
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna(subset=[time_col, score_col]).sort_values(time_col).reset_index(drop=True)

    if len(work) == 0:
        return 0, float("nan")

    times = work[time_col].astype(float).to_numpy()
    bad = (work[score_col].astype(float).to_numpy() >= thr)

    n_segments = 0
    max_len = 0

    cur_len = 0
    prev_t: Optional[float] = None
    prev_bad = False

    for t, is_bad in zip(times, bad):
        if is_bad:
            if prev_bad and prev_t is not None and abs(t - prev_t - 1.0) < 1e-9:
                cur_len += 1
            else:
                n_segments += 1
                cur_len = 1
        else:
            cur_len = 0

        if cur_len > max_len:
            max_len = cur_len

        prev_t = t
        prev_bad = bool(is_bad)

    return int(n_segments), float(max_len)


def build_threshold_table(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    primary = to_numeric_series(df, config.score_col)

    rows.append({
        "metric": config.score_col,
        "threshold_name": "mild_bad_global",
        "threshold_value": safe_quantile(primary, config.primary_q_mild),
        "quantile": config.primary_q_mild,
    })
    rows.append({
        "metric": config.score_col,
        "threshold_name": "bad_global",
        "threshold_value": safe_quantile(primary, config.primary_q_bad),
        "quantile": config.primary_q_bad,
    })
    rows.append({
        "metric": config.score_col,
        "threshold_name": "severe_bad_global",
        "threshold_value": safe_quantile(primary, config.primary_q_severe),
        "quantile": config.primary_q_severe,
    })

    aux_cols = [
        "blur_score",
        "smoke_fog_score",
        "exposure_score",
        "glare_score",
    ]
    for col in aux_cols:
        if col in df.columns:
            rows.append({
                "metric": col,
                "threshold_name": "bad_global",
                "threshold_value": safe_quantile(to_numeric_series(df, col), config.aux_q_bad),
                "quantile": config.aux_q_bad,
            })

    return pd.DataFrame(rows)


def get_threshold(thr_df: pd.DataFrame, metric: str, threshold_name: str) -> float:
    x = thr_df.loc[
        (thr_df["metric"] == metric) & (thr_df["threshold_name"] == threshold_name),
        "threshold_value",
    ]
    if len(x) == 0:
        return float("nan")
    return float(x.iloc[0])


def summarize_case(
    case_df: pd.DataFrame,
    config: Config,
    thr_df: pd.DataFrame,
) -> Dict[str, object]:
    score = to_numeric_series(case_df, config.score_col)

    thr_mild = get_threshold(thr_df, config.score_col, "mild_bad_global")
    thr_bad = get_threshold(thr_df, config.score_col, "bad_global")
    thr_severe = get_threshold(thr_df, config.score_col, "severe_bad_global")

    n_seg_bad, max_seg_bad = segment_stats_from_threshold(case_df, config.time_col, config.score_col, thr_bad)
    n_seg_severe, max_seg_severe = segment_stats_from_threshold(case_df, config.time_col, config.score_col, thr_severe)

    out: Dict[str, object] = {
        config.case_col: case_df[config.case_col].iloc[0],
        "n_frames": int(score.notna().sum()),
        "score_min": safe_min(score),
        "score_mean": safe_mean(score),
        "score_median": safe_median(score),
        "score_p90": safe_quantile(score, 0.90),
        "score_p95": safe_quantile(score, 0.95),
        "score_p99": safe_quantile(score, 0.99),
        "score_max": safe_max(score),

        "global_thr_mild_bad": thr_mild,
        "global_thr_bad": thr_bad,
        "global_thr_severe_bad": thr_severe,

        "frac_ge_p95_global": frac_ge(score, thr_mild),
        "frac_ge_p99_global": frac_ge(score, thr_bad),
        "frac_ge_p995_global": frac_ge(score, thr_severe),

        "n_ge_p95_global": n_ge(score, thr_mild),
        "n_ge_p99_global": n_ge(score, thr_bad),
        "n_ge_p995_global": n_ge(score, thr_severe),

        "top1pct_mean": top_tail_mean(score, config.tail_frac_primary_mean, config.min_tail_frames),
        "top0p5pct_mean": top_tail_mean(score, config.tail_frac_primary_p90, config.min_tail_frames),

        "n_bad_segments_ge_p99_global": n_seg_bad,
        "max_consecutive_bad_sec_ge_p99_global": max_seg_bad,
        "n_bad_segments_ge_p995_global": n_seg_severe,
        "max_consecutive_bad_sec_ge_p995_global": max_seg_severe,
    }

    # Compatibility aliases for existing downstream ranking script
    out["continuous_badness_primary_mean"] = out["top1pct_mean"]
    out["continuous_badness_primary_p90"] = out["top0p5pct_mean"]
    out["any_bad_ratio"] = out["frac_ge_p99_global"]
    out["two_or_more_bad_ratio"] = out["frac_ge_p995_global"]
    out["continuous_badness_with_glare_mean"] = out["top1pct_mean"]

    # Auxiliary compatibility columns
    aux_map = {
        "blur_score": "blur_bad_ratio",
        "smoke_fog_score": "smoke_fog_bad_ratio",
        "exposure_score": "exposure_bad_ratio",
        "glare_score": "glare_bad_ratio",
    }
    for src_col, out_col in aux_map.items():
        if src_col in case_df.columns:
            thr = get_threshold(thr_df, src_col, "bad_global")
            out[out_col] = frac_ge(to_numeric_series(case_df, src_col), thr)
            out[f"{src_col}_global_bad_thr"] = thr
        else:
            out[out_col] = float("nan")
            out[f"{src_col}_global_bad_thr"] = float("nan")

    return out


def main() -> None:
    args = parse_args()
    config = build_config(args)

    if not config.input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {config.input_csv}")

    if config.output_csv.exists() and not config.overwrite:
        raise FileExistsError(
            f"Output already exists: {config.output_csv}\n"
            f"Use --overwrite to replace it."
        )

    df = pd.read_csv(config.input_csv)
    require_columns(df, [config.case_col, config.time_col, config.score_col])

    df[config.time_col] = pd.to_numeric(df[config.time_col], errors="coerce")
    df[config.score_col] = pd.to_numeric(df[config.score_col], errors="coerce")

    log(f"[INFO] input_csv={config.input_csv}", quiet=config.quiet)
    log(f"[INFO] n_rows={len(df)}", quiet=config.quiet)
    log(f"[INFO] n_cases={df[config.case_col].nunique()}", quiet=config.quiet)
    log(f"[INFO] primary_score_col={config.score_col}", quiet=config.quiet)

    thr_df = build_threshold_table(df, config)
    ensure_parent(config.thresholds_csv)
    thr_df.to_csv(config.thresholds_csv, index=False, encoding="utf-8-sig")

    thr_mild = get_threshold(thr_df, config.score_col, "mild_bad_global")
    thr_bad = get_threshold(thr_df, config.score_col, "bad_global")
    thr_severe = get_threshold(thr_df, config.score_col, "severe_bad_global")

    log(f"[INFO] global_thr_mild_bad={thr_mild:.6f}", quiet=config.quiet)
    log(f"[INFO] global_thr_bad={thr_bad:.6f}", quiet=config.quiet)
    log(f"[INFO] global_thr_severe_bad={thr_severe:.6f}", quiet=config.quiet)

    rows: List[Dict[str, object]] = []
    grouped = df.groupby(config.case_col, sort=True, dropna=False)

    for i, (case_id, case_df) in enumerate(grouped, start=1):
        row = summarize_case(case_df=case_df, config=config, thr_df=thr_df)
        rows.append(row)
        if (i % 10) == 0 or i == 1:
            log(f"[INFO] summarized {i}/{len(grouped)}: {case_id}", quiet=config.quiet)

    out_df = pd.DataFrame(rows)

    # Helpful ordering
    preferred_cols = [
        config.case_col,
        "n_frames",
        "score_min", "score_mean", "score_median", "score_p90", "score_p95", "score_p99", "score_max",
        "global_thr_mild_bad", "global_thr_bad", "global_thr_severe_bad",
        "frac_ge_p95_global", "frac_ge_p99_global", "frac_ge_p995_global",
        "n_ge_p95_global", "n_ge_p99_global", "n_ge_p995_global",
        "top1pct_mean", "top0p5pct_mean",
        "n_bad_segments_ge_p99_global", "max_consecutive_bad_sec_ge_p99_global",
        "n_bad_segments_ge_p995_global", "max_consecutive_bad_sec_ge_p995_global",
        "continuous_badness_primary_mean", "continuous_badness_primary_p90",
        "continuous_badness_with_glare_mean",
        "any_bad_ratio", "two_or_more_bad_ratio",
        "blur_bad_ratio", "smoke_fog_bad_ratio", "exposure_bad_ratio", "glare_bad_ratio",
        "blur_score_global_bad_thr", "smoke_fog_score_global_bad_thr",
        "exposure_score_global_bad_thr", "glare_score_global_bad_thr",
    ]
    remaining = [c for c in out_df.columns if c not in preferred_cols]
    out_df = out_df[[c for c in preferred_cols if c in out_df.columns] + remaining]

    ensure_parent(config.output_csv)
    out_df.to_csv(config.output_csv, index=False, encoding="utf-8-sig")

    log("[OK] rule-based badness per case written", quiet=config.quiet)
    log(f"[INFO] output_csv={config.output_csv}", quiet=config.quiet)
    log(f"[INFO] thresholds_csv={config.thresholds_csv}", quiet=config.quiet)


if __name__ == "__main__":
    main()