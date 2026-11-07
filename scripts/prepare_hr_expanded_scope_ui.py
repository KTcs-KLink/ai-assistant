"""Local retained-response transport fixture only; never calls an answer model."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "output/playwright"
text = (output / "hr-saas-assistant-live.txt").read_text(encoding="utf-8-sig")
data = json.loads(text.split("### Result\n", 1)[1].split("\n###", 1)[0])
assert data["status"] == "PASSED" and data["response"]["paragraphs"]
template = (root / "scripts/verify_hr_expanded_scope_ui.js").read_text(encoding="utf-8")
marker = "/* RETAINED_SCOPE_FIXTURE */ {}"
assert template.count(marker) == 1
(output / "verify_hr_expanded_scope_ui.generated.js").write_text(template.replace(marker, json.dumps({"question": data["question"], "response": data["response"]}, ensure_ascii=False)), encoding="utf-8")
print("Prepared retained scope-boundary fixture; no model calls.")
