"""Class 37 · What Is MCP, Really   (World 9 · Many MCPs 🔌 (advanced))

Opening mystery: The drawer of cables
Python in this lab:  json.dumps / json.loads, subprocess and pipes, stdin / stdout, try / except KeyError, writing a file from a string
FDE ideas in this lab: MCP: one standard plug for tools, JSON-RPC requests, responses, errors, notifications, initialize / tools/list / tools/call, isError vs a protocol error, tool descriptions are prompts

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (37_What_Is_MCP_Really.ipynb) and the slides (37_What_Is_MCP_Really.html).
Run it:   python 37_what_is_mcp_really.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 37_what_is_mcp_really.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · A message is just a dictionary
# ====================================================================

import json

request  = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_price", "arguments": {"pizza": "garden"}}}
response = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "{\"price\": 11}"}], "isError": False}}
error    = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "method not found"}}
notice   = {"jsonrpc": "2.0", "method": "notifications/initialized"}            # no id = no reply expected

for name, message in (("request", request), ("response", response), ("error", error), ("notification", notice)):
    print(f"{name:<13}", json.dumps(message))


# ====================================================================
# Part 3 · Build a server in 30 lines
# ====================================================================

TINY = r'''
import json, sys

PRICES = {"garden": 11, "plant power": 12, "margherita": 9}

def handle(request):
    method, rid = request.get("method"), request.get("id")
    if rid is None:
        return None                                     # notification: stay silent
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"serverInfo": {"name": "tiny", "version": "0.1"}, "capabilities": {"tools": {}}}}
    if method == "tools/list":
        tool = {"name": "get_price", "description": "Get the price of a pizza by name", "inputSchema": {"type": "object", "properties": {"pizza": {"type": "string"}}}}
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [tool]}}
    if method == "tools/call":
        args = request["params"].get("arguments", {})
        try:
            value = {"price": PRICES[args["pizza"].lower()]}
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}}
        except KeyError:
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": "no such pizza"}], "isError": True}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}

for line in sys.stdin:
    if line.strip():
        reply = handle(json.loads(line))
        if reply is not None:
            print(json.dumps(reply), flush=True)
'''
open("tiny_server.py", "w").write(TINY)
print("wrote tiny_server.py:", len(TINY.splitlines()), "lines")


# ====================================================================
# Part 4 · Say hello to it
# ====================================================================

import subprocess, sys

messages = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_price", "arguments": {"pizza": "Garden"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_price", "arguments": {"pizza": "pineapple"}}},
    {"jsonrpc": "2.0", "id": 5, "method": "dance/party"},
]
out = subprocess.run([sys.executable, "tiny_server.py"], input="\n".join(json.dumps(m) for m in messages) + "\n", capture_output=True, text=True, timeout=20)
for line in out.stdout.splitlines():
    print(line[:150])
print("\n(5 requests with ids, 1 notification: 5 replies. Count them.)")


# ====================================================================
# Part 5 · The client side
# ====================================================================

import subprocess, sys, json, threading, queue

class McpClient:
    # talks to ONE server: JSON-RPC messages, one per line, over its stdin/stdout
    def __init__(self, server, script="mini_servers.py"):
        self.name = server
        self.proc = subprocess.Popen([sys.executable, script, server], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.lines, self.next_id = queue.Queue(), 1
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line)

    def request(self, method, params=None, timeout=5):
        rid, self.next_id = self.next_id, self.next_id + 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        while True:
            try:
                line = self.lines.get(timeout=timeout)
            except queue.Empty:
                raise TimeoutError(f"{self.name}: no answer to {method} within {timeout}s")
            message = json.loads(line)
            if message.get("id") == rid:                    # ignore late answers to old requests
                break
        if "error" in message:
            raise RuntimeError(f"{message['error']['code']}: {message['error']['message']}")
        return message["result"]

    def initialize(self):
        return self.request("initialize", {"clientInfo": {"name": "pico-client"}})

    def list_tools(self):
        return self.request("tools/list")["tools"]

    def call(self, tool, arguments=None, timeout=5):
        result = self.request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout)
        text = result["content"][0]["text"]
        if result.get("isError"):
            raise RuntimeError(text)
        return json.loads(text)

    def close(self):
        self.proc.terminate()
client = McpClient('tiny', script='tiny_server.py')
print(client.initialize())
print([t['name'] for t in client.list_tools()])
print(client.call('get_price', {'pizza': 'plant power'}))
client.close()


# ====================================================================
# Part 6 · What the model actually sees
# ====================================================================

client = McpClient('tiny', script='tiny_server.py')
client.initialize()
tools = client.list_tools()
menu = "\n".join(f"- {t['name']}: {t['description']}" for t in tools)
print("This text is ALL the model knows about your tool:\n" + menu)
reply = fde_llm.ask("Which tool would you use to find out what a Garden pizza costs?", system="You can use these tools:\n" + menu)
print("\nPico (practice mode):", reply[:120])
client.close()
