import pandas as pd
df = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\clinical_linkage_clean\case_visual_hazard_clinical_linkage.csv")
cols95 = ["level1_PortDockExplore__frac_visual_hazard_any_p95","level1_SpecimenPathway__frac_visual_hazard_any_p95","level1_LeakHemostasis__frac_visual_hazard_any_p95","level1_DrainClosure__frac_visual_hazard_any_p95"]
cols99 = ["level1_PortDockExplore__frac_visual_hazard_any_p99","level1_SpecimenPathway__frac_visual_hazard_any_p99","level1_LeakHemostasis__frac_visual_hazard_any_p99","level1_DrainClosure__frac_visual_hazard_any_p99"]
print("n rows total:", len(df))
print("p95 medians pct:")
print((df[cols95].median()*100).round(1))
print("p99 medians pct:")
print((df[cols99].median()*100).round(1))
