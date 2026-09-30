import importlib.util
import sys
from pathlib import Path
import cv2

VH = Path(r'C:\Users\SOhtani2024\visual_hazard_project')

spec = importlib.util.spec_from_file_location('bloodqc', str(VH / 'scripts' / 'phase05_apply_rats_blood_rule_visual_qc_gradable.py'))
bloodqc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bloodqc)

rats_rule = bloodqc.load_final_rule(VH / 'reports' / 'phase05_rats_blood_pixel_recalibration' / 'rats_recalibrated_blood_pixel_rule.csv')


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

    img_bgr_full = cv2.imread(image_path)
    if img_bgr_full is None:
        raise SystemExit('failed to read image: ' + image_path)

    if roi_x0 is not None:
        img_bgr = img_bgr_full[roi_y0:roi_y1, roi_x0:roi_x1]
    else:
        img_bgr = img_bgr_full

    mask, pbp = bloodqc.blood_mask(img_bgr, rats_rule)
    print('blood pixel proportion:', pbp)

    overlay = img_bgr.copy()
    overlay[mask] = [0, 0, 255]
    blended = cv2.addWeighted(img_bgr, 0.55, overlay, 0.45, 0)
    cv2.imwrite(out_path, blended)
    print('Saved heatmap:', out_path)


if __name__ == '__main__':
    main()