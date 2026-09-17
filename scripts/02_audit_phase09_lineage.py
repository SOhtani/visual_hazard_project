#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 00B: audit lineage around Phase 09.

Questions
---------
1. Which raw per-frame source row is absent from
   reports/visual_hazard_burden/visual_hazard_frame_flags.csv?
2. Does Phase 09 -> Phase 07 loss correspond exactly to
   hazard_ge_low_light_or_blackout_p99?
3. Which image-validity columns exist in source data but disappear from
   the Phase 09 frame-level export?

READ-ONLY for existing datasets.
Writes only audit outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_METRICS_DIR = (
    PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
)

DEFAULT_PHASE09 = (
    PROJECT_ROOT
    / "reports"
    / "visual_hazard_burden"
    / "visual_hazard_frame_flags.csv"
)

DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "color_phenotype_analyzable_frames_v1_full_metadata.csv"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "phase00_pipeline_audit"
    / "phase09_lineage"
)


VALIDITY_FLAGS = [
    "near_uniform_frame_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
    "photometric_failure_candidate_v1",
    "image_validity_problem_candidate_v1",
    "component_review_valid_candidate_v1",
]


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["case_id"] = (
        out["case_id"]
        .astype(str)
        .str.strip()
    )

    out["sample_time_sec"] = (
        pd.to_numeric(
            out["sample_time_sec"],
            errors="coerce",
        )
        .round(6)
    )

    return out


def load_raw_source(metrics_dir: Path) -> pd.DataFrame:
    frames = []

    files = sorted(
        metrics_dir.glob("CASE*_frame_scores.csv")
    )

    if not files:
        raise FileNotFoundError(
            f"No CASE*_frame_scores.csv files found in {metrics_dir}"
        )

    for path in files:
        df = pd.read_csv(
            path,
            low_memory=False,
        )

        if "case_id" not in df.columns:
            raise ValueError(
                f"{path.name}: case_id missing"
            )

        if "sample_time_sec" not in df.columns:
            raise ValueError(
                f"{path.name}: sample_time_sec missing"
            )

        df = normalize_keys(df)

        df["source_file"] = path.name
        df["source_row"] = range(len(df))

        frames.append(df)

        print(
            f"[OK] {path.name}: {len(df)} rows"
        )

    source = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    dup = source.duplicated(
        ["case_id", "sample_time_sec"]
    ).sum()

    if dup:
        raise RuntimeError(
            f"Raw source has {dup} duplicate case/time keys"
        )

    return source


def check_unique(
    df: pd.DataFrame,
    name: str,
) -> None:
    dup = df.duplicated(
        ["case_id", "sample_time_sec"]
    ).sum()

    if dup:
        raise RuntimeError(
            f"{name} has {dup} duplicate case/time keys"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
    )

    parser.add_argument(
        "--phase09",
        type=Path,
        default=DEFAULT_PHASE09,
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    args = parser.parse_args()

    metrics_dir = args.metrics_dir.resolve()
    phase09_path = args.phase09.resolve()
    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Raw source
    # ---------------------------------------------------------

    source = load_raw_source(
        metrics_dir
    )

    # ---------------------------------------------------------
    # Phase 09 output
    # ---------------------------------------------------------

    phase09 = pd.read_csv(
        phase09_path,
        low_memory=False,
    )

    phase09 = normalize_keys(
        phase09
    )

    check_unique(
        phase09,
        "Phase 09",
    )

    # ---------------------------------------------------------
    # Phase 07 color manifest
    # ---------------------------------------------------------

    manifest = pd.read_csv(
        manifest_path,
        low_memory=False,
    )

    manifest = normalize_keys(
        manifest
    )

    check_unique(
        manifest,
        "Color manifest",
    )

    # ---------------------------------------------------------
    # Raw source -> Phase 09
    # ---------------------------------------------------------

    phase09_keys = (
        phase09[
            ["case_id", "sample_time_sec"]
        ]
        .assign(in_phase09=1)
    )

    source_audit = source.merge(
        phase09_keys,
        on=["case_id", "sample_time_sec"],
        how="left",
        validate="one_to_one",
    )

    missing_from_phase09 = source_audit[
        source_audit["in_phase09"].isna()
    ].drop(
        columns=["in_phase09"]
    )

    source_keys = (
        source[
            ["case_id", "sample_time_sec"]
        ]
        .assign(in_source=1)
    )

    phase09_audit = phase09.merge(
        source_keys,
        on=["case_id", "sample_time_sec"],
        how="left",
        validate="one_to_one",
    )

    unexpected_phase09 = phase09_audit[
        phase09_audit["in_source"].isna()
    ].drop(
        columns=["in_source"]
    )

    missing_from_phase09.to_csv(
        output_dir
        / "raw_source_missing_from_phase09.csv",
        index=False,
    )

    unexpected_phase09.to_csv(
        output_dir
        / "phase09_not_found_in_raw_source.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Phase 09 -> Phase 07
    # ---------------------------------------------------------

    manifest_keys = (
        manifest[
            ["case_id", "sample_time_sec"]
        ]
        .assign(in_manifest=1)
    )

    x = phase09.merge(
        manifest_keys,
        on=["case_id", "sample_time_sec"],
        how="left",
        validate="one_to_one",
    )

    x["missing_from_color_manifest"] = (
        x["in_manifest"]
        .isna()
        .astype(int)
    )

    lowlight_col = (
        "hazard_ge_low_light_or_blackout_p99"
    )

    if lowlight_col not in x.columns:
        raise ValueError(
            f"{lowlight_col} missing from Phase 09"
        )

    x["low_light_p99"] = (
        pd.to_numeric(
            x[lowlight_col],
            errors="coerce",
        )
        .fillna(0)
        .ge(0.5)
        .astype(int)
    )

    membership_mismatch = (
        x["missing_from_color_manifest"]
        != x["low_light_p99"]
    )

    x.loc[
        membership_mismatch
    ].to_csv(
        output_dir
        / "phase09_to_manifest_membership_mismatches.csv",
        index=False,
    )

    crosstab = pd.crosstab(
        x["missing_from_color_manifest"],
        x["low_light_p99"],
        rownames=["missing_from_color_manifest"],
        colnames=["low_light_p99"],
        dropna=False,
    )

    crosstab.to_csv(
        output_dir
        / "phase09_to_manifest_lowlight_crosstab.csv"
    )

    # ---------------------------------------------------------
    # Column propagation
    # ---------------------------------------------------------

    propagation_rows = []

    for col in VALIDITY_FLAGS:
        propagation_rows.append(
            {
                "column": col,
                "present_in_raw_source": int(
                    col in source.columns
                ),
                "present_in_phase09_output": int(
                    col in phase09.columns
                ),
                "present_in_color_manifest": int(
                    col in manifest.columns
                ),
            }
        )

    propagation = pd.DataFrame(
        propagation_rows
    )

    propagation.to_csv(
        output_dir
        / "validity_column_propagation.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    summary_lines = [
        "# Phase 09 lineage audit",
        "",
        f"- Raw source rows: {len(source)}",
        f"- Phase 09 rows: {len(phase09)}",
        f"- Phase 07 color manifest rows: {len(manifest)}",
        "",
        (
            "- Raw source rows missing from Phase 09: "
            f"{len(missing_from_phase09)}"
        ),
        (
            "- Phase 09 rows absent from raw source: "
            f"{len(unexpected_phase09)}"
        ),
        (
            "- Phase 09 rows missing from color manifest: "
            f"{int(x['missing_from_color_manifest'].sum())}"
        ),
        (
            "- Phase 09 low-light p99 frames: "
            f"{int(x['low_light_p99'].sum())}"
        ),
        (
            "- Phase 09 -> manifest membership mismatches: "
            f"{int(membership_mismatch.sum())}"
        ),
        "",
        "## Validity-column propagation",
        "",
    ]

    for _, row in propagation.iterrows():
        summary_lines.append(
            f"- {row['column']}: "
            f"raw={row['present_in_raw_source']}, "
            f"phase09={row['present_in_phase09_output']}, "
            f"manifest={row['present_in_color_manifest']}"
        )

    (
        output_dir
        / "phase09_lineage_summary.md"
    ).write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    print()
    print("=== PHASE 09 LINEAGE AUDIT ===")
    print(f"raw source rows:             {len(source)}")
    print(f"Phase 09 rows:               {len(phase09)}")
    print(f"color manifest rows:         {len(manifest)}")
    print(
        "missing source -> Phase 09: "
        f"{len(missing_from_phase09)}"
    )
    print(
        "unexpected Phase 09 rows:   "
        f"{len(unexpected_phase09)}"
    )
    print(
        "Phase09 -> manifest loss:   "
        f"{int(x['missing_from_color_manifest'].sum())}"
    )
    print(
        "low-light p99 frames:       "
        f"{int(x['low_light_p99'].sum())}"
    )
    print(
        "membership mismatches:      "
        f"{int(membership_mismatch.sum())}"
    )

    print()
    print("Missing raw-source rows:")
    if missing_from_phase09.empty:
        print("NONE")
    else:
        preferred = [
            "case_id",
            "sample_time_sec",
            "image_path",
            "metric_status",
            "source_file",
            "source_row",
        ]

        preferred += [
            c
            for c in VALIDITY_FLAGS
            if c in missing_from_phase09.columns
        ]

        preferred = [
            c
            for c in preferred
            if c in missing_from_phase09.columns
        ]

        print(
            missing_from_phase09[
                preferred
            ].to_string(index=False)
        )

    print()
    print("Column propagation:")
    print(
        propagation.to_string(
            index=False
        )
    )

    print()
    print(f"Outputs: {output_dir}")


if __name__ == "__main__":
    main()