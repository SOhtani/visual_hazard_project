#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

PHENOMENA = [
    "blur",
    "smoke",
    "lens_contamination",
    "glare",
    "whiteout",
    "underexposure",
    "blood_fluid",
    "physical_obstruction",
    "near_contact",
]

TARGET_BY_STRATUM = {
    "near_contact_strict_proxy": ["near_contact"],
    "near_contact_relaxed_only": ["near_contact"],
    "smoke_extreme_temporal_proxy": ["smoke"],
    "smoke_temporal_high_only": ["smoke"],
    "lens_persistent_degradation_proxy": ["lens_contamination"],
    "blur_extreme": ["blur"],
    "blur_high_only": ["blur"],
    "obstruction_extreme": ["physical_obstruction"],
    "obstruction_high_only": ["physical_obstruction"],
    "glare_extreme": ["glare"],
    "glare_high_only": ["glare"],
    "whiteout_extreme": ["whiteout"],
    "whiteout_high_only": ["whiteout"],
    "lowlight_extreme": ["underexposure"],
    "lowlight_high_only": ["underexposure"],
    "blur_obstruction_overlap": ["blur", "physical_obstruction"],
    "glare_whiteout_overlap": ["glare", "whiteout"],
}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
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
    manifest = pd.read_csv(args.manifest, low_memory=False)

    req_l = {"audit_review_id", "case_id", "sample_time_sec"}
    req_m = {"audit_review_id", "audit_stratum", "case_id", "sample_time_sec"}
    miss_l = req_l - set(labels.columns)
    miss_m = req_m - set(manifest.columns)
    if miss_l:
        raise ValueError(f"Labels missing required columns: {sorted(miss_l)}")
    if miss_m:
        raise ValueError(f"Manifest missing required columns: {sorted(miss_m)}")

    label_cols = [f"present_{p}" for p in PHENOMENA]
    extra_cols = [
        "no_listed_phenomenon",
        "mechanism_uncertain",
        "nonstandard_imaging_mode",
    ]
    for c in label_cols + extra_cols:
        if c not in labels.columns:
            labels[c] = False
        labels[c] = as_bool(labels[c])

    dup_labels = int(labels["audit_review_id"].duplicated().sum())
    dup_manifest = int(manifest["audit_review_id"].duplicated().sum())

    merged = manifest.merge(
        labels,
        on="audit_review_id",
        how="left",
        suffixes=("_manifest", "_label"),
        indicator=True,
    )

    missing_labels = merged.loc[merged["_merge"] != "both", "audit_review_id"].astype(str).tolist()
    extra_ids = sorted(
        set(labels["audit_review_id"].astype(str))
        - set(manifest["audit_review_id"].astype(str))
    )

    qc = pd.DataFrame([{
        "manifest_rows": len(manifest),
        "label_rows": len(labels),
        "merged_rows": len(merged),
        "manifest_unique_ids": manifest["audit_review_id"].nunique(),
        "label_unique_ids": labels["audit_review_id"].nunique(),
        "manifest_duplicate_ids": dup_manifest,
        "label_duplicate_ids": dup_labels,
        "missing_label_count": len(missing_labels),
        "extra_label_id_count": len(extra_ids),
    }])
    qc.to_csv(args.output_dir / "phase01_presence_audit_qc.csv", index=False)

    if missing_labels:
        pd.DataFrame({"audit_review_id": missing_labels}).to_csv(
            args.output_dir / "phase01_presence_audit_missing_labels.csv", index=False
        )
    if extra_ids:
        pd.DataFrame({"audit_review_id": extra_ids}).to_csv(
            args.output_dir / "phase01_presence_audit_extra_label_ids.csv", index=False
        )

    if dup_labels or dup_manifest or missing_labels or extra_ids:
        print("QC issue detected. Scientific summaries not generated.")
        print(qc.to_string(index=False))
        print(f"See: {args.output_dir}")
        return

    case_col = "case_id_manifest" if "case_id_manifest" in merged.columns else "case_id"
    time_col = (
        "sample_time_sec_manifest"
        if "sample_time_sec_manifest" in merged.columns
        else "sample_time_sec"
    )

    freq = []
    for p in PHENOMENA:
        c = f"present_{p}"
        n = int(merged[c].sum())
        freq.append({
            "phenomenon": p,
            "n_present": n,
            "n_total": len(merged),
            "proportion": n / len(merged),
            "n_cases_present": merged.loc[merged[c], case_col].nunique(),
        })
    freq = pd.DataFrame(freq)
    freq.to_csv(
        args.output_dir / "phase01_presence_audit_overall_frequency.csv",
        index=False
    )

    cross_rows = []
    for stratum, g in merged.groupby("audit_stratum", sort=False):
        row = {"audit_stratum": stratum, "n_frames": len(g)}
        for p in PHENOMENA:
            c = f"present_{p}"
            n = int(g[c].sum())
            row[f"{p}_n"] = n
            row[f"{p}_prop"] = n / len(g)
        cross_rows.append(row)
    cross = pd.DataFrame(cross_rows)
    cross.to_csv(
        args.output_dir / "phase01_presence_audit_stratum_by_phenomenon.csv",
        index=False
    )

    target_rows = []
    for stratum, targets in TARGET_BY_STRATUM.items():
        g = merged[merged["audit_stratum"] == stratum]
        if g.empty:
            continue
        for target in targets:
            n = int(g[f"present_{target}"].sum())
            target_rows.append({
                "audit_stratum": stratum,
                "target_phenomenon": target,
                "n_frames": len(g),
                "n_target_present": n,
                "descriptive_target_present_fraction": n / len(g),
                "note": "Internal retrieval audit only; not unbiased precision.",
            })
    target = pd.DataFrame(target_rows)
    target.to_csv(
        args.output_dir / "phase01_presence_audit_retrieval_target_summary.csv",
        index=False
    )

    co = []
    for i, p1 in enumerate(PHENOMENA):
        for p2 in PHENOMENA[i:]:
            n = int((merged[f"present_{p1}"] & merged[f"present_{p2}"]).sum())
            co.append({
                "phenomenon_a": p1,
                "phenomenon_b": p2,
                "n_cooccur": n,
            })
    pd.DataFrame(co).to_csv(
        args.output_dir / "phase01_presence_audit_cooccurrence.csv",
        index=False
    )

    positives = []
    for _, r in merged.iterrows():
        for p in PHENOMENA:
            if bool(r[f"present_{p}"]):
                positives.append({
                    "phenomenon": p,
                    "audit_review_id": r["audit_review_id"],
                    "audit_stratum": r["audit_stratum"],
                    "case_id": r[case_col],
                    "sample_time_sec": r[time_col],
                    "image_path": r.get("image_path_manifest", r.get("image_path", "")),
                    "mechanism_uncertain": bool(r["mechanism_uncertain"]),
                    "nonstandard_imaging_mode": bool(r["nonstandard_imaging_mode"]),
                    "comment": r.get("comment", ""),
                })
    pd.DataFrame(positives).to_csv(
        args.output_dir / "phase01_presence_audit_positive_frames_long.csv",
        index=False,
        encoding="utf-8-sig"
    )

    merged.drop(columns=["_merge"]).to_csv(
        args.output_dir / "phase01_presence_audit_unblinded_full.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("QC: PASS")
    print(f"Frames: {len(merged)}")
    print(f"Cases: {merged[case_col].nunique()}")
    print()
    print("Overall human-confirmed presence:")
    print(freq.to_string(index=False))
    print()
    print("Retrieval target presence by stratum (descriptive only):")
    print(target[
        [
            "audit_stratum",
            "target_phenomenon",
            "n_target_present",
            "n_frames",
            "descriptive_target_present_fraction",
        ]
    ].to_string(index=False))
    print()
    print(f"Saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
