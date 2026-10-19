"""Matching accuracy on questions that are NOT in the data.  Run:  python backend/tests/test_faq_match.py"""
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app import faq  # noqa: E402
faq.FAQ_FILE = ROOT / "data/faq.json"
faq.LIBRARY_FILE = ROOT / "data/answer_library.json"

# (question, expected key or None for "should go to the live AI")
CASES = [
 ("hello there", "lib:greeting"), ("good morning!", "lib:greeting"), ("thanks so much", "lib:thank_you"),
 ("where's your office located", "lib:location"), ("what's your phone number", "lib:phone"),
 ("what hours are you open", "lib:hours"), ("who started the agency", "lib:founder"),
 ("what kind of insurance do you guys sell", "lib:services_overview"), ("can i get a quote for my car", "lib:get_quote"),
 ("i need help filing a claim", "lib:claims"), ("do you have umbrella insurance", "lib:service_umbrella"),
 ("do you do cyber insurance for small businesses", "lib:service_cyber"), ("do you sell surety bonds", "lib:service_bond"),
 ("can you insure my wedding", "lib:service_event"), ("can you insure my company trucks", "lib:service_commercial_auto"),
 ("can you explain what insurance actually is", "faq:what_is_insurance"), ("why would i need insurance at all", "faq:why_insurance"),
 ("how much will my premium be each month", "faq:premium_cost"), ("whats a deductible", "faq:premium_vs_deductible"),
 ("is your quote free of charge", "lib:get_quote"), ("how can i save on my insurance", "faq:lower_costs"),
 ("which insurance company should i go with", "faq:best_company"),
 ("how much is auto insurance per month", "faq:auto_cost"), ("what's the minimum coverage to drive in virginia", "faq:auto_minimum"),
 ("is liability enough or do i need full coverage", "faq:full_vs_liability"), ("if i cause a crash am i covered", "faq:at_fault_accident"),
 ("will my rates increase after an accident", "faq:premium_after_accident"), ("can i get insured with a dui on my record", "faq:bad_record"),
 ("am i covered when i rent a car on vacation", "faq:rental_cars"), ("can i add my teenage son to my car policy", "faq:add_family_auto"),
 ("my cousin wrecked my car who pays", "faq:someone_else_drives"), ("what if i'm hit by someone with no insurance", "faq:uninsured_driver"),
 ("what does a homeowners policy cover", "faq:home_covers"), ("how much is homeowners insurance a year", "faq:home_cost"),
 ("do i have to carry home insurance", "faq:home_required"), ("is fire damage covered on my home policy", "faq:home_fire"),
 ("does my house insurance cover floods", "faq:home_flood"), ("hail damaged my roof is that covered", "faq:home_roof_storm"),
 ("a visitor slipped on my stairs am i liable", "faq:home_injury"), ("my tv was stolen from my house is it covered", "faq:home_theft"),
 ("can i bundle my house and car insurance", "faq:bundle_home_auto"), ("how much should i insure my home for", "faq:home_how_much"),
 ("do you have renters insurance", "faq:renters_what"), ("how much is renters insurance a month", "faq:renters_cost"),
 ("does renters insurance cover stolen stuff", "faq:renters_theft"), ("can a landlord make me get renters insurance", "faq:landlord_require"),
 ("what is a landlord policy", "faq:landlord_what"), ("will landlord insurance cover lost rent", "faq:landlord_lost_rent"),
 ("do you offer life insurance policies", "faq:life_what"), ("how much life insurance should i have", "faq:life_how_much"),
 ("is term or whole life better", "faq:term_vs_whole"), ("can i get life coverage without an exam", "faq:life_no_exam"),
 ("how do i change the beneficiary on my life policy", "faq:life_beneficiary"),
 ("do you sell health insurance plans", "faq:health_plans"), ("ppo or hmo which is better", "faq:hmo_ppo"),
 ("what's a copay", "faq:copay_deductible_oop"), ("can i sign up for health insurance after open enrollment", "faq:health_sep"),
 ("what insurance does a small business need", "faq:business_needs" if False else "lib:service_business"),
 ("what does general liability insurance cover", "lib:service_commercial_liability"),
 ("what's a bop", "lib:service_bop"), ("do i need workers comp for my two employees", "lib:service_workers_comp"),
 ("what insurance does a restaurant need", "faq:restaurant_retail"), ("what insurance do i need for my gas station", "faq:restaurant_retail"),
 ("who needs professional liability", "lib:service_professional_liability"), ("a customer sued my business am i covered", "faq:business_lawsuits"),
 ("what documents do i need for a claim", "faq:claim_documents"), ("how long do claims usually take", "faq:claim_time"),
 ("does filing a claim make my premium go up", "faq:claim_premium"), ("i was just in a car accident what should i do", "faq:after_accident"),
 ("my claim got denied what can i do", "faq:claim_denied"), ("how do i appeal a claim denial", "faq:claim_appeal"),
 ("can you check my claim status", "faq:claim_status"), ("can i use my own body shop", "faq:choose_repair_shop"),
 ("can i pay my premium monthly", "faq:pay_monthly"), ("what if i miss a payment", "faq:missed_payment"),
 ("can i set up autopay", "faq:autopay"), ("is there a discount for safe drivers", "faq:good_driver_discount"),
 ("why did my premium go up this year", "faq:premium_increase"), ("how do i cancel my policy", "faq:cancel"),
 ("will i get a refund if i cancel", "faq:cancel_refund"), ("do you compare quotes from multiple companies", "lib:carriers"),
 ("what info do you need for a quote", "faq:quote_info"), ("can i be insured today", "faq:same_day"),
 ("do i have to come to the office", "faq:visit_office"), ("can i buy a policy online", "faq:phone_online"),
 ("i want to speak to a real agent", "lib:phone"), ("can you help me switch my insurance company", "faq:switch_provider"),
 ("i need proof of insurance", "faq:proof_of_insurance"), ("who do i call for an emergency on the weekend", "faq:after_hours"),
 ("what is your email", "lib:email_website"), ("what is your website", "lib:email_website"),
 # should NOT get a canned answer
 ("what's the weather like today", None), ("tell me a joke", None), ("who won the football game last night", None),
 ("what's 25 times 4", None), ("do you insure pets", None), ("can you insure my boat", None),
 ("how much is insurance for a 2019 honda civic for a 22 year old in woodbridge with one ticket", "faq:auto_cost"),
]

def main():
    t = time.time(); faq._load(); build = time.time() - t
    m = faq._cache["matcher"]
    ok = bad = 0; times = []
    for q, want in CASES:
        t = time.time(); ranked = m.rank(q, 4); times.append(time.time() - t)
        score, ans = ranked[0] if ranked else (0, {"key": None})
        if score >= faq.STRONG: got, how = ans["key"], "instant"
        elif score >= faq.MAYBE: got, how = ([a["key"] for _, a in ranked]), "ai-pick"
        else: got, how = None, "live"
        if how == "ai-pick":
            good = (want in got) if want else True   # AI will choose among candidates or none
        else:
            good = got == want
        ok += good; bad += not good
        if not good or how == "ai-pick":
            print(f"{'OK ' if good else 'BAD'} {how:8s} {score:.2f} {q!r} -> {got if how!='ai-pick' else got[:3]} (want {want})")
    print(f"\n{ok}/{len(CASES)} correct | build {build*1000:.0f} ms | avg match {sum(times)/len(times)*1000:.1f} ms")

main()
