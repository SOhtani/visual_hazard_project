#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_args():
    p = argparse.ArgumentParser(description="Export internal visual-audit contact sheets from Phase-01 candidate pool.")
    p.add_argument("--candidate-pool", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--n-per-stratum", type=int, default=8)
    p.add_argument("--per-case-cap", type=int, default=3)
    p.add_argument("--min-gap-sec", type=float, default=60.0)
    p.add_argument("--seed", type=int, default=20260918)
    p.add_argument("--thumb-width", type=int, default=420)
    p.add_argument("--thumb-height", type=int, default=300)
    p.add_argument("--columns", type=int, default=4)
    return p.parse_args()


def b(df, col):
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[col]
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna("").astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y", "t"})


def moment_key(df):
    case = df["case_id"].astype(str).str.strip().str.upper()
    t = pd.to_numeric(df["sample_time_sec"], errors="coerce")
    return case + "|" + t.round(3).map(lambda x: f"{x:.3f}" if pd.notna(x) else "NA")


def strata(df):
    blur_h, blur_x = b(df, "cand_blur_high"), b(df, "cand_blur_extreme")
    smoke_h, smoke_x = b(df, "cand_smoke_temporal_proxy"), b(df, "cand_smoke_extreme_temporal_proxy")
    glare_h, glare_x = b(df, "cand_glare_high"), b(df, "cand_glare_extreme")
    white_h, white_x = b(df, "cand_whiteout_high"), b(df, "cand_whiteout_extreme")
    low_h, low_x = b(df, "cand_lowlight_high"), b(df, "cand_lowlight_extreme")
    obs_h, obs_x = b(df, "cand_obstruction_high"), b(df, "cand_obstruction_extreme")
    near_r, near_s = b(df, "cand_near_contact_relaxed_proxy"), b(df, "cand_near_contact_strict_proxy")
    lens = b(df, "cand_lens_persistent_degradation_proxy")

    return [
        ("near_contact_strict_proxy", near_s, "Strict near-contact/wall-view retrieval proxy."),
        ("near_contact_relaxed_only", near_r & ~near_s, "Relaxed near-contact proxy excluding strict candidates."),
        ("smoke_extreme_temporal_proxy", smoke_x, "Extreme temporal smoke retrieval proxy."),
        ("smoke_temporal_high_only", smoke_h & ~smoke_x, "High temporal smoke proxy excluding extreme candidates."),
        ("lens_persistent_degradation_proxy", lens, "Persistent degradation proxy; not semantic lens ground truth."),
        ("blur_extreme", blur_x, "Extreme focus-badness candidates."),
        ("blur_high_only", blur_h & ~blur_x, "High focus-badness excluding extreme candidates."),
        ("obstruction_extreme", obs_x, "Extreme low-structure / obstruction proxy."),
        ("obstruction_high_only", obs_h & ~obs_x, "High obstruction proxy excluding extreme candidates."),
        ("glare_extreme", glare_x, "Extreme glare/specular candidates."),
        ("glare_high_only", glare_h & ~glare_x, "High glare excluding extreme candidates."),
        ("whiteout_extreme", white_x, "Extreme saturation/whiteout candidates."),
        ("whiteout_high_only", white_h & ~white_x, "High whiteout excluding extreme candidates."),
        ("lowlight_extreme", low_x, "Extreme low-light/blackout candidates."),
        ("lowlight_high_only", low_h & ~low_x, "High low-light excluding extreme candidates."),
        ("blur_obstruction_overlap", blur_h & obs_h, "Overlap of blur and obstruction retrieval."),
        ("glare_whiteout_overlap", glare_h & white_h, "Overlap of glare and whiteout retrieval."),
    ]


def existing_path(v):
    if pd.isna(v):
        return None
    p = Path(str(v).strip().strip('"'))
    return p if p.exists() else None


def can_take(row, selected_keys, case_counts, case_times, per_case_cap, min_gap_sec):
    key = row["_moment_key"]
    if key in selected_keys:
        return False
    case = str(row["case_id"]).upper()
    t = float(row["sample_time_sec"])
    if case_counts.get(case, 0) >= per_case_cap:
        return False
    if any(abs(t - pt) < min_gap_sec for pt in case_times.get(case, [])):
        return False
    return existing_path(row["image_path"]) is not None


def choose(df, mask, n, rng, selected_keys, case_counts, case_times, per_case_cap, min_gap_sec):
    pool = df.loc[mask].copy()
    pool = pool[pool["sample_time_sec"].notna() & pool["image_path"].notna()]
    idx = list(pool.index)
    rng.shuffle(idx)
    chosen = []
    for i in idx:
        row = pool.loc[i]
        if not can_take(row, selected_keys, case_counts, case_times, per_case_cap, min_gap_sec):
            continue
        chosen.append(i)
        key = row["_moment_key"]
        case = str(row["case_id"]).upper()
        t = float(row["sample_time_sec"])
        selected_keys.add(key)
        case_counts[case] = case_counts.get(case, 0) + 1
        case_times.setdefault(case, []).append(t)
        if len(chosen) >= n:
            break
    return pool.loc[chosen].copy()


def make_sheet(rows, title, note, out_path, thumb_w, thumb_h, cols):
    if rows.empty:
        return
    font = ImageFont.load_default()
    pad, label_h, title_h = 10, 42, 54
    nrows = math.ceil(len(rows) / cols)
    cell_w = thumb_w + 2 * pad
    cell_h = thumb_h + label_h + 2 * pad
    canvas = Image.new("RGB", (cols * cell_w, title_h + nrows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), title, fill="black", font=font)
    draw.text((12, 26), note, fill="black", font=font)

    for j, (_, row) in enumerate(rows.iterrows()):
        c, r = j % cols, j // cols
        x0, y0 = c * cell_w + pad, title_h + r * cell_h + pad
        p = existing_path(row["image_path"])
        if p is None:
            continue
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im = ImageOps.contain(im, (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        except Exception:
            continue
        bx = x0 + (thumb_w - im.width) // 2
        by = y0 + (thumb_h - im.height) // 2
        canvas.paste(im, (bx, by))
        label = f"{row['audit_review_id']} | {row['case_id']} | t={float(row['sample_time_sec']):.0f}s"
        draw.text((x0, y0 + thumb_h + 6), label, fill="black", font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main():
    args = parse_args()
    if not args.candidate_pool.exists():
        raise FileNotFoundError(args.candidate_pool)

    outdir = args.output_dir
    sheets_dir = outdir / "contact_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.candidate_pool, low_memory=False)
    for c in ["case_id", "sample_time_sec", "image_path"]:
        if c not in df.columns:
            raise ValueError(f"Missing required column: {c}")

    df["sample_time_sec"] = pd.to_numeric(df["sample_time_sec"], errors="coerce")
    df["_moment_key"] = moment_key(df)

    rng = random.Random(args.seed)
    selected_keys, case_counts, case_times = set(), {}, {}
    selected_parts = []
    summary_rows = []
    counter = 1

    for name, mask, note in strata(df):
        candidate_count = int(mask.fillna(False).sum())
        sel = choose(
            df, mask.fillna(False), args.n_per_stratum, rng,
            selected_keys, case_counts, case_times,
            args.per_case_cap, args.min_gap_sec
        )
        if not sel.empty:
            sel = sel.copy()
            sel["audit_stratum"] = name
            sel["audit_stratum_note"] = note
            ids = [f"AUD{counter+i:03d}" for i in range(len(sel))]
            counter += len(sel)
            sel["audit_review_id"] = ids
            selected_parts.append(sel)
            make_sheet(
                sel, name, note, sheets_dir / f"{name}.png",
                args.thumb_width, args.thumb_height, args.columns
            )
        summary_rows.append({
            "audit_stratum": name,
            "candidate_count_before_selection": candidate_count,
            "selected_count": len(sel),
            "target_n": args.n_per_stratum,
            "note": note
        })

    selected = pd.concat(selected_parts, ignore_index=True, sort=False) if selected_parts else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)

    reviewer_cols = ["audit_review_id", "audit_stratum", "case_id", "sample_time_sec", "image_path"]
    reviewer = selected[reviewer_cols].copy() if not selected.empty else pd.DataFrame(columns=reviewer_cols)

    selected.to_csv(outdir / "phase01_targeted_visual_audit_selected_full_metadata.csv", index=False, encoding="utf-8-sig")
    reviewer.to_csv(outdir / "phase01_targeted_visual_audit_manifest.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(outdir / "phase01_targeted_visual_audit_summary.csv", index=False, encoding="utf-8-sig")

    readme = f"""# Phase 01 targeted candidate visual audit

Internal retrieval-quality audit only; not the final calibration set.

- candidate pool: {args.candidate_pool}
- n per stratum: {args.n_per_stratum}
- per-case cap across audit: {args.per_case_cap}
- minimum same-case separation: {args.min_gap_sec} sec
- seed: {args.seed}

Exact metric values are not drawn on contact sheets to reduce anchoring.
Lens, smoke, and near-contact rows remain retrieval proxies until surgeon review.
"""
    (outdir / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    print("Done.")
    print(f"Candidate pool rows: {len(df):,}")
    print(f"Unique audit frames selected: {len(selected):,}")
    print()
    print(summary[["audit_stratum", "candidate_count_before_selection", "selected_count"]].to_string(index=False))
    print()
    print(f"Saved to: {outdir}")


if __name__ == "__main__":
    main()
