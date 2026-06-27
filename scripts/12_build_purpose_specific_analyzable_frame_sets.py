#!/usr/bin/env python
"""Build purpose-specific analyzable frame sets for visual field phenotype analysis.

This script intentionally separates:
  1. hard technical exclusion,
  2. color-phenotype analyzability,
  3. structural/morphology analyzability,
  4. clean reference frame selection.

Rationale:
- p95 component cutoffs are too broad for hard exclusion before downstream
  blood-like redness / blackness / anthracosis-like phenotype analysis.
- p99 component cutoffs are useful severe-obstruction flags, but structural
  and center-low-structure p99 frames may still contain phenotype-rich red-out,
  blood-pool-like, tissue-contact-like, or dark-field information.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_ID_COLS = [
    "case_id",
    "frame_id",
    "frame_index",
    "time_sec",
    "timestamp_sec",
    "t",
    "source_video",
    "video_path",
    "frame_path",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
]

# Hard technical validity / failure columns, if present.
HARD_TECHNICAL_FLAG_COLS = [
    "image_validity_problem_candidate_v1",
    "photometric_failure_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
]

# Near-uniform is intentionally configurable. It can remove true technical
# failures but can also remove red-out / tissue-contact / phenotype-rich frames.
NEAR_UNIFORM_FLAG_COL = "near_uniform_frame_candidate_v1"

# Component metric columns used by the current Tier-1 gate.
COMPONENT_SCORE_COLS = [
    "structural_visibility_loss_v1",
    "center_low_structure_area_v1",
    "whiteout_ratio_v1",
    "low_light_or_blackout_ratio_v1",
]

# Flag naming candidates that may exist in visual_hazard_frame_flags.csv.
COMPONENT_FLAG_ALIASES = {
    "structural_visibility_loss": {
        "score": "structural_visibility_loss_v1",
        "p95": [
            "structural_visibility_loss_ge_p95",
            "flag_structural_visibility_loss_ge_p95",
            "visual_hazard_structural_visibility_loss_p95",
        ],
        "p99": [
            "structural_visibility_loss_ge_p99",
            "flag_structural_visibility_loss_ge_p99",
            "visual_hazard_structural_visibility_loss_p99",
        ],
    },
    "center_low_structure_area": {
        "score": "center_low_structure_area_v1",
        "p95": [
            "center_low_structure_area_ge_p95",
            "flag_center_low_structure_area_ge_p95",
            "visual_hazard_center_low_structure_area_p95",
        ],
        "p99": [
            "center_low_structure_area_ge_p99",
            "flag_center_low_structure_area_ge_p99",
            "visual_hazard_center_low_structure_area_p99",
        ],
    },
    "whiteout": {
        "score": "whiteout_ratio_v1",
        "p95": [
            "whiteout_ge_p95",
            "whiteout_ratio_ge_p95",
            "flag_whiteout_ge_p95",
            "visual_hazard_whiteout_p95",
        ],
        "p99": [
            "whiteout_ge_p99",
            "whiteout_ratio_ge_p99",
            "flag_whiteout_ge_p99",
            "visual_hazard_whiteout_p99",
        ],
    },
    "low_light_or_blackout": {
        "score": "low_light_or_blackout_ratio_v1",
        "p95": [
            "low_light_or_blackout_ge_p95",
            "low_light_or_blackout_ratio_ge_p95",
            "flag_low_light_or_blackout_ge_p95",
            "visual_hazard_low_light_or_blackout_p95",
        ],
        "p99": [
            "low_light_or_blackout_ge_p99",
            "low_light_or_blackout_ratio_ge_p99",
            "flag_low_light_or_blackout_ge_p99",
            "visual_hazard_low_light_or_blackout_p99",
        ],
    },
}

ANY_FLAG_ALIASES = {
    "p95": ["visual_hazard_any_p95", "any_visual_hazard_p95", "hazard_any_p95"],
    "p99": ["visual_hazard_any_p99", "any_visual_hazard_p99", "hazard_any_p99"],
}

CLEAN_FLAG_ALIASES = {
    "p95": ["clean_reference_candidate_p95", "clean_reference_p95"],
    "p99": ["clean_reference_candidate_p99", "clean_reference_p99"],
}

PHASE_CANDIDATES = [
    "level1_phase",
    "phase_level1",
    "level1_label",
    "phase",
    "phase_name",
    "surgical_phase",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build purpose-specific analyzable frame sets for field phenotype analysis."
    )
    parser.add_argument(
        "--frame-flags",
        required=True,
        help="Frame-level visual hazard flag CSV, e.g. visual_hazard_frame_flags.csv.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for summary CSV outputs.",
    )
    parser.add_argument(
        "--annotation-output-dir",
        default=None,
        help="Optional directory for frame manifest CSVs.",
    )
    parser.add_argument(
        "--include-near-uniform-as-technical-exclusion",
        action="store_true",
        help=(
            "Also hard-exclude near_uniform_frame_candidate_v1. Off by default because "
            "near-uniform red-out or tissue-contact frames may be phenotype-rich."
        ),
    )
    parser.add_argument(
        "--color-exclude-whiteout-p99",
        action="store_true",
        help=(
            "In addition to technical failures and p99 low-light/blackout, exclude whiteout p99 "
            "from color-phenotype analyzable frames. Default keeps it as a soft flag."
        ),
    )
    parser.add_argument(
        "--write-frame-manifests",
        action="store_true",
        help="Write full frame manifest CSVs for each analyzable set.",
    )
    parser.add_argument(
        "--id-col",
        nargs="*",
        default=None,
        help="Extra ID/path columns to keep at the left of output manifests if present.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def find_first_present(columns: Iterable[str], candidates: list[str]) -> str | None:
    colset = set(columns)
    for c in candidates:
        if c in colset:
            return c
    return None


def as_bool_series(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[col]
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False)
    if pd.api.types.is_numeric_dtype(s):
        return s.fillna(0).astype(float).ne(0)
    return s.astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y", "t"])


def build_quantile_flag_from_score(
    df: pd.DataFrame,
    score_col: str,
    quantile: float,
) -> tuple[pd.Series, float | None, str]:
    if score_col not in df.columns:
        return pd.Series(False, index=df.index), None, "missing_score_col"
    x = pd.to_numeric(df[score_col], errors="coerce")
    if x.notna().sum() == 0:
        return pd.Series(False, index=df.index), None, "all_missing_score_col"
    cutoff = float(x.quantile(quantile))
    return x.ge(cutoff).fillna(False), cutoff, "computed_from_score_quantile"


def get_component_flag(
    df: pd.DataFrame,
    component_key: str,
    threshold_name: str,
) -> tuple[pd.Series, str | None, float | None, str]:
    aliases = COMPONENT_FLAG_ALIASES[component_key][threshold_name]
    col = find_first_present(df.columns, aliases)
    if col:
        return as_bool_series(df, col), col, None, "existing_flag_col"
    score_col = COMPONENT_FLAG_ALIASES[component_key]["score"]
    q = 0.95 if threshold_name == "p95" else 0.99
    flag, cutoff, method = build_quantile_flag_from_score(df, score_col, q)
    return flag, None, cutoff, method


def get_any_flag(df: pd.DataFrame, threshold_name: str, component_flags: dict[str, pd.Series]) -> tuple[pd.Series, str | None, str]:
    col = find_first_present(df.columns, ANY_FLAG_ALIASES[threshold_name])
    if col:
        return as_bool_series(df, col), col, "existing_any_flag_col"
    any_flag = pd.Series(False, index=df.index)
    suffix = f"_{threshold_name}"
    for k, s in component_flags.items():
        if k.endswith(suffix):
            any_flag = any_flag | s
    return any_flag, None, "or_of_component_flags"


def safe_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def make_id_cols(df: pd.DataFrame, extra: list[str] | None) -> list[str]:
    candidates = DEFAULT_ID_COLS.copy()
    if extra:
        candidates = list(dict.fromkeys(extra + candidates))
    return [c for c in candidates if c in df.columns]


def summarize_set(df: pd.DataFrame, set_col: str, case_col: str | None, phase_col: str | None) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    total = len(df)
    n_true = int(as_bool_series(df, set_col).sum())
    overall = pd.DataFrame(
        [
            {
                "set_name": set_col,
                "total_frames": total,
                "n_in_set": n_true,
                "n_out_set": total - n_true,
                "frac_in_set": n_true / total if total else np.nan,
                "frac_out_set": (total - n_true) / total if total else np.nan,
            }
        ]
    )

    case_summary = None
    if case_col and case_col in df.columns:
        g = df.groupby(case_col, dropna=False)[set_col]
        case_summary = g.agg(total_frames="size", n_in_set="sum").reset_index()
        case_summary["n_out_set"] = case_summary["total_frames"] - case_summary["n_in_set"]
        case_summary["frac_in_set"] = case_summary["n_in_set"] / case_summary["total_frames"]
        case_summary["frac_out_set"] = case_summary["n_out_set"] / case_summary["total_frames"]
        case_summary.insert(0, "set_name", set_col)

    phase_summary = None
    if phase_col and phase_col in df.columns:
        group_cols = [phase_col]
        if case_col and case_col in df.columns:
            group_cols = [case_col, phase_col]
        g = df.groupby(group_cols, dropna=False)[set_col]
        phase_summary = g.agg(total_frames="size", n_in_set="sum").reset_index()
        phase_summary["n_out_set"] = phase_summary["total_frames"] - phase_summary["n_in_set"]
        phase_summary["frac_in_set"] = phase_summary["n_in_set"] / phase_summary["total_frames"]
        phase_summary["frac_out_set"] = phase_summary["n_out_set"] / phase_summary["total_frames"]
        phase_summary.insert(0, "set_name", set_col)

    return overall, case_summary, phase_summary


def main() -> int:
    args = parse_args()
    frame_path = Path(args.frame_flags)
    out_dir = Path(args.output_dir)
    ann_dir = Path(args.annotation_output_dir) if args.annotation_output_dir else None
    ensure_dir(out_dir)
    if ann_dir:
        ensure_dir(ann_dir)

    df = pd.read_csv(frame_path, low_memory=False)
    print(f"[OK] loaded frame flags rows={len(df)} cols={len(df.columns)}")

    case_col = "case_id" if "case_id" in df.columns else None
    phase_col = find_first_present(df.columns, PHASE_CANDIDATES)
    print(f"[OK] case column: {case_col or 'not_found'}")
    print(f"[OK] phase column: {phase_col or 'not_found'}")

    # Component flags p95/p99. Computed if existing flags are absent.
    component_flags: dict[str, pd.Series] = {}
    flag_inventory_rows = []
    for comp in COMPONENT_FLAG_ALIASES:
        for thr in ["p95", "p99"]:
            s, source_col, cutoff, method = get_component_flag(df, comp, thr)
            key = f"{comp}_{thr}"
            component_flags[key] = s
            out_col = f"flag_{comp}_ge_{thr}"
            df[out_col] = s.astype(int)
            flag_inventory_rows.append(
                {
                    "flag_key": key,
                    "output_col": out_col,
                    "source_col": source_col,
                    "score_col": COMPONENT_FLAG_ALIASES[comp]["score"],
                    "threshold_name": thr,
                    "computed_cutoff_if_any": cutoff,
                    "method": method,
                    "n_flagged": int(s.sum()),
                    "frac_flagged": float(s.mean()) if len(s) else np.nan,
                }
            )

    any_p95, any_p95_col, any_p95_method = get_any_flag(df, "p95", component_flags)
    any_p99, any_p99_col, any_p99_method = get_any_flag(df, "p99", component_flags)
    df["visual_hazard_any_p95_for_sets"] = any_p95.astype(int)
    df["visual_hazard_any_p99_for_sets"] = any_p99.astype(int)
    flag_inventory_rows.extend(
        [
            {
                "flag_key": "visual_hazard_any_p95",
                "output_col": "visual_hazard_any_p95_for_sets",
                "source_col": any_p95_col,
                "score_col": "",
                "threshold_name": "p95",
                "computed_cutoff_if_any": np.nan,
                "method": any_p95_method,
                "n_flagged": int(any_p95.sum()),
                "frac_flagged": float(any_p95.mean()) if len(any_p95) else np.nan,
            },
            {
                "flag_key": "visual_hazard_any_p99",
                "output_col": "visual_hazard_any_p99_for_sets",
                "source_col": any_p99_col,
                "score_col": "",
                "threshold_name": "p99",
                "computed_cutoff_if_any": np.nan,
                "method": any_p99_method,
                "n_flagged": int(any_p99.sum()),
                "frac_flagged": float(any_p99.mean()) if len(any_p99) else np.nan,
            },
        ]
    )

    # Hard technical exclusion.
    hard_reason_cols = [c for c in HARD_TECHNICAL_FLAG_COLS if c in df.columns]
    if args.include_near_uniform_as_technical_exclusion and NEAR_UNIFORM_FLAG_COL in df.columns:
        hard_reason_cols.append(NEAR_UNIFORM_FLAG_COL)

    technical_exclusion = pd.Series(False, index=df.index)
    for c in hard_reason_cols:
        technical_exclusion = technical_exclusion | as_bool_series(df, c)

    df["technical_exclusion_frame_v1"] = technical_exclusion.astype(int)
    df["technical_analyzable_frame_v1"] = (~technical_exclusion).astype(int)

    # Purpose-specific sets.
    low_light_p99 = component_flags["low_light_or_blackout_p99"]
    whiteout_p99 = component_flags["whiteout_p99"]
    structural_p99 = component_flags["structural_visibility_loss_p99"]
    center_p99 = component_flags["center_low_structure_area_p99"]

    # Color phenotype: keep structural/center p99 as soft flags, exclude technical and severe low-light.
    color_exclusion = technical_exclusion | low_light_p99
    if args.color_exclude_whiteout_p99:
        color_exclusion = color_exclusion | whiteout_p99
    df["color_phenotype_analyzable_frame_v1"] = (~color_exclusion).astype(int)

    # Structural/morphology phenotype: stricter because low-structure / whiteout / blackout disrupt morphology.
    structural_exclusion = technical_exclusion | any_p99
    df["structural_phenotype_analyzable_frame_v1"] = (~structural_exclusion).astype(int)

    # Clean reference: conservative, not the main phenotype analysis set.
    clean_flag_col = find_first_present(df.columns, CLEAN_FLAG_ALIASES["p95"])
    if clean_flag_col:
        clean_reference = as_bool_series(df, clean_flag_col) & (~technical_exclusion)
        clean_method = f"existing_{clean_flag_col}_and_not_technical_exclusion"
    else:
        clean_reference = (~technical_exclusion) & (~any_p95)
        clean_method = "not_technical_exclusion_and_not_any_p95"
    df["clean_reference_frame_p95_v1"] = clean_reference.astype(int)

    # Soft flags to preserve phenotype-rich severe visual hazard frames.
    df["softflag_structural_visibility_loss_ge_p99_v1"] = structural_p99.astype(int)
    df["softflag_center_low_structure_area_ge_p99_v1"] = center_p99.astype(int)
    df["softflag_whiteout_ge_p99_v1"] = whiteout_p99.astype(int)
    df["softflag_low_light_or_blackout_ge_p99_v1"] = low_light_p99.astype(int)
    df["softflag_visual_hazard_any_ge_p99_v1"] = any_p99.astype(int)
    df["softflag_visual_hazard_any_ge_p95_v1"] = any_p95.astype(int)

    # Technical reason summary.
    reason_rows = []
    for c in hard_reason_cols:
        s = as_bool_series(df, c)
        reason_rows.append({"reason_col": c, "n_frames": int(s.sum()), "frac_frames": float(s.mean())})
    if not hard_reason_cols:
        reason_rows.append({"reason_col": "none_found", "n_frames": 0, "frac_frames": 0.0})
    pd.DataFrame(reason_rows).to_csv(out_dir / "technical_exclusion_reason_summary.csv", index=False)

    # Summary tables for sets.
    set_cols = [
        "technical_analyzable_frame_v1",
        "color_phenotype_analyzable_frame_v1",
        "structural_phenotype_analyzable_frame_v1",
        "clean_reference_frame_p95_v1",
    ]
    overall_parts = []
    case_parts = []
    phase_parts = []
    for set_col in set_cols:
        overall, case_summary, phase_summary = summarize_set(df, set_col, case_col, phase_col)
        overall_parts.append(overall)
        if case_summary is not None:
            case_parts.append(case_summary)
        if phase_summary is not None:
            phase_parts.append(phase_summary)
    pd.concat(overall_parts, ignore_index=True).to_csv(out_dir / "frame_set_overall_summary.csv", index=False)
    if case_parts:
        pd.concat(case_parts, ignore_index=True).to_csv(out_dir / "case_frame_set_summary.csv", index=False)
    else:
        pd.DataFrame(columns=["set_name", "case_id", "total_frames", "n_in_set", "n_out_set", "frac_in_set", "frac_out_set"]).to_csv(out_dir / "case_frame_set_summary.csv", index=False)
    if phase_parts:
        pd.concat(phase_parts, ignore_index=True).to_csv(out_dir / "case_phase_frame_set_summary.csv", index=False)
    else:
        pd.DataFrame(columns=["set_name", "case_id", "level1_phase", "total_frames", "n_in_set", "n_out_set", "frac_in_set", "frac_out_set"]).to_csv(out_dir / "case_phase_frame_set_summary.csv", index=False)

    # Soft flag summary.
    soft_cols = [c for c in df.columns if c.startswith("softflag_")]
    soft_rows = []
    for c in soft_cols:
        s = as_bool_series(df, c)
        soft_rows.append({"soft_flag_col": c, "n_flagged": int(s.sum()), "frac_flagged": float(s.mean())})
    pd.DataFrame(soft_rows).to_csv(out_dir / "soft_visual_hazard_flag_summary.csv", index=False)

    pd.DataFrame(flag_inventory_rows).to_csv(out_dir / "frame_set_flag_inventory.csv", index=False)
    pd.DataFrame(
        [
            {
                "parameter": "clean_reference_method",
                "value": clean_method,
            },
            {
                "parameter": "near_uniform_hard_excluded",
                "value": str(bool(args.include_near_uniform_as_technical_exclusion)),
            },
            {
                "parameter": "color_exclude_whiteout_p99",
                "value": str(bool(args.color_exclude_whiteout_p99)),
            },
            {
                "parameter": "hard_technical_reason_cols",
                "value": ";".join(hard_reason_cols),
            },
        ]
    ).to_csv(out_dir / "frame_set_parameters.csv", index=False)

    # Optional frame manifests.
    if args.write_frame_manifests:
        if ann_dir is None:
            print("[ERROR] --write-frame-manifests requires --annotation-output-dir", file=sys.stderr)
            return 2
        id_cols = make_id_cols(df, args.id_col)
        useful_flag_cols = [
            "technical_exclusion_frame_v1",
            "technical_analyzable_frame_v1",
            "color_phenotype_analyzable_frame_v1",
            "structural_phenotype_analyzable_frame_v1",
            "clean_reference_frame_p95_v1",
            "visual_hazard_any_p95_for_sets",
            "visual_hazard_any_p99_for_sets",
        ] + soft_cols
        useful_flag_cols = [c for c in useful_flag_cols if c in df.columns]
        score_cols = [c for c in COMPONENT_SCORE_COLS if c in df.columns]
        manifest_cols = list(dict.fromkeys(id_cols + score_cols + useful_flag_cols + hard_reason_cols))
        if not manifest_cols:
            manifest_cols = list(df.columns)

        def write_subset(mask_col: str, filename: str, positive: bool = True) -> None:
            mask = as_bool_series(df, mask_col)
            if not positive:
                mask = ~mask
            df.loc[mask, manifest_cols].to_csv(ann_dir / filename, index=False)

        write_subset("technical_analyzable_frame_v1", "technical_analyzable_frames_v1.csv")
        write_subset("technical_analyzable_frame_v1", "technical_excluded_frames_v1.csv", positive=False)
        write_subset("color_phenotype_analyzable_frame_v1", "color_phenotype_analyzable_frames_v1.csv")
        write_subset("structural_phenotype_analyzable_frame_v1", "structural_phenotype_analyzable_frames_v1.csv")
        write_subset("clean_reference_frame_p95_v1", "clean_reference_frames_p95_v1.csv")
        df.loc[any_p99, manifest_cols].to_csv(ann_dir / "severe_visual_obstruction_softflag_p99_v1.csv", index=False)

    print(f"[OK] wrote {out_dir / 'frame_set_overall_summary.csv'}")
    print(f"[OK] wrote {out_dir / 'case_frame_set_summary.csv'}")
    print(f"[OK] wrote {out_dir / 'case_phase_frame_set_summary.csv'}")
    print(f"[OK] wrote {out_dir / 'technical_exclusion_reason_summary.csv'}")
    print(f"[OK] wrote {out_dir / 'soft_visual_hazard_flag_summary.csv'}")
    print("[OK] purpose-specific analyzable frame sets complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
