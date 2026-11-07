"""Prepare ignored UI fixtures from retained responses; no new generation or source writes."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / "output/playwright/hr-closeout-portal-live.txt").read_text(encoding="utf-8-sig")
match = re.search(r"### Result\s*\n(.*?)\n###", raw, re.S)
live = json.loads(match.group(1))
assert live["status"] == "PASSED"
withheld = json.loads((ROOT.parent / "outputs/klink_hr_quality_closeout_20261107/final/answers/KEPCO-HR-03-041.json").read_text(encoding="utf-8"))
assert withheld["response"]["generated_text_withheld"] and not withheld["response"]["paragraphs"]
fixtures = dict(answer=live["response"], withheld=withheld["response"])
template = (ROOT / "scripts/verify_hr_closeout_ui_replay.js").read_text(encoding="utf-8")
marker = "/* RETAINED_CLOSEOUT_RESPONSES */ {}"
assert marker in template
target = ROOT / "output/playwright/verify_hr_closeout_ui_replay.generated.js"
target.write_text(template.replace(marker, json.dumps(fixtures, ensure_ascii=False)), encoding="utf-8")
print("Prepared retained UI responses; new model generations: 0")
