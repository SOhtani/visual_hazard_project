#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


METRIC = "low_light_or_blackout_ratio_v1"
SUMMARY_NAME = "_frame_score_summary.csv"


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Build a neo color-phenotype analyzable-frame manifest using the same "
            "historical low-light p99 rule derived from the 2023 reference cohort."
        )
    )
    p.add_argument("--reference-dir", required=True, type=Path)
    p.add_argument("--neo-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument(
        "--expected-reference-excluded",
        type=int,
        default=5192,
        help="Known historical low-light exclusions from 519,198 technically analyzable reference frames.",
    )
    return p.parse_args()


def case_files(root: Path):
    return [
        p for p in sorted(root.glob("*_frame_scores.csv"))
        if p.name != SUMMARY_NAME
    ]


def read_minimal(path: Path):
    hdr = pd.read_csv(path, nrows=0)
    need = ["metric_status", METRIC]
    missing = [c for c in need if c not in hdr.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    d = pd.read_csv(path, usecols=need)
    d[METRIC] = pd.to_numeric(d[METRIC], errors="coerce")
    return d


def choose_rule(values: np.ndarray, threshold: float, expected: int):
    gt = int(np.sum(values > threshold))
    ge = int(np.sum(values >= threshold))

    if gt == expected and ge != expected:
        return ">", gt, ge
    if ge == expected and gt != expected:
        return ">=", gt, ge
    if gt == expected and ge == expected:
        return ">", gt, ge

    raise RuntimeError(
        "Could not reproduce the known historical exclusion count. "
        f"p99={threshold:.12g}, excluded_if_gt={gt}, excluded_if_ge={ge}, "
        f"expected={expected}. Stop rather than changing the historical rule."
    )


def excluded_mask(series: pd.Series, threshold: float, rule: str):
    x = pd.to_numeric(series, errors="coerce")
    if rule == ">":
        return x > threshold
    if rule == ">=":
        return x >= threshold
    raise ValueError(rule)


def main():
    a = parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)

    ref_files = case_files(a.reference_dir)
    neo_files = case_files(a.neo_dir)
    if not ref_files:
        raise FileNotFoundError(f"No reference case CSVs: {a.reference_dir}")
    if not neo_files:
        raise FileNotFoundError(f"No neo case CSVs: {a.neo_dir}")

    ref_vals = []
    n_ref_rows = 0
    n_ref_ok = 0

    for i, p in enumerate(ref_files, 1):
        d = read_minimal(p)
        n_ref_rows += len(d)
        ok = d["metric_status"].astype(str).eq("ok")
        n_ref_ok += int(ok.sum())
        x = d.loc[ok, METRIC].dropna().to_numpy(dtype=float)
        ref_vals.append(x)
        print(f"[reference] {i}/{len(ref_files)} {p.name}")

    ref = np.concatenate(ref_vals)
    threshold = float(np.nanpercentile(ref, 99))
    rule, n_gt, n_ge = choose_rule(
        ref, threshold, a.expected_reference_excluded
    )

    included_parts = []
    excluded_parts = []
    neo_qc = []

    for i, p in enumerate(neo_files, 1):
        d = pd.read_csv(p)
        if "metric_status" not in d.columns or METRIC not in d.columns:
            raise ValueError(f"{p} missing metric_status or {METRIC}")

        ok = d["metric_status"].astype(str).eq("ok")
        bad_low_light = excluded_mask(d[METRIC], threshold, rule)
        analyzable = ok & (~bad_low_light)

        inc = d.loc[analyzable].copy()
        exc = d.loc[ok & bad_low_light].copy()
        inc["color_phenotype_analyzable_v1"] = 1
        exc["color_phenotype_analyzable_v1"] = 0
        inc["historical_low_light_p99_threshold"] = threshold
        exc["historical_low_light_p99_threshold"] = threshold
        inc["historical_low_light_exclusion_rule"] = rule
        exc["historical_low_light_exclusion_rule"] = rule

        included_parts.append(inc)
        excluded_parts.append(exc)

        neo_qc.append({
            "case_id": p.stem.replace("_frame_scores", ""),
            "n_rows": len(d),
            "n_metric_status_ok": int(ok.sum()),
            "n_low_light_excluded": int((ok & bad_low_light).sum()),
            "n_color_analyzable": int(analyzable.sum()),
            "excluded_fraction_of_ok": (
                float((ok & bad_low_light).sum() / ok.sum()) if ok.sum() else np.nan
            ),
        })
        print(f"[neo] {i}/{len(neo_files)} {p.name}")

    included = pd.concat(included_parts, ignore_index=True)
    excluded = pd.concat(excluded_parts, ignore_index=True)

    included_path = a.output_dir / "neo_color_phenotype_analyzable_frames_v1_full_metadata.csv"
    excluded_path = a.output_dir / "neo_color_phenotype_low_light_excluded_frames_v1.csv"
    qc_path = a.output_dir / "neo_color_analyzable_qc.csv"
    rule_path = a.output_dir / "historical_low_light_rule_qc.csv"

    included.to_csv(included_path, index=False, encoding="utf-8-sig")
    excluded.to_csv(excluded_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(neo_qc).to_csv(qc_path, index=False, encoding="utf-8-sig")

    pd.DataFrame([{
        "reference_case_csvs": len(ref_files),
        "reference_rows_total": n_ref_rows,
        "reference_metric_status_ok": n_ref_ok,
        "reference_nonmissing_metric_rows": len(ref),
        "metric": METRIC,
        "reference_p99_threshold": threshold,
        "excluded_if_gt": n_gt,
        "excluded_if_ge": n_ge,
        "selected_rule": rule,
        "expected_historical_excluded": a.expected_reference_excluded,
        "expected_historical_analyzable": 514006,
    }]).to_csv(rule_path, index=False, encoding="utf-8-sig")

    print()
    print("=== Historical low-light rule ===")
    print(f"reference valid/nonmissing: {len(ref)}")
    print(f"{METRIC} p99: {threshold:.12g}")
    print(f"excluded if > p99 : {n_gt}")
    print(f"excluded if >= p99: {n_ge}")
    print(f"selected rule: {METRIC} {rule} {threshold:.12g}")
    print()
    print("=== Neo color analyzable QC ===")
    print(pd.DataFrame(neo_qc).to_string(index=False))
    print()
    print("Total neo analyzable:", len(included))
    print("Total neo low-light excluded:", len(excluded))
    print("Saved:", included_path)


if __name__ == "__main__":
    main()
