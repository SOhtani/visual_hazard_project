#!/usr/bin/env python
from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt


METRICS = [
    ("structural_p90", "primary"),
    ("persistent_degradation_fraction", "secondary"),
]


def parse_args():
    p = argparse.ArgumentParser(
        description="Formal within-case test of phase dependence for locked video measurements."
    )
    p.add_argument("--case-phase-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--min-phase-cases", type=int, default=20)
    return p.parse_args()


def holm_adjust(pvals):
    p = np.asarray(pvals, dtype=float)
    out = np.full(len(p), np.nan)
    mask = np.isfinite(p)
    if not mask.any():
        return out

    pv = p[mask]
    order = np.argsort(pv)
    ranked = pv[order]
    m = len(ranked)

    adj_ranked = np.maximum.accumulate(
        np.minimum(1.0, ranked * (m - np.arange(m)))
    )

    tmp = np.empty(m, dtype=float)
    tmp[order] = adj_ranked
    out[np.where(mask)[0]] = tmp
    return out


def rank_biserial_paired(diff):
    d = np.asarray(diff, dtype=float)
    d = d[np.isfinite(d)]
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    pos = ranks[d > 0].sum()
    neg = ranks[d < 0].sum()
    denom = pos + neg
    return float((pos - neg) / denom) if denom else 0.0


def phase_order_from_counts(df, label_col, min_cases):
    counts = (
        df.groupby(label_col)["case_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    eligible = counts[counts >= min_cases].index.tolist()

    # Preserve the clinically meaningful Level-1 sequence when these labels exist.
    preferred = [
        "PortDockExplore",
        "SpecimenPathway",
        "LeakHemostasis",
        "DrainClosure",
        "PortPreparation",
        "SpecimenRetrieval",
    ]
    ordered = [x for x in preferred if x in eligible]
    ordered += [x for x in eligible if x not in ordered]
    return ordered, counts


def make_boxplot(long_df, metric, phases, out_path):
    arrays = []
    labels = []
    for phase in phases:
        x = pd.to_numeric(
            long_df.loc[
                long_df["workflow_level1_label"] == phase, metric
            ],
            errors="coerce",
        ).dropna()
        if len(x):
            arrays.append(x.to_numpy())
            labels.append(phase)

    if not arrays:
        return

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.boxplot(arrays, tick_labels=labels, showfliers=False)

    # Add raw case-level observations using deterministic horizontal jitter.
    rng = np.random.default_rng(20260919)
    for i, x in enumerate(arrays, start=1):
        jitter = rng.normal(0, 0.04, size=len(x))
        ax.scatter(np.full(len(x), i) + jitter, x, s=14, alpha=0.45)

    ax.set_ylabel(metric)
    ax.set_xlabel("Workflow level 1")
    ax.set_title(f"{metric} by surgical phase")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = args.output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.case_phase_csv, low_memory=False)
    required = {"case_id", "workflow_level1_label"} | {m for m, _ in METRICS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["case_id"] = df["case_id"].astype("string").str.strip().str.upper()
    phases, phase_counts = phase_order_from_counts(
        df, "workflow_level1_label", args.min_phase_cases
    )

    if len(phases) < 2:
        raise ValueError("Fewer than two eligible phases.")

    omnibus_rows = []
    pairwise_rows = []
    completeness_rows = []

    for metric, role in METRICS:
        pivot = (
            df[df["workflow_level1_label"].isin(phases)]
            .pivot(index="case_id", columns="workflow_level1_label", values=metric)
            .reindex(columns=phases)
        )
        pivot = pivot.apply(pd.to_numeric, errors="coerce")

        complete = pivot.dropna()
        completeness_rows.append({
            "metric": metric,
            "metric_role": role,
            "eligible_phase_count": len(phases),
            "eligible_phases": ";".join(phases),
            "cases_with_any_eligible_phase": int(pivot.notna().any(axis=1).sum()),
            "complete_cases_all_eligible_phases": len(complete),
        })

        if len(complete) >= 3:
            vals = [complete[p].to_numpy(dtype=float) for p in phases]
            stat, pval = stats.friedmanchisquare(*vals)
        else:
            stat, pval = np.nan, np.nan

        omnibus_rows.append({
            "metric": metric,
            "metric_role": role,
            "test": "Friedman",
            "n_complete_cases": len(complete),
            "n_phases": len(phases),
            "phases": ";".join(phases),
            "statistic": stat,
            "p_value": pval,
        })

        metric_pair_rows = []
        for a, b in combinations(phases, 2):
            pair = pivot[[a, b]].dropna()
            n = len(pair)
            if n >= 3:
                diff = pair[b].to_numpy(dtype=float) - pair[a].to_numpy(dtype=float)
                if np.allclose(diff, 0):
                    wstat, wp = 0.0, 1.0
                else:
                    wstat, wp = stats.wilcoxon(
                        pair[b],
                        pair[a],
                        zero_method="wilcox",
                        alternative="two-sided",
                        method="auto",
                    )
                rbc = rank_biserial_paired(diff)
                med_diff = float(np.median(diff))
            else:
                wstat, wp, rbc, med_diff = np.nan, np.nan, np.nan, np.nan

            metric_pair_rows.append({
                "metric": metric,
                "metric_role": role,
                "phase_a": a,
                "phase_b": b,
                "difference_definition": "phase_b_minus_phase_a",
                "n_paired_cases": n,
                "median_paired_difference": med_diff,
                "rank_biserial_paired": rbc,
                "wilcoxon_statistic": wstat,
                "p_value": wp,
            })

        metric_pair_df = pd.DataFrame(metric_pair_rows)
        metric_pair_df["holm_p_within_metric"] = holm_adjust(
            metric_pair_df["p_value"].to_numpy()
        )
        pairwise_rows.extend(metric_pair_df.to_dict("records"))

        make_boxplot(
            df,
            metric,
            phases,
            fig_dir / f"{metric}_by_phase.png",
        )

    omnibus = pd.DataFrame(omnibus_rows)
    pairwise = pd.DataFrame(pairwise_rows)
    completeness = pd.DataFrame(completeness_rows)

    omnibus.to_csv(
        args.output_dir / "phase_within_case_friedman_tests.csv",
        index=False,
    )
    pairwise.to_csv(
        args.output_dir / "phase_pairwise_wilcoxon_holm.csv",
        index=False,
    )
    completeness.to_csv(
        args.output_dir / "phase_test_completeness.csv",
        index=False,
    )

    phase_counts.rename("n_cases").reset_index().to_csv(
        args.output_dir / "phase_case_counts.csv",
        index=False,
    )

    print("Eligible phases:")
    for p in phases:
        print(f"  {p}: {int(phase_counts[p])} cases")

    print()
    print("Completeness:")
    print(completeness.to_string(index=False))

    print()
    print("Friedman omnibus tests:")
    print(omnibus.to_string(index=False))

    print()
    print("Pairwise Wilcoxon tests with Holm correction:")
    show = [
        "metric",
        "phase_a",
        "phase_b",
        "n_paired_cases",
        "median_paired_difference",
        "rank_biserial_paired",
        "p_value",
        "holm_p_within_metric",
    ]
    print(pairwise[show].to_string(index=False))

    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
