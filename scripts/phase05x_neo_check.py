import json
import os
import pandas as pd
from pathlib import Path

neo_dir = Path(os.environ["NEO_DIR"])
print("=== A. SpecimenPathway segments per case ===")
for p in sorted(neo_dir.glob("*_annotation_v2.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    segs = d.get("active_annotation", {}).get("segments", [])
    sp = [s for s in segs if s.get("level") == "Level-1" and s.get("label") == "SpecimenPathway"]
    print(p.name, "-> SpecimenPathway segments:", sp)

print()
print("=== B. neo_quality_metrics columns ===")
qm_dir = Path(r"C:\Users\SOhtani2024\visual_hazard_project\data\derived\neo_quality_metrics\per_frame")
files = sorted(qm_dir.glob("*.csv"))
print("n files:", len(files))
if files:
    df = pd.read_csv(files[0], nrows=2)
    print(files[0].name)
    print(list(df.columns))