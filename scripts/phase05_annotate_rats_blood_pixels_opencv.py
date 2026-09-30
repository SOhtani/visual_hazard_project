#!/usr/bin/env python
from __future__ import annotations
import argparse
from pathlib import Path
import cv2
import numpy as np
import pandas as pd

WINDOW="RATS blood-pixel annotation"

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--output-csv",required=True,type=Path)
    p.add_argument("--display-width",type=int,default=1200)
    return p.parse_args()

def roi_bounds(row,w,h):
    cols=["roi_x0","roi_y0","roi_x1","roi_y1"]
    if all(c in row.index and pd.notna(row[c]) for c in cols):
        x0,y0,x1,y1=[int(round(float(row[c]))) for c in cols]
        x0=max(0,min(w-1,x0)); y0=max(0,min(h-1,y0))
        x1=max(x0+1,min(w,x1)); y1=max(y0+1,min(h,y1))
        return x0,y0,x1,y1
    return 0,0,w,h

def main():
    a=parse_args()
    man=pd.read_csv(a.manifest)
    existing=[]
    if a.output_csv.exists():
        try:
            existing=pd.read_csv(a.output_csv).to_dict("records")
        except Exception:
            existing=[]
    labels=existing[:]
    annotated_keys={(str(r.get("case_id")),float(r.get("sample_time_sec"))) for r in labels if "case_id" in r and "sample_time_sec" in r}

    idx=0
    mode=1 # 1 blood, 0 non-blood
    current_clicks=[]

    cv2.namedWindow(WINDOW,cv2.WINDOW_NORMAL)

    while idx<len(man):
        row=man.iloc[idx]
        key_id=(str(row["case_id"]),float(row["sample_time_sec"]))
        if key_id in annotated_keys:
            idx += 1
            continue
        path=Path(str(row["image_path"]))
        img=cv2.imread(str(path))
        if img is None:
            print("[WARN] unreadable:",path)
            idx+=1
            continue

        h,w=img.shape[:2]
        x0,y0,x1,y1=roi_bounds(row,w,h)
        crop=img[y0:y1,x0:x1].copy()
        ch,cw=crop.shape[:2]
        scale=min(1.0,a.display_width/float(cw))
        disp=cv2.resize(crop,(int(round(cw*scale)),int(round(ch*scale))),interpolation=cv2.INTER_AREA)

        already=sum(1 for r in labels if (str(r.get("case_id")),float(r.get("sample_time_sec")))==key_id)

        def redraw():
            canvas=disp.copy()
            for c in current_clicks:
                dx=int(round(c["x_roi"]*scale)); dy=int(round(c["y_roi"]*scale))
                color=(0,0,255) if c["label"]==1 else (255,255,0)
                cv2.circle(canvas,(dx,dy),5,color,-1,cv2.LINE_AA)
            bar=78
            out=np.zeros((canvas.shape[0]+bar,canvas.shape[1],3),np.uint8)
            out[bar:]=canvas
            mode_txt="BLOOD" if mode==1 else "NON-BLOOD"
            txt1=f'{idx+1}/{len(man)}  {row["case_id"]}  t={float(row["sample_time_sec"]):.0f}s  mode={mode_txt}'
            txt2=f'click=label | b/n switch | u undo | s save+next | k skip | p previous | q save+quit | prior labels={already}'
            cv2.putText(out,txt1,(10,28),cv2.FONT_HERSHEY_SIMPLEX,0.62,(255,255,255),2,cv2.LINE_AA)
            cv2.putText(out,txt2,(10,58),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1,cv2.LINE_AA)
            return out

        def on_mouse(event,x,y,flags,param):
            nonlocal current_clicks
            if event!=cv2.EVENT_LBUTTONDOWN: return
            yy=y-78
            if yy<0: return
            xr=int(round(x/scale)); yr=int(round(yy/scale))
            if not (0<=xr<cw and 0<=yr<ch): return

            px=crop[yr,xr]
            b,g,r=[int(v) for v in px]
            gray=int(cv2.cvtColor(np.uint8([[[b,g,r]]]),cv2.COLOR_BGR2GRAY)[0,0])
            red_img=crop[:,:,2].astype(np.float32)
            gray_img=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY).astype(np.float32)
            fr=float(red_img.mean()); fg=float(gray_img.mean())
            current_clicks.append({
                "case_id":str(row["case_id"]),
                "sample_time_sec":float(row["sample_time_sec"]),
                "image_path":str(path),
                "selection_stratum":str(row.get("selection_stratum","")),
                "label":int(mode),
                "label_name":"blood" if mode==1 else "non_blood",
                "x_roi":xr,"y_roi":yr,
                "x_full":xr+x0,"y_full":yr+y0,
                "pixel_r":r,"pixel_g":g,"pixel_b":b,"pixel_gray":gray,
                "frame_red_mean_roi":fr,
                "frame_gray_mean_roi":fg,
                "pixel_gray_over_red":(gray/r if r>0 else np.nan),
                "frame_gray_over_red":(fg/fr if fr>0 else np.nan),
            })

        cv2.setMouseCallback(WINDOW,on_mouse)

        while True:
            cv2.imshow(WINDOW,redraw())
            k=cv2.waitKey(50)&0xFF
            if k==255: continue
            if k in (ord("b"),ord("B")): mode=1
            elif k in (ord("n"),ord("N")): mode=0
            elif k in (ord("u"),ord("U")):
                if current_clicks: current_clicks.pop()
            elif k in (ord("s"),ord("S"),13,32):
                labels.extend(current_clicks); current_clicks=[]
                pd.DataFrame(labels).to_csv(a.output_csv,index=False,encoding="utf-8-sig")
                idx+=1; break
            elif k in (ord("k"),ord("K")):
                current_clicks=[]; idx+=1; break
            elif k in (ord("p"),ord("P")):
                current_clicks=[]; idx=max(0,idx-1); break
            elif k in (ord("q"),ord("Q"),27):
                labels.extend(current_clicks)
                pd.DataFrame(labels).to_csv(a.output_csv,index=False,encoding="utf-8-sig")
                cv2.destroyAllWindows()
                print("Saved:",a.output_csv)
                return

    pd.DataFrame(labels).to_csv(a.output_csv,index=False,encoding="utf-8-sig")
    cv2.destroyAllWindows()
    print("Saved:",a.output_csv)
    if labels:
        z=pd.DataFrame(labels)
        print(z["label_name"].value_counts().to_string())
        print("Cases:",z["case_id"].nunique())

if __name__=="__main__":
    main()
