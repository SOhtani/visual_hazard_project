#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Audit the 5,193 source frames absent from the Phase 07 color manifest.

READ-ONLY:
- reads existing per-frame metric CSVs
- reads Phase 00 missing-frame key list
- writes audit tables only

This script does NOT decide whether any image-validity flag is clinically
appropriate. It only tests whether missing-frame membership corresponds to
existing rule-based flags.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_METRICS_DIR = (
    PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
)

DEFAULT_MISSING_CSV = (
    PROJECT_ROOT
    / "reports"
    / "phase00_pipeline_audit"
    / "frames_missing_from_color_manifest.csv"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "phase00_pipeline_audit"
    / "missing_frame_reason_audit"
)


FLAGS = [
    "near_uniform_frame_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
    "photometric_failure_candidate_v1",
    "image_validity_problem_candidate_v1",
    "component_review_valid_candidate_v1",
]


def norm_time(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round(6)


def read_metric_flags(metrics_dir: Path) -> pd.DataFrame:
    frames = []

    for path in sorted(metrics_dir.glob("*.csv")):
        header = pd.read_csv(path, nrows=0).columns.tolist()

        required = ["case_id", "sample_time_sec"]

        if not all(c in header for c in required):
            print(f"[SKIP] {path.name}: missing case/time key")
            continue

        available_flags = [c for c in FLAGS if c in header]

        if len(available_flags) != len(FLAGS):
            print(
                f"[SKIP] {path.name}: "
                f"only {len(available_flags)}/{len(FLAGS)} validity flags"
            )
            continue

        usecols = required + FLAGS

        df = pd.read_csv(
            path,
            usecols=usecols,
            low_memory=False,
        )

        df["case_id"] = df["case_id"].astype(str).str.strip()
        df["sample_time_sec"] = norm_time(df["sample_time_sec"])
        df["source_file"] = path.name

        frames.append(df)

        print(f"[OK] {path.name}: {len(df)} rows")

    if not frames:
        raise RuntimeError("No valid per-frame metric files found.")

    out = pd.concat(frames, ignore_index=True)

    dup = out.duplicated(["case_id", "sample_time_sec"]).sum()

    if dup:
        raise RuntimeError(
            f"Combined source flag table has {dup} duplicate case/time keys."
        )

    return out


def normalize_flag(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")

    return numeric.fillna(0).astype(int)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
    )

    parser.add_argument(
        "--missing-csv",
        type=Path,
        default=DEFAULT_MISSING_CSV,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    args = parser.parse_args()

    metrics_dir = args.metrics_dir.resolve()
    missing_csv = args.missing_csv.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    source = read_metric_flags(metrics_dir)

    missing = pd.read_csv(
        missing_csv,
        low_memory=False,
    )

    missing["case_id"] = missing["case_id"].astype(str).str.strip()
    missing["sample_time_sec"] = norm_time(
        missing["sample_time_sec"]
    )

    missing_keys = (
        missing[
            ["case_id", "sample_time_sec"]
        ]
        .drop_duplicates()
        .assign(missing_from_color_manifest=1)
    )

    audited = source.merge(
        missing_keys,
        on=["case_id", "sample_time_sec"],
        how="left",
        validate="one_to_one",
    )

    audited["missing_from_color_manifest"] = (
        audited["missing_from_color_manifest"]
        .fillna(0)
        .astype(int)
    )

    for col in FLAGS:
        audited[col] = normalize_flag(audited[col])

    # ------------------------------------------------------------
    # Individual flag summary
    # ------------------------------------------------------------

    summaries = []

    for flag in FLAGS:
        for missing_status in [0, 1]:
            sub = audited[
                audited["missing_from_color_manifest"]
                == missing_status
            ]

            summaries.append(
                {
                    "flag": flag,
                    "missing_from_color_manifest": missing_status,
                    "n_frames": len(sub),
                    "n_flagged": int(sub[flag].sum()),
                    "frac_flagged": (
                        float(sub[flag].mean())
                        if len(sub)
                        else float("nan")
                    ),
                }
            )

    summary_df = pd.DataFrame(summaries)

    summary_df.to_csv(
        output_dir / "flag_summary_missing_vs_retained.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # Exact relationship to image_validity_problem_candidate_v1
    # ------------------------------------------------------------

    relation = pd.crosstab(
        audited["missing_from_color_manifest"],
        audited["image_validity_problem_candidate_v1"],
        rownames=["missing_from_color_manifest"],
        colnames=["image_validity_problem_candidate_v1"],
        dropna=False,
    )

    relation.to_csv(
        output_dir
        / "missing_vs_image_validity_problem_crosstab.csv"
    )

    # ------------------------------------------------------------
    # Component flag signatures among missing frames
    # ------------------------------------------------------------

    component_flags = [
        "near_uniform_frame_candidate_v1",
        "large_whiteout_candidate_v1",
        "large_blackout_candidate_v1",
        "color_bar_or_test_pattern_candidate_v1",
        "photometric_failure_candidate_v1",
    ]

    missing_only = audited[
        audited["missing_from_color_manifest"] == 1
    ].copy()

    missing_only["validity_signature"] = missing_only[
        component_flags
    ].astype(str).agg("|".join, axis=1)

    signature_summary = (
        missing_only
        .groupby(
            component_flags + ["validity_signature"],
            dropna=False,
        )
        .size()
        .reset_index(name="n_frames")
        .sort_values(
            "n_frames",
            ascending=False,
        )
    )

    signature_summary.to_csv(
        output_dir / "missing_frame_flag_signatures.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # Per-case comparison
    # ------------------------------------------------------------

    case_rows = []

    for case_id, sub in audited.groupby("case_id"):
        missing_sub = sub[
            sub["missing_from_color_manifest"] == 1
        ]

        row = {
            "case_id": case_id,
            "source_frames": len(sub),
            "missing_frames": len(missing_sub),
            "missing_fraction": (
                len(missing_sub) / len(sub)
                if len(sub)
                else float("nan")
            ),
        }

        for flag in FLAGS:
            row[f"missing_{flag}_n"] = int(
                missing_sub[flag].sum()
            )

        case_rows.append(row)

    pd.DataFrame(case_rows).to_csv(
        output_dir / "case_missing_flag_summary.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # Raw missing frame rows with flags
    # ------------------------------------------------------------

    missing_only.to_csv(
        output_dir / "missing_frames_with_validity_flags.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------

    print()
    print("=== MISSING FRAME REASON AUDIT COMPLETE ===")
    print(f"source frames:   {len(audited)}")
    print(
        "missing frames:  "
        f"{audited['missing_from_color_manifest'].sum()}"
    )

    print()
    print("Missing vs image_validity_problem_candidate_v1:")
    print(relation.to_string())

    print()
    print("Flag prevalence among missing frames:")

    missing_summary = summary_df[
        summary_df["missing_from_color_manifest"] == 1
    ][
        ["flag", "n_flagged", "n_frames", "frac_flagged"]
    ]

    print(missing_summary.to_string(index=False))

    print()
    print("Most common missing-frame validity signatures:")
    print(signature_summary.head(20).to_string(index=False))

    print()
    print(f"Outputs: {output_dir}")


if __name__ == "__main__":
    main()