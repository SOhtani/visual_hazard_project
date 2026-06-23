#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXED10_ROOT = PROJECT_ROOT / "reports" / "fixed10_metric_review"
DEFAULT_OUT_ROOT = PROJECT_ROOT / "reports" / "focus_goodness_v1_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate focus_badness_v1 on a fixed review set."
    )
    parser.add_argument(
        "--case",
        required=True,
        help="Case ID, e.g. CASE003",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Input fixed10 CSV. Default: reports/fixed10_metric_review/<CASE>/<CASE>_fixed10_selected_frames.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help=f"Output root directory. Default: {DEFAULT_OUT_ROOT}",
    )
    parser.add_argument(
        "--patch-size",
        type=int,
        default=48,
        help="Patch size in pixels. Default: 48",
    )
    parser.add_argument(
        "--patch-stride",
        type=int,
        default=24,
        help="Patch stride in pixels. Default: 24",
    )
    parser.add_argument(
        "--coverage-thr",
        type=float,
        default=0.38,
        help="Patch focus threshold for visible coverage. Default: 0.38",
    )
    parser.add_argument(
        "--tile-width",
        type=int,
        default=420,
        help="Tile width for review sheet. Default: 420",
    )
    parser.add_argument(
        "--tile-height",
        type=int,
        default=260,
        help="Tile height for review sheet. Default: 260",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite outputs.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_image_rgb(image_path: Path) -> np.ndarray:
    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def save_rgb(path: Path, rgb: np.ndarray) -> None:
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok = cv2.imwrite(str(path), bgr)
    if not ok:
        raise IOError(f"Failed to save image: {path}")


def draw_roi(rgb: np.ndarray, roi: Tuple[int, int, int, int], color=(0, 255, 0), thickness: int = 3) -> np.ndarray:
    out_bgr = cv2.cvtColor(rgb.copy(), cv2.COLOR_RGB2BGR)
    x0, y0, x1, y1 = roi
    cv2.rectangle(out_bgr, (x0, y0), (x1 - 1, y1 - 1), color, thickness)
    return cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)


def fit_image_with_padding(rgb: np.ndarray, width: int, height: int, pad_value: int = 0) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = min(width / w, height / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.full((height, width, 3), pad_value, dtype=np.uint8)
    x0 = (width - new_w) // 2
    y0 = (height - new_h) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def add_caption_block(
    rgb: np.ndarray,
    title: str,
    subtitle_lines: Sequence[str],
    block_h: int = 92,
) -> np.ndarray:
    h, w = rgb.shape[:2]
    out = np.full((h + block_h, w, 3), 0, dtype=np.uint8)
    out[:h] = rgb

    out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    cv2.putText(
        out_bgr,
        title,
        (10, h + 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    for i, line in enumerate(subtitle_lines):
        cv2.putText(
            out_bgr,
            line,
            (10, h + 48 + 16 * i),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
    return cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)


def concat_grid(images: Sequence[np.ndarray], n_cols: int, pad_value: int = 0) -> np.ndarray:
    if len(images) == 0:
        return np.full((200, 400, 3), pad_value, dtype=np.uint8)

    tile_h = max(img.shape[0] for img in images)
    tile_w = max(img.shape[1] for img in images)

    padded: List[np.ndarray] = []
    for img in images:
        canvas = np.full((tile_h, tile_w, 3), pad_value, dtype=np.uint8)
        canvas[:img.shape[0], :img.shape[1]] = img
        padded.append(canvas)

    rows: List[np.ndarray] = []
    for i in range(0, len(padded), n_cols):
        row_imgs = padded[i:i + n_cols]
        if len(row_imgs) < n_cols:
            for _ in range(n_cols - len(row_imgs)):
                row_imgs.append(np.full((tile_h, tile_w, 3), pad_value, dtype=np.uint8))
        rows.append(np.hstack(row_imgs))
    return np.vstack(rows)


def rgb_to_gray_float(rgb_u8: np.ndarray) -> np.ndarray:
    rgb_f = rgb_u8.astype(np.float32) / 255.0
    return cv2.cvtColor(rgb_f, cv2.COLOR_RGB2GRAY).astype(np.float32)


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


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    valid = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if valid.sum() == 0:
        return float("nan")
    vv = v[valid]
    ww = w[valid]
    return float(np.sum(vv * ww) / np.sum(ww))


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

    for y0 in y_starts:
        for x0 in x_starts:
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

    scores = np.asarray(patch_scores, dtype=np.float64)
    weights = np.asarray(patch_weights, dtype=np.float64)

    patch_focus_q90 = weighted_quantile(scores, weights, 0.90)
    patch_focus_mean = weighted_mean(scores, weights)
    focus_coverage = weighted_mean((scores >= float(coverage_thr)).astype(np.float64), weights)

    focus_badness_v1 = float(1.0 - np.clip(0.45 * patch_focus_q90 + 0.55 * focus_coverage, 0.0, 1.0))

    return {
        "patch_focus_mean": patch_focus_mean,
        "patch_focus_q90": patch_focus_q90,
        "focus_coverage": focus_coverage,
        "focus_badness_v1": focus_badness_v1,
        "tenengrad_patch_mean_raw": float(np.mean(ten_vals)) if ten_vals else float("nan"),
        "lapvar_patch_mean_raw": float(np.mean(lap_vals)) if lap_vals else float("nan"),
        "entropy_patch_mean_raw": float(np.mean(ent_vals)) if ent_vals else float("nan"),
    }


def score_one_row(
    row: pd.Series,
    patch_size: int,
    patch_stride: int,
    coverage_thr: float,
) -> Dict[str, float]:
    image_path = Path(str(row["image_path"]))
    rgb = load_image_rgb(image_path)

    x0 = int(float(row["roi_x0"]))
    y0 = int(float(row["roi_y0"]))
    x1 = int(float(row["roi_x1"]))
    y1 = int(float(row["roi_y1"]))

    x0 = max(0, min(x0, rgb.shape[1] - 1))
    y0 = max(0, min(y0, rgb.shape[0] - 1))
    x1 = max(x0 + 1, min(x1, rgb.shape[1]))
    y1 = max(y0 + 1, min(y1, rgb.shape[0]))

    roi = rgb[y0:y1, x0:x1]
    return compute_focus_badness_v1_for_roi(
        roi_rgb_u8=roi,
        patch_size=patch_size,
        patch_stride=patch_stride,
        coverage_thr=coverage_thr,
    )


def make_tile_from_row(
    row: pd.Series,
    tile_width: int,
    tile_height: int,
) -> np.ndarray:
    image_path = Path(str(row["image_path"]))
    rgb = load_image_rgb(image_path)

    roi = (
        int(float(row["roi_x0"])),
        int(float(row["roi_y0"])),
        int(float(row["roi_x1"])),
        int(float(row["roi_y1"])),
    )
    rgb = draw_roi(rgb, roi)
    rgb = fit_image_with_padding(rgb, tile_width, tile_height)

    title = f"#{int(row['fixed_id'])}  {row['slot_name']}  t={int(float(row['sample_time_sec']))}"

    subtitle_lines = [
        f"focus_badness_v1={float(row['focus_badness_v1']):.3f}",
        f"coverage={float(row['focus_coverage']):.3f}   q90={float(row['patch_focus_q90']):.3f}   mean={float(row['patch_focus_mean']):.3f}",
        f"comp={float(row['composite_badness_v3']):.3f}  blur={float(row['blur_like_mean']):.3f}  veil={float(row['veil_smoke_mean']):.3f}",
    ]
    return add_caption_block(rgb, title, subtitle_lines, block_h=92)


def create_sorted_sheet(
    df: pd.DataFrame,
    case_id: str,
    sort_col: str,
    ascending: bool,
    out_path: Path,
    title_suffix: str,
    tile_width: int,
    tile_height: int,
    overwrite: bool,
) -> None:
    if out_path.exists() and not overwrite:
        return

    work = df.sort_values(sort_col, ascending=ascending).reset_index(drop=True)

    tiles: List[np.ndarray] = []
    for _, row in work.iterrows():
        tiles.append(make_tile_from_row(row=row, tile_width=tile_width, tile_height=tile_height))

    grid = concat_grid(tiles, n_cols=5, pad_value=0)

    header = np.full((78, grid.shape[1], 3), 0, dtype=np.uint8)
    header_bgr = cv2.cvtColor(header, cv2.COLOR_RGB2BGR)
    cv2.putText(
        header_bgr,
        f"{case_id} / {title_suffix}",
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.82,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        header_bgr,
        "focus_badness_v1: lower is better, higher is worse",
        (12, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    header = cv2.cvtColor(header_bgr, cv2.COLOR_BGR2RGB)

    save_rgb(out_path, np.vstack([header, grid]))


def main() -> None:
    args = parse_args()

    if args.input_csv is None:
        input_csv = DEFAULT_FIXED10_ROOT / args.case / f"{args.case}_fixed10_selected_frames.csv"
    else:
        input_csv = args.input_csv

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    case_out_dir = args.out_dir / args.case
    ensure_dir(case_out_dir)

    df = pd.read_csv(input_csv)
    df["sample_time_sec"] = pd.to_numeric(df["sample_time_sec"], errors="coerce")

    scored_rows: List[Dict[str, object]] = []
    for _, row in df.iterrows():
        base = row.to_dict()
        scores = score_one_row(
            row=row,
            patch_size=int(args.patch_size),
            patch_stride=int(args.patch_stride),
            coverage_thr=float(args.coverage_thr),
        )
        base.update(scores)
        scored_rows.append(base)

    out_df = pd.DataFrame(scored_rows)

    out_df["focus_badness_rank_asc"] = (
        pd.to_numeric(out_df["focus_badness_v1"], errors="coerce")
        .rank(method="dense", ascending=True)
        .astype("Int64")
    )
    out_df["focus_badness_rank_desc"] = (
        pd.to_numeric(out_df["focus_badness_v1"], errors="coerce")
        .rank(method="dense", ascending=False)
        .astype("Int64")
    )

    scored_csv = case_out_dir / f"{args.case}_fixed10_with_focus_badness_v1.csv"
    if (not scored_csv.exists()) or args.overwrite:
        out_df.to_csv(scored_csv, index=False, encoding="utf-8-sig")

    sheet_good = case_out_dir / f"{args.case}_fixed10_sorted_by_focus_badness_v1_low_to_high.png"
    create_sorted_sheet(
        df=out_df,
        case_id=args.case,
        sort_col="focus_badness_v1",
        ascending=True,
        out_path=sheet_good,
        title_suffix="same fixed frames sorted by focus_badness_v1 (low -> high)",
        tile_width=int(args.tile_width),
        tile_height=int(args.tile_height),
        overwrite=bool(args.overwrite),
    )

    sheet_bad = case_out_dir / f"{args.case}_fixed10_sorted_by_focus_badness_v1_high_to_low.png"
    create_sorted_sheet(
        df=out_df,
        case_id=args.case,
        sort_col="focus_badness_v1",
        ascending=False,
        out_path=sheet_bad,
        title_suffix="same fixed frames sorted by focus_badness_v1 (high -> low)",
        tile_width=int(args.tile_width),
        tile_height=int(args.tile_height),
        overwrite=bool(args.overwrite),
    )

    summary_cols = [
        "fixed_id",
        "slot_name",
        "sample_time_sec",
        "focus_badness_v1",
        "focus_coverage",
        "patch_focus_q90",
        "patch_focus_mean",
        "blur_like_mean",
        "veil_smoke_mean",
        "local_obstruction_ratio",
        "saturation_ratio",
        "specular_ratio",
        "composite_badness_v3",
        "focus_badness_rank_asc",
        "focus_badness_rank_desc",
    ]
    summary_csv = case_out_dir / f"{args.case}_fixed10_focus_badness_rank_table.csv"
    if (not summary_csv.exists()) or args.overwrite:
        out_df[summary_cols].to_csv(summary_csv, index=False, encoding="utf-8-sig")

    print("[OK] focus_badness_v1 evaluation complete")
    print(f"[INFO] input_csv={input_csv}")
    print(f"[INFO] scored_csv={scored_csv}")
    print(f"[INFO] summary_csv={summary_csv}")
    print(f"[INFO] sheet_good={sheet_good}")
    print(f"[INFO] sheet_bad={sheet_bad}")


if __name__ == "__main__":
    main()