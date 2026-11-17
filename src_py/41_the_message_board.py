"""Class 41 · The Message Board   (World 10 · The Agent Board 💬 (advanced))

Opening mystery: The sticky-note kitchen
Python in this lab:  sqlite3 and SQL, parameterised queries (?), dict(zip(...)), re.findall, a class with a step() loop
FDE ideas in this lab: a shared board as coordination, channels, authors and replies, polling with after_id, threads, SQL injection defence

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (41_The_Message_Board.ipynb) and the slides (41_The_Message_Board.html).
Run it:   python 41_the_message_board.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 41_the_message_board.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · A board in 20 lines of SQL
# ====================================================================

import sqlite3

db = sqlite3.connect(":memory:")                 # a database that lives in memory (gone when the notebook stops)
db.execute('''CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    reply_to INTEGER
)''')

def post(channel, author, text, reply_to=None):
    cur = db.execute("INSERT INTO posts (channel, author, text, reply_to) VALUES (?, ?, ?, ?)", (channel, author, text, reply_to))
    db.commit()
    return cur.lastrowid

first = post("kitchen", "mario", "Cheese order arrives Tuesday.")
post("kitchen", "driver", "Thanks! I will plan the route.", reply_to=first)
post("menu", "sam", "Is the Garden Special vegan?")
print(db.execute("SELECT id, channel, author, text FROM posts").fetchall())

nasty = "x'); DROP TABLE posts; --"
post("menu", "eve", nasty)                       # stored as plain text, not run
print("posts still there:", db.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
print("the nasty text is just text:", db.execute("SELECT text FROM posts ORDER BY id DESC LIMIT 1").fetchone()[0])


# ====================================================================
# Part 3 · Read the board
# ====================================================================

def read(channel=None, after_id=0):
    sql, args = "SELECT id, channel, author, text, reply_to FROM posts WHERE id > ?", [after_id]
    if channel:
        sql, args = sql + " AND channel = ?", args + [channel]
    rows = db.execute(sql + " ORDER BY id", args).fetchall()
    return [dict(zip(("id", "channel", "author", "text", "reply_to"), r)) for r in rows]

print("kitchen channel:")
for p in read("kitchen"):
    print("  ", p)
print("\nanything after id 2:", [p["id"] for p in read(after_id=2)])


# ====================================================================
# Part 4 · An agent that reads the wall
# ====================================================================

import re

def mentions(text):
    return re.findall(r"@(\w+)", text.lower())

class EchoBot:
    def __init__(self, name):
        self.name, self.seen = name, 0

    def step(self):
        for p in read(after_id=self.seen):
            self.seen = p["id"]
            if p["author"] != self.name and self.name in mentions(p["text"]):
                post(p["channel"], self.name, f"Hello {p['author']}! You said: {p['text'][:30]}...", reply_to=p["id"])

bot = EchoBot("pico")
post("menu", "sam", "Hey @pico, what is good today?")
bot.step()
for p in read("menu"):
    print(p["id"], p["author"], "->", p["text"][:50], "| reply to", p["reply_to"])


# ====================================================================
# Part 5 · Threads
# ====================================================================

def thread_depth(post_id):
    depth = 0
    row = db.execute("SELECT reply_to FROM posts WHERE id = ?", (post_id,)).fetchone()
    while row and row[0]:
        depth += 1
        row = db.execute("SELECT reply_to FROM posts WHERE id = ?", (row[0],)).fetchone()
    return depth

for p in read():
    print("    " * thread_depth(p["id"]) + f"#{p['id']} {p['author']}: {p['text'][:42]}")


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: what you built vs the real tools (this only prints, nothing is installed)
rows = [
    ("idea",              "what you built",            "what real tools use"),
    ("store posts",       "SQLite in memory",          "Postgres on disk"),
    ("read what is new",  "after_id",                  "an offset or cursor"),
    ("many readers",      "each Agent keeps .seen",    "consumer groups"),
    ("safe inserts",      "? placeholders",            "prepared statements"),
    ("proof of author",   "HMAC signature",            "public-key signatures, key rotation"),
]
widths = [max(len(row[i]) for row in rows) for i in range(3)]
for row in rows:
    print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
print()
print("A board is a table plus a bookmark. Everything bigger is the same idea at scale.")
