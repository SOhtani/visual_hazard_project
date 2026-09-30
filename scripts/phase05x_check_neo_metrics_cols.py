import pandas as pd
from pathlib import Path
d = Path(r"C:\Users\SOhtani2024\visual_hazard_project\data\derived\neo_quality_metrics")
files = sorted(d.glob("*.csv"))
print("n files:", len(files))
if files:
    df = pd.read_csv(files[0], nrows=2)
    print(files[0].name)
    print(list(df.columns))
