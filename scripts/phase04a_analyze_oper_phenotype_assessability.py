#!/usr/bin/env python
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

PHENOTYPES = [
    "inflammatory_change",
    "fibrotic_appearance",
    "adhesion",
    "difficult_plane",
    "active_bleeding",
]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mapping", required=True, type=Path)
    p.add_argument("--still-ratings", required=True, type=Path)
    p.add_argument("--temporal-ratings", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    return p.parse_args()

def holm_adjust(pvals):
    p = np.asarray(pvals, dtype=float)
    out = np.full(len(p), np.nan)
    mask = np.isfinite(p)
    if not mask.any():
        return out
    pv = p[mask]
    order = np.argsort(pv)
    ranked = pv[order]
    m = len(ranked)
    adj_ranked = np.maximum.accumulate(np.minimum(1.0, ranked * (m - np.arange(m))))
    tmp = np.empty(m, dtype=float)
    tmp[order] = adj_ranked
    out[np.where(mask)[0]] = tmp
    return out

def mcnemar_exact(s, t):
    s, t = np.asarray(s, bool), np.asarray(t, bool)
    lost = int((s & ~t).sum())
    rescue = int((~s & t).sum())
    n = lost + rescue
    p = 1.0 if n == 0 else stats.binomtest(rescue, n=n, p=0.5, alternative="two-sided").pvalue
    return lost, rescue, float(p)

def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = pd.read_csv(args.mapping, low_memory=False)
    still = pd.read_csv(args.still_ratings, dtype=str).fillna("")
    temp = pd.read_csv(args.temporal_ratings, dtype=str).fillna("")

    if still["review_id"].duplicated().any() or temp["review_id"].duplicated().any():
        raise ValueError("Duplicate review_id in ratings.")

    sm = mapping[["segment_id","still_review_id"]].rename(columns={"still_review_id":"review_id"})
    tm = mapping[["segment_id","temporal_review_id"]].rename(columns={"temporal_review_id":"review_id"})
    s = sm.merge(still, on="review_id", how="left", validate="one_to_one")
    t = tm.merge(temp, on="review_id", how="left", validate="one_to_one")

    if len(still) != len(mapping) or len(temp) != len(mapping):
        raise ValueError(f"Incomplete ratings: mapping={len(mapping)}, still={len(still)}, temporal={len(temp)}")

    paired = s.merge(t, on="segment_id", suffixes=("_still","_temporal"), validate="one_to_one")

    rows, transitions = [], []
    for ph in PHENOTYPES:
        sa = paired[f"{ph}_assessability_still"].eq("Assessable")
        ta = paired[f"{ph}_assessability_temporal"].eq("Assessable")
        lost, rescue, p = mcnemar_exact(sa, ta)
        both = sa & ta
        sp = paired[f"{ph}_presence_still"].eq("Present")
        tp = paired[f"{ph}_presence_temporal"].eq("Present")
        rows.append({
            "phenotype": ph,
            "n_segments": len(paired),
            "still_assessable_n": int(sa.sum()),
            "still_assessable_prop": float(sa.mean()),
            "temporal_assessable_n": int(ta.sum()),
            "temporal_assessable_prop": float(ta.mean()),
            "absolute_assessability_gain": float(ta.mean()-sa.mean()),
            "temporal_rescue_n": rescue,
            "lost_assessability_n": lost,
            "mcnemar_exact_p": p,
            "both_assessable_n": int(both.sum()),
            "presence_label_changed_among_both_n": int((both & (sp != tp)).sum()),
        })
        for _, r in paired.iterrows():
            transitions.append({
                "segment_id": r["segment_id"], "phenotype": ph,
                "still_assessability": r[f"{ph}_assessability_still"],
                "temporal_assessability": r[f"{ph}_assessability_temporal"],
                "still_presence": r[f"{ph}_presence_still"],
                "temporal_presence": r[f"{ph}_presence_temporal"],
            })

    summary = pd.DataFrame(rows)
    summary["holm_p_across_5_phenotypes"] = holm_adjust(summary["mcnemar_exact_p"])
    summary.to_csv(args.output_dir/"operative_phenotype_assessability_summary.csv", index=False)
    pd.DataFrame(transitions).to_csv(args.output_dir/"operative_phenotype_rating_transitions.csv", index=False)
    qc = pd.DataFrame([{
        "mapping_segments": len(mapping), "still_rating_rows": len(still),
        "temporal_rating_rows": len(temp), "paired_segments": len(paired),
    }])
    qc.to_csv(args.output_dir/"operative_phenotype_assessability_qc.csv", index=False)

    print("QC:")
    print(qc.to_string(index=False))
    print("\nAssessability summary:")
    print(summary.to_string(index=False))
    print("\nSaved to:", args.output_dir)

if __name__ == "__main__":
    main()
