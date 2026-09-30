#!/usr/bin/env python
from __future__ import annotations

import argparse
import gc
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch


def install_torch26_checkpoint_compat():
    """Allow trusted legacy MMEngine checkpoints under PyTorch >=2.6.

    PyTorch 2.6 changed torch.load(weights_only) default from False to True.
    MMEngine 0.10.x checkpoints may contain metadata objects such as
    HistoryBuffer, so loading the user's own trusted training checkpoints
    requires weights_only=False.
    """
    original_torch_load = torch.load

    def torch_load_compat(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = torch_load_compat


REF_W = 1920
REF_H = 1080
REF_ROI = (395, 101, 1528, 889)
ROI_FRACS = (
    REF_ROI[0] / REF_W,
    REF_ROI[1] / REF_H,
    REF_ROI[2] / REF_W,
    REF_ROI[3] / REF_H,
)


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Apply the existing 5-fold Level-0 Swin classifiers to neo 1-Hz frames, "
            "ensemble fold probabilities, exclude OutsideBody frames, and create "
            "minimal per-case CSVs compatible with the visual-hazard metric pipeline."
        )
    )
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--surgcap-root", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--metric-input-dir", required=True, type=Path)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--outside-class-index",
        type=int,
        default=None,
        help=(
            "Optional explicit numeric class index for OutsideBody. "
            "If omitted, infer from data/prepared/csv/level0.csv and fold test annotations."
        ),
    )
    p.add_argument(
        "--checkpoint-policy",
        choices=["latest-best"],
        default="latest-best",
        help="Checkpoint selection policy per fold. Current policy: newest mtime among best_accuracy_top1_epoch_*.pth.",
    )
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Resolve class mapping and checkpoints, print them, then exit before inference.")
    return p.parse_args()


def canonical_semantic(x: object) -> str | None:
    s = str(x).strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    if "outsidebody" in s or s == "outside":
        return "OutsideBody"
    if "insidebody" in s or s == "inside":
        return "InsideBody"
    return None


def choose_column(columns, candidates):
    lower = {str(c).lower(): c for c in columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def load_level0_semantic_table(csv_path: Path) -> pd.DataFrame:
    d = pd.read_csv(csv_path)
    if d.shape[1] < 3:
        raise RuntimeError(f"Expected >=3 columns in {csv_path}; found {d.shape[1]}")

    case_col = choose_column(
        d.columns, ["case_id", "case", "case_uid", "caseid"]
    )
    time_col = choose_column(
        d.columns,
        [
            "sample_time_sec", "time_sec", "second", "seconds", "sec",
            "frame_idx_0based", "frame_index_0based", "time"
        ],
    )
    label_col = choose_column(
        d.columns, ["label", "level0", "level0_label", "class", "target"]
    )

    # Fallback to the first three columns; the known file has case, integer second, semantic label.
    cols = list(d.columns)
    if case_col is None:
        case_col = cols[0]
    if time_col is None:
        time_col = cols[1]
    if label_col is None:
        label_col = cols[2]

    out = d[[case_col, time_col, label_col]].copy()
    out.columns = ["case_id", "time_key", "semantic_label"]
    out["case_id"] = out["case_id"].astype(str).str.upper().str.strip()
    out["time_key"] = pd.to_numeric(out["time_key"], errors="coerce")
    out["semantic_label"] = out["semantic_label"].map(canonical_semantic)
    out = out.dropna(subset=["time_key", "semantic_label"])
    out["time_key"] = out["time_key"].round().astype(int)
    return out


FRAME_RE = re.compile(r"frame_(\d+)", re.IGNORECASE)


def parse_test_annotation(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.rsplit(maxsplit=1)
            if len(parts) != 2:
                continue
            rel, lab = parts
            try:
                numeric_label = int(lab)
            except ValueError:
                continue
            rel_norm = rel.replace("\\", "/")
            case_id = rel_norm.split("/")[0].upper()
            m = FRAME_RE.search(Path(rel_norm).name)
            if m is None:
                continue
            frame_1based = int(m.group(1))
            # 1-Hz historical convention: frame_000001 corresponds to t=0 s.
            time_key = frame_1based - 1
            rows.append(
                {
                    "case_id": case_id,
                    "time_key": time_key,
                    "numeric_label": numeric_label,
                    "annotation_path": str(path),
                }
            )
    return pd.DataFrame(rows)


def infer_numeric_mapping(surgcap_root: Path) -> tuple[dict[int, str], pd.DataFrame]:
    semantic_path = surgcap_root / "data" / "prepared" / "csv" / "level0.csv"
    if not semantic_path.exists():
        raise FileNotFoundError(semantic_path)
    sem = load_level0_semantic_table(semantic_path)

    ann_frames = []
    for fold in range(5):
        p = (
            surgcap_root
            / "outputs"
            / "level0"
            / f"cv{fold}"
            / "_normalized"
            / f"test_cv{fold}.txt"
        )
        if p.exists():
            x = parse_test_annotation(p)
            if not x.empty:
                x["fold"] = fold
                ann_frames.append(x)

    if not ann_frames:
        raise RuntimeError("Could not find/parse any Level-0 fold test annotations.")

    ann = pd.concat(ann_frames, ignore_index=True)
    joined = ann.merge(sem, on=["case_id", "time_key"], how="inner")
    if joined.empty:
        raise RuntimeError(
            "Could not join numeric fold annotations to semantic Level-0 CSV. "
            "Use --outside-class-index explicitly if needed."
        )

    ct = (
        joined.groupby(["numeric_label", "semantic_label"])
        .size()
        .rename("n")
        .reset_index()
    )
    mapping = {}
    for numeric, g in ct.groupby("numeric_label"):
        g = g.sort_values("n", ascending=False)
        top = g.iloc[0]
        total = int(g["n"].sum())
        purity = float(top["n"] / total)
        if purity < 0.95:
            raise RuntimeError(
                f"Ambiguous semantic mapping for numeric label {numeric}: "
                f"{g.to_dict('records')}"
            )
        mapping[int(numeric)] = str(top["semantic_label"])

    needed = {"InsideBody", "OutsideBody"}
    if set(mapping.values()) != needed:
        raise RuntimeError(f"Unexpected Level-0 mapping inferred: {mapping}")

    ct["mapping_source"] = "join(test_cv*.txt, level0.csv)"
    return mapping, ct


def select_checkpoints(surgcap_root: Path) -> pd.DataFrame:
    rows = []
    for fold in range(5):
        fold_dir = surgcap_root / "outputs" / "level0" / f"cv{fold}"
        config = fold_dir / "swin_small_rect.py"
        if not config.exists():
            raise FileNotFoundError(config)

        candidates = sorted(
            fold_dir.glob("best_accuracy_top1_epoch_*.pth"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(
                f"No best_accuracy_top1_epoch_*.pth under {fold_dir}"
            )
        chosen = candidates[0]
        rows.append(
            {
                "fold": fold,
                "config_path": str(config),
                "checkpoint_path": str(chosen),
                "checkpoint_mtime": pd.Timestamp.fromtimestamp(
                    chosen.stat().st_mtime
                ).isoformat(),
                "n_best_candidates_in_fold": len(candidates),
                "all_best_candidates": " | ".join(str(p) for p in candidates),
            }
        )
    return pd.DataFrame(rows)


def import_inferencer():
    try:
        from mmpretrain import ImageClassificationInferencer
        return ImageClassificationInferencer
    except Exception:
        from mmpretrain.apis import ImageClassificationInferencer
        return ImageClassificationInferencer


def extract_scores_one_result(r: dict, n_classes: int = 2):
    scores = r.get("pred_scores", None)
    if scores is not None:
        arr = np.asarray(scores, dtype=float).reshape(-1)
        if len(arr) != n_classes:
            raise RuntimeError(f"Expected {n_classes} pred_scores; got {len(arr)}")
        return arr

    # Fallback only if this mmpretrain result omits full scores.
    pred_label = r.get("pred_label", None)
    pred_score = r.get("pred_score", None)
    if pred_label is None:
        raise RuntimeError(f"Could not parse inference result keys: {list(r.keys())}")
    pred_label = int(pred_label)
    arr = np.zeros(n_classes, dtype=float)
    if pred_score is None:
        arr[pred_label] = 1.0
    else:
        top = float(pred_score)
        arr[pred_label] = top
        if n_classes == 2:
            arr[1 - pred_label] = 1.0 - top
    return arr


def run_fold(
    inferencer_cls,
    config_path: str,
    checkpoint_path: str,
    image_paths: list[str],
    device: str,
    batch_size: int,
) -> np.ndarray:
    print(f"Loading model: {checkpoint_path}")
    inferencer = inferencer_cls(
        model=config_path,
        pretrained=checkpoint_path,
        device=device,
    )

    all_scores = []
    n = len(image_paths)
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        chunk = image_paths[start:end]
        results = inferencer(chunk, batch_size=len(chunk))
        if isinstance(results, dict):
            results = [results]
        for r in results:
            all_scores.append(extract_scores_one_result(r, n_classes=2))
        if end == n or (start // batch_size) % 20 == 0:
            print(f"  inferred {end}/{n}")

    scores = np.vstack(all_scores)
    del inferencer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return scores


def scaled_roi(width: int, height: int) -> tuple[int, int, int, int]:
    x0f, y0f, x1f, y1f = ROI_FRACS
    x0 = int(round(width * x0f))
    y0 = int(round(height * y0f))
    x1 = int(round(width * x1f))
    y1 = int(round(height * y1f))
    x0 = max(0, min(x0, width - 1))
    y0 = max(0, min(y0, height - 1))
    x1 = max(x0 + 1, min(x1, width))
    y1 = max(y0 + 1, min(y1, height))
    return x0, y0, x1, y1


def build_metric_inputs(inbody: pd.DataFrame, metric_input_dir: Path):
    metric_input_dir.mkdir(parents=True, exist_ok=True)
    written = []

    for case_id, g in inbody.groupby("case_id", sort=True):
        g = g.sort_values("sample_time_sec").copy()
        rows = []
        for _, r in g.iterrows():
            w = int(r["source_width"])
            h = int(r["source_height"])
            x0, y0, x1, y1 = scaled_roi(w, h)
            rows.append(
                {
                    "case_id": case_id,
                    "sample_ordinal": int(r["frame_index_1based"]),
                    "segment_id": f"{case_id}_NEO",
                    "sample_time_sec": float(r["sample_time_sec"]),
                    "frame_idx_1based": int(r["frame_index_1based"]),
                    "image_file": Path(str(r["frame_path"])).name,
                    "image_path": str(r["frame_path"]),
                    "image_width_full": w,
                    "image_height_full": h,
                    "roi_x0": x0,
                    "roi_y0": y0,
                    "roi_x1": x1,
                    "roi_y1": y1,
                    "image_width_roi": x1 - x0,
                    "image_height_roi": y1 - y0,
                    "level0_pred_semantic": r["level0_pred_semantic"],
                    "level0_ensemble_confidence": float(
                        r["level0_ensemble_confidence"]
                    ),
                    "level0_p_outside": float(r["level0_p_outside"]),
                    "level0_p_inside": float(r["level0_p_inside"]),
                }
            )
        out = pd.DataFrame(rows)
        path = metric_input_dir / f"{case_id}_frame_scores.csv"
        out.to_csv(path, index=False, encoding="utf-8-sig")
        written.append((case_id, len(out), str(path)))
    return pd.DataFrame(written, columns=["case_id", "n_inbody_rows", "metric_input_csv"])


def main():
    args = parse_args()
    install_torch26_checkpoint_compat()
    print("[compat] torch.load default forced to weights_only=False for trusted local checkpoints.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.metric_input_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(args.manifest)
    required = {
        "case_id", "sample_time_sec", "frame_index_1based", "frame_path",
        "extract_ok", "source_width", "source_height",
    }
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError(f"Manifest missing columns: {sorted(missing)}")

    if manifest["extract_ok"].dtype != bool:
        manifest["extract_ok"] = (
            manifest["extract_ok"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    d = manifest.loc[manifest["extract_ok"]].copy()
    if d.empty:
        raise RuntimeError("No successfully extracted frames in manifest.")
    d["case_id"] = d["case_id"].astype(str)
    d = d.sort_values(["case_id", "sample_time_sec"]).reset_index(drop=True)

    missing_images = [p for p in d["frame_path"].astype(str) if not Path(p).exists()]
    if missing_images:
        raise FileNotFoundError(
            f"{len(missing_images)} manifest images are missing. First: {missing_images[0]}"
        )

    # Resolve semantic class mapping.
    if args.outside_class_index is None:
        mapping, mapping_counts = infer_numeric_mapping(args.surgcap_root)
    else:
        outside_idx = int(args.outside_class_index)
        if outside_idx not in (0, 1):
            raise ValueError("--outside-class-index must be 0 or 1")
        mapping = {
            outside_idx: "OutsideBody",
            1 - outside_idx: "InsideBody",
        }
        mapping_counts = pd.DataFrame(
            [
                {
                    "numeric_label": k,
                    "semantic_label": v,
                    "n": np.nan,
                    "mapping_source": "explicit_cli_override",
                }
                for k, v in mapping.items()
            ]
        )

    outside_idx = [k for k, v in mapping.items() if v == "OutsideBody"][0]
    inside_idx = [k for k, v in mapping.items() if v == "InsideBody"][0]

    print("Resolved Level-0 mapping:", mapping)
    mapping_counts.to_csv(
        args.output_dir / "level0_label_mapping_evidence.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Freeze checkpoint selection before inference.
    ckpts = select_checkpoints(args.surgcap_root)
    ckpts.to_csv(
        args.output_dir / "level0_checkpoint_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print()
    print("Selected checkpoints:")
    print(
        ckpts[
            ["fold", "checkpoint_path", "checkpoint_mtime", "n_best_candidates_in_fold"]
        ].to_string(index=False)
    )

    if args.dry_run:
        print()
        print("Dry run complete: no inference was performed.")
        return

    inferencer_cls = import_inferencer()
    image_paths = d["frame_path"].astype(str).tolist()

    fold_scores = {}
    for _, r in ckpts.iterrows():
        fold = int(r["fold"])
        scores = run_fold(
            inferencer_cls=inferencer_cls,
            config_path=str(r["config_path"]),
            checkpoint_path=str(r["checkpoint_path"]),
            image_paths=image_paths,
            device=args.device,
            batch_size=args.batch_size,
        )
        fold_scores[fold] = scores
        d[f"level0_p_class0_cv{fold}"] = scores[:, 0]
        d[f"level0_p_class1_cv{fold}"] = scores[:, 1]

    stack = np.stack([fold_scores[i] for i in sorted(fold_scores)], axis=0)
    mean_scores = stack.mean(axis=0)
    pred_numeric = mean_scores.argmax(axis=1)
    confidence = mean_scores.max(axis=1)

    d["level0_p_class0_mean"] = mean_scores[:, 0]
    d["level0_p_class1_mean"] = mean_scores[:, 1]
    d["level0_pred_numeric"] = pred_numeric
    d["level0_pred_semantic"] = [mapping[int(x)] for x in pred_numeric]
    d["level0_ensemble_confidence"] = confidence
    d["level0_p_outside"] = mean_scores[:, outside_idx]
    d["level0_p_inside"] = mean_scores[:, inside_idx]
    d["inside_body"] = d["level0_pred_semantic"].eq("InsideBody")
    d["outside_body"] = d["level0_pred_semantic"].eq("OutsideBody")
    d["low_confidence_lt_0_80"] = d["level0_ensemble_confidence"] < 0.80

    pred_path = args.output_dir / "neo_level0_ensemble_predictions.csv"
    if pred_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"{pred_path} already exists. Use --overwrite to replace."
        )
    d.to_csv(pred_path, index=False, encoding="utf-8-sig")

    inbody = d.loc[d["inside_body"]].copy()
    inbody_path = args.output_dir / "neo_level0_inbody_manifest.csv"
    inbody.to_csv(inbody_path, index=False, encoding="utf-8-sig")

    summary = (
        d.groupby("case_id", as_index=False)
        .agg(
            n_frames=("case_id", "size"),
            n_inside=("inside_body", "sum"),
            n_outside=("outside_body", "sum"),
            n_low_confidence_lt_0_80=("low_confidence_lt_0_80", "sum"),
            median_ensemble_confidence=("level0_ensemble_confidence", "median"),
            mean_p_outside=("level0_p_outside", "mean"),
        )
    )
    summary["inside_fraction"] = summary["n_inside"] / summary["n_frames"]
    summary["outside_fraction"] = summary["n_outside"] / summary["n_frames"]
    summary.to_csv(
        args.output_dir / "neo_level0_case_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    metric_inputs = build_metric_inputs(inbody, args.metric_input_dir)
    metric_inputs.to_csv(
        args.output_dir / "neo_metric_input_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=== Level-0 case summary ===")
    print(summary.to_string(index=False))
    print()
    print("=== Metric-input CSVs ===")
    print(metric_inputs.to_string(index=False))
    print()
    print("Saved:", pred_path)
    print("Saved:", inbody_path)
    print("Metric input dir:", args.metric_input_dir)
    print()
    print("Reference fractional ROI:")
    print(
        f"x0={ROI_FRACS[0]:.9f}, y0={ROI_FRACS[1]:.9f}, "
        f"x1={ROI_FRACS[2]:.9f}, y1={ROI_FRACS[3]:.9f}"
    )


if __name__ == "__main__":
    main()
