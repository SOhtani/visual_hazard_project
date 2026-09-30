#!/usr/bin/env python
from __future__ import annotations
import argparse, random
from pathlib import Path
import pandas as pd
from PIL import Image

WORKSPACE_TARGETS = [
    ("subcarinal", 5), ("inferior_hilum", 5), ("superior_hilum", 5),
    ("posterior_hilum", 5), ("anterior_hilum", 5), ("fissure", 5),
]
PATH_CANDIDATES = ["image_path", "frame_path", "image_full_path", "frame_full_path"]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--frame-source", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--seconds-each-side", type=int, default=5)
    p.add_argument("--gif-frame-ms", type=int, default=500)
    p.add_argument("--time-round-decimals", type=int, default=3)
    return p.parse_args()

def find_path_col(cols):
    for c in PATH_CANDIDATES:
        if c in cols:
            return c
    raise ValueError("No full image-path column found. Expected one of: " + ", ".join(PATH_CANDIDATES))

def build_lookup(g, decimals):
    out = {}
    for _, r in g.iterrows():
        t = pd.to_numeric(pd.Series([r["sample_time_sec"]]), errors="coerce").iloc[0]
        if pd.notna(t):
            out[round(float(t), decimals)] = r
    return out

def context_ok(lookup, t, side, decimals, path_col):
    for dt in range(-side, side + 1):
        k = round(float(t) + dt, decimals)
        if k not in lookup:
            return False
        if not Path(str(lookup[k][path_col])).exists():
            return False
    return True

def choose(df, mask, n, rng, selected_cases, lookups, side, decimals, path_col, category):
    idx = list(df.index[mask])
    rng.shuffle(idx)
    out = []
    for i in idx:
        r = df.loc[i]
        case = str(r["case_id"])
        if case in selected_cases:
            continue
        if not context_ok(lookups[case], float(r["sample_time_sec"]), side, decimals, path_col):
            continue
        selected_cases.add(case)
        out.append((i, category))
        if len(out) >= n:
            break
    return out

def make_gif(lookup, t, side, decimals, path_col, out_path, frame_ms):
    imgs = []
    for dt in range(-side, side + 1):
        k = round(float(t) + dt, decimals)
        imgs.append(Image.open(Path(str(lookup[k][path_col]))).convert("RGB"))
    imgs[0].save(out_path, save_all=True, append_images=imgs[1:], duration=frame_ms, loop=0, optimize=False)

def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gif_dir = args.output_dir / "temporal_gifs"
    gif_dir.mkdir(parents=True, exist_ok=True)

    hdr = pd.read_csv(args.frame_source, nrows=0)
    path_col = find_path_col(hdr.columns)
    need = ["case_id", "sample_time_sec", "workflow_level1_label", "workflow_level2_label", path_col]
    df = pd.read_csv(args.frame_source, usecols=need, low_memory=False)
    df["case_id"] = df["case_id"].astype("string").str.strip().str.upper()
    df["sample_time_sec"] = pd.to_numeric(df["sample_time_sec"], errors="coerce")
    df = df.dropna(subset=["case_id", "sample_time_sec"]).sort_values(["case_id", "sample_time_sec"])

    if df.duplicated(["case_id", "sample_time_sec"]).any():
        raise ValueError("Duplicate case/time rows in frame source.")

    lookups = {case: build_lookup(g, args.time_round_decimals) for case, g in df.groupby("case_id", sort=False)}
    rng = random.Random(args.seed)
    selected_cases, selections, shortfalls = set(), [], []

    for workspace, n in WORKSPACE_TARGETS:
        mask = df["workflow_level2_label"].astype(str).eq(workspace)
        picked = choose(df, mask, n, rng, selected_cases, lookups, args.seconds_each_side,
                        args.time_round_decimals, path_col, f"workspace:{workspace}")
        selections.extend(picked)
        if len(picked) < n:
            shortfalls.append((f"workspace:{workspace}", n, len(picked)))

    mask = df["workflow_level1_label"].astype(str).eq("LeakHemostasis")
    picked = choose(df, mask, 10, rng, selected_cases, lookups, args.seconds_each_side,
                    args.time_round_decimals, path_col, "phase:LeakHemostasis")
    selections.extend(picked)
    if len(picked) < 10:
        shortfalls.append(("phase:LeakHemostasis", 10, len(picked)))

    if len(selections) < 30:
        raise RuntimeError(f"Only {len(selections)} valid moments sampled.")

    rows = []
    for j, (idx, category) in enumerate(selections, 1):
        r = df.loc[idx]
        seg = f"OPP{j:03d}"
        gif_path = gif_dir / f"{seg}.gif"
        make_gif(lookups[str(r["case_id"])], float(r["sample_time_sec"]), args.seconds_each_side,
                 args.time_round_decimals, path_col, gif_path, args.gif_frame_ms)
        rows.append({
            "segment_id": seg, "case_id": r["case_id"], "anchor_time_sec": r["sample_time_sec"],
            "sampling_category": category, "workflow_level1_label": r["workflow_level1_label"],
            "workflow_level2_label": r["workflow_level2_label"],
            "still_image_path": r[path_col], "temporal_gif_path": str(gif_path),
        })

    mapping = pd.DataFrame(rows)

    still = mapping[["segment_id", "still_image_path"]].sample(frac=1, random_state=args.seed).reset_index(drop=True)
    temp = mapping[["segment_id", "temporal_gif_path"]].sample(frac=1, random_state=args.seed + 1).reset_index(drop=True)
    still["still_review_id"] = [f"S{i:03d}" for i in range(1, len(still)+1)]
    temp["temporal_review_id"] = [f"T{i:03d}" for i in range(1, len(temp)+1)]

    mapping = mapping.merge(still[["segment_id", "still_review_id"]], on="segment_id", validate="one_to_one")
    mapping = mapping.merge(temp[["segment_id", "temporal_review_id"]], on="segment_id", validate="one_to_one")

    mapping.to_csv(args.output_dir / "operative_phenotype_pilot_mapping.csv", index=False, encoding="utf-8-sig")
    still[["still_review_id", "still_image_path"]].rename(columns={"still_review_id":"review_id"}).to_csv(
        args.output_dir / "operative_phenotype_still_manifest.csv", index=False, encoding="utf-8-sig")
    temp[["temporal_review_id", "temporal_gif_path"]].rename(columns={"temporal_review_id":"review_id"}).to_csv(
        args.output_dir / "operative_phenotype_temporal_manifest.csv", index=False, encoding="utf-8-sig")

    print("Selected segments:", len(mapping))
    print("Selected cases:", mapping["case_id"].nunique())
    print(mapping["sampling_category"].value_counts().to_string())
    if shortfalls:
        print("Shortfalls:", shortfalls)
    print("Saved to:", args.output_dir)

if __name__ == "__main__":
    main()
