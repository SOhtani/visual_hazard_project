import json
import os
from pathlib import Path
neo_dir = Path(os.environ["NEO_DIR"])
for p in sorted(neo_dir.glob("*_annotation_v2.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    segs = d.get("active_annotation", {}).get("segments", [])
    sp = [s for s in segs if s.get("level") == "Level-1" and s.get("label") == "SpecimenPathway"]
    print(p.name, "-> SpecimenPathway segments:", sp)
