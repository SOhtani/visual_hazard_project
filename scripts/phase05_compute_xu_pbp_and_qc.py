#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


TAU_Y = 80.0
TAU_R = 14.0
ALPHA = 0.38
BETA = 0.24


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Apply the published Xu et al. (EJCTS 2022) blood-pixel rule to "
            "surgical frames and create explanatory QC montages. "
            "The published thresholds are not re-tuned."
        )
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--metrics-dir", type=Path)
    src.add_argument("--frame-csv", type=Path)

    p.add_argument("--output-csv", required=True, type=Path)
    p.add_argument("--report-dir", required=True, type=Path)
    p.add_argument(
        "--spatial-domain",
        choices=["roi", "full"],
        default="roi",
        help=(
            "roi: apply Xu rule within pre-existing surgical-field ROI; "
            "full: apply to the full image. Default=roi."
        ),
    )
    p.add_argument("--n-top-per-case", type=int, default=6)
    p.add_argument("--n-low-per-case", type=int, default=2)
    p.add_argument("--min-separation-sec", type=float, default=30.0)
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def log(msg, quiet=False):
    if not quiet:
        print(msg, flush=True)


def case_csvs(root: Path):
    files = sorted(root.glob("*_frame_scores.csv"))
    return [p for p in files if not p.name.startswith("_")]


def minimal_columns(header):
    preferred = [
        "case_id",
        "sample_time_sec",
        "frame_idx_1based",
        "frame_index_1based",
        "image_file",
        "image_path",
        "metric_status",
        "roi_x0",
        "roi_y0",
        "roi_x1",
        "roi_y1",
    ]
    return [c for c in preferred if c in header]


def load_sources(args):
    chunks = []

    if args.metrics_dir is not None:
        files = case_csvs(args.metrics_dir)
        if not files:
            raise FileNotFoundError(f"No case CSVs found: {args.metrics_dir}")

        for i, p in enumerate(files, 1):
            header = pd.read_csv(p, nrows=0)
            cols = minimal_columns(header.columns)
            d = pd.read_csv(p, usecols=cols)
            if "case_id" not in d.columns:
                d["case_id"] = p.stem.replace("_frame_scores", "")
            chunks.append(d)
            log(f"[load] {i}/{len(files)} {p.name} rows={len(d)}", args.quiet)

        d = pd.concat(chunks, ignore_index=True)
    else:
        header = pd.read_csv(args.frame_csv, nrows=0)
        cols = minimal_columns(header.columns)
        d = pd.read_csv(args.frame_csv, usecols=cols)
        log(f"[load] {args.frame_csv} rows={len(d)}", args.quiet)

    required = {"case_id", "sample_time_sec", "image_path"}
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if "metric_status" in d.columns:
        d = d[d["metric_status"].astype(str).eq("ok")].copy()

    d["sample_time_sec"] = pd.to_numeric(d["sample_time_sec"], errors="coerce")
    d = d.dropna(subset=["case_id", "sample_time_sec", "image_path"]).copy()

    if args.max_frames is not None:
        d = d.head(args.max_frames).copy()

    return d.reset_index(drop=True)


def get_roi(row, width, height, spatial_domain):
    if spatial_domain == "full":
        return 0, 0, width, height

    cols = ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]
    if not all(c in row.index and pd.notna(row[c]) for c in cols):
        raise ValueError(
            "ROI mode requested but ROI columns are absent/incomplete. "
            "Use --spatial-domain full or provide ROI columns."
        )

    x0 = int(round(float(row["roi_x0"])))
    y0 = int(round(float(row["roi_y0"])))
    x1 = int(round(float(row["roi_x1"])))
    y1 = int(round(float(row["roi_y1"])))

    x0 = max(0, min(width - 1, x0))
    y0 = max(0, min(height - 1, y0))
    x1 = max(x0 + 1, min(width, x1))
    y1 = max(y0 + 1, min(height, y1))
    return x0, y0, x1, y1


def xu_mask_and_stats(img_bgr, roi):
    x0, y0, x1, y1 = roi
    crop = img_bgr[y0:y1, x0:x1]

    if crop.size == 0:
        raise ValueError("empty ROI")

    red = crop[:, :, 2].astype(np.float32)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)

    frame_red = float(red.mean())
    frame_gray = float(gray.mean())

    if frame_red <= 0:
        return None, {
            "xu_pbp_v1": np.nan,
            "xu_blood_pixel_count_v1": 0,
            "xu_domain_pixel_count_v1": int(red.size),
            "xu_frame_red_mean_v1": frame_red,
            "xu_frame_gray_mean_v1": frame_gray,
            "xu_dynamic_gray_red_threshold_v1": np.nan,
        }

    frame_gray_red = frame_gray / frame_red
    dynamic_threshold = ALPHA * frame_gray_red + BETA

    ratio = np.divide(
        gray,
        red,
        out=np.full_like(gray, np.inf, dtype=np.float32),
        where=red > 0,
    )

    mask = (
        (gray < TAU_Y)
        & (red > TAU_R)
        & (ratio < dynamic_threshold)
    )

    n_blood = int(mask.sum())
    n_all = int(mask.size)
    pbp = float(n_blood / n_all) if n_all else np.nan

    return mask, {
        "xu_pbp_v1": pbp,
        "xu_blood_pixel_count_v1": n_blood,
        "xu_domain_pixel_count_v1": n_all,
        "xu_frame_red_mean_v1": frame_red,
        "xu_frame_gray_mean_v1": frame_gray,
        "xu_dynamic_gray_red_threshold_v1": float(dynamic_threshold),
    }


def compute_all(d, args):
    rows = []

    for i, row in d.iterrows():
        path = Path(str(row["image_path"]))
        out = row.to_dict()
        out.update({
            "xu_rule_status": "",
            "xu_spatial_domain": args.spatial_domain,
            "xu_tau_y": TAU_Y,
            "xu_tau_r": TAU_R,
            "xu_alpha": ALPHA,
            "xu_beta": BETA,
            "xu_gray_conversion": "OpenCV COLOR_BGR2GRAY",
        })

        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            out["xu_rule_status"] = "missing_image"
            rows.append(out)
            continue

        h, w = img.shape[:2]

        try:
            roi = get_roi(row, w, h, args.spatial_domain)
            _, stats = xu_mask_and_stats(img, roi)
            out.update(stats)
            out.update({
                "xu_roi_x0": roi[0],
                "xu_roi_y0": roi[1],
                "xu_roi_x1": roi[2],
                "xu_roi_y1": roi[3],
                "xu_rule_status": "ok",
            })
        except Exception as e:
            out["xu_rule_status"] = f"error:{type(e).__name__}"
            out["xu_pbp_v1"] = np.nan

        rows.append(out)

        if (i + 1) % 1000 == 0:
            log(f"[score] {i+1}/{len(d)}", args.quiet)

    return pd.DataFrame(rows)


def separated_select(g, ascending, n, min_sep):
    x = g.dropna(subset=["xu_pbp_v1", "sample_time_sec"]).sort_values(
        "xu_pbp_v1", ascending=ascending
    )
    chosen = []
    times = []

    for idx, row in x.iterrows():
        t = float(row["sample_time_sec"])
        if all(abs(t - t0) >= min_sep for t0 in times):
            chosen.append(idx)
            times.append(t)
        if len(chosen) >= n:
            break

    return x.loc[chosen].copy()


def make_pair_tile(img_bgr, mask, label, thumb_width=360):
    h, w = img_bgr.shape[:2]

    scale = thumb_width / float(w)
    nh = max(1, int(round(h * scale)))
    original = cv2.resize(img_bgr, (thumb_width, nh), interpolation=cv2.INTER_AREA)

    mask8 = (mask.astype(np.uint8) * 255)
    mask3 = cv2.cvtColor(mask8, cv2.COLOR_GRAY2BGR)
    mask3 = cv2.resize(mask3, (thumb_width, nh), interpolation=cv2.INTER_NEAREST)

    pair = np.hstack([original, mask3])

    bar_h = 42
    out = np.zeros((pair.shape[0] + bar_h, pair.shape[1], 3), dtype=np.uint8)
    out[bar_h:] = pair
    cv2.putText(
        out,
        label,
        (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return out


def grid(images, ncol=2):
    if not images:
        raise ValueError("no images")
    max_h = max(x.shape[0] for x in images)
    max_w = max(x.shape[1] for x in images)
    nrow = int(math.ceil(len(images) / ncol))
    canvas = np.zeros((nrow * max_h, ncol * max_w, 3), dtype=np.uint8)

    for i, img in enumerate(images):
        r, c = divmod(i, ncol)
        y = r * max_h
        x = c * max_w
        canvas[y:y + img.shape[0], x:x + img.shape[1]] = img
    return canvas


def add_title(img, title):
    top = 52
    out = np.zeros((img.shape[0] + top, img.shape[1], 3), dtype=np.uint8)
    out[top:] = img
    cv2.putText(
        out, title, (12, 35),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA
    )
    return out


def build_qc(scored, args):
    qc_dir = args.report_dir / "qc_montages"
    qc_dir.mkdir(parents=True, exist_ok=True)

    review_rows = []

    ok = scored[scored["xu_rule_status"].eq("ok")].copy()

    for case_id, g in ok.groupby("case_id", sort=True):
        top = separated_select(
            g, ascending=False, n=args.n_top_per_case,
            min_sep=args.min_separation_sec
        )
        low = separated_select(
            g, ascending=True, n=args.n_low_per_case,
            min_sep=args.min_separation_sec
        )

        sections = []

        for label_group, sel in [("TOP PBP", top), ("LOW PBP", low)]:
            tiles = []
            for rank, (_, row) in enumerate(sel.iterrows(), 1):
                path = Path(str(row["image_path"]))
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is None:
                    continue

                roi = (
                    int(row["xu_roi_x0"]),
                    int(row["xu_roi_y0"]),
                    int(row["xu_roi_x1"]),
                    int(row["xu_roi_y1"]),
                )
                mask, _ = xu_mask_and_stats(img, roi)
                if mask is None:
                    continue

                x0, y0, x1, y1 = roi
                crop = img[y0:y1, x0:x1]

                label = (
                    f"{label_group} #{rank}  "
                    f"t={float(row['sample_time_sec']):.0f}s  "
                    f"PBP={float(row['xu_pbp_v1']):.4f}"
                )
                tiles.append(make_pair_tile(crop, mask, label))

                review_rows.append({
                    "case_id": case_id,
                    "selection_group": label_group,
                    "selection_rank": rank,
                    "sample_time_sec": float(row["sample_time_sec"]),
                    "xu_pbp_v1": float(row["xu_pbp_v1"]),
                    "image_path": str(path),
                    "blood_stain_present_visual": "",
                    "mask_spatially_plausible": "",
                    "dominant_false_positive": "",
                    "manual_comment": "",
                })

            if tiles:
                section = add_title(
                    grid(tiles, ncol=2),
                    f"{case_id} | {label_group} | left=original ROI, right=Xu blood mask"
                )
                sections.append(section)

        if sections:
            width = max(x.shape[1] for x in sections)
            padded = []
            for x in sections:
                if x.shape[1] < width:
                    p = np.zeros((x.shape[0], width, 3), dtype=np.uint8)
                    p[:, :x.shape[1]] = x
                    x = p
                padded.append(x)
            spacer = np.zeros((18, width, 3), dtype=np.uint8)
            combined = padded[0]
            for sec in padded[1:]:
                combined = np.vstack([combined, spacer, sec])

            out_path = qc_dir / f"{case_id}_xu_pbp_qc.jpg"
            cv2.imwrite(str(out_path), combined)
            log(f"[qc] Saved: {out_path}", args.quiet)

    review = pd.DataFrame(review_rows)
    review_path = args.report_dir / "xu_pbp_manual_qc.csv"
    review.to_csv(review_path, index=False, encoding="utf-8-sig")
    return review_path


def case_summary(scored):
    ok = scored[scored["xu_rule_status"].eq("ok")].copy()
    rows = []

    for case_id, g in ok.groupby("case_id", sort=True):
        x = pd.to_numeric(g["xu_pbp_v1"], errors="coerce").dropna().to_numpy(dtype=float)
        rows.append({
            "case_id": case_id,
            "n_frames": len(x),
            "xu_sum_pbp_v1": float(np.sum(x)) if len(x) else np.nan,
            "xu_mean_pbp_v1": float(np.mean(x)) if len(x) else np.nan,
            "xu_median_pbp_v1": float(np.median(x)) if len(x) else np.nan,
            "xu_p90_pbp_v1": float(np.percentile(x, 90)) if len(x) else np.nan,
            "xu_p95_pbp_v1": float(np.percentile(x, 95)) if len(x) else np.nan,
            "xu_p99_pbp_v1": float(np.percentile(x, 99)) if len(x) else np.nan,
            "xu_max_pbp_v1": float(np.max(x)) if len(x) else np.nan,
        })

    return pd.DataFrame(rows)


def main():
    args = parse_args()

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    if args.output_csv.exists() and not args.overwrite:
        raise FileExistsError(
            f"{args.output_csv} exists. Use --overwrite to replace it."
        )

    d = load_sources(args)
    log(f"[INFO] frames to score={len(d)}", args.quiet)
    log(
        "[INFO] Xu rule: Gray<80, Red>14, "
        "Gray/Red < 0.38*(FrameGray/FrameRed)+0.24",
        args.quiet,
    )
    log(
        f"[INFO] spatial_domain={args.spatial_domain}; "
        "published thresholds are fixed and not re-tuned",
        args.quiet,
    )

    scored = compute_all(d, args)
    scored.to_csv(args.output_csv, index=False, encoding="utf-8-sig")

    summary = case_summary(scored)
    summary_path = args.report_dir / "xu_pbp_case_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    status = (
        scored["xu_rule_status"]
        .value_counts(dropna=False)
        .rename_axis("xu_rule_status")
        .reset_index(name="n_frames")
    )
    status.to_csv(
        args.report_dir / "xu_pbp_status_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    review_path = build_qc(scored, args)

    method = pd.DataFrame([{
        "method": "Xu et al. EJCTS 2022 blood-pixel rule",
        "tau_y": TAU_Y,
        "tau_r": TAU_R,
        "alpha": ALPHA,
        "beta": BETA,
        "rule": "Gray<80 AND Red>14 AND Gray/Red < 0.38*(FrameGray/FrameRed)+0.24",
        "spatial_domain": args.spatial_domain,
        "gray_conversion": "OpenCV COLOR_BGR2GRAY",
        "implementation_note": (
            "Thresholds are copied without re-tuning. In ROI mode, the published "
            "pixel rule is applied within the pre-existing surgical-field ROI; "
            "this is an adaptation of spatial domain rather than an exact reproduction "
            "of the original full-frame pipeline. The paper does not specify the "
            "exact RGB-to-gray conversion formula, so OpenCV grayscale conversion is used."
        ),
    }])
    method.to_csv(
        args.report_dir / "xu_pbp_method_record.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=== Status ===")
    print(status.to_string(index=False))
    print()
    print("=== Case summary ===")
    print(summary.to_string(index=False))
    print()
    print("Saved per-frame:", args.output_csv)
    print("Saved summary:", summary_path)
    print("Saved manual QC:", review_path)
    print("QC montages:", args.report_dir / "qc_montages")


if __name__ == "__main__":
    main()
