#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except Exception:
    STATSMODELS_AVAILABLE = False


CONTEXT_PREDICTORS = [
    ("structural_p90", "primary"),
    ("persistent_degradation_fraction", "secondary"),
]

OUTCOMES = [
    ("operation_time_min", "operative_time"),
    ("blood_loss_g", "blood_loss"),
]

COVARIATES = ["procedure_group", "side"]


def parse_args():
    p = argparse.ArgumentParser(
        description="Rebuild full 519,198-frame workflow context and run phase/workspace outcome analyses."
    )
    p.add_argument("--locked-frame-csv", required=True, type=Path)
    p.add_argument("--full-workflow-csv", required=True, type=Path)
    p.add_argument("--locked-thresholds-csv", required=True, type=Path)
    p.add_argument("--clinical-analysis-table", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--min-context-cases", type=int, default=20)
    p.add_argument("--time-round-decimals", type=int, default=3)
    return p.parse_args()


def num(s):
    return pd.to_numeric(s, errors="coerce")


def as_bool(s):
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna("").astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes", "y", "t"}
    )


def make_key(df, decimals):
    case = df["case_id"].astype("string").str.strip().str.upper()
    t = num(df["sample_time_sec"]).round(decimals)
    ttxt = t.map(lambda x: f"{x:.{decimals}f}" if pd.notna(x) else "NA")
    return case + "|" + ttxt


def bh_fdr(pvalues):
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


def load_locked_thresholds(path):
    t = pd.read_csv(path, low_memory=False)
    need = {"metric", "quantile", "value"}
    missing = need - set(t.columns)
    if missing:
        raise ValueError(f"Threshold file missing columns: {sorted(missing)}")
    s = t[t["metric"].astype(str) == "structural_visibility_loss_v1"].copy()
    lookup = dict(zip(s["quantile"].astype(str), num(s["value"])))
    if "p95" not in lookup or "p99" not in lookup:
        raise ValueError("Locked p95/p99 structural thresholds not found.")
    return float(lookup["p95"]), float(lookup["p99"])


def aggregate_case_context(df, label_col, p95, p99):
    rows = []
    x = df[df[label_col].notna()].copy()
    for (case_id, label), g in x.groupby(["case_id", label_col], sort=True):
        s = num(g["structural_visibility_loss_v1"])
        proxy = as_bool(g["persistent_degradation_proxy_v1"])
        rows.append({
            "case_id": case_id,
            label_col: label,
            "n_frames": len(g),
            "structural_median": float(s.median()),
            "structural_p90": float(s.quantile(0.90)),
            "structural_fraction_ge_global_p95": float((s >= p95).mean()),
            "structural_fraction_ge_global_p99": float((s >= p99).mean()),
            "persistent_degradation_frames": int(proxy.sum()),
            "persistent_degradation_fraction": float(proxy.mean()),
        })
    return pd.DataFrame(rows)


def descriptive_context_summary(context_df, label_col):
    rows = []
    metrics = [
        "structural_p90",
        "structural_fraction_ge_global_p95",
        "structural_fraction_ge_global_p99",
        "persistent_degradation_fraction",
    ]
    for label, g in context_df.groupby(label_col, sort=False):
        row = {
            label_col: label,
            "n_case_context_rows": len(g),
            "n_cases": g["case_id"].nunique(),
            "total_frames": int(num(g["n_frames"]).fillna(0).sum()),
            "median_frames_per_case": float(num(g["n_frames"]).median()),
        }
        for metric in metrics:
            s = num(g[metric]).dropna()
            row[f"{metric}_median"] = float(s.median()) if len(s) else np.nan
            row[f"{metric}_q25"] = float(s.quantile(0.25)) if len(s) else np.nan
            row[f"{metric}_q75"] = float(s.quantile(0.75)) if len(s) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def spearman_context(context_df, clinical, label_col, min_cases):
    merged = context_df.merge(
        clinical[
            ["case_id", "operation_time_min", "blood_loss_g", "procedure_group", "side"]
        ],
        on="case_id",
        how="left",
        validate="many_to_one",
    )

    eligible = (
        context_df.groupby(label_col)["case_id"]
        .nunique()
        .loc[lambda s: s >= min_cases]
        .index.tolist()
    )

    rows = []
    for label in eligible:
        g0 = merged[merged[label_col] == label]
        for predictor, role in CONTEXT_PREDICTORS:
            for outcome, outcome_label in OUTCOMES:
                g = g0[[predictor, outcome]].copy()
                g[predictor] = num(g[predictor])
                g[outcome] = num(g[outcome])
                g = g.dropna()
                if len(g) >= 3 and g[predictor].nunique() >= 2 and g[outcome].nunique() >= 2:
                    rho, p = stats.spearmanr(g[predictor], g[outcome])
                else:
                    rho, p = np.nan, np.nan
                rows.append({
                    "context_type": label_col,
                    "context_label": label,
                    "predictor": predictor,
                    "predictor_role": role,
                    "outcome": outcome,
                    "outcome_label": outcome_label,
                    "n": len(g),
                    "spearman_rho": rho,
                    "p_value": p,
                })

    out = pd.DataFrame(rows)
    if len(out):
        out["bh_fdr_q_within_context_family"] = bh_fdr(out["p_value"].to_numpy())
    return out, eligible, merged


def adjusted_context_models(context_merged, eligible, label_col):
    if not STATSMODELS_AVAILABLE:
        return pd.DataFrame([{"status": "statsmodels_not_available"}])

    rows = []
    for label in eligible:
        g0 = context_merged[context_merged[label_col] == label].copy()
        for predictor, role in CONTEXT_PREDICTORS:
            for outcome, outcome_label in OUTCOMES:
                cols = [predictor, outcome] + COVARIATES
                g = g0[cols].copy()
                g[predictor] = num(g[predictor])
                g[outcome] = num(g[outcome])
                for c in COVARIATES:
                    g[c] = g[c].replace({"": np.nan})
                g = g.dropna()

                if len(g) < 10 or g[predictor].nunique() < 2:
                    rows.append({
                        "context_type": label_col,
                        "context_label": label,
                        "predictor": predictor,
                        "predictor_role": role,
                        "outcome": outcome,
                        "n": len(g),
                        "status": "insufficient_data",
                    })
                    continue

                sd = g[predictor].std(ddof=1)
                if not np.isfinite(sd) or sd == 0:
                    rows.append({
                        "context_type": label_col,
                        "context_label": label,
                        "predictor": predictor,
                        "predictor_role": role,
                        "outcome": outcome,
                        "n": len(g),
                        "status": "zero_predictor_sd",
                    })
                    continue

                g["predictor_z"] = (g[predictor] - g[predictor].mean()) / sd

                if outcome == "blood_loss_g":
                    if (g[outcome] < 0).any():
                        rows.append({
                            "context_type": label_col,
                            "context_label": label,
                            "predictor": predictor,
                            "predictor_role": role,
                            "outcome": outcome,
                            "n": len(g),
                            "status": "negative_blood_loss",
                        })
                        continue
                    g["model_outcome"] = np.log1p(g[outcome])
                    outcome_scale = "log1p_blood_loss_g"
                else:
                    g["model_outcome"] = g[outcome]
                    outcome_scale = "minutes"

                formula = "model_outcome ~ predictor_z + C(procedure_group) + C(side)"
                try:
                    fit = smf.ols(formula, data=g).fit(cov_type="HC3")
                    ci = fit.conf_int().loc["predictor_z"]
                    rows.append({
                        "context_type": label_col,
                        "context_label": label,
                        "predictor": predictor,
                        "predictor_role": role,
                        "outcome": outcome,
                        "outcome_label": outcome_label,
                        "outcome_scale": outcome_scale,
                        "n": int(fit.nobs),
                        "predictor_sd_original_units": float(sd),
                        "beta_per_1SD_predictor": float(fit.params["predictor_z"]),
                        "robust_se_HC3": float(fit.bse["predictor_z"]),
                        "ci95_low": float(ci.iloc[0]),
                        "ci95_high": float(ci.iloc[1]),
                        "p_value": float(fit.pvalues["predictor_z"]),
                        "r_squared": float(fit.rsquared),
                        "adjusted_r_squared": float(fit.rsquared_adj),
                        "status": "ok",
                    })
                except Exception as e:
                    rows.append({
                        "context_type": label_col,
                        "context_label": label,
                        "predictor": predictor,
                        "predictor_role": role,
                        "outcome": outcome,
                        "n": len(g),
                        "status": f"model_error:{type(e).__name__}:{e}",
                    })

    out = pd.DataFrame(rows)
    if len(out) and "p_value" in out.columns:
        out["bh_fdr_q_within_context_family"] = np.nan
        mask = out.get("status", pd.Series(index=out.index, dtype=str)).eq("ok")
        if mask.any():
            out.loc[mask, "bh_fdr_q_within_context_family"] = bh_fdr(
                out.loc[mask, "p_value"].to_numpy()
            )
    return out


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    p95, p99 = load_locked_thresholds(args.locked_thresholds_csv)

    # ---- locked frame metrics ----
    frame = pd.read_csv(
        args.locked_frame_csv,
        usecols=[
            "case_id",
            "sample_time_sec",
            "structural_visibility_loss_v1",
            "persistent_degradation_proxy_v1",
        ],
        low_memory=False,
    )
    frame["case_id"] = frame["case_id"].astype("string").str.strip().str.upper()
    frame["sample_time_sec"] = num(frame["sample_time_sec"])
    frame["_key"] = make_key(frame, args.time_round_decimals)

    # ---- full workflow source ----
    wh = pd.read_csv(args.full_workflow_csv, nrows=0)
    need = [
        "case_id",
        "sample_time_sec",
        "workflow_level1_label",
        "workflow_level2_label",
    ]
    missing = [c for c in need if c not in wh.columns]
    if missing:
        raise ValueError(f"Full workflow source missing: {missing}")

    workflow = pd.read_csv(
        args.full_workflow_csv,
        usecols=need,
        low_memory=False,
    )
    workflow["case_id"] = workflow["case_id"].astype("string").str.strip().str.upper()
    workflow["sample_time_sec"] = num(workflow["sample_time_sec"])
    workflow["_key"] = make_key(workflow, args.time_round_decimals)

    if frame["_key"].duplicated().any():
        raise ValueError(f"Duplicate locked-frame keys: {int(frame['_key'].duplicated().sum())}")
    if workflow["_key"].duplicated().any():
        raise ValueError(f"Duplicate workflow keys: {int(workflow['_key'].duplicated().sum())}")

    merged = frame.merge(
        workflow[["_key", "workflow_level1_label", "workflow_level2_label"]],
        on="_key",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    matched = int((merged["_merge"] == "both").sum())
    unmatched = int((merged["_merge"] != "both").sum())

    # Require complete 519,198-frame key match before context analysis.
    if unmatched != 0:
        raise ValueError(
            f"Full workflow join is incomplete: matched={matched}, unmatched={unmatched}"
        )

    # ---- aggregate full context ----
    phase = aggregate_case_context(
        merged, "workflow_level1_label", p95, p99
    )
    workspace = aggregate_case_context(
        merged, "workflow_level2_label", p95, p99
    )

    phase.to_csv(
        args.output_dir / "full_case_phase_video_burden_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )
    workspace.to_csv(
        args.output_dir / "full_case_workspace_video_burden_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )

    phase_desc = descriptive_context_summary(phase, "workflow_level1_label")
    workspace_desc = descriptive_context_summary(workspace, "workflow_level2_label")
    phase_desc.to_csv(
        args.output_dir / "full_phase_video_burden_descriptive_summary.csv",
        index=False,
    )
    workspace_desc.to_csv(
        args.output_dir / "full_workspace_video_burden_descriptive_summary.csv",
        index=False,
    )

    # ---- clinical table already frozen from prior analysis ----
    clinical = pd.read_csv(args.clinical_analysis_table, low_memory=False)
    clinical["case_id"] = clinical["case_id"].astype("string").str.strip().str.upper()
    if clinical["case_id"].duplicated().any():
        raise ValueError("Duplicate case_id in locked clinical analysis table.")

    # ---- phase outcome analysis ----
    phase_sp, phase_eligible, phase_merged = spearman_context(
        phase, clinical, "workflow_level1_label", args.min_context_cases
    )
    phase_adj = adjusted_context_models(
        phase_merged, phase_eligible, "workflow_level1_label"
    )

    phase_sp.to_csv(
        args.output_dir / "phase_specific_outcome_spearman.csv",
        index=False,
    )
    phase_adj.to_csv(
        args.output_dir / "phase_specific_outcome_adjusted_models.csv",
        index=False,
    )

    # ---- workspace outcome analysis ----
    ws_sp, ws_eligible, ws_merged = spearman_context(
        workspace, clinical, "workflow_level2_label", args.min_context_cases
    )
    ws_adj = adjusted_context_models(
        ws_merged, ws_eligible, "workflow_level2_label"
    )

    ws_sp.to_csv(
        args.output_dir / "workspace_specific_outcome_spearman.csv",
        index=False,
    )
    ws_adj.to_csv(
        args.output_dir / "workspace_specific_outcome_adjusted_models.csv",
        index=False,
    )

    # ---- QC ----
    qc = pd.DataFrame([{
        "locked_frame_rows": len(frame),
        "workflow_rows": len(workflow),
        "matched_rows": matched,
        "unmatched_rows": unmatched,
        "cases": merged["case_id"].nunique(),
        "phase_nonmissing_frames": int(merged["workflow_level1_label"].notna().sum()),
        "workspace_nonmissing_frames": int(merged["workflow_level2_label"].notna().sum()),
        "phase_missing_frames": int(merged["workflow_level1_label"].isna().sum()),
        "workspace_missing_frames": int(merged["workflow_level2_label"].isna().sum()),
        "locked_structural_p95": p95,
        "locked_structural_p99": p99,
        "min_context_cases_for_outcome_analysis": args.min_context_cases,
        "eligible_phase_count": len(phase_eligible),
        "eligible_workspace_count": len(ws_eligible),
        "statsmodels_available": STATSMODELS_AVAILABLE,
    }])
    qc.to_csv(
        args.output_dir / "full_workflow_context_analysis_qc.csv",
        index=False,
    )

    print("QC summary:")
    print(qc.to_string(index=False))
    print()
    print("Full phase counts:")
    print(merged["workflow_level1_label"].value_counts(dropna=False).to_string())
    print()
    print("Full workspace counts:")
    print(merged["workflow_level2_label"].value_counts(dropna=False).to_string())
    print()
    print("Eligible phases (n_cases >= %d):" % args.min_context_cases)
    for x in phase_eligible:
        print(" ", x)
    print()
    print("Phase-specific Spearman:")
    if len(phase_sp):
        print(phase_sp.to_string(index=False))
    else:
        print("none")
    print()
    print("Phase-specific adjusted models:")
    if len(phase_adj):
        print(phase_adj.to_string(index=False))
    else:
        print("none")
    print()
    print("Eligible workspaces (n_cases >= %d):" % args.min_context_cases)
    for x in ws_eligible:
        print(" ", x)
    print()
    print("Workspace-specific Spearman:")
    if len(ws_sp):
        print(ws_sp.to_string(index=False))
    else:
        print("none")
    print()
    print("Workspace-specific adjusted models:")
    if len(ws_adj):
        print(ws_adj.to_string(index=False))
    else:
        print("none")
    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
