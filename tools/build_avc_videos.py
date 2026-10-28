"""Turn the AVC answers (tools/faq_source_3.py) into premade video answers.

  python tools/build_avc_videos.py      (then: python tools/build_faq.py)

- Splits each answer into short clip lines that fit one Google Flow clip (about 8 seconds)
- Adds/updates them in data/answer_library.json (videos library/<id>_<n>.mp4)
- Writes FLOW_PROMPTS_AVC.txt with one Flow prompt per clip
Until a clip exists, the screen speaks that answer with the Kokoro voice instead.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from faq_source_3 import FAQ_3  # noqa: E402

MAX_WORDS = 21   # about 8 seconds at a relaxed pace

BASE = ("Photorealistic video continuing from the reference frame: the same woman in the black saree with blue and green "
        "floral embroidery, standing as a calm, friendly receptionist, framed from the waist up, facing the camera straight on, "
        "hands folded at her waist. She speaks directly to the visitor in front of her, looking into the camera, with natural "
        "lip movement that matches her words, small natural nods and a warm, professional expression. She says, in a warm, calm, "
        "clear female voice with a gentle South Asian English accent, at a relaxed pace: \"{line}\" After she finishes speaking "
        "she closes her mouth, smiles softly, and returns to the same calm centered pose as the reference frame. Static "
        "locked-off camera, no zoom, no pan. Same soft even lighting and plain warm cream background. Her face, hair, skin tone "
        "and saree stay exactly the same as the reference frame. Real camera footage, natural skin texture, sharp focus. No "
        "subtitles, no captions, no on-screen text, no music, no background sound.")


def spoken(text: str) -> str:
    """How she should say it (numbers and letters written out)."""
    text = text.replace("(703) 627-0444", "seven zero three, six two seven, zero four four four")
    text = text.replace("14484 General Washington Drive", "fourteen four eighty-four General Washington Drive")
    text = text.replace("Virginia 22193", "Virginia, two two one nine three")
    text = text.replace("sahaagency.com", "saha agency dot com")
    text = re.sub(r"\bAVC\b", "A-V-C", text)
    text = re.sub(r"\bAI\b", "A-I", text)
    return text


def words(s: str) -> int:
    return len(s.split())


def split_long(sentence: str) -> list[str]:
    """Split one long sentence at commas / 'and' / 'while' near the middle."""
    if words(sentence) <= MAX_WORDS:
        return [sentence]
    w = sentence.split()
    best = None
    for i in range(4, len(w) - 3):
        prev = w[i - 1]
        if prev.endswith(",") or w[i] in ("and", "while", "or", "but", "so", "including", "allowing", "because"):
            score = abs(i - len(w) / 2)
            if best is None or score < best[0]:
                best = (score, i)
    i = best[1] if best else len(w) // 2
    a, b = " ".join(w[:i]).rstrip(","), " ".join(w[i:])
    a = a if a.endswith((".", "!", "?")) else a + ","
    b = b[0].upper() + b[1:] if b.split()[0] not in ("and", "or", "but") else b
    return split_long(a) + split_long(b)


def parts_of(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", spoken(text).strip())
    pieces = [p for s in sentences for p in split_long(s)]
    out, cur = [], ""
    for p in pieces:                      # join short sentences up to the clip length
        limit = MAX_WORDS + 3 if words(cur) <= 4 else MAX_WORDS   # a short opener rides along
        if cur and words(cur) + words(p) <= limit:
            cur = f"{cur} {p}"
        else:
            if cur:
                out.append(cur)
            cur = p
    if cur:
        out.append(cur)
    return out


def main():
    lib_path = ROOT / "data/answer_library.json"
    lib = json.loads(lib_path.read_text(encoding="utf-8"))
    keep = [e for e in lib["answers"] if not e["id"].startswith("avc_")]
    new, prompts, n = [], [], 0
    for e in FAQ_3:
        parts = parts_of(e["answer"])
        videos = ([f"library/{e['id']}.mp4"] if len(parts) == 1
                  else [f"library/{e['id']}_{i}.mp4" for i in range(1, len(parts) + 1)])
        speech = " ".join(parts).replace("A-V-C", "A V C").replace("A-I", "A I")
        new.append({"id": e["id"], "text": e["answer"], "speech": speech, "parts": parts,
                    "videos": videos, "questions": [q.lower().rstrip("?.!") for q in e["questions"][:3]]})
        for i, (part, video) in enumerate(zip(parts, videos), 1):
            n += 1
            label = f"part {i} of {len(parts)}" if len(parts) > 1 else "single clip"
            prompts.append(f"--- {n}. {Path(video).name}   (answer: {e['id']}, {label}, {words(part)} words)\n"
                           + BASE.format(line=part) + "\n")
    lib["answers"] = keep + new
    lib_path.write_text(json.dumps(lib, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    header = ("SAHA AVC - FLOW PROMPTS FOR THE AVC PRESENTATION ANSWERS\n"
              "========================================================\n"
              "Settings for EVERY clip: Frames to Video, first frame = saha-start-frame.png (front-facing),\n"
              "9:16, highest quality, download 1080p WITH sound. Save with the exact file name shown.\n"
              "Put all files in: avatar-frontend\\public\\videos\\library\\\n"
              "An answer plays as video only when ALL its parts exist; until then she speaks it with the computer voice.\n\n")
    (ROOT / "FLOW_PROMPTS_AVC.txt").write_text(header + "\n".join(prompts), encoding="utf-8")
    print(f"{len(new)} answers -> {n} clips; FLOW_PROMPTS_AVC.txt written")
    for a in new:
        print(f"  {a['id']:26s} {len(a['parts'])} clips  " + " | ".join(f"{words(p)}w" for p in a["parts"]))


if __name__ == "__main__":
    main()
