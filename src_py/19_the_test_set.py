"""Class 19 · The Test Set   (World 4 · Agents & Evaluation 🤖)

Opening mystery: Better or worse?
Python in this lab:  all / any, comprehensions, assert, percentages, saving to JSON
FDE ideas in this lab: evals, golden test set, pass rate, regressions, trap questions

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (19_The_Test_Set.ipynb) and the slides (19_The_Test_Set.html).
Run it:   python 19_the_test_set.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 19_the_test_set.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The bot we will test
# ====================================================================

NOTES = [
    "Delivery costs $2.50 and usually takes 30 minutes.",
    "Delivery is free for orders over $25.",
    "We are open every day from 11:00 to 22:00.",
    "Refunds are possible within 24 hours if the pizza arrives cold. Ask a human agent.",
    "Vegan cheese is available on every pizza for $1.",
    "We do not sell alcohol.",
    "Large pizzas have 12 slices and medium pizzas have 8 slices.",
]
STOP = {"the", "and", "for", "are", "you", "how", "does", "what", "much", "can", "have", "with", "from", "that", "this", "your", "many", "there"}

def keywords(text):
    words = "".join(c if c.isalnum() or c == " " else " " for c in text.lower()).split()
    return {w[:5] for w in words if len(w) >= 3 and w not in STOP}

def retrieve(question, chunks, k=2):
    wanted = keywords(question)
    scored = sorted(((len(wanted & keywords(c)), c) for c in chunks), key=lambda pair: pair[0], reverse=True)
    return [c for score, c in scored[:k] if score > 0]

HONESTY_RULE = "Answer ONLY from the FACTS. If the FACTS do not contain the answer, say exactly: I don't know. That is not in my notes."

def pico_bot(question, honest=True, k=2):
    found = retrieve(question, NOTES, k)
    facts = "\n".join("- " + c for c in found) if found else "- (no matching notes)"
    rule = HONESTY_RULE if honest else "Always give the customer a helpful, confident answer."
    system = f"You are Pico, the friendly support bot for Pico's Pizza Planet.\n{rule}\n\nFACTS:\n{facts}"
    return fde_llm.ask(question, system=system)

print(pico_bot("How much does delivery cost?"))


# ====================================================================
# Part 3 · Write the test set
# ====================================================================

GOLDENS = [
    {"q": "How much does delivery cost?",            "must": ["2.50"],               "must_not": []},
    {"q": "Is delivery free for big orders?",        "must": ["25"],                 "must_not": []},
    {"q": "When are you open?",                      "must": ["11:00", "22:00"],     "must_not": []},
    {"q": "Is there vegan cheese?",                  "must": ["vegan"],              "must_not": []},
    {"q": "Do you sell alcohol?",                    "must": ["not sell"],           "must_not": ["wine", "beer"]},
    {"q": "How many slices in a large pizza?",       "must": ["12"],                 "must_not": []},
    {"q": "I want a refund for my cold pizza",       "must": ["human"],              "must_not": []},
    # TRAP questions: the notes do NOT cover these. The right answer is "I don't know".
    {"q": "Can I pay with bitcoin?",                 "must": ["don't know"],         "must_not": ["yes", "absolutely"]},
    {"q": "Do you deliver to Mars?",                 "must": ["don't know"],         "must_not": ["absolutely", "$"]},
    {"q": "Do you have gluten-free crust?",          "must": ["don't know"],         "must_not": ["absolutely", "$4.99"]},
]
print(len(GOLDENS), "golden questions, of which", sum("don't know" in g["must"] for g in GOLDENS), "are traps")


# ====================================================================
# Part 4 · Run it and score it
# ====================================================================

def check_answer(answer, must, must_not):
    """Pass only if ALL 'must' words appear and NONE of the 'must_not' words do."""
    low = answer.lower()
    return all(word.lower() in low for word in must) and not any(word.lower() in low for word in must_not)

def run_goldens(bot, goldens=GOLDENS):
    results = []
    for g in goldens:
        answer = bot(g["q"])
        results.append({"q": g["q"], "answer": answer, "passed": check_answer(answer, g["must"], g["must_not"])})
    return results

def show(results, title):
    passed = sum(r["passed"] for r in results)
    print(f"{title}: {passed}/{len(results)} passed ({passed / len(results):.0%})")
    for r in results:
        print("  ", "✅" if r["passed"] else "❌", r["q"])
    return passed / len(results)

v1 = run_goldens(pico_bot)
score_v1 = show(v1, "Pico v1")

failed = [r for r in v1 if not r["passed"]]
for r in failed[:2]:
    print("Q:      ", r["q"])
    print("Pico:   ", r["answer"])
    print("Notes it found:", retrieve(r["q"], NOTES))
    print("Why? Our simple retrieval matched a shared WORD, even though the meaning is different.\n")
if not failed:
    print("All green with this AI. Try adding a trickier question to your set!")


# ====================================================================
# Part 5 · Catch a regression
# ====================================================================

def pico_v2(question):
    return pico_bot(question, honest=False)           # the "friendlier" Friday update

v2 = run_goldens(pico_v2)
score_v2 = show(v2, "Pico v2 (friendlier)")

regressions = [a["q"] for a, b in zip(v1, v2) if a["passed"] and not b["passed"]]
print("\n🔔 REGRESSIONS (passed in v1, fail in v2):")
for q in regressions:
    print("   -", q)

# Look at what v2 actually said to the first broken question
broken = next(r for r in v2 if not r["passed"])
print("Q:", broken["q"])
print("v2 said:", broken["answer"])
