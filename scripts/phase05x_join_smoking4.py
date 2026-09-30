import pandas as pd
from pathlib import Path
ref = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_clean\case_visual_hazard_clinical_linkage.csv")
smoking = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\data\annotations\rats_2023_smoking_complications.csv")
print("reference cohort rows:", len(ref))
ref["surgery_date"] = pd.to_datetime(ref["surgery_date"], errors="coerce")
smoking["手術年月日(1)"] = pd.to_datetime(smoking["手術年月日(1)"], errors="coerce")
merged = ref.merge(smoking, left_on="surgery_date", right_on="手術年月日(1)", how="left")
print("matched with smoking data:", merged["喫煙"].notna().sum())
print("matched with complication data:", merged["合併症"].notna().sum())
print()
print("smoking category counts (68 reference cases):")
print(merged["喫煙"].value_counts(dropna=False))
print()
print("complication counts (68 reference cases):")
print(merged["合併症"].value_counts(dropna=False))
out_cols = ["case_id", "surgery_date", "喫煙", "喫煙指数", "合併症", "合併症内訳", "肺瘻", "肺炎", "心房細動", "膿胸", "皮下気腫", "反回神経麻痺", "術後出血"]
present_cols = [c for c in out_cols if c in merged.columns]
out = merged[present_cols]
out_dir = Path(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_smoking_complications")
out_dir.mkdir(parents=True, exist_ok=True)
out.to_csv(out_dir / "case_smoking_complications_68ref_v2.csv", index=False)
print()
print("Saved:", out_dir / "case_smoking_complications_68ref_v2.csv")
