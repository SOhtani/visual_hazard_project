import pandas as pd
from scipy import stats
from pathlib import Path
blood = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase05_specimenpathway_blood_burden\case_specimenpathway_blood_pbp_summary.csv")
clinical = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_smoking_complications\case_smoking_complications_68ref_v2.csv")
merged = blood.merge(clinical, on="case_id", how="inner")
print("merged n:", len(merged))
print()
smoke_groups = merged.dropna(subset=["喫煙"]).groupby("喫煙")["rats_median_pbp"]
print("smoking group medians (rats_median_pbp):")
print(smoke_groups.median())
print("smoking group n:")
print(smoke_groups.size())
vals = [g.values for _, g in smoke_groups]
kw = stats.kruskal(*vals)
print("Kruskal-Wallis across 3 smoking groups: H=%.3f p=%.4f" % (kw.statistic, kw.pvalue))
print()
merged["ever_smoked"] = merged["喫煙"].isin([" 喫煙していた", " 喫煙している"])
ever = merged.dropna(subset=["喫煙"])
never_vals = ever.loc[~ever["ever_smoked"], "rats_median_pbp"]
ever_vals = ever.loc[ever["ever_smoked"], "rats_median_pbp"]
mw1 = stats.mannwhitneyu(never_vals, ever_vals)
print("Never vs Ever-smoked (Mann-Whitney): never median=%.4f (n=%d), ever median=%.4f (n=%d), p=%.4f" % (never_vals.median(), len(never_vals), ever_vals.median(), len(ever_vals), mw1.pvalue))
print()
comp = merged.dropna(subset=["合併症"])
no_comp = comp.loc[comp["合併症"] == " なし", "rats_median_pbp"]
yes_comp = comp.loc[comp["合併症"] == " あり", "rats_median_pbp"]
mw2 = stats.mannwhitneyu(no_comp, yes_comp)
print("No complication vs Complication (Mann-Whitney): no median=%.4f (n=%d), yes median=%.4f (n=%d), p=%.4f" % (no_comp.median(), len(no_comp), yes_comp.median(), len(yes_comp), mw2.pvalue))
