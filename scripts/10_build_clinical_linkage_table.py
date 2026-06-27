#!/usr/bin/env python
"""Build case-level clinical linkage tables for visual hazard burden.

This script merges Phase 04 visual-hazard burden summaries with case-level
clinical/procedural metadata, then produces exploratory correlation and group
summary tables. It does not modify source data.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


TIER1_COMPONENT_KEYS = [
    "visual_hazard_any",
    "structural_visibility_loss",
    "center_low_structure_area",
    "whiteout",
    "low_light_or_blackout",
]

PRIMARY_BURDEN_COLS = [
    "seconds_visual_hazard_any_p95",
    "frac_visual_hazard_any_p95",
    "max_consecutive_seconds_visual_hazard_any_p95",
    "seconds_visual_hazard_any_p99",
    "frac_visual_hazard_any_p99",
    "max_consecutive_seconds_visual_hazard_any_p99",
]

CASE_COL_CANDIDATES = [
    "case_id",
    "case",
    "case_no",
    "case_number",
    "video_case",
    "surgcap_case",
]

PROCEDURE_GROUP_CANDIDATES = [
    "procedure_group",
    "procedure",
    "operation",
    "operation_name",
    "術式",
]

GROUP_COL_CANDIDATES = [
    "procedure_group",
    "procedure",
    "side",
    "target",
    "target_lobe",
    "target_segment",
    "lobe",
    "segment",
    "approach",
]

CLINICAL_KEYWORDS = [
    "operation_time",
    "operative_time",
    "op_time",
    "手術時間",
    "blood_loss",
    "bleeding",
    "出血",
    "drain",
    "chest_tube",
    "air_leak",
    "airleak",
    "leak",
    "hospital",
    "los",
    "在院",
    "complication",
    "合併症",
    "clavien",
    "ae",
]


def canonical_case_id(x) -> str | float:
    if pd.isna(x):
        return np.nan
    s = str(x).strip().upper()
    if not s:
        return np.nan
    m = re.search(r"CASE\s*0*(\d{1,3})", s)
    if m:
        return f"CASE{int(m.group(1)):03d}"
    if re.fullmatch(r"\d+(\.0)?", s):
        return f"CASE{int(float(s)):03d}"
    return s.replace(" ", "")


def norm_col(c: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")


def sanitize_col(c: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(c).strip()).strip("_")
    return s or "unknown"


def read_table(path: Path, sheet_name: str | int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    ext = path.suffix.lower()
    if ext in [".xlsx", ".xls", ".xlsm"]:
        if sheet_name is None:
            return pd.read_excel(path)
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path, low_memory=False)


def find_case_col(df: pd.DataFrame, explicit: str | None = None) -> str:
    if explicit:
        if explicit not in df.columns:
            raise ValueError(f"Requested case column not found: {explicit}")
        return explicit
    normalized = {norm_col(c): c for c in df.columns}
    for cand in CASE_COL_CANDIDATES:
        if cand in normalized:
            return normalized[cand]
    for c in df.columns:
        nc = norm_col(c)
        if "case" in nc or "症例" in str(c):
            return c
    raise ValueError("Could not auto-detect case column. Use --metadata-case-col or --burden-case-col.")


def coerce_numeric_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    # Remove common unit text while preserving signs/decimals.
    cleaned = (
        s.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("分", "", regex=False)
        .str.replace("ml", "", case=False, regex=False)
        .str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def numeric_columns(df: pd.DataFrame, exclude: Iterable[str] = ()) -> list[str]:
    exclude = set(exclude)
    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        v = coerce_numeric_series(df[c])
        if v.notna().sum() >= max(5, int(0.2 * len(df))) and v.nunique(dropna=True) > 1:
            cols.append(c)
    return cols


def select_hazard_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        nc = norm_col(c)
        if c == "case_id":
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if any(k in nc for k in ["visual_hazard", "whiteout", "low_light", "blackout", "structural", "center_low"]):
            if any(prefix in nc for prefix in ["seconds", "frac", "max_consecutive", "n_frames"]):
                cols.append(c)
    # Keep primary columns first, then remaining stable order.
    ordered = [c for c in PRIMARY_BURDEN_COLS if c in cols]
    ordered += [c for c in cols if c not in ordered]
    return ordered


def select_clinical_numeric_cols(df: pd.DataFrame, case_col: str) -> list[str]:
    nums = numeric_columns(df, exclude=[case_col, "case_id"])
    # Prioritize clinical-looking fields, but retain all numeric metadata for exploration.
    pri = []
    other = []
    for c in nums:
        nc = norm_col(c)
        raw = str(c).lower()
        if any(k.lower() in nc or k.lower() in raw for k in CLINICAL_KEYWORDS):
            pri.append(c)
        else:
            other.append(c)
    return pri + other


def spearman_corr(x: pd.Series, y: pd.Series) -> float:
    xr = x.rank(method="average")
    yr = y.rank(method="average")
    return float(xr.corr(yr))


def build_correlations(df: pd.DataFrame, clinical_cols: list[str], hazard_cols: list[str]) -> pd.DataFrame:
    rows = []
    for clinical_col in clinical_cols:
        cx = coerce_numeric_series(df[clinical_col])
        for hazard_col in hazard_cols:
            hy = pd.to_numeric(df[hazard_col], errors="coerce")
            tmp = pd.DataFrame({"clinical": cx, "hazard": hy}).dropna()
            if len(tmp) < 5 or tmp["clinical"].nunique() <= 1 or tmp["hazard"].nunique() <= 1:
                continue
            rows.append(
                {
                    "clinical_col": clinical_col,
                    "hazard_col": hazard_col,
                    "n": len(tmp),
                    "spearman_rho": spearman_corr(tmp["clinical"], tmp["hazard"]),
                    "clinical_median": float(tmp["clinical"].median()),
                    "hazard_median": float(tmp["hazard"].median()),
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("spearman_rho", key=lambda s: s.abs(), ascending=False)
    return out


def build_group_summary(df: pd.DataFrame, hazard_cols: list[str]) -> pd.DataFrame:
    rows = []
    candidate_cols = []
    normalized_map = {norm_col(c): c for c in df.columns}
    for cand in GROUP_COL_CANDIDATES:
        if cand in normalized_map:
            candidate_cols.append(normalized_map[cand])
    for c in df.columns:
        if c in candidate_cols or c == "case_id":
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        nunique = df[c].nunique(dropna=True)
        if 2 <= nunique <= 12:
            candidate_cols.append(c)
    # Deduplicate, preserving order.
    seen = set()
    group_cols = []
    for c in candidate_cols:
        if c not in seen:
            seen.add(c)
            group_cols.append(c)
    main_hazards = [c for c in PRIMARY_BURDEN_COLS if c in hazard_cols]
    if not main_hazards:
        main_hazards = hazard_cols[:6]
    for group_col in group_cols:
        gdf = df[[group_col] + main_hazards].copy()
        gdf[group_col] = gdf[group_col].astype(str).replace({"nan": np.nan})
        for val, sub in gdf.dropna(subset=[group_col]).groupby(group_col):
            row = {"group_col": group_col, "group_value": val, "n_cases": len(sub)}
            for h in main_hazards:
                v = pd.to_numeric(sub[h], errors="coerce")
                row[f"{h}__median"] = float(v.median()) if v.notna().any() else np.nan
                row[f"{h}__q25"] = float(v.quantile(0.25)) if v.notna().any() else np.nan
                row[f"{h}__q75"] = float(v.quantile(0.75)) if v.notna().any() else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def build_phase_wide(phase_df: pd.DataFrame) -> pd.DataFrame:
    if phase_df.empty:
        return pd.DataFrame()
    needed = ["case_id", "phase_level", "phase_label"]
    if any(c not in phase_df.columns for c in needed):
        return pd.DataFrame()
    df = phase_df[phase_df["phase_level"].astype(str).eq("Level-1")].copy()
    if df.empty:
        return pd.DataFrame()
    value_cols = [
        c
        for c in [
            "seconds_visual_hazard_any_p95",
            "frac_visual_hazard_any_p95",
            "max_consecutive_seconds_visual_hazard_any_p95",
            "seconds_visual_hazard_any_p99",
            "frac_visual_hazard_any_p99",
            "max_consecutive_seconds_visual_hazard_any_p99",
        ]
        if c in df.columns
    ]
    if not value_cols:
        return pd.DataFrame()
    frames = []
    for val_col in value_cols:
        piv = df.pivot_table(index="case_id", columns="phase_label", values=val_col, aggfunc="sum")
        piv.columns = [f"level1_{sanitize_col(str(c))}__{val_col}" for c in piv.columns]
        frames.append(piv)
    wide = pd.concat(frames, axis=1).reset_index()
    return wide


def main() -> None:
    ap = argparse.ArgumentParser(description="Build clinical linkage table for visual-hazard burden.")
    ap.add_argument("--burden-summary", type=Path, default=Path("reports/visual_hazard_burden/case_visual_hazard_burden_summary.csv"))
    ap.add_argument("--phase-burden-summary", type=Path, default=Path("reports/visual_hazard_burden/case_phase_visual_hazard_burden_summary.csv"))
    ap.add_argument("--metadata", type=Path, default=None, help="Case-level clinical/procedural metadata CSV/XLSX.")
    ap.add_argument("--metadata-sheet", default=None, help="Excel sheet name/index for metadata.")
    ap.add_argument("--burden-case-col", default=None)
    ap.add_argument("--metadata-case-col", default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("reports/clinical_linkage"))
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    burden = read_table(args.burden_summary)
    burden_case_col = find_case_col(burden, args.burden_case_col)
    burden = burden.copy()
    burden["case_id"] = burden[burden_case_col].map(canonical_case_id)

    hazard_cols = select_hazard_cols(burden)
    if not hazard_cols:
        raise ValueError("No hazard burden columns detected in burden summary.")

    phase_wide = pd.DataFrame()
    if args.phase_burden_summary and args.phase_burden_summary.exists():
        phase = read_table(args.phase_burden_summary)
        phase_case_col = find_case_col(phase, None)
        phase = phase.copy()
        phase["case_id"] = phase[phase_case_col].map(canonical_case_id)
        phase_wide = build_phase_wide(phase)
        if not phase_wide.empty:
            phase_wide.to_csv(args.output_dir / "level1_phase_burden_wide.csv", index=False)

    merged = burden.copy()
    metadata_cols = []
    clinical_numeric_cols = []
    if args.metadata is not None:
        sheet = args.metadata_sheet
        if sheet is not None and str(sheet).isdigit():
            sheet = int(sheet)
        meta = read_table(args.metadata, sheet)
        meta_case_col = find_case_col(meta, args.metadata_case_col)
        meta = meta.copy()
        meta["case_id"] = meta[meta_case_col].map(canonical_case_id)
        # Avoid duplicate non-key columns by suffixing metadata columns.
        metadata_cols = [c for c in meta.columns if c != "case_id"]
        merged = burden.merge(meta, on="case_id", how="left", suffixes=("", "__metadata"))
        clinical_numeric_cols = select_clinical_numeric_cols(merged, case_col="case_id")
        pd.DataFrame(
            [
                {"source": "burden", "case_col": burden_case_col, "n_cases": burden["case_id"].nunique()},
                {"source": "metadata", "case_col": meta_case_col, "n_cases": meta["case_id"].nunique()},
                {"source": "merged", "case_col": "case_id", "n_cases": merged["case_id"].nunique()},
            ]
        ).to_csv(args.output_dir / "case_id_merge_audit.csv", index=False)
    else:
        pd.DataFrame(
            [{"source": "burden", "case_col": burden_case_col, "n_cases": burden["case_id"].nunique()}]
        ).to_csv(args.output_dir / "case_id_merge_audit.csv", index=False)

    if not phase_wide.empty:
        merged = merged.merge(phase_wide, on="case_id", how="left")

    merged.to_csv(args.output_dir / "case_visual_hazard_clinical_linkage.csv", index=False)

    pd.DataFrame(
        {
            "hazard_col": hazard_cols,
            "role": ["primary_candidate" if c in PRIMARY_BURDEN_COLS else "component_or_auxiliary" for c in hazard_cols],
        }
    ).to_csv(args.output_dir / "hazard_column_inventory.csv", index=False)

    if clinical_numeric_cols:
        pd.DataFrame({"clinical_numeric_col": clinical_numeric_cols}).to_csv(
            args.output_dir / "clinical_numeric_column_inventory.csv", index=False
        )
        corr = build_correlations(merged, clinical_numeric_cols, hazard_cols)
        corr.to_csv(args.output_dir / "numeric_spearman_correlations.csv", index=False)
    else:
        pd.DataFrame(columns=["clinical_numeric_col"]).to_csv(
            args.output_dir / "clinical_numeric_column_inventory.csv", index=False
        )
        pd.DataFrame(columns=["clinical_col", "hazard_col", "n", "spearman_rho"]).to_csv(
            args.output_dir / "numeric_spearman_correlations.csv", index=False
        )

    group_summary = build_group_summary(merged, hazard_cols)
    group_summary.to_csv(args.output_dir / "group_burden_summary.csv", index=False)

    # Compact top-case tables for the main burden metrics.
    top_rows = []
    for h in [c for c in PRIMARY_BURDEN_COLS if c in merged.columns]:
        top = merged[["case_id", h]].dropna().sort_values(h, ascending=False).head(20)
        for rank, (_, row) in enumerate(top.iterrows(), start=1):
            top_rows.append({"hazard_col": h, "rank": rank, "case_id": row["case_id"], "value": row[h]})
    pd.DataFrame(top_rows).to_csv(args.output_dir / "top_cases_by_primary_burden_metrics.csv", index=False)

    print(f"[OK] wrote {args.output_dir / 'case_visual_hazard_clinical_linkage.csv'} rows={len(merged)}")
    print(f"[OK] hazard columns: {len(hazard_cols)}")
    if args.metadata is not None:
        print(f"[OK] metadata columns merged: {len(metadata_cols)}")
        print(f"[OK] numeric clinical columns detected: {len(clinical_numeric_cols)}")
    if not phase_wide.empty:
        print(f"[OK] level-1 phase burden wide columns: {len(phase_wide.columns) - 1}")


if __name__ == "__main__":
    main()
