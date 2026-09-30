import pandas as pd
blood = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase05_specimenpathway_blood_burden\case_specimenpathway_blood_pbp_summary.csv")
clinical = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_smoking_complications\case_smoking_complications_68ref_v2.csv")
merged = blood.merge(clinical, on="case_id", how="inner")
comp_yes = merged.loc[merged["合併症"] == " あり"].sort_values("rats_median_pbp")
flag_cols = ["肺瘻", "肺炎", "心房細動", "膿胸", "皮下気腫", "反回神経麻痺", "術後出血"]
print(comp_yes[["rats_median_pbp"] + flag_cols].to_string(index=False))
