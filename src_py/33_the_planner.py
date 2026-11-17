"""Class 33 · The Planner   (World 8 · Agentic Pro 🧭 (advanced))

Opening mystery: The agent that did step 4 first
Python in this lab:  list of dicts as a plan, sets and all(), while loops, try / except around tool calls, regex substitution (re.sub)
FDE ideas in this lab: plan-and-execute, step dependencies, plan validation before running, failure containment, replanning

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (33_The_Planner.ipynb) and the slides (33_The_Planner.html).
Run it:   python 33_the_planner.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 33_the_planner.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · A tiny world with four tools
# ====================================================================

import json, re

STOCK = {"dough": 12, "cheese": 5, "basil": 0}
PRICES = {"margherita": 9, "garden": 11, "plant power": 12}
OUTBOX = []

def check_stock(item):
    return {"item": item, "left": STOCK.get(item, 0)}

def get_price(pizza):
    if pizza not in PRICES:
        raise KeyError(f"no pizza called {pizza!r}")
    return {"pizza": pizza, "price": PRICES[pizza]}

def add_up(a, b):
    return {"total": a + b}

def send_sms(to, text):
    OUTBOX.append((to, text))
    return {"sent": True, "to": to}

TOOLS = {"check_stock": check_stock, "get_price": get_price, "add_up": add_up, "send_sms": send_sms}
print(get_price("garden"), check_stock("basil"))


# ====================================================================
# Part 3 · A plan is data
# ====================================================================

PLAN = [
    {"id": "s1", "tool": "check_stock", "args": {"item": "cheese"}},
    {"id": "s2", "tool": "get_price", "args": {"pizza": "garden"}},
    {"id": "s3", "tool": "get_price", "args": {"pizza": "plant power"}},
    {"id": "s4", "tool": "add_up", "args": {"a": "$s2.price", "b": "$s3.price"}, "needs": ["s2", "s3"]},
    {"id": "s5", "tool": "send_sms", "args": {"to": "Sam", "text": "Both pizzas cost ${s4.total}"}, "needs": ["s4", "s1"]},
]
print(json.dumps(PLAN[3]))
print("'$s2.price' means: take the 'price' that step s2 produced.")


# ====================================================================
# Part 4 · Which step can go first?
# ====================================================================

def order_of(needs):
    done, order = set(), []
    while len(order) < len(needs):
        ready = sorted(s for s in needs if s not in done and all(d in done for d in needs[s]))
        if not ready:
            raise ValueError("the steps wait for each other in a circle")
        order.append(ready[0])
        done.add(ready[0])
    return order

needs = {s["id"]: list(s.get("needs", [])) for s in PLAN}
print("needs:", needs)
print("order:", order_of(needs))

circle = {"a": ["b"], "b": ["a"]}
try:
    order_of(circle)
except ValueError as e:
    print("caught:", e)


# ====================================================================
# Part 5 · Check the plan before running it
# ====================================================================

def validate_plan(plan, tools=TOOLS):
    problems, ids = [], [s["id"] for s in plan]
    for s in plan:
        if s["tool"] not in tools:
            problems.append(f"{s['id']}: unknown tool {s['tool']!r}")
        for d in s.get("needs", []):
            if d not in ids:
                problems.append(f"{s['id']}: needs {d!r}, which does not exist")
    if not problems:
        try:
            order_of({s["id"]: list(s.get("needs", [])) for s in plan})
        except ValueError as e:
            problems.append(str(e))
    return problems

print("good plan:", validate_plan(PLAN) or "no problems")

# a plan an AI might write on a bad day:
bad_plan = [
    {"id": "a", "tool": "delete_everything", "args": {}},
    {"id": "b", "tool": "add_up", "args": {"a": 1, "b": 2}, "needs": ["zzz"]},
]
for problem in validate_plan(bad_plan):
    print("caught:", problem)


# ====================================================================
# Part 6 · Run it, and survive a failing step
# ====================================================================

def resolve(value, results):
    if isinstance(value, str):
        whole = re.fullmatch(r"\$(\w+)\.(\w+)", value)
        if whole:
            return results[whole.group(1)][whole.group(2)]
        return re.sub(r"\{(\w+)\.(\w+)\}", lambda m: str(results[m.group(1)][m.group(2)]), value)
    return value

def run_plan(plan, tools=TOOLS):
    results, log, failed = {}, [], set()
    by_id = {s["id"]: s for s in plan}
    for sid in order_of({s["id"]: list(s.get("needs", [])) for s in plan}):
        step = by_id[sid]
        if any(d in failed for d in step.get("needs", [])):
            failed.add(sid)
            log.append((sid, "skipped", "a step it needs failed"))
            continue
        try:
            args = {k: resolve(v, results) for k, v in step.get("args", {}).items()}
            results[sid] = tools[step["tool"]](**args)
            log.append((sid, "ok", results[sid]))
        except Exception as e:
            failed.add(sid)
            log.append((sid, "failed", f"{type(e).__name__}: {e}"))
    return results, log

results, log = run_plan(PLAN)
for line in log:
    print(line)
print("Texts sent:", OUTBOX)

# Now Sam asks for a pizza that does not exist. What happens?
broken = [dict(s) for s in PLAN]
broken[2] = {"id": "s3", "tool": "get_price", "args": {"pizza": "pineapple surprise"}}
OUTBOX.clear()
results, log = run_plan(broken)
for line in log:
    print(line)
print("Texts sent:", OUTBOX or "none (good: nothing was sent with a made-up total)")


# ====================================================================
# Part 7 · Where does the AI come in?
# ====================================================================

ask = ("Write a JSON list of steps for a pizza agent. Tools: check_stock(item), get_price(pizza), add_up(a,b), send_sms(to,text). "
       "Each step: id, tool, args, optional needs. Goal: text Sam the total for a garden and a plant power pizza.")
reply = fde_llm.ask(ask)
print(reply[:300])
print("\nIn practice mode the reply is not real JSON, so we keep our hand-written PLAN.")
print("With a real AI you would do: plan = json.loads(reply); problems = validate_plan(plan); only run if there are none.")


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: what you built vs the real tools (this only prints, nothing is installed)
rows = [
    ("idea",               "what you built",               "what real tools add"),
    ("steps and needs",    "list of dicts with needs",     "nodes and edges in a graph"),
    ("order the steps",    "order_of()",                   "a scheduler that runs steps in parallel"),
    ("check the plan",     "validate_plan()",              "typed state and schema checks"),
    ("survive a crash",    "a JSON checkpoint (Class 34)", "a database-backed checkpointer"),
    ("human approval",     "Guard.approve (Class 35)",     "built-in pause and resume for approval"),
]
widths = [max(len(row[i]) for row in rows) for i in range(3)]
for row in rows:
    print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
print()
print("A framework is your toy plan with more features and more people maintaining it.")
