#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Audit suspected metric aliases across the full per-frame metric dataset.

This script verifies whether metric pairs that were identical in the
30-image Phase 01 calibration set are also identical across all available
per-frame CSVs.

Default input:
    data/derived/quality_metrics/per_frame

Output:
    reports/phase01_pilot_sampling/full_dataset_metric_alias_audit.csv

No source CSV is modified.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import math
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_METRICS_DIR = (
    ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
)

DEFAULT_OUTPUT = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "full_dataset_metric_alias_audit.csv"
)

PAIRS = [
    ("structural_visibility_loss_v1", "composite_badness_v4"),
    ("structural_visibility_loss_v1", "focus_badness_v1"),
    ("center_low_structure_area_v1", "local_obstruction_ratio"),
    ("reblur_response_loss_v1", "blur_like_mean"),
    ("whiteout_ratio_v1", "saturation_ratio"),
    ("specular_like_ratio_v1", "specular_ratio"),

    # Suspected from identical 30-image summary output; verify explicitly.
    ("veil_low_contrast_score_v1", "veil_smoke_mean"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS_DIR,
    )
    p.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    p.add_argument(
        "--atol",
        type=float,
        default=1e-12,
    )
    p.add_argument(
        "--rtol",
        type=float,
        default=1e-12,
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    metrics_dir = args.metrics_dir.resolve()
    output_csv = args.output_csv.resolve()

    if not metrics_dir.exists():
        raise FileNotFoundError(
            f"Metrics directory not found: {metrics_dir}"
        )

    csv_files = sorted(metrics_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found under: {metrics_dir}"
        )

    states = {}
    for a, b in PAIRS:
        states[(a, b)] = {
            "metric_a": a,
            "metric_b": b,
            "files_total": len(csv_files),
            "files_with_both": 0,
            "files_missing_pair": 0,
            "rows_total_in_files_with_both": 0,
            "rows_both_nonmissing": 0,
            "nan_pattern_mismatch_rows": 0,
            "exact_value_mismatch_rows": 0,
            "allclose_mismatch_rows": 0,
            "max_abs_diff": 0.0,
        }

    all_needed = sorted({c for pair in PAIRS for c in pair})

    for i, path in enumerate(csv_files, start=1):
        header = pd.read_csv(path, nrows=0)
        available = set(header.columns)

        needed_here = [
            c for c in all_needed if c in available
        ]

        if needed_here:
            d = pd.read_csv(
                path,
                usecols=needed_here,
                low_memory=False,
            )
        else:
            d = pd.DataFrame()

        for a, b in PAIRS:
            s = states[(a, b)]

            if a not in available or b not in available:
                s["files_missing_pair"] += 1
                continue

            s["files_with_both"] += 1
            s["rows_total_in_files_with_both"] += len(d)

            x = pd.to_numeric(d[a], errors="coerce")
            y = pd.to_numeric(d[b], errors="coerce")

            xna = x.isna()
            yna = y.isna()

            nan_mismatch = xna ^ yna
            s["nan_pattern_mismatch_rows"] += int(
                nan_mismatch.sum()
            )

            both = (~xna) & (~yna)
            s["rows_both_nonmissing"] += int(both.sum())

            if both.any():
                xv = x.loc[both].to_numpy(dtype=float)
                yv = y.loc[both].to_numpy(dtype=float)

                exact_mismatch = xv != yv
                s["exact_value_mismatch_rows"] += int(
                    exact_mismatch.sum()
                )

                close = np.isclose(
                    xv,
                    yv,
                    atol=args.atol,
                    rtol=args.rtol,
                    equal_nan=True,
                )
                s["allclose_mismatch_rows"] += int(
                    (~close).sum()
                )

                diffs = np.abs(xv - yv)
                if diffs.size:
                    local_max = float(np.nanmax(diffs))
                    if math.isfinite(local_max):
                        s["max_abs_diff"] = max(
                            s["max_abs_diff"],
                            local_max,
                        )

        if i % 10 == 0 or i == len(csv_files):
            print(
                f"Processed {i}/{len(csv_files)} CSV files"
            )

    rows = []
    for pair in PAIRS:
        s = states[pair]
        s["globally_exact_equal"] = (
            s["files_with_both"] > 0
            and s["nan_pattern_mismatch_rows"] == 0
            and s["exact_value_mismatch_rows"] == 0
        )
        s["globally_allclose"] = (
            s["files_with_both"] > 0
            and s["nan_pattern_mismatch_rows"] == 0
            and s["allclose_mismatch_rows"] == 0
        )
        rows.append(s)

    out = pd.DataFrame(rows)

    output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    out.to_csv(output_csv, index=False)

    print("\n=== Full-dataset metric alias audit ===")
    display_cols = [
        "metric_a",
        "metric_b",
        "files_with_both",
        "files_missing_pair",
        "rows_both_nonmissing",
        "nan_pattern_mismatch_rows",
        "exact_value_mismatch_rows",
        "allclose_mismatch_rows",
        "max_abs_diff",
        "globally_exact_equal",
        "globally_allclose",
    ]
    print(out[display_cols].to_string(index=False))

    print(f"\nSaved: {output_csv}")

    if (out["files_with_both"] == 0).any():
        print(
            "\nWARNING: At least one pair was never found together "
            "in the scanned per-frame CSVs."
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
