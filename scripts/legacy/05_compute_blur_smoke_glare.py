#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame_manual_roi"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
SUMMARY_CSV_NAME = "_frame_score_summary.csv"

SPECULAR_V_THR = 0.90
SPECULAR_S_THR = 0.30
SATURATION_V_THR = 0.98
SATURATION_RGB_THR = 0.98


@dataclass
class Config:
    per_frame_input_dir: Path
    per_frame_output_dir: Path
    fixed_roi: Optional[Tuple[int, int, int, int]]
    patch_size: int
    patch_stride: int
    focus_patch_size: int
    focus_patch_stride: int
    focus_coverage_thr: float
    illum_sigma: float
    reblur_sigma: float
    overwrite: bool
    case_filter: Optional[set[str]]
    limit_cases: Optional[int]
    quiet: bool


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute per-frame quality metrics with focus_badness_v1 as the main visibility metric."
    )
    parser.add_argument(
        "--per-frame-input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Input per-frame CSV directory. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--per-frame-output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output per-frame CSV directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--fixed-roi",
        nargs=4,
        type=int,
        metavar=("X0", "Y0", "X1", "Y1"),
        default=None,
        help="Override ROI for all frames.",
    )
    parser.add_argument(
        "--patch-size",
        type=int,
        default=24,
        help="Patch size for auxiliary local maps. Default: 24",
    )
    parser.add_argument(
        "--patch-stride",
        type=int,
        default=12,
        help="Patch stride for auxiliary local maps. Default: 12",
    )
    parser.add_argument(
        "--focus-patch-size",
        type=int,
        default=48,
        help="Patch size for focus_badness_v1. Default: 48",
    )
    parser.add_argument(
        "--focus-patch-stride",
        type=int,
        default=24,
        help="Patch stride for focus_badness_v1. Default: 24",
    )
    parser.add_argument(
        "--focus-coverage-thr",
        type=float,
        default=0.38,
        help="Patch focus threshold for visible coverage. Default: 0.38",
    )
    parser.add_argument(
        "--illum-sigma",
        type=float,
        default=31.0,
        help="Gaussian sigma for illumination estimation in auxiliary metrics. Default: 31",
    )
    parser.add_argument(
        "--reblur-sigma",
        type=float,
        default=1.2,
        help="Additional blur sigma for auxiliary blur metric. Default: 1.2",
    )
    parser.add_argument(
        "--case",
        nargs="*",
        default=None,
        help="Optional case_id filter(s), e.g. --case CASE003 CASE010",
    )
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=None,
        help="Optional limit on case CSV count.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output CSVs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce logging.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    fixed_roi = tuple(args.fixed_roi) if args.fixed_roi is not None else None
    case_filter = set(args.case) if args.case else None
    return Config(
        per_frame_input_dir=args.per_frame_input_dir,
        per_frame_output_dir=args.per_frame_output_dir,
        fixed_roi=fixed_roi,
        patch_size=int(args.patch_size),
        patch_stride=int(args.patch_stride),
        focus_patch_size=int(args.focus_patch_size),
        focus_patch_stride=int(args.focus_patch_stride),
        focus_coverage_thr=float(args.focus_coverage_thr),
        illum_sigma=float(args.illum_sigma),
        reblur_sigma=float(args.reblur_sigma),
        overwrite=bool(args.overwrite),
        case_filter=case_filter,
        limit_cases=args.limit_cases,
        quiet=bool(args.quiet),
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_case_csvs(input_dir: Path, case_filter: Optional[set[str]] = None) -> List[Path]:
    csvs = sorted(p for p in input_dir.glob("*.csv") if p.name != SUMMARY_CSV_NAME)
    if case_filter:
        out: List[Path] = []
        for p in csvs:
            case_id = p.stem.replace("_frame_scores", "")
            if case_id in case_filter:
                out.append(p)
        return out
    return csvs


def load_image_rgb(image_path: str) -> np.ndarray:
    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def clip_roi(x0: int, y0: int, x1: int, y1: int, w: int, h: int) -> Tuple[int, int, int, int]:
    x0 = max(0, min(int(x0), w - 1))
    y0 = max(0, min(int(y0), h - 1))
    x1 = max(x0 + 1, min(int(x1), w))
    y1 = max(y0 + 1, min(int(y1), h))
    return x0, y0, x1, y1


def parse_effective_roi(
    row: pd.Series,
    image_shape: Tuple[int, int, int],
    fixed_roi: Optional[Tuple[int, int, int, int]],
) -> Tuple[int, int, int, int]:
    h, w = image_shape[:2]
    if fixed_roi is not None:
        return clip_roi(*fixed_roi, w=w, h=h)

    x0 = int(float(row["roi_x0"]))
    y0 = int(float(row["roi_y0"]))
    x1 = int(float(row["roi_x1"]))
    y1 = int(float(row["roi_y1"]))
    return clip_roi(x0, y0, x1, y1, w=w, h=h)


def rgb_to_gray_float(rgb_u8: np.ndarray) -> np.ndarray:
    rgb_f = rgb_u8.astype(np.float32) / 255.0
    return cv2.cvtColor(rgb_f, cv2.COLOR_RGB2GRAY).astype(np.float32)


def rgb_to_hsv_float(rgb_u8: np.ndarray) -> np.ndarray:
    rgb_f = rgb_u8.astype(np.float32) / 255.0
    return cv2.cvtColor(rgb_f, cv2.COLOR_RGB2HSV).astype(np.float32)


def gaussian_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return img.copy()
    return cv2.GaussianBlur(
        img,
        ksize=(0, 0),
        sigmaX=float(sigma),
        sigmaY=float(sigma),
        borderType=cv2.BORDER_REFLECT101,
    )


def box_mean(img: np.ndarray, k: int) -> np.ndarray:
    return cv2.boxFilter(
        img,
        ddepth=-1,
        ksize=(int(k), int(k)),
        normalize=True,
        borderType=cv2.BORDER_REFLECT101,
    )


def robust_minmax_normalize(arr: np.ndarray, q_low: float = 0.05, q_high: float = 0.95) -> np.ndarray:
    x = np.asarray(arr, dtype=np.float32)
    valid = np.isfinite(x)
    out = np.zeros_like(x, dtype=np.float32)
    if valid.sum() == 0:
        return out
    xv = x[valid]
    lo = float(np.quantile(xv, q_low))
    hi = float(np.quantile(xv, q_high))
    if hi <= lo + 1e-12:
        out[valid] = 0.0
        return out
    out[valid] = np.clip((xv - lo) / (hi - lo), 0.0, 1.0)
    return out


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    valid = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if valid.sum() == 0:
        return float("nan")
    vv = v[valid]
    ww = w[valid]
    return float(np.sum(vv * ww) / np.sum(ww))


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    v = np.asarray(values, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    valid = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if valid.sum() == 0:
        return float("nan")
    vv = v[valid]
    ww = w[valid]
    order = np.argsort(vv)
    vv = vv[order]
    ww = ww[order]
    cdf = np.cumsum(ww)
    cutoff = float(q) * float(cdf[-1])
    idx = int(np.searchsorted(cdf, cutoff, side="left"))
    idx = max(0, min(idx, len(vv) - 1))
    return float(vv[idx])


def connected_component_metrics(binary_u8: np.ndarray) -> Dict[str, float]:
    grid = np.asarray(binary_u8, dtype=np.uint8)
    total = int(grid.size)
    if total == 0:
        return {
            "ratio": float("nan"),
            "max_component_ratio": float("nan"),
            "component_count": float("nan"),
        }

    ratio = float(grid.mean())
    if grid.max() == 0:
        return {
            "ratio": ratio,
            "max_component_ratio": 0.0,
            "component_count": 0.0,
        }

    num_labels, labels = cv2.connectedComponents(grid, connectivity=8)
    sizes: List[int] = []
    for lab in range(1, num_labels):
        sizes.append(int((labels == lab).sum()))

    if not sizes:
        return {
            "ratio": ratio,
            "max_component_ratio": 0.0,
            "component_count": 0.0,
        }

    return {
        "ratio": ratio,
        "max_component_ratio": float(max(sizes) / total),
        "component_count": float(len(sizes)),
    }


def make_center_weight(h: int, w: int, sigma: float = 0.45) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    nx = (xx - cx) / max(cx, 1.0)
    ny = (yy - cy) / max(cy, 1.0)
    rr2 = nx * nx + ny * ny
    weight = np.exp(-rr2 / (2.0 * sigma * sigma)).astype(np.float32)
    weight = weight / max(float(weight.mean()), 1e-6)
    return weight


def compute_illumination_corrected(gray: np.ndarray, illum_sigma: float) -> np.ndarray:
    eps = 1e-4
    log_gray = np.log(gray + eps)
    illum = gaussian_blur(log_gray, sigma=illum_sigma)
    reflect = log_gray - illum

    local_sigma = max(illum_sigma / 4.0, 3.0)
    mu = gaussian_blur(gray, sigma=local_sigma)
    sq = gaussian_blur(gray * gray, sigma=local_sigma)
    var = np.maximum(sq - mu * mu, 0.0)
    std = np.sqrt(var + eps)
    lcn = (gray - mu) / std

    mixed = 0.5 * reflect + 0.5 * lcn
    mixed = robust_minmax_normalize(mixed, q_low=0.02, q_high=0.98)
    return mixed.astype(np.float32)


def compute_auxiliary_local_maps(
    roi_rgb_u8: np.ndarray,
    patch_size: int,
    illum_sigma: float,
    reblur_sigma: float,
) -> Dict[str, np.ndarray]:
    gray = rgb_to_gray_float(roi_rgb_u8)
    hsv = rgb_to_hsv_float(roi_rgb_u8)

    v = hsv[..., 2]
    s = hsv[..., 1]

    rgb_f = roi_rgb_u8.astype(np.float32) / 255.0
    r = rgb_f[..., 0]
    g = rgb_f[..., 1]
    b = rgb_f[..., 2]

    illum_corr = compute_illumination_corrected(gray, illum_sigma=illum_sigma)

    gx_raw = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy_raw = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad_energy_raw = gx_raw * gx_raw + gy_raw * gy_raw

    mean_y = box_mean(gray, patch_size)
    mean_y_sq = box_mean(gray * gray, patch_size)
    var_y = np.maximum(mean_y_sq - mean_y * mean_y, 0.0)
    rms_contrast = np.sqrt(var_y, dtype=np.float32)

    reblur = gaussian_blur(illum_corr, sigma=reblur_sigma)
    reblur_absdiff = np.abs(illum_corr - reblur).astype(np.float32)
    reblur_response_local = box_mean(reblur_absdiff, patch_size)

    tenengrad_local = box_mean(grad_energy_raw, patch_size)

    specular_mask = ((v >= SPECULAR_V_THR) & (s <= SPECULAR_S_THR)).astype(np.float32)
    saturation_mask = (
        (v >= SATURATION_V_THR)
        | (r >= SATURATION_RGB_THR)
        | (g >= SATURATION_RGB_THR)
        | (b >= SATURATION_RGB_THR)
    ).astype(np.float32)

    specular_ratio_local = box_mean(specular_mask, patch_size)
    saturation_ratio_local = box_mean(saturation_mask, patch_size)

    return {
        "tenengrad_local": tenengrad_local.astype(np.float32),
        "rms_contrast_local": rms_contrast.astype(np.float32),
        "reblur_response_local": reblur_response_local.astype(np.float32),
        "specular_mask": specular_mask.astype(np.float32),
        "saturation_mask": saturation_mask.astype(np.float32),
        "specular_ratio_local": specular_ratio_local.astype(np.float32),
        "saturation_ratio_local": saturation_ratio_local.astype(np.float32),
    }


def summarize_auxiliary_metrics(local_maps: Dict[str, np.ndarray]) -> Dict[str, float]:
    tenengrad_local = local_maps["tenengrad_local"]
    rms_contrast_local = local_maps["rms_contrast_local"]
    reblur_response_local = local_maps["reblur_response_local"]
    specular_mask = local_maps["specular_mask"]
    saturation_mask = local_maps["saturation_mask"]

    ten_norm = robust_minmax_normalize(tenengrad_local)
    contrast_norm = robust_minmax_normalize(rms_contrast_local)
    reblur_norm = robust_minmax_normalize(reblur_response_local)

    blur_like_mean = float(np.clip(1.0 - np.mean(reblur_norm), 0.0, 1.0))
    blur_like_p90 = float(np.clip(1.0 - np.quantile(reblur_norm, 0.10), 0.0, 1.0))

    veil_local = np.clip(0.60 * (1.0 - contrast_norm) + 0.40 * (1.0 - ten_norm), 0.0, 1.0)
    veil_smoke_mean = float(np.mean(veil_local))
    veil_smoke_p90 = float(np.quantile(veil_local, 0.90))

    saturation_ratio = float(np.mean(saturation_mask))
    specular_ratio = float(np.mean(specular_mask))

    return {
        "blur_like_mean": blur_like_mean,
        "blur_like_p90": blur_like_p90,
        "veil_smoke_mean": veil_smoke_mean,
        "veil_smoke_p90": veil_smoke_p90,
        "saturation_ratio": saturation_ratio,
        "specular_ratio": specular_ratio,
    }


def calc_patch_entropy(gray_patch_u8: np.ndarray) -> float:
    hist = cv2.calcHist([gray_patch_u8], [0], None, [256], [0, 256]).ravel().astype(np.float64)
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    if len(p) == 0:
        return 0.0
    return float(-(p * np.log2(p)).sum())


def make_center_weight_for_patch(
    cx: float,
    cy: float,
    roi_w: int,
    roi_h: int,
    sigma: float = 0.45,
) -> float:
    roi_cx = (roi_w - 1) / 2.0
    roi_cy = (roi_h - 1) / 2.0
    nx = (cx - roi_cx) / max(roi_cx, 1.0)
    ny = (cy - roi_cy) / max(roi_cy, 1.0)
    rr2 = nx * nx + ny * ny
    return float(np.exp(-rr2 / (2.0 * sigma * sigma)))


def map_tenengrad_to_unit(x: float) -> float:
    return float(np.clip(np.log1p(x * 4000.0) / np.log1p(120.0), 0.0, 1.0))


def map_lapvar_to_unit(x: float) -> float:
    return float(np.clip(np.log1p(x * 50000.0) / np.log1p(200.0), 0.0, 1.0))


def map_entropy_to_unit(x: float) -> float:
    return float(np.clip((x - 2.0) / 4.5, 0.0, 1.0))


def compute_focus_badness_v1_for_roi(
    roi_rgb_u8: np.ndarray,
    patch_size: int,
    patch_stride: int,
    coverage_thr: float,
) -> Dict[str, float]:
    gray = rgb_to_gray_float(roi_rgb_u8)
    gray_u8 = np.clip(gray * 255.0, 0, 255).astype(np.uint8)

    h, w = gray.shape[:2]
    if h < patch_size or w < patch_size:
        patch_size = min(h, w)
        patch_stride = patch_size

    patch_scores: List[float] = []
    patch_weights: List[float] = []
    ten_vals: List[float] = []
    lap_vals: List[float] = []
    ent_vals: List[float] = []

    y_starts = list(range(0, max(h - patch_size + 1, 1), patch_stride))
    if len(y_starts) == 0 or y_starts[-1] != h - patch_size:
        y_starts.append(max(h - patch_size, 0))

    x_starts = list(range(0, max(w - patch_size + 1, 1), patch_stride))
    if len(x_starts) == 0 or x_starts[-1] != w - patch_size:
        x_starts.append(max(w - patch_size, 0))

    grid_rows = len(y_starts)
    grid_cols = len(x_starts)
    low_focus_grid = np.zeros((grid_rows, grid_cols), dtype=np.uint8)

    for gy_idx, y0 in enumerate(y_starts):
        for gx_idx, x0 in enumerate(x_starts):
            y1 = y0 + patch_size
            x1 = x0 + patch_size

            patch = gray[y0:y1, x0:x1]
            patch_u8 = gray_u8[y0:y1, x0:x1]

            gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
            tenengrad = float(np.mean(gx * gx + gy * gy))

            lap = cv2.Laplacian(patch, cv2.CV_32F, ksize=3)
            lap_var = float(np.var(lap))

            entropy = calc_patch_entropy(patch_u8)

            t_score = map_tenengrad_to_unit(tenengrad)
            l_score = map_lapvar_to_unit(lap_var)
            e_score = map_entropy_to_unit(entropy)

            patch_focus = float(0.45 * t_score + 0.30 * l_score + 0.25 * e_score)

            cx = x0 + (patch.shape[1] - 1) / 2.0
            cy = y0 + (patch.shape[0] - 1) / 2.0
            weight = make_center_weight_for_patch(cx=cx, cy=cy, roi_w=w, roi_h=h, sigma=0.45)

            patch_scores.append(patch_focus)
            patch_weights.append(weight)
            ten_vals.append(tenengrad)
            lap_vals.append(lap_var)
            ent_vals.append(entropy)

            if patch_focus < float(coverage_thr):
                low_focus_grid[gy_idx, gx_idx] = 1

    scores = np.asarray(patch_scores, dtype=np.float64)
    weights = np.asarray(patch_weights, dtype=np.float64)

    patch_focus_q90 = weighted_quantile(scores, weights, 0.90)
    patch_focus_mean = weighted_mean(scores, weights)
    focus_coverage = weighted_mean((scores >= float(coverage_thr)).astype(np.float64), weights)

    focus_badness_v1 = float(1.0 - np.clip(0.45 * patch_focus_q90 + 0.55 * focus_coverage, 0.0, 1.0))

    cc = connected_component_metrics(low_focus_grid)
    focus_lost_patch_ratio = cc["ratio"]
    focus_lost_max_component_ratio = cc["max_component_ratio"]
    focus_lost_component_count = cc["component_count"]

    center_weight_grid = make_center_weight(low_focus_grid.shape[0], low_focus_grid.shape[1], sigma=0.45)
    focus_lost_center_weighted_ratio = float(
        np.sum(low_focus_grid.astype(np.float32) * center_weight_grid) / np.sum(center_weight_grid)
    )

    return {
        "n_focus_patches": int(len(scores)),
        "patch_focus_mean": patch_focus_mean,
        "patch_focus_q90": patch_focus_q90,
        "focus_coverage": focus_coverage,
        "focus_badness_v1": focus_badness_v1,
        "focus_lost_patch_ratio": focus_lost_patch_ratio,
        "focus_lost_center_weighted_ratio": focus_lost_center_weighted_ratio,
        "focus_lost_max_component_ratio": focus_lost_max_component_ratio,
        "focus_lost_component_count": focus_lost_component_count,
        "tenengrad_patch_mean_raw": float(np.mean(ten_vals)) if ten_vals else float("nan"),
        "lapvar_patch_mean_raw": float(np.mean(lap_vals)) if lap_vals else float("nan"),
        "entropy_patch_mean_raw": float(np.mean(ent_vals)) if ent_vals else float("nan"),
    }


def process_one_row(row: pd.Series, config: Config) -> Dict[str, object]:
    out: Dict[str, object] = {}
    image_path = str(row["image_path"])
    out["image_path"] = image_path

    img_rgb = load_image_rgb(image_path)
    h, w = img_rgb.shape[:2]
    out["image_h"] = int(h)
    out["image_w"] = int(w)

    roi = parse_effective_roi(row, img_rgb.shape, config.fixed_roi)
    out["roi_x0"], out["roi_y0"], out["roi_x1"], out["roi_y1"] = roi

    if int(img_rgb.max()) == 0:
        out["metric_status"] = "all_zero_image"
        for c in [
            "blur_like_mean", "blur_like_p90",
            "veil_smoke_mean", "veil_smoke_p90",
            "saturation_ratio", "specular_ratio",
            "n_focus_patches", "patch_focus_mean", "patch_focus_q90", "focus_coverage",
            "focus_badness_v1",
            "focus_lost_patch_ratio", "focus_lost_center_weighted_ratio",
            "focus_lost_max_component_ratio", "focus_lost_component_count",
            "tenengrad_patch_mean_raw", "lapvar_patch_mean_raw", "entropy_patch_mean_raw",
            "local_obstruction_ratio", "local_obstruction_max_component_ratio", "local_obstruction_component_count",
            "composite_badness_v3", "composite_badness_v4",
            "blur_score", "smoke_fog_score", "exposure_score", "glare_score",
            "composite_degradation_score",
        ]:
            out[c] = float("nan")
        return out

    x0, y0, x1, y1 = roi
    roi_rgb = img_rgb[y0:y1, x0:x1]
    if roi_rgb.size == 0:
        out["metric_status"] = "empty_roi"
        return out

    aux_maps = compute_auxiliary_local_maps(
        roi_rgb_u8=roi_rgb,
        patch_size=config.patch_size,
        illum_sigma=config.illum_sigma,
        reblur_sigma=config.reblur_sigma,
    )
    aux_metrics = summarize_auxiliary_metrics(aux_maps)

    focus_metrics = compute_focus_badness_v1_for_roi(
        roi_rgb_u8=roi_rgb,
        patch_size=config.focus_patch_size,
        patch_stride=config.focus_patch_stride,
        coverage_thr=config.focus_coverage_thr,
    )

    out.update(aux_metrics)
    out.update(focus_metrics)

    out["local_obstruction_ratio"] = float(out["focus_lost_center_weighted_ratio"])
    out["local_obstruction_max_component_ratio"] = float(out["focus_lost_max_component_ratio"])
    out["local_obstruction_component_count"] = float(out["focus_lost_component_count"])

    out["composite_badness_v4"] = float(out["focus_badness_v1"])
    out["composite_badness_v3"] = float(out["focus_badness_v1"])
    out["composite_degradation_score"] = float(out["focus_badness_v1"])

    out["blur_score"] = float(out["blur_like_mean"])
    out["smoke_fog_score"] = float(out["veil_smoke_mean"])
    out["exposure_score"] = float(out["saturation_ratio"])
    out["glare_score"] = float(out["specular_ratio"])

    out["metric_status"] = "ok"
    out["n_eval_pixels"] = int(roi_rgb.shape[0] * roi_rgb.shape[1])
    out["patch_size_used"] = int(config.patch_size)
    out["patch_stride_used"] = int(config.patch_stride)
    out["focus_patch_size_used"] = int(config.focus_patch_size)
    out["focus_patch_stride_used"] = int(config.focus_patch_stride)
    out["focus_coverage_thr_used"] = float(config.focus_coverage_thr)
    out["illum_sigma_used"] = float(config.illum_sigma)
    out["reblur_sigma_used"] = float(config.reblur_sigma)
    return out


def process_case_csv(input_csv: Path, output_csv: Path, config: Config) -> Dict[str, object]:
    case_id = input_csv.stem.replace("_frame_scores", "")

    if output_csv.exists() and not config.overwrite:
        return {
            "case_id": case_id,
            "input_csv": str(input_csv),
            "output_csv": str(output_csv),
            "status": "skipped_exists",
            "n_rows": float("nan"),
            "n_ok": float("nan"),
            "n_all_zero": float("nan"),
            "n_missing_image": float("nan"),
            "n_error": float("nan"),
        }

    df = pd.read_csv(input_csv)
    results: List[Dict[str, object]] = []

    log(f"[INFO] processing {case_id} rows={len(df)}", quiet=config.quiet)

    n_ok = 0
    n_all_zero = 0
    n_missing_image = 0
    n_error = 0

    for idx, row in df.iterrows():
        row_out = row.to_dict()
        try:
            computed = process_one_row(row=row, config=config)
            row_out.update(computed)
            if row_out.get("metric_status") == "ok":
                n_ok += 1
            elif row_out.get("metric_status") == "all_zero_image":
                n_all_zero += 1
        except FileNotFoundError as e:
            row_out["metric_status"] = "missing_image"
            row_out["metric_error"] = str(e)
            n_missing_image += 1
        except Exception as e:
            row_out["metric_status"] = "error"
            row_out["metric_error"] = f"{type(e).__name__}: {e}"
            n_error += 1

        results.append(row_out)

        if (idx + 1) % 500 == 0:
            log(f"[INFO] {case_id}: {idx + 1}/{len(df)}", quiet=config.quiet)

    out_df = pd.DataFrame(results)
    ensure_dir(output_csv.parent)
    out_df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    log(
        f"[OK] {case_id} -> {output_csv} "
        f"(ok={n_ok}, all_zero={n_all_zero}, missing={n_missing_image}, error={n_error})",
        quiet=config.quiet,
    )

    return {
        "case_id": case_id,
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "status": "ok",
        "n_rows": int(len(df)),
        "n_ok": int(n_ok),
        "n_all_zero": int(n_all_zero),
        "n_missing_image": int(n_missing_image),
        "n_error": int(n_error),
    }


def write_summary(summary_rows: List[Dict[str, object]], out_dir: Path) -> Path:
    summary_df = pd.DataFrame(summary_rows)
    summary_path = out_dir / SUMMARY_CSV_NAME
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    return summary_path


def main() -> None:
    args = parse_args()
    config = build_config(args)

    ensure_dir(config.per_frame_output_dir)

    case_csvs = list_case_csvs(config.per_frame_input_dir, config.case_filter)
    if config.limit_cases is not None:
        case_csvs = case_csvs[: int(config.limit_cases)]

    if not case_csvs:
        raise FileNotFoundError(f"No case CSVs found in: {config.per_frame_input_dir}")

    log(f"[INFO] input_dir={config.per_frame_input_dir}", quiet=config.quiet)
    log(f"[INFO] output_dir={config.per_frame_output_dir}", quiet=config.quiet)
    log(f"[INFO] found_case_csvs={len(case_csvs)}", quiet=config.quiet)
    log(f"[INFO] patch_size={config.patch_size}", quiet=config.quiet)
    log(f"[INFO] patch_stride={config.patch_stride}", quiet=config.quiet)
    log(f"[INFO] focus_patch_size={config.focus_patch_size}", quiet=config.quiet)
    log(f"[INFO] focus_patch_stride={config.focus_patch_stride}", quiet=config.quiet)
    log(f"[INFO] focus_coverage_thr={config.focus_coverage_thr}", quiet=config.quiet)
    if config.fixed_roi is not None:
        log(f"[INFO] fixed_roi={config.fixed_roi}", quiet=config.quiet)

    summary_rows: List[Dict[str, object]] = []
    for i, input_csv in enumerate(case_csvs, start=1):
        case_id = input_csv.stem.replace("_frame_scores", "")
        output_csv = config.per_frame_output_dir / input_csv.name
        log(f"[INFO] case {i}/{len(case_csvs)}: {case_id}", quiet=config.quiet)
        res = process_case_csv(input_csv=input_csv, output_csv=output_csv, config=config)
        summary_rows.append(res)

    summary_path = write_summary(summary_rows, config.per_frame_output_dir)
    log("[OK] focus_badness_v1-based metric recomputation complete", quiet=config.quiet)
    log(f"[INFO] summary_csv={summary_path}", quiet=config.quiet)


if __name__ == "__main__":
    main()