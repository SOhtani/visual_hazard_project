#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy.stats import wilcoxon, binomtest
except Exception:
    wilcoxon = None
    binomtest = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OOB responsiveness statistics and window sensitivity analysis for focus_badness_v1."
    )
    parser.add_argument(
        "--score-csv",
        type=Path,
        default=ANALYSIS_DIR / "all_frames_selected_scores.csv",
        help="Frame-level score CSV.",
    )
    parser.add_argument(
        "--segments-csv",
        type=Path,
        default=ANALYSIS_DIR / "oob_segments_with_level1_context.csv",
        help="OOB event CSV with Level-1 context.",
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
        help="Case column. Default: case_id",
    )
    parser.add_argument(
        "--time-col",
        type=str,
        default="sample_time_sec",
        help="Time column in seconds. Default: sample_time_sec",
    )
    parser.add_argument(
        "--window-spec",
        action="append",
        default=[],
        help="Window spec as pre:post:pregap:postgap . Can be repeated. Example: 30:30:0:0",
    )
    parser.add_argument(
        "--bootstrap-iter",
        type=int,
        default=5000,
        help="Bootstrap iterations. Default: 5000",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=42,
        help="Bootstrap seed. Default: 42",
    )
    parser.add_argument(
        "--out-event-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_event_delta_multiwindow.csv",
        help="Output event-level CSV.",
    )
    parser.add_argument(
        "--out-overall-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_responsiveness_stats.csv",
        help="Output overall summary CSV.",
    )
    parser.add_argument(
        "--out-context-csv",
        type=Path,
        default=ANALYSIS_DIR / "focus_badness_oob_responsiveness_by_context.csv",
        help="Output context summary CSV.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite outputs.",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def default_window_specs() -> List[Tuple[int, int, int, int]]:
    return [
        (10, 10, 0, 0),
        (30, 30, 0, 0),
        (60, 60, 0, 0),
        (30, 30, 5, 5),
    ]


def parse_window_specs(specs: List[str]) -> List[Tuple[int, int, int, int]]:
    if not specs:
        return default_window_specs()

    out: List[Tuple[int, int, int, int]] = []
    for s in specs:
        parts = s.split(":")
        if len(parts) != 4:
            raise ValueError(f"Invalid --window-spec: {s}. Expected pre:post:pregap:postgap")
        out.append(tuple(int(x) for x in parts))
    return out


def window_name(pre: int, post: int, pre_gap: int, post_gap: int) -> str:
    return f"pre{pre}_post{post}_pregap{pre_gap}_postgap{post_gap}"


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


def exact_binom_greater_p(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return np.nan
    if binomtest is not None:
        return float(binomtest(k, n, p=p, alternative="greater").pvalue)
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return float(total)


def exact_binom_two_sided_p(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return np.nan
    if binomtest is not None:
        return float(binomtest(k, n, p=p, alternative="two-sided").pvalue)
    # conservative fallback
    lower = sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, min(k, n - k) + 1))
    return float(min(1.0, 2.0 * lower))


def bootstrap_ci(values: np.ndarray, stat_fn, n_iter: int, seed: int) -> Tuple[float, float]:
    x = np.asarray(values)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    stats = []
    n = len(x)
    for _ in range(n_iter):
        sample = x[rng.integers(0, n, size=n)]
        stats.append(stat_fn(sample))
    return (float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975)))


def compute_event_delta_for_window(
    scores: pd.DataFrame,
    segments: pd.DataFrame,
    case_col: str,
    time_col: str,
    score_col: str,
    pre_window_sec: int,
    post_window_sec: int,
    pre_gap_sec: int,
    post_gap_sec: int,
) -> pd.DataFrame:
    grouped_scores = {
        case_id: sdf.sort_values(time_col).reset_index(drop=True)
        for case_id, sdf in scores.groupby(case_col, sort=False)
    }

    rows: List[Dict[str, object]] = []
    wname = window_name(pre_window_sec, post_window_sec, pre_gap_sec, post_gap_sec)

    for _, srow in segments.iterrows():
        case_id = str(srow[case_col])
        start_sec = float(srow["oob_start_sec"])
        end_sec = float(srow["oob_end_sec"])
        if end_sec < start_sec:
            start_sec, end_sec = end_sec, start_sec

        case_df = grouped_scores.get(case_id)
        if case_df is None or len(case_df) == 0:
            continue

        pre_end = start_sec - pre_gap_sec
        pre_start = pre_end - pre_window_sec
        post_start = end_sec + post_gap_sec
        post_end = post_start + post_window_sec

        pre_df = case_df.loc[
            (case_df[time_col] >= pre_start) &
            (case_df[time_col] < pre_end)
        ].copy()

        post_df = case_df.loc[
            (case_df[time_col] > post_start) &
            (case_df[time_col] <= post_end)
        ].copy()

        pre_stats = summarize_window(pre_df[score_col])
        post_stats = summarize_window(post_df[score_col])

        pre_nearest = nearest_row_before(case_df, time_col, start_sec)
        post_nearest = nearest_row_after(case_df, time_col, end_sec)

        pre_nearest_score = float(pre_nearest[score_col]) if pre_nearest is not None else np.nan
        post_nearest_score = float(post_nearest[score_col]) if post_nearest is not None else np.nan

        row = srow.to_dict()
        row.update({
            "window_name": wname,
            "pre_window_sec": pre_window_sec,
            "post_window_sec": post_window_sec,
            "pre_gap_sec": pre_gap_sec,
            "post_gap_sec": post_gap_sec,

            "pre_window_start_sec": float(pre_start),
            "pre_window_end_sec": float(pre_end),
            "post_window_start_sec": float(post_start),
            "post_window_end_sec": float(post_end),

            "pre_n": pre_stats["n"],
            "pre_mean": pre_stats["mean"],
            "pre_median": pre_stats["median"],
            "pre_p90": pre_stats["p90"],

            "post_n": post_stats["n"],
            "post_mean": post_stats["mean"],
            "post_median": post_stats["median"],
            "post_p90": post_stats["p90"],

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

            "pre_nearest_time_sec": float(pre_nearest[time_col]) if pre_nearest is not None else np.nan,
            "pre_nearest_score": pre_nearest_score,
            "post_nearest_time_sec": float(post_nearest[time_col]) if post_nearest is not None else np.nan,
            "post_nearest_score": post_nearest_score,
            "delta_post_minus_pre_nearest": (
                float(post_nearest_score - pre_nearest_score)
                if np.isfinite(post_nearest_score) and np.isfinite(pre_nearest_score) else np.nan
            ),
            "improvement_nearest": (
                float(pre_nearest_score - post_nearest_score)
                if np.isfinite(post_nearest_score) and np.isfinite(pre_nearest_score) else np.nan
            ),
        })

        row["improved_median"] = bool(np.isfinite(row["improvement_median"]) and row["improvement_median"] > 0)
        row["improved_nearest"] = bool(np.isfinite(row["improvement_nearest"]) and row["improvement_nearest"] > 0)

        rows.append(row)

    return pd.DataFrame(rows)


def summarize_stats(df: pd.DataFrame, bootstrap_iter: int, bootstrap_seed: int) -> Dict[str, object]:
    out: Dict[str, object] = {
        "n_events_total": int(len(df)),
        "n_events_with_window_median": int(pd.to_numeric(df["improvement_median"], errors="coerce").notna().sum()),
        "n_events_with_nearest": int(pd.to_numeric(df["improvement_nearest"], errors="coerce").notna().sum()),
    }

    imp_med = pd.to_numeric(df["improvement_median"], errors="coerce").dropna().to_numpy(dtype=float)
    imp_near = pd.to_numeric(df["improvement_nearest"], errors="coerce").dropna().to_numpy(dtype=float)
    pre_med = pd.to_numeric(df["pre_median"], errors="coerce").dropna().to_numpy(dtype=float)
    post_med = pd.to_numeric(df["post_median"], errors="coerce").dropna().to_numpy(dtype=float)

    out["median_pre_median"] = float(np.median(pre_med)) if len(pre_med) else np.nan
    out["median_post_median"] = float(np.median(post_med)) if len(post_med) else np.nan

    out["median_improvement_median"] = float(np.median(imp_med)) if len(imp_med) else np.nan
    out["mean_improvement_median"] = float(np.mean(imp_med)) if len(imp_med) else np.nan
    out["improved_fraction_median"] = float(np.mean(imp_med > 0)) if len(imp_med) else np.nan

    out["median_improvement_nearest"] = float(np.median(imp_near)) if len(imp_near) else np.nan
    out["mean_improvement_nearest"] = float(np.mean(imp_near)) if len(imp_near) else np.nan
    out["improved_fraction_nearest"] = float(np.mean(imp_near > 0)) if len(imp_near) else np.nan

    if len(imp_med):
        ci_lo, ci_hi = bootstrap_ci(
            imp_med,
            stat_fn=lambda x: float(np.median(x)),
            n_iter=bootstrap_iter,
            seed=bootstrap_seed,
        )
        out["median_improvement_median_ci95_lo"] = ci_lo
        out["median_improvement_median_ci95_hi"] = ci_hi

        ci_lo, ci_hi = bootstrap_ci(
            imp_med,
            stat_fn=lambda x: float(np.mean(x > 0)),
            n_iter=bootstrap_iter,
            seed=bootstrap_seed + 1,
        )
        out["improved_fraction_median_ci95_lo"] = ci_lo
        out["improved_fraction_median_ci95_hi"] = ci_hi
    else:
        out["median_improvement_median_ci95_lo"] = np.nan
        out["median_improvement_median_ci95_hi"] = np.nan
        out["improved_fraction_median_ci95_lo"] = np.nan
        out["improved_fraction_median_ci95_hi"] = np.nan

    if len(imp_near):
        ci_lo, ci_hi = bootstrap_ci(
            imp_near,
            stat_fn=lambda x: float(np.median(x)),
            n_iter=bootstrap_iter,
            seed=bootstrap_seed + 2,
        )
        out["median_improvement_nearest_ci95_lo"] = ci_lo
        out["median_improvement_nearest_ci95_hi"] = ci_hi
    else:
        out["median_improvement_nearest_ci95_lo"] = np.nan
        out["median_improvement_nearest_ci95_hi"] = np.nan

    if len(imp_med):
        n_pos = int((imp_med > 0).sum())
        n_neg = int((imp_med < 0).sum())
        n_tie = int((imp_med == 0).sum())
        n_eff = n_pos + n_neg

        out["sign_test_n_pos"] = n_pos
        out["sign_test_n_neg"] = n_neg
        out["sign_test_n_tie"] = n_tie
        out["sign_test_n_effective"] = n_eff
        out["sign_test_p_greater"] = exact_binom_greater_p(n_pos, n_eff, p=0.5) if n_eff > 0 else np.nan
        out["sign_test_p_two_sided"] = exact_binom_two_sided_p(n_pos, n_eff, p=0.5) if n_eff > 0 else np.nan
    else:
        out["sign_test_n_pos"] = np.nan
        out["sign_test_n_neg"] = np.nan
        out["sign_test_n_tie"] = np.nan
        out["sign_test_n_effective"] = np.nan
        out["sign_test_p_greater"] = np.nan
        out["sign_test_p_two_sided"] = np.nan

    paired = df[["pre_median", "post_median"]].apply(pd.to_numeric, errors="coerce").dropna()
    if wilcoxon is not None and len(paired) >= 3:
        try:
            stat, pval = wilcoxon(
                paired["pre_median"].to_numpy(dtype=float),
                paired["post_median"].to_numpy(dtype=float),
                alternative="greater",
                zero_method="wilcox",
            )
            out["wilcoxon_pre_gt_post_stat"] = float(stat)
            out["wilcoxon_pre_gt_post_p"] = float(pval)
        except Exception:
            out["wilcoxon_pre_gt_post_stat"] = np.nan
            out["wilcoxon_pre_gt_post_p"] = np.nan
    else:
        out["wilcoxon_pre_gt_post_stat"] = np.nan
        out["wilcoxon_pre_gt_post_p"] = np.nan

    return out


def context_summary(
    df: pd.DataFrame,
    bootstrap_iter: int,
    bootstrap_seed: int,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []

    group_specs = [
        ("overall", None),
        ("prev_level1_label", "prev_level1_label"),
        ("post_level1_label", "post_level1_label"),
        ("primary_level1_label", "primary_level1_label"),
        ("context_pair", "context_pair"),
        ("same_phase_context", "same_phase_context"),
    ]

    for wname, wdf in df.groupby("window_name", sort=False):
        for grouping_type, col in group_specs:
            if col is None:
                stats = summarize_stats(wdf, bootstrap_iter, bootstrap_seed)
                rows.append({
                    "window_name": wname,
                    "grouping_type": grouping_type,
                    "group_value": "ALL",
                    **stats,
                })
                continue

            work = wdf.copy()
            work[col] = work[col].fillna("NA").astype(str)
            for group_value, sdf in work.groupby(col, sort=True):
                stats = summarize_stats(sdf, bootstrap_iter, bootstrap_seed)
                rows.append({
                    "window_name": wname,
                    "grouping_type": grouping_type,
                    "group_value": group_value,
                    **stats,
                })

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    for p in [args.score_csv, args.segments_csv]:
        if not p.exists():
            raise FileNotFoundError(f"Input not found: {p}")

    for p in [args.out_event_csv, args.out_overall_csv, args.out_context_csv]:
        if p.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {p}. Use --overwrite to replace it.")

    window_specs = parse_window_specs(args.window_spec)

    scores = pd.read_csv(args.score_csv)
    segments = pd.read_csv(args.segments_csv)

    required_score_cols = [args.case_col, args.time_col, args.score_col]
    missing_score = [c for c in required_score_cols if c not in scores.columns]
    if missing_score:
        raise ValueError(f"Missing score columns: {missing_score}")

    required_seg_cols = [args.case_col, "oob_start_sec", "oob_end_sec"]
    missing_seg = [c for c in required_seg_cols if c not in segments.columns]
    if missing_seg:
        raise ValueError(f"Missing segment columns: {missing_seg}")

    scores[args.time_col] = pd.to_numeric(scores[args.time_col], errors="coerce")
    scores[args.score_col] = pd.to_numeric(scores[args.score_col], errors="coerce")
    segments["oob_start_sec"] = pd.to_numeric(segments["oob_start_sec"], errors="coerce")
    segments["oob_end_sec"] = pd.to_numeric(segments["oob_end_sec"], errors="coerce")

    all_event_dfs: List[pd.DataFrame] = []
    overall_rows: List[Dict[str, object]] = []

    for pre_w, post_w, pre_gap, post_gap in window_specs:
        edf = compute_event_delta_for_window(
            scores=scores,
            segments=segments,
            case_col=args.case_col,
            time_col=args.time_col,
            score_col=args.score_col,
            pre_window_sec=pre_w,
            post_window_sec=post_w,
            pre_gap_sec=pre_gap,
            post_gap_sec=post_gap,
        )
        all_event_dfs.append(edf)

        stats = summarize_stats(edf, args.bootstrap_iter, args.bootstrap_seed)
        overall_rows.append({
            "window_name": window_name(pre_w, post_w, pre_gap, post_gap),
            "pre_window_sec": pre_w,
            "post_window_sec": post_w,
            "pre_gap_sec": pre_gap,
            "post_gap_sec": post_gap,
            **stats,
        })

    event_df = pd.concat(all_event_dfs, ignore_index=True)
    overall_df = pd.DataFrame(overall_rows)
    context_df = context_summary(event_df, args.bootstrap_iter, args.bootstrap_seed)

    ensure_parent(args.out_event_csv)
    ensure_parent(args.out_overall_csv)
    ensure_parent(args.out_context_csv)

    event_df.to_csv(args.out_event_csv, index=False, encoding="utf-8-sig")
    overall_df.to_csv(args.out_overall_csv, index=False, encoding="utf-8-sig")
    context_df.to_csv(args.out_context_csv, index=False, encoding="utf-8-sig")

    print("[OK] OOB responsiveness stats and sensitivity analysis complete")
    print(f"[INFO] event_csv={args.out_event_csv}")
    print(f"[INFO] overall_csv={args.out_overall_csv}")
    print(f"[INFO] context_csv={args.out_context_csv}")
    print()
    print("[INFO] Overall summary")
    print(overall_df.to_string(index=False))


if __name__ == "__main__":
    main()