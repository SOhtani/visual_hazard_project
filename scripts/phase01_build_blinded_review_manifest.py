#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Create a blinded still-image review manifest for the Phase 01 pilot.

Inputs:
    reports/phase01_pilot_sampling/phase01_pilot_moments.csv

Outputs:
    data/annotations/phase01_pilot_review_manifest.csv
    data/derived/phase01_pilot_review/stills/V001.png ... V030.png
    reports/phase01_pilot_sampling/phase01_pilot_review_mapping.csv
    reports/phase01_pilot_sampling/phase01_pilot_review_manifest_audit.json

The reviewer-facing manifest contains only blinded review IDs, order, and
blinded image paths. Sampling strata and metric values remain only in the
internal mapping file.

By default, this script refuses to overwrite an existing manifest/mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MOMENTS_CSV = (
    PROJECT_ROOT
    / "reports"
    / "phase01_pilot_sampling"
    / "phase01_pilot_moments.csv"
)

DEFAULT_MANIFEST_CSV = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_pilot_review_manifest.csv"
)

DEFAULT_MAPPING_CSV = (
    PROJECT_ROOT
    / "reports"
    / "phase01_pilot_sampling"
    / "phase01_pilot_review_mapping.csv"
)

DEFAULT_AUDIT_JSON = (
    PROJECT_ROOT
    / "reports"
    / "phase01_pilot_sampling"
    / "phase01_pilot_review_manifest_audit.json"
)

DEFAULT_MEDIA_DIR = (
    PROJECT_ROOT
    / "data"
    / "derived"
    / "phase01_pilot_review"
    / "stills"
)

DEFAULT_RATINGS_CSV = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_pilot_still_ratings.csv"
)

DEFAULT_SEED = 20260917
EXPECTED_N = 30


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--moments-csv", type=Path, default=DEFAULT_MOMENTS_CSV)
    p.add_argument("--manifest-csv", type=Path, default=DEFAULT_MANIFEST_CSV)
    p.add_argument("--mapping-csv", type=Path, default=DEFAULT_MAPPING_CSV)
    p.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    p.add_argument("--media-dir", type=Path, default=DEFAULT_MEDIA_DIR)
    p.add_argument("--ratings-csv", type=Path, default=DEFAULT_RATINGS_CSV)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the blinded manifest/mapping/media if no ratings exist.",
    )
    return p.parse_args()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ratings_exist(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path)
        return len(df) > 0
    except Exception:
        return path.stat().st_size > 0


def ensure_can_write(
    outputs: list[Path],
    media_dir: Path,
    *,
    overwrite: bool,
    ratings_csv: Path,
) -> None:
    existing = [p for p in outputs if p.exists()]
    media_exists = media_dir.exists() and any(media_dir.iterdir())

    if not existing and not media_exists:
        return

    if not overwrite:
        items = [str(p) for p in existing]
        if media_exists:
            items.append(str(media_dir))
        raise SystemExit(
            "Blinded review materials already exist.\n"
            "Refusing to change the mapping.\n"
            "Existing:\n  - "
            + "\n  - ".join(items)
            + "\nUse --overwrite only if this is intentional and no ratings exist."
        )

    if ratings_exist(ratings_csv):
        raise SystemExit(
            f"Ratings already exist at {ratings_csv}.\n"
            "Refusing to overwrite the blinded mapping after annotation began."
        )


def main() -> None:
    args = parse_args()

    moments_csv = args.moments_csv.resolve()
    manifest_csv = args.manifest_csv.resolve()
    mapping_csv = args.mapping_csv.resolve()
    audit_json = args.audit_json.resolve()
    media_dir = args.media_dir.resolve()
    ratings_csv = args.ratings_csv.resolve()

    if not moments_csv.exists():
        raise FileNotFoundError(f"Missing pilot moments CSV: {moments_csv}")

    outputs = [manifest_csv, mapping_csv, audit_json]
    ensure_can_write(
        outputs,
        media_dir,
        overwrite=args.overwrite,
        ratings_csv=ratings_csv,
    )

    d = pd.read_csv(moments_csv, low_memory=False)

    required = [
        "moment_id",
        "case_id",
        "sample_time_sec",
        "selection_stratum",
        "selection_slot",
        "selection_metric",
        "selection_value",
        "selection_percentile_band",
        "image_path",
    ]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if len(d) != EXPECTED_N:
        raise ValueError(f"Expected {EXPECTED_N} moments, found {len(d)}")

    if d["moment_id"].duplicated().any():
        raise ValueError("Duplicate moment_id detected")

    missing_images = [
        str(p)
        for p in d["image_path"].astype(str)
        if not Path(p).exists()
    ]
    if missing_images:
        raise FileNotFoundError(
            "One or more selected images do not exist:\n  - "
            + "\n  - ".join(missing_images[:10])
        )

    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(len(d))
    r = d.iloc[perm].reset_index(drop=True).copy()

    r["review_order"] = np.arange(1, len(r) + 1, dtype=int)
    r["review_item_id"] = [
        f"V{i:03d}" for i in range(1, len(r) + 1)
    ]

    manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping_csv.parent.mkdir(parents=True, exist_ok=True)
    audit_json.parent.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    # If overwrite was explicitly requested, clear only blinded media files.
    if args.overwrite:
        for p in media_dir.glob("V*.*"):
            if p.is_file():
                p.unlink()

    blinded_paths = []
    source_hashes = []

    for _, row in r.iterrows():
        src = Path(str(row["image_path"]))
        suffix = src.suffix.lower() or ".png"
        dst = media_dir / f"{row['review_item_id']}{suffix}"
        shutil.copy2(src, dst)
        blinded_paths.append(str(dst))
        source_hashes.append(sha256_file(src))

    r["review_image_path"] = blinded_paths
    r["source_image_sha256"] = source_hashes

    reviewer_manifest = r[
        [
            "review_item_id",
            "review_order",
            "review_image_path",
        ]
    ].rename(columns={"review_image_path": "image_path"})

    reviewer_manifest.to_csv(manifest_csv, index=False)

    internal_cols = [
        "review_item_id",
        "review_order",
        "moment_id",
        "case_id",
        "sample_time_sec",
        "selection_stratum",
        "selection_slot",
        "selection_metric",
        "selection_value",
        "selection_percentile_band",
        "eligible_strata",
        "discordance_reason",
        "image_path",
        "review_image_path",
        "source_image_sha256",
    ]
    internal_cols = [c for c in internal_cols if c in r.columns]
    r[internal_cols].to_csv(mapping_csv, index=False)

    audit = {
        "source_moments_csv": str(moments_csv),
        "source_moments_sha256": sha256_file(moments_csv),
        "randomization_seed": int(args.seed),
        "n_items": int(len(r)),
        "manifest_csv": str(manifest_csv),
        "mapping_csv": str(mapping_csv),
        "media_dir": str(media_dir),
        "manifest_sha256": sha256_file(manifest_csv),
        "mapping_sha256": sha256_file(mapping_csv),
        "review_ids": r["review_item_id"].tolist(),
    }
    audit_json.write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    print("=== PHASE 01 BLINDED STILL REVIEW MANIFEST ===")
    print(f"items:          {len(r)}")
    print(f"seed:           {args.seed}")
    print(f"manifest:       {manifest_csv}")
    print(f"mapping:        {mapping_csv}")
    print(f"blinded stills: {media_dir}")
    print(f"audit:          {audit_json}")
    print()
    print("Reviewer-facing manifest columns:")
    print("  " + ", ".join(reviewer_manifest.columns))
    print()
    print("Mapping is frozen unless deliberately regenerated before ratings begin.")


if __name__ == "__main__":
    main()
