import pandas as pd
df = pd.read_csv(r"C:\Users\SOhtani2024\visual_hazard_project\reports\phase_component_distributions\case_phase_component_distribution_summary.csv")
sub = df[(df["phase_level"]=="Level-1") & (df["component"]=="legacy_badness_alias")]
print((sub.groupby("phase_label")[["frac_ge_global_p90","frac_ge_global_p95","frac_ge_global_p99"]].median()*100).round(1))
print(sub.groupby("phase_label")["case_id"].nunique())
