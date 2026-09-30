#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

LABELS = [
    "near_contact",
    "smoke",
    "blood",
    "nonblood_fluid",
    "lens_contamination",
]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--selected-full-metadata", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    return p.parse_args()


def as_bool(s):
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna("").astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes", "y", "t"}
    )


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    labels = pd.read_csv(args.labels, low_memory=False)
    meta = pd.read_csv(args.selected_full_metadata, low_memory=False)

    if labels["review_id"].duplicated().any():
        raise ValueError("Duplicate review_id in labels.")
    if meta["review_id"].duplicated().any():
        raise ValueError("Duplicate review_id in selected metadata.")

    merged = meta.merge(
        labels,
        on="review_id",
        how="left",
        suffixes=("", "_label"),
        indicator=True,
    )

    missing = merged.loc[merged["_merge"] != "both", "review_id"].astype(str).tolist()
    extra = sorted(set(labels["review_id"].astype(str)) - set(meta["review_id"].astype(str)))

    qc = pd.DataFrame([{
        "selected_rows": len(meta),
        "label_rows": len(labels),
        "merged_rows": len(merged),
        "missing_label_count": len(missing),
        "extra_label_count": len(extra),
        "duplicate_label_ids": int(labels["review_id"].duplicated().sum()),
        "duplicate_metadata_ids": int(meta["review_id"].duplicated().sum()),
    }])
    qc.to_csv(args.output_dir / "phase01c_v2_review_qc.csv", index=False)

    if missing or extra:
        print("QC ISSUE")
        print(qc.to_string(index=False))
        if missing:
            print("Missing:", missing)
        if extra:
            print("Extra:", extra)
        return

    for key in LABELS:
        c = f"present_{key}"
        if c not in merged.columns:
            merged[c] = False
        merged[c] = as_bool(merged[c])

    for c in ["no_listed_phenomenon", "mechanism_uncertain", "nonstandard_imaging_mode"]:
        if c not in merged.columns:
            merged[c] = False
        merged[c] = as_bool(merged[c])

    freq = []
    for key in LABELS:
        c = f"present_{key}"
        freq.append({
            "phenomenon": key,
            "n_present": int(merged[c].sum()),
            "n_total": len(merged),
            "proportion": float(merged[c].mean()),
            "n_cases_present": merged.loc[merged[c], "case_id"].nunique(),
        })
    freq = pd.DataFrame(freq)
    freq.to_csv(args.output_dir / "phase01c_v2_overall_frequency.csv", index=False)

    rows = []
    for route, g in merged.groupby("primary_sampling_route", sort=False):
        row = {"primary_sampling_route": route, "n_frames": len(g)}
        for key in LABELS:
            c = f"present_{key}"
            row[f"{key}_n"] = int(g[c].sum())
            row[f"{key}_prop"] = float(g[c].mean())
        rows.append(row)
    cross = pd.DataFrame(rows)
    cross.to_csv(args.output_dir / "phase01c_v2_route_by_phenomenon.csv", index=False)

    merged.drop(columns="_merge").to_csv(
        args.output_dir / "phase01c_v2_unblinded_full.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("QC: PASS")
    print(f"Frames: {len(merged)}")
    print(f"Cases: {merged['case_id'].nunique()}")
    print()
    print("Overall human-confirmed presence:")
    print(freq.to_string(index=False))
    print()
    print("Route x phenomenon:")
    cols = [
        "primary_sampling_route",
        "n_frames",
        "near_contact_n",
        "smoke_n",
        "blood_n",
        "nonblood_fluid_n",
        "lens_contamination_n",
    ]
    print(cross[cols].to_string(index=False))
    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
