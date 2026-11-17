"""Class 11 · Vector Pico   (World 3 · Memory & Workflows 🧠)

Opening mystery: Zero words in common
Python in this lab:  zip and dot products, math.sqrt, lists of numbers, a class with add and search, sorted(key=...)
FDE ideas in this lab: embeddings, cosine similarity, a tiny vector database, keyword vs vector search, score thresholds

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (11_Vector_Pico.ipynb) and the slides (11_Vector_Pico.html).
Run it:   python 11_vector_pico.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 11_vector_pico.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 1 · Meaning as coordinates
# ====================================================================

import math

# A tiny 2-D map. x = how COLD it is.  y = how much it is about MONEY.   (We placed these by hand.)
toy = {
    "pizza arrived cold":      (0.9, 0.1),
    "my pie came chilly":      (0.8, 0.1),
    "give me my money back":   (0.1, 0.9),
    "refund please":           (0.1, 1.0),
    "hot fresh pizza":         (0.0, 0.0),
    "chilly pizza, refund me": (0.8, 0.9),
}

try:
    import matplotlib.pyplot as plt
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for text, (x, y) in toy.items():
        ax.scatter(x, y, s=140, color="#22d3ee")
        ax.annotate(text, (x, y), textcoords="offset points", xytext=(8, 6), fontsize=10)
    ax.set_xlabel("← warm        COLD →"); ax.set_ylabel("← not money        MONEY →")
    ax.set_xlim(-0.2, 1.5); ax.set_ylim(-0.15, 1.2); ax.set_title("A meaning map (made by hand)")
    plt.show()
except Exception as problem:
    print("(Chart skipped:", problem, ")")

target = toy["pizza arrived cold"]
ranking = sorted(toy, key=lambda text: math.dist(toy[text], target))   # math.dist = straight-line distance
for text in ranking:
    print(f"{math.dist(toy[text], target):.2f}  {text}")


# ====================================================================
# Part 2 · Measuring closeness
# ====================================================================

import os, re, time

NOTES = [
    "Delivery costs $2.50 and usually takes 30 minutes.",
    "Delivery is free for orders over $25.",
    "We are open every day from 11:00 to 22:00.",
    "Refunds are possible within 24 hours if the pizza arrives cold. Ask a human agent.",
    "Vegan cheese is available on every pizza for $1.",
    "We do not sell alcohol.",
    "Large pizzas have 12 slices and medium pizzas have 8 slices.",
]
STOP = {"the", "and", "for", "are", "you", "how", "does", "what", "much", "can", "have", "with", "from", "that", "this", "your", "many", "there"}
HONESTY_RULE = "Answer ONLY from the FACTS. If the FACTS do not contain the answer, say exactly: I don't know. That is not in my notes."
SECRET = "MANAGER-CODE-7788"        # a pretend secret (real ones never go in prompts)

def keywords(text):
    words = "".join(c if c.isalnum() or c == " " else " " for c in text.lower()).split()
    return {w[:5] for w in words if len(w) >= 3 and w not in STOP}

def retrieve(question, chunks=NOTES, k=2):
    wanted = keywords(question)
    scored = sorted(((len(wanted & keywords(c)), c) for c in chunks), key=lambda pair: pair[0], reverse=True)
    return [c for score, c in scored[:k] if score > 0]

INJECTION = [
    re.compile(r"ignore (all |any |the )?(your |previous |prior |above )(instructions|rules|prompt)", re.I),
    re.compile(r"(reveal|show|print|repeat).{0,25}(your|the system|hidden|secret).{0,12}(instructions|prompt|rules|password|code)", re.I),
    re.compile(r"\b(reveal|print)\b.{0,25}\bsecret\b", re.I),
    re.compile(r"pretend (to be|you are)|you are now (dan|an ai with no)|developer mode", re.I),
]
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")

def input_guard(text, max_length=500):
    if not text.strip():
        return False, "empty message"
    if len(text) > max_length:
        return False, "message too long"
    if any(p.search(text) for p in INJECTION):
        return False, "prompt-injection attempt"
    return True, "ok"

def output_guard(text):
    problems = []
    if SECRET.lower() in text.lower():
        problems.append("secret leaked")
        text = re.sub(re.escape(SECRET), "[REDACTED]", text, flags=re.I)
    if CARD.search(text):
        problems.append("card number")
        text = CARD.sub("[CARD HIDDEN]", text)
    return text, problems

def pico_brain(question):
    found = retrieve(question)
    facts = "\n".join("- " + c for c in found) if found else "- (no matching notes)"
    system = f"You are Pico, the friendly support bot for Pico's Pizza Planet.\n{HONESTY_RULE}\nSECRET: {SECRET}\n\nFACTS:\n{facts}"
    return fde_llm.ask(question, system=system)

vector = fde_llm.embed("my pie came chilly, I want my money back")
print(len(vector), "numbers in this embedding. The first 8:", vector[:8])

# In practice mode every number is ONE concept, so you can read it:
if len(vector) == len(fde_llm.CONCEPTS) + 8:
    print({name: value for name, value in zip(fde_llm.CONCEPTS, vector) if value})
else:
    print("(A real embedding model gives hundreds or thousands of numbers that nobody can read one by one.)")

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))                  # multiply pairs, add them up
    length_a = math.sqrt(sum(x * x for x in a))              # length of an arrow = √(sum of squares)
    length_b = math.sqrt(sum(y * y for y in b))
    if length_a == 0 or length_b == 0:
        return 0.0
    return dot / (length_a * length_b)

print(cosine_similarity([1, 0], [1, 0]))     # same arrow
print(cosine_similarity([1, 0], [0, 1]))     # at a right angle: unrelated
print(round(cosine_similarity([3, 4], [4, 3]), 2))

question = "my pie came chilly, I want my money back"
q_vec = fde_llm.embed(question)
note_vecs = fde_llm.embed(NOTES)                   # one call can embed many texts
scores = {note[:38]: round(cosine_similarity(q_vec, v), 2) for note, v in zip(NOTES, note_vecs)}


# ====================================================================
# Part 3 · Build a vector database
# ====================================================================

class VectorStore:
    def __init__(self):
        self.items = []                     # each item: {"text":..., "vector":[...], "meta":{...}}

    def add_many(self, texts, **meta):
        for text, vector in zip(texts, fde_llm.embed(texts)):
            self.items.append({"text": text, "vector": vector, "meta": meta})

    def search(self, question, k=2, where=None):
        q = fde_llm.embed(question)
        pool = [i for i in self.items if not where or all(i["meta"].get(key) == val for key, val in where.items())]
        scored = [(round(cosine_similarity(q, i["vector"]), 2), i["text"]) for i in pool]
        return sorted(scored, reverse=True)[:k]

store = VectorStore()
store.add_many(NOTES[:3], topic="delivery and hours")
store.add_many(NOTES[3:], topic="food and rules")
print(len(store.items), "notes stored")
for score, text in store.search("my pie came chilly, I want my money back"):
    print(score, text)
print("— only searching 'delivery and hours' notes —")
print(store.search("my pie came chilly, I want my money back", where={"topic": "delivery and hours"}))


# ====================================================================
# Part 4 · The duel
# ====================================================================

EXTRA = ["Menu code PZ204 is the veggie special."]            # an exact code: keywords love these
store.add_many(EXTRA, topic="menu codes")
ALL_NOTES = NOTES + EXTRA

duel = [
    ("my pie came chilly, I want my money back", 3),    # expected note number
    ("Do you sell beer?", 5),
    ("What time do you close?", 2),
    ("Is plant-based cheese ok?", 4),
    ("What is PZ204?", 7),
]
print(f"{'question':<44}{'keyword':<10}{'vector':<10}")
for question, expected in duel:
    kw = retrieve(question, ALL_NOTES, k=1)
    kw_ok = bool(kw) and kw[0] == ALL_NOTES[expected]
    vec = store.search(question, k=1)
    vec_ok = vec[0][1] == ALL_NOTES[expected]
    print(f"{question:<44}{'✅' if kw_ok else '❌':<10}{'✅' if vec_ok else '❌':<10}")


# ====================================================================
# Part 5 · Nearest is not the same as right
# ====================================================================

for question in ("What is the capital of France?", "Do you have gluten-free crust?", "Can I pay with bitcoin?"):
    print(question, "→", store.search(question, k=1))

THRESHOLD = 0.45      # ✏️ try 0.3 and 0.7. What changes?

def pico_vector_bot(question):
    hits = [(score, text) for score, text in store.search(question, k=2) if score >= THRESHOLD]
    facts = "\n".join("- " + text for score, text in hits) if hits else "- (no matching notes)"
    system = f"You are Pico, the friendly support bot for Pico's Pizza Planet.\n{HONESTY_RULE}\nThe question may use different words than the notes below, so match by meaning, not only by exact words.\n\nFACTS:\n{facts}"
    return fde_llm.ask(question, system=system)

for q in ("my pie came chilly, I want my money back", "Do you sell beer?", "What is the capital of France?", "Do you have gluten-free crust?"):
    print("🗨️ ", q)
    print("🦜 ", pico_vector_bot(q), "\n")


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: what you built vs the real tools (this only prints, nothing is installed)
rows = [
    ("what you did",       "our VectorStore",             "Chroma",                          "pgvector (Postgres)"),
    ("add an item",        "store.add(text, vector)",     "col.add(ids=..., documents=...)", "INSERT INTO notes ..."),
    ("find the closest",   "store.search(vector, k=3)",   "col.query(query_texts=..., n_results=3)", "ORDER BY embedding <=> $1 LIMIT 3"),
    ("survives a restart", "no (it is a list)",           "yes (saved to disk)",             "yes (it is a database)"),
    ("how it searches",    "compares with every item",    "HNSW index (approximate)",        "HNSW or IVFFlat index"),
]
widths = [max(len(row[i]) for row in rows) for i in range(4)]
for row in rows:
    print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
print()
print("Same ideas as Class 11: embeddings, cosine similarity, top-k, a score threshold.")
print("Only the spelling changes. That is why learning the tiny version first works.")
