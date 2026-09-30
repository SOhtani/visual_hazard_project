#!/usr/bin/env python
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import pandas as pd


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def parse_args():
    p = argparse.ArgumentParser(
        description="Inventory neo videos and extract native-resolution frames at 1 Hz."
    )
    p.add_argument("--video-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def safe_float(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(
        p for p in args.video_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )
    if not videos:
        raise FileNotFoundError(f"No videos found under {args.video_dir}")

    inventory_rows = []
    manifest_rows = []

    for video in videos:
        case_id = video.stem
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            inventory_rows.append({
                "case_id": case_id,
                "video_path": str(video),
                "open_ok": False,
                "width": None,
                "height": None,
                "fps": None,
                "frame_count": None,
                "duration_sec": None,
                "n_extracted": 0,
            })
            continue

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = safe_float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = safe_float(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        duration_sec = None
        if fps and fps > 0 and frame_count is not None and frame_count >= 0:
            duration_sec = frame_count / fps

        if duration_sec is None or duration_sec <= 0:
            cap.release()
            raise RuntimeError(f"Could not determine duration for {video}")

        max_t = max(0, int(math.floor(duration_sec - 1e-6)))
        frame_dir = args.output_dir / "frames" / case_id
        frame_dir.mkdir(parents=True, exist_ok=True)

        extracted = 0
        for t in range(max_t + 1):
            out_path = frame_dir / f"frame_{t + 1:06d}.png"

            if out_path.exists() and not args.overwrite:
                ok = True
            else:
                cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
                ok, frame = cap.read()
                if ok and frame is not None:
                    ok = bool(cv2.imwrite(str(out_path), frame))

            manifest_rows.append({
                "case_id": case_id,
                "video_path": str(video),
                "sample_time_sec": float(t),
                "frame_index_1based": t + 1,
                "frame_path": str(out_path),
                "extract_ok": bool(ok),
                "source_width": width,
                "source_height": height,
            })
            extracted += int(bool(ok))

        cap.release()

        inventory_rows.append({
            "case_id": case_id,
            "video_path": str(video),
            "open_ok": True,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration_sec": duration_sec,
            "n_requested": max_t + 1,
            "n_extracted": extracted,
        })

        print(
            f"{case_id}: {width}x{height}, "
            f"duration={duration_sec:.1f}s, extracted={extracted}/{max_t + 1}"
        )

    inventory = pd.DataFrame(inventory_rows)
    manifest = pd.DataFrame(manifest_rows)

    inventory_path = args.output_dir / "neo_video_inventory.csv"
    manifest_path = args.output_dir / "neo_frames_1fps_manifest.csv"
    inventory.to_csv(inventory_path, index=False, encoding="utf-8-sig")
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    print()
    print("=== QC ===")
    print("videos:", len(inventory))
    print("opened:", int(inventory["open_ok"].fillna(False).sum()))
    if not manifest.empty:
        print("frame rows:", len(manifest))
        print("extract_ok:", int(manifest["extract_ok"].sum()))
        print("extract_failed:", int((~manifest["extract_ok"]).sum()))
        print()
        print("source resolution counts:")
        print(
            inventory.groupby(["width", "height"], dropna=False)
            .size()
            .rename("n_videos")
            .to_string()
        )
    print()
    print("Saved:", inventory_path)
    print("Saved:", manifest_path)


if __name__ == "__main__":
    main()
