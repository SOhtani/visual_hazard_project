#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

METRICS = [
    "structural_visibility_loss_v1",
    "center_low_structure_area_v1",
    "reblur_response_loss_v1",
    "veil_low_contrast_score_v1",
    "whiteout_ratio_v1",
    "specular_like_ratio_v1",
]
CASE_STATS = ["median", "p90", "p95", "p99", "frac_ge_ref_p95", "frac_ge_ref_p99"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--reference-dir", required=True, type=Path)
    p.add_argument("--neo-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--neo-inventory", type=Path, default=None)
    return p.parse_args()


def case_files(root):
    return [p for p in sorted(root.glob("*_frame_scores.csv"))
            if p.name != "_frame_score_summary.csv"]


def cid(path):
    return path.stem.replace("_frame_scores", "")


def read_case(path):
    header = pd.read_csv(path, nrows=0)
    cols = [c for c in ["metric_status"] + METRICS if c in header.columns]
    d = pd.read_csv(path, usecols=cols)
    if "metric_status" in d.columns:
        d = d.loc[d["metric_status"].astype(str).eq("ok")].copy()
    for m in METRICS:
        if m not in d:
            d[m] = np.nan
        d[m] = pd.to_numeric(d[m], errors="coerce")
    return d[METRICS]


def percentile(ref, value):
    ref = np.asarray(ref, dtype=float)
    ref = ref[np.isfinite(ref)]
    if len(ref) == 0 or not np.isfinite(value):
        return np.nan
    return 100.0 * (np.sum(ref < value) + 0.5 * np.sum(ref == value)) / len(ref)


def ecdf(x):
    x = np.sort(np.asarray(x, dtype=float))
    x = x[np.isfinite(x)]
    return x, np.arange(1, len(x) + 1) / len(x) if len(x) else x


def summarize_case(case_id, cohort, d, thresholds, meta=None):
    meta = meta or {}
    rows = []
    for m in METRICS:
        x = d[m].dropna().to_numpy(dtype=float)
        p95 = thresholds[m]["p95"]
        p99 = thresholds[m]["p99"]
        rows.append({
            "cohort": cohort,
            "case_id": case_id,
            "resolution_group": meta.get("resolution_group"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "metric": m,
            "n_frames": len(x),
            "median": np.nanmedian(x) if len(x) else np.nan,
            "p90": np.nanpercentile(x, 90) if len(x) else np.nan,
            "p95": np.nanpercentile(x, 95) if len(x) else np.nan,
            "p99": np.nanpercentile(x, 99) if len(x) else np.nan,
            "frac_ge_ref_p95": np.mean(x >= p95) if len(x) else np.nan,
            "frac_ge_ref_p99": np.mean(x >= p99) if len(x) else np.nan,
        })
    return rows


def main():
    a = parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    ref_files = case_files(a.reference_dir)
    neo_files = case_files(a.neo_dir)
    if not ref_files or not neo_files:
        raise RuntimeError(f"ref={len(ref_files)} neo={len(neo_files)} case CSVs")

    inv_map = {}
    if a.neo_inventory and a.neo_inventory.exists():
        inv = pd.read_csv(a.neo_inventory)
        for _, r in inv.iterrows():
            w, h = int(float(r["width"])), int(float(r["height"]))
            inv_map[str(r["case_id"])] = {
                "width": w, "height": h,
                "resolution_group": "HD" if (w >= 1280 or h >= 720) else "SD",
            }

    pooled = {m: [] for m in METRICS}
    ref_cache = {}
    for i, p in enumerate(ref_files, 1):
        d = read_case(p)
        ref_cache[cid(p)] = d
        for m in METRICS:
            x = d[m].dropna().to_numpy(dtype=float)
            if len(x):
                pooled[m].append(x)
        print(f"[reference] {i}/{len(ref_files)} {p.name}")

    pooled = {m: np.concatenate(v) if v else np.array([]) for m, v in pooled.items()}
    thr_rows, thresholds = [], {}
    for m, x in pooled.items():
        thresholds[m] = {
            "p95": float(np.nanpercentile(x, 95)),
            "p99": float(np.nanpercentile(x, 99)),
        }
        thr_rows.append({
            "metric": m,
            "n_reference_frames": len(x),
            "ref_frame_median": float(np.nanmedian(x)),
            "ref_frame_p90": float(np.nanpercentile(x, 90)),
            "ref_frame_p95": thresholds[m]["p95"],
            "ref_frame_p99": thresholds[m]["p99"],
        })
    thr_df = pd.DataFrame(thr_rows)
    thr_df.to_csv(a.output_dir / "reference_frame_thresholds.csv",
                  index=False, encoding="utf-8-sig")

    rows = []
    for case_id, d in ref_cache.items():
        rows += summarize_case(case_id, "reference", d, thresholds)

    neo_cache = {}
    for i, p in enumerate(neo_files, 1):
        case_id = cid(p)
        d = read_case(p)
        neo_cache[case_id] = d
        rows += summarize_case(case_id, "neo", d, thresholds, inv_map.get(case_id))
        print(f"[neo] {i}/{len(neo_files)} {case_id}")

    case_df = pd.DataFrame(rows)
    case_df.to_csv(a.output_dir / "case_level_metric_summary_long.csv",
                   index=False, encoding="utf-8-sig")

    desc = []
    pct_rows = []
    for m in METRICS:
        for stat in CASE_STATS:
            ref = case_df.loc[
                (case_df.cohort == "reference") & (case_df.metric == m), stat
            ].dropna()
            neo = case_df.loc[
                (case_df.cohort == "neo") & (case_df.metric == m),
                ["case_id", "resolution_group", stat]
            ].dropna()
            desc.append({
                "metric": m, "case_stat": stat,
                "n_reference_cases": len(ref),
                "reference_median": ref.median(),
                "reference_q25": ref.quantile(0.25),
                "reference_q75": ref.quantile(0.75),
                "n_neo_cases": len(neo),
                "neo_median": neo[stat].median() if len(neo) else np.nan,
                "neo_min": neo[stat].min() if len(neo) else np.nan,
                "neo_max": neo[stat].max() if len(neo) else np.nan,
            })
            for _, r in neo.iterrows():
                pct_rows.append({
                    "case_id": r["case_id"],
                    "resolution_group": r["resolution_group"],
                    "metric": m,
                    "case_stat": stat,
                    "neo_value": r[stat],
                    "reference_case_percentile": percentile(ref.to_numpy(), r[stat]),
                })

    pd.DataFrame(desc).to_csv(
        a.output_dir / "neo_vs_reference_case_descriptives.csv",
        index=False, encoding="utf-8-sig")
    pct = pd.DataFrame(pct_rows)
    pct.to_csv(a.output_dir / "neo_case_reference_percentiles_long.csv",
               index=False, encoding="utf-8-sig")

    focus = pct[pct.case_stat.isin(["median", "p90", "p95", "p99"])].copy()
    wide = focus.pivot_table(
        index=["case_id", "resolution_group"],
        columns=["metric", "case_stat"],
        values=["neo_value", "reference_case_percentile"],
        aggfunc="first",
    )
    wide.columns = ["__".join(map(str, c)) for c in wide.columns]
    wide.reset_index().to_csv(
        a.output_dir / "neo_case_reference_percentiles_wide.csv",
        index=False, encoding="utf-8-sig")

    fig_case = a.output_dir / "figures_case_level"
    fig_ecdf = a.output_dir / "figures_frame_ecdf"
    fig_case.mkdir(exist_ok=True)
    fig_ecdf.mkdir(exist_ok=True)

    rng = np.random.default_rng(20260920)
    for m in METRICS:
        g = case_df[case_df.metric == m]
        for stat in ["median", "p90", "p95", "p99"]:
            ref = g.loc[g.cohort == "reference", stat].dropna().to_numpy(float)
            neo = g.loc[g.cohort == "neo", ["case_id", "resolution_group", stat]].dropna()

            fig, ax = plt.subplots(figsize=(7.5, 5.0))
            if len(ref):
                ax.scatter(rng.normal(0, 0.035, len(ref)), ref, s=22, alpha=0.6,
                           label="Reference 2023 cases")
                q25, med, q75 = np.percentile(ref, [25, 50, 75])
                ax.plot([-0.18, 0.18], [med, med], linewidth=2)
                ax.plot([0, 0], [q25, q75], linewidth=4, alpha=0.8)
            if len(neo):
                ax.scatter(np.ones(len(neo)), neo[stat].to_numpy(float), s=55,
                           label="Neo cases")
                for _, r in neo.iterrows():
                    ax.annotate(
                        f"{str(r['case_id'])[:8]} {r['resolution_group']}",
                        (1, float(r[stat])), xytext=(7, 0),
                        textcoords="offset points", fontsize=8, va="center")
            ax.set_xticks([0, 1], ["Reference 2023", "Neo 2024-2026"])
            ax.set_ylabel(stat)
            ax.set_title(m)
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="best")
            fig.tight_layout()
            fig.savefig(fig_case / f"{m}__{stat}.png", dpi=180)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5.2))
        x, y = ecdf(pooled[m])
        ax.plot(x, y, linewidth=2, label="Reference pooled frames")
        for case_id, d in neo_cache.items():
            x, y = ecdf(d[m].to_numpy(float))
            grp = inv_map.get(case_id, {}).get("resolution_group", "")
            ax.plot(x, y, linewidth=1.2, alpha=0.8,
                    label=f"{case_id[:8]} {grp}")
        ax.set_xlabel(m)
        ax.set_ylabel("ECDF")
        ax.set_title(f"Frame-level descriptive ECDF: {m}")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7, loc="best")
        fig.tight_layout()
        fig.savefig(fig_ecdf / f"{m}__ecdf.png", dpi=180)
        plt.close(fig)

    pd.DataFrame([{
        "n_reference_case_csvs": len(ref_files),
        "n_neo_case_csvs": len(neo_files),
        "n_neo_valid_rows_total": int(sum(len(d) for d in neo_cache.values())),
        "note": ("Descriptive distribution-shift analysis only; frame-level data are "
                 "not independent clinical observations. Neo and reference cohorts "
                 "differ in calendar period and acquisition resolution.")
    }]).to_csv(a.output_dir / "analysis_qc.csv",
                index=False, encoding="utf-8-sig")

    print()
    print("=== Reference frame thresholds ===")
    print(thr_df.to_string(index=False))
    print()
    print("=== Neo case percentiles: structural_visibility_loss_v1 ===")
    show = pct[
        (pct.metric == "structural_visibility_loss_v1") &
        pct.case_stat.isin(["median", "p90", "p95", "p99"])
    ].sort_values(["case_id", "case_stat"])
    print(show.to_string(index=False))
    print()
    print("Saved:", a.output_dir)


if __name__ == "__main__":
    main()
