#!/usr/bin/env python
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PILOT_DIR = PROJECT_ROOT / "reports" / "phase04a_operative_phenotype_pilot"
ANNOT_DIR = PROJECT_ROOT / "data" / "annotations"
STILL_MANIFEST = PILOT_DIR / "operative_phenotype_still_manifest.csv"
TEMPORAL_MANIFEST = PILOT_DIR / "operative_phenotype_temporal_manifest.csv"
STILL_OUTPUT = ANNOT_DIR / "phase04a_oper_phenotype_still_ratings.csv"
TEMPORAL_OUTPUT = ANNOT_DIR / "phase04a_oper_phenotype_temporal_ratings.csv"
BACKUP_DIR = ANNOT_DIR / "phase04a_oper_phenotype_backups"

PHENOTYPES = [
    ("inflammatory_change", "Macroscopic inflammatory-appearing change"),
    ("fibrotic_appearance", "Fibrotic-appearing tissue"),
    ("adhesion", "Adhesion"),
    ("difficult_plane", "Difficult / unclear dissection plane"),
    ("active_bleeding", "Active bleeding"),
]
ASSESS = ["Assessable", "Uncertain", "Not assessable"]
PRESENCE = ["Absent", "Present"]

def load_saved(path):
    if not path.exists():
        return {}
    d = pd.read_csv(path, dtype=str).fillna("")
    return {str(r["review_id"]): r.to_dict() for _, r in d.iterrows()} if "review_id" in d.columns else {}

def backup(path):
    if not path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    shutil.copy2(path, BACKUP_DIR / f"{path.stem}_{ts}{path.suffix}")

def save_row(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    if path.exists():
        df = pd.read_csv(path, dtype=str).fillna("")
        if "review_id" in df.columns:
            df = df[df["review_id"].astype(str) != str(row["review_id"])]
    else:
        df = pd.DataFrame()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    if "review_order" in df.columns:
        df["_sort"] = pd.to_numeric(df["review_order"], errors="coerce")
        df = df.sort_values("_sort", kind="mergesort").drop(columns="_sort")
    df.to_csv(path, index=False, encoding="utf-8-sig")

def choice(existing, key, options, default):
    v = str(existing.get(key, "")).strip()
    return v if v in options else default

def show_media(path, mode):
    p = Path(str(path))
    if not p.exists():
        st.error(f"File not found: {p}")
        return
    if mode == "still":
        st.image(Image.open(p), use_column_width=True)
    else:
        st.image(p.read_bytes(), use_column_width=True)

def main():
    st.set_page_config(page_title="Operative Phenotype Assessability Pilot", layout="wide")
    st.title("Operative Phenotype Assessability Pilot")

    with st.sidebar:
        pass_name = st.radio("Review pass", ["Still images", "Temporal context"], index=0)
        if pass_name == "Still images":
            manifest_path, output_path, mode = STILL_MANIFEST, STILL_OUTPUT, "still"
            st.warning("Complete all still-image reviews before starting temporal context.")
        else:
            manifest_path, output_path, mode = TEMPORAL_MANIFEST, TEMPORAL_OUTPUT, "temporal"
            st.info("Temporal condition = 11-frame sequence from t-5 to t+5 s using 1-Hz source frames.")

    if not manifest_path.exists():
        st.error(f"Manifest not found: {manifest_path}")
        st.stop()

    manifest = pd.read_csv(manifest_path, dtype=str).fillna("").reset_index(drop=True)
    media_col = "still_image_path" if mode == "still" else "temporal_gif_path"
    saved = load_saved(output_path)
    completed = set(saved)

    key_idx = f"idx_{mode}"
    if key_idx not in st.session_state:
        st.session_state[key_idx] = 0
    idx = max(0, min(int(st.session_state[key_idx]), len(manifest)-1))
    st.session_state[key_idx] = idx

    row = manifest.iloc[idx]
    rid = str(row["review_id"])
    existing = saved.get(rid, {})

    with st.sidebar:
        st.write(f"Progress: {len(completed)} / {len(manifest)}")
        st.progress(len(completed)/len(manifest) if len(manifest) else 0)
        jump = st.number_input("Jump to item", 1, len(manifest), idx+1, 1, key=f"jump_{mode}")
        if int(jump)-1 != idx:
            st.session_state[key_idx] = int(jump)-1
            st.rerun()

    st.subheader(f"{pass_name}: {idx+1} / {len(manifest)} — {rid}")
    show_media(row[media_col], mode)
    st.markdown("---")
    st.caption("For each phenotype: first judge assessability. Only if Assessable, judge Present/Absent.")

    ratings = {}
    for key, label in PHENOTYPES:
        st.markdown(f"#### {label}")
        c1, c2 = st.columns(2)
        with c1:
            a0 = choice(existing, f"{key}_assessability", ASSESS, "Uncertain")
            assess = st.radio("Assessability", ASSESS, index=ASSESS.index(a0),
                              horizontal=True, key=f"{mode}_{rid}_{key}_a")
        with c2:
            p0 = choice(existing, f"{key}_presence", PRESENCE, "Absent")
            pres = st.radio("Phenotype", PRESENCE, index=PRESENCE.index(p0),
                            horizontal=True, disabled=(assess != "Assessable"),
                            key=f"{mode}_{rid}_{key}_p")
        ratings[f"{key}_assessability"] = assess
        ratings[f"{key}_presence"] = pres if assess == "Assessable" else ""

    comment = st.text_area("Optional comment", value=str(existing.get("comment","")),
                           key=f"{mode}_{rid}_comment", height=70)

    def outrow():
        out = {
            "review_id": rid, "review_order": idx+1, "review_condition": mode,
            "media_path": row[media_col], "comment": comment,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        out.update(ratings)
        return out

    st.markdown("---")
    b1,b2,b3,b4 = st.columns(4)
    with b1:
        if st.button("← Previous", key=f"prev_{mode}"):
            st.session_state[key_idx] = max(0, idx-1); st.rerun()
    with b2:
        if st.button("Save", key=f"save_{mode}"):
            save_row(output_path, outrow()); st.rerun()
    with b3:
        if st.button("Save & Next", key=f"savenext_{mode}"):
            save_row(output_path, outrow())
            st.session_state[key_idx] = min(len(manifest)-1, idx+1); st.rerun()
    with b4:
        if st.button("Next →", key=f"next_{mode}"):
            st.session_state[key_idx] = min(len(manifest)-1, idx+1); st.rerun()

    with st.expander("Definitions"):
        st.markdown("""
- **Macroscopic inflammatory-appearing change**: visible inflammatory-type reaction such as edema, erythematous/friable appearance; not histopathologic proof.
- **Fibrotic-appearing tissue**: dense, scar-like, whitish or rigid-appearing tissue; not histopathologic proof.
- **Adhesion**: apparent abnormal adherence between tissue surfaces or structures.
- **Difficult / unclear dissection plane**: operative plane difficult to identify or maintain.
- **Active bleeding**: active emergence, flow or ongoing accumulation of blood. Static redness or old blood alone is not active bleeding.
""")

if __name__ == "__main__":
    main()
