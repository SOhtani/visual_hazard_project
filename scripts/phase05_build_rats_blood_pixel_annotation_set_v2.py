#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import cv2


STRUCT = "structural_visibility_loss_v1"
LOWLIGHT = "low_light_or_blackout_ratio_v1"
WHITEOUT = "whiteout_ratio_v1"
SPECULAR = "specular_like_ratio_v1"
VEIL = "veil_low_contrast_score_v1"

BLOODLIKE = "blood_like_redness_ratio_v1"
FRESH = "fresh_red_candidate_ratio_v1"


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Build a technically gradable RATS blood-pixel annotation set. "
            "Technical-quality gating is performed before color-based enrichment."
        )
    )
    p.add_argument("--color-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--exclude-frame-qc", type=Path, default=None)
    p.add_argument("--seed", type=int, default=20260920)
    p.add_argument("--n-high-bloodlike", type=int, default=20)
    p.add_argument("--n-high-fresh", type=int, default=15)
    p.add_argument("--n-random", type=int, default=15)
    p.add_argument("--n-low-red", type=int, default=10)
    return p.parse_args()


def frame_key_df(d):
    return (
        d["case_id"].astype(str)
        + "||"
        + pd.to_numeric(d["sample_time_sec"], errors="coerce").round(3).astype(str)
    )


def sample_unique_cases(pool, n, rng, used_cases):
    if pool.empty:
        return pool.copy()

    x = pool.copy()
    x = x.loc[~x["case_id"].astype(str).isin(used_cases)].copy()

    # Randomize within the eligible stratum instead of taking the most extreme frames.
    x = x.iloc[rng.permutation(len(x))].copy()

    picked = []
    seen = set()
    for _, r in x.iterrows():
        c = str(r["case_id"])
        if c in seen or c in used_cases:
            continue
        picked.append(r)
        seen.add(c)
        if len(picked) >= n:
            break

    out = pd.DataFrame(picked)
    used_cases.update(seen)
    return out


def crop_roi(img, row):
    h, w = img.shape[:2]
    cols = ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]
    if all(c in row.index and pd.notna(row[c]) for c in cols):
        x0, y0, x1, y1 = [int(round(float(row[c]))) for c in cols]
        x0 = max(0, min(w - 1, x0))
        y0 = max(0, min(h - 1, y0))
        x1 = max(x0 + 1, min(w, x1))
        y1 = max(y0 + 1, min(h, y1))
        return img[y0:y1, x0:x1]
    return img


def contact_sheet(sel, out_path):
    width = 360
    thumbs = []

    for _, r in sel.iterrows():
        img = cv2.imread(str(r["image_path"]))
        if img is None:
            continue
        img = crop_roi(img, r)
        h, w = img.shape[:2]
        nh = max(1, int(round(h * width / w)))
        img = cv2.resize(img, (width, nh), interpolation=cv2.INTER_AREA)

        bar = 48
        canvas = np.zeros((nh + bar, width, 3), dtype=np.uint8)
        canvas[bar:] = img
        txt = (
            f'{r["selection_stratum"]} | {str(r["case_id"])} | '
            f't={float(r["sample_time_sec"]):.0f}s'
        )
        cv2.putText(
            canvas, txt, (8, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.44,
            (255, 255, 255), 1, cv2.LINE_AA
        )
        thumbs.append(canvas)

    if not thumbs:
        return

    max_h = max(x.shape[0] for x in thumbs)
    ncol = 3
    nrow = int(np.ceil(len(thumbs) / ncol))
    sheet = np.zeros((nrow * max_h, ncol * width, 3), dtype=np.uint8)

    for i, img in enumerate(thumbs):
        rr, cc = divmod(i, ncol)
        y = rr * max_h
        x = cc * width
        sheet[y:y + img.shape[0], x:x + img.shape[1]] = img

    cv2.imwrite(str(out_path), sheet)


def main():
    a = parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    d = pd.read_csv(a.color_csv, low_memory=False)

    needed = {
        "case_id", "sample_time_sec", "image_path",
        STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL,
        BLOODLIKE, FRESH,
    }
    missing = needed - set(d.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    for c in [STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL, BLOODLIKE, FRESH]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d = d.dropna(subset=list(needed)).copy()

    if a.exclude_frame_qc is not None and a.exclude_frame_qc.exists():
        old = pd.read_csv(a.exclude_frame_qc)
        if {"case_id", "sample_time_sec"}.issubset(old.columns):
            old_keys = set(frame_key_df(old))
            d = d.loc[~frame_key_df(d).isin(old_keys)].copy()

    # Annotation-suitability gate.
    # These are sampling/QC cutoffs, not inferential thresholds.
    gates = {
        STRUCT: float(d[STRUCT].quantile(0.90)),
        LOWLIGHT: float(d[LOWLIGHT].quantile(0.95)),
        WHITEOUT: float(d[WHITEOUT].quantile(0.95)),
        SPECULAR: float(d[SPECULAR].quantile(0.95)),
        VEIL: float(d[VEIL].quantile(0.95)),
    }

    gradable = d.copy()
    for metric, thr in gates.items():
        gradable = gradable.loc[gradable[metric] <= thr].copy()

    # Avoid only the absolute color extremes, which were highly enriched for
    # ungradable/technical artifacts in the first pilot.
    bl_q = gradable[BLOODLIKE].quantile([0.05, 0.25, 0.90, 0.98])
    fr_q = gradable[FRESH].quantile([0.90, 0.98])

    strata = [
        (
            "high_bloodlike_gradable",
            gradable[
                (gradable[BLOODLIKE] >= bl_q.loc[0.90])
                & (gradable[BLOODLIKE] <= bl_q.loc[0.98])
            ],
            a.n_high_bloodlike,
            BLOODLIKE,
        ),
        (
            "high_freshred_gradable",
            gradable[
                (gradable[FRESH] >= fr_q.loc[0.90])
                & (gradable[FRESH] <= fr_q.loc[0.98])
            ],
            a.n_high_fresh,
            FRESH,
        ),
        (
            "random_gradable",
            gradable,
            a.n_random,
            "random",
        ),
        (
            "low_red_control_gradable",
            gradable[
                (gradable[BLOODLIKE] >= bl_q.loc[0.05])
                & (gradable[BLOODLIKE] <= bl_q.loc[0.25])
            ],
            a.n_low_red,
            BLOODLIKE,
        ),
    ]

    used_cases = set()
    parts = []

    for name, pool, n, metric in strata:
        s = sample_unique_cases(pool, n, rng, used_cases)
        if len(s) < n:
            print(f"[WARN] {name}: requested {n}, selected {len(s)}")
        s = s.copy()
        s["selection_stratum"] = name
        s["selection_metric"] = metric
        if metric != "random":
            s["selection_metric_value"] = s[metric]
        else:
            s["selection_metric_value"] = np.nan
        parts.append(s)

    sel = pd.concat(parts, ignore_index=True)

    keep = [
        "case_id", "sample_time_sec", "image_path",
        "roi_x0", "roi_y0", "roi_x1", "roi_y1",
        STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL,
        BLOODLIKE, FRESH,
        "selection_stratum", "selection_metric", "selection_metric_value",
    ]
    keep = [c for c in keep if c in sel.columns]

    out_csv = a.output_dir / "rats_blood_pixel_annotation_frames_v2.csv"
    sel[keep].to_csv(out_csv, index=False, encoding="utf-8-sig")
    contact_sheet(
        sel,
        a.output_dir / "rats_blood_pixel_annotation_frames_v2_contact_sheet.jpg"
    )

    gate_df = pd.DataFrame([
        {
            "metric": m,
            "annotation_sampling_quantile": 0.90 if m == STRUCT else 0.95,
            "threshold": t,
        }
        for m, t in gates.items()
    ])
    gate_df.to_csv(
        a.output_dir / "rats_blood_pixel_annotation_v2_gradability_gate.csv",
        index=False, encoding="utf-8-sig"
    )

    print("=== Candidate-pool QC ===")
    print("Input frames:", len(d))
    print("Technically gradable pool:", len(gradable))
    print("Gradable fraction:", len(gradable) / len(d) if len(d) else np.nan)
    print()
    print("=== Sampling gates ===")
    print(gate_df.to_string(index=False))
    print()
    print("=== Selected annotation set ===")
    print("Frames:", len(sel))
    print("Unique cases:", sel["case_id"].astype(str).nunique())
    print(sel["selection_stratum"].value_counts().to_string())
    print()
    print("Saved:", out_csv)


if __name__ == "__main__":
    main()
