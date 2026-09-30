import pandas as pd
blood = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase05_specimenpathway_blood_burden\case_specimenpathway_blood_pbp_summary.csv")
clinical = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_smoking_complications\case_smoking_complications_68ref_v2.csv")
merged = blood.merge(clinical, on="case_id", how="inner")
comp_yes = merged.loc[merged["合併症"] == " あり", "rats_median_pbp"].sort_values()
print("complication=あり group individual values (sorted, no case_id shown):")
print(comp_yes.to_numpy())
