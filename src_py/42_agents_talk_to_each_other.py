"""Class 42 · Agents Talk to Each Other   (World 10 · The Agent Board 💬 (advanced))

Opening mystery: Thank you, thank you, thank you
Python in this lab:  classes with handlers, functions as arguments, re.findall with a group, while loops with a round cap, string building for handoffs
FDE ideas in this lab: specialist agents with lanes, @mention routing, loop prevention (depth, self, mention), handoffs between agents, a round cap as a safety net

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (42_Agents_Talk_to_Each_Other.ipynb) and the slides (42_Agents_Talk_to_Each_Other.html).
Run it:   python 42_agents_talk_to_each_other.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 42_agents_talk_to_each_other.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The board and its agents
# ====================================================================

import re, sqlite3, hmac, hashlib, secrets

class Board:
    # a message board in SQLite: channels, authors, replies. A tick counter stands in for the clock, so runs are repeatable.
    COLUMNS = ("id", "channel", "author", "text", "reply_to", "ts", "sig")

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, author TEXT NOT NULL, "
                        "text TEXT NOT NULL, reply_to INTEGER, ts INTEGER NOT NULL, sig TEXT NOT NULL DEFAULT '')")
        self.tick = 0

    def post(self, channel, author, text, reply_to=None, sig=""):
        self.tick += 1
        cur = self.db.execute("INSERT INTO posts (channel, author, text, reply_to, ts, sig) VALUES (?, ?, ?, ?, ?, ?)",
                              (channel, author, text, reply_to, self.tick, sig))
        self.db.commit()
        return cur.lastrowid

    def read(self, channel=None, after_id=0):
        sql, args = "SELECT id, channel, author, text, reply_to, ts, sig FROM posts WHERE id > ?", [after_id]
        if channel:
            sql, args = sql + " AND channel = ?", args + [channel]
        return [dict(zip(self.COLUMNS, row)) for row in self.db.execute(sql + " ORDER BY id", args)]

    def get(self, post_id):
        rows = self.db.execute("SELECT id, channel, author, text, reply_to, ts, sig FROM posts WHERE id = ?", (post_id,)).fetchall()
        return dict(zip(self.COLUMNS, rows[0])) if rows else None

def mentions(text):
    return re.findall(r"@(\w+)", text.lower())

def thread_depth(board, post_id):
    depth, row = 0, board.get(post_id)
    while row and row["reply_to"]:
        depth, row = depth + 1, board.get(row["reply_to"])
    return depth

PRICES = {"garden": 11, "plant power": 12, "margherita": 9}
STOCK = {"cheese": 5, "dough": 12, "basil": 0}

def price_handler(post):
    found = [p for p in PRICES if p in post["text"].lower()]
    return "Prices: " + ", ".join(f"{p} ${PRICES[p]}" for p in found) if found else None

def stock_handler(post):
    found = [i for i in STOCK if i in post["text"].lower()]
    return "Stock: " + ", ".join(f"{i} {STOCK[i]}" for i in found) if found else None

class Agent:
    # reads new posts, replies only when @mentioned, never to itself, never too deep in a thread
    def __init__(self, name, handler, max_depth=3, signer=None, skip=None):
        self.name, self.handler, self.max_depth, self.seen = name, handler, max_depth, 0
        self.signer, self.skip = signer, skip                # signer(name, text) -> signature;  skip(post) -> True to ignore a post

    def step(self, board):
        replies = 0
        for post in board.read(after_id=self.seen):
            self.seen = post["id"]
            if post["author"] == self.name or self.name not in mentions(post["text"]):
                continue
            if self.skip and self.skip(post):
                continue
            if thread_depth(board, post["id"]) >= self.max_depth:
                continue
            answer = self.handler(post)
            if answer:
                board.post(post["channel"], self.name, answer, reply_to=post["id"], sig=self.signer(self.name, answer) if self.signer else "")
                replies += 1
        return replies

def run_agents(board, agents, max_rounds=10):
    for round_number in range(1, max_rounds + 1):
        if sum(agent.step(board) for agent in agents) == 0:
            return round_number                                  # quiet: nobody had anything to say
    return max_rounds

def show(board, channel=None):
    names = {p["id"]: p for p in board.read()}
    for p in board.read(channel):
        indent = "    " * thread_depth(board, p["id"])
        print(f"{indent}#{p['id']} [{p['channel']}] {p['author']}: {p['text']}")
print('Board, Agent, mentions, thread_depth, run_agents ready')


# ====================================================================
# Part 3 · Specialists
# ====================================================================

board = Board()
agents = [Agent("pricebot", price_handler), Agent("stockbot", stock_handler)]

board.post("menu", "sam", "@pricebot what does the garden cost? and the plant power?")
board.post("kitchen", "mario", "@stockbot how much cheese and basil is left?")
rounds = run_agents(board, agents)
show(board)
print("quiet after", rounds, "rounds")


# ====================================================================
# Part 4 · Break it: the thank-you loop
# ====================================================================

def polite(other):
    return lambda post: "Thank you! @" + other           # always replies, always @mentions the other bot

loop_board = Board()
a, b = Agent("anna", polite("bob"), max_depth=10**9), Agent("bob", polite("anna"), max_depth=10**9)
loop_board.post("chat", "sam", "@anna say hi to @bob")
rounds = run_agents(loop_board, [a, b], max_rounds=15)
print("rounds run:", rounds, "(stopped only because WE capped at 15)")
print("posts written:", len(loop_board.read()))


# ====================================================================
# Part 5 · Three rules that stop it
# ====================================================================

def should_reply(post, me, depth, max_depth=3):
    if post["author"] == me:
        return False                                      # rule 1: never answer yourself
    if depth >= max_depth:
        return False                                      # rule 2: do not go too deep in one thread
    return me in mentions(post["text"])                   # rule 3: only when someone @mentions me

print(should_reply({"author": "sam", "text": "@anna hi"}, "anna", 0))
print(should_reply({"author": "anna", "text": "@anna hi"}, "anna", 0))
print(should_reply({"author": "sam", "text": "@anna hi"}, "anna", 3))

safe_board = Board()
a, b = Agent("anna", polite("bob"), max_depth=3), Agent("bob", polite("anna"), max_depth=3)
safe_board.post("chat", "sam", "@anna say hi to @bob")
rounds = run_agents(safe_board, [a, b], max_rounds=15)
print("\nwith limits -> rounds:", rounds, "| posts:", len(safe_board.read()))
show(safe_board)


# ====================================================================
# Part 6 · Handoffs
# ====================================================================

def concierge(post):
    text = post["text"].lower()
    if "cost" in text or "price" in text:
        return "Let me ask @pricebot: " + post["text"].replace("@concierge", "").strip() + " @pricebot"       # hand off
    return None

team = Board()
agents = [Agent("concierge", concierge), Agent("pricebot", price_handler)]
team.post("menu", "sam", "@concierge what does the garden cost?")
run_agents(team, agents)
show(team)
