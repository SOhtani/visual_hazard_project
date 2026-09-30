#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 01 - Construct-specific metric correspondence analysis.

Input
-----
reports/phase01_pilot_sampling/phase01_unblinded_calibration.csv

Outputs
-------
reports/phase01_pilot_sampling/phase01_construct_metric_correspondence.csv
reports/phase01_pilot_sampling/phase01_construct_metric_score_summary.csv
reports/phase01_pilot_sampling/phase01_warning_case_detail.csv

Interpretation
--------------
This is a 30-image, deliberately enriched, single-reviewer calibration pilot.
The script reports descriptive rank correspondence only.
It does NOT calculate p-values and should not be treated as independent
validation, prevalence estimation, or clinical-effect analysis.
"""

from __future__ import annotations

from pathlib import Path
import math
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_unblinded_calibration.csv"
)

OUT_CORR = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_construct_metric_correspondence.csv"
)

OUT_SCORE = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_construct_metric_score_summary.csv"
)

OUT_WARN = (
    ROOT / "reports" / "phase01_pilot_sampling"
    / "phase01_warning_case_detail.csv"
)


# Prespecified construct-to-metric candidates.
# "primary" means first candidate to inspect, not a validated winner.
MAPPINGS = [
    # Global visibility
    ("overall_visibility", "overall_visibility_impairment",
     "structural_visibility_loss_v1", "primary"),
    ("overall_visibility", "overall_visibility_impairment",
     "composite_badness_v4", "secondary"),
    ("overall_visibility", "overall_visibility_impairment",
     "center_low_structure_area_v1", "secondary"),

    # Blur / focus
    ("blur_defocus", "component_blur_defocus",
     "focus_badness_v1", "primary"),
    ("blur_defocus", "component_blur_defocus",
     "reblur_response_loss_v1", "secondary"),
    ("blur_defocus", "component_blur_defocus",
     "blur_like_mean", "legacy"),

    # Smoke / fog / veil
    ("smoke_fog_veil", "component_smoke_fog_veil",
     "veil_low_contrast_score_v1", "primary"),
    ("smoke_fog_veil", "component_smoke_fog_veil",
     "veil_smoke_mean", "legacy"),

    # Whiteout / overexposure
    ("whiteout_overexposure", "component_whiteout_overexposure",
     "whiteout_ratio_v1", "primary"),
    ("whiteout_overexposure", "component_whiteout_overexposure",
     "whiteout_center_weighted_ratio_v1", "secondary"),
    ("whiteout_overexposure", "component_whiteout_overexposure",
     "saturation_ratio", "legacy"),

    # Glare / specularity
    ("glare_specular", "component_glare_specular",
     "specular_like_ratio_v1", "primary"),
    ("glare_specular", "component_glare_specular",
     "specular_center_weighted_ratio_v1", "secondary"),
    ("glare_specular", "component_glare_specular",
     "specular_ratio", "legacy"),

    # Underexposure / blackout
    ("underexposure_blackout", "component_underexposure_blackout",
     "low_light_or_blackout_ratio_v1", "primary"),
    ("underexposure_blackout", "component_underexposure_blackout",
     "low_light_center_weighted_ratio_v1", "secondary"),

    # Physical obstruction
    ("physical_obstruction", "component_physical_obstruction",
     "local_obstruction_ratio", "primary_proxy"),
    ("physical_obstruction", "component_physical_obstruction",
     "local_obstruction_max_component_ratio", "secondary_proxy"),
]

NO_DIRECT_METRIC = [
    ("blood_fluid", "component_blood_fluid",
     "No dedicated blood/fluid visibility metric in the current table."),
    ("lens_contamination", "component_lens_contamination",
     "No dedicated lens-contamination metric in the current table."),
    ("near_contact_redout", "component_near_contact_redout",
     "No validated direct near-contact/red-out metric. Do not treat structural proxies as direct measures."),
]


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")


def spearman_rank_corr(x: pd.Series, y: pd.Series) -> float:
    """
    Spearman rho as Pearson correlation of average ranks.
    Avoids inferential p-values in this calibration pilot.
    """
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    mask = x.notna() & y.notna()
    x = x.loc[mask]
    y = y.loc[mask]

    if len(x) < 3:
        return float("nan")
    if x.nunique() < 2 or y.nunique() < 2:
        return float("nan")

    xr = x.rank(method="average")
    yr = y.rank(method="average")
    return float(xr.corr(yr, method="pearson"))


def score_range_note(s: pd.Series) -> str:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return "no human scores"
    levels = sorted(set(int(v) for v in s.unique()))
    if levels == [0, 1]:
        return "only 0-1 represented"
    if max(levels) < 2:
        return "no moderate/severe scores"
    if 3 not in levels:
        return "score 3 absent"
    return "0-3 range includes severe"


def quantile_or_nan(s: pd.Series, q: float) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return float("nan")
    return float(s.quantile(q))


def main() -> int:
    require_file(INPUT)
    d = pd.read_csv(INPUT, low_memory=False)

    required = [
        "review_item_id",
        "technical_evaluable",
        "task_context_sufficient",
        "overall_visibility_impairment",
        "imaging_mode_context",
    ]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Analysis universe: technically evaluable + sufficient context.
    valid = d[
        pd.to_numeric(d["technical_evaluable"], errors="coerce").eq(1)
        & pd.to_numeric(d["task_context_sufficient"], errors="coerce").eq(1)
    ].copy()

    print("=== Construct-specific calibration analysis ===")
    print(f"Input rows: {len(d)}")
    print(f"Analyzable human-rated rows: {len(valid)}")
    print(
        "Standard visible-light rows: "
        f"{valid['imaging_mode_context'].eq('Standard visible-light').sum()}"
    )
    print(
        "Firefly / ICG rows: "
        f"{valid['imaging_mode_context'].eq('Firefly / ICG').sum()}"
    )

    corr_rows = []
    score_rows = []

    for construct, human_col, metric_col, role in MAPPINGS:
        if human_col not in valid.columns:
            print(f"WARNING: missing human column: {human_col}")
            continue
        if metric_col not in valid.columns:
            print(f"WARNING: missing metric column: {metric_col}")
            continue

        g = valid[[human_col, metric_col, "imaging_mode_context"]].copy()
        g[human_col] = pd.to_numeric(g[human_col], errors="coerce")
        g[metric_col] = pd.to_numeric(g[metric_col], errors="coerce")
        g = g.dropna(subset=[human_col, metric_col])

        standard = g[g["imaging_mode_context"].eq("Standard visible-light")].copy()

        corr_rows.append(
            {
                "construct": construct,
                "human_column": human_col,
                "metric": metric_col,
                "metric_role": role,
                "n_all": len(g),
                "human_levels_all": ",".join(
                    str(int(v)) for v in sorted(g[human_col].dropna().unique())
                ),
                "score_range_note": score_range_note(g[human_col]),
                "spearman_rho_all": (
                    round(spearman_rank_corr(g[human_col], g[metric_col]), 3)
                    if len(g) >= 3 else np.nan
                ),
                "n_standard_only": len(standard),
                "spearman_rho_standard_only": (
                    round(
                        spearman_rank_corr(
                            standard[human_col],
                            standard[metric_col],
                        ),
                        3,
                    )
                    if len(standard) >= 3 else np.nan
                ),
            }
        )

        for score in [0, 1, 2, 3]:
            sg = g[g[human_col].eq(score)][metric_col]
            score_rows.append(
                {
                    "construct": construct,
                    "human_column": human_col,
                    "metric": metric_col,
                    "metric_role": role,
                    "human_score": score,
                    "n": int(sg.notna().sum()),
                    "metric_median": (
                        round(float(sg.median()), 6)
                        if sg.notna().any() else np.nan
                    ),
                    "metric_q25": (
                        round(quantile_or_nan(sg, 0.25), 6)
                        if sg.notna().any() else np.nan
                    ),
                    "metric_q75": (
                        round(quantile_or_nan(sg, 0.75), 6)
                        if sg.notna().any() else np.nan
                    ),
                }
            )

    corr = pd.DataFrame(corr_rows)
    score_summary = pd.DataFrame(score_rows)

    OUT_CORR.parent.mkdir(parents=True, exist_ok=True)
    corr.to_csv(OUT_CORR, index=False)
    score_summary.to_csv(OUT_SCORE, index=False)

    # Warning-case details: human scores + key metrics, for manual review.
    warning_mask = d.get(
        "qc_warning",
        pd.Series("", index=d.index, dtype="object")
    ).fillna("").astype(str).str.strip().ne("")

    key_cols = [
        "review_item_id",
        "moment_id",
        "case_id",
        "sample_time_sec",
        "selection_stratum",
        "selection_metric",
        "selection_value",
        "overall_visibility_impairment",
        "component_blur_defocus",
        "component_smoke_fog_veil",
        "component_blood_fluid",
        "component_glare_specular",
        "component_whiteout_overexposure",
        "component_underexposure_blackout",
        "component_physical_obstruction",
        "component_lens_contamination",
        "component_near_contact_redout",
        "confidence",
        "qc_warning",
        "comment",
        "structural_visibility_loss_v1",
        "focus_badness_v1",
        "veil_low_contrast_score_v1",
        "whiteout_ratio_v1",
        "specular_like_ratio_v1",
        "low_light_or_blackout_ratio_v1",
        "local_obstruction_ratio",
        "center_low_structure_area_v1",
    ]
    key_cols = [c for c in key_cols if c in d.columns]
    warning_detail = d.loc[warning_mask, key_cols].copy()
    warning_detail.to_csv(OUT_WARN, index=False)

    print("\n=== Prespecified construct-metric rank correspondence ===")
    if corr.empty:
        print("No analyzable mappings.")
    else:
        display_cols = [
            "construct",
            "metric",
            "metric_role",
            "n_all",
            "human_levels_all",
            "score_range_note",
            "spearman_rho_all",
            "spearman_rho_standard_only",
        ]
        print(corr[display_cols].to_string(index=False))

    print("\n=== Human score distributions ===")
    human_cols = [
        "overall_visibility_impairment",
        "component_blur_defocus",
        "component_smoke_fog_veil",
        "component_blood_fluid",
        "component_glare_specular",
        "component_whiteout_overexposure",
        "component_underexposure_blackout",
        "component_physical_obstruction",
        "component_lens_contamination",
        "component_near_contact_redout",
    ]
    for col in human_cols:
        if col not in valid.columns:
            continue
        vc = (
            pd.to_numeric(valid[col], errors="coerce")
            .value_counts(dropna=False)
            .sort_index()
        )
        print(f"\n{col}")
        print(vc.to_string())

    print("\n=== Constructs without a direct current metric ===")
    for construct, human_col, note in NO_DIRECT_METRIC:
        levels = ""
        if human_col in valid.columns:
            s = pd.to_numeric(valid[human_col], errors="coerce").dropna()
            levels = ",".join(str(int(v)) for v in sorted(s.unique()))
        print(f"{construct}: human levels [{levels}] - {note}")

    print("\n=== Soft-warning detail ===")
    if warning_detail.empty:
        print("None")
    else:
        print(warning_detail.to_string(index=False))

    print("\nSaved:")
    print(OUT_CORR)
    print(OUT_SCORE)
    print(OUT_WARN)

    print(
        "\nNOTE: rho values are descriptive only. "
        "The 30 images were deliberately enriched and rated by one reviewer "
        "during instrument calibration; do not treat these as validation statistics."
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
