"""Class 7 · Tool Calling   (World 2 · Tools & Knowledge 🔌)

Opening mystery: Order #4821, where are you?
Python in this lab:  functions as tools, type hints, docstrings, dicts as fake databases, while loops
FDE ideas in this lab: tool calling, the tool loop, parallel calls, errors as results, built-in tools (web search)

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (07_Tool_Calling.ipynb) and the slides (07_Tool_Calling.html).
Run it:   python 07_tool_calling.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 07_tool_calling.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Write the tools
# ====================================================================

ORDERS = {
    "1042": {"status": "in the oven", "minutes_left": 12},
    "1043": {"status": "out for delivery", "minutes_left": 5},
}
PRICES = {"margherita": 9.0, "pepperoni": 11.0, "veggie": 10.0}

def get_order_status(order_id: str):
    """Look up the status of a customer's order by its order number."""
    if order_id not in ORDERS:
        return f"No order with number {order_id} was found."
    return ORDERS[order_id]

def get_price(item: str):
    """Get the price in dollars of one menu item."""
    return PRICES.get(item.lower(), "That item is not on the menu.")

TOOLS = [fde_llm.make_tool(get_order_status), fde_llm.make_tool(get_price)]
for tool in TOOLS:
    print(tool["name"], "->", tool["description"])
    print("   inputs:", list(tool["parameters"]["properties"]))


# ====================================================================
# Part 3 · One round, by hand
# ====================================================================

question = "Where is order '1042'?"
history = [{"role": "user", "text": question}]

step1 = fde_llm.chat_tools(history, TOOLS, system="You are Pico, the support bot for Pico's Pizza Planet.")
print("AI text:      ", repr(step1["text"]))
print("AI wants tools:", [(c["name"], c["args"]) for c in step1["tool_calls"]])

history.append(step1)                                    # remember what the AI said
for call in step1["tool_calls"]:
    result_message = fde_llm.run_tool(call, TOOLS)       # YOUR code runs the function
    print("Tool result:", result_message["result"])
    history.append(result_message)

step2 = fde_llm.chat_tools(history, TOOLS, system="You are Pico, the support bot for Pico's Pizza Planet.")
print("Final answer:", step2["text"])


# ====================================================================
# Part 4 · The tool loop
# ====================================================================

def run_with_tools(question, tools, system, max_rounds=5):
    """The loop: ask -> run any tools the AI wants -> ask again -> until it just answers."""
    history = [{"role": "user", "text": question}]
    for round_number in range(1, max_rounds + 1):
        reply = fde_llm.chat_tools(history, tools, system=system)
        if not reply["tool_calls"]:
            return reply["text"]
        history.append(reply)
        for call in reply["tool_calls"]:                    # may be SEVERAL at once (parallel calls)
            print(f"   round {round_number}: 🔧 {call['name']}({call['args']})")
            history.append(fde_llm.run_tool(call, tools))
    return "I could not finish. Let me get a human to help."   # safety limit

SYSTEM = "You are Pico, the support bot for Pico's Pizza Planet. Use tools for order and price questions. Never guess."
print(run_with_tools("What is the status of order '1043' and the price of 'pepperoni'?", TOOLS, SYSTEM))

print(run_with_tools("Where is order '9999'?", TOOLS, SYSTEM))

def explode(reason: str):
    """A broken tool, to test error handling."""
    raise RuntimeError("the oven computer is down")

message = fde_llm.run_tool({"id": "x1", "name": "explode", "args": {"reason": "test"}}, [fde_llm.make_tool(explode)])
print(message["result"])


# ====================================================================
# Part 5 · Same tool, three dialects
# ====================================================================

import json
spec = next(t for t in TOOLS if t["name"] == "get_order_status")
neutral = {key: spec[key] for key in ("name", "description", "parameters")}       # the menu card, without the function itself

def to_claude(tool):
    return {"name": tool["name"], "description": tool["description"], "input_schema": tool["parameters"]}

def to_openai(tool):
    return {"type": "function", "function": {"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]}}

def to_gemini(tool):
    return {"functionDeclarations": [{"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]}]}

for name, convert in (("🟠 Claude", to_claude), ("🟢 OpenAI", to_openai), ("🔵 Gemini", to_gemini)):
    print("=====", name, "=====")
    print(json.dumps(convert(neutral), indent=2))

# What each provider sends back when the AI wants a tool (shortened, but the shapes are real)
claude_reply = {"content": [{"type": "text", "text": "Let me check that."},
                            {"type": "tool_use", "id": "toolu_01", "name": "get_order_status", "input": {"order_id": "1042"}}]}
openai_reply = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                            {"id": "call_01", "type": "function", "function": {"name": "get_order_status", "arguments": '{"order_id": "1042"}'}}]}}]}
gemini_reply = {"candidates": [{"content": {"role": "model", "parts": [
                            {"functionCall": {"name": "get_order_status", "args": {"order_id": "1042"}}}]}}]}

def read_calls(provider, reply):
    """Every provider hides the 'please run this tool' message in a different spot. Return one simple list."""
    if provider == "claude":
        return [{"id": b["id"], "name": b["name"], "args": b["input"]} for b in reply["content"] if b["type"] == "tool_use"]
    if provider == "openai":
        calls = reply["choices"][0]["message"].get("tool_calls") or []
        return [{"id": c["id"], "name": c["function"]["name"], "args": json.loads(c["function"]["arguments"])} for c in calls]   # arguments is TEXT
    if provider == "gemini":
        parts = reply["candidates"][0]["content"]["parts"]
        found = [p["functionCall"] for p in parts if "functionCall" in p]
        return [{"id": f"call_{i}", "name": c["name"], "args": c["args"]} for i, c in enumerate(found)]

seen = {"claude": claude_reply, "openai": openai_reply, "gemini": gemini_reply}
for provider, reply in seen.items():
    print(f"{provider:<7}", read_calls(provider, reply))
same = read_calls("claude", claude_reply)[0]["args"] == read_calls("openai", openai_reply)[0]["args"] == read_calls("gemini", gemini_reply)[0]["args"]
print("\n✅ Three dialects, one meaning!" if same else "❌ They disagree")

def result_message(provider, call, result):
    """How you hand the tool's answer back. Again, three spellings."""
    if provider == "claude":
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call["id"], "content": result}]}
    if provider == "openai":
        return {"role": "tool", "tool_call_id": call["id"], "content": result}
    if provider == "gemini":
        return {"role": "user", "parts": [{"functionResponse": {"name": call["name"], "response": {"result": result}}}]}

call = read_calls("openai", openai_reply)[0]
answer = fde_llm.run_tool(call, TOOLS)["result"]          # YOUR code runs the tool, whatever the dialect
print("Tool result:", answer, "\n")
for provider in ("claude", "openai", "gemini"):
    print(provider, "→", json.dumps(result_message(provider, call, answer)))


# ====================================================================
# Part 6 · Built-in tools
# ====================================================================

result = fde_llm.ask_with_search("What is a good topping to put on a Hawaiian pizza? Answer in one sentence.")
print(result["text"])
for source in result["sources"][:3]:
    print("🔗", source["title"], "-", source["url"])
