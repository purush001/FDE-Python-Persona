"""Class 27 · The Blueprint   (World 6 · Pro Skills 🎓 (bonus))

Opening mystery: The name that deleted the orders
Python in this lab:  sqlite3: connect, execute, fetchall, placeholders (?), tuples and parameters, with and commit, urllib.parse, hmac
FDE ideas in this lab: AI application and system architecture, database connections and connection strings, SQL injection and read-only access, scaling: stateless servers, queues, caches, enterprise integration: SSO, roles, data governance, webhooks

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (27_The_Blueprint.ipynb) and the slides (27_The_Blueprint.html).
Run it:   python 27_the_blueprint.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 27_the_blueprint.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · Scaling in three moves
# ====================================================================

QUESTIONS = ["When do you open?", "Where is my order?", "When do you open?", "When do you open?",
             "Do you sell wine?", "Where is my order?", "When do you open?", "When do you open?"]
COST_PER_CALL = 0.002                                  # dollars, a made-up number

def cacheable(q):
    return " my " not in " " + q.lower() + " "         # personal questions must NOT be shared

def slow_answer(q):
    return "answer to " + q                            # pretend this is a real AI call

cache, hits, ai_calls = {}, 0, 0
for q in QUESTIONS:
    if cacheable(q) and q in cache:
        hits += 1
    else:
        ai_calls += 1
        answer = slow_answer(q)
        if cacheable(q):
            cache[q] = answer
print(f"{len(QUESTIONS)} questions: {hits} answered from the cache, {ai_calls} AI calls")


# ====================================================================
# Part 3 · Connect a database
# ====================================================================

import sqlite3

conn = sqlite3.connect(":memory:")        # a database that lives in RAM (a real one lives on a server or in a file)
conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, name TEXT, status TEXT, total REAL, created TEXT)")
rows = [(1, "Ana", "delivered", 18.5, "2026-10-01"),
        (2, "Ben", "cooking",   12.0, "2026-11-12"),
        (3, "Ana", "cooking",    9.0, "2026-11-13"),
        (4, "Cy",  "late",      30.0, "2026-11-14")]
conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", rows)
conn.commit()                              # commit = save the change

for row in conn.execute("SELECT id, name, status FROM orders ORDER BY id"):
    print(row)

evil = "x' OR '1'='1"

unsafe_sql = f"SELECT id, name FROM orders WHERE name = '{evil}'"
print("UNSAFE command text:", unsafe_sql)
print("rows it returns    :", conn.execute(unsafe_sql).fetchall())

print()
print("SAFE (placeholder) :", conn.execute("SELECT id, name FROM orders WHERE name = ?", (evil,)).fetchall())
print("A normal name      :", conn.execute("SELECT id, name FROM orders WHERE name = ?", ("Ana",)).fetchall())


# ====================================================================
# Part 4 · Read-only, tools and memory
# ====================================================================

from pathlib import Path

Path("pico_orders.db").unlink(missing_ok=True)         # start fresh every run
admin = sqlite3.connect("pico_orders.db")              # the 'admin' login: can read AND write
admin.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, name TEXT, status TEXT, total REAL)")
admin.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [(1, "Ana", "delivered", 18.5), (2, "Ben", "cooking", 12.0), (3, "Ana", "cooking", 9.0)])
admin.commit()
admin.close()

readonly = sqlite3.connect("file:pico_orders.db?mode=ro", uri=True)   # the 'lookup' login: can only read
print("read works :", readonly.execute("SELECT COUNT(*) FROM orders").fetchone())
try:
    readonly.execute("DELETE FROM orders")
except sqlite3.OperationalError as error:
    print("write blocked:", error)

def lookup_order(order_id: int):
    # Look up ONE order by its number. Read-only: it can never change an order.
    row = readonly.execute("SELECT id, status, total FROM orders WHERE id = ?", (order_id,)).fetchone()
    return {"id": row[0], "status": row[1], "total": row[2]} if row else {"error": "no such order"}

print(lookup_order(3))
print(lookup_order(999))

class MemoryDB:
    # Pico's long-term memory, kept in a database file so it survives a restart.
    def __init__(self, path="pico_memory.db"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS facts (user TEXT, fact TEXT)")

    def remember(self, user, fact):
        self.conn.execute("INSERT INTO facts VALUES (?, ?)", (user, fact))
        self.conn.commit()

    def recall(self, user):
        return [r[0] for r in self.conn.execute("SELECT fact FROM facts WHERE user = ?", (user,))]

    def forget(self, user):
        self.conn.execute("DELETE FROM facts WHERE user = ?", (user,))
        self.conn.commit()

    def close(self):
        self.conn.close()

Path("pico_memory.db").unlink(missing_ok=True)
memory = MemoryDB()
memory.remember("ana", "likes extra olives")
memory.close()
del memory                                     # a 'restart': the old object is gone

memory = MemoryDB()                            # a brand-new object, same file
print("after the restart:", memory.recall("ana"))
memory.forget("ana")
print("after forgetting :", memory.recall("ana"))


# ====================================================================
# Part 5 · Real databases and connection strings
# ====================================================================

from urllib.parse import urlsplit

url = "postgresql://pico:s3cret@db.example.com:5432/pizza?sslmode=require"
parts = urlsplit(url)
print("scheme   :", parts.scheme, "   (which kind of database)")
print("user     :", parts.username)
print("password :", parts.password, "   <- a SECRET inside the string!")
print("host     :", parts.hostname)
print("port     :", parts.port)
print("database :", parts.path.lstrip("/"))
print("options  :", parts.query, "   (here: use an encrypted connection)")


# ====================================================================
# Part 6 · Enterprise integration
# ====================================================================

GROUP_TO_ROLE = {"pizza-managers": "manager", "pizza-staff": "agent"}
ROLE_CAN = {"manager": {"ask", "refund", "view_logs"}, "agent": {"ask"}}

def roles_from_token(token):
    return {GROUP_TO_ROLE[g] for g in token.get("groups", []) if g in GROUP_TO_ROLE}

def may(token, action):
    return any(action in ROLE_CAN[role] for role in roles_from_token(token))

people = {
    "Maria (manager)": {"user": "maria", "groups": ["pizza-managers"]},
    "Sam (staff)":     {"user": "sam",   "groups": ["pizza-staff"]},
    "Visitor":         {"user": "guest", "groups": ["random-group"]},
}
for who, token in people.items():
    print(f"{who:<18} ask: {may(token, 'ask')!s:<6} refund: {may(token, 'refund')!s:<6} view_logs: {may(token, 'view_logs')}")

def purge_older_than(conn, cutoff):
    # Data rule: do not keep customer data forever.
    cursor = conn.execute("DELETE FROM orders WHERE created < ?", (cutoff,))
    conn.commit()
    return cursor.rowcount

print("orders before:", conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
print("deleted      :", purge_older_than(conn, "2026-11-01"), "order(s) older than 1 November")
print("orders after :", conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])

import hmac, hashlib

SECRET = b"demo-secret-not-real"                 # in real life: from the environment

def sign(body: bytes):
    return hmac.new(SECRET, body, hashlib.sha256).hexdigest()

def accept(body: bytes, signature: str):
    return hmac.compare_digest(sign(body), signature)

body = b'{"event": "order_paid", "id": 4821}'
good_signature = sign(body)
print("real message accepted  :", accept(body, good_signature))
print("tampered body accepted :", accept(b'{"event": "order_paid", "id": 9999}', good_signature))
print("forged signature       :", accept(body, "0" * 64))


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: idempotent handling + a dead-letter list (runs offline)
refunds = []                      # the real-world effect we must not repeat

def do_refund(msg):
    if msg["amount"] < 0:
        raise ValueError("negative amount")
    refunds.append(msg["id"])

def process(msg, seen, dead_letters, tries=3):
    if msg["id"] in seen:                       # idempotent: we already did this one
        return "duplicate, skipped"
    for _ in range(tries):                      # a limit, as always
        try:
            do_refund(msg)
            seen.add(msg["id"])
            return "done"
        except ValueError:
            pass
    dead_letters.append(msg)                    # give up politely, keep it for a human
    return "moved to dead letters"

seen, dead_letters = set(), []
inbox = [{"id": "m1", "amount": 20}, {"id": "m1", "amount": 20}, {"id": "m2", "amount": -5}]
for msg in inbox:
    print(msg["id"], "->", process(msg, seen, dead_letters))
print("refunds made:", refunds, "(m1 only once)")
print("dead letters:", dead_letters)
