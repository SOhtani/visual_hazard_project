import importlib.util
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import cv2

VH = Path(r'C:\Users\SOhtani2024\visual_hazard_project')

spec = importlib.util.spec_from_file_location('bloodqc', str(VH / 'scripts' / 'phase05_apply_rats_blood_rule_visual_qc_gradable.py'))
bloodqc = importlib.util.module_from_spec(spec)
sys.modules['bloodqc'] = bloodqc
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / 'reports' / 'phase05_rats_blood_pixel_recalibration' / 'rats_recalibrated_blood_pixel_rule.csv')

df = pd.read_csv(VH / 'data' / 'analysis' / 'all_frames_blood_pbp_scores.csv')
sub = df[(df['workflow_level1_label'] == 'SpecimenPathway') & (df['rats_pbp_v1'] > 0.02)].copy()

target_percentiles = [30, 40, 50, 55, 60, 65, 70, 75, 80, 85]
targets = [np.percentile(sub['rats_pbp_v1'], p) for p in target_percentiles]

used_cases = set()
selected_rows = []
for p, t in zip(target_percentiles, targets):
    remaining = sub[~sub['case_id'].isin(used_cases)]
    idx = (remaining['rats_pbp_v1'] - t).abs().idxmin()
    row = remaining.loc[idx].copy()
    row['target_percentile'] = p
    selected_rows.append(row)
    used_cases.add(row['case_id'])

candidates = pd.DataFrame(selected_rows)

print(candidates[['case_id', 'image_path', 'target_percentile', 'rats_pbp_v1']].to_string())

out_dir = VH / 'reports' / 'heatmaps'
out_dir.mkdir(parents=True, exist_ok=True)

tiles = []
for i, row in enumerate(candidates.itertuples(), 1):
    img_bgr_full = cv2.imread(row.image_path)
    if img_bgr_full is None:
        print('failed to read:', row.image_path)
        continue
    x0, y0, x1, y1 = int(row.roi_x0), int(row.roi_y0), int(row.roi_x1), int(row.roi_y1)
    img_bgr = img_bgr_full[y0:y1, x0:x1]

    mask, pbp = bloodqc.blood_mask(img_bgr, rats_rule)
    overlay = img_bgr.copy()
    overlay[mask] = [0, 255, 0]
    blended = cv2.addWeighted(img_bgr, 0.55, overlay, 0.45, 0)

    pair = np.hstack([img_bgr, blended])
    label = row.case_id + ' p' + str(row.target_percentile) + ' pbp=' + format(row.rats_pbp_v1, '.3f')
    pair = cv2.copyMakeBorder(pair, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(pair, str(i) + ') ' + label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    tile_path = out_dir / ('blood_candidate_v2_' + str(i) + '_' + row.case_id + '.png')
    cv2.imwrite(str(tile_path), pair)
    tiles.append(pair)

widths = [t.shape[1] for t in tiles]
min_w = min(widths)
resized_tiles = []
for t in tiles:
    scale = min_w / t.shape[1]
    new_h = int(t.shape[0] * scale)
    resized_tiles.append(cv2.resize(t, (min_w, new_h)))

contact_sheet = np.vstack(resized_tiles)
contact_path = out_dir / 'blood_candidates_contact_sheet_v2.png'
cv2.imwrite(str(contact_path), contact_sheet)
print('Saved contact sheet:', contact_path)