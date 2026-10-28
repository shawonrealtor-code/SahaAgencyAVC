"""Instant answers: match a visitor's question against every prepared question
(premade video answers + data/faq.json) in a few milliseconds, without the AI.

score >= STRONG  -> answer immediately
score >= MAYBE   -> let Qwen pick from the top few candidates (short, fast prompt)
otherwise        -> live AI answer
"""

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

import httpx

log = logging.getLogger("saha.faq")
FAQ_FILE = Path("/app/data/faq.json")
LIBRARY_FILE = Path("/app/data/answer_library.json")
SKIP_IDS = {"not_sure"}

STRONG = 0.62
MAYBE = 0.28

STOP = set("""
a an the is are am was were be been being do does did doing i me my mine we our you your yours it its this that these
those to of in on at for from with about as by or and if so can could would will shall may might must there here
please tell know like just also any some have has had get got give let us them they their what which who whom
how when where why one ok okay hi hey um uh really per nefa nafa nifa guys actually all each usually so then than too very
""".split())

# Different words, same meaning.
SYNONYMS = {
    "car": "auto", "cars": "auto", "vehicle": "auto", "vehicles": "auto", "automobile": "auto", "truck": "auto",
    "house": "home", "homeowner": "home", "homeowners": "home", "homes": "home", "dwelling": "home",
    "price": "cost", "prices": "cost", "priced": "cost", "costs": "cost", "expensive": "cost", "cheap": "cost",
    "rate": "cost", "rates": "cost", "premium": "premium", "pricing": "cost", "much": "cost",
    "coverage": "cover", "covered": "cover", "covers": "cover", "covering": "cover", "insure": "insurance",
    "insured": "insurance", "insuring": "insurance", "policies": "policy", "quotes": "quote", "quoted": "quote",
    "claims": "claim", "renter": "renters", "tenant": "renters", "tenants": "renters", "apartment": "renters",
    "landlords": "landlord", "agent": "advisor", "agents": "advisor", "advisors": "advisor", "person": "advisor",
    "human": "advisor", "company": "carrier", "companies": "carrier", "carriers": "carrier", "insurer": "carrier",
    "insurers": "carrier", "provider": "carrier", "providers": "carrier", "kids": "children", "child": "children",
    "son": "children", "daughter": "children", "teen": "children", "teenager": "children", "wife": "spouse",
    "husband": "spouse", "employees": "employee", "staff": "employee", "workers": "employee", "business": "business",
    "businesses": "business", "company's": "carrier", "stolen": "theft", "steal": "theft", "robbed": "theft",
    "burglary": "theft", "crash": "accident", "wreck": "accident", "accidents": "accident", "collision": "accident",
    "medical": "health", "doctor": "health", "monthly": "month", "annually": "year", "yearly": "year",
    "speak": "talk", "talking": "talk", "chat": "talk", "real": "advisor", "licensed": "advisor",
    "sued": "lawsuit", "sue": "lawsuit", "suing": "lawsuit", "lawsuits": "lawsuit", "wrecked": "accident",
    "slipped": "injur", "slip": "injur", "fell": "injur", "fall": "injur", "hurt": "injur", "injured": "injur",
    "injury": "injur", "injuries": "injur", "save": "save", "saving": "save", "savings": "save", "lower": "save",
    "reduce": "save", "cheaper": "save", "minimums": "minimum", "required": "require", "requirement": "require",
    "requirements": "require", "mandatory": "require", "law": "require", "legally": "require",
    "best": "best", "better": "best", "pick": "choose", "choosing": "choose", "go": "choose",
    "insurance": "insurance", "virginia": "state", "va": "state",
    "abc": "avc", "avg": "avc", "avs": "avc",   # common mishearings of "AVC"
}

# Words that name a topic: a match must share them.
TOPICS = {"auto", "home", "life", "lifeinsurance", "health", "healthinsurance", "renters", "landlord", "business",
          "claim", "employee", "workerscomp", "bop", "flood", "fire", "roof", "theft", "rental", "spouse", "children",
          "termlife", "wholelife", "commercialauto", "generalliability", "eando", "quote", "accident", "lawsuit"}

KEEP_PHRASES = [
    ("full coverage", "fullcoverage"), ("general liability", "generalliability"), ("workers comp", "workerscomp"),
    ("workers compensation", "workerscomp"), ("errors and omissions", "eando"), ("e and o", "eando"),
    ("business owners policy", "bop"), ("open enrollment", "openenrollment"), ("pre existing", "preexisting"),
    ("out of pocket", "outofpocket"), ("term life", "termlife"), ("whole life", "wholelife"),
    ("life insurance", "lifeinsurance"), ("health insurance", "healthinsurance"), ("commercial auto", "commercialauto"),
    ("not my fault", "notatfault"), ("my fault", "atfault"), ("at fault", "atfault"), ("same day", "sameday"),
    ("how much", "cost"), ("phone number", "phone"), ("email address", "email"),
]


def normalize(text: str) -> str:
    text = text.lower().replace("&", " and ").replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    text = " " + normalize(text) + " "
    for phrase, word in KEEP_PHRASES:
        text = text.replace(f" {phrase} ", f" {word} ")
    out = []
    for word in text.split():
        word = SYNONYMS.get(word, word)
        if word in STOP or len(word) < 2:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = SYNONYMS.get(word[:-1], word[:-1])
        elif len(word) > 6 and word.endswith("ing"):
            word = SYNONYMS.get(word[:-3], word[:-3])
        elif len(word) > 5 and word.endswith("ed"):
            word = SYNONYMS.get(word[:-2], word[:-2])
        out.append(word)
    return out


def features(text: str) -> list[str]:
    toks = tokens(text)
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


class Matcher:
    """TF-IDF cosine similarity over all prepared questions."""

    def __init__(self, docs: list[tuple[str, dict]]):
        self.docs = []  # (vector, norm, answer, topics)
        df = Counter()
        feats = [(features(q), ans) for q, ans in docs]
        for f, _ in feats:
            df.update(set(f))
        n = max(len(feats), 1)
        self.idf = {t: math.log((n + 1) / (c + 0.5)) + 1 for t, c in df.items()}
        self.default_idf = math.log(n + 1) + 1
        for f, ans in feats:
            vec = self._vector(f)
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.docs.append((vec, norm, ans, TOPICS.intersection(f)))

    def _vector(self, feats: list[str]) -> dict[str, float]:
        counts = Counter(feats)
        return {t: (1 + math.log(c)) * self.idf.get(t, self.default_idf) for t, c in counts.items()}

    def rank(self, question: str, top: int = 5) -> list[tuple[float, dict]]:
        qf = features(question)
        q = self._vector(qf)
        qt = TOPICS.intersection(qf)
        qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
        best: dict[str, tuple[float, dict]] = {}
        for vec, norm, ans, dt in self.docs:
            dot = sum(w * vec[t] for t, w in q.items() if t in vec)
            if not dot:
                continue
            score = dot / (qn * norm)
            score *= 0.8 ** len(qt - dt)        # visitor named a topic this answer isn't about
            score *= 0.9 ** len(dt - qt)        # answer is about a topic the visitor didn't mention
            key = ans["key"]
            if key not in best or score > best[key][0]:
                best[key] = (score, ans)
        return sorted(best.values(), key=lambda x: -x[0])[:top]


_cache = {"stamp": None, "matcher": None, "answers": {}}


def _load():
    stamp = tuple(p.stat().st_mtime if p.exists() else 0 for p in (FAQ_FILE, LIBRARY_FILE))
    if _cache["stamp"] == stamp:
        return _cache["matcher"], _cache["answers"]
    answers, docs = {}, []
    library = {}
    if LIBRARY_FILE.exists():
        for e in json.loads(LIBRARY_FILE.read_text(encoding="utf-8")).get("answers", []):
            if not e.get("id") or e["id"] in SKIP_IDS:
                continue
            library[e["id"]] = e
            ans = {"key": "lib:" + e["id"], "kind": "library", "entry": e, "text": e["text"]}
            answers[ans["key"]] = ans
            docs += [(q, ans) for q in e.get("questions", [])]
    if FAQ_FILE.exists():
        for e in json.loads(FAQ_FILE.read_text(encoding="utf-8")).get("faq", []):
            if e.get("video") in library:
                ans = answers["lib:" + e["video"]]   # same answer as a premade video
            else:
                ans = {"key": "faq:" + e["id"], "kind": "faq", "entry": e, "text": e["answer"]}
                answers[ans["key"]] = ans
            docs += [(q, ans) for q in e.get("questions", [])]
    matcher = Matcher(docs)
    _cache.update(stamp=stamp, matcher=matcher, answers=answers)
    log.info("Instant answers ready: %d answers, %d questions", len(answers), len(docs))
    return matcher, answers


def stats() -> dict:
    matcher, answers = _load()
    return {"instant_answers": len(answers), "instant_questions": len(matcher.docs)}


def all_speech() -> list[str]:
    """Every prepared spoken answer (for warming the voice cache)."""
    _, answers = _load()
    out = []
    for a in answers.values():
        e = a["entry"]
        out.append(e.get("speech") or e.get("text") or e.get("answer"))
    return [t for t in out if t]


PICK_PROMPT = """A visitor at an insurance agency asked a question. Choose the prepared answer that
directly answers it, or "none" if none of them does (for example when the visitor asks about something
more specific, different, or two topics at once).

Prepared answers:
{options}

Reply with JSON only: {{"pick": <number of the answer, or "none">}}"""


async def find(question: str, ollama_url: str, model: str) -> tuple[dict | None, float, str]:
    """Return (answer, score, how) where how is 'instant', 'ai-pick' or 'none'."""
    try:
        matcher, _ = _load()
    except (OSError, ValueError) as error:
        log.warning("Instant answers unavailable: %s", error)
        return None, 0.0, "none"
    ranked = matcher.rank(question, top=4)
    if not ranked:
        return None, 0.0, "none"
    score, best = ranked[0]
    if score >= STRONG:
        return best, score, "instant"
    if score < MAYBE:
        return None, score, "none"

    options = "\n".join(f"{i + 1}. {a['text'][:220]}" for i, (_, a) in enumerate(ranked))
    payload = {
        "model": model, "stream": False, "think": False, "format": "json",
        "messages": [{"role": "system", "content": PICK_PROMPT.format(options=options)},
                     {"role": "user", "content": question.strip()}],
        "options": {"temperature": 0, "num_predict": 12, "num_ctx": 2048},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            result = await client.post(f"{ollama_url}/api/chat", json=payload)
            result.raise_for_status()
            pick = json.loads(result.json()["message"]["content"]).get("pick")
        index = int(pick) - 1
        if 0 <= index < len(ranked):
            return ranked[index][1], ranked[index][0], "ai-pick"
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return None, score, "none"
