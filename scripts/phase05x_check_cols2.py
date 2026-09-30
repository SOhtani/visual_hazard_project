import pandas as pd
from pathlib import Path

VH = Path(r"C:\Users\SOhtani2024\visual_hazard_project")
quality = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_quality" / "neo_case_reference_percentiles_long.csv")
color = pd.read_csv(VH / "reports" / "phase05_neo_vs_reference_color" / "color_neo_case_reference_percentiles_long.csv")
print("=== quality columns ===")
print(list(quality.columns))
print()
print("=== quality head ===")
print(quality.head(10).to_string())
print()
print("=== color columns ===")
print(list(color.columns))
print()
print("=== color head ===")
print(color.head(10).to_string())