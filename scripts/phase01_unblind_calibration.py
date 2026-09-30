#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 01 calibration pilot: unblind the frozen second-pass ratings.

This script:
1. Loads the frozen second-pass ratings.
2. Joins the internal blinded-review mapping on review_item_id.
3. Joins the original selected-moment table on moment_id when available.
4. Validates that the 30 reviewed items map one-to-one.
5. Writes a single unblinded calibration table.
6. Writes the soft-warning subset and a simple stratum summary.

This is a calibration/descriptive analysis only.
Do not interpret these 30 enriched samples as a prevalence estimate or
independent validation cohort.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

RATINGS = (
    ROOT / "data" / "annotations"
    / "phase01_pilot_still_ratings_second_pass_frozen.csv"
)

MAPPING = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_pilot_review_mapping.csv"
)

MOMENTS = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_pilot_moments.csv"
)

OUT = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_unblinded_calibration.csv"
)

WARN_OUT = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_unblinded_warning_cases.csv"
)

STRATUM_OUT = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_unblinded_stratum_summary.csv"
)


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")


def pick_first(columns: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def main() -> int:
    for path in (RATINGS, MAPPING, MOMENTS):
        require_file(path)

    ratings = pd.read_csv(RATINGS, low_memory=False)
    mapping = pd.read_csv(MAPPING, low_memory=False)
    moments = pd.read_csv(MOMENTS, low_memory=False)

    if "review_item_id" not in ratings.columns:
        raise ValueError("Ratings missing review_item_id")
    if "review_item_id" not in mapping.columns:
        raise ValueError("Mapping missing review_item_id")

    if ratings["review_item_id"].duplicated().any():
        dup = ratings.loc[
            ratings["review_item_id"].duplicated(keep=False),
            "review_item_id"
        ].tolist()
        raise ValueError(f"Duplicate review_item_id in ratings: {dup}")

    if mapping["review_item_id"].duplicated().any():
        dup = mapping.loc[
            mapping["review_item_id"].duplicated(keep=False),
            "review_item_id"
        ].tolist()
        raise ValueError(f"Duplicate review_item_id in mapping: {dup}")

    merged = ratings.merge(
        mapping,
        on="review_item_id",
        how="left",
        validate="one_to_one",
        suffixes=("", "_mapping"),
        indicator="_mapping_merge",
    )

    missing_mapping = merged["_mapping_merge"].ne("both")
    if missing_mapping.any():
        missing_ids = merged.loc[missing_mapping, "review_item_id"].tolist()
        raise ValueError(f"Missing internal mapping for: {missing_ids}")

    merged = merged.drop(columns=["_mapping_merge"])

    moment_key = pick_first(
        merged.columns.tolist(),
        ["moment_id", "pilot_moment_id", "source_moment_id"],
    )

    moments_key = pick_first(
        moments.columns.tolist(),
        ["moment_id", "pilot_moment_id", "source_moment_id"],
    )

    if moment_key and moments_key:
        moment_extra_cols = [
            c for c in moments.columns
            if c == moments_key or c not in merged.columns
        ]
        moments_small = moments[moment_extra_cols].copy()

        if moments_small[moments_key].duplicated().any():
            raise ValueError(
                f"Duplicate {moments_key} in selected moments table"
            )

        merged = merged.merge(
            moments_small,
            left_on=moment_key,
            right_on=moments_key,
            how="left",
            validate="many_to_one",
            indicator="_moment_merge",
            suffixes=("", "_moment"),
        )

        if merged["_moment_merge"].ne("both").any():
            bad = merged.loc[
                merged["_moment_merge"].ne("both"),
                ["review_item_id", moment_key],
            ]
            raise ValueError(
                "Some reviewed items did not match the selected-moment table:\n"
                + bad.to_string(index=False)
            )

        merged = merged.drop(columns=["_moment_merge"])

        if moments_key != moment_key and moments_key in merged.columns:
            merged = merged.drop(columns=[moments_key])
    else:
        print(
            "WARNING: Could not identify a moment-id column shared between "
            "mapping and selected moments. Mapping join completed, but the "
            "selected-moment table was not joined."
        )

    sort_cols = [c for c in ["review_order", "review_item_id"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT, index=False)

    warning_series = merged.get(
        "qc_warning",
        pd.Series("", index=merged.index, dtype="object"),
    )
    warning_mask = (
        warning_series.fillna("").astype(str).str.strip().ne("")
    )
    warnings = merged.loc[warning_mask].copy()
    warnings.to_csv(WARN_OUT, index=False)

    stratum_col = pick_first(
        merged.columns.tolist(),
        ["sampling_stratum", "stratum", "selection_stratum", "pilot_stratum"],
    )

    if stratum_col is not None:
        overall = "overall_visibility_impairment"
        rows = []
        for stratum, g in merged.groupby(stratum_col, dropna=False):
            ov = pd.to_numeric(g[overall], errors="coerce")
            vc = ov.value_counts(dropna=False)
            rows.append(
                {
                    "stratum": stratum,
                    "n": len(g),
                    "overall_0": int(vc.get(0.0, 0)),
                    "overall_1": int(vc.get(1.0, 0)),
                    "overall_2": int(vc.get(2.0, 0)),
                    "overall_3": int(vc.get(3.0, 0)),
                    "overall_na": int(ov.isna().sum()),
                    "overall_mean_nonmissing": (
                        round(float(ov.mean()), 3) if ov.notna().any() else float("nan")
                    ),
                }
            )
        stratum_summary = pd.DataFrame(rows)
        stratum_summary.to_csv(STRATUM_OUT, index=False)
    else:
        stratum_summary = pd.DataFrame()
        print(
            "WARNING: No recognizable sampling-stratum column found; "
            "stratum summary was not created."
        )

    print("=== Phase 01 unblinding complete ===")
    print(f"ratings rows: {len(ratings)}")
    print(f"unique review items: {ratings['review_item_id'].nunique()}")
    print(f"merged rows: {len(merged)}")
    print(f"warning cases: {len(warnings)}")
    print()
    print(f"Saved: {OUT}")
    print(f"Saved: {WARN_OUT}")
    if not stratum_summary.empty:
        print(f"Saved: {STRATUM_OUT}")

    show_candidates = [
        "review_item_id",
        "moment_id",
        "case_id",
        "sample_time_sec",
        stratum_col,
        "overall_visibility_impairment",
        "confidence",
        "qc_warning",
        "comment",
    ]
    show_cols = [c for c in show_candidates if c is not None and c in merged.columns]

    print("\n=== Soft-warning cases ===")
    if warnings.empty:
        print("None")
    else:
        print(warnings[show_cols].to_string(index=False))

    if not stratum_summary.empty:
        print("\n=== Overall by sampling stratum ===")
        print(stratum_summary.to_string(index=False))

    print("\n=== Available columns in unblinded table ===")
    for c in merged.columns:
        print(c)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
