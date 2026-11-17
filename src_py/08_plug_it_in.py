"""Class 8 · Plug It In   (World 2 · Tools & Knowledge 🔌)

Opening mystery: The drawer of cables
Python in this lab:  classes, __init__ and self, methods, dispatch with dictionaries
FDE ideas in this lab: MCP, client and server, JSON-RPC, initialize / tools/list / tools/call, tool discovery

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (08_Plug_It_In.ipynb) and the slides (08_Plug_It_In.html).
Run it:   python 08_plug_it_in.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 08_plug_it_in.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Python: classes
# ====================================================================

class Pizza:
    def __init__(self, size, toppings=None):
        self.size = size
        self.toppings = toppings or []

    def add(self, topping):
        self.toppings.append(topping)
        return self                         # returning self lets you chain calls

    def describe(self):
        extras = ", ".join(self.toppings) if self.toppings else "plain"
        return f"A {self.size} pizza ({extras})"

lunch = Pizza("large")
lunch.add("cheese").add("olives")
print(lunch.describe())
print(lunch.size)
print(Pizza("small").describe())              # a second, separate object


# ====================================================================
# Part 3 · A mini MCP server
# ====================================================================

import json

class PizzaServer:
    """A tiny MCP-style server for the pizza shop."""
    def __init__(self):
        self.orders = {"1042": "in the oven", "1043": "out for delivery"}
        self.tools = {}                      # name -> {"description", "inputSchema", "run"}
        self.add_tool("get_order_status", "Look up the status of an order by number",
                      {"order_id": "string"}, lambda order_id: self.orders.get(order_id, "No such order"))
        self.add_tool("get_opening_hours", "Tell the shop's opening hours", {}, lambda: "Every day, 11:00 to 22:00")

    def add_tool(self, name, description, inputs, run):
        schema = {"type": "object", "properties": {k: {"type": v} for k, v in inputs.items()}, "required": list(inputs)}
        self.tools[name] = {"description": description, "inputSchema": schema, "run": run}

    def handle(self, request):
        method, params = request["method"], request.get("params", {})
        if method == "initialize":
            result = {"serverInfo": {"name": "pizza-server", "version": "0.1"}, "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"tools": [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]} for n, t in self.tools.items()]}
        elif method == "tools/call":
            tool = self.tools[params["name"]]
            result = {"content": [{"type": "text", "text": str(tool["run"](**params.get("arguments", {})))}]}
        else:
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}

server = PizzaServer()
print("Server ready with tools:", list(server.tools))


# ====================================================================
# Part 4 · Connect a client
# ====================================================================

def send(request):
    """Pretend wire: print the message going out and the reply coming back."""
    print("➡️ ", json.dumps(request))
    reply = server.handle(request)
    print("⬅️ ", json.dumps(reply)[:230])
    return reply

send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
print()
listing = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
print()
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_order_status", "arguments": {"order_id": "1043"}}})

def tools_from_server(server):
    """Discover the server's tools and wrap each as a tool for fde_llm.chat_tools."""
    listing = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    wrapped = []
    for t in listing:
        def run(_name=t["name"], **arguments):
            reply = server.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": _name, "arguments": arguments}})
            return reply["result"]["content"][0]["text"]
        wrapped.append({"name": t["name"], "description": t["description"], "parameters": t["inputSchema"], "func": run})
    return wrapped

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

SYSTEM = "You are Pico, the support bot for Pico's Pizza Planet. Use tools. Never guess."
tools = tools_from_server(server)
print("Discovered:", [t["name"] for t in tools])
print(run_with_tools("Where is order '1043'?", tools, SYSTEM))


# ====================================================================
# Part 5 · The payoff
# ====================================================================

server.add_tool("get_special_of_the_day", "Tell today's pizza special", {}, lambda: "Pineapple Dream, $8")

tools = tools_from_server(server)                       # SAME client code as before
print("Now discovered:", [t["name"] for t in tools])
print(run_with_tools("What is today's special?", tools, SYSTEM))
