#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


STRUCT = "structural_visibility_loss_v1"
LOWLIGHT = "low_light_or_blackout_ratio_v1"
WHITEOUT = "whiteout_ratio_v1"
SPECULAR = "specular_like_ratio_v1"
VEIL = "veil_low_contrast_score_v1"

BLOODLIKE = "blood_like_redness_ratio_v1"
FRESH = "fresh_red_candidate_ratio_v1"

TECH_ALIASES = {
    STRUCT: ["structural_visibility_loss_v1", "composite_badness_v4", "focus_badness_v1"],
    LOWLIGHT: ["low_light_or_blackout_ratio_v1"],
    WHITEOUT: ["whiteout_ratio_v1", "saturation_ratio"],
    SPECULAR: ["specular_like_ratio_v1", "specular_ratio"],
    VEIL: ["veil_low_contrast_score_v1", "veil_smoke_mean"],
}

ROI_COLS = ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Build a technically gradable RATS blood-pixel annotation set. "
            "Missing technical metrics in the color CSV are filled from the "
            "canonical per-frame quality-metric directory before sampling."
        )
    )
    p.add_argument("--color-csv", required=True, type=Path)
    p.add_argument("--quality-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--exclude-frame-qc", type=Path, default=None)
    p.add_argument("--seed", type=int, default=20260920)
    p.add_argument("--n-high-bloodlike", type=int, default=20)
    p.add_argument("--n-high-fresh", type=int, default=15)
    p.add_argument("--n-random", type=int, default=15)
    p.add_argument("--n-low-red", type=int, default=10)
    return p.parse_args()


def normalize_path_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.replace("/", "\\", regex=False)
        .str.lower()
        .str.strip()
    )


def first_existing(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def load_quality_lookup(quality_dir: Path, needed_canonical: list[str], need_roi: bool):
    files = [
        p for p in sorted(quality_dir.glob("*_frame_scores.csv"))
        if not p.name.startswith("_")
    ]
    if not files:
        raise FileNotFoundError(f"No case quality CSVs found: {quality_dir}")

    parts = []
    source_map = {}

    for i, p in enumerate(files, 1):
        hdr = pd.read_csv(p, nrows=0)
        cols = list(hdr.columns)

        use = []
        for c in ["case_id", "sample_time_sec", "image_path"]:
            if c in cols:
                use.append(c)

        local_map = {}
        for canonical in needed_canonical:
            src = first_existing(cols, TECH_ALIASES[canonical])
            if src is not None:
                use.append(src)
                local_map[canonical] = src
                source_map.setdefault(canonical, src)

        if need_roi:
            for c in ROI_COLS:
                if c in cols:
                    use.append(c)

        use = list(dict.fromkeys(use))
        q = pd.read_csv(p, usecols=use)

        if "case_id" not in q.columns:
            q["case_id"] = p.stem.replace("_frame_scores", "")

        if "image_path" not in q.columns:
            raise ValueError(f"{p} has no image_path; cannot merge robustly.")

        out = q[["case_id", "image_path"]].copy()
        out["_join_path"] = normalize_path_series(q["image_path"])

        for canonical in needed_canonical:
            src = local_map.get(canonical)
            if src is None:
                out[canonical] = np.nan
            else:
                out[canonical] = pd.to_numeric(q[src], errors="coerce")

        if need_roi:
            for c in ROI_COLS:
                out[c] = pd.to_numeric(q[c], errors="coerce") if c in q.columns else np.nan

        parts.append(out)

        if i % 10 == 0 or i == len(files):
            print(f"[quality lookup] {i}/{len(files)}")

    lookup = pd.concat(parts, ignore_index=True)

    dup = lookup.duplicated("_join_path", keep=False)
    if dup.any():
        # Exact same path should be unique. Fail rather than silently duplicating rows.
        examples = lookup.loc[dup, "_join_path"].head(5).tolist()
        raise RuntimeError(
            "Duplicate image_path keys in quality lookup. "
            f"Examples: {examples}"
        )

    return lookup, source_map


def frame_key_df(d):
    return (
        d["case_id"].astype(str)
        + "||"
        + pd.to_numeric(d["sample_time_sec"], errors="coerce").round(3).astype(str)
    )


def sample_unique_cases(pool, n, rng, used_cases):
    if pool.empty:
        return pool.copy()

    x = pool.loc[~pool["case_id"].astype(str).isin(used_cases)].copy()
    if x.empty:
        return x

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

    used_cases.update(seen)
    return pd.DataFrame(picked)


def crop_roi(img, row):
    h, w = img.shape[:2]
    if all(c in row.index and pd.notna(row[c]) for c in ROI_COLS):
        x0, y0, x1, y1 = [int(round(float(row[c]))) for c in ROI_COLS]
        x0 = max(0, min(w - 1, x0))
        y0 = max(0, min(h - 1, y0))
        x1 = max(x0 + 1, min(w, x1))
        y1 = max(y0 + 1, min(h, y1))
        return img[y0:y1, x0:x1]
    return img


def make_contact_sheet(sel, out_path):
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

        bar = 50
        canvas = np.zeros((nh + bar, width, 3), dtype=np.uint8)
        canvas[bar:] = img

        txt = (
            f'{r["selection_stratum"]} | {r["case_id"]} | '
            f't={float(r["sample_time_sec"]):.0f}s'
        )
        cv2.putText(
            canvas, txt, (8, 31),
            cv2.FONT_HERSHEY_SIMPLEX, 0.43,
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

    base_required = {"case_id", "sample_time_sec", "image_path", BLOODLIKE, FRESH}
    missing_base = base_required - set(d.columns)
    if missing_base:
        raise ValueError(f"Color CSV missing base columns: {sorted(missing_base)}")

    d["_join_path"] = normalize_path_series(d["image_path"])

    # Resolve whatever technical metrics already exist in the color CSV.
    resolved = {}
    missing_tech = []

    for canonical, aliases in TECH_ALIASES.items():
        src = first_existing(d.columns, aliases)
        if src is not None:
            d[canonical] = pd.to_numeric(d[src], errors="coerce")
            resolved[canonical] = f"color_csv:{src}"
        else:
            missing_tech.append(canonical)

    need_roi = not all(c in d.columns for c in ROI_COLS)

    if missing_tech or need_roi:
        print("Technical metrics/ROI missing from color CSV; loading quality lookup...")
        lookup, source_map = load_quality_lookup(
            a.quality_dir,
            needed_canonical=missing_tech,
            need_roi=need_roi,
        )

        merge_cols = ["_join_path"] + missing_tech
        if need_roi:
            merge_cols += ROI_COLS

        before = len(d)
        d = d.merge(
            lookup[merge_cols],
            on="_join_path",
            how="left",
            validate="many_to_one",
            suffixes=("", "_quality"),
        )
        if len(d) != before:
            raise RuntimeError("Unexpected row-count change after quality merge.")

        for canonical in missing_tech:
            resolved[canonical] = f"quality_dir:{source_map.get(canonical, canonical)}"

        if need_roi:
            for c in ROI_COLS:
                if c not in d.columns and f"{c}_quality" in d.columns:
                    d[c] = d[f"{c}_quality"]
                elif c in d.columns and f"{c}_quality" in d.columns:
                    d[c] = d[c].fillna(d[f"{c}_quality"])

    print()
    print("=== Resolved technical metrics ===")
    for canonical in [STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL]:
        print(f"{canonical} <- {resolved.get(canonical, 'UNRESOLVED')}")
    print()

    unresolved = [c for c in [STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL] if c not in d.columns]
    if unresolved:
        raise ValueError(f"Unresolved technical metrics after quality merge: {unresolved}")

    for c in [STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL, BLOODLIKE, FRESH]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    needed = [
        "case_id", "sample_time_sec", "image_path",
        STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL,
        BLOODLIKE, FRESH,
    ]
    n_before_nonmissing = len(d)
    d = d.dropna(subset=needed).copy()
    print(f"Rows after required-metric nonmissing filter: {len(d)}/{n_before_nonmissing}")

    # Exclude all frames already reviewed in the failed first pilot.
    if a.exclude_frame_qc is not None and a.exclude_frame_qc.exists():
        old = pd.read_csv(a.exclude_frame_qc)
        if {"case_id", "sample_time_sec"}.issubset(old.columns):
            old_keys = set(frame_key_df(old))
            before = len(d)
            d = d.loc[~frame_key_df(d).isin(old_keys)].copy()
            print(f"Excluded prior reviewed frames: {before - len(d)}")

    # Sampling-only gradability gate.
    gates = {
        STRUCT: float(d[STRUCT].quantile(0.90)),
        LOWLIGHT: float(d[LOWLIGHT].quantile(0.95)),
        WHITEOUT: float(d[WHITEOUT].quantile(0.95)),
        SPECULAR: float(d[SPECULAR].quantile(0.95)),
        VEIL: float(d[VEIL].quantile(0.95)),
    }

    gradable = d.copy()
    for metric, threshold in gates.items():
        gradable = gradable.loc[gradable[metric] <= threshold].copy()

    if gradable.empty:
        raise RuntimeError("Gradability gate produced zero candidate frames.")

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
        ("random_gradable", gradable, a.n_random, "random"),
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
        s["selection_metric_value"] = (
            s[metric] if metric != "random" else np.nan
        )
        parts.append(s)

    sel = pd.concat(parts, ignore_index=True)

    keep = [
        "case_id", "sample_time_sec", "image_path",
        *ROI_COLS,
        STRUCT, LOWLIGHT, WHITEOUT, SPECULAR, VEIL,
        BLOODLIKE, FRESH,
        "selection_stratum", "selection_metric", "selection_metric_value",
    ]
    keep = [c for c in keep if c in sel.columns]

    out_csv = a.output_dir / "rats_blood_pixel_annotation_frames_v2.csv"
    sel[keep].to_csv(out_csv, index=False, encoding="utf-8-sig")

    make_contact_sheet(
        sel,
        a.output_dir / "rats_blood_pixel_annotation_frames_v2_contact_sheet.jpg",
    )

    gate_rows = []
    for metric, threshold in gates.items():
        gate_rows.append({
            "metric": metric,
            "sampling_gate_quantile": 0.90 if metric == STRUCT else 0.95,
            "threshold": threshold,
            "purpose": "annotation-candidate gradability gate only",
        })
    pd.DataFrame(gate_rows).to_csv(
        a.output_dir / "rats_blood_pixel_annotation_v2_gradability_gate.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=== Candidate-pool QC ===")
    print("Input eligible rows:", len(d))
    print("Technically gradable pool:", len(gradable))
    print("Gradable fraction:", f"{len(gradable) / len(d):.4f}")
    print()
    print("=== Sampling gates ===")
    print(pd.DataFrame(gate_rows).to_string(index=False))
    print()
    print("=== Selected annotation set ===")
    print("Frames:", len(sel))
    print("Unique cases:", sel["case_id"].astype(str).nunique())
    print(sel["selection_stratum"].value_counts().to_string())
    print()
    print("Saved:", out_csv)


if __name__ == "__main__":
    main()
