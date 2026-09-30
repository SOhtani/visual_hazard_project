#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


REF_W = 1920
REF_H = 1080
REF_ROI = (395, 101, 1528, 889)
ROI_FRACS = (
    REF_ROI[0] / REF_W,
    REF_ROI[1] / REF_H,
    REF_ROI[2] / REF_W,
    REF_ROI[3] / REF_H,
)


def parse_args():
    p = argparse.ArgumentParser(
        description="Create Level-0 / ROI QC contact sheets for neo cases."
    )
    p.add_argument("--predictions", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--thumb-width", type=int, default=480)
    return p.parse_args()


def scaled_roi(w: int, h: int):
    x0 = int(round(w * ROI_FRACS[0]))
    y0 = int(round(h * ROI_FRACS[1]))
    x1 = int(round(w * ROI_FRACS[2]))
    y1 = int(round(h * ROI_FRACS[3]))
    return x0, y0, x1, y1


def take_even(g: pd.DataFrame, n: int):
    if len(g) <= n:
        return g.copy()
    idx = np.linspace(0, len(g) - 1, n).round().astype(int)
    return g.iloc[np.unique(idx)].copy()


def choose_rows(g: pd.DataFrame):
    picked = []

    inside = g[g["level0_pred_semantic"].eq("InsideBody")].sort_values("sample_time_sec")
    outside = g[g["level0_pred_semantic"].eq("OutsideBody")].sort_values("sample_time_sec")

    x = take_even(inside, 4)
    x["qc_reason"] = "inside_even"
    picked.append(x)

    x = take_even(outside, 3)
    x["qc_reason"] = "outside_even"
    picked.append(x)

    low = g.assign(
        margin=(g["level0_ensemble_confidence"] - 0.5).abs()
    ).sort_values(["margin", "sample_time_sec"]).head(3).copy()
    low["qc_reason"] = "lowest_confidence"
    picked.append(low)

    out = pd.concat(picked, ignore_index=True)
    out = out.drop_duplicates(subset=["frame_path"]).sort_values(
        ["qc_reason", "sample_time_sec"]
    )
    return out


def annotate(img, row):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = scaled_roi(w, h)

    cv2.rectangle(img, (x0, y0), (x1, y1), (255, 255, 255), 3)

    label = str(row["level0_pred_semantic"])
    conf = float(row["level0_ensemble_confidence"])
    t = float(row["sample_time_sec"])
    reason = str(row["qc_reason"])
    text = f"{label}  conf={conf:.3f}  t={t:.0f}s  {reason}"

    cv2.rectangle(img, (0, 0), (w, 48), (0, 0, 0), -1)
    cv2.putText(
        img, text, (12, 32),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA
    )
    return img


def make_sheet(images, thumb_width=480, ncol=3):
    thumbs = []
    for img in images:
        h, w = img.shape[:2]
        scale = thumb_width / float(w)
        th = max(1, int(round(h * scale)))
        thumbs.append(cv2.resize(img, (thumb_width, th), interpolation=cv2.INTER_AREA))

    max_h = max(x.shape[0] for x in thumbs)
    nrow = int(math.ceil(len(thumbs) / ncol))
    sheet = np.zeros((nrow * max_h, ncol * thumb_width, 3), dtype=np.uint8)

    for i, img in enumerate(thumbs):
        r, c = divmod(i, ncol)
        y = r * max_h
        x = c * thumb_width
        sheet[y:y + img.shape[0], x:x + img.shape[1]] = img
    return sheet


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    d = pd.read_csv(args.predictions)
    required = {
        "case_id", "sample_time_sec", "frame_path",
        "level0_pred_semantic", "level0_ensemble_confidence"
    }
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    manifest_rows = []

    for case_id, g in d.groupby("case_id", sort=True):
        q = choose_rows(g)
        imgs = []
        kept = []

        for _, row in q.iterrows():
            p = Path(str(row["frame_path"]))
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is None:
                continue
            img = annotate(img, row)
            imgs.append(img)
            kept.append(row)

        if not imgs:
            continue

        sheet = make_sheet(imgs, thumb_width=args.thumb_width)
        out_path = args.output_dir / f"{case_id}_level0_roi_qc.jpg"
        cv2.imwrite(str(out_path), sheet)
        print("Saved:", out_path)

        for row in kept:
            manifest_rows.append(
                {
                    "case_id": case_id,
                    "sample_time_sec": row["sample_time_sec"],
                    "frame_path": row["frame_path"],
                    "level0_pred_semantic": row["level0_pred_semantic"],
                    "level0_ensemble_confidence": row["level0_ensemble_confidence"],
                    "qc_reason": row["qc_reason"],
                    "contact_sheet": str(out_path),
                }
            )

    pd.DataFrame(manifest_rows).to_csv(
        args.output_dir / "neo_level0_roi_qc_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()
