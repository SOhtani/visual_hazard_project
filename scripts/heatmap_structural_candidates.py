import importlib.util
import os
from pathlib import Path
import numpy as np
import pandas as pd
import cv2

VH = Path(r'C:\Users\SOhtani2024\visual_hazard_project')

spec = importlib.util.spec_from_file_location('heatmapviz', str(VH / 'scripts' / 'heatmap_structural_visibility.py'))
heatmapviz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heatmapviz)

REQUIRED_COLS = ['case_id', 'image_path', 'roi_x0', 'roi_y0', 'roi_x1', 'roi_y1',
                  'structural_visibility_loss_v1', 'low_light_or_blackout_ratio_v1', 'whiteout_ratio_v1']

per_frame_dir = VH / 'data' / 'derived' / 'quality_metrics' / 'per_frame'
files = [per_frame_dir / f for f in os.listdir(per_frame_dir) if f.endswith('.csv')]

frames = []
skipped = []
for f in files:
    cols = pd.read_csv(f, nrows=0).columns.tolist()
    if all(c in cols for c in REQUIRED_COLS):
        frames.append(pd.read_csv(f, usecols=REQUIRED_COLS))
    else:
        skipped.append(f.name)

print('skipped files (missing columns):', skipped)

df = pd.concat(frames, ignore_index=True)
filtered = df[(df['low_light_or_blackout_ratio_v1'] < 0.3) & (df['whiteout_ratio_v1'] < 0.3)].copy()

target_percentiles = [58, 65, 71, 77, 82, 87, 91, 94, 97, 99]
targets = [np.percentile(filtered['structural_visibility_loss_v1'], p) for p in target_percentiles]

used_cases = set()
selected_rows = []
for p, t in zip(target_percentiles, targets):
    remaining = filtered[~filtered['case_id'].isin(used_cases)]
    diffs = (remaining['structural_visibility_loss_v1'] - t).abs()
    pool_idx = diffs.nsmallest(25).index
    chosen_idx = np.random.choice(pool_idx)
    row = remaining.loc[chosen_idx].copy()
    row['target_percentile'] = p
    selected_rows.append(row)
    used_cases.add(row['case_id'])

candidates = pd.DataFrame(selected_rows)

print(candidates[['case_id', 'image_path', 'target_percentile', 'structural_visibility_loss_v1',
                    'low_light_or_blackout_ratio_v1', 'whiteout_ratio_v1']].to_string())

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
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    score_grid, y_starts, x_starts, patch_size_used = heatmapviz.compute_patch_grid(
        img_rgb, 48, 24, 0.38
    )
    heat = 1.0 - np.clip(score_grid, 0.0, 1.0)
    heat_resized = cv2.resize((heat * 255).astype(np.uint8), (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    alpha = (heat_resized.astype(np.float32) / 255.0) * 0.65
    cyan = np.zeros_like(img_bgr, dtype=np.float32)
    cyan[:, :, 0] = 255
    cyan[:, :, 1] = 255
    cyan[:, :, 2] = 0
    alpha_3 = alpha[:, :, None]
    overlay = (img_bgr.astype(np.float32) * (1 - alpha_3) + cyan * alpha_3).astype(np.uint8)

    pair = np.hstack([img_bgr, overlay])
    label = row.case_id + ' p' + str(row.target_percentile) + ' score=' + format(row.structural_visibility_loss_v1, '.3f')
    pair = cv2.copyMakeBorder(pair, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(pair, str(i) + ') ' + label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    tile_path = out_dir / ('structural_candidate_v3_' + str(i) + '_' + row.case_id + '.png')
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
contact_path = out_dir / 'structural_candidates_contact_sheet_v3.png'
cv2.imwrite(str(contact_path), contact_sheet)
print('Saved contact sheet:', contact_path)
