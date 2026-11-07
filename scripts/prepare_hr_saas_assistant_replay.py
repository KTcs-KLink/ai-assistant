"""Prepare explicitly retained UI fixtures; never calls a model."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "output/playwright"
latest = "--latest-live" in sys.argv[1:]
receipt = (output / ("hr-saas-assistant-live.txt" if latest else "hr-intent-portal-live.txt")).read_text(encoding="utf-8-sig")
data = json.loads(receipt.split("### Result\n", 1)[1].split("\n###", 1)[0])
fixture = {"question": data["question"], "response": data["response"]} if latest else data["records"][0]
assert data["status"] == "PASSED" and fixture["response"]["paragraphs"]
template = (root / "scripts/verify_hr_saas_assistant.js").read_text(encoding="utf-8")
marker = "/* RETAINED_ASSISTANT_FIXTURE */ {}"
assert template.count(marker) == 1
(output / "verify_hr_saas_assistant.generated.js").write_text(template.replace(marker, json.dumps(fixture, ensure_ascii=False)), encoding="utf-8")
print("Prepared retained fixture; no model calls.")
