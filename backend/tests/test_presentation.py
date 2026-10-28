"""Presentation questions as speech recognition hears them.  Run:  python backend/tests/test_presentation.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app import faq, library  # noqa: E402
faq.FAQ_FILE = ROOT / "data/faq.json"
faq.LIBRARY_FILE = library.LIBRARY_FILE = ROOT / "data/answer_library.json"

CASES = [
 ("Hello Nefa we have some special guests with us today could you please introduce yourself", "faq:avc_introduce"),
 ("hello we have some special guests with us today could you please introduce yourself", "faq:avc_introduce"),
 ("AVC what makes you different from a traditional information kiosk or a regular chatbot", "faq:avc_different"),
 ("Nefa what makes you different from a traditional information kiosk or a regular chatbot", "faq:avc_different"),
 ("AVC could you explain how you understand and respond when someone speaks to you", "faq:avc_how_work"),
 ("Nefa could you tell our audience which company you're representing today", "faq:avc_company"),
 ("AVC where exactly is Saha agency located and how can someone contact the office", "faq:avc_location_contact"),
 ("AVC how can you make a customer's experience easier and more convenient", "faq:avc_customer_experience"),
 ("AVC if I own a business what benefits could I get from using an AI virtual concierge", "faq:avc_business_benefits"),
 ("AVC can your technology be adapted for different types of businesses could you give us a few examples", "faq:avc_industries"),
 ("AVC what would you do if a customer asked you something you weren't sure about", "faq:avc_unsure"),
 ("AVC what exciting possibilities do you see for the future of AI virtual concierge technology", "faq:avc_future"),
 ("AVC if you could describe your main purpose in just a few words what would you say", "faq:avc_purpose"),
 ("AVC would you like to say something to our audience before we finish today's presentation", "faq:avc_final_words"),
 # audience-style
 ("what does AVC stand for", "faq:avc_what_is"), ("is she a real person", "faq:avc_real_person"),
 ("what AI do you use", "faq:avc_tech"), ("can you speak Spanish", "faq:avc_languages"),
 ("can you book me an appointment", "faq:avc_appointments"), ("will this replace receptionists", "faq:avc_replace_staff"),
 ("who made you", "faq:avc_who_made"), ("how much does it cost to get AVC for my business", "faq:avc_get_one"),
 ("where do you get your information from", "faq:avc_knowledge_source"), ("is my data safe with you", "faq:avc_privacy"),
 ("can I use you on my phone", "faq:avc_where_used"),
 # must still go to the old answers
 ("where is your office", "lib:location"), ("what is your phone number", "lib:phone"), ("hello", "lib:greeting"),
 ("how much is car insurance", "faq:auto_cost"),
]

def main():
    entries = library.load_library()
    m, _ = faq._load()
    ok = 0
    for q, want in CASES:
        ex = library.quick_match(q, entries)
        if ex:
            got, how, score = "lib:" + ex["id"], "exact", 1.0
        else:
            ranked = m.rank(q, 4)
            score, ans = ranked[0] if ranked else (0, {"key": None})
            how = "instant" if score >= faq.STRONG else ("ai-pick" if score >= faq.MAYBE else "live")
            got = ans["key"] if how == "instant" else [a["key"] for _, a in ranked] if how == "ai-pick" else None
        good = (got == want) if how in ("exact", "instant") else (how == "ai-pick" and want in got)
        ok += good
        flag = "OK " if good and how in ("exact", "instant") else ("ai " if good else "BAD")
        print(f"{flag} {how:7s} {score:.2f}  {q[:70]!r} -> {got if not isinstance(got, list) else got[:3]}")
    print(f"\n{ok}/{len(CASES)} right")

main()
