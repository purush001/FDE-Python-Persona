"""Class 34 · Save Your Place   (World 8 · Agentic Pro 🧭 (advanced))

Opening mystery: Crashed at step 8 of 10
Python in this lab:  json files, os.replace for safe writes, closures that wrap functions, enumerate(items, 1), sets for seen keys
FDE ideas in this lab: checkpoint and resume, retryable vs non-retryable errors, exponential backoff, idempotency keys, atomic writes

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (34_Save_Your_Place.ipynb) and the slides (34_Save_Your_Place.html).
Run it:   python 34_save_your_place.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 34_save_your_place.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The kit from last class
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
print(len(PLAN), 'steps ready. Tools:', list(TOOLS))


# ====================================================================
# Part 3 · Crash it on purpose
# ====================================================================

import json, os, tempfile

class Crash(Exception):
    pass

def crashing_tools(die_on_call):
    # wraps every tool: the Nth call anywhere raises Crash (the power cut)
    calls = {"n": 0}
    def wrap(fn):
        def inner(**kw):
            calls["n"] += 1
            if calls["n"] == die_on_call:
                raise Crash("the internet blinked")
            return fn(**kw)
        return inner
    return {name: wrap(fn) for name, fn in TOOLS.items()}

OUTBOX.clear()
results, log = run_plan(PLAN, crashing_tools(die_on_call=2))
for line in log:
    print(line)
print("Done so far:", sorted(results))


# ====================================================================
# Part 4 · Checkpoints
# ====================================================================

class Checkpoint:
    def __init__(self, path):
        self.path = path
        self.results = json.load(open(path)) if os.path.exists(path) else {}

    def save(self, results):
        tmp = self.path + ".tmp"
        json.dump(results, open(tmp, "w"))
        os.replace(tmp, self.path)            # replace in one move, so a crash cannot leave a half-written file

path = os.path.join(tempfile.gettempdir(), "pico_checkpoint.json")
if os.path.exists(path):
    os.remove(path)

def run_with_checkpoint(plan, tools, path):
    cp = Checkpoint(path)
    results, log = run_plan(plan, tools, results=dict(cp.results))     # steps already in results are skipped
    cp.save(results)
    return results, log

OUTBOX.clear()
first, log1 = run_with_checkpoint(PLAN, crashing_tools(die_on_call=4), path)
print("run 1 finished steps:", sorted(first), "| texts sent:", len(OUTBOX))
second, log2 = run_with_checkpoint(PLAN, TOOLS, path)
print("run 2 finished steps:", sorted(second), "| texts sent:", len(OUTBOX))
print("run 2 only did:", [entry[0] for entry in log2])


# ====================================================================
# Part 5 · Retry, but politely
# ====================================================================

RETRYABLE = {"timeout", "rate_limit", "server_error"}      # worth trying again
# NOT retryable: "bad_request", "not_found", "forbidden": trying again changes nothing

def backoff_delays(tries, base=1, cap=8):
    return [min(cap, base * 2 ** i) for i in range(tries)]

def call_with_retry(fn, tries=4, sleep=lambda s: None):
    waited = []
    for attempt, delay in enumerate(backoff_delays(tries), 1):
        try:
            return fn(), attempt, waited
        except Exception as e:
            if getattr(e, "kind", "") not in RETRYABLE or attempt == tries:
                raise
            waited.append(delay)
            sleep(delay)

class Flaky(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind

state = {"n": 0}
def sometimes_works():
    state["n"] += 1
    if state["n"] < 3:
        raise Flaky("timeout")
    return "ok!"

print(backoff_delays(6))
print(call_with_retry(sometimes_works))
try:
    call_with_retry(lambda: (_ for _ in ()).throw(Flaky("bad_request")))
except Flaky as e:
    print("not retried:", e)


# ====================================================================
# Part 6 · Doing it twice must be safe
# ====================================================================

SENT_KEYS = set()

def send_sms_once(to, text, key):
    # an idempotency key = a name for THIS request. Seen before? Do nothing and say so.
    if key in SENT_KEYS:
        return {"sent": False, "reason": "already sent", "to": to}
    SENT_KEYS.add(key)
    return send_sms(to, text)

OUTBOX.clear()
for attempt in range(3):                      # a retry loop that fires the same request three times
    print(send_sms_once("Sam", "Your pizza is on the way", key="order-1042-notify"))
print("Texts actually sent:", len(OUTBOX))
