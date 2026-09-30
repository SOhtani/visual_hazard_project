
import importlib.util
import sys
from pathlib import Path
import numpy as np
import cv2

VH = Path(r'C:\Users\SOhtani2024\visual_hazard_project')
SRC = VH / 'scripts' / '05_compute_frame_visual_hazard_components.py'

spec = importlib.util.spec_from_file_location('vhcomp', str(SRC))
vhcomp = importlib.util.module_from_spec(spec)
sys.modules['vhcomp'] = vhcomp
spec.loader.exec_module(vhcomp)


def compute_patch_grid(roi_rgb_u8, patch_size, patch_stride, coverage_thr):
    gray = vhcomp.rgb_to_gray_float(roi_rgb_u8)
    gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)
    h, w = gray.shape[:2]
    if h < patch_size or w < patch_size:
        patch_size = min(h, w)
        patch_stride = patch_size

    y_starts = list(range(0, max(h - patch_size + 1, 1), patch_stride))
    if len(y_starts) == 0 or y_starts[-1] != h - patch_size:
        y_starts.append(max(h - patch_size, 0))
    x_starts = list(range(0, max(w - patch_size + 1, 1), patch_stride))
    if len(x_starts) == 0 or x_starts[-1] != w - patch_size:
        x_starts.append(max(w - patch_size, 0))

    grid_rows = len(y_starts)
    grid_cols = len(x_starts)
    score_grid = np.zeros((grid_rows, grid_cols), dtype=np.float64)

    for gy_idx, y0 in enumerate(y_starts):
        for gx_idx, x0 in enumerate(x_starts):
            y1 = y0 + patch_size
            x1 = x0 + patch_size
            patch = gray[y0:y1, x0:x1]
            patch_u8 = gray_u8[y0:y1, x0:x1]

            gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3)
            tenengrad = float(np.mean(gx * gx + gy * gy))

            lap = cv2.Laplacian(patch, cv2.CV_32F, ksize=3)
            lap_var = float(np.var(lap))

            entropy = vhcomp.calc_patch_entropy(patch_u8)

            t_score = vhcomp.map_tenengrad_to_unit(tenengrad)
            l_score = vhcomp.map_lapvar_to_unit(lap_var)
            e_score = vhcomp.map_entropy_to_unit(entropy)

            patch_focus = float(0.45 * t_score + 0.30 * l_score + 0.25 * e_score)
            score_grid[gy_idx, gx_idx] = patch_focus

    return score_grid, y_starts, x_starts, patch_size


def main():
    image_path = sys.argv[1]
    out_path = sys.argv[2]
    if len(sys.argv) >= 7:
        roi_x0 = int(sys.argv[3])
        roi_y0 = int(sys.argv[4])
        roi_x1 = int(sys.argv[5])
        roi_y1 = int(sys.argv[6])
    else:
        roi_x0 = roi_y0 = roi_x1 = roi_y1 = None

    patch_size = 48
    patch_stride = 24
    coverage_thr = 0.38

    img_bgr_full = cv2.imread(image_path)
    if img_bgr_full is None:
        raise SystemExit('failed to read image: ' + image_path)

    if roi_x0 is not None:
        img_bgr = img_bgr_full[roi_y0:roi_y1, roi_x0:roi_x1]
    else:
        img_bgr = img_bgr_full

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    score_grid, y_starts, x_starts, patch_size_used = compute_patch_grid(
        img_rgb, patch_size, patch_stride, coverage_thr
    )

    heat = 1.0 - np.clip(score_grid, 0.0, 1.0)
    heat_u8 = (heat * 255).astype(np.uint8)
    heat_resized = cv2.resize(heat_u8, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    heat_color = cv2.applyColorMap(heat_resized, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(img_bgr, 0.55, heat_color, 0.45, 0)
    cv2.imwrite(out_path, overlay)
    print('Saved heatmap:', out_path)
    print('grid shape:', score_grid.shape, 'patch_size_used:', patch_size_used)


if __name__ == '__main__':
    main()