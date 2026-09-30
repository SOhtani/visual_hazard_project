#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phase 01 blinded still-image visibility review app - v0.3

Purpose
-------
Calibration second pass after first-pass instrument review.

Key v0.3 rules
--------------
1. Overall and component scores are judged independently.
2. Component scores are NOT summed.
3. Overall is NOT forced to equal max(component).
4. If max(component) > overall, show a soft warning only; saving remains allowed.
5. Near-contact/red-out anchors are clarified.
6. Confidence is defined as repeat-rating confidence.
7. Firefly/ICG is recorded as a context flag, not as visibility impairment.
8. Second-pass ratings are written to a separate CSV so first-pass ratings are preserved.

Run
---
streamlit run scripts/phase01_still_review_app.py
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_CSV = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_pilot_review_manifest.csv"
)

# IMPORTANT: v0.3 calibration second pass is written separately.
RATINGS_CSV = (
    PROJECT_ROOT
    / "data"
    / "annotations"
    / "phase01_pilot_still_ratings_second_pass.csv"
)

PHYSICAL_OBSTRUCTION_COL = "component_physical_obstruction"

COMPONENTS = [
    (
        "component_blur_defocus",
        "Blur / defocus / motion blur",
        "Defocus or motion-related loss of relevant structural detail.",
        "0: none/no effect; 1: slight softness but recognition intact; "
        "2: relevant detail clearly reduced; 3: reliable recognition prevented.",
    ),
    (
        "component_smoke_fog_veil",
        "Smoke / fog / veil",
        "Diffuse haze or veil-like contrast loss. The exact physical cause need not be certain.",
        "0: none/no effect; 1: mild haze, anatomy still clear; "
        "2: contrast loss clearly limits recognition; 3: useful local contrast largely lost.",
    ),
    (
        "component_blood_fluid",
        "Blood / fluid",
        "Rate the visibility consequence of blood/fluid, not simple presence.",
        "0: absent or no visibility effect; 1: mild effect; "
        "2: relevant field clearly partly obscured; 3: reliable recognition prevented.",
    ),
    (
        "component_glare_specular",
        "Glare / specular reflection",
        "Localized intense reflection or highlight that may hide relevant detail.",
        "0: no relevant effect; 1: focal glare but recognition intact; "
        "2: relevant detail clearly blocked; 3: reliable recognition prevented.",
    ),
    (
        "component_whiteout_overexposure",
        "Whiteout / overexposure",
        "Broad exposure-related saturation or information loss. A white object is not automatically whiteout.",
        "0: no exposure-related loss; 1: mild overexposure; "
        "2: relevant information partly lost; 3: relevant field cannot be reliably recognized.",
    ),
    (
        "component_underexposure_blackout",
        "Underexposure / blackout",
        "Visibility loss caused by insufficient illumination or black crush. Darkness alone is not impairment.",
        "0: dark but no visibility loss; 1: mild effect; "
        "2: recognition clearly limited; 3: relevant field effectively not visible.",
    ),
    (
        PHYSICAL_OBSTRUCTION_COL,
        "Physical obstruction",
        "Physical blocking by instrument, tissue, gauze, sponge, specimen bag, suction device, stapler, or other surgical material.",
        "0: object does not block relevant information; 1: slight overlap; "
        "2: relevant structure partly blocked; 3: relevant field substantially/completely blocked.",
    ),
    (
        "component_lens_contamination",
        "Lens contamination",
        "Visibility loss that appears to arise from contamination on the lens/imaging system.",
        "0: none; 1: small smear/drop, recognition intact; "
        "2: part of field clearly limited; 3: reliable recognition prevented.",
    ),
    (
        "component_near_contact_redout",
        "Near-contact / red-out",
        "Loss of task-relevant field information because the camera is excessively close to, or contacting, tissue. "
        "A close-up alone is NOT near-contact impairment.",
        "0: close or not close, but relevant structure/relationships remain clear; "
        "1: slightly too close, recognition intact; "
        "2: excessive proximity clearly limits structure/orientation; "
        "3: contact/red-out/extreme close-up prevents reliable field interpretation.",
    ),
]

TECHNICAL_ISSUES = [
    "",
    "all_zero_image",
    "corrupt_or_unreadable",
    "decoder_or_render_failure",
    "no_signal",
    "test_pattern_or_color_bar",
    "other_technical_failure",
    "uncertain_technical_failure",
]

IMAGING_MODES = [
    "Standard visible-light",
    "Firefly / ICG",
    "Other alternate imaging mode",
    "Uncertain",
]

RATING_COLUMNS = [
    "reviewer_id",
    "review_item_id",
    "review_order",
    "imaging_mode_context",
    "technical_evaluable",
    "technical_issue",
    "task_context_sufficient",
    "overall_visibility_impairment",
] + [x[0] for x in COMPONENTS] + [
    "confidence",
    "comment",
    "qc_warning",
    "review_started_at",
    "review_saved_at",
    "review_time_sec",
    "completed",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_reviewer_id(value: str) -> str:
    value = value.strip()
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def load_manifest() -> pd.DataFrame:
    if not MANIFEST_CSV.exists():
        raise FileNotFoundError(
            f"Blinded manifest not found: {MANIFEST_CSV}\n"
            "Run scripts/phase01_build_blinded_review_manifest.py first."
        )

    d = pd.read_csv(MANIFEST_CSV)

    required = ["review_item_id", "review_order", "image_path"]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError(f"Manifest missing required columns: {missing}")

    if d["review_item_id"].duplicated().any():
        raise ValueError("Duplicate review_item_id in manifest")

    d = d.sort_values("review_order").reset_index(drop=True)

    missing_images = [p for p in d["image_path"].astype(str) if not Path(p).exists()]
    if missing_images:
        raise FileNotFoundError("One or more blinded review images are missing.")

    return d


def load_ratings() -> pd.DataFrame:
    if not RATINGS_CSV.exists():
        return pd.DataFrame(columns=RATING_COLUMNS)

    d = pd.read_csv(RATINGS_CSV, low_memory=False)

    for col in RATING_COLUMNS:
        if col not in d.columns:
            d[col] = np.nan

    return d[RATING_COLUMNS].copy()


def atomic_write_ratings(d: pd.DataFrame) -> None:
    RATINGS_CSV.parent.mkdir(parents=True, exist_ok=True)
    tmp = RATINGS_CSV.with_suffix(".tmp.csv")
    d.to_csv(tmp, index=False)
    os.replace(tmp, RATINGS_CSV)


def saved_row(
    ratings: pd.DataFrame,
    reviewer_id: str,
    review_item_id: str,
) -> pd.Series | None:
    g = ratings.loc[
        ratings["reviewer_id"].astype(str).eq(reviewer_id)
        & ratings["review_item_id"].astype(str).eq(review_item_id)
    ]
    if g.empty:
        return None
    return g.iloc[-1]


def to_int_or_none(value):
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def yes_no_from_saved(value):
    v = to_int_or_none(value)
    if v == 1:
        return "Yes"
    if v == 0:
        return "No"
    return None


def init_item_state(prefix: str, row: pd.Series | None) -> None:
    defaults = {
        f"{prefix}_imaging_mode": (
            str(row.get("imaging_mode_context"))
            if row is not None and not pd.isna(row.get("imaging_mode_context"))
            else None
        ),
        f"{prefix}_technical": (
            yes_no_from_saved(row.get("technical_evaluable"))
            if row is not None
            else None
        ),
        f"{prefix}_technical_issue": (
            "" if row is None or pd.isna(row.get("technical_issue"))
            else str(row.get("technical_issue"))
        ),
        f"{prefix}_task_context": (
            yes_no_from_saved(row.get("task_context_sufficient"))
            if row is not None
            else None
        ),
        f"{prefix}_overall": (
            to_int_or_none(row.get("overall_visibility_impairment"))
            if row is not None
            else None
        ),
        f"{prefix}_confidence": (
            to_int_or_none(row.get("confidence"))
            if row is not None
            else None
        ),
        f"{prefix}_comment": (
            "" if row is None or pd.isna(row.get("comment"))
            else str(row.get("comment"))
        ),
    }

    for col, _, _, _ in COMPONENTS:
        defaults[f"{prefix}_{col}"] = (
            to_int_or_none(row.get(col))
            if row is not None
            else None
        )

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def derive_qc_warning(
    overall,
    component_values: dict[str, int | None],
) -> str:
    """
    Soft QC only.

    IMPORTANT:
    - Overall is not a sum.
    - Overall is not mechanically set to max(component).
    - Discordance is allowed and may be informative during instrument calibration.
    """
    if overall is None:
        return ""

    vals = [v for v in component_values.values() if v is not None]
    if not vals:
        return ""

    warnings = []

    max_component = max(vals)

    if max_component > overall:
        warnings.append("component_higher_than_overall_review_if_intended")

    if overall >= 2 and all(v == 0 for v in vals):
        warnings.append("overall_ge_2_but_all_components_0_review_if_intended")

    return ";".join(warnings)


def validate_and_build_record(
    *,
    reviewer_id: str,
    review_item_id: str,
    review_order: int,
    prefix: str,
    existing: pd.Series | None,
    elapsed_sec: float,
) -> tuple[dict | None, list[str], str]:
    errors = []

    imaging_mode = st.session_state.get(f"{prefix}_imaging_mode")
    technical = st.session_state.get(f"{prefix}_technical")
    technical_issue = st.session_state.get(f"{prefix}_technical_issue", "")
    task_context = st.session_state.get(f"{prefix}_task_context")
    overall = st.session_state.get(f"{prefix}_overall")
    confidence = st.session_state.get(f"{prefix}_confidence")
    comment = st.session_state.get(f"{prefix}_comment", "").strip()

    technical_value = 1 if technical == "Yes" else 0 if technical == "No" else None
    task_value = 1 if task_context == "Yes" else 0 if task_context == "No" else None

    component_values = {
        col: st.session_state.get(f"{prefix}_{col}")
        for col, _, _, _ in COMPONENTS
    }

    if imaging_mode is None:
        errors.append("Imaging mode context を選択してください。")

    if technical_value is None:
        errors.append("Technical evaluable を選択してください。")

    if technical_value == 0:
        if technical_issue == "":
            errors.append("Technical issue を選択してください。")
        task_value = None
        overall = None
        component_values = {k: None for k in component_values}

    if technical_value == 1:
        technical_issue = ""

        if task_value is None:
            errors.append("Task context sufficient を選択してください。")

        if task_value == 0:
            overall = None
            component_values = {k: None for k in component_values}

        if task_value == 1:
            if overall is None:
                errors.append("Overall visibility impairment を選択してください.")

            missing_components = [
                label
                for col, label, _, _ in COMPONENTS
                if component_values[col] is None
            ]
            if missing_components:
                errors.append(
                    "9 component をすべて評価してください: "
                    + ", ".join(missing_components)
                )

    if confidence is None:
        errors.append("Confidence を選択してください。")

    qc_warning = derive_qc_warning(overall, component_values)

    if errors:
        return None, errors, qc_warning

    prior_time = 0.0
    started_at = now_iso()

    if existing is not None:
        if not pd.isna(existing.get("review_time_sec")):
            try:
                prior_time = float(existing.get("review_time_sec"))
            except Exception:
                prior_time = 0.0

        if not pd.isna(existing.get("review_started_at")):
            started_at = str(existing.get("review_started_at"))

    record = {
        "reviewer_id": reviewer_id,
        "review_item_id": review_item_id,
        "review_order": int(review_order),
        "imaging_mode_context": imaging_mode,
        "technical_evaluable": technical_value,
        "technical_issue": technical_issue if technical_value == 0 else np.nan,
        "task_context_sufficient": task_value,
        "overall_visibility_impairment": overall,
        **component_values,
        "confidence": confidence,
        "comment": comment,
        "qc_warning": qc_warning,
        "review_started_at": started_at,
        "review_saved_at": now_iso(),
        "review_time_sec": round(prior_time + max(0.0, elapsed_sec), 1),
        "completed": 1,
    }

    return record, [], qc_warning


def upsert_record(ratings: pd.DataFrame, record: dict) -> pd.DataFrame:
    key_mask = (
        ratings["reviewer_id"].astype(str).eq(str(record["reviewer_id"]))
        & ratings["review_item_id"].astype(str).eq(str(record["review_item_id"]))
    )

    out = ratings.loc[~key_mask].copy()
    out = pd.concat([out, pd.DataFrame([record])], ignore_index=True)
    out = out[RATING_COLUMNS]
    out = out.sort_values(["reviewer_id", "review_order"], kind="mergesort").reset_index(drop=True)
    return out


def completed_ids(ratings: pd.DataFrame, reviewer_id: str) -> set[str]:
    g = ratings.loc[ratings["reviewer_id"].astype(str).eq(reviewer_id)]

    if "completed" in g.columns:
        done = pd.to_numeric(g["completed"], errors="coerce").fillna(0).ge(0.5)
        g = g.loc[done]

    return set(g["review_item_id"].astype(str))


def set_current_index(new_index: int, n_items: int) -> None:
    new_index = max(0, min(n_items - 1, int(new_index)))
    st.session_state["phase01_current_index"] = new_index
    st.session_state["phase01_timer_item_id"] = None
    st.rerun()


def render_anchor_guide() -> None:
    st.markdown(
        """
### Overall: what are you judging?

> **Considering the image as a whole, how much is task-relevant operative-field visibility impaired?**

日本語では、

> **すべての要因をまとめて考えたとき、必要な構造・境界・位置関係の視認性はどの程度低下していますか？**

| Overall | Practical anchor |
|---|---|
| **0** | 普通に見える。必要な術野情報は保たれている |
| **1** | 少し見づらいが、必要な構造・境界の認識には実質的に困らない |
| **2** | 明らかに見づらく、認識が制限されるが、術野としてはまだ解釈できる |
| **3** | 必要な構造・境界・位置関係を信頼して認識できない |

### Components: what are you judging?

Components answer **why the field is difficult to see** and how strongly each factor contributes.

**Do not sum component scores. Do not force Overall to equal the maximum component score.**
Overall and components are independent judgments.

### Common component 0-3 anchor

| Score | Component anchor |
|---|---|
| **0** | Absent, or present but does **not** contribute to task-relevant visibility loss |
| **1** | Mild contribution, but recognition remains essentially intact |
| **2** | Clearly limits recognition, but the relevant field remains broadly interpretable |
| **3** | Severely limits or prevents reliable recognition/following |
"""
    )


def render_examples() -> None:
    with st.expander("Concrete label examples", expanded=False):
        st.markdown(
            """
**Gauze completely covers the operative field, but gauze itself is sharp**
- Technical evaluable: **Yes**
- Task context sufficient: **Yes**
- Overall: **3**
- Physical obstruction: **3**
- Whiteout/overexposure: **0**, unless true exposure clipping is also present

**Blood visible away from the target**
- Blood/fluid: **0**
- Overall: **0 or 1**, depending on the whole field

**Blood partly covers the dissection plane**
- Blood/fluid: typically **2**
- Overall is judged independently from the whole image

**Dark image but anatomy remains clear**
- Underexposure/blackout: **0 or 1**
- Overall: **0 or 1**

**Severe optical whiteout hides the field**
- Whiteout/overexposure: **3**
- Overall: usually severe, but judge it independently

**Large instrument in the image but not blocking relevant information**
- Physical obstruction: **0**

**Small instrument tip blocks a critical boundary**
- Physical obstruction: often **2**

**Close-up with clear vessel wall and spatial relationships**
- Near-contact/red-out: **0**

**Slightly too close, but recognition remains intact**
- Near-contact/red-out: **1**

**Excessively close; surrounding orientation is clearly limited**
- Near-contact/red-out: **2**

**Tissue contact / homogeneous red-out / extreme close-up with loss of field interpretation**
- Near-contact/red-out: **3**

**Firefly / ICG image that is visually clear**
- Imaging mode context: **Firefly / ICG**
- Do **not** increase Overall merely because the color appearance is non-standard

**All-zero image**
- Technical evaluable: **No**
- Technical issue: `all_zero_image`
- Overall/components: **NA**
"""
        )


def main() -> None:
    st.set_page_config(page_title="Phase 01 Still Review - Pass 2", layout="wide")

    st.title("Phase 01 - Blinded still-image visibility review")
    st.info(
        "Calibration second pass (v0.3). "
        "Results are saved separately from the first pass."
    )

    try:
        manifest = load_manifest()
    except Exception as e:
        st.error(str(e))
        st.stop()

    ratings = load_ratings()

    default_reviewer = os.environ.get("PHASE01_REVIEWER_ID", "surgeon01")
    reviewer_raw = st.sidebar.text_input("Reviewer ID", value=default_reviewer)
    reviewer_id = clean_reviewer_id(reviewer_raw)

    if not reviewer_id:
        st.warning("Reviewer ID を入力してください。")
        st.stop()

    st.sidebar.caption("Output: phase01_pilot_still_ratings_second_pass.csv")

    if st.session_state.get("phase01_active_reviewer") != reviewer_id:
        st.session_state["phase01_active_reviewer"] = reviewer_id
        done = completed_ids(ratings, reviewer_id)

        first_incomplete = 0
        for i, item_id in enumerate(manifest["review_item_id"].astype(str)):
            if item_id not in done:
                first_incomplete = i
                break

        st.session_state["phase01_current_index"] = first_incomplete
        st.session_state["phase01_timer_item_id"] = None

    if "phase01_current_index" not in st.session_state:
        st.session_state["phase01_current_index"] = 0

    idx = int(st.session_state["phase01_current_index"])
    idx = max(0, min(len(manifest) - 1, idx))

    item = manifest.iloc[idx]
    item_id = str(item["review_item_id"])
    review_order = int(item["review_order"])

    done = completed_ids(ratings, reviewer_id)
    n_done = len(done)

    st.sidebar.progress(n_done / len(manifest))
    st.sidebar.write(f"Completed: {n_done} / {len(manifest)}")

    if st.session_state.get("phase01_jump_sync_index") != idx:
        st.session_state["phase01_jump_item"] = item_id
        st.session_state["phase01_jump_sync_index"] = idx

    nav_label = st.sidebar.selectbox(
        "Jump to item",
        options=manifest["review_item_id"].astype(str).tolist(),
        key="phase01_jump_item",
    )

    jump_idx = int(
        manifest.index[
            manifest["review_item_id"].astype(str).eq(nav_label)
        ][0]
    )

    if jump_idx != idx:
        st.session_state["phase01_current_index"] = jump_idx
        st.session_state["phase01_timer_item_id"] = None
        st.rerun()

    status = "Completed" if item_id in done else "Incomplete"

    st.write(
        f"**Review item {item_id}**  |  "
        f"Item {review_order} / {len(manifest)}  |  "
        f"**{status}**"
    )

    render_anchor_guide()
    render_examples()

    image_path = Path(str(item["image_path"]))
    st.image(str(image_path), use_column_width=True)

    existing = saved_row(ratings, reviewer_id, item_id)
    prefix = f"p01pass2_{reviewer_id}_{item_id}"
    init_item_state(prefix, existing)

    if st.session_state.get("phase01_timer_item_id") != item_id:
        st.session_state["phase01_timer_item_id"] = item_id
        st.session_state["phase01_timer_started"] = time.monotonic()

    st.subheader("0. Imaging mode context")
    st.caption(
        "This is a context flag, not a visibility score. "
        "Firefly/ICG should not increase Overall merely because its appearance differs from standard visible light."
    )
    st.radio(
        "Imaging mode",
        options=IMAGING_MODES,
        horizontal=True,
        index=None,
        key=f"{prefix}_imaging_mode",
    )

    st.subheader("1. Technical evaluability")
    st.caption(
        "Is this a valid image that can be visually interpreted? "
        "Dark, bloody, blurred, whiteout, gauze-covered, or red-out operative fields "
        "are still technically evaluable if the image data are valid."
    )

    technical = st.radio(
        "Is this image technically interpretable as an image?",
        options=["Yes", "No"],
        horizontal=True,
        index=None,
        key=f"{prefix}_technical",
    )

    if technical == "No":
        st.selectbox(
            "Technical issue",
            options=TECHNICAL_ISSUES,
            key=f"{prefix}_technical_issue",
        )

    if technical == "Yes":
        st.subheader("2. Task-context sufficiency")
        st.caption(
            "This does NOT ask whether the target itself is visible. "
            "If gauze, blood, blackout, or red-out clearly makes the field unusable, "
            "select Yes and score the impairment."
        )

        task_context = st.radio(
            "From this image alone, can you judge whether the operative field is visually usable or impaired?",
            options=["Yes", "No"],
            horizontal=True,
            index=None,
            key=f"{prefix}_task_context",
        )
    else:
        task_context = None

    if technical == "Yes" and task_context == "Yes":
        st.subheader("3. Overall visibility impairment")
        st.caption(
            "Judge the whole field first. "
            "Do not calculate Overall from the component scores."
        )

        st.radio(
            "Considering the image as a whole, how much is task-relevant operative-field visibility impaired?",
            options=[0, 1, 2, 3],
            horizontal=True,
            index=None,
            key=f"{prefix}_overall",
            help=(
                "0: clear/intact; 1: slightly difficult but recognition essentially intact; "
                "2: recognition clearly limited but field still interpretable; "
                "3: relevant structures/boundaries/spatial relationships cannot be reliably recognized."
            ),
        )

        st.subheader("4. Component impairment")
        st.caption(
            "For each factor, rate how much it contributes to visibility loss. "
            "Do not sum these scores and do not force them to match Overall."
        )

        for col, label, definition, example_anchor in COMPONENTS:
            st.markdown(f"**{label}**")
            st.caption(definition + "  " + example_anchor)
            st.radio(
                label,
                options=[0, 1, 2, 3],
                horizontal=True,
                index=None,
                key=f"{prefix}_{col}",
                label_visibility="collapsed",
            )

    st.subheader("5. Confidence")
    st.caption(
        "How confident are you that, under the same rules, you would assign essentially "
        "the same Overall/component ratings if you reviewed this still again? "
        "1 = low, 2 = moderate, 3 = high."
    )

    st.radio(
        "Confidence",
        options=[1, 2, 3],
        horizontal=True,
        index=None,
        key=f"{prefix}_confidence",
    )

    st.subheader("6. Optional comment")
    st.text_area(
        "Comment",
        key=f"{prefix}_comment",
        height=100,
        placeholder=(
            "Use for borderline scores, uncertain mechanisms, "
            "insufficient still-image context, alternate imaging, or unusual findings."
        ),
    )

    overall_preview = st.session_state.get(f"{prefix}_overall")
    component_preview = {
        col: st.session_state.get(f"{prefix}_{col}")
        for col, _, _, _ in COMPONENTS
    }

    qc_preview = derive_qc_warning(overall_preview, component_preview)

    if qc_preview:
        if "component_higher_than_overall" in qc_preview:
            st.warning(
                "Soft consistency check: at least one component score is higher than Overall. "
                "This is allowed. Recheck whether both ratings express what you intend; "
                "if yes, save them unchanged."
            )
        if "overall_ge_2_but_all_components_0" in qc_preview:
            st.warning(
                "Soft consistency check: Overall is 2-3 but all component scores are 0. "
                "This is allowed if the impairment is real but not captured by the current component taxonomy. "
                "Consider adding a comment."
            )

    col_prev, col_save, col_next = st.columns([1, 1, 1])

    with col_prev:
        prev_clicked = st.button(
            "Previous",
            disabled=(idx == 0),
            use_container_width=True,
        )

    with col_save:
        save_clicked = st.button(
            "Save",
            use_container_width=True,
            type="secondary",
        )

    with col_next:
        save_next_clicked = st.button(
            "Save & Next",
            use_container_width=True,
            type="primary",
        )

    if prev_clicked:
        set_current_index(idx - 1, len(manifest))

    if save_clicked or save_next_clicked:
        elapsed = (
            time.monotonic()
            - float(
                st.session_state.get(
                    "phase01_timer_started",
                    time.monotonic(),
                )
            )
        )

        current_ratings = load_ratings()
        current_existing = saved_row(
            current_ratings,
            reviewer_id,
            item_id,
        )

        record, errors, qc_warning = validate_and_build_record(
            reviewer_id=reviewer_id,
            review_item_id=item_id,
            review_order=review_order,
            prefix=prefix,
            existing=current_existing,
            elapsed_sec=elapsed,
        )

        if errors:
            for error in errors:
                st.error(error)
        else:
            updated = upsert_record(current_ratings, record)
            atomic_write_ratings(updated)

            st.session_state["phase01_timer_started"] = time.monotonic()
            st.success("Saved.")

            if save_next_clicked:
                done_after = completed_ids(updated, reviewer_id)
                next_idx = None

                for j in range(idx + 1, len(manifest)):
                    next_item = str(manifest.iloc[j]["review_item_id"])
                    if next_item not in done_after:
                        next_idx = j
                        break

                if next_idx is None:
                    for j in range(0, idx + 1):
                        next_item = str(manifest.iloc[j]["review_item_id"])
                        if next_item not in done_after:
                            next_idx = j
                            break

                if next_idx is None:
                    st.success("All 30 second-pass items are complete.")
                else:
                    set_current_index(next_idx, len(manifest))


if __name__ == "__main__":
    main()
