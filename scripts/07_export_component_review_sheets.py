#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export montage sheets for component-specific visual hazard review frames.

The script reads component_review_frames.csv produced by
06_build_component_review_set.py and creates PNG review sheets grouped by
component and selection type. Output images should generally not be committed to
GitHub because they may contain surgical images.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable, Optional, Tuple

import cv2
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_CSV = PROJECT_ROOT / "data" / "annotations" / "component_review_frames.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "component_review_sheets"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export component-specific visual review montage sheets."
    )
    parser.add_argument(
        "--review-csv",
        type=Path,
        default=DEFAULT_REVIEW_CSV,
        help=f"Input review CSV. Default: {DEFAULT_REVIEW_CSV}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for montage PNGs. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--component",
        nargs="*",
        default=None,
        help="Optional target_component filters.",
    )
    parser.add_argument(
        "--selection-type",
        nargs="*",
        default=None,
        help="Optional selection_type filters, e.g. high low manual.",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=4,
        help="Number of image columns per sheet. Default: 4",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Number of image rows per sheet. Default: 5",
    )
    parser.add_argument(
        "--tile-width",
        type=int,
        default=360,
        help="Tile image width in pixels. Default: 360",
    )
    parser.add_argument(
        "--tile-height",
        type=int,
        default=260,
        help="Tile image height in pixels. Default: 260",
    )
    parser.add_argument(
        "--label-height",
        type=int,
        default=82,
        help="Label panel height under each tile. Default: 82",
    )
    parser.add_argument(
        "--crop-roi",
        action="store_true",
        help="Crop to ROI instead of showing full frame with ROI rectangle.",
    )
    parser.add_argument(
        "--draw-roi",
        action="store_true",
        help="Draw ROI rectangle when not cropping.",
    )
    parser.add_argument(
        "--max-pages-per-group",
        type=int,
        default=None,
        help="Optional cap on pages per component/selection group.",
    )
    parser.add_argument(
        "--missing-ok",
        action="store_true",
        help="Continue if image files are missing, rendering placeholder tiles.",
    )
    return parser.parse_args()


def safe_slug(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def parse_float(row: pd.Series, col: str) -> Optional[float]:
    if col not in row.index:
        return None
    try:
        value = float(row[col])
    except Exception:
        return None
    if not math.isfinite(value):
        return None
    return value


def parse_roi(row: pd.Series, image_shape: Tuple[int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    vals = []
    for col in ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]:
        v = parse_float(row, col)
        if v is None:
            return None
        vals.append(int(round(v)))
    h, w = image_shape[:2]
    x0, y0, x1, y1 = vals
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))
    return x0, y0, x1, y1


def read_image_bgr(path: str, missing_ok: bool, width: int, height: int) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is not None:
        return img
    if not missing_ok:
        raise FileNotFoundError(f"Failed to read image: {path}")
    canvas = np.full((height, width, 3), 235, dtype=np.uint8)
    cv2.putText(canvas, "MISSING IMAGE", (20, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 180), 2)
    return canvas


def fit_image(img_bgr: np.ndarray, width: int, height: int) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return np.full((height, width, 3), 240, dtype=np.uint8)
    scale = min(width / w, height / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    x = (width - new_w) // 2
    y = (height - new_h) // 2
    canvas[y : y + new_h, x : x + new_w] = resized
    return canvas


def wrap_text(text: str, max_chars: int) -> list[str]:
    text = str(text)
    if len(text) <= max_chars:
        return [text]
    parts = []
    current = ""
    for token in text.split():
        if len(current) + len(token) + 1 <= max_chars:
            current = (current + " " + token).strip()
        else:
            if current:
                parts.append(current)
            current = token
    if current:
        parts.append(current)
    if not parts:
        parts = [text[:max_chars]]
    return parts[:4]


def make_tile(row: pd.Series, args: argparse.Namespace) -> np.ndarray:
    path = str(row.get("image_path", ""))
    img = read_image_bgr(path, args.missing_ok, args.tile_width, args.tile_height)

    if args.crop_roi:
        roi = parse_roi(row, img.shape)
        if roi is not None:
            x0, y0, x1, y1 = roi
            img = img[y0:y1, x0:x1].copy()
    elif args.draw_roi:
        roi = parse_roi(row, img.shape)
        if roi is not None:
            x0, y0, x1, y1 = roi
            cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 255), 3)

    image_panel = fit_image(img, args.tile_width, args.tile_height)
    label_panel = np.full((args.label_height, args.tile_width, 3), 255, dtype=np.uint8)

    case_id = row.get("case_id", "")
    t = row.get("sample_time_sec", "")
    score_col = row.get("source_score_col", "")
    score_value = row.get("source_score_value", "")
    review_id = row.get("review_id", "")
    label = row.get("candidate_label", "")

    try:
        score_txt = f"{float(score_value):.4f}"
    except Exception:
        score_txt = str(score_value)

    lines = [
        f"{review_id} | {case_id} | t={t}",
        f"{score_col}: {score_txt}",
    ]
    lines.extend(wrap_text(str(label), max_chars=46)[:2])

    y = 18
    for line in lines:
        cv2.putText(label_panel, line[:72], (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (20, 20, 20), 1, cv2.LINE_AA)
        y += 19

    return np.vstack([image_panel, label_panel])


def make_sheet(rows: pd.DataFrame, args: argparse.Namespace, title: str, page_num: int, total_pages: int) -> np.ndarray:
    tile_h = args.tile_height + args.label_height
    tile_w = args.tile_width
    header_h = 54
    sheet_h = header_h + args.rows * tile_h
    sheet_w = args.cols * tile_w
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, title[:120], (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(sheet, f"page {page_num}/{total_pages}", (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 50, 50), 1, cv2.LINE_AA)

    for idx, (_, row) in enumerate(rows.iterrows()):
        r = idx // args.cols
        c = idx % args.cols
        if r >= args.rows:
            break
        tile = make_tile(row, args)
        y0 = header_h + r * tile_h
        x0 = c * tile_w
        sheet[y0 : y0 + tile_h, x0 : x0 + tile_w] = tile
        cv2.rectangle(sheet, (x0, y0), (x0 + tile_w - 1, y0 + tile_h - 1), (210, 210, 210), 1)
    return sheet


def filter_df(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = df.copy()
    if args.component:
        out = out[out["target_component"].astype(str).isin(set(args.component))]
    if args.selection_type:
        out = out[out["selection_type"].astype(str).isin(set(args.selection_type))]
    return out


def sort_group(g: pd.DataFrame) -> pd.DataFrame:
    if "source_rank_within_score" in g.columns:
        rank = pd.to_numeric(g["source_rank_within_score"], errors="coerce")
        return g.assign(_rank=rank).sort_values(["_rank", "review_id"], na_position="last").drop(columns=["_rank"])
    return g.sort_values("review_id")


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.review_csv)
    required = {"target_component", "selection_type", "image_path"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Review CSV missing required columns: {missing}")

    df = filter_df(df, args)
    if df.empty:
        raise ValueError("No review rows after filtering.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_page = args.cols * args.rows
    written = []

    for (component, selection_type), group in df.groupby(["target_component", "selection_type"], dropna=False):
        group = sort_group(group)
        total_pages = int(math.ceil(len(group) / per_page))
        if args.max_pages_per_group is not None:
            total_pages = min(total_pages, int(args.max_pages_per_group))
        for page_idx in range(total_pages):
            start = page_idx * per_page
            end = start + per_page
            page_rows = group.iloc[start:end]
            title = f"{component} | {selection_type} | n={len(group)}"
            sheet = make_sheet(page_rows, args, title, page_idx + 1, total_pages)
            filename = f"review_{safe_slug(component)}_{safe_slug(selection_type)}_p{page_idx + 1:02d}.png"
            out_path = args.output_dir / filename
            cv2.imwrite(str(out_path), sheet)
            written.append(out_path)

    print(f"Wrote {len(written)} montage sheet(s) to {args.output_dir}")
    for path in written[:20]:
        print(path)
    if len(written) > 20:
        print(f"... {len(written) - 20} more")


if __name__ == "__main__":
    main()
