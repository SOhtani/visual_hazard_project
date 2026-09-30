#!/usr/bin/env python
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import cv2

STRATA = [
    ("high_blood_like", "blood_like_redness_ratio_v1", False),
    ("high_dark_red", "dark_red_brown_candidate_ratio_v1", False),
    ("high_fresh_red", "fresh_red_candidate_ratio_v1", False),
    ("low_red_control", "blood_like_redness_ratio_v1", True),
]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--color-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--n-per-stratum", type=int, default=10)
    p.add_argument("--seed", type=int, default=20260920)
    return p.parse_args()

def pick_unique_cases(df, metric, ascending, n, used_cases):
    x = df.dropna(subset=[metric, "case_id", "image_path"]).copy()
    x[metric] = pd.to_numeric(x[metric], errors="coerce")
    x = x.dropna(subset=[metric])
    x = x.sort_values(metric, ascending=ascending)
    out = []
    for _, r in x.iterrows():
        c = str(r["case_id"])
        if c in used_cases:
            continue
        out.append(r)
        used_cases.add(c)
        if len(out) >= n:
            break
    return pd.DataFrame(out)

def crop_roi(img, row):
    h, w = img.shape[:2]
    if all(c in row.index and pd.notna(row[c]) for c in ["roi_x0","roi_y0","roi_x1","roi_y1"]):
        x0,y0,x1,y1 = [int(round(float(row[c]))) for c in ["roi_x0","roi_y0","roi_x1","roi_y1"]]
        x0=max(0,min(w-1,x0)); y0=max(0,min(h-1,y0))
        x1=max(x0+1,min(w,x1)); y1=max(y0+1,min(h,y1))
        return img[y0:y1,x0:x1]
    return img

def make_contact_sheet(sel, out_path):
    thumbs=[]
    width=360
    for _,r in sel.iterrows():
        img=cv2.imread(str(r["image_path"]))
        if img is None: continue
        img=crop_roi(img,r)
        h,w=img.shape[:2]
        nh=max(1,int(round(h*width/w)))
        img=cv2.resize(img,(width,nh),interpolation=cv2.INTER_AREA)
        bar=44
        canvas=np.zeros((nh+bar,width,3),np.uint8)
        canvas[bar:]=img
        label=f'{r["selection_stratum"]} | {r["case_id"]} | t={float(r["sample_time_sec"]):.0f}s'
        cv2.putText(canvas,label,(8,28),cv2.FONT_HERSHEY_SIMPLEX,0.48,(255,255,255),1,cv2.LINE_AA)
        thumbs.append(canvas)
    if not thumbs: return
    maxh=max(x.shape[0] for x in thumbs)
    ncol=3; nrow=int(np.ceil(len(thumbs)/ncol))
    sheet=np.zeros((nrow*maxh,ncol*width,3),np.uint8)
    for i,img in enumerate(thumbs):
        rr,cc=divmod(i,ncol)
        sheet[rr*maxh:rr*maxh+img.shape[0],cc*width:(cc+1)*width]=img
    cv2.imwrite(str(out_path),sheet)

def main():
    a=parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.color_csv,low_memory=False)
    req={"case_id","sample_time_sec","image_path"}
    missing=req-set(d.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    for _,m,_ in STRATA:
        if m not in d.columns: raise ValueError(f"Missing metric: {m}")

    # Deterministic case-unique enriched set.
    used=set(); parts=[]
    for name,metric,ascending in STRATA:
        s=pick_unique_cases(d,metric,ascending,a.n_per_stratum,used)
        if len(s)<a.n_per_stratum:
            print(f"[WARN] {name}: requested {a.n_per_stratum}, got {len(s)}")
        s=s.copy()
        s["selection_stratum"]=name
        s["selection_metric"]=metric
        s["selection_metric_value"]=pd.to_numeric(s[metric],errors="coerce")
        parts.append(s)
    sel=pd.concat(parts,ignore_index=True)
    sel["annotation_status"]=""
    sel["annotation_comment"]=""
    keep=[
        "case_id","sample_time_sec","image_path",
        "roi_x0","roi_y0","roi_x1","roi_y1",
        "selection_stratum","selection_metric","selection_metric_value",
        "annotation_status","annotation_comment"
    ]
    keep=[c for c in keep if c in sel.columns]
    out=a.output_dir/"rats_blood_pixel_annotation_frames.csv"
    sel[keep].to_csv(out,index=False,encoding="utf-8-sig")
    make_contact_sheet(sel, a.output_dir/"rats_blood_pixel_annotation_frames_contact_sheet.jpg")
    print(f"Selected frames: {len(sel)}")
    print(f"Unique cases: {sel['case_id'].nunique()}")
    print(sel["selection_stratum"].value_counts().to_string())
    print("Saved:",out)

if __name__=="__main__":
    main()
