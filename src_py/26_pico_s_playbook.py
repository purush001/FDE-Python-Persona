"""Class 26 · Pico's Playbook   (World 6 · Pro Skills 🎓 (bonus))

Opening mystery: Five bots, one job
Python in this lab:  functions as values, dict dispatch, for loops with a limit, max(key=...), returning (result, history)
FDE ideas in this lab: agentic design patterns, chain, route, parallel, orchestrator-workers, evaluator-optimizer, reflection, plan-and-execute, ReAct, cost and latency of each pattern, choose the simplest pattern that passes the tests

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (26_Pico_s_Playbook.ipynb) and the slides (26_Pico_s_Playbook.html).
Run it:   python 26_pico_s_playbook.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 26_pico_s_playbook.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 3 · Run them and count the calls
# ====================================================================

class CountedAI:
    # A pretend AI. It answers in a simple way and counts every call.
    def __init__(self):
        self.calls = 0

    def say(self, prompt):
        self.calls += 1
        p = prompt.lower()
        if p.startswith("classify"):
            return "order" if ("order" in p or "where" in p) else "menu"
        if p.startswith("check"):
            return "ok"
        return "Pico: " + prompt[:40]

def lookup_order(order_id):
    return {"4821": "out for delivery", "4822": "cooking"}.get(order_id, "not found")

print(CountedAI().say("classify: Where is my order?"))
print(lookup_order("4821"))

def single(ai, q):
    return ai.say(q)

def chain(ai, q):                                   # step 1 -> step 2 -> step 3
    kind = ai.say("classify: " + q)
    draft = ai.say("answer as " + kind + ": " + q)
    return ai.say("polish: " + draft)

def route(ai, q):                                   # one cheap decision, then ONE specialist
    kind = ai.say("classify: " + q)
    return ai.say(kind + " specialist answers: " + q)

def parallel(ai, q):                                # independent checks (they could run at the same time), then merge
    checks = [ai.say(f"check {what}: {q}") for what in ("tone", "facts", "safety")]
    return ai.say("merge " + ", ".join(checks))

def orchestrator(ai, q):                            # a boss splits the job, workers do the parts, the boss merges
    ai.say("plan: " + q)
    parts = [ai.say(f"worker {i}: " + q) for i in (1, 2)]
    return ai.say("merge: " + " | ".join(parts))

def evaluator_optimizer(ai, q, rounds=2):           # write, critique, improve
    draft = ai.say("draft: " + q)
    for _ in range(rounds - 1):
        notes = ai.say("critique: " + draft)
        draft = ai.say("improve: " + draft + " " + notes)
    return draft

def reflection(ai, q):                              # answer, then check your own answer once
    draft = ai.say("answer: " + q)
    verdict = ai.say("check: is this answer supported? " + draft)
    return draft if verdict == "ok" else ai.say("fix: " + draft)

def plan_and_execute(ai, q):                        # ONE planning call, then plain code does the steps
    ai.say("plan: " + q)
    return "Your order is " + lookup_order("4821")

def react(ai, q, max_steps=4):                      # think, act, look... with a step limit
    for step in range(max_steps):
        ai.say("think: what next? " + q)
        if step >= 1:                               # pretend it knows enough on the second look
            return "Your order is " + lookup_order("4821")
        lookup_order("4821")
    return "I could not finish."

question = "Where is my order 4821?"
PATTERNS = [("single call", single), ("chain", chain), ("route", route), ("parallel", parallel), ("orchestrator", orchestrator),
            ("evaluator-optimizer", evaluator_optimizer), ("reflection", reflection), ("plan-and-execute", plan_and_execute), ("ReAct", react)]
bill = {}
for name, pattern in PATTERNS:
    ai = CountedAI()
    pattern(ai, question)
    bill[name] = ai.calls


# ====================================================================
# Part 4 · Write, critique, improve
# ====================================================================

def write(topic, feedback):
    words = ["Fresh", topic, "daily"] if "fresh" in feedback else [topic, "here"]
    text = " ".join(words)
    if "price" in feedback:
        text += " for $9"
    return text

def critique(text):
    score, notes = 0, []
    if "$" in text:
        score += 34
    else:
        notes.append("add a price")
    if len(text.split()) <= 12:
        score += 33
    else:
        notes.append("make it shorter")
    if "fresh" in text.lower():
        score += 33
    else:
        notes.append("say fresh")
    return score, " and ".join(notes)

text, feedback = "", ""
for round_no in range(1, 4):
    text = write("pizza", feedback)
    score, feedback = critique(text)
    print(f"round {round_no}: {text!r} -> score {score}   notes: {feedback or 'none'}")
    if score >= 90:
        break

def never_happy(text):
    return 40, "do better"

rounds, calls = 0, 0
for rounds in range(1, 11):                          # we cap it at 10 so the demo stops
    text = write("pizza", "do better")
    score, notes = never_happy(text)
    calls += 2                                       # one write call + one critique call
    if score >= 90:
        break
print(f"{rounds} rounds, {calls} AI calls, final score {score}. All wasted.")


# ====================================================================
# Part 5 · Choose the simplest move
# ====================================================================

GUIDE = [
    ("The answer is a fixed fact",                              "a lookup or ONE call"),
    ("The steps are known and always the same",                 "chain"),
    ("Different questions need different experts",              "route"),
    ("Several checks do not depend on each other",              "parallel"),
    ("The work splits into parts and one boss must merge them", "orchestrator + workers"),
    ("The first draft is rarely good enough",                   "evaluator-optimizer (with a limit)"),
    ("A wrong answer is costly and checkable",                  "reflection"),
    ("You know the steps and can run them in code",             "plan-and-execute"),
    ("You cannot know the steps in advance",                    "ReAct agent (with a step limit)"),
]
for situation, pattern in GUIDE:
    print(f"{situation:<58} -> {pattern}")


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: a tiny graph runner (plain Python, no framework)
def run_graph(nodes, edges, start, state, max_steps=10):
    step = start
    for _ in range(max_steps):              # a hard limit, as always
        if step == "END":
            break
        state = nodes[step](state)           # do this step
        step = edges[step](state)            # then ask the edge: where next?
    return state

nodes = {
    "write":    lambda s: {**s, "text": s["text"] + " 🍕", "rounds": s["rounds"] + 1},
    "critique": lambda s: {**s, "score": 30 * s["rounds"]},
}
edges = {
    "write":    lambda s: "critique",                                   # a plain edge
    "critique": lambda s: "END" if s["score"] >= 90 else "write",        # a conditional edge: the exit
}

final = run_graph(nodes, edges, "write", {"text": "Pizza", "rounds": 0, "score": 0})
print(final)
print("write -> critique -> write -> ... until the score is high enough. A framework draws this same picture.")
