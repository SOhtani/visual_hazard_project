#!/usr/bin/env python
from __future__ import annotations

import argparse
import glob
import random
from pathlib import Path

import numpy as np
import pandas as pd


QUALITY_NEEDED = [
    "case_id",
    "sample_time_sec",
    "frame_idx_1based",
    "image_file",
    "image_path",
    "roi_edge_density_v1",
    "focus_badness_v1",
    "local_obstruction_max_component_ratio",
    "center_low_structure_area_v1",
    "veil_low_contrast_score_v1",
    "metric_status",
]

COLOR_NEEDED = [
    "case_id",
    "sample_time_sec",
    "image_path",
    "red_saturation_mean_v1",
    "red_excess_mean_v1",
    "fresh_red_candidate_ratio_v1",
    "dark_red_brown_candidate_ratio_v1",
    "blood_like_redness_ratio_v1",
    "center_weighted_blood_like_redness_v1",
    "red_dominance_ratio_v1",
]

ROUTES = [
    "NC_A_very_low_edge",
    "NC_B_low_edge_high_focus_badness",
    "NC_C_low_edge_large_low_structure_component",
    "SM_A_very_high_veil",
    "SM_B_high_veil_positive_rise",
    "SM_C_extreme_positive_veil_rise",
    "BL_A_red_saturation_extreme",
    "BL_B_red_excess_extreme",
    "BL_C_fresh_red_extreme",
    "BL_D_dark_red_brown_extreme",
    "BL_E_multifeature_high",
    "BL_HN_redness_only_challenge",
]


def parse_args():
    p = argparse.ArgumentParser(
        description="Build Phase-01C targeted retrieval v2 candidate audit."
    )
    p.add_argument("--metrics-dir", required=True, type=Path)
    p.add_argument("--color-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--pilot-moments", type=Path, default=None)
    p.add_argument("--prior-audit-manifest", type=Path, default=None)
    p.add_argument("--n-per-route", type=int, default=6)
    p.add_argument("--per-case-cap", type=int, default=2)
    p.add_argument("--min-gap-sec", type=float, default=60.0)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--time-round-decimals", type=int, default=3)
    return p.parse_args()


def read_quality(metrics_dir: Path) -> pd.DataFrame:
    paths = sorted(glob.glob(str(metrics_dir / "CASE*_frame_scores.csv")))
    if not paths:
        raise FileNotFoundError(f"No CASE*_frame_scores.csv files found in {metrics_dir}")

    parts = []
    for p in paths:
        head = pd.read_csv(p, nrows=0)
        cols = [c for c in QUALITY_NEEDED if c in head.columns]
        part = pd.read_csv(p, usecols=cols, low_memory=False)
        parts.append(part)

    df = pd.concat(parts, ignore_index=True, sort=False)
    return df


def status_valid_mask(df: pd.DataFrame) -> pd.Series:
    if "metric_status" not in df.columns:
        return pd.Series(True, index=df.index)

    s = df["metric_status"].fillna("").astype(str).str.strip().str.lower()
    counts = s.value_counts(dropna=False)

    known_good = {"ok", "valid", "success"}
    good_present = [x for x in known_good if x in set(counts.index)]

    if good_present:
        return s.isin(good_present)

    known_bad_tokens = (
        "invalid",
        "error",
        "fail",
        "zero",
        "empty",
        "corrupt",
        "missing",
        "unreadable",
    )
    bad = pd.Series(False, index=df.index)
    for token in known_bad_tokens:
        bad |= s.str.contains(token, regex=False)
    return ~bad


def build_key(df: pd.DataFrame, decimals: int) -> pd.Series:
    case = df["case_id"].astype(str).str.strip().str.upper()
    t = pd.to_numeric(df["sample_time_sec"], errors="coerce").round(decimals)
    tstr = t.map(lambda x: f"{x:.{decimals}f}" if pd.notna(x) else "NA")
    return case + "|" + tstr


def collect_exclusion_keys(paths, decimals: int):
    keys = set()
    audit = []
    for label, path in paths:
        if path is None or not path.exists():
            audit.append({"source": label, "path": str(path) if path else "", "rows": 0, "keys_added": 0})
            continue

        d = pd.read_csv(path, low_memory=False)
        if "case_id" not in d.columns or "sample_time_sec" not in d.columns:
            raise ValueError(f"{path} lacks case_id/sample_time_sec.")
        k = set(build_key(d, decimals))
        before = len(keys)
        keys.update(k)
        audit.append({
            "source": label,
            "path": str(path),
            "rows": len(d),
            "keys_added": len(keys) - before,
        })
    return keys, pd.DataFrame(audit)


def numeric(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def q(series, value):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return np.nan
    return float(s.quantile(value))


def add_quality_routes(qdf: pd.DataFrame):
    edge = numeric(qdf, "roi_edge_density_v1")
    focus = numeric(qdf, "focus_badness_v1")
    loc = numeric(qdf, "local_obstruction_max_component_ratio")
    center = numeric(qdf, "center_low_structure_area_v1")
    veil = numeric(qdf, "veil_low_contrast_score_v1")

    # Compute transparent temporal delta within each case.
    qdf = qdf.sort_values(["case_id", "sample_time_sec"], kind="mergesort").copy()
    qdf["veil_delta_prev_v2"] = (
        qdf.groupby("case_id", sort=False)["veil_low_contrast_score_v1"].diff()
    )
    delta = numeric(qdf, "veil_delta_prev_v2")

    thr = {
        "edge_q01": q(edge, 0.01),
        "edge_q05": q(edge, 0.05),
        "focus_q95": q(focus, 0.95),
        "local_component_q95": q(loc, 0.95),
        "center_low_structure_q95": q(center, 0.95),
        "veil_q95": q(veil, 0.95),
        "veil_q99": q(veil, 0.99),
        "veil_delta_q95": q(delta, 0.95),
        "veil_delta_q99": q(delta, 0.99),
    }

    qdf["NC_A_very_low_edge"] = edge <= thr["edge_q01"]
    qdf["NC_B_low_edge_high_focus_badness"] = (
        (edge <= thr["edge_q05"]) & (focus >= thr["focus_q95"])
    )
    qdf["NC_C_low_edge_large_low_structure_component"] = (
        (edge <= thr["edge_q05"]) & (loc >= thr["local_component_q95"])
    )

    qdf["SM_A_very_high_veil"] = veil >= thr["veil_q99"]
    qdf["SM_B_high_veil_positive_rise"] = (
        (veil >= thr["veil_q95"]) & (delta >= thr["veil_delta_q95"])
    )
    qdf["SM_C_extreme_positive_veil_rise"] = delta >= thr["veil_delta_q99"]

    return qdf, thr


def add_color_routes(cdf: pd.DataFrame):
    rs = numeric(cdf, "red_saturation_mean_v1")
    rex = numeric(cdf, "red_excess_mean_v1")
    fresh = numeric(cdf, "fresh_red_candidate_ratio_v1")
    dark = numeric(cdf, "dark_red_brown_candidate_ratio_v1")
    broad = numeric(cdf, "blood_like_redness_ratio_v1")

    thr = {
        "red_saturation_q95": q(rs, 0.95),
        "red_saturation_q99": q(rs, 0.99),
        "red_excess_q95": q(rex, 0.95),
        "red_excess_q99": q(rex, 0.99),
        "fresh_red_q95": q(fresh, 0.95),
        "fresh_red_q99": q(fresh, 0.99),
        "dark_red_brown_q95": q(dark, 0.95),
        "dark_red_brown_q99": q(dark, 0.99),
        "broad_redness_q99": q(broad, 0.99),
    }

    cdf["BL_A_red_saturation_extreme"] = rs >= thr["red_saturation_q99"]
    cdf["BL_B_red_excess_extreme"] = rex >= thr["red_excess_q99"]
    cdf["BL_C_fresh_red_extreme"] = fresh >= thr["fresh_red_q99"]
    cdf["BL_D_dark_red_brown_extreme"] = dark >= thr["dark_red_brown_q99"]

    high95 = pd.DataFrame({
        "rs": rs >= thr["red_saturation_q95"],
        "rex": rex >= thr["red_excess_q95"],
        "fresh": fresh >= thr["fresh_red_q95"],
        "dark": dark >= thr["dark_red_brown_q95"],
    })
    cdf["blood_feature_count_ge_q95_v2"] = high95.sum(axis=1)
    cdf["BL_E_multifeature_high"] = cdf["blood_feature_count_ge_q95_v2"] >= 3

    positive_bl = (
        cdf["BL_A_red_saturation_extreme"]
        | cdf["BL_B_red_excess_extreme"]
        | cdf["BL_C_fresh_red_extreme"]
        | cdf["BL_D_dark_red_brown_extreme"]
        | cdf["BL_E_multifeature_high"]
    )
    cdf["BL_HN_redness_only_challenge"] = (
        (broad >= thr["broad_redness_q99"]) & (~positive_bl)
    )

    return cdf, thr


def route_strength(df: pd.DataFrame, route: str):
    # Only used to provide an auditable sorting variable; sampling remains random.
    if route == "NC_A_very_low_edge":
        return -numeric(df, "roi_edge_density_v1")
    if route == "NC_B_low_edge_high_focus_badness":
        return numeric(df, "focus_badness_v1") - numeric(df, "roi_edge_density_v1")
    if route == "NC_C_low_edge_large_low_structure_component":
        return numeric(df, "local_obstruction_max_component_ratio") - numeric(df, "roi_edge_density_v1")
    if route == "SM_A_very_high_veil":
        return numeric(df, "veil_low_contrast_score_v1")
    if route in {"SM_B_high_veil_positive_rise", "SM_C_extreme_positive_veil_rise"}:
        return numeric(df, "veil_delta_prev_v2")
    if route == "BL_A_red_saturation_extreme":
        return numeric(df, "red_saturation_mean_v1")
    if route == "BL_B_red_excess_extreme":
        return numeric(df, "red_excess_mean_v1")
    if route == "BL_C_fresh_red_extreme":
        return numeric(df, "fresh_red_candidate_ratio_v1")
    if route == "BL_D_dark_red_brown_extreme":
        return numeric(df, "dark_red_brown_candidate_ratio_v1")
    if route == "BL_E_multifeature_high":
        return numeric(df, "blood_feature_count_ge_q95_v2")
    if route == "BL_HN_redness_only_challenge":
        return numeric(df, "blood_like_redness_ratio_v1")
    return pd.Series(np.nan, index=df.index)


def select_diverse(df, route, n, rng, selected_keys, case_counts, case_times,
                   per_case_cap, min_gap_sec):
    pool = df[df[route].fillna(False)].copy()
    if pool.empty:
        return pool

    idx = list(pool.index)
    rng.shuffle(idx)

    chosen = []
    for i in idx:
        row = pool.loc[i]
        key = row["_key"]
        case = str(row["case_id"]).upper()
        t = float(row["sample_time_sec"])

        if key in selected_keys:
            continue
        if case_counts.get(case, 0) >= per_case_cap:
            continue
        if any(abs(t - pt) < min_gap_sec for pt in case_times.get(case, [])):
            continue

        chosen.append(i)
        selected_keys.add(key)
        case_counts[case] = case_counts.get(case, 0) + 1
        case_times.setdefault(case, []).append(t)

        if len(chosen) >= n:
            break

    return pool.loc[chosen].copy()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- Quality cohort ----------------
    qdf = read_quality(args.metrics_dir)
    qdf["sample_time_sec"] = pd.to_numeric(qdf["sample_time_sec"], errors="coerce")
    qdf["_key"] = build_key(qdf, args.time_round_decimals)

    status_counts = (
        qdf["metric_status"].fillna("<NA>").astype(str).value_counts(dropna=False)
        if "metric_status" in qdf.columns else pd.Series(dtype=int)
    )
    valid = status_valid_mask(qdf)
    qdf_valid = qdf.loc[valid].copy()

    qdf_valid, quality_thr = add_quality_routes(qdf_valid)

    # ---------------- Color cohort ----------------
    color_head = pd.read_csv(args.color_csv, nrows=0)
    color_cols = [c for c in COLOR_NEEDED if c in color_head.columns]
    cdf = pd.read_csv(args.color_csv, usecols=color_cols, low_memory=False)
    cdf["sample_time_sec"] = pd.to_numeric(cdf["sample_time_sec"], errors="coerce")
    cdf["_key"] = build_key(cdf, args.time_round_decimals)
    if cdf["_key"].duplicated().any():
        raise ValueError("Duplicate case/time keys in color CSV.")

    cdf, color_thr = add_color_routes(cdf)

    # ---------------- Exclusions ----------------
    exclusion_keys, exclusion_audit = collect_exclusion_keys(
        [
            ("pilot_moments", args.pilot_moments),
            ("prior_136_audit", args.prior_audit_manifest),
        ],
        args.time_round_decimals,
    )
    exclusion_audit.to_csv(
        args.output_dir / "phase01c_v2_exclusion_audit.csv", index=False
    )

    qdf_valid["_excluded_reviewed"] = qdf_valid["_key"].isin(exclusion_keys)
    cdf["_excluded_reviewed"] = cdf["_key"].isin(exclusion_keys)

    q_eligible = qdf_valid.loc[~qdf_valid["_excluded_reviewed"]].copy()
    c_eligible = cdf.loc[~cdf["_excluded_reviewed"]].copy()

    # Merge all candidate routes into one frame table.
    q_keep = [
        "_key", "case_id", "sample_time_sec", "frame_idx_1based",
        "image_file", "image_path",
        "roi_edge_density_v1", "focus_badness_v1",
        "local_obstruction_max_component_ratio",
        "center_low_structure_area_v1",
        "veil_low_contrast_score_v1", "veil_delta_prev_v2",
    ] + ROUTES[:6]
    q_keep = [c for c in q_keep if c in q_eligible.columns]

    c_keep = [
        "_key", "case_id", "sample_time_sec", "image_path",
        "red_saturation_mean_v1", "red_excess_mean_v1",
        "fresh_red_candidate_ratio_v1",
        "dark_red_brown_candidate_ratio_v1",
        "blood_like_redness_ratio_v1",
        "center_weighted_blood_like_redness_v1",
        "red_dominance_ratio_v1",
        "blood_feature_count_ge_q95_v2",
    ] + ROUTES[6:]
    c_keep = [c for c in c_keep if c in c_eligible.columns]

    qpart = q_eligible[q_keep].copy()
    cpart = c_eligible[c_keep].copy()

    combined = qpart.merge(
        cpart,
        on="_key",
        how="outer",
        suffixes=("_quality", "_color"),
    )

    # Coalesce identity/path after outer merge.
    for col in ["case_id", "sample_time_sec", "image_path"]:
        a = f"{col}_quality"
        b = f"{col}_color"
        if a in combined.columns or b in combined.columns:
            sa = combined[a] if a in combined.columns else pd.Series(np.nan, index=combined.index)
            sb = combined[b] if b in combined.columns else pd.Series(np.nan, index=combined.index)
            combined[col] = sa.combine_first(sb)

    for route in ROUTES:
        if route not in combined.columns:
            combined[route] = False
        combined[route] = combined[route].astype("boolean").fillna(False).astype(bool)

    candidate_union = combined[combined[ROUTES].any(axis=1)].copy()

    # Route summary before sampling.
    route_summary = []
    for route in ROUTES:
        g = candidate_union[candidate_union[route]]
        route_summary.append({
            "route": route,
            "candidate_count": len(g),
            "case_count": g["case_id"].nunique(),
        })
    route_summary = pd.DataFrame(route_summary)
    route_summary.to_csv(
        args.output_dir / "phase01c_v2_route_summary.csv", index=False
    )

    # Pairwise overlap.
    overlap = []
    for i, a in enumerate(ROUTES):
        A = candidate_union[a]
        for b in ROUTES[i + 1:]:
            B = candidate_union[b]
            inter = int((A & B).sum())
            union = int((A | B).sum())
            overlap.append({
                "route_a": a,
                "route_b": b,
                "intersection_count": inter,
                "union_count": union,
                "jaccard": inter / union if union else 0.0,
            })
    pd.DataFrame(overlap).to_csv(
        args.output_dir / "phase01c_v2_route_overlap.csv", index=False
    )

    # Threshold audit.
    threshold_rows = (
        [{"source": "quality", "threshold": k, "value": v} for k, v in quality_thr.items()]
        + [{"source": "color", "threshold": k, "value": v} for k, v in color_thr.items()]
    )
    pd.DataFrame(threshold_rows).to_csv(
        args.output_dir / "phase01c_v2_thresholds.csv", index=False
    )

    # Sampling.
    rng = random.Random(args.seed)
    selected_keys = set()
    case_counts = {}
    case_times = {}
    selected_parts = []

    for route in ROUTES:
        sel = select_diverse(
            candidate_union,
            route,
            args.n_per_route,
            rng,
            selected_keys,
            case_counts,
            case_times,
            args.per_case_cap,
            args.min_gap_sec,
        )
        if sel.empty:
            continue
        sel = sel.copy()
        sel["primary_sampling_route"] = route
        sel["primary_route_strength"] = route_strength(sel, route).values
        selected_parts.append(sel)

    selected = (
        pd.concat(selected_parts, ignore_index=True, sort=False)
        if selected_parts else pd.DataFrame()
    )

    if not selected.empty:
        selected["all_positive_routes"] = selected.apply(
            lambda r: ";".join([route for route in ROUTES if bool(r.get(route, False))]),
            axis=1,
        )
        selected["review_id"] = [f"V2A{i:03d}" for i in range(1, len(selected) + 1)]

        # Put review_id first.
        first = [
            "review_id", "case_id", "sample_time_sec", "image_path",
            "primary_sampling_route", "all_positive_routes",
            "primary_route_strength",
        ]
        rest = [c for c in selected.columns if c not in first]
        selected = selected[first + rest]

    selected.to_csv(
        args.output_dir / "phase01c_v2_selected_full_metadata.csv",
        index=False,
        encoding="utf-8-sig",
    )

    blinded_cols = ["review_id", "case_id", "sample_time_sec", "image_path"]
    blinded = (
        selected[blinded_cols].copy()
        if not selected.empty
        else pd.DataFrame(columns=blinded_cols)
    )
    blinded.to_csv(
        args.output_dir / "phase01c_v2_blinded_review_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Selected count per primary route.
    if not selected.empty:
        selected_summary = (
            selected.groupby("primary_sampling_route")
            .size()
            .reindex(ROUTES, fill_value=0)
            .rename("selected_count")
            .rename_axis("route")
            .reset_index()
        )
    else:
        selected_summary = pd.DataFrame(
            {"route": ROUTES, "selected_count": [0] * len(ROUTES)}
        )
    selected_summary = route_summary.merge(
        selected_summary, on="route", how="left"
    )
    selected_summary.to_csv(
        args.output_dir / "phase01c_v2_selected_summary.csv", index=False
    )

    # QC summary.
    qc = pd.DataFrame([{
        "quality_raw_rows": len(qdf),
        "quality_valid_rows": len(qdf_valid),
        "quality_invalid_rows": int((~valid).sum()),
        "color_rows": len(cdf),
        "reviewed_exclusion_keys": len(exclusion_keys),
        "quality_eligible_after_review_exclusion": len(q_eligible),
        "color_eligible_after_review_exclusion": len(c_eligible),
        "candidate_union_rows": len(candidate_union),
        "selected_rows": len(selected),
        "selected_cases": selected["case_id"].nunique() if not selected.empty else 0,
        "seed": args.seed,
        "n_per_route": args.n_per_route,
        "per_case_cap": args.per_case_cap,
        "min_gap_sec": args.min_gap_sec,
    }])
    qc.to_csv(args.output_dir / "phase01c_v2_qc.csv", index=False)

    if not status_counts.empty:
        status_counts.rename_axis("metric_status").reset_index(name="count").to_csv(
            args.output_dir / "phase01c_v2_metric_status_counts.csv", index=False
        )

    readme = f"""# Phase 01C targeted retrieval v2

Internal development candidate audit only.

- quality raw rows: {len(qdf):,}
- quality valid rows: {len(qdf_valid):,}
- color rows: {len(cdf):,}
- previously reviewed keys excluded: {len(exclusion_keys):,}
- candidate union: {len(candidate_union):,}
- selected frames: {len(selected):,}
- selected cases: {selected['case_id'].nunique() if not selected.empty else 0}
- n per route target: {args.n_per_route}
- per-case cap: {args.per_case_cap}
- minimum same-case separation: {args.min_gap_sec} sec
- seed: {args.seed}

The selected review manifest is blinded to retrieval route.
BL-HN is a redness-only challenge route, not a presumed true-negative label.
"""
    (args.output_dir / "README.md").write_text(
        readme, encoding="utf-8", newline="\n"
    )

    print("QC summary:")
    print(qc.to_string(index=False))
    print()
    print("Route summary:")
    print(selected_summary.to_string(index=False))
    print()
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
