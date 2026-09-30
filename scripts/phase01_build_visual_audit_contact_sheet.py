#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Build internal visual-audit contact sheets for the Phase 01 pilot sample.

This script:
- reads reports/phase01_pilot_sampling/phase01_pilot_moments.csv
- opens the already-extracted still images referenced by image_path
- creates INTERNAL (unblinded) contact sheets for sampling QC
- creates both full-frame and metric-ROI views
- writes an image-access audit CSV

It does NOT:
- modify source images
- generate video clips
- create reviewer-facing blinded materials
- change the selected 30 moments

The sheets intentionally show selection strata/metrics because they are for
internal sampling audit only.
"""

from __future__ import annotations

import argparse
import math
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as e:
    raise SystemExit(
        "Pillow is required. Install it in the active environment with:\n"
        "  python -m pip install pillow"
    ) from e


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MOMENTS_CSV = (
    PROJECT_ROOT
    / "reports"
    / "phase01_pilot_sampling"
    / "phase01_pilot_moments.csv"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "phase01_pilot_sampling"
    / "visual_audit"
)

STRATUM_ORDER = [
    "H_confirmed_technical_failure",
    "I_ambiguous_validity_challenge",
    "G_metric_discordant",
    "F_obstruction_or_near_contact_proxy",
    "E_whiteout_or_specular",
    "D_low_light_or_blackout",
    "C_veil_or_low_contrast",
    "B_structural_visibility_loss",
    "A_clear_low_degradation",
]

SHORT_STRATUM = {
    "H_confirmed_technical_failure": "H technical failure",
    "I_ambiguous_validity_challenge": "I validity challenge",
    "G_metric_discordant": "G metric discordant",
    "F_obstruction_or_near_contact_proxy": "F obstruction/near-contact proxy",
    "E_whiteout_or_specular": "E whiteout/specular",
    "D_low_light_or_blackout": "D low-light/blackout",
    "C_veil_or_low_contrast": "C veil/low-contrast",
    "B_structural_visibility_loss": "B structural loss",
    "A_clear_low_degradation": "A clear/low degradation",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument(
        "--moments-csv",
        type=Path,
        default=DEFAULT_MOMENTS_CSV,
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    p.add_argument(
        "--columns",
        type=int,
        default=5,
    )
    p.add_argument(
        "--thumb-width",
        type=int,
        default=420,
    )
    p.add_argument(
        "--thumb-height",
        type=int,
        default=236,
    )
    p.add_argument(
        "--label-height",
        type=int,
        default=118,
    )

    return p.parse_args()


def font_default():
    # Use Pillow's built-in font to avoid machine-specific font dependencies.
    return ImageFont.load_default()


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def format_number(value) -> str:
    if pd.isna(value):
        return "NA"
    try:
        v = float(value)
    except Exception:
        return str(value)
    if math.isfinite(v):
        return f"{v:.6g}"
    return str(value)


def build_label(row: pd.Series) -> list[str]:
    stratum = safe_text(row.get("selection_stratum"))
    short_stratum = SHORT_STRATUM.get(stratum, stratum)

    line1 = (
        f"{safe_text(row.get('moment_id'))} | "
        f"{safe_text(row.get('case_id'))} | "
        f"t={format_number(row.get('sample_time_sec'))}s"
    )

    line2 = short_stratum

    slot = safe_text(row.get("selection_slot"))
    line3 = slot

    metric = safe_text(row.get("selection_metric"))
    value = format_number(row.get("selection_value"))
    band = safe_text(row.get("selection_percentile_band"))

    if metric:
        line4 = f"{metric} = {value} [{band}]"
    else:
        line4 = f"[{band}]"

    discordance = safe_text(row.get("discordance_reason"))
    line5 = discordance

    lines = [line1, line2, line3, line4]
    if line5:
        lines.append(line5)

    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(
            textwrap.wrap(
                line,
                width=62,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )

    return wrapped[:7]


def valid_roi(row: pd.Series, width: int, height: int):
    cols = ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]
    if not all(c in row.index for c in cols):
        return None

    try:
        vals = [float(row[c]) for c in cols]
    except Exception:
        return None

    if not all(math.isfinite(v) for v in vals):
        return None

    x0, y0, x1, y1 = [int(round(v)) for v in vals]

    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0))
    y1 = max(0, min(height, y1))

    if x1 <= x0 or y1 <= y0:
        return None

    return (x0, y0, x1, y1)


def fit_image(im: Image.Image, width: int, height: int) -> Image.Image:
    # Internal audit only: preserve aspect ratio with padding.
    return ImageOps.contain(im, (width, height))


def make_tile(
    row: pd.Series,
    image: Image.Image | None,
    *,
    width: int,
    image_height: int,
    label_height: int,
) -> Image.Image:
    font = font_default()
    tile = Image.new("RGB", (width, image_height + label_height))
    draw = ImageDraw.Draw(tile)

    if image is not None:
        fitted = fit_image(image, width, image_height)
        x = (width - fitted.width) // 2
        y = (image_height - fitted.height) // 2
        tile.paste(fitted, (x, y))
    else:
        draw.text(
            (10, 10),
            "IMAGE UNAVAILABLE",
            font=font,
        )

    y_text = image_height + 5
    for line in build_label(row):
        draw.text(
            (6, y_text),
            line,
            font=font,
        )
        y_text += 14

    return tile


def make_sheet(
    rows: pd.DataFrame,
    images: dict[str, Image.Image | None],
    *,
    output_path: Path,
    columns: int,
    thumb_width: int,
    thumb_height: int,
    label_height: int,
) -> None:
    n = len(rows)
    if n == 0:
        return

    cols = max(1, min(columns, n))
    n_rows = int(math.ceil(n / cols))

    tile_h = thumb_height + label_height
    sheet = Image.new(
        "RGB",
        (cols * thumb_width, n_rows * tile_h),
    )

    for i, (_, row) in enumerate(rows.iterrows()):
        moment_id = str(row["moment_id"])
        tile = make_tile(
            row,
            images.get(moment_id),
            width=thumb_width,
            image_height=thumb_height,
            label_height=label_height,
        )

        x = (i % cols) * thumb_width
        y = (i // cols) * tile_h
        sheet.paste(tile, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def load_views(
    moments: pd.DataFrame,
) -> tuple[
    dict[str, Image.Image | None],
    dict[str, Image.Image | None],
    pd.DataFrame,
]:
    full_views: dict[str, Image.Image | None] = {}
    roi_views: dict[str, Image.Image | None] = {}
    audit_rows: list[dict] = []

    for _, row in moments.iterrows():
        moment_id = str(row["moment_id"])
        image_path = Path(str(row["image_path"]))

        rec = {
            "moment_id": moment_id,
            "case_id": row.get("case_id"),
            "sample_time_sec": row.get("sample_time_sec"),
            "selection_stratum": row.get("selection_stratum"),
            "image_path": str(image_path),
            "image_exists": int(image_path.exists()),
            "image_open_ok": 0,
            "roi_available": 0,
            "roi_crop_ok": 0,
            "image_width_actual": np.nan,
            "image_height_actual": np.nan,
            "image_extrema_min": np.nan,
            "image_extrema_max": np.nan,
            "all_zero_image_detected": 0,
            "error": "",
        }

        if not image_path.exists():
            full_views[moment_id] = None
            roi_views[moment_id] = None
            rec["error"] = "image_path_not_found"
            audit_rows.append(rec)
            continue

        try:
            with Image.open(image_path) as src:
                im = src.convert("RGB").copy()

            rec["image_open_ok"] = 1
            rec["image_width_actual"] = im.width
            rec["image_height_actual"] = im.height

            extrema = im.getextrema()
            mins = [x[0] for x in extrema]
            maxs = [x[1] for x in extrema]
            rec["image_extrema_min"] = min(mins)
            rec["image_extrema_max"] = max(maxs)
            rec["all_zero_image_detected"] = int(
                max(maxs) == 0
            )

            full_views[moment_id] = im

            roi = valid_roi(
                row,
                im.width,
                im.height,
            )

            if roi is not None:
                rec["roi_available"] = 1
                try:
                    roi_im = im.crop(roi)
                    roi_views[moment_id] = roi_im
                    rec["roi_crop_ok"] = 1
                except Exception as e:
                    roi_views[moment_id] = None
                    rec["error"] = f"roi_crop_error: {e}"
            else:
                roi_views[moment_id] = None

        except Exception as e:
            full_views[moment_id] = None
            roi_views[moment_id] = None
            rec["error"] = f"image_open_error: {e}"

        audit_rows.append(rec)

    return (
        full_views,
        roi_views,
        pd.DataFrame(audit_rows),
    )


def sort_moments(moments: pd.DataFrame) -> pd.DataFrame:
    order = {name: i for i, name in enumerate(STRATUM_ORDER)}
    out = moments.copy()
    out["_stratum_order"] = (
        out["selection_stratum"]
        .map(order)
        .fillna(999)
    )

    out = out.sort_values(
        [
            "_stratum_order",
            "selection_slot",
            "moment_id",
        ],
        kind="mergesort",
    )

    return out.drop(columns=["_stratum_order"])


def main() -> None:
    args = parse_args()

    moments_csv = args.moments_csv.resolve()
    output_dir = args.output_dir.resolve()

    if not moments_csv.exists():
        raise FileNotFoundError(
            f"Pilot moments CSV not found: {moments_csv}"
        )

    moments = pd.read_csv(
        moments_csv,
        low_memory=False,
    )

    required = [
        "moment_id",
        "case_id",
        "sample_time_sec",
        "selection_stratum",
        "selection_slot",
        "image_path",
    ]

    missing = [
        c for c in required
        if c not in moments.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required column(s): {missing}"
        )

    if len(moments) != 30:
        raise ValueError(
            f"Expected 30 pilot moments, found {len(moments)}"
        )

    if moments["moment_id"].duplicated().any():
        raise ValueError("Duplicate moment_id detected")

    moments = sort_moments(moments)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== PHASE 01 INTERNAL VISUAL AUDIT ===")
    print(f"moments: {moments_csv}")
    print(f"output:  {output_dir}")
    print()

    full_views, roi_views, access_audit = load_views(
        moments
    )

    audit_csv = (
        output_dir
        / "phase01_pilot_image_access_audit.csv"
    )
    access_audit.to_csv(
        audit_csv,
        index=False,
    )

    overall_full = (
        output_dir
        / "phase01_pilot_contact_sheet_full.png"
    )
    overall_roi = (
        output_dir
        / "phase01_pilot_contact_sheet_roi.png"
    )

    make_sheet(
        moments,
        full_views,
        output_path=overall_full,
        columns=args.columns,
        thumb_width=args.thumb_width,
        thumb_height=args.thumb_height,
        label_height=args.label_height,
    )

    make_sheet(
        moments,
        roi_views,
        output_path=overall_roi,
        columns=args.columns,
        thumb_width=args.thumb_width,
        thumb_height=args.thumb_height,
        label_height=args.label_height,
    )

    by_stratum_dir = output_dir / "by_stratum"

    for stratum in STRATUM_ORDER:
        g = moments.loc[
            moments["selection_stratum"].eq(stratum)
        ].copy()

        if g.empty:
            continue

        stem = stratum

        make_sheet(
            g,
            full_views,
            output_path=(
                by_stratum_dir
                / f"{stem}_full.png"
            ),
            columns=min(3, len(g)),
            thumb_width=560,
            thumb_height=315,
            label_height=args.label_height,
        )

        make_sheet(
            g,
            roi_views,
            output_path=(
                by_stratum_dir
                / f"{stem}_roi.png"
            ),
            columns=min(3, len(g)),
            thumb_width=560,
            thumb_height=315,
            label_height=args.label_height,
        )

    n_exists = int(access_audit["image_exists"].sum())
    n_open = int(access_audit["image_open_ok"].sum())
    n_roi = int(access_audit["roi_crop_ok"].sum())
    n_zero = int(
        access_audit["all_zero_image_detected"].sum()
    )
    n_errors = int(
        access_audit["error"]
        .fillna("")
        .astype(str)
        .ne("")
        .sum()
    )

    readme = output_dir / "README.md"
    lines = [
        "# Phase 01 internal visual sampling audit",
        "",
        "These contact sheets are INTERNAL and UNBLINDED.",
        "They show metric-driven selection metadata and must not be used as reviewer-facing materials.",
        "",
        f"- Pilot moments: {len(moments)}",
        f"- Image paths found: {n_exists}",
        f"- Images opened: {n_open}",
        f"- ROI crops created: {n_roi}",
        f"- All-zero images detected from pixel extrema: {n_zero}",
        f"- Image/ROI errors: {n_errors}",
        "",
        "Files:",
        "",
        "- `phase01_pilot_contact_sheet_full.png`",
        "- `phase01_pilot_contact_sheet_roi.png`",
        "- `phase01_pilot_image_access_audit.csv`",
        "- `by_stratum/*_full.png`",
        "- `by_stratum/*_roi.png`",
        "",
        "Review the images for sampling composition only.",
        "Do not assign final surgeon reference labels from these unblinded sheets.",
        "",
    ]

    readme.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )

    print(f"image paths found: {n_exists}/{len(moments)}")
    print(f"images opened:     {n_open}/{len(moments)}")
    print(f"ROI crops created: {n_roi}/{len(moments)}")
    print(f"all-zero detected: {n_zero}")
    print(f"errors:            {n_errors}")
    print()
    print("Outputs:")
    print(f"  {overall_full}")
    print(f"  {overall_roi}")
    print(f"  {audit_csv}")
    print(f"  {by_stratum_dir}")
    print(f"  {readme}")

    if n_open != len(moments):
        raise SystemExit(
            "\nOne or more selected still images could not be opened. "
            "Audit phase01_pilot_image_access_audit.csv before proceeding."
        )


if __name__ == "__main__":
    main()
