#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


STRUCT_METRIC = "structural_visibility_loss_v1"
COLOR_METRIC = "dark_red_brown_candidate_ratio_v1"


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Build explanatory QC contact sheets for neo cases using top frames from "
            "structural_visibility_loss_v1 and dark_red_brown_candidate_ratio_v1. "
            "This is descriptive visual QC, not semantic validation."
        )
    )
    p.add_argument("--quality-dir", required=True, type=Path)
    p.add_argument("--color-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--n-per-metric", type=int, default=6)
    p.add_argument(
        "--min-separation-sec",
        type=float,
        default=30.0,
        help="Minimum temporal separation between selected frames within each metric/case.",
    )
    p.add_argument("--thumb-width", type=int, default=420)
    p.add_argument(
        "--show-roi-only",
        action="store_true",
        help="Crop displayed images to the metric ROI instead of showing the full frame.",
    )
    return p.parse_args()


def case_id_from_path(path: Path) -> str:
    return path.stem.replace("_frame_scores", "")


def load_quality_case(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    required = {
        "case_id", "sample_time_sec", "image_path",
        STRUCT_METRIC, "roi_x0", "roi_y0", "roi_x1", "roi_y1"
    }
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

    if "metric_status" in d.columns:
        d = d[d["metric_status"].astype(str).eq("ok")].copy()

    d["sample_time_sec"] = pd.to_numeric(d["sample_time_sec"], errors="coerce")
    d[STRUCT_METRIC] = pd.to_numeric(d[STRUCT_METRIC], errors="coerce")
    return d


def load_color(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    required = {"case_id", "sample_time_sec", "image_path", COLOR_METRIC}
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

    d["sample_time_sec"] = pd.to_numeric(d["sample_time_sec"], errors="coerce")
    d[COLOR_METRIC] = pd.to_numeric(d[COLOR_METRIC], errors="coerce")
    return d


def choose_top_separated(
    d: pd.DataFrame,
    metric: str,
    n: int,
    min_sep: float
) -> pd.DataFrame:
    x = d.dropna(subset=[metric, "sample_time_sec", "image_path"]).copy()
    x = x.sort_values(metric, ascending=False)

    selected = []
    selected_times = []

    for idx, row in x.iterrows():
        t = float(row["sample_time_sec"])
        if all(abs(t - t0) >= min_sep for t0 in selected_times):
            selected.append(idx)
            selected_times.append(t)
        if len(selected) >= n:
            break

    out = x.loc[selected].copy()
    out["selection_rank"] = np.arange(1, len(out) + 1)
    return out


def roi_from_row(row, img_shape):
    h, w = img_shape[:2]
    vals = []
    for c in ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]:
        if c in row.index and pd.notna(row[c]):
            vals.append(int(round(float(row[c]))))
        else:
            vals.append(None)

    if any(v is None for v in vals):
        return 0, 0, w, h

    x0, y0, x1, y1 = vals
    x0 = max(0, min(w - 1, x0))
    y0 = max(0, min(h - 1, y0))
    x1 = max(x0 + 1, min(w, x1))
    y1 = max(y0 + 1, min(h, y1))
    return x0, y0, x1, y1


def annotate_image(img, row, metric, rank, show_roi_only):
    x0, y0, x1, y1 = roi_from_row(row, img.shape)

    if show_roi_only:
        img = img[y0:y1, x0:x1].copy()
    else:
        cv2.rectangle(img, (x0, y0), (x1, y1), (255, 255, 255), 3)

    h, w = img.shape[:2]
    bar_h = max(52, int(round(h * 0.07)))
    cv2.rectangle(img, (0, 0), (w, bar_h), (0, 0, 0), -1)

    score = float(row[metric])
    t = float(row["sample_time_sec"])
    metric_short = "STRUCT" if metric == STRUCT_METRIC else "DARK-RED"
    label = f"{metric_short} rank {rank} | t={t:.0f}s | score={score:.6f}"

    font_scale = max(0.55, min(0.9, w / 950.0))
    thickness = 2
    cv2.putText(
        img,
        label,
        (12, int(bar_h * 0.68)),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
    return img


def resize_to_width(img, width):
    h, w = img.shape[:2]
    scale = width / float(w)
    nh = max(1, int(round(h * scale)))
    return cv2.resize(img, (width, nh), interpolation=cv2.INTER_AREA)


def make_grid(images, ncol, thumb_width):
    thumbs = [resize_to_width(img, thumb_width) for img in images]
    max_h = max(x.shape[0] for x in thumbs)
    nrow = int(np.ceil(len(thumbs) / ncol))
    canvas = np.zeros(
        (nrow * max_h, ncol * thumb_width, 3),
        dtype=np.uint8,
    )

    for i, img in enumerate(thumbs):
        r, c = divmod(i, ncol)
        y = r * max_h
        x = c * thumb_width
        canvas[y:y + img.shape[0], x:x + img.shape[1]] = img

    return canvas


def add_section_title(sheet, title):
    title_h = 54
    out = np.zeros((sheet.shape[0] + title_h, sheet.shape[1], 3), dtype=np.uint8)
    out[title_h:, :, :] = sheet
    cv2.putText(
        out,
        title,
        (14, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return out


def stack_sections(top, bottom):
    w = max(top.shape[1], bottom.shape[1])

    def pad(x):
        if x.shape[1] == w:
            return x
        out = np.zeros((x.shape[0], w, 3), dtype=np.uint8)
        out[:, :x.shape[1], :] = x
        return out

    gap = np.zeros((20, w, 3), dtype=np.uint8)
    return np.vstack([pad(top), gap, pad(bottom)])


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    quality_files = sorted(args.quality_dir.glob("*_frame_scores.csv"))
    quality_files = [p for p in quality_files if not p.name.startswith("_")]
    if not quality_files:
        raise FileNotFoundError(f"No quality case CSVs found in {args.quality_dir}")

    color = load_color(args.color_csv)

    manifest_rows = []

    for qpath in quality_files:
        case_id = case_id_from_path(qpath)
        q = load_quality_case(qpath)
        c = color[color["case_id"].astype(str).eq(case_id)].copy()

        if c.empty:
            raise ValueError(f"No color rows found for case {case_id}")

        struct_sel = choose_top_separated(
            q, STRUCT_METRIC, args.n_per_metric, args.min_separation_sec
        )
        color_sel = choose_top_separated(
            c, COLOR_METRIC, args.n_per_metric, args.min_separation_sec
        )

        sections = []

        for metric, sel, section_label in [
            (STRUCT_METRIC, struct_sel, "Top structural-visibility-loss frames"),
            (COLOR_METRIC, color_sel, "Top dark-red/brown candidate frames"),
        ]:
            images = []
            for _, row in sel.iterrows():
                path = Path(str(row["image_path"]))
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None:
                    print(f"[WARN] could not read {path}")
                    continue

                img = annotate_image(
                    img,
                    row,
                    metric,
                    int(row["selection_rank"]),
                    args.show_roi_only,
                )
                images.append(img)

                manifest_rows.append({
                    "case_id": case_id,
                    "selection_metric": metric,
                    "selection_rank": int(row["selection_rank"]),
                    "sample_time_sec": float(row["sample_time_sec"]),
                    "score": float(row[metric]),
                    "image_path": str(path),
                    "min_separation_sec": args.min_separation_sec,
                    "show_roi_only": int(args.show_roi_only),
                    "manual_primary_visual_cause": "",
                    "manual_secondary_visual_cause": "",
                    "manual_semantic_oper_phenotype_visible": "",
                    "manual_comment": "",
                })

            if not images:
                raise RuntimeError(f"No readable selected images for {case_id} {metric}")

            sheet = make_grid(
                images,
                ncol=min(3, args.n_per_metric),
                thumb_width=args.thumb_width,
            )
            sheet = add_section_title(sheet, section_label)
            sections.append(sheet)

        combined = stack_sections(sections[0], sections[1])
        suffix = "_roi" if args.show_roi_only else "_full"
        out_path = args.output_dir / f"{case_id}_explanatory_qc{suffix}.jpg"
        cv2.imwrite(str(out_path), combined)
        print("Saved:", out_path)

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = args.output_dir / "neo_explanatory_topframe_qc_manifest.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    print()
    print("Saved manifest:", manifest_path)
    print(
        "Manual columns are intentionally blank. This montage is descriptive QC only "
        "and should not be interpreted as semantic detector validation."
    )


if __name__ == "__main__":
    main()
