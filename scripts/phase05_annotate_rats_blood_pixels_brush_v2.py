#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


WINDOW = "RATS blood-pixel brush annotation v2"

UNLABELED = 0
BLOOD = 1
NON_BLOOD = 2

EXCLUSION_KEYS = {
    ord("1"): "blur_or_out_of_focus",
    ord("2"): "lens_contamination",
    ord("3"): "near_contact_or_occlusion",
    ord("4"): "dark_or_exposure_failure",
    ord("5"): "smoke_or_fog",
    ord("6"): "other_ungradable",
}


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Brush-based RATS blood/non-blood pixel annotation with a separate "
            "frame-level gradability gate. Ungradable frames can be excluded with "
            "a recorded reason instead of forcing pixel labels."
        )
    )
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output-csv", required=True, type=Path)
    p.add_argument("--mask-dir", required=True, type=Path)
    p.add_argument(
        "--frame-qc-csv",
        type=Path,
        default=None,
        help="Frame-level gradability log. Defaults beside output CSV.",
    )
    p.add_argument("--display-width", type=int, default=1200)
    p.add_argument("--brush-radius", type=int, default=18)
    p.add_argument(
        "--pixels-per-class-per-frame",
        type=int,
        default=1500,
        help=(
            "Maximum exported pixels per class per annotated frame. "
            "Painted masks are preserved in full; exported pixel rows are "
            "deterministically subsampled so one frame cannot dominate."
        ),
    )
    p.add_argument("--seed", type=int, default=20260920)
    p.add_argument(
        "--revisit-completed",
        action="store_true",
        help="Show frames already marked annotated/excluded instead of skipping them.",
    )
    return p.parse_args()


def roi_bounds(row, w, h):
    cols = ["roi_x0", "roi_y0", "roi_x1", "roi_y1"]
    if all(c in row.index and pd.notna(row[c]) for c in cols):
        x0, y0, x1, y1 = [int(round(float(row[c]))) for c in cols]
        x0 = max(0, min(w - 1, x0))
        y0 = max(0, min(h - 1, y0))
        x1 = max(x0 + 1, min(w, x1))
        y1 = max(y0 + 1, min(h, y1))
        return x0, y0, x1, y1
    return 0, 0, w, h


def frame_key(row):
    return (str(row["case_id"]), float(row["sample_time_sec"]))


def mask_path(mask_dir: Path, row) -> Path:
    case_id = str(row["case_id"])
    t = int(round(float(row["sample_time_sec"])))
    return mask_dir / f"{case_id}__t{t:06d}.png"


def load_or_init_mask(path: Path, shape_hw):
    h, w = shape_hw
    if path.exists():
        m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if m is not None and m.shape == (h, w):
            return m
    return np.zeros((h, w), dtype=np.uint8)


def overlay_mask(img, mask):
    out = img.copy()
    overlay = out.copy()
    blood = mask == BLOOD
    non = mask == NON_BLOOD
    overlay[blood] = (0, 0, 255)       # red
    overlay[non] = (255, 255, 0)       # cyan
    any_lab = blood | non
    alpha = 0.38
    if np.any(any_lab):
        blended = cv2.addWeighted(out, 1.0 - alpha, overlay, alpha, 0)
        out[any_lab] = blended[any_lab]
    return out


def load_qc(path: Path):
    if path.exists():
        q = pd.read_csv(path)
        if len(q):
            return q
    return pd.DataFrame(
        columns=[
            "case_id",
            "sample_time_sec",
            "image_path",
            "selection_stratum",
            "frame_status",
            "exclusion_reason",
            "painted_blood_pixels",
            "painted_non_blood_pixels",
        ]
    )


def upsert_qc(qc: pd.DataFrame, record: dict):
    key_case = str(record["case_id"])
    key_t = float(record["sample_time_sec"])
    if len(qc):
        mask = (
            qc["case_id"].astype(str).eq(key_case)
            & pd.to_numeric(qc["sample_time_sec"], errors="coerce").eq(key_t)
        )
        qc = qc.loc[~mask].copy()
    return pd.concat([qc, pd.DataFrame([record])], ignore_index=True)


def save_qc(qc: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    qc.sort_values(["case_id", "sample_time_sec"]).to_csv(
        path, index=False, encoding="utf-8-sig"
    )


def completed_keys(qc: pd.DataFrame):
    if qc.empty:
        return set()
    z = qc[qc["frame_status"].isin(["annotated", "excluded"])].copy()
    return {
        (str(r["case_id"]), float(r["sample_time_sec"]))
        for _, r in z.iterrows()
    }


def export_pixels_for_frame(row, crop, mask, max_per_class, seed):
    red = crop[:, :, 2].astype(np.float32)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)

    fr = float(red.mean())
    fg = float(gray.mean())
    frame_ratio = fg / fr if fr > 0 else np.nan

    rng_seed = (
        int(seed)
        + sum(ord(c) for c in str(row["case_id"]))
        + int(round(float(row["sample_time_sec"])))
    )
    rng = np.random.default_rng(rng_seed)

    rows = []
    for mask_value, label, label_name in [
        (BLOOD, 1, "blood"),
        (NON_BLOOD, 0, "non_blood"),
    ]:
        yy, xx = np.where(mask == mask_value)
        n_total = len(xx)
        if n_total == 0:
            continue

        if n_total > max_per_class:
            keep = rng.choice(n_total, size=max_per_class, replace=False)
            yy = yy[keep]
            xx = xx[keep]

        for y, x in zip(yy, xx):
            b, g, r = [int(v) for v in crop[y, x]]
            gy = int(gray[y, x])
            rows.append(
                {
                    "case_id": str(row["case_id"]),
                    "sample_time_sec": float(row["sample_time_sec"]),
                    "image_path": str(row["image_path"]),
                    "selection_stratum": str(row.get("selection_stratum", "")),
                    "label": int(label),
                    "label_name": label_name,
                    "x_roi": int(x),
                    "y_roi": int(y),
                    "pixel_r": r,
                    "pixel_g": g,
                    "pixel_b": b,
                    "pixel_gray": gy,
                    "frame_red_mean_roi": fr,
                    "frame_gray_mean_roi": fg,
                    "pixel_gray_over_red": (gy / r if r > 0 else np.nan),
                    "frame_gray_over_red": frame_ratio,
                    "painted_pixels_in_class_frame": int(n_total),
                }
            )
    return rows


def rebuild_export(man, qc, mask_dir, output_csv, max_per_class, seed):
    annotated = set()
    if len(qc):
        q = qc[qc["frame_status"].eq("annotated")]
        annotated = {
            (str(r["case_id"]), float(r["sample_time_sec"]))
            for _, r in q.iterrows()
        }

    rows = []
    for _, row in man.iterrows():
        if frame_key(row) not in annotated:
            continue

        path = Path(str(row["image_path"]))
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            continue

        h, w = img.shape[:2]
        x0, y0, x1, y1 = roi_bounds(row, w, h)
        crop = img[y0:y1, x0:x1].copy()

        mp = mask_path(mask_dir, row)
        if not mp.exists():
            continue
        mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        if mask is None or mask.shape != crop.shape[:2]:
            continue

        rows.extend(
            export_pixels_for_frame(
                row, crop, mask, max_per_class, seed
            )
        )

    out = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return out


def main():
    a = parse_args()
    if a.frame_qc_csv is None:
        a.frame_qc_csv = a.output_csv.with_name(
            a.output_csv.stem + "_frame_qc.csv"
        )

    man = pd.read_csv(a.manifest)
    required = {"case_id", "sample_time_sec", "image_path"}
    missing = required - set(man.columns)
    if missing:
        raise ValueError(f"Manifest missing columns: {sorted(missing)}")

    a.mask_dir.mkdir(parents=True, exist_ok=True)
    qc = load_qc(a.frame_qc_csv)

    idx = 0
    mode = BLOOD
    brush_radius = max(1, int(a.brush_radius))
    drawing = False

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)

    while idx < len(man):
        row = man.iloc[idx]
        key = frame_key(row)

        if not a.revisit_completed and key in completed_keys(qc):
            idx += 1
            continue

        path = Path(str(row["image_path"]))
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            qc = upsert_qc(
                qc,
                {
                    "case_id": str(row["case_id"]),
                    "sample_time_sec": float(row["sample_time_sec"]),
                    "image_path": str(path),
                    "selection_stratum": str(row.get("selection_stratum", "")),
                    "frame_status": "excluded",
                    "exclusion_reason": "missing_or_unreadable_image",
                    "painted_blood_pixels": 0,
                    "painted_non_blood_pixels": 0,
                },
            )
            save_qc(qc, a.frame_qc_csv)
            idx += 1
            continue

        h, w = img.shape[:2]
        x0, y0, x1, y1 = roi_bounds(row, w, h)
        crop = img[y0:y1, x0:x1].copy()
        ch, cw = crop.shape[:2]

        mp = mask_path(a.mask_dir, row)
        mask = load_or_init_mask(mp, (ch, cw))

        scale = min(1.0, a.display_width / float(cw))
        dw = int(round(cw * scale))
        dh = int(round(ch * scale))

        def mode_name():
            return {
                BLOOD: "BLOOD",
                NON_BLOOD: "NON-BLOOD",
                UNLABELED: "ERASER",
            }[mode]

        def paint_at(dx, dy):
            nonlocal mask
            rx = int(round(dx / scale))
            ry = int(round((dy - 126) / scale))
            if not (0 <= rx < cw and 0 <= ry < ch):
                return
            rr = max(1, int(round(brush_radius / scale)))
            cv2.circle(mask, (rx, ry), rr, int(mode), -1)

        def on_mouse(event, x, y, flags, param):
            nonlocal drawing, mode
            if y < 126:
                return
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                paint_at(x, y)
            elif event == cv2.EVENT_MOUSEMOVE and drawing:
                paint_at(x, y)
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                paint_at(x, y)
            elif event == cv2.EVENT_RBUTTONDOWN:
                old_mode = mode
                mode = UNLABELED
                paint_at(x, y)
                mode = old_mode
            elif event == cv2.EVENT_RBUTTONUP:
                drawing = False

        cv2.setMouseCallback(WINDOW, on_mouse)

        while True:
            vis = overlay_mask(crop, mask)
            disp = cv2.resize(
                vis, (dw, dh), interpolation=cv2.INTER_AREA
            )

            top = 126
            canvas = np.zeros((dh + top, dw, 3), dtype=np.uint8)
            canvas[top:] = disp

            blood_n = int(np.sum(mask == BLOOD))
            non_n = int(np.sum(mask == NON_BLOOD))

            line1 = (
                f"{idx+1}/{len(man)}  {row['case_id']}  "
                f"t={float(row['sample_time_sec']):.0f}s  "
                f"mode={mode_name()}  brush={brush_radius}px"
            )
            line2 = (
                f"painted: blood={blood_n} non-blood={non_n} | "
                "drag LMB=paint, RMB=erase"
            )
            line3 = (
                "b=blood n=non-blood e=eraser [ ]=brush c=clear "
                "s=ANNOTATED k=temp-skip p=prev q=quit"
            )
            line4 = (
                "EXCLUDE: 1=blur 2=lens-dirt 3=near-contact/occlusion "
                "4=dark/exposure 5=smoke/fog 6=other-ungradable"
            )

            for txt, y in [
                (line1, 25),
                (line2, 52),
                (line3, 79),
                (line4, 106),
            ]:
                cv2.putText(
                    canvas, txt, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.46 if y > 52 else 0.55,
                    (255, 255, 255),
                    1 if y > 25 else 2,
                    cv2.LINE_AA,
                )

            cv2.imshow(WINDOW, canvas)
            k = cv2.waitKey(30) & 0xFF

            if k == 255:
                continue
            if k in (ord("b"), ord("B")):
                mode = BLOOD
            elif k in (ord("n"), ord("N")):
                mode = NON_BLOOD
            elif k in (ord("e"), ord("E")):
                mode = UNLABELED
            elif k == ord("["):
                brush_radius = max(2, brush_radius - 3)
            elif k == ord("]"):
                brush_radius = min(120, brush_radius + 3)
            elif k in (ord("c"), ord("C")):
                mask[:] = UNLABELED

            elif k in (ord("s"), ord("S"), 13, 32):
                blood_n = int(np.sum(mask == BLOOD))
                non_n = int(np.sum(mask == NON_BLOOD))
                if blood_n == 0 and non_n == 0:
                    print(
                        "[WARN] No pixels painted. Paint at least one class, "
                        "or exclude/temporarily skip the frame."
                    )
                    continue

                cv2.imwrite(str(mp), mask)
                qc = upsert_qc(
                    qc,
                    {
                        "case_id": str(row["case_id"]),
                        "sample_time_sec": float(row["sample_time_sec"]),
                        "image_path": str(path),
                        "selection_stratum": str(row.get("selection_stratum", "")),
                        "frame_status": "annotated",
                        "exclusion_reason": "",
                        "painted_blood_pixels": blood_n,
                        "painted_non_blood_pixels": non_n,
                    },
                )
                save_qc(qc, a.frame_qc_csv)
                idx += 1
                break

            elif k in EXCLUSION_KEYS:
                reason = EXCLUSION_KEYS[k]
                if mp.exists():
                    mp.unlink()
                qc = upsert_qc(
                    qc,
                    {
                        "case_id": str(row["case_id"]),
                        "sample_time_sec": float(row["sample_time_sec"]),
                        "image_path": str(path),
                        "selection_stratum": str(row.get("selection_stratum", "")),
                        "frame_status": "excluded",
                        "exclusion_reason": reason,
                        "painted_blood_pixels": 0,
                        "painted_non_blood_pixels": 0,
                    },
                )
                save_qc(qc, a.frame_qc_csv)
                idx += 1
                break

            elif k in (ord("k"), ord("K")):
                # Temporary skip only: not marked complete.
                cv2.imwrite(str(mp), mask)
                idx += 1
                break

            elif k in (ord("p"), ord("P")):
                cv2.imwrite(str(mp), mask)
                idx = max(0, idx - 1)
                break

            elif k in (ord("q"), ord("Q"), 27):
                cv2.imwrite(str(mp), mask)
                idx = len(man)
                break

    cv2.destroyAllWindows()

    out = rebuild_export(
        man=man,
        qc=qc,
        mask_dir=a.mask_dir,
        output_csv=a.output_csv,
        max_per_class=a.pixels_per_class_per_frame,
        seed=a.seed,
    )

    print()
    print("Saved masks:", a.mask_dir)
    print("Saved frame QC:", a.frame_qc_csv)
    print("Saved sampled pixels:", a.output_csv)

    if len(qc):
        print()
        print("=== Frame QC ===")
        print(qc["frame_status"].value_counts(dropna=False).to_string())
        exc = qc[qc["frame_status"].eq("excluded")]
        if len(exc):
            print()
            print("=== Exclusion reasons ===")
            print(exc["exclusion_reason"].value_counts(dropna=False).to_string())

    if len(out):
        print()
        print("=== Exported pixel labels ===")
        print(out["label_name"].value_counts().to_string())
        print(
            "Annotated frames:",
            out[["case_id", "sample_time_sec"]].drop_duplicates().shape[0],
        )
        print("Cases:", out["case_id"].nunique())
    else:
        print("[WARN] No exported pixel labels yet.")


if __name__ == "__main__":
    main()
