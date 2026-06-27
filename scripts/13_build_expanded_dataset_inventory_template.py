#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build a preliminary 2021-2025 expanded surgical-video inventory.

This script is intentionally conservative. It scans one or more video roots,
infers rough approach/procedure candidates from filenames and parent folders,
and optionally merges a metadata CSV if a case_id-like column is available.

The output is a review-ready inventory, not a finalized research cohort.
No raw video files are copied.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "dataset_expansion_2021_2025"
VIDEO_EXTS = [".m2ts", ".mts", ".mp4", ".mov", ".avi", ".wmv", ".mpg", ".mpeg"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a preliminary expanded surgical-video inventory for 2021-2025.")
    parser.add_argument("--video-root", type=Path, nargs="+", required=True, help="One or more roots to scan for surgical videos.")
    parser.add_argument("--metadata-csv", type=Path, default=None, help="Optional metadata CSV to merge by case_id/original_case_id if available.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case-regex", default=r"CASE\d{3,}|RATS\d{4}_CASE\d{3,}|VATS\d{4}_CASE\d{3,}|OPEN\d{4}_CASE\d{3,}", help="Regex used to infer case IDs from paths.")
    parser.add_argument("--year-min", type=int, default=2021)
    parser.add_argument("--year-max", type=int, default=2025)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def infer_year(text: str) -> Optional[int]:
    years = [int(y) for y in re.findall(r"20\d{2}", text)]
    years = [y for y in years if 2000 <= y <= 2099]
    return years[0] if years else None


def infer_case_id(path: Path, regex: str) -> str:
    text = str(path)
    m = re.search(regex, text, flags=re.IGNORECASE)
    if m:
        return m.group(0).upper()
    # Fallback: use stem before first whitespace or extension-like suffix.
    stem = path.stem
    stem = re.sub(r"[_\- ]?(video|movie|surgery|operation|op)$", "", stem, flags=re.IGNORECASE)
    return stem


def infer_approach(path: Path) -> str:
    text = str(path).lower()
    if any(k in text for k in ["rats", "robot", "robotic", "da vinci", "davinci", "ロボット"]):
        return "RATS_candidate"
    if any(k in text for k in ["vats", "thoracoscopic", "scope", "胸腔鏡"]):
        return "VATS_candidate"
    if any(k in text for k in ["open", "thoracotomy", "開胸"]):
        return "open_candidate"
    return "unknown_approach"


def infer_procedure(path: Path) -> str:
    text = str(path).lower()
    if any(k in text for k in ["lobectomy", "lobe", "葉切", "肺葉切除"]):
        return "lobectomy_candidate"
    if any(k in text for k in ["segment", "segmentectomy", "区域", "区切"]):
        return "segmentectomy_candidate"
    if any(k in text for k in ["wedge", "partial", "部分切除", "部切"]):
        return "wedge_or_partial_candidate"
    if any(k in text for k in ["pneumonectomy", "全摘"]):
        return "pneumonectomy_candidate"
    return "unknown_procedure"


def scan_videos(roots: List[Path], case_regex: str, year_min: int, year_max: int) -> pd.DataFrame:
    rows = []
    seen = set()
    for root in roots:
        if not root.exists():
            print(f"[WARN] video root does not exist: {root}")
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            year = infer_year(str(path))
            in_year_range = (year is None) or (year_min <= year <= year_max)
            rows.append({
                "case_id_candidate": infer_case_id(path, case_regex),
                "year_candidate": year,
                "in_requested_year_range_or_unknown": bool(in_year_range),
                "approach_candidate": infer_approach(path),
                "procedure_candidate": infer_procedure(path),
                "video_path": str(path),
                "video_file_name": path.name,
                "video_ext": path.suffix.lower(),
                "parent_dir": str(path.parent),
                "file_size_bytes": path.stat().st_size,
            })
    return pd.DataFrame(rows)


def choose_metadata_case_col(meta: pd.DataFrame) -> Optional[str]:
    preferred = ["case_id", "original_case_id", "case_uid", "CASE", "Case", "症例ID"]
    for col in preferred:
        if col in meta.columns:
            return col
    for col in meta.columns:
        if "case" in col.lower():
            return col
    return None


def merge_metadata(inv: pd.DataFrame, metadata_csv: Optional[Path]) -> pd.DataFrame:
    if metadata_csv is None:
        inv["metadata_merge_status"] = "metadata_not_provided"
        return inv
    if not metadata_csv.exists():
        print(f"[WARN] metadata CSV does not exist: {metadata_csv}")
        inv["metadata_merge_status"] = "metadata_missing"
        return inv
    meta = pd.read_csv(metadata_csv, low_memory=False)
    col = choose_metadata_case_col(meta)
    if col is None:
        print("[WARN] no case-like column found in metadata; skipping merge")
        inv["metadata_merge_status"] = "no_case_column_in_metadata"
        return inv
    meta = meta.copy()
    meta["_merge_case_id"] = meta[col].astype(str).str.upper()
    inv = inv.copy()
    inv["_merge_case_id"] = inv["case_id_candidate"].astype(str).str.upper()
    merged = inv.merge(meta, on="_merge_case_id", how="left", suffixes=("", "__metadata"))
    merged["metadata_merge_status"] = merged[col].notna().map({True: "matched", False: "unmatched"}) if col in merged.columns else "merged"
    return merged.drop(columns=["_merge_case_id"], errors="ignore")


def make_summary(inv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in ["year_candidate", "approach_candidate", "procedure_candidate", "video_ext", "metadata_merge_status"]:
        if col not in inv.columns:
            continue
        s = inv[col].fillna("NA").value_counts(dropna=False).reset_index()
        s.columns = ["value", "n_videos"]
        s.insert(0, "summary_col", col)
        rows.append(s)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main() -> None:
    args = parse_args()
    inv = scan_videos(args.video_root, args.case_regex, args.year_min, args.year_max)
    inv = inv[inv["in_requested_year_range_or_unknown"]].copy() if not inv.empty else inv
    inv = merge_metadata(inv, args.metadata_csv)
    summary = make_summary(inv)

    print(f"[OK] scanned video roots: {len(args.video_root)}")
    print(f"[OK] video files found in requested range or unknown year: {len(inv)}")
    if not summary.empty:
        print(summary.to_string(index=False))

    if args.dry_run:
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    inv.to_csv(args.output_dir / "expanded_video_inventory_raw.csv", index=False)
    summary.to_csv(args.output_dir / "expanded_video_inventory_summary.csv", index=False)

    review_cols = [c for c in [
        "case_id_candidate",
        "year_candidate",
        "approach_candidate",
        "procedure_candidate",
        "metadata_merge_status",
        "video_file_name",
        "video_path",
    ] if c in inv.columns]
    inv[review_cols].to_csv(args.output_dir / "expanded_case_candidates_for_review.csv", index=False)
    print(f"[OK] wrote {args.output_dir / 'expanded_video_inventory_raw.csv'} rows={len(inv)}")
    print(f"[OK] wrote {args.output_dir / 'expanded_video_inventory_summary.csv'} rows={len(summary)}")
    print(f"[OK] wrote {args.output_dir / 'expanded_case_candidates_for_review.csv'} rows={len(inv)}")


if __name__ == "__main__":
    main()
