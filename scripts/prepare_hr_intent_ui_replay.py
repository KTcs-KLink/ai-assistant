"""Build a local browser fixture from the retained actual UI result; no API calls."""
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "output" / "playwright"
    receipt = (output / "hr-intent-portal-live.txt").read_text(encoding="utf-8-sig")
    payload = receipt.split("### Result\n", 1)[1].split("\n###", 1)[0].strip()
    result = json.loads(payload)
    if result.get("status") != "PASSED" or len(result.get("records", [])) != 2:
        raise SystemExit("Two successful actual responses are required; no model calls made.")
    template = (root / "scripts" / "verify_hr_intent_ui_replay.js").read_text(encoding="utf-8")
    marker = "/* RETAINED_INTENT_RESPONSE */ {}"
    if template.count(marker) != 1:
        raise SystemExit("Replay marker mismatch")
    (output / "verify_hr_intent_ui_replay.generated.js").write_text(
        template.replace(marker, json.dumps(result["records"][0], ensure_ascii=False)), encoding="utf-8")
    print("Prepared retained response replay; no API calls.")


if __name__ == "__main__":
    main()
