#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


XU_ORIGINAL = {
    "tau_y": 80.0,
    "tau_r": 14.0,
    "alpha": 0.38,
    "beta": 0.24,
}


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Apply the final RATS-recalibrated blood-pixel rule to technically valid "
            "1-fps frames and create side-by-side visual QC against the original Xu rule. "
            "Designed for qualitative post-calibration QC, not for performance estimation."
        )
    )
    p.add_argument("--metrics-dir", required=True, type=Path)
    p.add_argument("--rule-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument(
        "--labels-csv",
        type=Path,
        default=None,
        help=(
            "Optional sparse annotation CSV used for calibration. "
            "If supplied with --unseen-cases-only, cases appearing in this file are excluded."
        ),
    )
    p.add_argument(
        "--unseen-cases-only",
        action="store_true",
        help="Restrict QC to cases absent from --labels-csv.",
    )
    p.add_argument(
        "--case",
        nargs="*",
        default=None,
        help="Optional explicit case_id list. Applied after unseen-case filtering.",
    )
    p.add_argument("--n-top-per-case", type=int, default=4)
    p.add_argument("--n-mid-per-case", type=int, default=1)
    p.add_argument("--n-low-per-case", type=int, default=1)
    p.add_argument("--min-separation-sec", type=float, default=30.0)
    p.add_argument("--thumb-width", type=int, default=320)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def log(msg, quiet=False):
    if not quiet:
        print(msg, flush=True)


def load_final_rule(path: Path):
    d = pd.read_csv(path)
    if len(d) != 1:
        raise ValueError(f"Expected exactly one final rule row in {path}; got {len(d)}")
    row = d.iloc[0]
    needed = ["tau_y", "tau_r", "alpha", "beta"]
    missing = [c for c in needed if c not in d.columns]
    if missing:
        raise ValueError(f"Rule CSV missing columns: {missing}")
    return {c: float(row[c]) for c in needed}


def case_files(root: Path):
    files = sorted(root.glob("*_frame_scores.csv"))
    return [p for p in files if not p.name.startswith("_")]


def case_id_from_file(path: Path):
    return path.stem.replace("_frame_scores", "")


def load_case(path: Path):
    d = pd.read_csv(path)
    required = {
        "case_id",
        "sample_time_sec",
        "image_path",
        "roi_x0",
        "roi_y0",
        "roi_x1",
        "roi_y1",
    }
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")
    if "metric_status" in d.columns:
        d = d[d["metric_status"].astype(str).eq("ok")].copy()
    d["sample_time_sec"] = pd.to_numeric(d["sample_time_sec"], errors="coerce")
    return d.dropna(subset=["sample_time_sec", "image_path"]).copy()


def roi_bounds(row, width, height):
    x0 = int(round(float(row["roi_x0"])))
    y0 = int(round(float(row["roi_y0"])))
    x1 = int(round(float(row["roi_x1"])))
    y1 = int(round(float(row["roi_y1"])))
    x0 = max(0, min(width - 1, x0))
    y0 = max(0, min(height - 1, y0))
    x1 = max(x0 + 1, min(width, x1))
    y1 = max(y0 + 1, min(height, y1))
    return x0, y0, x1, y1


def blood_mask(crop_bgr, params):
    red = crop_bgr[:, :, 2].astype(np.float32)
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    frame_red = float(red.mean())
    frame_gray = float(gray.mean())
    if frame_red <= 0:
        mask = np.zeros(gray.shape, dtype=bool)
        return mask, np.nan

    dyn = params["alpha"] * (frame_gray / frame_red) + params["beta"]
    ratio = np.divide(
        gray,
        red,
        out=np.full_like(gray, np.inf, dtype=np.float32),
        where=red > 0,
    )

    mask = (
        (gray < params["tau_y"])
        & (red > params["tau_r"])
        & (ratio < dyn)
    )
    pbp = float(mask.mean())
    return mask, pbp


def score_case(d: pd.DataFrame, rats_rule, quiet=False):
    rows = []
    for i, (_, row) in enumerate(d.iterrows(), 1):
        path = Path(str(row["image_path"]))
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            continue

        h, w = img.shape[:2]
        roi = roi_bounds(row, w, h)
        x0, y0, x1, y1 = roi
        crop = img[y0:y1, x0:x1]

        rats_mask, rats_pbp = blood_mask(crop, rats_rule)
        xu_mask, xu_pbp = blood_mask(crop, XU_ORIGINAL)

        rows.append(
            {
                "case_id": str(row["case_id"]),
                "sample_time_sec": float(row["sample_time_sec"]),
                "image_path": str(path),
                "roi_x0": x0,
                "roi_y0": y0,
                "roi_x1": x1,
                "roi_y1": y1,
                "rats_pbp_v1": rats_pbp,
                "xu_original_pbp_v1": xu_pbp,
                "rats_minus_xu_pbp": (
                    rats_pbp - xu_pbp
                    if np.isfinite(rats_pbp) and np.isfinite(xu_pbp)
                    else np.nan
                ),
            }
        )
        if i % 1000 == 0:
            log(f"  scored {i}/{len(d)}", quiet)

    return pd.DataFrame(rows)


def select_separated(g, sort_col, ascending, n, min_sep):
    x = g.dropna(subset=[sort_col, "sample_time_sec"]).sort_values(
        sort_col, ascending=ascending
    )
    chosen = []
    times = []
    for idx, row in x.iterrows():
        t = float(row["sample_time_sec"])
        if all(abs(t - z) >= min_sep for z in times):
            chosen.append(idx)
            times.append(t)
        if len(chosen) >= n:
            break
    return x.loc[chosen].copy()


def select_mid(g, n, min_sep):
    x = g.dropna(subset=["rats_pbp_v1"]).copy()
    if x.empty or n <= 0:
        return x.iloc[0:0].copy()
    med = float(x["rats_pbp_v1"].median())
    x["_dist_mid"] = (x["rats_pbp_v1"] - med).abs()
    return select_separated(
        x, "_dist_mid", ascending=True, n=n, min_sep=min_sep
    )


def mask_panel(crop, mask, label, width):
    h, w = crop.shape[:2]
    scale = width / float(w)
    nh = max(1, int(round(h * scale)))

    image = cv2.resize(crop, (width, nh), interpolation=cv2.INTER_AREA)

    mask8 = (mask.astype(np.uint8) * 255)
    mask3 = cv2.cvtColor(mask8, cv2.COLOR_GRAY2BGR)
    mask3 = cv2.resize(mask3, (width, nh), interpolation=cv2.INTER_NEAREST)

    panel = np.zeros((nh + 42, width, 3), dtype=np.uint8)
    panel[42:] = mask3 if label != "ORIGINAL" else image
    cv2.putText(
        panel, label, (8, 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
        (255, 255, 255), 1, cv2.LINE_AA
    )
    return panel


def make_triplet(row, rats_rule, thumb_width):
    path = Path(str(row["image_path"]))
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return None

    x0 = int(row["roi_x0"])
    y0 = int(row["roi_y0"])
    x1 = int(row["roi_x1"])
    y1 = int(row["roi_y1"])
    crop = img[y0:y1, x0:x1]

    rats_mask, rats_pbp = blood_mask(crop, rats_rule)
    xu_mask, xu_pbp = blood_mask(crop, XU_ORIGINAL)

    orig = mask_panel(crop, rats_mask, "ORIGINAL", thumb_width)
    xu = mask_panel(
        crop, xu_mask,
        f"XU  PBP={xu_pbp:.4f}",
        thumb_width
    )
    rats = mask_panel(
        crop, rats_mask,
        f"RATS  PBP={rats_pbp:.4f}",
        thumb_width
    )

    triplet = np.hstack([orig, xu, rats])

    title_h = 48
    canvas = np.zeros(
        (triplet.shape[0] + title_h, triplet.shape[1], 3),
        dtype=np.uint8
    )
    canvas[title_h:] = triplet
    title = (
        f"{row['selection_group']} | "
        f"t={float(row['sample_time_sec']):.0f}s | "
        "left=original, center=Xu mask, right=RATS mask"
    )
    cv2.putText(
        canvas, title, (10, 31),
        cv2.FONT_HERSHEY_SIMPLEX, 0.58,
        (255, 255, 255), 1, cv2.LINE_AA
    )
    return canvas


def stack_tiles(tiles, ncol=1):
    if not tiles:
        return None
    max_w = max(x.shape[1] for x in tiles)
    padded = []
    for x in tiles:
        if x.shape[1] < max_w:
            p = np.zeros((x.shape[0], max_w, 3), dtype=np.uint8)
            p[:, :x.shape[1]] = x
            x = p
        padded.append(x)
    gap = np.zeros((14, max_w, 3), dtype=np.uint8)
    out = padded[0]
    for x in padded[1:]:
        out = np.vstack([out, gap, x])
    return out


def build_qc_for_case(scored, rats_rule, args, out_dir):
    top = select_separated(
        scored, "rats_pbp_v1", False,
        args.n_top_per_case, args.min_separation_sec
    )
    mid = select_mid(
        scored, args.n_mid_per_case, args.min_separation_sec
    )
    low = select_separated(
        scored, "rats_pbp_v1", True,
        args.n_low_per_case, args.min_separation_sec
    )

    parts = []
    for label, d in [("TOP", top), ("MID", mid), ("LOW", low)]:
        z = d.copy()
        z["selection_group"] = label
        parts.append(z)

    selected = pd.concat(parts, ignore_index=True)
    tiles = []

    for _, row in selected.iterrows():
        tile = make_triplet(row, rats_rule, args.thumb_width)
        if tile is not None:
            tiles.append(tile)

    sheet = stack_tiles(tiles)
    if sheet is None:
        return selected

    case_id = str(scored.iloc[0]["case_id"])
    out_path = out_dir / f"{case_id}_rats_blood_rule_qc.jpg"
    cv2.imwrite(str(out_path), sheet)
    log(f"[QC] Saved: {out_path}", args.quiet)
    selected["qc_montage"] = str(out_path)
    return selected


def case_summary(scored):
    x = scored["rats_pbp_v1"].dropna().to_numpy(dtype=float)
    y = scored["xu_original_pbp_v1"].dropna().to_numpy(dtype=float)
    return {
        "case_id": str(scored.iloc[0]["case_id"]),
        "n_frames": len(scored),
        "rats_mean_pbp": float(np.mean(x)) if len(x) else np.nan,
        "rats_median_pbp": float(np.median(x)) if len(x) else np.nan,
        "rats_p90_pbp": float(np.percentile(x, 90)) if len(x) else np.nan,
        "rats_p95_pbp": float(np.percentile(x, 95)) if len(x) else np.nan,
        "rats_p99_pbp": float(np.percentile(x, 99)) if len(x) else np.nan,
        "xu_mean_pbp": float(np.mean(y)) if len(y) else np.nan,
        "xu_p99_pbp": float(np.percentile(y, 99)) if len(y) else np.nan,
    }


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir = args.output_dir / "qc_montages"
    qc_dir.mkdir(parents=True, exist_ok=True)

    rats_rule = load_final_rule(args.rule_csv)
    print("=== RATS final rule ===")
    print(rats_rule)

    files = case_files(args.metrics_dir)
    if not files:
        raise FileNotFoundError(f"No case CSVs in {args.metrics_dir}")

    calibration_cases = set()
    if args.labels_csv is not None:
        lab = pd.read_csv(args.labels_csv, usecols=["case_id"])
        calibration_cases = set(lab["case_id"].astype(str).unique())

    if args.unseen_cases_only:
        if args.labels_csv is None:
            raise ValueError("--unseen-cases-only requires --labels-csv")
        files = [
            p for p in files
            if case_id_from_file(p) not in calibration_cases
        ]

    if args.case:
        wanted = set(map(str, args.case))
        files = [
            p for p in files
            if case_id_from_file(p) in wanted
        ]

    if not files:
        raise RuntimeError("No cases remain after filtering.")

    print()
    print("=== QC case set ===")
    print("Cases:", len(files))
    for p in files:
        print(" ", case_id_from_file(p))

    all_scores = []
    summaries = []
    review_rows = []

    for i, p in enumerate(files, 1):
        cid = case_id_from_file(p)
        print(f"[{i}/{len(files)}] {cid}")
        d = load_case(p)
        scored = score_case(d, rats_rule, args.quiet)
        if scored.empty:
            continue

        all_scores.append(scored)
        summaries.append(case_summary(scored))
        selected = build_qc_for_case(
            scored, rats_rule, args, qc_dir
        )
        review_rows.append(selected)

    scores = pd.concat(all_scores, ignore_index=True)
    summary = pd.DataFrame(summaries)
    review = pd.concat(review_rows, ignore_index=True)

    scores_path = args.output_dir / "rats_blood_rule_unseen_case_frame_scores.csv"
    summary_path = args.output_dir / "rats_blood_rule_unseen_case_summary.csv"
    review_path = args.output_dir / "rats_blood_rule_visual_qc_manifest.csv"

    if scores_path.exists() and not args.overwrite:
        raise FileExistsError(f"{scores_path} exists; use --overwrite.")

    scores.to_csv(scores_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    for c in [
        "visual_blood_present",
        "rats_mask_spatially_plausible",
        "xu_mask_spatially_plausible",
        "dominant_rats_false_positive",
        "manual_comment",
    ]:
        review[c] = ""
    review.to_csv(review_path, index=False, encoding="utf-8-sig")

    rule_record = pd.DataFrame([{
        "rats_tau_y": rats_rule["tau_y"],
        "rats_tau_r": rats_rule["tau_r"],
        "rats_alpha": rats_rule["alpha"],
        "rats_beta": rats_rule["beta"],
        "xu_tau_y": XU_ORIGINAL["tau_y"],
        "xu_tau_r": XU_ORIGINAL["tau_r"],
        "xu_alpha": XU_ORIGINAL["alpha"],
        "xu_beta": XU_ORIGINAL["beta"],
        "qc_scope": (
            "qualitative visual QC on cases not represented in the calibration "
            "annotation set" if args.unseen_cases_only
            else "qualitative visual QC"
        ),
        "performance_claim": (
            "Do not estimate sensitivity/specificity from this montage selection. "
            "Formal performance comes from case-grouped cross-validation on sparse labels."
        ),
    }])
    rule_record.to_csv(
        args.output_dir / "rats_blood_rule_visual_qc_method_record.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=== Case summary ===")
    print(summary.to_string(index=False))
    print()
    print("Saved frame scores:", scores_path)
    print("Saved QC manifest:", review_path)
    print("QC montages:", qc_dir)


if __name__ == "__main__":
    main()
