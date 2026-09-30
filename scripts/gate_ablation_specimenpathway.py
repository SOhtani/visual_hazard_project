import importlib.util
import pandas as pd
from pathlib import Path

VH = Path(r'C:\Users\SOhtani2024\visual_hazard_project')

spec = importlib.util.spec_from_file_location('bloodqc', str(VH / 'scripts' / 'phase05_apply_rats_blood_rule_visual_qc_gradable.py'))
bloodqc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / 'reports' / 'phase05_rats_blood_pixel_recalibration' / 'rats_recalibrated_blood_pixel_rule.csv')
gate = bloodqc.load_gradability_gate(VH / 'data' / 'annotations' / 'rats_blood_pixel_pilot_v2' / 'rats_blood_pixel_annotation_v2_gradability_gate.csv')

flags = pd.read_csv(VH / 'reports' / 'visual_hazard_burden' / 'visual_hazard_frame_flags.csv', usecols=['case_id', 'sample_time_sec', 'workflow_level1_label'])
flags['sample_time_sec'] = pd.to_numeric(flags['sample_time_sec'], errors='coerce')

case_paths = bloodqc.case_files(VH / 'data' / 'derived' / 'quality_metrics' / 'per_frame')

rows = []
for idx, path in enumerate(case_paths, 1):
    case_id = bloodqc.case_id_from_file(path)
    print(idx, '/', len(case_paths), case_id)
    d = bloodqc.load_case(path)
    case_flags = flags[flags['case_id'] == case_id]
    merged = d.merge(case_flags[['sample_time_sec', 'workflow_level1_label']], on='sample_time_sec', how='left')
    sp = merged[merged['workflow_level1_label'] == 'SpecimenPathway'].copy()
    if len(sp) == 0:
        continue

    ungated_scored = bloodqc.score_case(sp, rats_rule, quiet=True)

    gated = bloodqc.apply_gradability_gate(sp, gate)
    if len(gated) > 0:
        gated_scored = bloodqc.score_case(gated, rats_rule, quiet=True)
    else:
        gated_scored = ungated_scored.iloc[0:0]

    excluded_idx = sp.index.difference(gated.index)
    excluded_frames = sp.loc[excluded_idx]
    if len(excluded_frames) > 0:
        excluded_scored = bloodqc.score_case(excluded_frames, rats_rule, quiet=True)
    else:
        excluded_scored = ungated_scored.iloc[0:0]

    rows.append({
        'case_id': case_id,
        'n_frames_total': len(sp),
        'n_frames_gated_in': len(gated),
        'n_frames_gated_out': len(excluded_frames),
        'pbp_all_frames_mean': ungated_scored['rats_pbp_v1'].mean() if len(ungated_scored) else float('nan'),
        'pbp_all_frames_median': ungated_scored['rats_pbp_v1'].median() if len(ungated_scored) else float('nan'),
        'pbp_gated_in_mean': gated_scored['rats_pbp_v1'].mean() if len(gated_scored) else float('nan'),
        'pbp_gated_in_median': gated_scored['rats_pbp_v1'].median() if len(gated_scored) else float('nan'),
        'pbp_gated_out_mean': excluded_scored['rats_pbp_v1'].mean() if len(excluded_scored) else float('nan'),
        'pbp_gated_out_median': excluded_scored['rats_pbp_v1'].median() if len(excluded_scored) else float('nan'),
    })

df = pd.DataFrame(rows)
out_path = VH / 'data' / 'analysis' / 'gate_ablation_specimenpathway_v2.csv'
df.to_csv(out_path, index=False)

print()
print('Saved:', out_path)
print(df.to_string())