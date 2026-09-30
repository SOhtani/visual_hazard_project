
import json
import os
import pandas as pd
import importlib.util
from pathlib import Path
from scipy import stats

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
spec = importlib.util.spec_from_file_location("bloodqc", str(VH / "scripts" / "phase05_apply_rats_blood_rule_visual_qc_gradable.py"))
bloodqc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / "reports" / "phase05_rats_blood_pixel_recalibration" / "rats_recalibrated_blood_pixel_rule.csv")
gate = bloodqc.load_gradability_gate(VH / "data" / "annotations" / "rats_blood_pixel_pilot_v2" / "rats_blood_pixel_annotation_v2_gradability_gate.csv")

neo_dir = Path(os.environ["NEO_DIR"])
qm_dir = VH / "data" / "derived" / "neo_quality_metrics" / "per_frame"

summaries = []
qc_rows = []
for ann_path in sorted(neo_dir.glob("*_annotation_v2.json")):
    case_id = ann_path.stem.replace("_annotation_v2", "")
    ann = json.loads(ann_path.read_text(encoding="utf-8"))
    segs = ann.get("active_annotation", {}).get("segments", [])
    sp_segs = [s for s in segs if s.get("level") == "Level-1" and s.get("label") == "SpecimenPathway"]
    print(case_id, "SpecimenPathway segments:", len(sp_segs))
    if not sp_segs:
        qc_rows.append({"case_id": case_id, "n_specimenpathway_frames": 0, "n_gradable_frames": 0})
        continue
    metrics_path = qm_dir / (case_id + "_frame_scores.csv")
    if not metrics_path.exists():
        print("  metrics file not found:", metrics_path)
        continue
    d = bloodqc.load_case(metrics_path)
    mask = pd.Series(False, index=d.index)
    for seg in sp_segs:
        mask = mask | ((d["sample_time_sec"] >= seg["start_sec"]) & (d["sample_time_sec"] <= seg["end_sec"]))
    d_sp = d.loc[mask].copy()
    n_sp = len(d_sp)
    gated = bloodqc.apply_gradability_gate(d_sp, gate)
    n_gradable = len(gated)
    qc_rows.append({"case_id": case_id, "n_specimenpathway_frames": n_sp, "n_gradable_frames": n_gradable})
    if n_gradable == 0:
        continue
    scored = bloodqc.score_case(gated, rats_rule, quiet=True)
    if len(scored) == 0:
        continue
    summary = bloodqc.case_summary(scored)
    summaries.append(summary)

out_dir = VH / "reports" / "phase05_specimenpathway_blood_burden_neo"
out_dir.mkdir(parents=True, exist_ok=True)
summary_df = pd.DataFrame(summaries)
summary_df.to_csv(out_dir / "case_specimenpathway_blood_pbp_summary_neo.csv", index=False)
qc_df = pd.DataFrame(qc_rows)
qc_df.to_csv(out_dir / "specimenpathway_frame_count_qc_neo.csv", index=False)

print()
print("=== neo case-level summary ===")
print(summary_df.to_string(index=False))

ref = pd.read_csv(VH / "reports" / "phase05_specimenpathway_blood_burden" / "case_specimenpathway_blood_pbp_summary.csv")
print()
print("=== reference (n=%d) medians ===" % len(ref))
print(ref[["rats_mean_pbp", "rats_median_pbp", "rats_p90_pbp"]].median())
print()
print("=== neo (n=%d) medians ===" % len(summary_df))
print(summary_df[["rats_mean_pbp", "rats_median_pbp", "rats_p90_pbp"]].median())

if len(summary_df) > 0:
    mw = stats.mannwhitneyu(ref["rats_median_pbp"], summary_df["rats_median_pbp"])
    print()
    print("Mann-Whitney reference vs neo (rats_median_pbp): p=%.4f" % mw.pvalue)