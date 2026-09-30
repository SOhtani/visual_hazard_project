#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations
import glob as _glob_module

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_GLOB = r"C:\Users\SOhtani2024\SurgCap\surgcap-project\data\raw\videos\*_annotation.json"
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export all OutsideBody segments from annotation JSONs and attach Level-1 context."
    )
    parser.add_argument(
        "--json-glob",
        type=str,
        default=DEFAULT_JSON_GLOB,
        help=f"Glob for annotation JSON files. Default: {DEFAULT_JSON_GLOB}",
    )
    parser.add_argument(
        "--out-events-csv",
        type=Path,
        default=ANALYSIS_DIR / "oob_segments_with_level1_context.csv",
        help="Output OOB event CSV with context.",
    )
    parser.add_argument(
        "--out-phase-features-csv",
        type=Path,
        default=ANALYSIS_DIR / "level1_phase_oob_case_features.csv",
        help="Output case x Level-1 feature CSV.",
    )
    parser.add_argument(
        "--oob-label",
        type=str,
        default="OutsideBody",
        help="Level-0 OOB label. Default: OutsideBody",
    )
    parser.add_argument(
        "--level1-name",
        type=str,
        default="Level-1",
        help="Name of Level-1 segments. Default: Level-1",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite outputs.",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not intervals:
        return []
    xs = sorted((float(a), float(b)) if a <= b else (float(b), float(a)) for a, b in intervals)
    merged: List[List[float]] = [[xs[0][0], xs[0][1]]]
    for a, b in xs[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def interval_total_sec(intervals: List[Tuple[float, float]]) -> float:
    return float(sum(max(0.0, b - a) for a, b in merge_intervals(intervals)))


def nearest_prev_level1(level1_df: pd.DataFrame, t: float) -> Tuple[str, float]:
    if len(level1_df) == 0:
        return "", np.nan

    active = level1_df.loc[(level1_df["start_sec"] <= t) & (level1_df["end_sec"] >= t)].copy()
    if len(active) > 0:
        active = active.sort_values(["start_sec", "end_sec"], ascending=[False, False])
        row = active.iloc[0]
        return str(row["label"]), 0.0

    prev_df = level1_df.loc[level1_df["end_sec"] <= t].copy()
    if len(prev_df) == 0:
        return "", np.nan

    prev_df["gap_sec"] = t - prev_df["end_sec"]
    prev_df = prev_df.sort_values(["end_sec", "start_sec"], ascending=[False, False])
    row = prev_df.iloc[0]
    return str(row["label"]), float(row["gap_sec"])


def nearest_post_level1(level1_df: pd.DataFrame, t: float) -> Tuple[str, float]:
    if len(level1_df) == 0:
        return "", np.nan

    active = level1_df.loc[(level1_df["start_sec"] <= t) & (level1_df["end_sec"] >= t)].copy()
    if len(active) > 0:
        active = active.sort_values(["start_sec", "end_sec"], ascending=[True, True])
        row = active.iloc[0]
        return str(row["label"]), 0.0

    post_df = level1_df.loc[level1_df["start_sec"] >= t].copy()
    if len(post_df) == 0:
        return "", np.nan

    post_df["gap_sec"] = post_df["start_sec"] - t
    post_df = post_df.sort_values(["start_sec", "end_sec"], ascending=[True, True])
    row = post_df.iloc[0]
    return str(row["label"]), float(row["gap_sec"])


def load_json(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_case_id(path: Path) -> str:
    name = path.stem
    if name.endswith("_annotation"):
        return name[:-11]
    return name


def main() -> None:
    args = parse_args()

    out_events = args.out_events_csv
    out_phase = args.out_phase_features_csv

    for p in [out_events, out_phase]:
        if p.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {p}. Use --overwrite to replace it.")

    json_paths = sorted(Path(p) for p in _glob_module.glob(args.json_glob))
    if not json_paths:
        json_paths = sorted(Path().anchor and [] or [])
    # robust glob from absolute pattern
    if not json_paths:
        import glob
        json_paths = [Path(x) for x in sorted(glob.glob(args.json_glob))]

    if not json_paths:
        raise FileNotFoundError(f"No JSON files matched: {args.json_glob}")

    all_event_rows: List[Dict[str, object]] = []
    phase_duration_rows: List[Dict[str, object]] = []
    all_level1_labels: set[str] = set()
    case_ids: List[str] = []

    for jp in json_paths:
        data = load_json(jp)
        case_id = json_case_id(jp)
        case_ids.append(case_id)

        segs = data.get("segments", [])
        duration_sec = float(data.get("duration_sec", np.nan))

        level1_rows: List[Dict[str, object]] = []
        oob_rows: List[Dict[str, object]] = []

        for s in segs:
            level = str(s.get("level", ""))
            label = str(s.get("label", ""))
            start_sec = s.get("start_sec", None)
            end_sec = s.get("end_sec", None)

            if start_sec is None or end_sec is None:
                continue

            try:
                start_sec = float(start_sec)
                end_sec = float(end_sec)
            except Exception:
                continue

            if end_sec < start_sec:
                start_sec, end_sec = end_sec, start_sec

            if level == args.level1_name:
                level1_rows.append({
                    "case_id": case_id,
                    "label": label,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                })
                all_level1_labels.add(label)

            if label == args.oob_label:
                oob_rows.append({
                    "case_id": case_id,
                    "oob_start_sec": start_sec,
                    "oob_end_sec": end_sec,
                    "oob_duration_sec": float(end_sec - start_sec),
                    "oob_label": label,
                    "oob_level": level,
                })

        level1_df = pd.DataFrame(level1_rows)
        if len(level1_df) > 0:
            level1_df = level1_df.sort_values(["start_sec", "end_sec"]).reset_index(drop=True)

        # phase duration by label (union within label)
        if len(level1_df) > 0:
            for lab, sdf in level1_df.groupby("label", sort=True):
                intervals = list(zip(pd.to_numeric(sdf["start_sec"], errors="coerce"),
                                     pd.to_numeric(sdf["end_sec"], errors="coerce")))
                phase_total_sec = interval_total_sec(intervals)
                phase_duration_rows.append({
                    "case_id": case_id,
                    "level1_label": str(lab),
                    "phase_total_sec": phase_total_sec,
                    "phase_total_min": phase_total_sec / 60.0,
                    "case_duration_sec": duration_sec,
                    "phase_total_ratio_of_case": (
                        phase_total_sec / duration_sec if np.isfinite(duration_sec) and duration_sec > 0 else np.nan
                    ),
                })

        # OOB events with context
        for i, row in enumerate(sorted(oob_rows, key=lambda r: (r["oob_start_sec"], r["oob_end_sec"])), start=1):
            start_sec = float(row["oob_start_sec"])
            end_sec = float(row["oob_end_sec"])

            prev_label, prev_gap_sec = nearest_prev_level1(level1_df, start_sec) if len(level1_df) > 0 else ("", np.nan)
            post_label, post_gap_sec = nearest_post_level1(level1_df, end_sec) if len(level1_df) > 0 else ("", np.nan)

            primary_label = prev_label if prev_label else post_label
            context_pair = f"{prev_label if prev_label else 'NA'}->{post_label if post_label else 'NA'}"
            same_phase_context = bool(prev_label != "" and prev_label == post_label)

            all_event_rows.append({
                "event_id_within_case": i,
                "case_id": case_id,
                "json_path": str(jp),
                "oob_start_sec": start_sec,
                "oob_end_sec": end_sec,
                "oob_duration_sec": float(end_sec - start_sec),
                "prev_level1_label": prev_label,
                "post_level1_label": post_label,
                "primary_level1_label": primary_label,
                "context_pair": context_pair,
                "same_phase_context": same_phase_context,
                "prev_gap_sec": prev_gap_sec,
                "post_gap_sec": post_gap_sec,
                "case_duration_sec": duration_sec,
            })

    event_df = pd.DataFrame(all_event_rows).sort_values(["case_id", "oob_start_sec", "oob_end_sec"]).reset_index(drop=True)
    phase_duration_df = pd.DataFrame(phase_duration_rows)

    # Build case x label feature table
    global_labels = sorted(all_level1_labels)
    case_label_rows: List[Dict[str, object]] = []

    for case_id in sorted(set(case_ids)):
        case_events = event_df.loc[event_df["case_id"] == case_id].copy()
        case_phase = phase_duration_df.loc[phase_duration_df["case_id"] == case_id].copy()
        case_duration_sec = float(case_phase["case_duration_sec"].iloc[0]) if len(case_phase) > 0 else np.nan

        phase_map = {
            str(r["level1_label"]): float(r["phase_total_sec"])
            for _, r in case_phase.iterrows()
        }

        for lab in global_labels:
            phase_total_sec = float(phase_map.get(lab, 0.0))
            prev_mask = case_events["prev_level1_label"] == lab
            post_mask = case_events["post_level1_label"] == lab
            any_mask = prev_mask | post_mask
            same_mask = (case_events["prev_level1_label"] == lab) & (case_events["post_level1_label"] == lab)
            out_mask = (case_events["prev_level1_label"] == lab) & (case_events["post_level1_label"] != lab)
            in_mask = (case_events["prev_level1_label"] != lab) & (case_events["post_level1_label"] == lab)

            prev_n = int(prev_mask.sum())
            prev_oob_total_sec = float(pd.to_numeric(case_events.loc[prev_mask, "oob_duration_sec"], errors="coerce").sum()) if len(case_events) else 0.0
            post_n = int(post_mask.sum())
            post_oob_total_sec = float(pd.to_numeric(case_events.loc[post_mask, "oob_duration_sec"], errors="coerce").sum()) if len(case_events) else 0.0
            any_n = int(any_mask.sum())
            any_oob_total_sec = float(pd.to_numeric(case_events.loc[any_mask, "oob_duration_sec"], errors="coerce").sum()) if len(case_events) else 0.0

            row = {
                "case_id": case_id,
                "level1_label": lab,
                "case_duration_sec": case_duration_sec,
                "phase_total_sec": phase_total_sec,
                "phase_total_min": phase_total_sec / 60.0,
                "phase_total_ratio_of_case": (
                    phase_total_sec / case_duration_sec if np.isfinite(case_duration_sec) and case_duration_sec > 0 else np.nan
                ),

                "oob_n_events_prev": prev_n,
                "oob_total_sec_prev": prev_oob_total_sec,
                "oob_total_min_prev": prev_oob_total_sec / 60.0,
                "oob_events_per_hour_prev": (
                    prev_n / (phase_total_sec / 3600.0) if phase_total_sec > 0 else np.nan
                ),
                "oob_ratio_prev": (
                    prev_oob_total_sec / phase_total_sec if phase_total_sec > 0 else np.nan
                ),
                "mean_oob_duration_sec_prev": (
                    prev_oob_total_sec / prev_n if prev_n > 0 else np.nan
                ),

                "oob_n_events_post": post_n,
                "oob_total_sec_post": post_oob_total_sec,
                "oob_total_min_post": post_oob_total_sec / 60.0,
                "oob_events_per_hour_post": (
                    post_n / (phase_total_sec / 3600.0) if phase_total_sec > 0 else np.nan
                ),
                "oob_ratio_post": (
                    post_oob_total_sec / phase_total_sec if phase_total_sec > 0 else np.nan
                ),
                "mean_oob_duration_sec_post": (
                    post_oob_total_sec / post_n if post_n > 0 else np.nan
                ),

                "oob_n_events_any": any_n,
                "oob_total_sec_any": any_oob_total_sec,
                "oob_total_min_any": any_oob_total_sec / 60.0,
                "oob_events_per_hour_any": (
                    any_n / (phase_total_sec / 3600.0) if phase_total_sec > 0 else np.nan
                ),
                "oob_ratio_any": (
                    any_oob_total_sec / phase_total_sec if phase_total_sec > 0 else np.nan
                ),
                "mean_oob_duration_sec_any": (
                    any_oob_total_sec / any_n if any_n > 0 else np.nan
                ),

                "same_phase_return_count": int(same_mask.sum()),
                "transition_out_count": int(out_mask.sum()),
                "transition_in_count": int(in_mask.sum()),
            }
            case_label_rows.append(row)

    case_label_df = pd.DataFrame(case_label_rows).sort_values(["level1_label", "case_id"]).reset_index(drop=True)

    ensure_parent(out_events)
    ensure_parent(out_phase)
    event_df.to_csv(out_events, index=False, encoding="utf-8-sig")
    case_label_df.to_csv(out_phase, index=False, encoding="utf-8-sig")

    print("[OK] Exported all OOB segments with Level-1 context")
    print(f"[INFO] json_files={len(json_paths)}")
    print(f"[INFO] n_oob_events={len(event_df)}")
    print(f"[INFO] n_level1_labels={len(global_labels)}")
    print(f"[INFO] level1_labels={global_labels}")
    print(f"[INFO] events_csv={out_events}")
    print(f"[INFO] phase_features_csv={out_phase}")


if __name__ == "__main__":
    main()