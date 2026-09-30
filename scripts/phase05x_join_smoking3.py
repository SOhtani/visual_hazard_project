import pandas as pd
from pathlib import Path
master = pd.read_csv(r"C:\Users\SOhtani2024\SurgCap\RATS_2021_2025_data\index\master_case_inventory_2021_2025_with_metadata.csv")
smoking = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\data\annotations\rats_2023_smoking_complications.csv")
master["surgery_date"] = pd.to_datetime(master["surgery_date"], errors="coerce")
smoking["手術年月日(1)"] = pd.to_datetime(smoking["手術年月日(1)"], errors="coerce")
merged = master.merge(smoking, left_on="surgery_date", right_on="手術年月日(1)", how="left")
mask68 = (merged["year"] == 2023) & (merged["include_level1"] == True)
print("include_level1==True の2023症例数:", mask68.sum())
print("そのうち喫煙データありの件数:", merged.loc[mask68, "喫煙"].notna().sum())
print("そのうち合併症データありの件数:", merged.loc[mask68, "合併症"].notna().sum())
print()
print("smoking category counts (68例のみ):")
print(merged.loc[mask68, "喫煙"].value_counts(dropna=False))
print()
print("complication counts (68例のみ):")
print(merged.loc[mask68, "合併症"].value_counts(dropna=False))
out_cols = ["case_id", "surgery_date", "喫煙", "喫煙指数", "合併症", "合併症内訳", "肺瘻", "肺炎", "心房細動", "膿胸", "皮下気腫", "反回神経麻痺", "術後出血"]
present_cols = [c for c in out_cols if c in merged.columns]
out68 = merged.loc[mask68, present_cols]
out_dir = Path(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_smoking_complications")
out_dir.mkdir(parents=True, exist_ok=True)
out68.to_csv(out_dir / "case_smoking_complications_68ref.csv", index=False)
print()
print("Saved:", out_dir / "case_smoking_complications_68ref.csv")
