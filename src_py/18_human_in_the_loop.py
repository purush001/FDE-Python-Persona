"""Class 18 · Human in the Loop   (World 4 · Agents & Evaluation 🤖)

Opening mystery: The $5,000 refund
Python in this lab:  decorators, functools.wraps, input(), try/except for missing input, lists as logs
FDE ideas in this lab: human approval, risk tiers, default-deny, audit logs, reversible vs irreversible

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (18_Human_in_the_Loop.ipynb) and the slides (18_Human_in_the_Loop.html).
Run it:   python 18_human_in_the_loop.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 18_human_in_the_loop.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Sort the actions
# ====================================================================

RISK = {
    "get_order_status": "low",       # read-only
    "get_menu": "low",
    "send_apology_email": "medium",  # reversible-ish, but visible to the customer
    "refund_order": "high",          # money leaves the shop
}
for tool_name, level in RISK.items():
    icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}[level]
    print(icon, level.upper().ljust(7), tool_name)


# ====================================================================
# Part 3 · Python: decorators
# ====================================================================

import functools

def shout(func):
    @functools.wraps(func)                       # keeps the original name and description
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return str(result).upper() + "!"
    return wrapper

@shout
def hello(name):
    """Say hello."""
    return "hello " + name

print(hello("pico"))
print(hello.__name__)       # still 'hello', thanks to functools.wraps


# ====================================================================
# Part 4 · Guard the dangerous tools
# ====================================================================

HUMAN = "ask me"

AUDIT_LOG = []                                    # a written record of every decision

def confirm(question):
    """Ask a human yes/no. If nobody can answer, the safe answer is NO (default-deny)."""
    if HUMAN == "always yes (demo)":
        answer = "yes"
    elif HUMAN == "always no (demo)":
        answer = "no"
    else:
        try:
            answer = input(question + " [yes/no] ")
        except Exception:                         # no keyboard available (for example in a test run)
            print(question, "\n   (no human here: defaulting to NO, the safe answer)")
            answer = "no"
    approved = answer.strip().lower() in ("y", "yes")
    AUDIT_LOG.append({"question": question, "approved": approved})
    return approved

def ask_human_first(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        shown = ", ".join([*map(str, args), *[f"{k}={v}" for k, v in kwargs.items()]])
        if confirm(f"🙋 Pico wants to run {func.__name__}({shown}). Allow?"):
            return func(*args, **kwargs)
        return "DENIED: a human said no. Tell the customer a human agent will follow up."
    return wrapper

ORDERS = {"1042": {"status": "in the oven", "total": 11.0}, "1043": {"status": "out for delivery", "total": 20.0}}

def get_order_status(order_id: str):
    """Look up the status of an order by its number."""
    return ORDERS.get(order_id, "No such order.")

@ask_human_first
def refund_order(order_id: str, amount: float):
    """Refund money to the customer for an order. Needs human approval."""
    return f"Refunded ${amount} for order {order_id}."

TOOLS = [fde_llm.make_tool(get_order_status), fde_llm.make_tool(refund_order)]
print([(t["name"], t["description"]) for t in TOOLS])


# ====================================================================
# Part 5 · Run it with a human
# ====================================================================

def run_with_tools(question, tools, system, max_rounds=5):
    history = [{"role": "user", "text": question}]
    for _ in range(max_rounds):
        reply = fde_llm.chat_tools(history, tools, system=system)
        if not reply["tool_calls"]:
            return reply["text"]
        history.append(reply)
        for call in reply["tool_calls"]:
            print(f"   🔧 {call['name']}({call['args']})")
            history.append(fde_llm.run_tool(call, tools))
    return "I could not finish."

SYSTEM = "You are Pico's support agent. Use tools. For refunds, use refund_order; a human will approve it."
print(run_with_tools("Please refund order '1042' for 5.5 dollars because the pizza was cold.", TOOLS, SYSTEM))

print("Audit log:")
for entry in AUDIT_LOG:
    print("  ", "✅ approved" if entry["approved"] else "❌ denied  ", "|", entry["question"][:80])
