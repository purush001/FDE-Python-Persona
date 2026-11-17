"""Class 16 · The ReAct Agent   (World 4 · Agents & Evaluation 🤖)

Opening mystery: The lost sock
Python in this lab:  while loops, break, counters, enumerate, building a trace list
FDE ideas in this lab: agents, ReAct loop (Reason, Act, Observe), max_steps, workflow vs agent

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (16_The_ReAct_Agent.ipynb) and the slides (16_The_ReAct_Agent.html).
Run it:   python 16_the_react_agent.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 16_the_react_agent.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 3 · Build the loop
# ====================================================================

ORDERS = {
    "1042": {"status": "in the oven", "minutes_left": 12, "total": 11.0},
    "1043": {"status": "out for delivery", "minutes_left": 5, "total": 20.0},
}

def get_order_status(order_id: str):
    """Look up the status of an order by its number."""
    return ORDERS.get(order_id, "No such order.")

def get_refund_policy(topic: str):
    """Get the shop's refund policy for a topic such as cold pizza or late delivery."""
    return "Refunds: up to 50 percent back if the pizza arrives cold or more than 30 minutes late. Larger refunds need a human."

def calculate_refund(order_total: float, percent: float):
    """Calculate the refund amount in dollars from an order total and a percent."""
    return round(order_total * percent / 100, 2)

TOOLS = [fde_llm.make_tool(f) for f in (get_order_status, get_refund_policy, calculate_refund)]
print("Tools:", [t["name"] for t in TOOLS])

SYSTEM = (
    "You are Pico, an agent for Pico's Pizza Planet. Think about what you need, call tools to find it, "
    "read the results, and only then answer. Never guess numbers: use the tools."
)

def react_agent(goal, tools, system=SYSTEM, max_steps=6):
    """Reason -> Act -> Observe, until the AI answers or we run out of steps."""
    history = [{"role": "user", "text": goal}]
    trace, step = [], 0
    while step < max_steps:                                     # a WHILE loop with a safety limit
        step += 1
        reply = fde_llm.chat_tools(history, tools, system=system)
        if reply["text"] and reply["tool_calls"]:
            trace.append((step, "💭 reason", reply["text"][:90]))
        if not reply["tool_calls"]:                             # no more tools wanted: this is the answer
            trace.append((step, "✅ answer", reply["text"][:90]))
            return reply["text"], trace
        history.append(reply)
        for call in reply["tool_calls"]:
            trace.append((step, "🔧 act", f"{call['name']}({call['args']})"))
            result = fde_llm.run_tool(call, tools)
            trace.append((step, "👀 observe", result["result"][:90]))
            history.append(result)
    return "I ran out of steps. A human will look at this.", trace + [(step, "🛑 stopped", "max_steps reached")]

goal = "Order '1042' arrived cold. The pizza cost 11 dollars. Am I eligible for a refund? Give me 50 percent back if so."
answer, trace = react_agent(goal, TOOLS)
print(answer)


# ====================================================================
# Part 4 · Read the trace
# ====================================================================

for step, kind, detail in trace:
    print(f"step {step}  {kind:<11} {detail}")


# ====================================================================
# Part 5 · Safety limits
# ====================================================================

# A confused agent: a tool that always says "ask again"
def ask_again(topic: str):
    """Look up anything the customer wants to know about."""
    return "I need more information. Please call me again."

loop_tools = [fde_llm.make_tool(ask_again)]

# A stubborn pretend brain that ALWAYS asks for the tool again (for the test only)
def stubborn_brain(history, tools, system=None, **options):
    return {"role": "assistant", "text": "Let me look again...", "provider": "mock", "raw": None,
            "tool_calls": [{"id": f"s{len(history)}", "name": "ask_again", "args": {"topic": "pizza"}}]}

real_chat_tools = fde_llm.chat_tools
fde_llm.chat_tools = stubborn_brain
try:
    stuck_answer, stuck_trace = react_agent("Look up anything about pizza.", loop_tools, max_steps=3)
finally:
    fde_llm.chat_tools = real_chat_tools            # always put the real brain back

print(stuck_answer)
print("steps used:", max(s for s, _, _ in stuck_trace))
print(stuck_trace[-1])
