#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build frame-level visual-hazard flags and case/phase burden summaries.

This script converts component scores into exploratory visual-hazard flags using
candidate cutoffs from Phase 3 distribution summaries. It is not a final clinical
cutoff model. It is intended to separate frames that should be treated as visual
hazard / non-clean candidates from clean/reference frames, and to summarize their
burden by case and workflow phase.

Important terminology:
- "visual_hazard_any" means at least one selected Tier-1 component exceeds the
  chosen candidate threshold.
- These frames are not discarded from hazard-burden analyses; they are counted.
- They may be excluded only from downstream analyses requiring clean/assessable
  reference frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_DIR = PROJECT_ROOT / "data" / "derived" / "quality_metrics" / "per_frame"
DEFAULT_CUTOFF_CSV = PROJECT_ROOT / "reports" / "phase_component_distributions" / "global_component_candidate_cutoffs.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "visual_hazard_burden"
DEFAULT_AUDIT_CSV = PROJECT_ROOT / "data" / "annotations" / "visual_hazard_gate_audit_frames.csv"
SUMMARY_CSV_NAME = "_frame_score_summary.csv"


@dataclass(frozen=True)
class HazardComponent:
    component: str
    score_col: str
    tier: str
    role: str


COMPONENTS: List[HazardComponent] = [
    HazardComponent("structural_visibility_loss", "structural_visibility_loss_v1", "tier1_main", "whole_roi_structural_loss"),
    HazardComponent("center_low_structure_area", "center_low_structure_area_v1", "tier1_main", "central_structural_loss"),
    HazardComponent("whiteout", "whiteout_ratio_v1", "tier1_main_photometric", "whiteout_photometric_hazard"),
    HazardComponent("low_light_or_blackout", "low_light_or_blackout_ratio_v1", "tier1_main_photometric", "low_light_blackout_photometric_hazard"),
    HazardComponent("reblur_response_loss", "reblur_response_loss_v1", "tier2_auxiliary", "low_high_frequency_response"),
    HazardComponent("veil_low_contrast", "veil_low_contrast_score_v1", "tier2_auxiliary", "low_contrast_low_edge"),
    HazardComponent("raw_blackness", "blackness_raw_ratio_v1", "tier2_auxiliary", "generic_raw_blackness"),
    HazardComponent("corrected_blackness", "blackness_corrected_ratio_v1", "tier2_auxiliary", "generic_corrected_blackness"),
    HazardComponent("specular_like_reflection", "specular_like_ratio_v1", "tier3_reconsider", "whiteout_overlapping_specular_like"),
]

PROFILE_COMPONENTS: Dict[str, List[str]] = {
    # More sensitive; flags any of the four Tier-1 candidates seen in Phase 3 audit.
    "tier1_broad": [
        "structural_visibility_loss_v1",
        "center_low_structure_area_v1",
        "whiteout_ratio_v1",
        "low_light_or_blackout_ratio_v1",
    ],
    # Less redundant; uses central structure + the two photometric hazards.
    "tier1_compact": [
        "center_low_structure_area_v1",
        "whiteout_ratio_v1",
        "low_light_or_blackout_ratio_v1",
    ],
    # Exploratory; includes Tier-1 plus Tier-2 descriptors but not specular.
    "tier1_tier2_exploratory": [
        "structural_visibility_loss_v1",
        "center_low_structure_area_v1",
        "whiteout_ratio_v1",
        "low_light_or_blackout_ratio_v1",
        "reblur_response_loss_v1",
        "veil_low_contrast_score_v1",
        "blackness_raw_ratio_v1",
        "blackness_corrected_ratio_v1",
    ],
}

VALIDITY_FLAG_COLUMNS = [
    "near_uniform_frame_candidate_v1",
    "large_whiteout_candidate_v1",
    "large_blackout_candidate_v1",
    "color_bar_or_test_pattern_candidate_v1",
    "photometric_failure_candidate_v1",
    "image_validity_problem_candidate_v1",
    "component_review_valid_candidate_v1",
]

REVIEW_CORE_COLUMNS = [
    "review_id",
    "review_set_version",
    "case_id",
    "sample_time_sec",
    "frame_index",
    "image_path",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
    "target_component",
    "candidate_label",
    "selection_type",
    "source_score_col",
    "source_score_value",
    "source_rank_within_score",
    "selection_reason",
    "metric_status",
    *VALIDITY_FLAG_COLUMNS,
    "component_interpretation",
    "manual_include",
    "manual_primary_label",
    "manual_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build exploratory visual-hazard flags and burden summaries.")
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--cutoff-csv", type=Path, default=DEFAULT_CUTOFF_CSV)
    parser.add_argument("--annotation-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case", nargs="*", default=None)
    parser.add_argument("--component-profile", choices=sorted(PROFILE_COMPONENTS), default="tier1_broad")
    parser.add_argument("--score-col", nargs="*", default=None, help="Override selected score columns.")
    parser.add_argument("--threshold", nargs="*", default=["p95", "p99"], help="Quantile names from cutoff CSV, e.g. p95 p99.")
    parser.add_argument("--time-col", default="sample_time_sec")
    parser.add_argument("--phase-level", nargs="*", default=["Level-1", "Level-2"], choices=["Level-0", "Level-1", "Level-2"])
    parser.add_argument("--write-frame-flags", action="store_true", help="Write full frame-level flags CSV under output-dir.")
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV, help="Output CSV compatible with 07_export_component_review_sheets.py.")
    parser.add_argument("--audit-threshold", default="p95", help="Threshold name used for audit-frame selection. Default: p95.")
    parser.add_argument("--audit-per-component-n", type=int, default=24, help="Frames per component for hazard audit montage.")
    parser.add_argument("--audit-clean-n", type=int, default=24, help="Clean candidate frames for audit montage.")
    parser.add_argument("--per-case-cap", type=int, default=2, help="Per-case cap for audit selection.")
    parser.add_argument("--review-set-version", default="phase04_visual_hazard_gate_v1")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def infer_case_id_from_path(path: Path) -> str:
    stem = path.stem
    for suffix in ["_frame_scores", "_metrics", "_visual_hazard_components"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def list_metric_csvs(metrics_dir: Path, case_filter: Optional[set[str]]) -> List[Path]:
    paths = sorted(p for p in metrics_dir.glob("*.csv") if p.name != SUMMARY_CSV_NAME)
    if case_filter:
        paths = [p for p in paths if infer_case_id_from_path(p) in case_filter]
    return paths


def load_metric_frames(metrics_dir: Path, case_filter: Optional[set[str]]) -> pd.DataFrame:
    paths = list_metric_csvs(metrics_dir, case_filter)
    if not paths:
        raise FileNotFoundError(f"No metric CSVs found in {metrics_dir}")
    dfs = []
    for path in paths:
        df = pd.read_csv(path)
        if "case_id" not in df.columns:
            df["case_id"] = infer_case_id_from_path(path)
        else:
            df["case_id"] = df["case_id"].fillna(infer_case_id_from_path(path)).astype(str)
        df["source_metric_csv"] = str(path)
        dfs.append(df)
    out = pd.concat(dfs, ignore_index=True, sort=False)
    if "metric_status" in out.columns:
        out = out[(out["metric_status"].isna()) | (out["metric_status"].astype(str) == "ok")].copy()
    return out


def version_key(path: Path) -> Tuple[int, str]:
    m = re.search(r"_v(\d+)\.json$", path.name)
    if m:
        return int(m.group(1)), path.name
    return 1, path.name


def find_annotation_json(annotation_root: Path, case_id: str) -> Optional[Path]:
    candidates = sorted(annotation_root.glob(f"{case_id}_annotation*.json"), key=version_key)
    candidates = [p for p in candidates if "backup" not in p.name.lower()]
    if not candidates:
        candidates = sorted(annotation_root.rglob(f"{case_id}_annotation*.json"), key=version_key)
        candidates = [p for p in candidates if "backup" not in p.name.lower()]
    return candidates[-1] if candidates else None


def load_surgcap_segments(annotation_path: Path) -> List[dict]:
    obj = json.loads(annotation_path.read_text(encoding="utf-8"))
    segments = obj.get("active_annotation", {}).get("segments", [])
    out = []
    for s in segments:
        try:
            start = float(s.get("start_sec"))
            end = float(s.get("end_sec"))
        except Exception:
            continue
        if not math.isfinite(start) or not math.isfinite(end) or end < start:
            continue
        out.append({"level": str(s.get("level", "")), "label": str(s.get("label", "")), "start_sec": start, "end_sec": end})
    return out


def assign_workflow_labels(df: pd.DataFrame, annotation_root: Optional[Path], time_col: str) -> pd.DataFrame:
    df = df.copy()
    for level in ["Level-0", "Level-1", "Level-2"]:
        df[f"workflow_{level.lower().replace('-', '')}_label"] = ""
    if annotation_root is None:
        return df
    if time_col not in df.columns:
        print(f"[WARN] time column '{time_col}' not found; workflow labels will be blank.")
        return df
    for case_id, idx in df.groupby("case_id").groups.items():
        ann = find_annotation_json(annotation_root, str(case_id))
        if ann is None:
            print(f"[WARN] no annotation JSON found for {case_id}")
            continue
        try:
            segments = load_surgcap_segments(ann)
        except Exception as exc:
            print(f"[WARN] failed to read annotation for {case_id}: {ann} ({exc})")
            continue
        t = pd.to_numeric(df.loc[idx, time_col], errors="coerce")
        for s in segments:
            col = f"workflow_{s['level'].lower().replace('-', '')}_label"
            if col not in df.columns:
                continue
            mask = (t >= s["start_sec"]) & (t <= s["end_sec"])
            if mask.any():
                df.loc[t.index[mask], col] = s["label"]
        print(f"[INFO] assigned workflow labels for {case_id}: {ann.name}")
    return df


def component_by_col() -> Dict[str, HazardComponent]:
    return {c.score_col: c for c in COMPONENTS}


def selected_score_cols(args: argparse.Namespace) -> List[str]:
    cols = list(args.score_col) if args.score_col else list(PROFILE_COMPONENTS[args.component_profile])
    # Keep order while dropping duplicates.
    seen = set()
    out = []
    for c in cols:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def load_cutoffs(cutoff_csv: Path, df: pd.DataFrame, score_cols: Sequence[str], thresholds: Sequence[str]) -> pd.DataFrame:
    if cutoff_csv.exists():
        cut = pd.read_csv(cutoff_csv)
        needed = cut[cut["score_col"].isin(score_cols) & cut["quantile_name"].isin(thresholds)].copy()
        if not needed.empty:
            return needed
        print(f"[WARN] cutoff CSV did not contain requested score_col/thresholds: {cutoff_csv}; recomputing from data.")
    else:
        print(f"[WARN] cutoff CSV not found: {cutoff_csv}; recomputing from data.")

    rows = []
    for col in score_cols:
        if col not in df.columns:
            continue
        x = pd.to_numeric(df[col], errors="coerce").dropna()
        for name in thresholds:
            if not name.startswith("p"):
                raise ValueError(f"Cannot recompute threshold '{name}'. Use names like p95 or provide cutoff CSV.")
            pct = float(name[1:].replace("p", ".")) / 100.0
            rows.append({
                "component": component_by_col().get(col, HazardComponent(col, col, "custom", "custom")).component,
                "score_col": col,
                "tier": component_by_col().get(col, HazardComponent(col, col, "custom", "custom")).tier,
                "threshold_scope": "global_recomputed",
                "quantile_name": name,
                "threshold_value": float(x.quantile(pct)) if len(x) else np.nan,
                "n_frames": int(len(x)),
            })
    return pd.DataFrame(rows)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_")


def sample_interval_by_case(df: pd.DataFrame, time_col: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if time_col not in df.columns:
        return {str(c): 1.0 for c in df["case_id"].unique()}
    for case_id, g in df.groupby("case_id"):
        t = pd.to_numeric(g[time_col], errors="coerce").dropna().sort_values().to_numpy()
        if len(t) >= 2:
            diffs = np.diff(t)
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            out[str(case_id)] = float(np.median(diffs)) if len(diffs) else 1.0
        else:
            out[str(case_id)] = 1.0
    return out


def max_consecutive_seconds(flags: pd.Series, sample_interval: float) -> float:
    arr = flags.fillna(False).astype(bool).to_numpy()
    best = 0
    cur = 0
    for flag in arr:
        if flag:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return float(best * sample_interval)


def add_hazard_flags(df: pd.DataFrame, score_cols: Sequence[str], cutoffs: pd.DataFrame, thresholds: Sequence[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    used_rows = []
    lookup = {(r["score_col"], r["quantile_name"]): float(r["threshold_value"]) for _, r in cutoffs.iterrows()}
    for q in thresholds:
        component_flag_cols = []
        comp_names = []
        for col in score_cols:
            if col not in df.columns:
                print(f"[WARN] score column missing: {col}")
                continue
            thr = lookup.get((col, q), np.nan)
            if not np.isfinite(thr):
                print(f"[WARN] threshold missing for {col} {q}")
                continue
            comp = component_by_col().get(col, HazardComponent(col, col, "custom", "custom"))
            flag_col = f"hazard_ge_{safe_name(comp.component)}_{q}"
            df[flag_col] = pd.to_numeric(df[col], errors="coerce") >= thr
            component_flag_cols.append(flag_col)
            comp_names.append(comp.component)
            used_rows.append({
                "threshold_name": q,
                "component": comp.component,
                "score_col": col,
                "threshold_value": thr,
                "tier": comp.tier,
                "role": comp.role,
            })
        any_col = f"visual_hazard_any_{q}"
        count_col = f"visual_hazard_component_count_{q}"
        components_col = f"visual_hazard_components_{q}"
        if component_flag_cols:
            flags = df[component_flag_cols].fillna(False).astype(bool)
            df[any_col] = flags.any(axis=1)
            df[count_col] = flags.sum(axis=1).astype(int)
            labels = []
            for _, row in flags.iterrows():
                labels.append(";".join([name for name, val in zip(comp_names, row.to_list()) if bool(val)]))
            df[components_col] = labels
        else:
            df[any_col] = False
            df[count_col] = 0
            df[components_col] = ""
        problem = pd.Series(False, index=df.index)
        if "image_validity_problem_candidate_v1" in df.columns:
            problem = pd.to_numeric(df["image_validity_problem_candidate_v1"], errors="coerce").fillna(0) >= 0.5
        df[f"clean_reference_candidate_{q}"] = (~df[any_col].astype(bool)) & (~problem)
    return df, pd.DataFrame(used_rows)


def summarize_case(df: pd.DataFrame, score_cols: Sequence[str], thresholds: Sequence[str], interval_map: Dict[str, float]) -> pd.DataFrame:
    rows = []
    for case_id, g in df.groupby("case_id"):
        dt = interval_map.get(str(case_id), 1.0)
        row = {"case_id": case_id, "n_frames": int(len(g)), "estimated_duration_sec": float(len(g) * dt), "sample_interval_sec": dt}
        for q in thresholds:
            any_col = f"visual_hazard_any_{q}"
            clean_col = f"clean_reference_candidate_{q}"
            flags = g[any_col].fillna(False).astype(bool)
            row[f"frac_visual_hazard_any_{q}"] = float(flags.mean()) if len(flags) else np.nan
            row[f"seconds_visual_hazard_any_{q}"] = float(flags.sum() * dt)
            row[f"max_consecutive_seconds_visual_hazard_any_{q}"] = max_consecutive_seconds(flags, dt)
            clean = g[clean_col].fillna(False).astype(bool) if clean_col in g.columns else ~flags
            row[f"frac_clean_reference_candidate_{q}"] = float(clean.mean()) if len(clean) else np.nan
            row[f"seconds_clean_reference_candidate_{q}"] = float(clean.sum() * dt)
            count_col = f"visual_hazard_component_count_{q}"
            row[f"mean_hazard_component_count_{q}"] = float(pd.to_numeric(g[count_col], errors="coerce").mean()) if count_col in g.columns else np.nan
            for col in score_cols:
                comp = component_by_col().get(col, HazardComponent(col, col, "custom", "custom"))
                flag_col = f"hazard_ge_{safe_name(comp.component)}_{q}"
                if flag_col in g.columns:
                    cflags = g[flag_col].fillna(False).astype(bool)
                    row[f"frac_{safe_name(comp.component)}_ge_{q}"] = float(cflags.mean()) if len(cflags) else np.nan
                    row[f"seconds_{safe_name(comp.component)}_ge_{q}"] = float(cflags.sum() * dt)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_case_phase(df: pd.DataFrame, score_cols: Sequence[str], thresholds: Sequence[str], interval_map: Dict[str, float], phase_levels: Sequence[str]) -> pd.DataFrame:
    rows = []
    for level in phase_levels:
        label_col = f"workflow_{level.lower().replace('-', '')}_label"
        if label_col not in df.columns:
            continue
        tmp = df.copy()
        tmp["_phase_label"] = tmp[label_col].replace("", "NoLabel").fillna("NoLabel")
        for (case_id, phase_label), g in tmp.groupby(["case_id", "_phase_label"], dropna=False):
            dt = interval_map.get(str(case_id), 1.0)
            row = {"case_id": case_id, "phase_level": level, "phase_label": phase_label, "n_frames": int(len(g)), "estimated_duration_sec": float(len(g) * dt), "sample_interval_sec": dt}
            for q in thresholds:
                any_col = f"visual_hazard_any_{q}"
                clean_col = f"clean_reference_candidate_{q}"
                flags = g[any_col].fillna(False).astype(bool)
                row[f"frac_visual_hazard_any_{q}"] = float(flags.mean()) if len(flags) else np.nan
                row[f"seconds_visual_hazard_any_{q}"] = float(flags.sum() * dt)
                row[f"max_consecutive_seconds_visual_hazard_any_{q}"] = max_consecutive_seconds(flags, dt)
                clean = g[clean_col].fillna(False).astype(bool) if clean_col in g.columns else ~flags
                row[f"frac_clean_reference_candidate_{q}"] = float(clean.mean()) if len(clean) else np.nan
                row[f"seconds_clean_reference_candidate_{q}"] = float(clean.sum() * dt)
                for col in score_cols:
                    comp = component_by_col().get(col, HazardComponent(col, col, "custom", "custom"))
                    flag_col = f"hazard_ge_{safe_name(comp.component)}_{q}"
                    if flag_col in g.columns:
                        cflags = g[flag_col].fillna(False).astype(bool)
                        row[f"frac_{safe_name(comp.component)}_ge_{q}"] = float(cflags.mean()) if len(cflags) else np.nan
                        row[f"seconds_{safe_name(comp.component)}_ge_{q}"] = float(cflags.sum() * dt)
            rows.append(row)
    return pd.DataFrame(rows)


def build_component_overlap(df: pd.DataFrame, score_cols: Sequence[str], thresholds: Sequence[str]) -> pd.DataFrame:
    rows = []
    comps = [(component_by_col().get(c, HazardComponent(c, c, "custom", "custom")).component, c) for c in score_cols]
    for q in thresholds:
        for i, (name_a, col_a) in enumerate(comps):
            flag_a = f"hazard_ge_{safe_name(name_a)}_{q}"
            if flag_a not in df.columns:
                continue
            a = df[flag_a].fillna(False).astype(bool)
            for name_b, col_b in comps[i:]:
                flag_b = f"hazard_ge_{safe_name(name_b)}_{q}"
                if flag_b not in df.columns:
                    continue
                b = df[flag_b].fillna(False).astype(bool)
                inter = int((a & b).sum())
                union = int((a | b).sum())
                rows.append({
                    "threshold_name": q,
                    "component_a": name_a,
                    "component_b": name_b,
                    "n_a": int(a.sum()),
                    "n_b": int(b.sum()),
                    "n_intersection": inter,
                    "n_union": union,
                    "jaccard": float(inter / union) if union else np.nan,
                    "conditional_b_given_a": float(inter / a.sum()) if a.sum() else np.nan,
                    "conditional_a_given_b": float(inter / b.sum()) if b.sum() else np.nan,
                })
    return pd.DataFrame(rows)


def get_value(row: pd.Series, col: str, default=""):
    return row[col] if col in row.index else default


def frame_index_value(row: pd.Series):
    for col in ["frame_index", "frame_idx", "frame_id", "frame_no"]:
        if col in row.index:
            return row[col]
    return ""


def stable_review_id(row: pd.Series, target_component: str, selection_type: str, version: str, rank: int) -> str:
    key = "|".join([version, str(row.get("case_id", "")), str(row.get("sample_time_sec", row.get("frame_index", ""))), str(row.get("image_path", "")), target_component, selection_type, str(rank)])
    return f"RVW_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]}"


def select_top_with_case_cap(df: pd.DataFrame, score_col: str, n: int, per_case_cap: int, ascending: bool = False) -> pd.DataFrame:
    if n <= 0 or score_col not in df.columns or df.empty:
        return df.iloc[0:0].copy()
    tmp = df[np.isfinite(pd.to_numeric(df[score_col], errors="coerce"))].copy()
    tmp[score_col] = pd.to_numeric(tmp[score_col], errors="coerce")
    tmp = tmp.sort_values(score_col, ascending=ascending)
    selected = []
    counts: Dict[str, int] = {}
    for idx, row in tmp.iterrows():
        case_id = str(row.get("case_id", ""))
        if counts.get(case_id, 0) >= per_case_cap:
            continue
        selected.append(idx)
        counts[case_id] = counts.get(case_id, 0) + 1
        if len(selected) >= n:
            break
    return tmp.loc[selected].copy()


def make_review_row(row: pd.Series, version: str, target_component: str, selection_type: str, score_col: str, score_value: float, rank: int, reason: str) -> dict:
    out = {
        "review_id": stable_review_id(row, target_component, selection_type, version, rank),
        "review_set_version": version,
        "case_id": get_value(row, "case_id"),
        "sample_time_sec": get_value(row, "sample_time_sec"),
        "frame_index": frame_index_value(row),
        "image_path": get_value(row, "image_path"),
        "roi_x0": get_value(row, "roi_x0"),
        "roi_y0": get_value(row, "roi_y0"),
        "roi_x1": get_value(row, "roi_x1"),
        "roi_y1": get_value(row, "roi_y1"),
        "target_component": target_component,
        "candidate_label": f"candidate_{target_component}_{selection_type}",
        "selection_type": selection_type,
        "source_score_col": score_col,
        "source_score_value": score_value,
        "source_rank_within_score": rank,
        "selection_reason": reason,
        "metric_status": get_value(row, "metric_status"),
        "component_interpretation": "Visual-hazard gate audit candidate.",
        "manual_include": "",
        "manual_primary_label": "",
        "manual_notes": "",
    }
    for col in VALIDITY_FLAG_COLUMNS:
        out[col] = get_value(row, col)
    return out


def build_audit_csv(df: pd.DataFrame, score_cols: Sequence[str], threshold_name: str, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    # Per-component high candidates among threshold-positive frames.
    for col in score_cols:
        comp = component_by_col().get(col, HazardComponent(col, col, "custom", "custom"))
        flag_col = f"hazard_ge_{safe_name(comp.component)}_{threshold_name}"
        if flag_col not in df.columns:
            continue
        candidates = df[df[flag_col].fillna(False).astype(bool)].copy()
        selected = select_top_with_case_cap(candidates, col, args.audit_per_component_n, args.per_case_cap, ascending=False)
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            rows.append(make_review_row(row, args.review_set_version, comp.component, f"hazard_ge_{threshold_name}", col, float(row[col]), rank, f"auto_hazard_ge_{threshold_name}_by_{col}"))
    # Any-hazard top candidates: rank by count, then max normalized score approximately using component count only.
    any_col = f"visual_hazard_any_{threshold_name}"
    count_col = f"visual_hazard_component_count_{threshold_name}"
    if any_col in df.columns:
        tmp = df[df[any_col].fillna(False).astype(bool)].copy()
        if count_col in tmp.columns:
            tmp["_any_score"] = pd.to_numeric(tmp[count_col], errors="coerce")
        else:
            tmp["_any_score"] = 1
        selected = select_top_with_case_cap(tmp, "_any_score", args.audit_per_component_n, args.per_case_cap, ascending=False)
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            rows.append(make_review_row(row, args.review_set_version, "visual_hazard_any", f"hazard_ge_{threshold_name}", count_col if count_col in row.index else "visual_hazard_any", float(row.get("_any_score", 1)), rank, f"auto_any_hazard_ge_{threshold_name}"))
    # Clean reference candidates.
    clean_col = f"clean_reference_candidate_{threshold_name}"
    if clean_col in df.columns:
        clean = df[df[clean_col].fillna(False).astype(bool)].copy()
        # Prefer middle of the dataset rather than top/bottom by any particular score.
        if args.time_col in clean.columns:
            clean = clean.sort_values(["case_id", args.time_col])
        selected = select_top_with_case_cap(clean.assign(_clean_score=0.0), "_clean_score", args.audit_clean_n, args.per_case_cap, ascending=True)
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            rows.append(make_review_row(row, args.review_set_version, "visual_hazard_any", f"clean_reference_{threshold_name}", "clean_reference_candidate", 0.0, rank, f"auto_clean_reference_not_hazard_ge_{threshold_name}"))
    return pd.DataFrame(rows, columns=REVIEW_CORE_COLUMNS)


def main() -> None:
    args = parse_args()
    case_filter = set(args.case) if args.case else None
    score_cols = selected_score_cols(args)
    df = load_metric_frames(args.metrics_dir, case_filter)
    df = assign_workflow_labels(df, args.annotation_root, args.time_col)
    print(f"Loaded frames: {len(df)}")
    print(f"Cases: {df['case_id'].nunique()}")
    print(f"Component profile: {args.component_profile}")
    print("Score columns:", ", ".join(score_cols))
    print("Thresholds:", ", ".join(args.threshold))

    cutoffs = load_cutoffs(args.cutoff_csv, df, score_cols, args.threshold)
    flagged, used_thresholds = add_hazard_flags(df, score_cols, cutoffs, args.threshold)
    interval_map = sample_interval_by_case(flagged, args.time_col)

    case_summary = summarize_case(flagged, score_cols, args.threshold, interval_map)
    case_phase_summary = summarize_case_phase(flagged, score_cols, args.threshold, interval_map, args.phase_level)
    overlap = build_component_overlap(flagged, score_cols, args.threshold)

    top_rows = []
    for q in args.threshold:
        sec_col = f"seconds_visual_hazard_any_{q}"
        frac_col = f"frac_visual_hazard_any_{q}"
        if sec_col in case_summary.columns:
            tmp = case_summary.sort_values(sec_col, ascending=False).head(30).copy()
            tmp["rank_basis"] = sec_col
            tmp["threshold_name"] = q
            top_rows.append(tmp)
        if frac_col in case_summary.columns:
            tmp = case_summary.sort_values(frac_col, ascending=False).head(30).copy()
            tmp["rank_basis"] = frac_col
            tmp["threshold_name"] = q
            top_rows.append(tmp)
    top_cases = pd.concat(top_rows, ignore_index=True, sort=False) if top_rows else pd.DataFrame()

    audit_df = build_audit_csv(flagged, score_cols, args.audit_threshold, args)

    if args.dry_run:
        print(used_thresholds.to_string(index=False))
        print(case_summary.head().to_string(index=False))
        print(audit_df.groupby(["target_component", "selection_type"]).size().to_string() if not audit_df.empty else "No audit rows")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    used_thresholds.to_csv(args.output_dir / "visual_hazard_thresholds_used.csv", index=False)
    case_summary.to_csv(args.output_dir / "case_visual_hazard_burden_summary.csv", index=False)
    case_phase_summary.to_csv(args.output_dir / "case_phase_visual_hazard_burden_summary.csv", index=False)
    overlap.to_csv(args.output_dir / "component_hazard_overlap_summary.csv", index=False)
    top_cases.to_csv(args.output_dir / "top_visual_hazard_cases.csv", index=False)
    if args.write_frame_flags:
        keep_cols = [
            "case_id",
            args.time_col,
            "image_path",
            "roi_x0",
            "roi_y0",
            "roi_x1",
            "roi_y1",
            *score_cols,
        ]
        keep_cols += [c for c in flagged.columns if c.startswith("hazard_ge_") or c.startswith("visual_hazard_") or c.startswith("clean_reference_candidate_")]
        keep_cols += [c for c in flagged.columns if c.startswith("workflow_level")]
        keep_cols = [c for c in keep_cols if c in flagged.columns]
        flagged[keep_cols].to_csv(args.output_dir / "visual_hazard_frame_flags.csv", index=False)

    args.audit_csv.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(args.audit_csv, index=False)

    print(f"[OK] wrote {args.output_dir / 'visual_hazard_thresholds_used.csv'} rows={len(used_thresholds)}")
    print(f"[OK] wrote {args.output_dir / 'case_visual_hazard_burden_summary.csv'} rows={len(case_summary)}")
    print(f"[OK] wrote {args.output_dir / 'case_phase_visual_hazard_burden_summary.csv'} rows={len(case_phase_summary)}")
    print(f"[OK] wrote {args.output_dir / 'component_hazard_overlap_summary.csv'} rows={len(overlap)}")
    print(f"[OK] wrote {args.output_dir / 'top_visual_hazard_cases.csv'} rows={len(top_cases)}")
    if args.write_frame_flags:
        print(f"[OK] wrote {args.output_dir / 'visual_hazard_frame_flags.csv'} rows={len(flagged)}")
    print(f"[OK] wrote {args.audit_csv} rows={len(audit_df)}")
    if not audit_df.empty:
        print(audit_df.groupby(["target_component", "selection_type"]).size().to_string())


if __name__ == "__main__":
    main()
