#!/usr/bin/env python
from __future__ import annotations
import argparse, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd

TAU_Y_GRID=[40,60,80,100,120,140,160,180,200]
TAU_R_GRID=[5,10,14,20,30,40,60,80,100]
ALPHA_GRID=[0.0,0.15,0.30,0.38,0.50,0.65,0.80,1.00]
BETA_GRID=[0.0,0.10,0.20,0.24,0.30,0.40,0.50,0.60]
XU=(80.0,14.0,0.38,0.24)

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--labels-csv",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--n-folds",type=int,default=5)
    p.add_argument("--seed",type=int,default=20260920)
    return p.parse_args()

def pred_rule(d,params):
    ty,tr,a,b=params
    gray=d["pixel_gray"].to_numpy(float)
    red=d["pixel_r"].to_numpy(float)
    pr=np.divide(gray,red,out=np.full_like(gray,np.inf),where=red>0)
    fr=d["frame_gray_over_red"].to_numpy(float)
    return ((gray<ty)&(red>tr)&(pr<(a*fr+b))).astype(int)

def metrics(y,p):
    y=np.asarray(y,int); p=np.asarray(p,int)
    tp=int(np.sum((y==1)&(p==1))); tn=int(np.sum((y==0)&(p==0)))
    fp=int(np.sum((y==0)&(p==1))); fn=int(np.sum((y==1)&(p==0)))
    sens=tp/(tp+fn) if tp+fn else np.nan
    spec=tn/(tn+fp) if tn+fp else np.nan
    acc=(tp+tn)/len(y) if len(y) else np.nan
    bacc=np.nanmean([sens,spec])
    ppv=tp/(tp+fp) if tp+fp else np.nan
    return {"n":len(y),"tp":tp,"tn":tn,"fp":fp,"fn":fn,
            "sensitivity":sens,"specificity":spec,"accuracy":acc,
            "balanced_accuracy":bacc,"ppv":ppv}

def best_params(train):
    y=train["label"].to_numpy(int)
    best=None
    for params in itertools.product(TAU_Y_GRID,TAU_R_GRID,ALPHA_GRID,BETA_GRID):
        p=pred_rule(train,params)
        m=metrics(y,p)
        score=(m["balanced_accuracy"],m["specificity"],m["sensitivity"])
        if best is None or score>best[0]:
            best=(score,params,m)
    return best[1],best[2]

def main():
    a=parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.labels_csv)
    req={"case_id","label","pixel_gray","pixel_r","frame_gray_over_red"}
    missing=req-set(d.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    d=d.dropna(subset=list(req)).copy()
    d["label"]=pd.to_numeric(d["label"],errors="coerce").astype(int)
    npos=int((d.label==1).sum()); nneg=int((d.label==0).sum())
    cases=sorted(d.case_id.astype(str).unique())
    if npos<30 or nneg<30 or len(cases)<5:
        raise RuntimeError(f"Need >=30 blood, >=30 non-blood, >=5 cases. Got blood={npos}, non-blood={nneg}, cases={len(cases)}")

    rng=np.random.default_rng(a.seed)
    cases=np.array(cases,dtype=object); rng.shuffle(cases)
    folds=np.array_split(cases,min(a.n_folds,len(cases)))

    pred_rows=[]; cv_rows=[]
    for i,test_cases in enumerate(folds,1):
        test_mask=d.case_id.astype(str).isin(set(test_cases))
        tr=d.loc[~test_mask].copy(); te=d.loc[test_mask].copy()
        params,_=best_params(tr)

        for name,par in [("xu_original",XU),("rats_recalibrated",params)]:
            p=pred_rule(te,par); m=metrics(te.label.to_numpy(int),p)
            cv_rows.append({"fold":i,"method":name,
                            "tau_y":par[0],"tau_r":par[1],"alpha":par[2],"beta":par[3],
                            **m,"n_test_cases":len(test_cases)})
            tmp=te[["case_id","sample_time_sec","image_path","label","pixel_r","pixel_g","pixel_b","pixel_gray"]].copy()
            tmp["fold"]=i; tmp["method"]=name; tmp["pred"]=p
            pred_rows.append(tmp)

    cv=pd.DataFrame(cv_rows)
    preds=pd.concat(pred_rows,ignore_index=True)
    cv.to_csv(a.output_dir/"blood_pixel_case_grouped_cv_results.csv",index=False,encoding="utf-8-sig")
    preds.to_csv(a.output_dir/"blood_pixel_case_grouped_cv_predictions.csv",index=False,encoding="utf-8-sig")

    final_params,train_m=best_params(d)
    final=pd.DataFrame([{
        "tau_y":final_params[0],"tau_r":final_params[1],"alpha":final_params[2],"beta":final_params[3],
        "n_labels":len(d),"n_blood":npos,"n_non_blood":nneg,"n_cases":len(cases),
        "training_balanced_accuracy":train_m["balanced_accuracy"],
        "training_sensitivity":train_m["sensitivity"],
        "training_specificity":train_m["specificity"],
        "note":"Final parameters fit to all pilot labels; use grouped CV for performance claims."
    }])
    final.to_csv(a.output_dir/"rats_recalibrated_blood_pixel_rule.csv",index=False,encoding="utf-8-sig")

    summary=(cv.groupby("method")[["sensitivity","specificity","accuracy","balanced_accuracy","ppv"]]
               .agg(["mean","std"]).reset_index())
    summary.columns=["method"]+[f"{a}_{b}" for a,b in summary.columns.tolist()[1:]]
    summary.to_csv(a.output_dir/"blood_pixel_case_grouped_cv_summary.csv",index=False,encoding="utf-8-sig")

    print("=== Annotation set ===")
    print(f"labels={len(d)} blood={npos} non_blood={nneg} cases={len(cases)}")
    print()
    print("=== Case-grouped CV summary ===")
    print(summary.to_string(index=False))
    print()
    print("=== Final RATS-specific rule (fit on all pilot labels) ===")
    print(final.to_string(index=False))
    print()
    print("IMPORTANT: performance claims must use grouped CV, not final training metrics.")
    print("Saved:",a.output_dir)

if __name__=="__main__":
    main()
