#!/usr/bin/env python
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd


METRIC_COLS = [
    "case_id",
    "sample_time_sec",
    "structural_visibility_loss_v1",
    "metric_status",
]

WORKFLOW_COLS = [
    "case_id",
    "sample_time_sec",
    "workflow_level1_label",
    "workflow_level2_label",
]

LENS_FLAG = "cand_lens_persistent_degradation_proxy"


def parse_args():
    p = argparse.ArgumentParser(
        description="Build locked full-cohort video-burden tables for the 2023 development cohort."
    )
    p.add_argument("--metrics-dir", required=True, type=Path)
    p.add_argument("--lens-candidate-pool", required=True, type=Path)
    p.add_argument("--workflow-metadata", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--episode-gap-sec", type=float, default=1.5)
    p.add_argument("--time-round-decimals", type=int, default=3)
    return p.parse_args()


def valid_metric_status(df: pd.DataFrame) -> pd.Series:
    if "metric_status" not in df.columns:
        return pd.Series(True, index=df.index)
    s = df["metric_status"].fillna("").astype(str).str.strip().str.lower()
    known_good = {"ok", "valid", "success"}
    observed = set(s.unique())
    if known_good & observed:
        return s.isin(known_good)
    bad = pd.Series(False, index=df.index)
    for token in ("invalid", "error", "fail", "zero", "empty", "corrupt", "missing", "unreadable"):
        bad |= s.str.contains(token, regex=False)
    return ~bad


def as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.fillna("").astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes", "y", "t"}
    )


def make_key(df: pd.DataFrame, decimals: int) -> pd.Series:
    case = df["case_id"].astype(str).str.strip().str.upper()
    t = pd.to_numeric(df["sample_time_sec"], errors="coerce").round(decimals)
    return case + "|" + t.map(lambda x: f"{x:.{decimals}f}" if pd.notna(x) else "NA")


def read_metrics(metrics_dir: Path) -> pd.DataFrame:
    paths = sorted(glob.glob(str(metrics_dir / "CASE*_frame_scores.csv")))
    if not paths:
        raise FileNotFoundError(f"No CASE*_frame_scores.csv under {metrics_dir}")
    parts = []
    for path in paths:
        hdr = pd.read_csv(path, nrows=0)
        cols = [c for c in METRIC_COLS if c in hdr.columns]
        d = pd.read_csv(path, usecols=cols, low_memory=False)
        parts.append(d)
    return pd.concat(parts, ignore_index=True, sort=False)


def episode_stats(g: pd.DataFrame, flag_col: str, gap_sec: float):
    x = g[["sample_time_sec", flag_col]].copy()
    x["sample_time_sec"] = pd.to_numeric(x["sample_time_sec"], errors="coerce")
    x[flag_col] = x[flag_col].astype(bool)
    x = x.sort_values("sample_time_sec", kind="mergesort")

    pos = x[x[flag_col]].copy()
    if pos.empty:
        return {
            f"{flag_col}_total_seconds": 0,
            f"{flag_col}_episode_count": 0,
            f"{flag_col}_max_episode_seconds": 0,
        }

    dt = pos["sample_time_sec"].diff()
    new_episode = dt.isna() | (dt > gap_sec)
    pos["_episode_id"] = new_episode.cumsum()

    sizes = pos.groupby("_episode_id").size()
    return {
        f"{flag_col}_total_seconds": int(len(pos)),
        f"{flag_col}_episode_count": int(len(sizes)),
        f"{flag_col}_max_episode_seconds": int(sizes.max()),
    }


def aggregate_group(g: pd.DataFrame, global_p95: float, global_p99: float):
    s = pd.to_numeric(g["structural_visibility_loss_v1"], errors="coerce")
    n_valid = int(s.notna().sum())
    proxy = g["persistent_degradation_proxy_v1"].astype(bool)

    out = {
        "n_frames": len(g),
        "n_structural_nonmissing": n_valid,
        "structural_median": float(s.median()) if n_valid else np.nan,
        "structural_p90": float(s.quantile(0.90)) if n_valid else np.nan,
        "structural_fraction_ge_global_p95": float((s >= global_p95).mean()) if n_valid else np.nan,
        "structural_fraction_ge_global_p99": float((s >= global_p99).mean()) if n_valid else np.nan,
        "persistent_degradation_frames": int(proxy.sum()),
        "persistent_degradation_fraction": float(proxy.mean()) if len(g) else np.nan,
    }
    return out


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- full quality cohort ----
    raw = read_metrics(args.metrics_dir)
    raw["case_id"] = raw["case_id"].astype(str).str.strip().str.upper()
    raw["sample_time_sec"] = pd.to_numeric(raw["sample_time_sec"], errors="coerce")
    raw["_key"] = make_key(raw, args.time_round_decimals)

    valid = valid_metric_status(raw)
    df = raw.loc[valid].copy()

    if df["_key"].duplicated().any():
        ndup = int(df["_key"].duplicated().sum())
        raise ValueError(f"Duplicate case/time keys in valid metric cohort: {ndup}")

    # ---- freeze historical persistent-degradation proxy identity ----
    pool = pd.read_csv(args.lens_candidate_pool, low_memory=False)
    required_pool = {"case_id", "sample_time_sec", LENS_FLAG}
    missing_pool = required_pool - set(pool.columns)
    if missing_pool:
        raise ValueError(f"Lens candidate pool missing: {sorted(missing_pool)}")

    pool["_key"] = make_key(pool, args.time_round_decimals)
    lens_positive_keys = set(
        pool.loc[as_bool(pool[LENS_FLAG]), "_key"].astype(str)
    )
    df["persistent_degradation_proxy_v1"] = df["_key"].isin(lens_positive_keys)

    # ---- locked global structural thresholds ----
    structural = pd.to_numeric(
        df["structural_visibility_loss_v1"], errors="coerce"
    )
    global_p95 = float(structural.quantile(0.95))
    global_p99 = float(structural.quantile(0.99))

    # ---- workflow context ----
    whdr = pd.read_csv(args.workflow_metadata, nrows=0)
    wcols = [c for c in WORKFLOW_COLS if c in whdr.columns]
    workflow = pd.read_csv(
        args.workflow_metadata,
        usecols=wcols,
        low_memory=False,
    )
    workflow["case_id"] = workflow["case_id"].astype(str).str.strip().str.upper()
    workflow["sample_time_sec"] = pd.to_numeric(
        workflow["sample_time_sec"], errors="coerce"
    )
    workflow["_key"] = make_key(workflow, args.time_round_decimals)

    if workflow["_key"].duplicated().any():
        ndup = int(workflow["_key"].duplicated().sum())
        raise ValueError(f"Duplicate workflow case/time keys: {ndup}")

    df = df.merge(
        workflow[["_key", "workflow_level1_label", "workflow_level2_label"]],
        on="_key",
        how="left",
        indicator="_workflow_merge",
    )

    # ---- case-level aggregation ----
    case_rows = []
    for case_id, g in df.groupby("case_id", sort=True):
        out = {"case_id": case_id}
        out.update(aggregate_group(g, global_p95, global_p99))
        eps = episode_stats(
            g,
            "persistent_degradation_proxy_v1",
            args.episode_gap_sec,
        )
        out.update({
            "persistent_degradation_total_seconds": eps["persistent_degradation_proxy_v1_total_seconds"],
            "persistent_degradation_episode_count": eps["persistent_degradation_proxy_v1_episode_count"],
            "persistent_degradation_max_episode_seconds": eps["persistent_degradation_proxy_v1_max_episode_seconds"],
        })
        case_rows.append(out)
    case_df = pd.DataFrame(case_rows)

    # ---- case x phase ----
    phase_rows = []
    phase_valid = df[df["workflow_level1_label"].notna()].copy()
    for (case_id, label), g in phase_valid.groupby(
        ["case_id", "workflow_level1_label"], sort=True
    ):
        out = {"case_id": case_id, "workflow_level1_label": label}
        out.update(aggregate_group(g, global_p95, global_p99))
        phase_rows.append(out)
    phase_df = pd.DataFrame(phase_rows)

    # ---- case x workspace ----
    workspace_rows = []
    workspace_valid = df[df["workflow_level2_label"].notna()].copy()
    for (case_id, label), g in workspace_valid.groupby(
        ["case_id", "workflow_level2_label"], sort=True
    ):
        out = {"case_id": case_id, "workflow_level2_label": label}
        out.update(aggregate_group(g, global_p95, global_p99))
        workspace_rows.append(out)
    workspace_df = pd.DataFrame(workspace_rows)

    # ---- compact frame-level locked table ----
    frame_cols = [
        "case_id",
        "sample_time_sec",
        "structural_visibility_loss_v1",
        "persistent_degradation_proxy_v1",
        "workflow_level1_label",
        "workflow_level2_label",
    ]
    frame_df = df[frame_cols].copy()

    # ---- write outputs ----
    frame_df.to_csv(
        args.output_dir / "locked_frame_level_video_metrics_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )
    case_df.to_csv(
        args.output_dir / "locked_case_level_video_burden_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )
    phase_df.to_csv(
        args.output_dir / "locked_case_phase_video_burden_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )
    workspace_df.to_csv(
        args.output_dir / "locked_case_workspace_video_burden_2023.csv",
        index=False,
        encoding="utf-8-sig",
    )

    thresholds = pd.DataFrame([
        {"metric": "structural_visibility_loss_v1", "quantile": "p95", "value": global_p95},
        {"metric": "structural_visibility_loss_v1", "quantile": "p99", "value": global_p99},
    ])
    thresholds.to_csv(
        args.output_dir / "locked_structural_thresholds_2023.csv",
        index=False,
    )

    qc = pd.DataFrame([{
        "raw_metric_rows": len(raw),
        "valid_metric_rows": len(df),
        "technical_invalid_rows": int((~valid).sum()),
        "cases": df["case_id"].nunique(),
        "structural_nonmissing": int(structural.notna().sum()),
        "persistent_degradation_positive_frames": int(df["persistent_degradation_proxy_v1"].sum()),
        "persistent_degradation_positive_cases": int(
            df.loc[df["persistent_degradation_proxy_v1"], "case_id"].nunique()
        ),
        "workflow_source_rows": len(workflow),
        "workflow_matched_frames": int((df["_workflow_merge"] == "both").sum()),
        "workflow_unmatched_frames": int((df["_workflow_merge"] != "both").sum()),
        "phase_nonmissing_frames": int(df["workflow_level1_label"].notna().sum()),
        "workspace_nonmissing_frames": int(df["workflow_level2_label"].notna().sum()),
        "structural_global_p95": global_p95,
        "structural_global_p99": global_p99,
        "episode_gap_sec": args.episode_gap_sec,
    }])
    qc.to_csv(
        args.output_dir / "locked_full_cohort_video_burden_qc.csv",
        index=False,
    )

    print("QC summary:")
    print(qc.to_string(index=False))
    print()
    print("Case-level table:")
    print(f"  rows={len(case_df)} columns={len(case_df.columns)}")
    print()
    print("Phase labels:")
    if not phase_valid.empty:
        print(phase_valid["workflow_level1_label"].value_counts().to_string())
    else:
        print("  none")
    print()
    print("Workspace labels:")
    if not workspace_valid.empty:
        print(workspace_valid["workflow_level2_label"].value_counts().to_string())
    else:
        print("  none")
    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
