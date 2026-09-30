#!/usr/bin/env python
from __future__ import annotations

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
    / "phase01c_targeted_retrieval_v2"
    / "phase01c_v2_blinded_review_manifest_frozen_20260919.csv"
)

DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01c_v2_quick_presence_labels.csv"
)

DEFAULT_BACKUP_DIR = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01c_v2_quick_presence_backups"
)

LABELS = [
    ("near_contact", "Near-contact / wall view"),
    ("smoke", "Smoke / airborne veil"),
    ("blood", "Blood"),
    ("nonblood_fluid", "Non-blood fluid"),
    ("lens_contamination", "Lens contamination / fogging"),
]


def parse_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    if "review_id" not in df.columns:
        return {}
    return {str(row["review_id"]): row.to_dict() for _, row in df.iterrows()}


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

    if not df.empty and "review_id" in df.columns:
        df = df[df["review_id"].astype(str) != str(new_row["review_id"])]

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    if "review_order" in df.columns:
        df["_sort"] = pd.to_numeric(df["review_order"], errors="coerce")
        df = df.sort_values("_sort", kind="mergesort").drop(columns="_sort")

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


def existing_bool(existing: dict, key: str) -> bool:
    return parse_bool(existing.get(key, False))


def main():
    st.set_page_config(
        page_title="Phase 01C V2 Quick Review",
        layout="wide",
    )

    st.title("Phase 01C V2 — Quick Presence Review")
    st.caption(
        "Blinded retrieval-development review. Retrieval route and metric values are hidden."
    )

    with st.sidebar:
        st.header("Files")
        manifest_path = Path(st.text_input("Frozen manifest", str(DEFAULT_MANIFEST)))
        output_path = Path(st.text_input("Output CSV", str(DEFAULT_OUTPUT)))
        backup_dir = Path(st.text_input("Backup directory", str(DEFAULT_BACKUP_DIR)))

    if not manifest_path.exists():
        st.error(f"Manifest not found: {manifest_path}")
        st.stop()

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    required = {"review_id", "case_id", "sample_time_sec", "image_path"}
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
    review_id = str(row["review_id"])
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
    st.markdown("### Which phenomena are visibly present?")
    st.caption("Select all that apply. Judge the image itself; do not infer the retrieval route.")

    values = {}
    cols = st.columns(3)
    for i, (key, label) in enumerate(LABELS):
        with cols[i % 3]:
            values[key] = st.checkbox(
                label,
                value=existing_bool(existing, f"present_{key}"),
                key=f"{review_id}_{key}",
            )

    st.markdown("### Context / uncertainty")
    c1, c2, c3 = st.columns(3)
    with c1:
        none_selected = st.checkbox(
            "None of the listed phenomena",
            value=existing_bool(existing, "no_listed_phenomenon"),
            key=f"{review_id}_none",
        )
    with c2:
        uncertain = st.checkbox(
            "Mechanism uncertain / cannot classify confidently",
            value=existing_bool(existing, "mechanism_uncertain"),
            key=f"{review_id}_uncertain",
        )
    with c3:
        nonstandard = st.checkbox(
            "Non-standard imaging mode (e.g. Firefly/ICG)",
            value=existing_bool(existing, "nonstandard_imaging_mode"),
            key=f"{review_id}_nonstandard",
        )

    comment = st.text_area(
        "Optional comment",
        value=str(existing.get("comment", "")),
        key=f"{review_id}_comment",
        height=70,
    )

    any_present = any(values.values())
    if none_selected and any_present:
        st.warning(
            "'None of the listed phenomena' is selected together with a phenomenon. "
            "Review if intentional."
        )
    if not any_present and not none_selected and not uncertain and not nonstandard:
        st.info(
            "No phenomenon selected. Mark None, Uncertain, or Non-standard mode if intentional."
        )

    def output_row():
        out = {
            "review_id": review_id,
            "review_order": idx + 1,
            "case_id": row["case_id"],
            "sample_time_sec": row["sample_time_sec"],
            "image_path": row["image_path"],
        }
        for key, _ in LABELS:
            out[f"present_{key}"] = bool(values[key])
        out["no_listed_phenomenon"] = bool(none_selected)
        out["mechanism_uncertain"] = bool(uncertain)
        out["nonstandard_imaging_mode"] = bool(nonstandard)
        out["comment"] = comment
        out["saved_at"] = datetime.now().isoformat(timespec="seconds")
        return out

    st.markdown("---")
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        if st.button("← Previous"):
            st.session_state.idx = max(0, idx - 1)
            st.rerun()

    with b2:
        if st.button("Save"):
            save_row(output_path, backup_dir, output_row())
            st.success("Saved.")
            st.rerun()

    with b3:
        if st.button("Save & Next"):
            save_row(output_path, backup_dir, output_row())
            st.session_state.idx = min(len(manifest) - 1, idx + 1)
            st.rerun()

    with b4:
        if st.button("Next →"):
            st.session_state.idx = min(len(manifest) - 1, idx + 1)
            st.rerun()

    with st.expander("Definitions"):
        st.markdown(
            """
- **Near-contact / wall view**: camera is extremely close to or contacting tissue, with loss of spatial context. Redness is not required.
- **Smoke / airborne veil**: translucent smoke- or mist-like veil between camera and operative field.
- **Blood**: visible blood, pooled blood, flowing blood, or blood coating in the operative field. Do not use redness alone.
- **Non-blood fluid**: clearly visible fluid that is not blood (for example irrigation fluid). If blood vs non-blood fluid cannot be distinguished, use Uncertain.
- **Lens contamination / fogging**: blood, smear, condensation, droplets, or fog that appears to lie on the lens surface.
            """
        )


if __name__ == "__main__":
    main()
