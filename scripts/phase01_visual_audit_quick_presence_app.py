#!/usr/bin/env python
from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "reports"
    / "phase01_targeted_visual_audit"
    / "phase01_targeted_visual_audit_manifest.csv"
)

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_targeted_visual_audit_presence_labels.csv"
)

DEFAULT_BACKUP_DIR = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_targeted_visual_audit_presence_backups"
)

PHENOMENA = [
    ("blur", "Blur / defocus / motion blur"),
    ("smoke", "Smoke / airborne veil"),
    ("lens_contamination", "Lens contamination / lens fogging"),
    ("glare", "Glare / specular reflection"),
    ("whiteout", "Whiteout / overexposure"),
    ("underexposure", "Underexposure / blackout"),
    ("blood_fluid", "Blood / fluid"),
    ("physical_obstruction", "Physical obstruction"),
    ("near_contact", "Near-contact / wall view"),
]


def parse_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    if "audit_review_id" not in df.columns:
        return {}
    return {
        str(row["audit_review_id"]): row.to_dict()
        for _, row in df.iterrows()
    }


def backup_existing(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    shutil.copy2(path, backup_dir / f"{path.stem}_{ts}{path.suffix}")


def save_row(path: Path, backup_dir: Path, new_row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing(path, backup_dir)

    if path.exists():
        df = pd.read_csv(path, dtype=str).fillna("")
    else:
        df = pd.DataFrame()

    if not df.empty and "audit_review_id" in df.columns:
        df = df[df["audit_review_id"].astype(str) != str(new_row["audit_review_id"])]

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    if "review_order" in df.columns:
        df["review_order_sort"] = pd.to_numeric(df["review_order"], errors="coerce")
        df = df.sort_values("review_order_sort", kind="mergesort").drop(
            columns=["review_order_sort"]
        )

    df.to_csv(path, index=False, encoding="utf-8-sig")


def resolve_image_path(value: object) -> Path | None:
    if value is None:
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    p = Path(text)
    if p.exists():
        return p
    p2 = PROJECT_ROOT / p
    if p2.exists():
        return p2
    return None


def get_default(existing: dict, key: str, default=False):
    return parse_bool(existing.get(key, default))


def main():
    st.set_page_config(
        page_title="Phase 01 Visual Audit - Presence Only",
        layout="wide",
    )

    st.title("Phase 01 Targeted Visual Audit — Quick Presence Labeling")
    st.caption(
        "Internal retrieval audit only. Candidate stratum and metric values are hidden."
    )

    with st.sidebar:
        st.header("Files")
        manifest_path = Path(
            st.text_input("Manifest", str(DEFAULT_MANIFEST))
        )
        output_path = Path(
            st.text_input("Output CSV", str(DEFAULT_OUTPUT))
        )
        backup_dir = Path(
            st.text_input("Backup directory", str(DEFAULT_BACKUP_DIR))
        )

    if not manifest_path.exists():
        st.error(f"Manifest not found: {manifest_path}")
        st.stop()

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    required = {"audit_review_id", "case_id", "sample_time_sec", "image_path"}
    missing = required - set(manifest.columns)
    if missing:
        st.error(f"Manifest missing required columns: {sorted(missing)}")
        st.stop()

    manifest = manifest.reset_index(drop=True)
    manifest["review_order"] = range(1, len(manifest) + 1)

    existing_map = load_existing(output_path)
    completed = set(existing_map.keys())

    if "idx" not in st.session_state:
        st.session_state.idx = 0

    idx = max(0, min(int(st.session_state.idx), len(manifest) - 1))
    st.session_state.idx = idx
    row = manifest.iloc[idx]
    review_id = str(row["audit_review_id"])
    existing = existing_map.get(review_id, {})

    with st.sidebar:
        st.header("Progress")
        st.write(f"{len(completed)} / {len(manifest)} saved")
        st.progress(len(completed) / len(manifest) if len(manifest) else 0)

        jump = st.number_input(
            "Jump to item",
            min_value=1,
            max_value=len(manifest),
            value=idx + 1,
            step=1,
        )
        if int(jump) - 1 != idx:
            st.session_state.idx = int(jump) - 1
            st.rerun()

        if review_id in completed:
            st.success("Current item saved")
        else:
            st.info("Current item not yet saved")

    st.subheader(f"Item {idx + 1} / {len(manifest)} — {review_id}")

    image_path = resolve_image_path(row["image_path"])
    if image_path is None:
        st.error(f"Could not resolve image: {row['image_path']}")
    else:
        try:
            img = Image.open(image_path)
            st.image(img, use_column_width=True)
        except Exception as e:
            st.error(f"Could not open image: {e}")

    st.markdown("---")
    st.markdown("### What visual phenomena are present?")
    st.caption(
        "Select all that are visibly present. Do not infer the label from the retrieval route."
    )

    values = {}
    cols = st.columns(3)
    for i, (key, label) in enumerate(PHENOMENA):
        with cols[i % 3]:
            values[key] = st.checkbox(
                label,
                value=get_default(existing, f"present_{key}", False),
                key=f"{review_id}_present_{key}",
            )

    st.markdown("### Context / uncertainty")
    c1, c2, c3 = st.columns(3)
    with c1:
        no_listed = st.checkbox(
            "None of the listed phenomena",
            value=get_default(existing, "no_listed_phenomenon", False),
            key=f"{review_id}_none",
        )
    with c2:
        uncertain = st.checkbox(
            "Mechanism uncertain / cannot confidently classify",
            value=get_default(existing, "mechanism_uncertain", False),
            key=f"{review_id}_uncertain",
        )
    with c3:
        nonstandard = st.checkbox(
            "Non-standard imaging mode (e.g. Firefly/ICG)",
            value=get_default(existing, "nonstandard_imaging_mode", False),
            key=f"{review_id}_nonstandard",
        )

    comment = st.text_area(
        "Optional comment",
        value=str(existing.get("comment", "")),
        key=f"{review_id}_comment",
        height=80,
    )

    any_present = any(values.values())
    if no_listed and any_present:
        st.warning(
            "'None of the listed phenomena' is selected together with a phenomenon. "
            "You may still save, but review if intentional."
        )
    if not any_present and not no_listed and not uncertain:
        st.info(
            "No phenomenon selected. Choose 'None of the listed phenomena' or "
            "'Mechanism uncertain' if that is intentional."
        )

    def make_output_row():
        out = {
            "audit_review_id": review_id,
            "review_order": idx + 1,
            "case_id": row["case_id"],
            "sample_time_sec": row["sample_time_sec"],
            "image_path": row["image_path"],
        }
        for key, _ in PHENOMENA:
            out[f"present_{key}"] = bool(values[key])
        out["no_listed_phenomenon"] = bool(no_listed)
        out["mechanism_uncertain"] = bool(uncertain)
        out["nonstandard_imaging_mode"] = bool(nonstandard)
        out["comment"] = comment
        out["saved_at"] = datetime.now().isoformat(timespec="seconds")
        return out

    st.markdown("---")
    b1, b2, b3, b4 = st.columns([1, 1, 1, 1])

    with b1:
        if st.button("← Previous"):
            st.session_state.idx = max(0, idx - 1)
            st.rerun()

    with b2:
        if st.button("Save"):
            save_row(output_path, backup_dir, make_output_row())
            st.success("Saved.")
            st.rerun()

    with b3:
        if st.button("Save & Next"):
            save_row(output_path, backup_dir, make_output_row())
            st.session_state.idx = min(len(manifest) - 1, idx + 1)
            st.rerun()

    with b4:
        if st.button("Next →"):
            st.session_state.idx = min(len(manifest) - 1, idx + 1)
            st.rerun()

    with st.expander("Quick definitions"):
        st.markdown(
            """
- **Blur / defocus / motion blur**: loss of fine detail/boundaries due to focus or motion; not simply smooth tissue.
- **Smoke / airborne veil**: translucent smoke/mist-like veil between camera and field.
- **Lens contamination / fogging**: blood, smear, condensation or fog appearing to be on the lens surface.
- **Glare / specular reflection**: focal bright reflection from a shiny surface; a white object itself is not glare.
- **Whiteout / overexposure**: information loss from overexposure/saturation; a white object itself is not whiteout.
- **Underexposure / blackout**: information loss because the image/region is too dark.
- **Blood / fluid**: visible blood or fluid in the operative field, regardless of whether visibility is impaired.
- **Physical obstruction**: an object/tissue materially blocks the field behind it; mere instrument presence is insufficient.
- **Near-contact / wall view**: the camera is extremely close to/contacting tissue so spatial context is lost; redness is not required.
            """
        )


if __name__ == "__main__":
    main()
