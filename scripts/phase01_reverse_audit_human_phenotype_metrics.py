#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

PHENOMENA = [
    "blur",
    "smoke",
    "lens_contamination",
    "whiteout",
    "underexposure",
    "blood_fluid",
    "near_contact",
]

QUALITY_METRICS = [
    "focus_badness_v1",
    "reblur_response_loss_v1",
    "veil_low_contrast_score_v1",
    "saturation_ratio",
    "specular_ratio",
    "low_light_or_blackout_ratio_v1",
    "center_low_structure_area_v1",
    "local_obstruction_max_component_ratio",
    "roi_edge_density_v1",
    "roi_gray_entropy_bits_v1",
    "roi_gray_mean_v1",
    "roi_gray_std_v1",
    "roi_v_mean_v1",
    "roi_v_std_v1",
    "roi_s_mean_v1",
    "roi_high_saturation_ratio_v1",
    "focus_lost_patch_ratio",
    "focus_lost_center_weighted_ratio",
    "focus_lost_max_component_ratio",
    "veil_low_contrast_score_v1__delta_prev",
    "veil_low_contrast_score_v1__abruptness",
    "center_low_structure_area_v1__abruptness",
]

COLOR_METRICS = [
    "blood_like_redness_ratio_v1",
    "center_weighted_blood_like_redness_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "red_dominance_ratio_v1",
    "red_excess_mean_v1",
    "red_saturation_mean_v1",
]

def parse_args():
    p = argparse.ArgumentParser(
        description="Reverse audit: human-confirmed visual phenotypes -> existing metrics."
    )
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--selected-full-metadata", required=True, type=Path)
    p.add_argument("--color-metrics", required=False, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--time-round-decimals", type=int, default=3)
    return p.parse_args()

def to_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna("").astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes", "y", "t"}
    )

def qstats(x: pd.Series):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return (np.nan, np.nan, np.nan, 0)
    return (x.quantile(0.25), x.median(), x.quantile(0.75), len(x))

def auc_from_ranks(values: pd.Series, labels: pd.Series):
    d = pd.DataFrame({
        "x": pd.to_numeric(values, errors="coerce"),
        "y": labels.astype(bool),
    }).dropna()
    n1 = int(d["y"].sum())
    n0 = int((~d["y"]).sum())
    if n1 == 0 or n0 == 0:
        return np.nan, n1, n0
    ranks = d["x"].rank(method="average")
    r1 = ranks[d["y"]].sum()
    auc = (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)
    return float(auc), n1, n0

def build_key(df: pd.DataFrame, decimals: int):
    case = df["case_id"].astype(str).str.strip().str.upper()
    t = pd.to_numeric(df["sample_time_sec"], errors="coerce").round(decimals)
    return case + "|" + t.map(lambda z: f"{z:.{decimals}f}" if pd.notna(z) else "NA")

def summarize(df: pd.DataFrame, metrics: list[str], scope: str):
    rows = []
    for p in PHENOMENA:
        lab = f"present_{p}"
        if lab not in df.columns:
            continue
        y = to_bool(df[lab])
        n_pos_total = int(y.sum())
        n_neg_total = int((~y).sum())
        if n_pos_total == 0 or n_neg_total == 0:
            continue

        for m in metrics:
            if m not in df.columns:
                continue
            x = pd.to_numeric(df[m], errors="coerce")
            p25_pos, med_pos, p75_pos, n_pos = qstats(x[y])
            p25_neg, med_neg, p75_neg, n_neg = qstats(x[~y])
            auc, auc_n_pos, auc_n_neg = auc_from_ranks(x, y)

            if pd.isna(auc):
                orientation = ""
                sep = np.nan
            elif auc >= 0.5:
                orientation = "higher_in_positive"
                sep = auc
            else:
                orientation = "lower_in_positive"
                sep = 1.0 - auc

            rows.append({
                "scope": scope,
                "phenomenon": p,
                "metric": m,
                "n_positive_total": n_pos_total,
                "n_negative_total": n_neg_total,
                "n_positive_metric_nonmissing": n_pos,
                "n_negative_metric_nonmissing": n_neg,
                "positive_q25": p25_pos,
                "positive_median": med_pos,
                "positive_q75": p75_pos,
                "negative_q25": p25_neg,
                "negative_median": med_neg,
                "negative_q75": p75_neg,
                "median_difference_pos_minus_neg": (
                    med_pos - med_neg
                    if pd.notna(med_pos) and pd.notna(med_neg)
                    else np.nan
                ),
                "rank_auc_positive_vs_negative": auc,
                "orientation": orientation,
                "oriented_separation_auc": sep,
                "note": (
                    "Development-set descriptive separation only; "
                    "metric-enriched sampling means this is not validation performance."
                ),
            })
    return pd.DataFrame(rows)

def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    labels = pd.read_csv(args.labels, low_memory=False)
    meta = pd.read_csv(args.selected_full_metadata, low_memory=False)

    if "audit_review_id" not in labels.columns or "audit_review_id" not in meta.columns:
        raise ValueError("Both labels and selected-full-metadata must contain audit_review_id.")

    if labels["audit_review_id"].duplicated().any():
        raise ValueError("Duplicate audit_review_id in labels.")
    if meta["audit_review_id"].duplicated().any():
        raise ValueError("Duplicate audit_review_id in selected full metadata.")

    merged = meta.merge(
        labels,
        on="audit_review_id",
        how="left",
        suffixes=("", "_label"),
        indicator=True,
    )
    missing_labels = merged.loc[merged["_merge"] != "both", "audit_review_id"].astype(str).tolist()
    if missing_labels:
        raise ValueError(f"Missing labels for {len(missing_labels)} audit frames.")

    # Normalize case/time columns after merge.
    if "case_id" not in merged.columns and "case_id_label" in merged.columns:
        merged["case_id"] = merged["case_id_label"]
    if "sample_time_sec" not in merged.columns and "sample_time_sec_label" in merged.columns:
        merged["sample_time_sec"] = merged["sample_time_sec_label"]

    merged["_merge_key"] = build_key(merged, args.time_round_decimals)

    color_status = "not_requested"
    color_rows = 0
    color_matched = 0
    color_duplicate_keys = 0

    if args.color_metrics is not None:
        if not args.color_metrics.exists():
            raise FileNotFoundError(args.color_metrics)

        usecols = ["case_id", "sample_time_sec"] + COLOR_METRICS
        color = pd.read_csv(
            args.color_metrics,
            usecols=lambda c: c in usecols,
            low_memory=False,
        )
        color_rows = len(color)
        color["_merge_key"] = build_key(color, args.time_round_decimals)
        color_duplicate_keys = int(color["_merge_key"].duplicated().sum())
        if color_duplicate_keys:
            raise ValueError(
                f"Color metrics have {color_duplicate_keys} duplicate case/time keys."
            )

        merged = merged.merge(
            color[["_merge_key"] + [c for c in COLOR_METRICS if c in color.columns]],
            on="_merge_key",
            how="left",
            suffixes=("", "_color"),
            indicator="_color_merge",
        )
        color_matched = int((merged["_color_merge"] == "both").sum())
        color_status = "merged"

    # Identify available metrics from the curated registry only.
    available_quality = [m for m in QUALITY_METRICS if m in merged.columns]
    available_color = [m for m in COLOR_METRICS if m in merged.columns]
    available_metrics = available_quality + available_color

    # Ensure label columns are boolean-compatible.
    for p in PHENOMENA:
        c = f"present_{p}"
        if c in merged.columns:
            merged[c] = to_bool(merged[c])

    if "nonstandard_imaging_mode" not in merged.columns:
        merged["nonstandard_imaging_mode"] = False
    else:
        merged["nonstandard_imaging_mode"] = to_bool(
            merged["nonstandard_imaging_mode"]
        )

    all_summary = summarize(merged, available_metrics, "all_frames")
    standard = merged.loc[~merged["nonstandard_imaging_mode"]].copy()
    standard_summary = summarize(
        standard, available_metrics, "standard_imaging_only"
    )

    combined = pd.concat(
        [all_summary, standard_summary],
        ignore_index=True,
        sort=False,
    )
    combined.to_csv(
        args.output_dir / "phase01_reverse_metric_audit_all_results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Rank within phenotype/scope by descriptive separation.
    ranked = combined.copy()
    ranked = ranked[
        ranked["oriented_separation_auc"].notna()
        & (ranked["n_positive_metric_nonmissing"] >= 3)
    ]
    ranked = ranked.sort_values(
        ["scope", "phenomenon", "oriented_separation_auc"],
        ascending=[True, True, False],
    )
    ranked["rank_within_phenomenon"] = (
        ranked.groupby(["scope", "phenomenon"]).cumcount() + 1
    )
    ranked.to_csv(
        args.output_dir / "phase01_reverse_metric_audit_ranked.csv",
        index=False,
        encoding="utf-8-sig",
    )

    top = ranked[ranked["rank_within_phenomenon"] <= 10].copy()
    top.to_csv(
        args.output_dir / "phase01_reverse_metric_audit_top10.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Focus table: only the constructs that currently have enough positive frames
    # or are scientifically important for refinement.
    focus_phenomena = [
        "lens_contamination",
        "blur",
        "smoke",
        "near_contact",
        "blood_fluid",
    ]
    focus = top[
        (top["scope"] == "standard_imaging_only")
        & top["phenomenon"].isin(focus_phenomena)
    ].copy()
    focus.to_csv(
        args.output_dir / "phase01_reverse_metric_audit_focus_constructs.csv",
        index=False,
        encoding="utf-8-sig",
    )

    qc = pd.DataFrame([{
        "label_rows": len(labels),
        "selected_metadata_rows": len(meta),
        "merged_audit_rows": len(merged),
        "standard_imaging_rows": len(standard),
        "nonstandard_imaging_rows": int(merged["nonstandard_imaging_mode"].sum()),
        "available_quality_metrics_n": len(available_quality),
        "available_color_metrics_n": len(available_color),
        "color_merge_status": color_status,
        "color_source_rows": color_rows,
        "color_matched_audit_frames": color_matched,
        "color_unmatched_audit_frames": len(merged) - color_matched
            if args.color_metrics is not None else np.nan,
        "color_duplicate_keys": color_duplicate_keys,
    }])
    qc.to_csv(
        args.output_dir / "phase01_reverse_metric_audit_qc.csv",
        index=False,
    )

    # Save compact registry used.
    pd.DataFrame(
        [{"metric": m, "source": "quality"} for m in available_quality]
        + [{"metric": m, "source": "color"} for m in available_color]
    ).to_csv(
        args.output_dir / "phase01_reverse_metric_audit_metric_registry.csv",
        index=False,
    )

    print("QC summary:")
    print(qc.to_string(index=False))
    print()
    print("Human-positive counts:")
    for p in PHENOMENA:
        c = f"present_{p}"
        if c in merged.columns:
            print(f"  {p}: {int(merged[c].sum())}/{len(merged)}")
    print()
    print("Top 5 metrics per focus phenotype (standard imaging only):")
    if focus.empty:
        print("  No focus results.")
    else:
        for p in focus_phenomena:
            g = focus[focus["phenomenon"] == p].head(5)
            if g.empty:
                continue
            print(f"\n[{p}]")
            print(
                g[
                    [
                        "metric",
                        "n_positive_metric_nonmissing",
                        "positive_median",
                        "negative_median",
                        "orientation",
                        "oriented_separation_auc",
                    ]
                ].to_string(index=False)
            )
    print()
    print(f"Saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
