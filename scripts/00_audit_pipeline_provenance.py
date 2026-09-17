#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 00 pipeline / provenance audit for visual_hazard_project.

Purpose
-------
This script performs a READ-ONLY audit of existing CSV artifacts and source
scripts. It does not modify existing datasets.

Primary questions:
1. Where do the frames excluded between the original per-frame metric dataset
   and the Phase 07 color-phenotype manifest disappear?
2. Where are the image-validity candidate columns present or absent across
   pipeline artifacts?
3. Are frame-level keys unique and stable?
4. Which scripts reference the critical columns and CSV artifacts?

Outputs
-------
reports/phase00_pipeline_audit/
    table_inventory.csv
    critical_column_presence.csv
    per_frame_source_summary.csv
    source_vs_color_manifest_case_diff.csv
    frames_missing_from_color_manifest.csv
    frames_unexpected_in_color_manifest.csv
    duplicate_key_summary.csv
    script_column_references.csv
    script_csv_references.csv
    audit_summary.md

The script writes only to the audit output directory.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_METRICS_DIR = (
    PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
)

DEFAULT_COLOR_MANIFEST = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "color_phenotype_analyzable_frames_v1_full_metadata.csv"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "reports" / "phase00_pipeline_audit"
)


IMAGE_VALIDITY_COLUMNS = [
    "near_uniform_frame_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
    "photometric_failure_candidate_v1",
    "image_validity_problem_candidate_v1",
    "component_review_valid_candidate_v1",
]


PURPOSE_SPECIFIC_COLUMNS = [
    "technical_exclusion_frame_v1",
    "technical_analyzable_frame_v1",
    "color_phenotype_analyzable_frame_v1",
    "structural_phenotype_analyzable_frame_v1",
    "clean_reference_frame_p95_v1",
    "visual_hazard_any_p95_for_sets",
    "visual_hazard_any_p99_for_sets",
]


KEY_COLUMNS = [
    "case_id",
    "sample_time_sec",
    "frame_index",
    "image_path",
]


CORE_METRIC_COLUMNS = [
    "structural_visibility_loss_v1",
    "center_low_structure_area_v1",
    "whiteout_ratio_v1",
    "low_light_or_blackout_ratio_v1",
]


CRITICAL_COLUMNS = (
    KEY_COLUMNS
    + IMAGE_VALIDITY_COLUMNS
    + PURPOSE_SPECIFIC_COLUMNS
    + CORE_METRIC_COLUMNS
)


SCAN_ROOTS = [
    PROJECT_ROOT / "data" / "annotations",
    PROJECT_ROOT / "data" / "derived",
    PROJECT_ROOT / "reports",
]


SCRIPT_ROOTS = [
    PROJECT_ROOT / "scripts",
]


def normalize_case_id(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_time(value: object) -> Optional[float]:
    if pd.isna(value):
        return None
    try:
        return round(float(value), 6)
    except Exception:
        return None


def safe_read_header(path: Path) -> List[str]:
    try:
        return pd.read_csv(path, nrows=0).columns.tolist()
    except Exception:
        return []


def safe_csv_row_count(path: Path) -> Optional[int]:
    """
    Count data rows without loading the full file.
    Returns None if the file cannot be read.
    """
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            count = sum(1 for _ in f)
        return max(count - 1, 0)
    except Exception:
        return None


def detect_case_column(columns: Sequence[str]) -> Optional[str]:
    for col in ["case_id", "case", "video_id"]:
        if col in columns:
            return col
    return None


def detect_time_column(columns: Sequence[str]) -> Optional[str]:
    for col in [
        "sample_time_sec",
        "time_sec",
        "timestamp_sec",
        "frame_time_sec",
        "t_sec",
        "seconds",
        "sec",
        "t",
    ]:
        if col in columns:
            return col
    return None


def detect_frame_index_column(columns: Sequence[str]) -> Optional[str]:
    for col in [
        "frame_index",
        "frame_idx",
        "frame_no",
        "frame_number",
        "sample_index",
        "idx",
    ]:
        if col in columns:
            return col
    return None


def inventory_csv(path: Path) -> Dict[str, object]:
    columns = safe_read_header(path)
    row_count = safe_csv_row_count(path)

    case_col = detect_case_column(columns)
    time_col = detect_time_column(columns)
    frame_col = detect_frame_index_column(columns)

    case_count = None

    if case_col is not None:
        try:
            cases = pd.read_csv(
                path,
                usecols=[case_col],
                low_memory=False,
            )[case_col]
            case_count = int(cases.dropna().astype(str).nunique())
        except Exception:
            case_count = None

    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "rows": row_count,
        "n_columns": len(columns),
        "case_column": case_col or "",
        "time_column": time_col or "",
        "frame_index_column": frame_col or "",
        "n_cases": case_count,
        "has_case_id": int("case_id" in columns),
        "has_sample_time_sec": int("sample_time_sec" in columns),
        "has_frame_index": int("frame_index" in columns),
        "has_image_path": int("image_path" in columns),
    }


def discover_csvs() -> List[Path]:
    paths: List[Path] = []

    for root in SCAN_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*.csv"):
            if DEFAULT_OUTPUT_DIR in path.parents:
                continue
            paths.append(path)

    return sorted(set(paths))


def build_table_inventory(csv_paths: Sequence[Path]) -> pd.DataFrame:
    records = []

    for i, path in enumerate(csv_paths, start=1):
        print(f"[inventory {i}/{len(csv_paths)}] {path.relative_to(PROJECT_ROOT)}")
        records.append(inventory_csv(path))

    return pd.DataFrame(records)


def build_column_presence(csv_paths: Sequence[Path]) -> pd.DataFrame:
    records = []

    for path in csv_paths:
        columns = set(safe_read_header(path))

        record: Dict[str, object] = {
            "path": str(path.relative_to(PROJECT_ROOT)),
        }

        for col in CRITICAL_COLUMNS:
            record[col] = int(col in columns)

        records.append(record)

    return pd.DataFrame(records)


def load_per_frame_source(
    metrics_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted(metrics_dir.glob("*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No per-frame metric CSV files found: {metrics_dir}"
        )

    source_frames = []
    summaries = []

    for i, path in enumerate(files, start=1):
        print(f"[source {i}/{len(files)}] {path.name}")

        header = safe_read_header(path)

        case_col = detect_case_column(header)
        time_col = detect_time_column(header)
        frame_col = detect_frame_index_column(header)

        if case_col is None:
            summaries.append(
                {
                    "file": path.name,
                    "status": "missing_case_column",
                    "rows": safe_csv_row_count(path),
                    "n_keys": None,
                    "duplicate_keys": None,
                    "case_id": "",
                    "min_time": None,
                    "max_time": None,
                }
            )
            continue

        key_cols = [case_col]

        if time_col is not None:
            key_cols.append(time_col)

        if frame_col is not None and frame_col not in key_cols:
            key_cols.append(frame_col)

        if len(key_cols) < 2:
            summaries.append(
                {
                    "file": path.name,
                    "status": "missing_time_and_frame_index",
                    "rows": safe_csv_row_count(path),
                    "n_keys": None,
                    "duplicate_keys": None,
                    "case_id": "",
                    "min_time": None,
                    "max_time": None,
                }
            )
            continue

        df = pd.read_csv(
            path,
            usecols=key_cols,
            low_memory=False,
        )

        out = pd.DataFrame()
        out["case_id"] = df[case_col].map(normalize_case_id)

        if time_col is not None:
            out["sample_time_sec"] = df[time_col].map(normalize_time)
        else:
            out["sample_time_sec"] = pd.NA

        if frame_col is not None:
            out["frame_index"] = df[frame_col]
        else:
            out["frame_index"] = pd.NA

        out["source_file"] = path.name
        out["source_row"] = range(len(out))

        if time_col is not None:
            duplicate_count = int(
                out.duplicated(["case_id", "sample_time_sec"]).sum()
            )
        else:
            duplicate_count = int(
                out.duplicated(["case_id", "frame_index"]).sum()
            )

        cases = out["case_id"].dropna().unique().tolist()

        summaries.append(
            {
                "file": path.name,
                "status": "ok",
                "rows": len(out),
                "n_keys": len(out),
                "duplicate_keys": duplicate_count,
                "case_id": "|".join(map(str, cases[:10])),
                "min_time": (
                    pd.to_numeric(
                        out["sample_time_sec"],
                        errors="coerce",
                    ).min()
                    if time_col is not None
                    else None
                ),
                "max_time": (
                    pd.to_numeric(
                        out["sample_time_sec"],
                        errors="coerce",
                    ).max()
                    if time_col is not None
                    else None
                ),
            }
        )

        source_frames.append(out)

    if not source_frames:
        raise RuntimeError(
            "Could not construct frame-level keys from any source metric CSV."
        )

    combined = pd.concat(source_frames, ignore_index=True)
    summary_df = pd.DataFrame(summaries)

    return combined, summary_df


def load_color_manifest(path: Path) -> pd.DataFrame:
    header = safe_read_header(path)

    if "case_id" not in header:
        raise ValueError(
            f"Color manifest does not contain case_id: {path}"
        )

    if "sample_time_sec" not in header:
        raise ValueError(
            f"Color manifest does not contain sample_time_sec: {path}"
        )

    usecols = ["case_id", "sample_time_sec"]

    if "image_path" in header:
        usecols.append("image_path")

    df = pd.read_csv(
        path,
        usecols=usecols,
        low_memory=False,
    )

    df["case_id"] = df["case_id"].map(normalize_case_id)
    df["sample_time_sec"] = df["sample_time_sec"].map(normalize_time)

    return df


def compare_source_and_manifest(
    source_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_keys = source_df[
        ["case_id", "sample_time_sec", "source_file", "source_row"]
    ].copy()

    manifest_keys = manifest_df[
        ["case_id", "sample_time_sec"]
    ].copy()

    source_key_unique = (
        source_keys
        .drop_duplicates(["case_id", "sample_time_sec"])
        .copy()
    )

    manifest_key_unique = (
        manifest_keys
        .drop_duplicates(["case_id", "sample_time_sec"])
        .copy()
    )

    missing = source_key_unique.merge(
        manifest_key_unique.assign(in_manifest=1),
        on=["case_id", "sample_time_sec"],
        how="left",
    )

    missing = missing[
        missing["in_manifest"].isna()
    ].drop(columns=["in_manifest"])

    unexpected = manifest_key_unique.merge(
        source_key_unique[
            ["case_id", "sample_time_sec"]
        ].assign(in_source=1),
        on=["case_id", "sample_time_sec"],
        how="left",
    )

    unexpected = unexpected[
        unexpected["in_source"].isna()
    ].drop(columns=["in_source"])

    source_case = (
        source_key_unique
        .groupby("case_id")
        .size()
        .rename("source_unique_frames")
    )

    manifest_case = (
        manifest_key_unique
        .groupby("case_id")
        .size()
        .rename("manifest_unique_frames")
    )

    missing_case = (
        missing
        .groupby("case_id")
        .size()
        .rename("missing_from_manifest")
    )

    unexpected_case = (
        unexpected
        .groupby("case_id")
        .size()
        .rename("unexpected_in_manifest")
    )

    case_diff = pd.concat(
        [
            source_case,
            manifest_case,
            missing_case,
            unexpected_case,
        ],
        axis=1,
    ).fillna(0)

    for col in case_diff.columns:
        case_diff[col] = case_diff[col].astype(int)

    case_diff["source_minus_manifest"] = (
        case_diff["source_unique_frames"]
        - case_diff["manifest_unique_frames"]
    )

    case_diff = case_diff.reset_index()

    return missing, unexpected, case_diff


def build_duplicate_summary(
    source_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
) -> pd.DataFrame:
    source_dup = int(
        source_df.duplicated(
            ["case_id", "sample_time_sec"]
        ).sum()
    )

    manifest_dup = int(
        manifest_df.duplicated(
            ["case_id", "sample_time_sec"]
        ).sum()
    )

    return pd.DataFrame(
        [
            {
                "dataset": "per_frame_source_combined",
                "rows": len(source_df),
                "duplicate_case_time_keys": source_dup,
            },
            {
                "dataset": "color_manifest_full_metadata",
                "rows": len(manifest_df),
                "duplicate_case_time_keys": manifest_dup,
            },
        ]
    )


def discover_python_scripts() -> List[Path]:
    scripts = []

    for root in SCRIPT_ROOTS:
        if not root.exists():
            continue

        scripts.extend(root.rglob("*.py"))

    return sorted(set(scripts))


def scan_script_references(
    script_paths: Sequence[Path],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    column_records = []
    csv_records = []

    csv_pattern = re.compile(
        r"""['"]([^'"]+\.csv)['"]""",
        flags=re.IGNORECASE,
    )

    for path in script_paths:
        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        rel = str(path.relative_to(PROJECT_ROOT))

        for col in CRITICAL_COLUMNS:
            count = text.count(col)
            if count > 0:
                column_records.append(
                    {
                        "script": rel,
                        "column": col,
                        "reference_count": count,
                    }
                )

        for match in csv_pattern.finditer(text):
            csv_records.append(
                {
                    "script": rel,
                    "csv_reference": match.group(1),
                }
            )

    return (
        pd.DataFrame(column_records),
        pd.DataFrame(csv_records),
    )


def write_summary(
    output_path: Path,
    source_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    unexpected_df: pd.DataFrame,
    case_diff_df: pd.DataFrame,
    column_presence_df: pd.DataFrame,
    source_summary_df: pd.DataFrame,
) -> None:
    source_rows = len(source_df)
    manifest_rows = len(manifest_df)

    source_unique = source_df[
        ["case_id", "sample_time_sec"]
    ].drop_duplicates()

    manifest_unique = manifest_df[
        ["case_id", "sample_time_sec"]
    ].drop_duplicates()

    source_unique_n = len(source_unique)
    manifest_unique_n = len(manifest_unique)

    source_cases = source_unique["case_id"].nunique()
    manifest_cases = manifest_unique["case_id"].nunique()

    column_counts = {}

    for col in IMAGE_VALIDITY_COLUMNS:
        if col in column_presence_df.columns:
            column_counts[col] = int(
                column_presence_df[col].sum()
            )

    lines = [
        "# Phase 00 pipeline provenance audit",
        "",
        "## Source per-frame dataset",
        "",
        f"- Combined rows: {source_rows}",
        f"- Unique case/time keys: {source_unique_n}",
        f"- Cases: {source_cases}",
        f"- Source CSV files: {len(source_summary_df)}",
        "",
        "## Phase 07 full-metadata color manifest",
        "",
        f"- Rows: {manifest_rows}",
        f"- Unique case/time keys: {manifest_unique_n}",
        f"- Cases: {manifest_cases}",
        "",
        "## Source vs manifest",
        "",
        f"- Raw row difference: {source_rows - manifest_rows}",
        f"- Unique-key difference: {source_unique_n - manifest_unique_n}",
        f"- Source keys missing from manifest: {len(missing_df)}",
        f"- Manifest keys not found in source: {len(unexpected_df)}",
        "",
        "## Image-validity column artifact presence",
        "",
    ]

    for col in IMAGE_VALIDITY_COLUMNS:
        lines.append(
            f"- {col}: present in {column_counts.get(col, 0)} scanned CSV artifacts"
        )

    lines.extend(
        [
            "",
            "## Interpretation guardrail",
            "",
            "This audit identifies where rows and columns are present or absent.",
            "It does not infer the clinical meaning of exclusions.",
            "Any exclusion reason must be traced to the generating script and rule",
            "before being classified as technical invalidity, visual degradation,",
            "workflow exclusion, or another mechanism.",
            "",
            "## Case-level differences",
            "",
        ]
    )

    nonzero = case_diff_df[
        (case_diff_df["source_minus_manifest"] != 0)
        | (case_diff_df["missing_from_manifest"] != 0)
        | (case_diff_df["unexpected_in_manifest"] != 0)
    ]

    if nonzero.empty:
        lines.append("- No case-level source/manifest count differences.")
    else:
        for _, row in nonzero.iterrows():
            lines.append(
                f"- {row['case_id']}: "
                f"source={row['source_unique_frames']}, "
                f"manifest={row['manifest_unique_frames']}, "
                f"missing={row['missing_from_manifest']}, "
                f"unexpected={row['unexpected_in_manifest']}"
            )

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Phase 00 pipeline provenance audit."
    )

    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
    )

    parser.add_argument(
        "--color-manifest",
        type=Path,
        default=DEFAULT_COLOR_MANIFEST,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    metrics_dir = args.metrics_dir.resolve()
    color_manifest = args.color_manifest.resolve()
    output_dir = args.output_dir.resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=== Phase 00 pipeline provenance audit ===")
    print(f"project root:   {PROJECT_ROOT}")
    print(f"metrics dir:    {metrics_dir}")
    print(f"color manifest: {color_manifest}")
    print(f"output dir:     {output_dir}")
    print()

    # ------------------------------------------------------------
    # 1. Artifact inventory
    # ------------------------------------------------------------
    csv_paths = discover_csvs()

    print(f"[INFO] discovered CSV artifacts: {len(csv_paths)}")

    table_inventory = build_table_inventory(csv_paths)
    table_inventory.to_csv(
        output_dir / "table_inventory.csv",
        index=False,
    )

    column_presence = build_column_presence(csv_paths)
    column_presence.to_csv(
        output_dir / "critical_column_presence.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # 2. Per-frame source dataset
    # ------------------------------------------------------------
    source_df, source_summary = load_per_frame_source(
        metrics_dir
    )

    source_summary.to_csv(
        output_dir / "per_frame_source_summary.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # 3. Phase 07 full-metadata manifest
    # ------------------------------------------------------------
    manifest_df = load_color_manifest(
        color_manifest
    )

    # ------------------------------------------------------------
    # 4. Compare source vs manifest
    # ------------------------------------------------------------
    missing, unexpected, case_diff = compare_source_and_manifest(
        source_df,
        manifest_df,
    )

    case_diff.to_csv(
        output_dir / "source_vs_color_manifest_case_diff.csv",
        index=False,
    )

    missing.to_csv(
        output_dir / "frames_missing_from_color_manifest.csv",
        index=False,
    )

    unexpected.to_csv(
        output_dir / "frames_unexpected_in_color_manifest.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # 5. Duplicate keys
    # ------------------------------------------------------------
    duplicate_summary = build_duplicate_summary(
        source_df,
        manifest_df,
    )

    duplicate_summary.to_csv(
        output_dir / "duplicate_key_summary.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # 6. Source-code references
    # ------------------------------------------------------------
    scripts = discover_python_scripts()

    script_columns, script_csvs = scan_script_references(
        scripts
    )

    script_columns.to_csv(
        output_dir / "script_column_references.csv",
        index=False,
    )

    script_csvs.to_csv(
        output_dir / "script_csv_references.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # 7. Human-readable summary
    # ------------------------------------------------------------
    write_summary(
        output_dir / "audit_summary.md",
        source_df,
        manifest_df,
        missing,
        unexpected,
        case_diff,
        column_presence,
        source_summary,
    )

    print()
    print("=== AUDIT COMPLETE ===")
    print(
        f"source rows:                  {len(source_df)}"
    )
    print(
        f"manifest rows:                {len(manifest_df)}"
    )
    print(
        f"raw row difference:           {len(source_df) - len(manifest_df)}"
    )
    print(
        f"missing source keys:           {len(missing)}"
    )
    print(
        f"unexpected manifest keys:      {len(unexpected)}"
    )
    print(
        f"source case/time duplicates:   "
        f"{source_df.duplicated(['case_id', 'sample_time_sec']).sum()}"
    )
    print(
        f"manifest case/time duplicates: "
        f"{manifest_df.duplicated(['case_id', 'sample_time_sec']).sum()}"
    )
    print()
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()