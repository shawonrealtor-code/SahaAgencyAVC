"""Build data/faq.json from tools/faq_source_*.py

  python tools/build_faq.py
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from faq_source_1 import FAQ_1  # noqa: E402
from faq_source_2 import FAQ_2  # noqa: E402

DIGITS = "zero one two three four five six seven eight nine".split()


def speech(text):
    """Words Kokoro reads naturally (phone digits, web addresses)."""
    text = text.replace("(703) 627-0444", "seven zero three, six two seven, zero four four four")
    text = text.replace("sahaagency.com", "saha agency dot com").replace("HealthCare.gov", "healthcare dot gov")
    text = re.sub(r"\b911\b", "nine one one", text)
    return text


def main():
    entries = FAQ_1 + FAQ_2
    library = {e["id"] for e in json.loads((ROOT / "data/answer_library.json").read_text())["answers"]}
    ids, total = set(), 0
    out = []
    for e in entries:
        assert e["id"] not in ids, f"duplicate id {e['id']}"
        ids.add(e["id"])
        assert not e["video"] or e["video"] in library, f"unknown video {e['video']}"
        qs = list(dict.fromkeys(q.strip() for q in e["questions"] if q.strip()))
        total += len(qs)
        out.append({"id": e["id"], "video": e["video"], "answer": e["answer"],
                    "speech": speech(e["answer"]), "questions": qs})
    (ROOT / "data/faq.json").write_text(json.dumps({"faq": out}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(out)} answers, {total} questions -> data/faq.json")


if __name__ == "__main__":
    main()
