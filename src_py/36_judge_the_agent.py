"""Class 36 · Judge the Agent   (World 8 · Agentic Pro 🧭 (advanced))

Opening mystery: The lucky answer
Python in this lab:  dict of checks, all() and any(), random.Random(seed), json.dumps(sort_keys=True), slicing runs[:k]
FDE ideas in this lab: trajectory evaluation, pass@k vs pass^k, replay and regression, safety checks as pass/fail, release gate for agents

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (36_Judge_the_Agent.ipynb) and the slides (36_Judge_the_Agent.html).
Run it:   python 36_judge_the_agent.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 36_judge_the_agent.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The kit and two agents
# ====================================================================

import json, re

# ---- a tiny pizza-shop world with four tools ---------------------------------
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

# ---- plans are DATA: a list of steps, each with an id, a tool, args and what it needs first ----
def order_of(needs):
    # which step can go first? (a step is ready when everything it needs is done)
    done, order = set(), []
    while len(order) < len(needs):
        ready = sorted(s for s in needs if s not in done and all(d in done for d in needs[s]))
        if not ready:
            raise ValueError("the steps wait for each other in a circle")
        order.append(ready[0])
        done.add(ready[0])
    return order

def resolve(value, results):
    # "$s2.price" -> the raw value;  "Total: {s4.total}" -> text with the value filled in
    if isinstance(value, str):
        whole = re.fullmatch(r"\$(\w+)\.(\w+)", value)
        if whole:
            return results[whole.group(1)][whole.group(2)]
        return re.sub(r"\{(\w+)\.(\w+)\}", lambda m: str(results[m.group(1)][m.group(2)]), value)
    return value

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

def run_plan(plan, tools=TOOLS, results=None, log=None):
    results = results if results is not None else {}
    log = log if log is not None else []
    by_id, failed = {s["id"]: s for s in plan}, set()
    for sid in order_of({s["id"]: list(s.get("needs", [])) for s in plan}):
        if sid in results:                                   # already done (used by resume in Class 34)
            continue
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

PLAN = [
    {"id": "s1", "tool": "check_stock", "args": {"item": "cheese"}},
    {"id": "s2", "tool": "get_price", "args": {"pizza": "garden"}},
    {"id": "s3", "tool": "get_price", "args": {"pizza": "plant power"}},
    {"id": "s4", "tool": "add_up", "args": {"a": "$s2.price", "b": "$s3.price"}, "needs": ["s2", "s3"]},
    {"id": "s5", "tool": "send_sms", "args": {"to": "Sam", "text": "Both pizzas cost ${s4.total}"}, "needs": ["s4", "s1"]},
]

def careful_agent(goal):
    OUTBOX.clear()
    results, log = run_plan(PLAN)
    return {"answer": results["s4"]["total"], "trajectory": [(step["tool"], step.get("args", {})) for step in PLAN], "texts": list(OUTBOX)}

def sloppy_agent(goal):
    OUTBOX.clear()
    send_sms(to="Sam", text="Both pizzas cost $23")          # guessed the total and acted before checking stock
    send_sms(to="Sam", text="Both pizzas cost $23")          # ...twice
    return {"answer": 23, "trajectory": [("send_sms", {"to": "Sam"}), ("send_sms", {"to": "Sam"})], "texts": list(OUTBOX)}

for agent in (careful_agent, sloppy_agent):
    out = agent("total for garden + plant power")
    print(agent.__name__, "->", out["answer"], "| tools:", [t for t, _ in out["trajectory"]], "| texts:", len(out["texts"]))


# ====================================================================
# Part 3 · Check the trajectory
# ====================================================================

def judge(run, must_use=(), must_not_repeat=("send_sms",), max_steps=8, expected_answer=None):
    tools_used = [t for t, _ in run["trajectory"]]
    checks = {
        "answer is right": expected_answer is None or run["answer"] == expected_answer,
        "looked things up first": all(t in tools_used for t in must_use),
        "no repeated side effects": all(tools_used.count(t) <= 1 for t in must_not_repeat),
        "within the step limit": len(tools_used) <= max_steps,
    }
    return checks

for agent in (careful_agent, sloppy_agent):
    checks = judge(agent("goal"), must_use=("get_price", "check_stock"), expected_answer=23)
    print(f"{agent.__name__}:")
    for name, ok in checks.items():
        print("   ", "✅" if ok else "❌", name)


# ====================================================================
# Part 4 · Run it more than once
# ====================================================================

import random

def flaky_agent(p_success, rng):
    # a stand-in for a real agent that works with probability p_success
    return rng.random() < p_success

def run_suite(p_success, tasks=20, runs=5, seed=7):
    rng = random.Random(seed)
    return [[flaky_agent(p_success, rng) for _ in range(runs)] for _ in range(tasks)]

def pass_at_k(results, k):            # did it succeed AT LEAST ONCE in k tries?
    return sum(1 for r in results if any(r[:k])) / len(results) if results else 0.0

def pass_all_k(results, k):           # did it succeed EVERY time in k tries?
    return sum(1 for r in results if all(r[:k])) / len(results) if results else 0.0

results = run_suite(0.85)
print(f"{'k':>3}{'pass@k (once)':>16}{'pass^k (every time)':>22}")
for k in (1, 3, 5):
    print(f"{k:>3}{pass_at_k(results, k):>16.2f}{pass_all_k(results, k):>22.2f}")


# ====================================================================
# Part 5 · Replay, then a release gate
# ====================================================================

import json

def record(run):
    return json.dumps({"answer": run["answer"], "trajectory": run["trajectory"]}, sort_keys=True)

old = record(careful_agent("goal"))
new = record(careful_agent("goal"))
print("same journey as last release?", old == new)

def release_gate(passk_old, passk_new, safety_checks_pass, tolerance=0.02):
    if not safety_checks_pass:
        return "BLOCK: a safety check failed"
    if passk_new + tolerance < passk_old:
        return "BLOCK: it got worse"
    return "SHIP"

print(release_gate(0.55, 0.60, True))
print(release_gate(0.55, 0.40, True))
print(release_gate(0.55, 0.90, False))
