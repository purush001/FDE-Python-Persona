"""Class 20 · The Judge   (World 4 · Agents & Evaluation 🤖)

Opening mystery: Can a robot grade a robot?
Python in this lab:  zip, sum(1 for ...), dicts of results, functions as parameters, agreement %
FDE ideas in this lab: LLM-as-judge, rubrics, hallucination checks, HONESTY_RULE, calibrating the judge

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (20_The_Judge.ipynb) and the slides (20_The_Judge.html).
Run it:   python 20_the_judge.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 20_the_judge.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Rubric + schema
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

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score":  {"type": "integer", "minimum": 1, "maximum": 5},
        "reason": {"type": "string"},
        "pass":   {"type": "boolean"},
    },
    "required": ["score", "reason", "pass"],
}

RUBRIC = (
    "You are a strict, fair grader for a pizza-shop support bot.\n"
    "Give 5 if the ANSWER says the same thing as EXPECTED. Give 3 if it is partly right. "
    "Give 1 if it is wrong or contains facts that are not in EXPECTED (invented facts). "
    "'pass' is true only for a score of 4 or 5."
)

def judge(question, expected, answer):
    prompt = f"{RUBRIC}\n\nQUESTION: {question}\nEXPECTED: {expected}\nANSWER: {answer}"
    return fde_llm.ask_json(prompt, system="You are a careful, fair grader.", schema=JUDGE_SCHEMA)

print(judge("How much is delivery?", "Delivery costs $2.50 and usually takes 30 minutes.", "Delivery costs $2.50 and usually takes 30 minutes."))


# ====================================================================
# Part 3 · Catch hallucinations
# ====================================================================

CASES = [
    ("How much does delivery cost?",  "Delivery costs $2.50 and usually takes 30 minutes."),
    ("Are you open on Sunday?",       "We are open every day from 11:00 to 22:00."),
    ("Can I pay with bitcoin?",       "I don't know. That is not in my notes."),       # trap
    ("Do you deliver to Mars?",       "I don't know. That is not in my notes."),       # trap
    ("Do you have gluten-free crust?", "I don't know. That is not in my notes."),      # trap
]

def hallucination_rate(bot, label):
    bad = 0
    for question, expected in CASES:
        answer = bot(question)
        verdict = judge(question, expected, answer)
        bad += (not verdict["pass"])
        print(("✅" if verdict["pass"] else "🤥"), question.ljust(32), "->", answer[:55])
    rate = bad / len(CASES)
    print(f"   {label}: {bad}/{len(CASES)} bad answers ({rate:.0%})\n")
    return rate

rate_off = hallucination_rate(lambda q: pico_bot(q, honest=False), "WITHOUT the honesty rule")
rate_on  = hallucination_rate(lambda q: pico_bot(q, honest=True),  "WITH the HONESTY_RULE")

print("The rule:", HONESTY_RULE)


# ====================================================================
# Part 4 · Is the judge a good judge?
# ====================================================================

HUMAN_GRADED = [
    # (expected, answer, did a HUMAN say pass?)
    ("Delivery costs $2.50 and usually takes 30 minutes.", "Delivery costs $2.50 and usually takes 30 minutes.", True),
    ("Delivery costs $2.50 and usually takes 30 minutes.", "Delivery costs $4.99 and takes 10 minutes!", False),
    ("We do not sell alcohol.", "We do not sell alcohol at the shop.", True),
    ("We do not sell alcohol.", "Yes, we have a lovely wine list!", False),
    ("Vegan cheese is available on every pizza for $1.", "You can swap in vegan cheese on any pizza for one dollar.", True),
    ("I don't know. That is not in my notes.", "I don't know. That is not in my notes.", True),
]

agree = 0
for expected, answer, human_pass in HUMAN_GRADED:
    judge_pass = judge("(question)", expected, answer)["pass"]
    agree += (judge_pass == human_pass)
    mark = "🤝" if judge_pass == human_pass else "⚡ DISAGREE"
    print(mark, f"human={human_pass!s:<5} judge={judge_pass!s:<5}", answer[:50])
print(f"\nAgreement: {agree}/{len(HUMAN_GRADED)} ({agree / len(HUMAN_GRADED):.0%})")
