"""Class 28 · From Idea to Launch   (World 6 · Pro Skills 🎓 (bonus))

Opening mystery: The bot nobody asked for
Python in this lab:  dictionaries and lists of records, sorted(key=lambda ...), re.search for checking text, f-strings for a report, formulas and what-if loops
FDE ideas in this lab: the solution lifecycle: discover, prototype, pilot, launch, improve, turning a memo into measurable requirements, value versus effort, ROI and payback, pilot gates: go, fix or stop, risks, mitigations and status updates

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (28_From_Idea_to_Launch.ipynb) and the slides (28_From_Idea_to_Launch.html).
Run it:   python 28_from_idea_to_launch.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 28_from_idea_to_launch.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Discover
# ====================================================================

import re

def is_measurable(requirement):
    # A real requirement has a NUMBER and a UNIT or comparison.
    has_number = bool(re.search(r"\d", requirement))
    has_unit = bool(re.search(r"%|second|minute|hour|per |under|at least|at most|fewer|more than|zero", requirement.lower()))
    return has_number and has_unit

wishes = ["Pico should be fast", "Customers should be happy", "Pico should be helpful"]
requirements = ["Reply in under 5 seconds for 95% of questions",
                "Answer 90% of order-status questions without a human",
                "Zero invented refund promises in the 20 trap questions"]
for text in wishes + requirements:
    print("✅" if is_measurable(text) else "❌", text)

your_requirement = "Average rating of at least 4 out of 5 from 50 customers"       # ✏️ write your own, then run
print("✅ measurable" if is_measurable(your_requirement) else "❌ not measurable yet: add a number and a unit", "->", your_requirement)


# ====================================================================
# Part 3 · Value, effort, money
# ====================================================================

IDEAS = [
    {"name": "Order-status answers",       "value": 9, "effort": 3},
    {"name": "Menu questions",             "value": 6, "effort": 2},
    {"name": "Refund approvals",           "value": 7, "effort": 8},
    {"name": "Wine pairings",              "value": 1, "effort": 5},
    {"name": "Daily sales summary",        "value": 5, "effort": 4},
]
ranked = sorted(IDEAS, key=lambda idea: idea["value"] / idea["effort"], reverse=True)

def monthly_saving(tickets, share_automated, minutes_each, hourly_cost):
    hours = tickets * share_automated * minutes_each / 60
    return hours * hourly_cost

TICKETS, MINUTES, HOURLY = 2000, 4, 18             # a month of order-status questions
SETUP = 4000                                        # one-time cost
for share in (0.2, 0.4, 0.6, 0.8):
    saving = monthly_saving(TICKETS, share, MINUTES, HOURLY)
    run_cost = 300 + TICKETS * share * 0.01         # fixed + 1 cent per automated ticket
    net = saving - run_cost
    months = SETUP / net if net > 0 else float("inf")
    print(f"{share:.0%} automated: saves ${saving:,.0f}/month, costs ${run_cost:,.0f}, net ${net:,.0f}, payback {months:.1f} months")


# ====================================================================
# Part 4 · Pilot, risks, status
# ====================================================================

PILOT = {"pass_rate": 0.88, "hallucination_rate": 0.01, "p95_seconds": 6.2, "user_rating": 4.3}
print("Pilot numbers from 10 real users and the test set:")
for metric, value in PILOT.items():
    print(f"  {metric:<20} {value}")

RISKS = [
    {"risk": "Bot invents a refund promise",     "likelihood": 3, "impact": 5, "plan": "Honesty rule + trap tests + human approval for refunds"},
    {"risk": "Nobody uses it",                   "likelihood": 4, "impact": 4, "plan": "Show it to cashiers early; measure adoption"},
    {"risk": "Price of AI calls grows",          "likelihood": 3, "impact": 3, "plan": "Budget limit + cache + cheaper model for easy questions"},
    {"risk": "Private data leaks into logs",     "likelihood": 2, "impact": 5, "plan": "Redaction (Class 21) + retention rule"},
]
for r in sorted(RISKS, key=lambda r: r["likelihood"] * r["impact"], reverse=True):
    print(f"score {r['likelihood'] * r['impact']:>2}  {r['risk']:<34} -> {r['plan']}")

def status_update(done, doing, risks, asks):
    lines = ["Weekly update"]
    lines += ["Done:  " + "; ".join(done), "Doing: " + "; ".join(doing), "Risks: " + "; ".join(risks), "Need:  " + "; ".join(asks)]
    return "\n".join(lines)

print(status_update(
    done=["pilot ran with 10 users", "pass rate 88%"],
    doing=["fixing slow replies (6.2 s, target 5 s)"],
    risks=["adoption is the biggest unknown"],
    asks=["two more cashiers for the pilot"],
))
