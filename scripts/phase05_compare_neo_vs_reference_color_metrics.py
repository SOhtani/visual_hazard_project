#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


COLOR_METRICS = [
    "red_dominance_ratio_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "blood_like_redness_ratio_v1",
    "center_weighted_blood_like_redness_v1",
    "red_excess_mean_v1",
    "red_saturation_mean_v1",
]

CASE_STATS = ["median", "p90", "p95", "p99"]


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Descriptive case-level comparison of existing color-field metrics "
            "between the 2023 reference cohort and neo videos."
        )
    )
    p.add_argument("--reference-csv", required=True, type=Path)
    p.add_argument("--neo-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--neo-inventory", type=Path, default=None)
    return p.parse_args()


def empirical_percentile(ref, value):
    x = np.asarray(ref, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0 or not np.isfinite(value):
        return np.nan
    return 100.0 * (np.sum(x < value) + 0.5 * np.sum(x == value)) / len(x)


def require_columns(df, metrics, label):
    missing = [m for m in metrics if m not in df.columns]
    if missing:
        raise ValueError(f"{label} missing metrics: {missing}")
    if "case_id" not in df.columns:
        raise ValueError(f"{label} missing case_id")


def summarize_by_case(df, cohort, inventory=None):
    inventory = inventory or {}
    rows = []
    for case_id, g in df.groupby("case_id", sort=True):
        meta = inventory.get(str(case_id), {})
        for m in COLOR_METRICS:
            x = pd.to_numeric(g[m], errors="coerce").dropna().to_numpy(dtype=float)
            rows.append({
                "cohort": cohort,
                "case_id": str(case_id),
                "resolution_group": meta.get("resolution_group"),
                "width": meta.get("width"),
                "height": meta.get("height"),
                "metric": m,
                "n_frames": len(x),
                "median": np.nanmedian(x) if len(x) else np.nan,
                "p90": np.nanpercentile(x, 90) if len(x) else np.nan,
                "p95": np.nanpercentile(x, 95) if len(x) else np.nan,
                "p99": np.nanpercentile(x, 99) if len(x) else np.nan,
            })
    return pd.DataFrame(rows)


def main():
    a = parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)

    ref = pd.read_csv(a.reference_csv)
    neo = pd.read_csv(a.neo_csv)

    require_columns(ref, COLOR_METRICS, "reference")
    require_columns(neo, COLOR_METRICS, "neo")

    inv_map = {}
    if a.neo_inventory is not None and a.neo_inventory.exists():
        inv = pd.read_csv(a.neo_inventory)
        for _, r in inv.iterrows():
            w = int(float(r["width"]))
            h = int(float(r["height"]))
            inv_map[str(r["case_id"])] = {
                "width": w,
                "height": h,
                "resolution_group": "HD" if (w >= 1280 or h >= 720) else "SD",
            }

    ref_case = summarize_by_case(ref, "reference")
    neo_case = summarize_by_case(neo, "neo", inv_map)
    case = pd.concat([ref_case, neo_case], ignore_index=True)
    case.to_csv(
        a.output_dir / "color_case_level_summary_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pct_rows = []
    desc_rows = []
    for m in COLOR_METRICS:
        for stat in CASE_STATS:
            r = case.loc[
                (case["cohort"] == "reference") & (case["metric"] == m), stat
            ].dropna().to_numpy(dtype=float)
            n = case.loc[
                (case["cohort"] == "neo") & (case["metric"] == m),
                ["case_id", "resolution_group", stat],
            ].dropna()

            desc_rows.append({
                "metric": m,
                "case_stat": stat,
                "n_reference_cases": len(r),
                "reference_median": np.nanmedian(r) if len(r) else np.nan,
                "reference_q25": np.nanpercentile(r, 25) if len(r) else np.nan,
                "reference_q75": np.nanpercentile(r, 75) if len(r) else np.nan,
                "n_neo_cases": len(n),
                "neo_median": np.nanmedian(n[stat]) if len(n) else np.nan,
                "neo_min": np.nanmin(n[stat]) if len(n) else np.nan,
                "neo_max": np.nanmax(n[stat]) if len(n) else np.nan,
            })

            for _, row in n.iterrows():
                pct_rows.append({
                    "case_id": row["case_id"],
                    "resolution_group": row["resolution_group"],
                    "metric": m,
                    "case_stat": stat,
                    "neo_value": row[stat],
                    "reference_case_percentile": empirical_percentile(r, row[stat]),
                })

    pd.DataFrame(desc_rows).to_csv(
        a.output_dir / "color_neo_vs_reference_descriptives.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pct = pd.DataFrame(pct_rows)
    pct.to_csv(
        a.output_dir / "color_neo_case_reference_percentiles_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    wide = pct.pivot_table(
        index=["case_id", "resolution_group"],
        columns=["metric", "case_stat"],
        values=["neo_value", "reference_case_percentile"],
        aggfunc="first",
    )
    wide.columns = ["__".join(map(str, c)) for c in wide.columns]
    wide.reset_index().to_csv(
        a.output_dir / "color_neo_case_reference_percentiles_wide.csv",
        index=False,
        encoding="utf-8-sig",
    )

    fig_dir = a.output_dir / "figures_case_level"
    fig_dir.mkdir(exist_ok=True)
    rng = np.random.default_rng(20260920)

    for m in COLOR_METRICS:
        g = case[case["metric"] == m]
        for stat in ["median", "p90", "p99"]:
            r = g.loc[g["cohort"] == "reference", stat].dropna().to_numpy(dtype=float)
            n = g.loc[
                g["cohort"] == "neo",
                ["case_id", "resolution_group", stat],
            ].dropna()

            fig, ax = plt.subplots(figsize=(7.5, 5.0))
            if len(r):
                ax.scatter(
                    rng.normal(0, 0.035, len(r)),
                    r,
                    s=22,
                    alpha=0.6,
                    label="Reference 2023 cases",
                )
                q25, med, q75 = np.percentile(r, [25, 50, 75])
                ax.plot([-0.18, 0.18], [med, med], linewidth=2)
                ax.plot([0, 0], [q25, q75], linewidth=4, alpha=0.8)

            if len(n):
                ax.scatter(
                    np.ones(len(n)),
                    n[stat].to_numpy(dtype=float),
                    s=55,
                    label="Neo cases",
                )
                for _, row in n.iterrows():
                    ax.annotate(
                        f"{str(row['case_id'])[:8]} {row['resolution_group']}",
                        (1, float(row[stat])),
                        xytext=(7, 0),
                        textcoords="offset points",
                        fontsize=8,
                        va="center",
                    )

            ax.set_xticks([0, 1], ["Reference 2023", "Neo 2024-2026"])
            ax.set_ylabel(stat)
            ax.set_title(m)
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="best")
            fig.tight_layout()
            fig.savefig(fig_dir / f"{m}__{stat}.png", dpi=180)
            plt.close(fig)

    qc = pd.DataFrame([{
        "reference_csv": str(a.reference_csv),
        "neo_csv": str(a.neo_csv),
        "reference_rows": len(ref),
        "neo_rows": len(neo),
        "reference_cases": ref["case_id"].nunique(),
        "neo_cases": neo["case_id"].nunique(),
        "note": (
            "Exploratory descriptive comparison only. Existing color metrics are "
            "not validated semantic detectors of blood, inflammation, fibrosis, "
            "adhesion, or treatment effect."
        ),
    }])
    qc.to_csv(a.output_dir / "color_analysis_qc.csv", index=False, encoding="utf-8-sig")

    print("=== QC ===")
    print(qc.to_string(index=False))
    print()
    print("=== Neo p90/p99 reference-case percentiles ===")
    show = pct[pct["case_stat"].isin(["p90", "p99"])].sort_values(
        ["metric", "case_stat", "case_id"]
    )
    print(show.to_string(index=False))
    print()
    print("Saved:", a.output_dir)


if __name__ == "__main__":
    main()
