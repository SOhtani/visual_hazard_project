#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compute rule-based color field phenotype metrics on purpose-specific analyzable frames.

This script is designed for the visual_hazard_project workflow after Phase 07.
It computes conservative, interpretable color features for blood-like redness and
blackness/anthracosis-like dark field candidates. These are NOT diagnostic labels.
They are image-derived field phenotype candidates.

Typical input:
  data/annotations/color_phenotype_analyzable_frames_v1.csv

Typical output:
  data/derived/field_phenotypes/per_frame/color_field_phenotypes_v1.csv
  reports/color_field_phenotypes/color_field_phenotype_global_thresholds.csv
  reports/color_field_phenotypes/case_color_field_phenotype_summary.csv
  data/annotations/color_field_phenotype_review_frames.csv
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRAME_CSV = PROJECT_ROOT / "data" / "annotations" / "color_phenotype_analyzable_frames_v1.csv"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "derived" / "field_phenotypes" / "per_frame" / "color_field_phenotypes_v1.csv"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "color_field_phenotypes"
DEFAULT_REVIEW_CSV = PROJECT_ROOT / "data" / "annotations" / "color_field_phenotype_review_frames.csv"

IMAGE_PATH_CANDIDATES = [
    "image_path",
    "frame_path",
    "filepath",
    "file_path",
    "png_path",
    "jpg_path",
    "jpeg_path",
    "image_file",
    "frame_file",
    "frame_png",
    "frame_jpg",
    "image_rel_path",
    "frame_rel_path",
    "relative_image_path",
    "relative_frame_path",
    "path",
]
IMAGE_SOURCE_KEEP_CANDIDATES = IMAGE_PATH_CANDIDATES + [
    "roi_x0", "roi_y0", "roi_x1", "roi_y1",
    "x0", "y0", "x1", "y1",
    "crop_x0", "crop_y0", "crop_x1", "crop_y1",
    "roi_left", "roi_top", "roi_right", "roi_bottom",
]
CASE_COL_CANDIDATES = ["case_id", "case", "video_id"]
TIME_COL_CANDIDATES = ["sample_time_sec", "time_sec", "timestamp_sec", "t", "frame_time_sec", "t_sec", "sec", "seconds"]
FRAME_INDEX_COL_CANDIDATES = ["frame_index", "frame_idx", "frame_no", "frame_number", "sample_index", "idx"]

ROI_CANDIDATE_SETS = [
    ("roi_x0", "roi_y0", "roi_x1", "roi_y1"),
    ("x0", "y0", "x1", "y1"),
    ("crop_x0", "crop_y0", "crop_x1", "crop_y1"),
    ("roi_left", "roi_top", "roi_right", "roi_bottom"),
]

METRIC_COLS = [
    "red_dominance_ratio_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "blood_like_redness_ratio_v1",
    "center_weighted_blood_like_redness_v1",
    "red_excess_mean_v1",
    "red_saturation_mean_v1",
    "blackness_candidate_ratio_v2",
    "corrected_blackness_candidate_ratio_v2",
    "anthracosis_like_blackness_candidate_v2",
    "center_weighted_blackness_candidate_v2",
]

SUMMARY_METRICS = [
    "blood_like_redness_ratio_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "center_weighted_blood_like_redness_v1",
    "blackness_candidate_ratio_v2",
    "corrected_blackness_candidate_ratio_v2",
    "anthracosis_like_blackness_candidate_v2",
]

REVIEW_METRICS = [
    "blood_like_redness_ratio_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "anthracosis_like_blackness_candidate_v2",
    "corrected_blackness_candidate_ratio_v2",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute rule-based blood-like redness and blackness field phenotype metrics."
    )
    parser.add_argument("--frame-csv", type=Path, default=DEFAULT_FRAME_CSV)
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory of per-frame metric CSV files. Used to attach image_path/ROI columns "
            "when the input analyzable-frame manifest contains only case/time/flag columns."
        ),
    )
    parser.add_argument(
        "--metrics-csv",
        nargs="*",
        type=Path,
        default=None,
        help="Optional explicit per-frame metric CSV file(s) to use as an image-path lookup.",
    )
    parser.add_argument(
        "--image-col",
        default=None,
        help="Optional explicit image path column name after merge.",
    )
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument(
        "--case",
        nargs="*",
        default=None,
        help="Optional case_id filter(s), e.g. --case CASE003 CASE010",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional global frame limit for smoke tests.",
    )
    parser.add_argument(
        "--max-frames-per-case",
        type=int,
        default=None,
        help="Optional per-case frame limit for smoke tests.",
    )
    parser.add_argument(
        "--fixed-roi",
        nargs=4,
        type=int,
        metavar=("X0", "Y0", "X1", "Y1"),
        default=None,
        help="Optional fixed ROI if ROI columns are absent.",
    )
    parser.add_argument(
        "--n-review",
        type=int,
        default=12,
        help="Frames per metric/selection for review CSV. Default: 12.",
    )
    parser.add_argument(
        "--write-review-csv",
        action="store_true",
        help="Write review frame CSV for montage export.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If output CSV exists, reuse it for thresholds/summaries instead of recomputing.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def find_first_col(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    lower_map = {str(c).lower(): str(c) for c in columns}
    for cand in candidates:
        if cand in columns:
            return cand
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def find_roi_cols(columns: Sequence[str]) -> Optional[Tuple[str, str, str, str]]:
    lower_map = {str(c).lower(): str(c) for c in columns}
    for cand_set in ROI_CANDIDATE_SETS:
        resolved: List[str] = []
        ok = True
        for c in cand_set:
            if c in columns:
                resolved.append(c)
            elif c.lower() in lower_map:
                resolved.append(lower_map[c.lower()])
            else:
                ok = False
                break
        if ok:
            return tuple(resolved)  # type: ignore[return-value]
    return None


def resolve_path(value: object, base_dirs: Sequence[Path]) -> Optional[Path]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    p = Path(text)
    if p.is_absolute() and p.exists():
        return p
    for base in base_dirs:
        cand = base / p
        if cand.exists():
            return cand
    if p.exists():
        return p
    return None


def clamp_roi(roi: Tuple[int, int, int, int], w: int, h: int) -> Optional[Tuple[int, int, int, int]]:
    x0, y0, x1, y1 = [int(v) for v in roi]
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def row_roi(row: pd.Series, roi_cols: Optional[Tuple[str, str, str, str]], fixed_roi: Optional[Tuple[int, int, int, int]], w: int, h: int) -> Tuple[int, int, int, int]:
    if fixed_roi is not None:
        roi = clamp_roi(fixed_roi, w=w, h=h)
        if roi is not None:
            return roi
    if roi_cols is not None:
        vals: List[int] = []
        ok = True
        for c in roi_cols:
            v = pd.to_numeric(pd.Series([row.get(c)]), errors="coerce").iloc[0]
            if not np.isfinite(v):
                ok = False
                break
            vals.append(int(round(float(v))))
        if ok:
            roi = clamp_roi((vals[0], vals[1], vals[2], vals[3]), w=w, h=h)
            if roi is not None:
                return roi
    return (0, 0, w, h)


def make_center_weight(h: int, w: int, sigma: float = 0.45) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    nx = (xx - cx) / max(cx, 1.0)
    ny = (yy - cy) / max(cy, 1.0)
    rr2 = nx * nx + ny * ny
    weight = np.exp(-rr2 / (2.0 * sigma * sigma)).astype(np.float32)
    m = float(weight.mean())
    if m > 0:
        weight /= m
    return weight


def safe_ratio(mask: np.ndarray, valid: Optional[np.ndarray] = None) -> float:
    if valid is None:
        denom = mask.size
        if denom == 0:
            return float("nan")
        return float(np.asarray(mask, dtype=bool).mean())
    valid_b = np.asarray(valid, dtype=bool)
    denom = int(valid_b.sum())
    if denom == 0:
        return float("nan")
    return float(np.asarray(mask, dtype=bool)[valid_b].mean())


def weighted_ratio(mask: np.ndarray, weight: np.ndarray, valid: Optional[np.ndarray] = None) -> float:
    m = np.asarray(mask, dtype=bool)
    w = np.asarray(weight, dtype=np.float32)
    if valid is not None:
        v = np.asarray(valid, dtype=bool)
        denom = float(w[v].sum())
        if denom <= 0:
            return float("nan")
        return float(w[v & m].sum() / denom)
    denom = float(w.sum())
    if denom <= 0:
        return float("nan")
    return float(w[m].sum() / denom)


def score_rgb_roi(rgb: np.ndarray) -> Dict[str, float]:
    """Compute conservative color phenotype metrics for an RGB ROI."""
    if rgb.size == 0:
        return {c: float("nan") for c in METRIC_COLS}

    rgb_f = rgb.astype(np.float32) / 255.0
    r = rgb_f[..., 0]
    g = rgb_f[..., 1]
    b = rgb_f[..., 2]
    max_gb = np.maximum(g, b)

    hsv = cv2.cvtColor(rgb_f, cv2.COLOR_RGB2HSV).astype(np.float32)
    h = hsv[..., 0]  # 0-360 for float OpenCV
    s = hsv[..., 1]
    v = hsv[..., 2]

    # Ignore near-black border and near-white saturated blanks for mean color phenotype denominators.
    valid_color = (v > 0.05) & (v < 0.98) & np.isfinite(v) & np.isfinite(s)

    red_hue = (h <= 28.0) | (h >= 335.0)
    orange_brown_hue = (h > 8.0) & (h <= 45.0)
    red_excess = np.maximum(r - max_gb, 0.0)

    red_dominance = red_hue & (s >= 0.22) & (v >= 0.08) & (red_excess >= 0.035)
    fresh_red = red_hue & (s >= 0.38) & (v >= 0.22) & (red_excess >= 0.07)
    dark_red_brown = ((red_hue | orange_brown_hue) & (s >= 0.28) & (v >= 0.06) & (v <= 0.55) & (r >= g + 0.025) & (r >= b + 0.025))
    blood_like = red_dominance | fresh_red | dark_red_brown

    blackness = (v <= 0.14)
    # Illumination-corrected dark candidate: local-ish threshold based on ROI value distribution.
    v_valid = v[np.isfinite(v)]
    if v_valid.size:
        v_med = float(np.median(v_valid))
        corrected_dark_thr = max(0.07, min(0.22, 0.45 * v_med))
    else:
        corrected_dark_thr = 0.14
    corrected_black = v <= corrected_dark_thr

    # Exploratory: dark, not highly saturated red. Without tissue/lung mask this is generic dark-field candidate.
    anthracosis_like = corrected_black & (s <= 0.62) & ~(fresh_red | dark_red_brown)

    center_w = make_center_weight(h=rgb.shape[0], w=rgb.shape[1])

    rows: Dict[str, float] = {
        "red_dominance_ratio_v1": safe_ratio(red_dominance, valid_color),
        "fresh_red_candidate_ratio_v1": safe_ratio(fresh_red, valid_color),
        "dark_red_brown_candidate_ratio_v1": safe_ratio(dark_red_brown, valid_color),
        "blood_like_redness_ratio_v1": safe_ratio(blood_like, valid_color),
        "center_weighted_blood_like_redness_v1": weighted_ratio(blood_like, center_w, valid_color),
        "red_excess_mean_v1": float(np.nanmean(red_excess[valid_color])) if int(valid_color.sum()) else float("nan"),
        "red_saturation_mean_v1": float(np.nanmean(s[red_dominance & valid_color])) if int((red_dominance & valid_color).sum()) else 0.0,
        "blackness_candidate_ratio_v2": safe_ratio(blackness),
        "corrected_blackness_candidate_ratio_v2": safe_ratio(corrected_black),
        "anthracosis_like_blackness_candidate_v2": safe_ratio(anthracosis_like),
        "center_weighted_blackness_candidate_v2": weighted_ratio(anthracosis_like, center_w),
    }
    return rows


def choose_key_cols(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    case_col = find_first_col(df.columns, CASE_COL_CANDIDATES)
    time_col = find_first_col(df.columns, TIME_COL_CANDIDATES)
    index_col = find_first_col(df.columns, FRAME_INDEX_COL_CANDIDATES)
    return case_col, time_col, index_col


def make_merge_key(df: pd.DataFrame, case_col: str, time_col: Optional[str], index_col: Optional[str]) -> pd.Series:
    case_part = df[case_col].astype(str)
    if time_col is not None and time_col in df.columns:
        t = pd.to_numeric(df[time_col], errors="coerce").round(3)
        return case_part + "__t__" + t.astype("string").fillna("NA")
    if index_col is not None and index_col in df.columns:
        idx = pd.to_numeric(df[index_col], errors="coerce").round(0).astype("Int64").astype("string")
        return case_part + "__i__" + idx.fillna("NA")
    raise ValueError("Could not construct merge key: need a time or frame-index column.")


def list_metric_csvs(args: argparse.Namespace) -> List[Path]:
    files: List[Path] = []
    if args.metrics_csv:
        files.extend([Path(p) for p in args.metrics_csv])
    if args.metrics_dir is not None:
        root = Path(args.metrics_dir)
        if root.exists():
            files.extend(sorted(root.glob("*.csv")))
            files.extend(sorted(root.glob("*.csv.gz")))
    # stable unique order
    seen = set()
    out: List[Path] = []
    for f in files:
        key = str(f.resolve()) if f.exists() else str(f)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def attach_image_metadata_from_metrics(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    """Attach image path / ROI columns to an analyzable-frame manifest.

    Phase-07 analyzable manifests are intentionally lean and may not contain a
    per-frame image path. The original per-frame metric CSVs usually retain the
    path and ROI columns used by review-sheet exporters. This function joins
    those columns back by case_id + time_sec or case_id + frame_index.
    """
    explicit_col = args.image_col
    if explicit_col and explicit_col in df.columns:
        return df
    if find_first_col(df.columns, IMAGE_PATH_CANDIDATES) is not None:
        return df

    metric_files = list_metric_csvs(args)
    if not metric_files:
        raise ValueError(
            "Could not find an image path column in the input frame CSV, and no --metrics-dir/--metrics-csv "
            "was supplied. Re-run with --metrics-dir .\\data\\derived\\quality_metrics\\per_frame "
            "or provide explicit per-frame metric CSVs with --metrics-csv."
        )

    frame_case_col, frame_time_col, frame_index_col = choose_key_cols(df)
    if frame_case_col is None:
        raise ValueError("Input frame CSV has no case column; cannot merge image paths from metrics.")
    df = df.copy()
    df["__merge_key"] = make_merge_key(df, frame_case_col, frame_time_col, frame_index_col)
    wanted_keys = set(df["__merge_key"].astype(str))

    lookup_parts: List[pd.DataFrame] = []
    loaded_files = 0
    for path in metric_files:
        if not path.exists():
            continue
        try:
            m = pd.read_csv(path, low_memory=False)
        except Exception:
            continue
        m_case_col, m_time_col, m_index_col = choose_key_cols(m)
        if m_case_col is None:
            # Some per-case files encode case_id only in the filename.
            stem = path.name
            case_guess = None
            for token in stem.replace("-", "_").split("_"):
                if token.upper().startswith("CASE"):
                    case_guess = token.upper().split(".")[0]
                    break
            if case_guess is None:
                continue
            m = m.copy()
            m[frame_case_col] = case_guess
            m_case_col = frame_case_col
        image_col = explicit_col if explicit_col in m.columns else find_first_col(m.columns, IMAGE_PATH_CANDIDATES)
        if image_col is None:
            continue
        try:
            m["__merge_key"] = make_merge_key(m, m_case_col, m_time_col, m_index_col)
        except Exception:
            continue
        m = m[m["__merge_key"].astype(str).isin(wanted_keys)].copy()
        if m.empty:
            continue
        keep_cols = ["__merge_key"]
        for c in IMAGE_SOURCE_KEEP_CANDIDATES:
            if c in m.columns and c not in keep_cols:
                keep_cols.append(c)
        if image_col not in keep_cols:
            keep_cols.append(image_col)
        part = m[keep_cols].copy()
        if image_col != "image_path" and "image_path" not in part.columns:
            part = part.rename(columns={image_col: "image_path"})
        lookup_parts.append(part)
        loaded_files += 1

    if not lookup_parts:
        raise ValueError(
            "Could not attach image paths from metrics files. Check that the metric CSVs contain "
            "case/time keys and an image path column. Quick check: "
            "python -c \"import pandas as pd, glob; p=glob.glob(r'.\\data\\derived\\quality_metrics\\per_frame\\*.csv')[0]; "
            "df=pd.read_csv(p,nrows=1); print(p); print(df.columns.tolist())\""
        )

    lookup = pd.concat(lookup_parts, ignore_index=True)
    lookup = lookup.drop_duplicates("__merge_key", keep="first")
    merged = df.merge(lookup, on="__merge_key", how="left", suffixes=("", "_from_metrics"))
    matched = int(merged["image_path"].notna().sum()) if "image_path" in merged.columns else 0
    if matched == 0:
        raise ValueError("Image-path merge produced zero matches. Check time/frame key columns in the input and metrics CSVs.")
    return merged.drop(columns=["__merge_key"], errors="ignore")

def apply_filters(df: pd.DataFrame, args: argparse.Namespace, case_col: Optional[str]) -> pd.DataFrame:
    out = df.copy()
    if args.case and case_col is not None:
        keep = set(str(x) for x in args.case)
        out = out[out[case_col].astype(str).isin(keep)].copy()
    if args.max_frames_per_case is not None and case_col is not None:
        out = out.groupby(case_col, sort=False, group_keys=False).head(int(args.max_frames_per_case)).copy()
    if args.max_frames is not None:
        out = out.head(int(args.max_frames)).copy()
    return out.reset_index(drop=True)


def process_frames(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    image_col = args.image_col if args.image_col in df.columns else find_first_col(df.columns, IMAGE_PATH_CANDIDATES)
    if image_col is None:
        raise ValueError(
            "Could not find an image path column after optional metrics merge. Expected one of: " + ", ".join(IMAGE_PATH_CANDIDATES)
        )
    roi_cols = find_roi_cols(df.columns)
    fixed_roi = tuple(args.fixed_roi) if args.fixed_roi is not None else None
    base_dirs = [PROJECT_ROOT, Path.cwd()]

    rows: List[Dict[str, object]] = []
    n = len(df)
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        base = row.to_dict()
        path = resolve_path(row.get(image_col), base_dirs=base_dirs)
        if "image_path" not in base:
            base["image_path"] = row.get(image_col)
        base["color_metric_image_path_resolved"] = str(path) if path is not None else ""
        base["color_metric_status"] = "ok"
        base["color_metric_error"] = ""
        if path is None:
            base.update({c: float("nan") for c in METRIC_COLS})
            base["color_metric_status"] = "missing_image_path"
            rows.append(base)
            continue
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            base.update({c: float("nan") for c in METRIC_COLS})
            base["color_metric_status"] = "read_error"
            rows.append(base)
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        x0, y0, x1, y1 = row_roi(row=row, roi_cols=roi_cols, fixed_roi=fixed_roi, w=w, h=h)
        roi_rgb = rgb[y0:y1, x0:x1]
        base["color_metric_roi_x0"] = x0
        base["color_metric_roi_y0"] = y0
        base["color_metric_roi_x1"] = x1
        base["color_metric_roi_y1"] = y1
        try:
            base.update(score_rgb_roi(roi_rgb))
        except Exception as exc:  # keep long batch running
            base.update({c: float("nan") for c in METRIC_COLS})
            base["color_metric_status"] = "score_error"
            base["color_metric_error"] = repr(exc)
        rows.append(base)
        if i % 10000 == 0:
            log(f"[INFO] scored {i}/{n} frames", quiet=args.quiet)
    return pd.DataFrame(rows)


def quantile_table(df: pd.DataFrame, metrics: Sequence[str]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for col in metrics:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        ok = s[np.isfinite(s)]
        for name, q in [("p50", 0.50), ("p75", 0.75), ("p90", 0.90), ("p95", 0.95), ("p99", 0.99)]:
            rows.append({
                "metric": col,
                "threshold_name": name,
                "quantile": q,
                "threshold_value": float(ok.quantile(q)) if len(ok) else float("nan"),
                "n_evaluable": int(len(ok)),
            })
    return pd.DataFrame(rows)


def summarize_group(df: pd.DataFrame, group_cols: Sequence[str], metrics: Sequence[str], thresholds: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in group_cols if c in df.columns]
    if not cols:
        return pd.DataFrame()
    rows: List[Dict[str, object]] = []
    grouped = df.groupby(cols, sort=True, dropna=False)
    p95_map = thresholds[thresholds["threshold_name"].eq("p95")].set_index("metric")["threshold_value"].to_dict()
    p99_map = thresholds[thresholds["threshold_name"].eq("p99")].set_index("metric")["threshold_value"].to_dict()
    for key, g in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        base = {col: val for col, val in zip(cols, key)}
        base["n_frames"] = int(len(g))
        for metric in metrics:
            if metric not in g.columns:
                continue
            s = pd.to_numeric(g[metric], errors="coerce")
            ok = s[np.isfinite(s)]
            prefix = metric
            base[f"{prefix}__n"] = int(len(ok))
            base[f"{prefix}__mean"] = float(ok.mean()) if len(ok) else float("nan")
            base[f"{prefix}__median"] = float(ok.median()) if len(ok) else float("nan")
            base[f"{prefix}__p90"] = float(ok.quantile(0.90)) if len(ok) else float("nan")
            base[f"{prefix}__p95"] = float(ok.quantile(0.95)) if len(ok) else float("nan")
            p95 = p95_map.get(metric, float("nan"))
            p99 = p99_map.get(metric, float("nan"))
            base[f"{prefix}__frac_ge_global_p95"] = float((ok >= p95).mean()) if len(ok) and np.isfinite(p95) else float("nan")
            base[f"{prefix}__frac_ge_global_p99"] = float((ok >= p99).mean()) if len(ok) and np.isfinite(p99) else float("nan")
        rows.append(base)
    return pd.DataFrame(rows)


def build_review_rows(df: pd.DataFrame, metrics: Sequence[str], thresholds: pd.DataFrame, n_review: int) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    review_id = 1
    thr_lookup = thresholds.set_index(["metric", "threshold_name"])["threshold_value"].to_dict()
    for metric in metrics:
        if metric not in df.columns:
            continue
        work = df.copy()
        work[metric] = pd.to_numeric(work[metric], errors="coerce")
        work = work[np.isfinite(work[metric])].copy()
        if work.empty:
            continue
        selections: List[Tuple[str, pd.DataFrame]] = []
        selections.append(("top_highest", work.sort_values(metric, ascending=False).head(n_review)))
        selections.append(("bottom_lowest", work.sort_values(metric, ascending=True).head(n_review)))
        for tname in ["p95", "p99"]:
            cutoff = float(thr_lookup.get((metric, tname), float("nan")))
            if not np.isfinite(cutoff):
                continue
            above = work[work[metric] >= cutoff].copy()
            below = work[work[metric] < cutoff].copy()
            above["_dist"] = (above[metric] - cutoff).abs()
            below["_dist"] = (below[metric] - cutoff).abs()
            selections.append((f"just_above_{tname}", above.sort_values("_dist", ascending=True).head(n_review)))
            selections.append((f"just_below_{tname}", below.sort_values("_dist", ascending=True).head(n_review)))
        for sel_name, part in selections:
            for _, row in part.iterrows():
                d = row.to_dict()
                d["review_id"] = f"CFP_{review_id:05d}"
                d["target_component"] = metric.replace("_v1", "").replace("_v2", "")
                d["selection_type"] = sel_name
                d["score_col"] = metric
                d["score_value"] = row.get(metric)
                rows.append(d)
                review_id += 1
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    ensure_parent(args.output_csv)
    ensure_dir(args.report_dir)
    ensure_parent(args.review_csv)

    if args.skip_existing and args.output_csv.exists():
        out_df = pd.read_csv(args.output_csv, low_memory=False)
        log(f"[OK] loaded existing output rows={len(out_df)} cols={len(out_df.columns)}", quiet=args.quiet)
    else:
        if not args.frame_csv.exists():
            raise FileNotFoundError(f"Frame CSV not found: {args.frame_csv}")
        df = pd.read_csv(args.frame_csv, low_memory=False)
        df = attach_image_metadata_from_metrics(df, args=args)
        case_col = find_first_col(df.columns, CASE_COL_CANDIDATES)
        filtered = apply_filters(df, args=args, case_col=case_col)
        log(f"[OK] loaded frame CSV rows={len(df)} cols={len(df.columns)}", quiet=args.quiet)
        log(f"[OK] filtered rows={len(filtered)}", quiet=args.quiet)
        out_df = process_frames(filtered, args=args)
        out_df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")
        log(f"[OK] wrote {args.output_csv} rows={len(out_df)}", quiet=args.quiet)

    thresholds = quantile_table(out_df[out_df.get("color_metric_status", "ok").eq("ok") if "color_metric_status" in out_df.columns else slice(None)], SUMMARY_METRICS)
    thresholds_path = args.report_dir / "color_field_phenotype_global_thresholds.csv"
    thresholds.to_csv(thresholds_path, index=False, encoding="utf-8-sig")
    log(f"[OK] wrote {thresholds_path} rows={len(thresholds)}", quiet=args.quiet)

    case_col = find_first_col(out_df.columns, CASE_COL_CANDIDATES)
    time_col = find_first_col(out_df.columns, TIME_COL_CANDIDATES)
    group_cols = [c for c in [case_col] if c is not None]
    case_summary = summarize_group(out_df, group_cols=group_cols, metrics=SUMMARY_METRICS, thresholds=thresholds)
    case_summary_path = args.report_dir / "case_color_field_phenotype_summary.csv"
    case_summary.to_csv(case_summary_path, index=False, encoding="utf-8-sig")
    log(f"[OK] wrote {case_summary_path} rows={len(case_summary)}", quiet=args.quiet)

    # Optional phase summary if a phase column exists in the input.
    phase_col = find_first_col(out_df.columns, ["level1_phase", "phase", "workflow_label", "level1", "basic_phase"])
    phase_summary = pd.DataFrame()
    if phase_col is not None:
        phase_group_cols = [c for c in [case_col, phase_col] if c is not None]
        phase_summary = summarize_group(out_df, group_cols=phase_group_cols, metrics=SUMMARY_METRICS, thresholds=thresholds)
    phase_summary_path = args.report_dir / "case_phase_color_field_phenotype_summary.csv"
    phase_summary.to_csv(phase_summary_path, index=False, encoding="utf-8-sig")
    log(f"[OK] wrote {phase_summary_path} rows={len(phase_summary)}", quiet=args.quiet)

    status_rows = []
    if "color_metric_status" in out_df.columns:
        for status, n in out_df["color_metric_status"].value_counts(dropna=False).items():
            status_rows.append({"color_metric_status": status, "n_frames": int(n), "frac_frames": float(n / len(out_df)) if len(out_df) else float("nan")})
    status_df = pd.DataFrame(status_rows)
    status_path = args.report_dir / "color_field_phenotype_status_summary.csv"
    status_df.to_csv(status_path, index=False, encoding="utf-8-sig")
    log(f"[OK] wrote {status_path} rows={len(status_df)}", quiet=args.quiet)

    if args.write_review_csv:
        review_df = build_review_rows(out_df, metrics=REVIEW_METRICS, thresholds=thresholds, n_review=int(args.n_review))
        review_df.to_csv(args.review_csv, index=False, encoding="utf-8-sig")
        review_report_path = args.report_dir / "color_field_phenotype_review_frames.csv"
        review_df.to_csv(review_report_path, index=False, encoding="utf-8-sig")
        log(f"[OK] wrote {args.review_csv} rows={len(review_df)}", quiet=args.quiet)
        log(f"[OK] wrote {review_report_path} rows={len(review_df)}", quiet=args.quiet)

    log("[OK] color field phenotype metrics complete", quiet=args.quiet)


if __name__ == "__main__":
    main()
