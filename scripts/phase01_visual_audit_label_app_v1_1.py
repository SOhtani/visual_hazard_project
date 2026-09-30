#!/usr/bin/env python
"""Streamlit app for blinded labeling of Phase-01 targeted visual-audit frames.

This app intentionally hides candidate stratum and metric values.
It writes a separate annotation CSV keyed only by audit_review_id.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "phase01_targeted_visual_audit" / "phase01_targeted_visual_audit_manifest.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "annotations" / "phase01_targeted_visual_audit_labels.csv"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "annotations" / "phase01_targeted_visual_audit_backups"

PHENOMENA = [
    ("blur", "Blur / defocus / motion blur", "technical"),
    ("smoke", "Smoke / airborne veil", "technical"),
    ("lens", "Lens contamination / lens fogging", "technical"),
    ("glare", "Glare / specular reflection", "technical"),
    ("whiteout", "Whiteout / overexposure", "technical"),
    ("underexposure", "Underexposure / blackout", "technical"),
    ("blood_fluid", "Blood / fluid", "field"),
    ("physical_obstruction", "Physical obstruction", "field"),
    ("near_contact", "Near-contact / wall view", "field"),
]

PRESENCE_OPTIONS = ["0", "1", "2", "3", "U"]
IMPAIRMENT_OPTIONS = ["0", "1", "2", "3", "NA"]
OVERALL_OPTIONS = ["0", "1", "2", "3", "NA"]


def load_manifest(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"audit_review_id", "image_path"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Manifest missing required columns: {sorted(missing)}")
    if df["audit_review_id"].duplicated().any():
        raise ValueError("audit_review_id must be unique")
    return df.reset_index(drop=True)


def label_columns():
    cols = [
        "audit_review_id",
        "technical_evaluable",
        "imaging_mode_context",
        "overall_visibility_impairment",
        "mechanism_uncertain",
        "confidence",
        "comments",
        "review_completed",
        "updated_at",
    ]
    for key, _, _ in PHENOMENA:
        cols += [f"{key}_presence", f"{key}_impairment"]
    return cols


def empty_labels(ids):
    df = pd.DataFrame({"audit_review_id": ids})
    for c in label_columns():
        if c not in df.columns:
            df[c] = ""
    return df[label_columns()]


def load_labels(path: Path, ids):
    base = empty_labels(ids)
    if not path.exists():
        return base
    old = pd.read_csv(path, dtype=str).fillna("")
    if "audit_review_id" not in old.columns:
        return base
    for c in label_columns():
        if c not in old.columns:
            old[c] = ""
    merged = base[["audit_review_id"]].merge(old[label_columns()], on="audit_review_id", how="left")
    return merged.fillna("")


def backup_and_save(df: pd.DataFrame, output: Path, backup_dir: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if output.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = backup_dir / f"{output.stem}_{stamp}.csv"
        backup.write_bytes(output.read_bytes())
        # Keep backup directory bounded.
        backups = sorted(backup_dir.glob(f"{output.stem}_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in backups[40:]:
            try:
                p.unlink()
            except OSError:
                pass
    df.to_csv(output, index=False, encoding="utf-8-sig")


def row_dict(df: pd.DataFrame, review_id: str):
    hit = df[df["audit_review_id"] == review_id]
    if hit.empty:
        return {c: "" for c in label_columns()}
    return hit.iloc[0].to_dict()


def option_index(options, value, default=0):
    v = str(value) if value is not None else ""
    return options.index(v) if v in options else default


def render_phenomenon(key, label, saved):
    st.markdown(f"**{label}**")
    c1, c2 = st.columns(2)
    with c1:
        presence = st.selectbox(
            "Presence / burden",
            PRESENCE_OPTIONS,
            index=option_index(PRESENCE_OPTIONS, saved.get(f"{key}_presence", ""), 0),
            key=f"{key}_presence_widget",
            help="0 absent; 1 focal/mild; 2 moderate; 3 extensive/dominant; U uncertain",
        )
    with c2:
        default_imp = "0" if presence == "0" else saved.get(f"{key}_impairment", "0")
        impairment = st.selectbox(
            "Visibility impairment",
            IMPAIRMENT_OPTIONS,
            index=option_index(IMPAIRMENT_OPTIONS, default_imp, 0),
            key=f"{key}_impairment_widget",
            help="0 none; 1 mild; 2 clearly limiting; 3 severe; NA cannot attribute",
        )
    return presence, impairment


def main():
    st.set_page_config(page_title="Phase 01 Visual Audit", layout="wide")
    st.title("Phase 01 targeted visual-audit labeling")
    st.caption("Internal development set. Retrieval stratum and metric values are intentionally hidden.")

    with st.sidebar:
        manifest_text = st.text_input("Manifest", str(DEFAULT_MANIFEST))
        output_text = st.text_input("Output labels", str(DEFAULT_OUTPUT))
        st.markdown("---")
        st.caption("Presence: 0 absent, 1 mild/focal, 2 moderate, 3 extensive/dominant, U uncertain")
        st.caption("Impairment: 0 none, 1 mild, 2 clearly limiting, 3 severe, NA cannot attribute")

    manifest_path = Path(manifest_text)
    output_path = Path(output_text)
    backup_dir = DEFAULT_BACKUP_DIR

    if not manifest_path.exists():
        st.error(f"Manifest not found: {manifest_path}")
        st.stop()

    try:
        manifest = load_manifest(manifest_path)
    except Exception as e:
        st.error(str(e))
        st.stop()

    labels = load_labels(output_path, manifest["audit_review_id"].tolist())
    completed = labels["review_completed"].astype(str).str.lower().eq("true")

    if "audit_index" not in st.session_state:
        incomplete_indices = [i for i, rid in enumerate(manifest["audit_review_id"]) if not completed.iloc[i]]
        st.session_state.audit_index = incomplete_indices[0] if incomplete_indices else 0

    idx = max(0, min(int(st.session_state.audit_index), len(manifest) - 1))
    item = manifest.iloc[idx]
    review_id = str(item["audit_review_id"])
    saved = row_dict(labels, review_id)

    progress = int(completed.sum())
    st.progress(progress / max(1, len(manifest)), text=f"Completed {progress}/{len(manifest)}")

    nav1, nav2, nav3 = st.columns([1, 1, 3])
    with nav1:
        if st.button("← Previous", disabled=idx == 0):
            st.session_state.audit_index = idx - 1
            st.rerun()
    with nav2:
        if st.button("Next →", disabled=idx == len(manifest) - 1):
            st.session_state.audit_index = idx + 1
            st.rerun()
    with nav3:
        jump = st.number_input("Jump to item", min_value=1, max_value=len(manifest), value=idx + 1, step=1)
        if int(jump) - 1 != idx:
            st.session_state.audit_index = int(jump) - 1
            st.rerun()

    st.subheader(f"{review_id}  ({idx + 1}/{len(manifest)})")

    image_path = Path(str(item["image_path"]))
    left, right = st.columns([1.35, 1])

    with left:
        if image_path.exists():
            try:
                img = Image.open(image_path)
                st.image(img, use_column_width=True)
            except Exception as e:
                st.error(f"Could not open image: {e}")
        else:
            st.error(f"Image not found: {image_path}")

    with right:
        technical = st.radio(
            "Technical evaluability",
            ["Yes", "No"],
            index=0 if saved.get("technical_evaluable", "Yes") != "No" else 1,
            horizontal=True,
            help="No only for true invalid image data, not poor clinical visibility.",
        )

        imaging_mode = st.selectbox(
            "Imaging mode context",
            ["Standard visible light", "Firefly / ICG", "Other", "Uncertain"],
            index=option_index(
                ["Standard visible light", "Firefly / ICG", "Other", "Uncertain"],
                saved.get("imaging_mode_context", "Standard visible light"),
                0,
            ),
        )

        overall = st.selectbox(
            "Overall task-relevant visibility impairment",
            OVERALL_OPTIONS,
            index=option_index(OVERALL_OPTIONS, saved.get("overall_visibility_impairment", ""), 0),
            help="Independent global judgment; do not derive from component scores.",
        )

        mechanism_uncertain = st.radio(
            "Mechanism uncertain?",
            ["No", "Yes"],
            index=1 if saved.get("mechanism_uncertain", "No") == "Yes" else 0,
            horizontal=True,
        )

        st.markdown("### Technical / visual-condition phenotypes")
        ratings = {}
        for key, label, group in PHENOMENA:
            if group == "technical":
                ratings[key] = render_phenomenon(key, label, saved)

        st.markdown("### Operative-field / camera-interaction phenotypes")
        for key, label, group in PHENOMENA:
            if group == "field":
                ratings[key] = render_phenomenon(key, label, saved)

        confidence = st.selectbox(
            "Confidence",
            ["1", "2", "3"],
            index=option_index(["1", "2", "3"], saved.get("confidence", "2"), 1),
            help="How confident are you that you would give essentially the same ratings again?",
        )
        comments = st.text_area("Comments", value=saved.get("comments", ""), height=90)
        completed_now = st.checkbox("Mark this item complete", value=str(saved.get("review_completed", "")).lower() == "true")

        if st.button("Save ratings", type="primary", use_container_width=True):
            update = {
                "audit_review_id": review_id,
                "technical_evaluable": technical,
                "imaging_mode_context": imaging_mode,
                "overall_visibility_impairment": overall,
                "mechanism_uncertain": mechanism_uncertain,
                "confidence": confidence,
                "comments": comments,
                "review_completed": str(bool(completed_now)),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            for key, _, _ in PHENOMENA:
                presence, impairment = ratings[key]
                if presence == "0":
                    impairment = "0"
                update[f"{key}_presence"] = presence
                update[f"{key}_impairment"] = impairment

            loc = labels["audit_review_id"] == review_id
            for c, v in update.items():
                labels.loc[loc, c] = v
            backup_and_save(labels, output_path, backup_dir)
            st.success("Saved")

            if completed_now and idx < len(manifest) - 1:
                st.session_state.audit_index = idx + 1
                st.rerun()

    with st.expander("Scoring definitions"):
        st.markdown(
            """
**Overall visibility**  
0 intact · 1 mildly degraded · 2 clearly limiting but interpretable · 3 unreliable recognition · NA cannot judge.

**Presence / burden**  
0 absent · 1 focal/mild · 2 moderate · 3 extensive/dominant · U uncertain.

**Phenomenon-related impairment**  
0 none · 1 mild · 2 clearly limiting · 3 severe · NA cannot attribute.

The retrieval stratum is not the label. A frame retrieved by one heuristic may receive another phenomenon label.
"""
        )


if __name__ == "__main__":
    main()
