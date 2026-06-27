#!/usr/bin/env python
"""
Build figure-ready exploratory outputs from the case-level visual hazard clinical linkage table.

This script intentionally uses an explicit whitelist for clinical variables so that identifiers,
availability flags, and other metadata-derived numeric columns are not accidentally treated as
clinical endpoints.

Inputs:
  - reports/clinical_linkage_clean/case_visual_hazard_clinical_linkage.csv

Outputs:
  - primary_clinical_hazard_spearman.csv
  - group_burden_summary_whitelist_long.csv
  - top_cases_by_figure_metric.csv
  - figure_manifest.csv
  - optional PNG figures under scatter_plots/ and boxplots/
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_CLINICAL_COLS = [
    "operation_time_min",
    "blood_loss_g",
    "age",
]

DEFAULT_HAZARD_COLS = [
    "frac_visual_hazard_any_p95",
    "frac_visual_hazard_any_p99",
    "seconds_visual_hazard_any_p95",
    "seconds_visual_hazard_any_p99",
    "max_consecutive_seconds_visual_hazard_any_p95",
    "max_consecutive_seconds_visual_hazard_any_p99",
    "mean_hazard_component_count_p95",
    "mean_hazard_component_count_p99",
    "frac_center_low_structure_area_ge_p95",
    "frac_structural_visibility_loss_ge_p95",
    "frac_whiteout_ge_p95",
    "frac_low_light_or_blackout_ge_p95",
    "frac_center_low_structure_area_ge_p99",
    "frac_structural_visibility_loss_ge_p99",
    "frac_whiteout_ge_p99",
    "frac_low_light_or_blackout_ge_p99",
]

DEFAULT_CORE_HAZARD_COLS = [
    "frac_visual_hazard_any_p95",
    "frac_visual_hazard_any_p99",
    "seconds_visual_hazard_any_p95",
    "seconds_visual_hazard_any_p99",
    "max_consecutive_seconds_visual_hazard_any_p95",
    "max_consecutive_seconds_visual_hazard_any_p99",
]

DEFAULT_GROUP_COLS = [
    "procedure_group",
    "side",
    "sex",
    "target_lobe_or_segment",
]

DEFAULT_TOP_CASE_COLS = [
    "case_id",
    "procedure_group",
    "side",
    "target_lobe_or_segment",
    "age",
    "sex",
    "operation_time_min",
    "blood_loss_g",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build figure-ready exploratory summaries from clinical linkage table."
    )
    parser.add_argument(
        "--linkage-csv",
        default="reports/clinical_linkage_clean/case_visual_hazard_clinical_linkage.csv",
        help="Case-level clinical linkage CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/figure_ready_exploration",
        help="Output directory for figure-ready tables and optional figures.",
    )
    parser.add_argument(
        "--clinical-col",
        nargs="*",
        default=None,
        help="Explicit clinical numeric columns to correlate with hazard burden. Defaults to operation_time_min blood_loss_g age.",
    )
    parser.add_argument(
        "--hazard-col",
        nargs="*",
        default=None,
        help="Explicit hazard burden columns. Defaults to core visual hazard and component fraction columns.",
    )
    parser.add_argument(
        "--core-hazard-col",
        nargs="*",
        default=None,
        help="Core hazard columns for compact inspection and plotting. Defaults to any p95/p99 seconds/fraction/max consecutive.",
    )
    parser.add_argument(
        "--group-col",
        nargs="*",
        default=None,
        help="Categorical grouping columns for boxplot-ready summaries.",
    )
    parser.add_argument(
        "--min-n",
        type=int,
        default=5,
        help="Minimum complete cases for Spearman correlations.",
    )
    parser.add_argument(
        "--min-group-n",
        type=int,
        default=3,
        help="Minimum cases per group for group summaries and boxplots.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top cases to output per selected hazard metric.",
    )
    parser.add_argument(
        "--make-plots",
        action="store_true",
        help="Generate simple PNG scatter plots and group boxplots using matplotlib.",
    )
    return parser.parse_args()


def existing_columns(df: pd.DataFrame, cols: Iterable[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def safe_filename(text: str, max_len: int = 160) -> str:
    text = str(text)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] if len(text) > max_len else text


def quantile_or_nan(s: pd.Series, q: float) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return float("nan")
    return float(s.quantile(q))


def build_correlations(
    df: pd.DataFrame,
    clinical_cols: list[str],
    hazard_cols: list[str],
    min_n: int,
) -> pd.DataFrame:
    rows = []
    for c in clinical_cols:
        for h in hazard_cols:
            sub = df[[c, h]].copy()
            sub[c] = numeric_series(sub[c])
            sub[h] = numeric_series(sub[h])
            sub = sub.dropna()
            if len(sub) < min_n:
                continue
            if sub[c].nunique() < 2 or sub[h].nunique() < 2:
                continue
            rho = sub[c].corr(sub[h], method="spearman")
            rows.append(
                {
                    "clinical_col": c,
                    "hazard_col": h,
                    "n": int(len(sub)),
                    "spearman_rho": float(rho) if pd.notna(rho) else np.nan,
                    "abs_spearman_rho": abs(float(rho)) if pd.notna(rho) else np.nan,
                    "clinical_median": float(sub[c].median()),
                    "clinical_q25": float(sub[c].quantile(0.25)),
                    "clinical_q75": float(sub[c].quantile(0.75)),
                    "hazard_median": float(sub[h].median()),
                    "hazard_q25": float(sub[h].quantile(0.25)),
                    "hazard_q75": float(sub[h].quantile(0.75)),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "clinical_col",
                "hazard_col",
                "n",
                "spearman_rho",
                "abs_spearman_rho",
                "clinical_median",
                "clinical_q25",
                "clinical_q75",
                "hazard_median",
                "hazard_q25",
                "hazard_q75",
            ]
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["abs_spearman_rho", "clinical_col", "hazard_col"], ascending=[False, True, True])


def build_group_summary(
    df: pd.DataFrame,
    group_cols: list[str],
    hazard_cols: list[str],
    min_group_n: int,
) -> pd.DataFrame:
    rows = []
    for g in group_cols:
        tmp = df[[g] + hazard_cols].copy()
        tmp[g] = tmp[g].astype("string").fillna("Missing")
        for h in hazard_cols:
            tmp[h] = numeric_series(tmp[h])
        for group_value, sub in tmp.groupby(g, dropna=False):
            n_cases = int(len(sub))
            if n_cases < min_group_n:
                continue
            for h in hazard_cols:
                vals = sub[h].dropna()
                if vals.empty:
                    continue
                rows.append(
                    {
                        "group_col": g,
                        "group_value": str(group_value),
                        "hazard_col": h,
                        "n_cases": n_cases,
                        "n_nonmissing": int(vals.shape[0]),
                        "median": float(vals.median()),
                        "q25": quantile_or_nan(vals, 0.25),
                        "q75": quantile_or_nan(vals, 0.75),
                        "mean": float(vals.mean()),
                        "min": float(vals.min()),
                        "max": float(vals.max()),
                    }
                )
    if not rows:
        return pd.DataFrame(
            columns=["group_col", "group_value", "hazard_col", "n_cases", "n_nonmissing", "median", "q25", "q75", "mean", "min", "max"]
        )
    return pd.DataFrame(rows).sort_values(["group_col", "hazard_col", "group_value"])


def build_top_cases(
    df: pd.DataFrame,
    hazard_cols: list[str],
    top_n: int,
) -> pd.DataFrame:
    rows = []
    base_cols = existing_columns(df, DEFAULT_TOP_CASE_COLS)
    for h in hazard_cols:
        tmp = df.copy()
        tmp[h] = numeric_series(tmp[h])
        tmp = tmp.dropna(subset=[h]).sort_values(h, ascending=False).head(top_n)
        for rank, (_, row) in enumerate(tmp.iterrows(), start=1):
            rec = {"rank_metric": h, "rank": rank, "rank_value": row[h]}
            for c in base_cols:
                rec[c] = row[c]
            for c in hazard_cols:
                if c in df.columns:
                    rec[c] = row[c]
            rows.append(rec)
    return pd.DataFrame(rows)


def write_missing_inventory(out_dir: Path, requested: dict[str, list[str]], df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for kind, cols in requested.items():
        for c in cols:
            rows.append({"column_role": kind, "column": c, "exists": c in df.columns})
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "requested_column_inventory.csv", index=False)
    return out


def make_scatter_plot(df: pd.DataFrame, x_col: str, y_col: str, rho: float, out_path: Path) -> None:
    import matplotlib.pyplot as plt

    sub = df[[x_col, y_col]].copy()
    sub[x_col] = numeric_series(sub[x_col])
    sub[y_col] = numeric_series(sub[y_col])
    sub = sub.dropna()
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(sub[x_col], sub[y_col], alpha=0.75)
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    title_rho = "NA" if pd.isna(rho) else f"{rho:.3f}"
    ax.set_title(f"Spearman rho = {title_rho}, n = {len(sub)}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def make_boxplot(df: pd.DataFrame, group_col: str, y_col: str, min_group_n: int, out_path: Path) -> bool:
    import matplotlib.pyplot as plt

    tmp = df[[group_col, y_col]].copy()
    tmp[group_col] = tmp[group_col].astype("string").fillna("Missing")
    tmp[y_col] = numeric_series(tmp[y_col])
    tmp = tmp.dropna(subset=[y_col])
    groups = []
    labels = []
    for label, sub in tmp.groupby(group_col, dropna=False):
        vals = sub[y_col].dropna().to_numpy()
        if vals.size >= min_group_n:
            groups.append(vals)
            labels.append(str(label))
    if len(groups) < 2:
        return False
    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(labels)), 4.5))
    ax.boxplot(groups, labels=labels, showfliers=True)
    ax.set_xlabel(group_col)
    ax.set_ylabel(y_col)
    ax.set_title(f"{y_col} by {group_col}")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return True


def main() -> None:
    args = parse_args()
    linkage_csv = Path(args.linkage_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not linkage_csv.exists():
        raise FileNotFoundError(f"linkage CSV not found: {linkage_csv}")

    df = pd.read_csv(linkage_csv, low_memory=False)

    requested_clinical = args.clinical_col if args.clinical_col is not None else DEFAULT_CLINICAL_COLS
    requested_hazard = args.hazard_col if args.hazard_col is not None else DEFAULT_HAZARD_COLS
    requested_core = args.core_hazard_col if args.core_hazard_col is not None else DEFAULT_CORE_HAZARD_COLS
    requested_groups = args.group_col if args.group_col is not None else DEFAULT_GROUP_COLS

    clinical_cols = existing_columns(df, requested_clinical)
    hazard_cols = existing_columns(df, requested_hazard)
    core_hazard_cols = existing_columns(df, requested_core)
    group_cols = existing_columns(df, requested_groups)

    write_missing_inventory(
        out_dir,
        {
            "clinical": requested_clinical,
            "hazard": requested_hazard,
            "core_hazard": requested_core,
            "group": requested_groups,
        },
        df,
    )

    if not clinical_cols:
        raise ValueError("No requested clinical columns found in linkage table.")
    if not hazard_cols:
        raise ValueError("No requested hazard columns found in linkage table.")

    corr = build_correlations(df, clinical_cols, hazard_cols, args.min_n)
    corr_path = out_dir / "primary_clinical_hazard_spearman.csv"
    corr.to_csv(corr_path, index=False)

    # Compact core table: all requested clinical columns against the core burden metrics.
    core_corr = corr[corr["hazard_col"].isin(core_hazard_cols)].copy()
    core_corr_path = out_dir / "core_clinical_hazard_spearman.csv"
    core_corr.to_csv(core_corr_path, index=False)

    group_summary = build_group_summary(df, group_cols, core_hazard_cols, args.min_group_n)
    group_path = out_dir / "group_burden_summary_whitelist_long.csv"
    group_summary.to_csv(group_path, index=False)

    top_cases = build_top_cases(df, core_hazard_cols, args.top_n)
    top_path = out_dir / "top_cases_by_figure_metric.csv"
    top_cases.to_csv(top_path, index=False)

    manifest_rows = [
        {"artifact_type": "table", "path": str(corr_path), "description": "Whitelisted clinical variables correlated against hazard burden metrics."},
        {"artifact_type": "table", "path": str(core_corr_path), "description": "Compact correlation table for core p95/p99 burden metrics."},
        {"artifact_type": "table", "path": str(group_path), "description": "Boxplot-ready group summaries using whitelisted grouping variables."},
        {"artifact_type": "table", "path": str(top_path), "description": "Top cases by core hazard metric with clinical metadata."},
        {"artifact_type": "table", "path": str(out_dir / "requested_column_inventory.csv"), "description": "Inventory of requested and available columns."},
    ]

    if args.make_plots:
        scatter_dir = out_dir / "scatter_plots"
        box_dir = out_dir / "boxplots"
        scatter_dir.mkdir(parents=True, exist_ok=True)
        box_dir.mkdir(parents=True, exist_ok=True)

        # Plot only compact core correlations to avoid an unreadable number of plots.
        for _, row in core_corr.iterrows():
            x_col = row["clinical_col"]
            y_col = row["hazard_col"]
            rho = row["spearman_rho"]
            fname = f"scatter_{safe_filename(x_col)}__vs__{safe_filename(y_col)}.png"
            path = scatter_dir / fname
            make_scatter_plot(df, x_col, y_col, rho, path)
            manifest_rows.append(
                {"artifact_type": "figure", "path": str(path), "description": f"Scatter plot: {x_col} vs {y_col}."}
            )

        for g in group_cols:
            for h in core_hazard_cols:
                fname = f"boxplot_{safe_filename(h)}__by__{safe_filename(g)}.png"
                path = box_dir / fname
                ok = make_boxplot(df, g, h, args.min_group_n, path)
                if ok:
                    manifest_rows.append(
                        {"artifact_type": "figure", "path": str(path), "description": f"Boxplot: {h} by {g}."}
                    )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = out_dir / "figure_manifest.csv"
    manifest.to_csv(manifest_path, index=False)

    print(f"[OK] loaded linkage rows={len(df)} cols={df.shape[1]}")
    print(f"[OK] clinical columns used: {', '.join(clinical_cols)}")
    print(f"[OK] hazard columns used: {len(hazard_cols)}")
    print(f"[OK] core hazard columns used: {', '.join(core_hazard_cols)}")
    print(f"[OK] group columns used: {', '.join(group_cols) if group_cols else '(none)'}")
    print(f"[OK] wrote {corr_path} rows={len(corr)}")
    print(f"[OK] wrote {core_corr_path} rows={len(core_corr)}")
    print(f"[OK] wrote {group_path} rows={len(group_summary)}")
    print(f"[OK] wrote {top_path} rows={len(top_cases)}")
    print(f"[OK] wrote {manifest_path} rows={len(manifest)}")


if __name__ == "__main__":
    main()
