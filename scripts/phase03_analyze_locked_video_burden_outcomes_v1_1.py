#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib.pyplot as plt

try:
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except Exception:
    STATSMODELS_AVAILABLE = False


PREDICTORS = [
    ("structural_p90", "primary"),
    ("structural_fraction_ge_global_p95", "secondary"),
    ("structural_fraction_ge_global_p99", "secondary"),
    ("persistent_degradation_fraction", "secondary"),
]

OUTCOMES = [
    ("operation_time_min", "operative_time"),
    ("blood_loss_g", "blood_loss"),
]

COVARIATES = ["procedure_group", "side"]


def parse_args():
    p = argparse.ArgumentParser(
        description="Locked 2023 case-level video burden vs clinical outcomes."
    )
    p.add_argument("--video-case-csv", required=True, type=Path)
    p.add_argument("--video-phase-csv", required=True, type=Path)
    p.add_argument("--video-workspace-csv", required=True, type=Path)
    p.add_argument("--clinical-metadata", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    return p.parse_args()


def numeric(s):
    return pd.to_numeric(s, errors="coerce")


def summarize_numeric(s: pd.Series):
    x = numeric(s).dropna()
    if x.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "sd": np.nan,
            "median": np.nan,
            "q25": np.nan,
            "q75": np.nan,
            "min": np.nan,
            "max": np.nan,
        }
    return {
        "n": len(x),
        "mean": float(x.mean()),
        "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
        "median": float(x.median()),
        "q25": float(x.quantile(0.25)),
        "q75": float(x.quantile(0.75)),
        "min": float(x.min()),
        "max": float(x.max()),
    }


def bh_fdr(pvalues):
    """Benjamini-Hochberg q-values; preserves NaNs."""
    p = np.asarray(pvalues, dtype=float)
    q = np.full_like(p, np.nan, dtype=float)
    mask = np.isfinite(p)
    if not mask.any():
        return q
    pv = p[mask]
    order = np.argsort(pv)
    ranked = pv[order]
    m = len(ranked)
    adj = ranked * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    tmp = np.empty(m, dtype=float)
    tmp[order] = adj
    q[mask] = tmp
    return q


def spearman_table(df):
    rows = []
    for pred, role in PREDICTORS:
        for outcome, outcome_name in OUTCOMES:
            sub = df[[pred, outcome]].copy()
            sub[pred] = numeric(sub[pred])
            sub[outcome] = numeric(sub[outcome])
            sub = sub.dropna()
            if len(sub) >= 3 and sub[pred].nunique() >= 2 and sub[outcome].nunique() >= 2:
                rho, pval = stats.spearmanr(sub[pred], sub[outcome])
            else:
                rho, pval = np.nan, np.nan
            rows.append({
                "predictor": pred,
                "predictor_role": role,
                "outcome": outcome,
                "outcome_label": outcome_name,
                "n": len(sub),
                "spearman_rho": rho,
                "p_value": pval,
            })
    out = pd.DataFrame(rows)
    out["bh_fdr_q_across_8_tests"] = bh_fdr(out["p_value"].to_numpy())
    return out


def regression_rows(df):
    rows = []
    if not STATSMODELS_AVAILABLE:
        return pd.DataFrame([{
            "status": "statsmodels_not_available",
        }])

    for pred, role in PREDICTORS:
        for outcome, outcome_name in OUTCOMES:
            needed = [pred, outcome] + COVARIATES
            sub = df[needed].copy()

            sub[pred] = numeric(sub[pred])
            sub[outcome] = numeric(sub[outcome])

            for c in COVARIATES:
                sub[c] = sub[c].replace({"": np.nan})

            sub = sub.dropna()

            if len(sub) < 10 or sub[pred].nunique() < 2:
                rows.append({
                    "predictor": pred,
                    "predictor_role": role,
                    "outcome": outcome,
                    "outcome_label": outcome_name,
                    "n": len(sub),
                    "status": "insufficient_data",
                })
                continue

            sd = sub[pred].std(ddof=1)
            if not np.isfinite(sd) or sd == 0:
                rows.append({
                    "predictor": pred,
                    "predictor_role": role,
                    "outcome": outcome,
                    "outcome_label": outcome_name,
                    "n": len(sub),
                    "status": "zero_predictor_sd",
                })
                continue

            sub["predictor_z"] = (sub[pred] - sub[pred].mean()) / sd

            if outcome == "blood_loss_g":
                if (sub[outcome] < 0).any():
                    rows.append({
                        "predictor": pred,
                        "predictor_role": role,
                        "outcome": outcome,
                        "outcome_label": outcome_name,
                        "n": len(sub),
                        "status": "negative_blood_loss_value",
                    })
                    continue
                sub["model_outcome"] = np.log1p(sub[outcome])
                outcome_scale = "log1p_blood_loss_g"
            else:
                sub["model_outcome"] = sub[outcome]
                outcome_scale = "minutes"

            # Separate model per video predictor.
            formula = (
                "model_outcome ~ predictor_z + C(procedure_group) + C(side)"
            )

            try:
                fit = smf.ols(formula, data=sub).fit(cov_type="HC3")
                beta = float(fit.params["predictor_z"])
                se = float(fit.bse["predictor_z"])
                pval = float(fit.pvalues["predictor_z"])
                ci = fit.conf_int().loc["predictor_z"]
                ci_low = float(ci.iloc[0])
                ci_high = float(ci.iloc[1])

                rows.append({
                    "predictor": pred,
                    "predictor_role": role,
                    "outcome": outcome,
                    "outcome_label": outcome_name,
                    "outcome_scale": outcome_scale,
                    "n": int(fit.nobs),
                    "predictor_sd_original_units": float(sd),
                    "beta_per_1SD_predictor": beta,
                    "robust_se_HC3": se,
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                    "p_value": pval,
                    "r_squared": float(fit.rsquared),
                    "adjusted_r_squared": float(fit.rsquared_adj),
                    "procedure_levels": ";".join(sorted(sub["procedure_group"].astype(str).unique())),
                    "side_levels": ";".join(sorted(sub["side"].astype(str).unique())),
                    "status": "ok",
                })
            except Exception as e:
                rows.append({
                    "predictor": pred,
                    "predictor_role": role,
                    "outcome": outcome,
                    "outcome_label": outcome_name,
                    "n": len(sub),
                    "status": f"model_error:{type(e).__name__}:{e}",
                })

    out = pd.DataFrame(rows)
    if "p_value" in out.columns:
        mask = out["status"].eq("ok") if "status" in out.columns else pd.Series(False, index=out.index)
        out["bh_fdr_q_across_adjusted_models"] = np.nan
        if mask.any():
            out.loc[mask, "bh_fdr_q_across_adjusted_models"] = bh_fdr(
                out.loc[mask, "p_value"].to_numpy()
            )
    return out


def quartile_summary(df, predictor="structural_p90"):
    sub = df[
        ["case_id", predictor, "operation_time_min", "blood_loss_g"]
    ].copy()
    sub[predictor] = numeric(sub[predictor])

    if sub[predictor].notna().sum() < 4:
        return pd.DataFrame()

    try:
        sub["quartile"] = pd.qcut(
            sub[predictor],
            q=4,
            labels=["Q1", "Q2", "Q3", "Q4"],
            duplicates="drop",
        )
    except Exception:
        return pd.DataFrame()

    rows = []
    for q, g in sub.groupby("quartile", observed=True):
        row = {
            "quartile": str(q),
            "n_cases": len(g),
            "predictor_median": numeric(g[predictor]).median(),
            "predictor_q25": numeric(g[predictor]).quantile(0.25),
            "predictor_q75": numeric(g[predictor]).quantile(0.75),
        }
        for outcome, _ in OUTCOMES:
            s = summarize_numeric(g[outcome])
            row[f"{outcome}_n"] = s["n"]
            row[f"{outcome}_median"] = s["median"]
            row[f"{outcome}_q25"] = s["q25"]
            row[f"{outcome}_q75"] = s["q75"]
        rows.append(row)
    return pd.DataFrame(rows)


def context_summary(df: pd.DataFrame, label_col: str):
    metrics = [
        "structural_p90",
        "structural_fraction_ge_global_p95",
        "structural_fraction_ge_global_p99",
        "persistent_degradation_fraction",
    ]
    rows = []
    if label_col not in df.columns:
        return pd.DataFrame()

    for label, g in df.groupby(label_col, dropna=True, sort=False):
        row = {
            label_col: label,
            "n_case_context_rows": len(g),
            "n_cases": g["case_id"].nunique(),
            "total_frames_across_case_context_rows": int(
                numeric(g["n_frames"]).fillna(0).sum()
            ) if "n_frames" in g.columns else np.nan,
        }
        for metric in metrics:
            if metric in g.columns:
                s = summarize_numeric(g[metric])
                row[f"{metric}_median_across_cases"] = s["median"]
                row[f"{metric}_q25_across_cases"] = s["q25"]
                row[f"{metric}_q75_across_cases"] = s["q75"]
        rows.append(row)

    return pd.DataFrame(rows)


def scatter_plot(df, predictor, outcome, out_path, title):
    sub = df[[predictor, outcome]].copy()
    sub[predictor] = numeric(sub[predictor])
    sub[outcome] = numeric(sub[outcome])
    sub = sub.dropna()

    if len(sub) < 3:
        return

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.scatter(sub[predictor], sub[outcome])

    x = sub[predictor].to_numpy(dtype=float)
    y = sub[outcome].to_numpy(dtype=float)
    if np.unique(x).size >= 2:
        coef = np.polyfit(x, y, 1)
        xx = np.linspace(np.nanmin(x), np.nanmax(x), 100)
        yy = coef[0] * xx + coef[1]
        ax.plot(xx, yy)

    rho, p = stats.spearmanr(x, y)
    ax.set_xlabel(predictor)
    ax.set_ylabel(outcome)
    ax.set_title(title)
    ax.text(
        0.02,
        0.98,
        f"n={len(sub)}\nSpearman rho={rho:.3f}\np={p:.3g}",
        transform=ax.transAxes,
        va="top",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = args.output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    video = pd.read_csv(args.video_case_csv, low_memory=False)
    clinical = pd.read_csv(args.clinical_metadata, low_memory=False)
    phase = pd.read_csv(args.video_phase_csv, low_memory=False)
    workspace = pd.read_csv(args.video_workspace_csv, low_memory=False)

    # Normalize case IDs without converting missing values to the literal string "NAN".
    for d in (video, clinical, phase, workspace):
        if "case_id" in d.columns:
            d["case_id"] = d["case_id"].astype("string").str.strip().str.upper()

    # The locked video table defines the analysis cohort. Clinical rows with missing
    # case_id cannot be merged and are retained only in QC counts.
    clinical_missing_case_id_rows = int(
        clinical["case_id"].isna().sum()
        | clinical["case_id"].fillna("").eq("").sum()
    )
    clinical_for_merge = clinical[
        clinical["case_id"].notna() & clinical["case_id"].ne("")
    ].copy()

    # Canonical one-to-one merge on case_id.
    if video["case_id"].isna().any() or video["case_id"].eq("").any():
        raise ValueError("Missing case_id in locked video case-level table.")
    if video["case_id"].duplicated().any():
        raise ValueError("Duplicate case_id in video case-level table.")
    if clinical_for_merge["case_id"].duplicated().any():
        dup = clinical_for_merge.loc[
            clinical_for_merge["case_id"].duplicated(keep=False), "case_id"
        ].tolist()
        raise ValueError(f"Duplicate case_id in clinical metadata: {dup}")

    video_cases = set(video["case_id"])
    clinical_cases = set(clinical_for_merge["case_id"])
    unmatched_video = sorted(video_cases - clinical_cases)
    extra_clinical = sorted(clinical_cases - video_cases)

    analysis = video.merge(
        clinical_for_merge,
        on="case_id",
        how="left",
        validate="one_to_one",
        indicator="_clinical_merge",
        suffixes=("", "_clinical"),
    )

    # Canonical clinical variables.
    for c in ["operation_time_min", "blood_loss_g", "age"]:
        if c in analysis.columns:
            analysis[c] = numeric(analysis[c])

    # Clean categorical covariates.
    for c in ["procedure_group", "side"]:
        if c in analysis.columns:
            analysis[c] = analysis[c].replace({"": np.nan})

    required = [
        "operation_time_min",
        "blood_loss_g",
        "procedure_group",
        "side",
    ] + [p for p, _ in PREDICTORS]
    missing_required = [c for c in required if c not in analysis.columns]
    if missing_required:
        raise ValueError(f"Required columns missing after merge: {missing_required}")

    # QC.
    qc = pd.DataFrame([{
        "video_rows": len(video),
        "video_cases": video["case_id"].nunique(),
        "clinical_rows": len(clinical),
        "clinical_rows_with_missing_case_id": clinical_missing_case_id_rows,
        "clinical_unique_cases_nonmissing": clinical_for_merge["case_id"].nunique(),
        "matched_video_cases": int((analysis["_clinical_merge"] == "both").sum()),
        "unmatched_video_cases": len(unmatched_video),
        "extra_clinical_cases_not_in_video": len(extra_clinical),
        "operation_time_nonmissing": int(analysis["operation_time_min"].notna().sum()),
        "blood_loss_nonmissing": int(analysis["blood_loss_g"].notna().sum()),
        "procedure_group_nonmissing": int(analysis["procedure_group"].notna().sum()),
        "side_nonmissing": int(analysis["side"].notna().sum()),
        "complete_cases_for_adjusted_operation_time": int(
            analysis[
                ["operation_time_min", "procedure_group", "side"]
                + [PREDICTORS[0][0]]
            ].notna().all(axis=1).sum()
        ),
        "complete_cases_for_adjusted_blood_loss": int(
            analysis[
                ["blood_loss_g", "procedure_group", "side"]
                + [PREDICTORS[0][0]]
            ].notna().all(axis=1).sum()
        ),
        "statsmodels_available": STATSMODELS_AVAILABLE,
    }])
    qc.to_csv(args.output_dir / "clinical_outcome_analysis_qc.csv", index=False)

    if unmatched_video:
        pd.DataFrame({"case_id": unmatched_video}).to_csv(
            args.output_dir / "unmatched_video_cases.csv", index=False
        )
    if extra_clinical:
        pd.DataFrame({"case_id": extra_clinical}).to_csv(
            args.output_dir / "extra_clinical_cases_not_in_video.csv", index=False
        )

    # Freeze merged analysis table.
    analysis.to_csv(
        args.output_dir / "locked_case_clinical_analysis_table_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Descriptive tables.
    descriptives = []
    desc_vars = [p for p, _ in PREDICTORS] + [
        "operation_time_min",
        "blood_loss_g",
        "age",
    ]
    for c in desc_vars:
        if c in analysis.columns:
            row = {"variable": c}
            row.update(summarize_numeric(analysis[c]))
            descriptives.append(row)
    pd.DataFrame(descriptives).to_csv(
        args.output_dir / "descriptive_numeric_summary.csv", index=False
    )

    categorical_rows = []
    for c in ["procedure_group", "side", "sex"]:
        if c in analysis.columns:
            vc = analysis[c].value_counts(dropna=False)
            for level, n in vc.items():
                categorical_rows.append({
                    "variable": c,
                    "level": level,
                    "n": int(n),
                    "proportion": n / len(analysis),
                })
    pd.DataFrame(categorical_rows).to_csv(
        args.output_dir / "descriptive_categorical_summary.csv", index=False
    )

    # Spearman.
    sp = spearman_table(analysis)
    sp.to_csv(
        args.output_dir / "video_predictor_outcome_spearman.csv",
        index=False,
    )

    # Adjusted models.
    reg = regression_rows(analysis)
    reg.to_csv(
        args.output_dir / "video_predictor_outcome_adjusted_models.csv",
        index=False,
    )

    # Quartile summary for locked primary predictor.
    quart = quartile_summary(analysis, "structural_p90")
    quart.to_csv(
        args.output_dir / "structural_p90_quartile_outcome_summary.csv",
        index=False,
    )

    # Phase/workspace descriptive summaries.
    phase_summary = context_summary(phase, "workflow_level1_label")
    phase_summary.to_csv(
        args.output_dir / "phase_video_burden_descriptive_summary.csv",
        index=False,
    )

    workspace_summary = context_summary(workspace, "workflow_level2_label")
    workspace_summary.to_csv(
        args.output_dir / "workspace_video_burden_descriptive_summary.csv",
        index=False,
    )

    # Simple presentation-ready scatters.
    scatter_plot(
        analysis,
        "structural_p90",
        "operation_time_min",
        fig_dir / "structural_p90_vs_operation_time.png",
        "Structural visibility burden vs operative time",
    )
    scatter_plot(
        analysis,
        "structural_p90",
        "blood_loss_g",
        fig_dir / "structural_p90_vs_blood_loss.png",
        "Structural visibility burden vs blood loss",
    )
    scatter_plot(
        analysis,
        "persistent_degradation_fraction",
        "operation_time_min",
        fig_dir / "persistent_degradation_vs_operation_time.png",
        "Persistent degradation proxy vs operative time",
    )
    scatter_plot(
        analysis,
        "persistent_degradation_fraction",
        "blood_loss_g",
        fig_dir / "persistent_degradation_vs_blood_loss.png",
        "Persistent degradation proxy vs blood loss",
    )

    # Console.
    print("QC summary:")
    print(qc.to_string(index=False))
    print()
    print("Procedure distribution:")
    print(analysis["procedure_group"].value_counts(dropna=False).to_string())
    print()
    print("Side distribution:")
    print(analysis["side"].value_counts(dropna=False).to_string())
    print()
    print("Spearman results:")
    print(
        sp[
            [
                "predictor",
                "predictor_role",
                "outcome",
                "n",
                "spearman_rho",
                "p_value",
                "bh_fdr_q_across_8_tests",
            ]
        ].to_string(index=False)
    )
    print()
    print("Adjusted models:")
    if "status" in reg.columns:
        cols = [
            c for c in [
                "predictor",
                "predictor_role",
                "outcome",
                "n",
                "beta_per_1SD_predictor",
                "ci95_low",
                "ci95_high",
                "p_value",
                "bh_fdr_q_across_adjusted_models",
                "status",
            ] if c in reg.columns
        ]
        print(reg[cols].to_string(index=False))
    else:
        print(reg.to_string(index=False))
    print()
    print("Phase descriptive summary:")
    print(phase_summary.to_string(index=False))
    print()
    print("Workspace descriptive summary:")
    print(workspace_summary.to_string(index=False))
    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
