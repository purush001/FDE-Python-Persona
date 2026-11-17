"""Class 30 · Two Searches Are Better Than One   (World 7 · RAG Pro 📖 (advanced))

Opening mystery: Two customers, two searches
Python in this lab:  math.log, collections.Counter, sorted(key=lambda ...), enumerate(items, 1), dicts of scores
FDE ideas in this lab: keyword search (BM25), meaning search (embeddings), hybrid search, Reciprocal Rank Fusion, when each search wins and loses

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (30_Two_Searches_Are_Better_Than_One.ipynb) and the slides (30_Two_Searches_Are_Better_Than_One.html).
Run it:   python 30_two_searches_are_better_than_one.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 30_two_searches_are_better_than_one.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The chunks
# ====================================================================

import math, re
from collections import Counter

HANDBOOK = """# DELIVERY
We deliver within 5 km of the shop. Delivery is free for orders over $25. Smaller orders pay a $3 delivery fee. Pizzas usually arrive in 30 minutes. On rainy days allow 45 minutes.

# GLUTEN AND ALLERGIES
Our gluten-free crust is baked in a separate oven and costs $2 extra. We cannot promise zero gluten in the kitchen, so guests with celiac disease should ask the manager. Every pizza can be made without nuts.

# VEGAN AND VEGETARIAN
The Garden Special is vegetarian. The Plant Power pizza is fully vegan and uses cashew cheese. Vegan cheese costs $1.50 extra on any other pizza.

# REFUNDS
If a pizza arrives cold, we refund it in full within 24 hours. Refunds over $50 need manager approval. We never refund pizzas that were eaten and enjoyed.

# OPENING HOURS
We are open every day from 11:00 to 22:00. On Fridays we stay open until 23:00. We are closed on the first Monday of each month for oven cleaning.

# PARTY PACKAGES
The Party Pack serves 10 people and includes 4 large pizzas, 2 salads and 10 drinks for $79. Book at least 2 days ahead. A $20 deposit holds the date."""

STOP = set("the and for are you how does what much can have with from that this your who which when many there pizza pizzas to a an of in on at is it or not do i my me we our us be as by if so up".split())

def stem(word):
    return word[:5]                    # a crude "stem": fridays -> frida, delivery -> deliv

def tokens(text):
    return [stem(w) for w in re.findall(r"[a-z0-9$]+", text.lower()) if w not in STOP and len(w) > 1]

def chunk_sentences(text, per=2):
    chunks, section = [], ""
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            section = line[2:]
            continue
        sentences = re.split(r"(?<=[.!?])\s+", line)
        for i in range(0, len(sentences), per):
            body = " ".join(sentences[i:i + per])
            chunks.append({"id": len(chunks), "section": section, "text": body, "full": section.title() + ": " + body})
    return chunks

chunks = chunk_sentences(HANDBOOK, 2)
print(len(chunks), "chunks. Example:", chunks[3]["full"])


# ====================================================================
# Part 3 · Search 1: keyword (BM25)
# ====================================================================

class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [tokens(t) for t in texts]
        self.k1, self.b = k1, b
        self.avg = sum(len(d) for d in self.docs) / len(self.docs)
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in set(d))                 # in how many chunks does each word appear?
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}   # rare word = big number

    def score(self, question, i):
        doc, tf, total = self.docs[i], Counter(self.docs[i]), 0.0
        for w in tokens(question):
            if w in tf:
                total += self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(doc) / self.avg))
        return total

bm25 = BM25([c["full"] for c in chunks])
for word in ("celiac", "delivery", "open"):
    print(f"idf of {word!r}: {bm25.idf[stem(word)]:.2f}   (bigger = rarer = more useful)")

def keyword_search(question):
    scored = [(bm25.score(question, i), i) for i in range(len(chunks))]
    return [i for s, i in sorted(scored, key=lambda p: -p[0]) if s > 0]       # only chunks that share a word

for q in ("celiac", "I do not eat meat or dairy"):
    found = keyword_search(q)
    print(f"\n{q!r} ->", chunks[found[0]]["full"][:70] if found else "NOTHING (no shared words)")


# ====================================================================
# Part 4 · Search 2: meaning
# ====================================================================

# A hand-made meaning map. Real embeddings (Class 11) learn this from billions of sentences.
MEANING = {
    "no-animal":  "vegan vegetarian plant cashew meat dairy cheese animal veggie",
    "money-back": "refund refunded money back return reimburse cold",
    "closing":    "close closed shut open hours late stay",
    "arrival":    "arrive arrival deliver delivery shows wait long minutes fast soon",
    "group":      "party crowd group people feed pack serves book deposit",
    "allergy":    "gluten celiac allergy allergies nuts peanut",
    "price":      "cost costs price cheap cheapest free fee extra pay",
}
CONCEPT_OF = {stem(w): i for i, words in enumerate(MEANING.values()) for w in words.split()}

def meaning_vector(text):
    vec = [0.0] * len(MEANING)
    for w in tokens(text):
        if w in CONCEPT_OF:
            vec[CONCEPT_OF[w]] += 1
    return vec

def cosine(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0

vectors = [meaning_vector(c["full"]) for c in chunks]

def meaning_search(question):
    q = meaning_vector(question)
    scored = [(cosine(q, v), i) for i, v in enumerate(vectors)]
    return [i for s, i in sorted(scored, key=lambda p: -p[0]) if s > 0]

for q in ("I do not eat meat or dairy", "celiac"):
    found = meaning_search(q)
    print(f"{q!r} ->", chunks[found[0]]["full"][:70] if found else "NOTHING")


# ====================================================================
# Part 5 · Fuse the two lists
# ====================================================================

def rrf(rankings, k=60):
    # Every list gives each item 1/(k + rank) points. Add the points up. High in BOTH lists wins.
    scores = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + position)
    return sorted(scores, key=lambda item: (-scores[item], item))

def hybrid_search(question):
    return rrf([keyword_search(question), meaning_search(question)])

print(rrf([["a", "b", "c"], ["b", "c", "a"]]), " <- b is high in both lists")


# ====================================================================
# Part 6 · The face-off
# ====================================================================

TESTS = [
    ("celiac", "celiac disease"),
    ("What is the $25 rule?", "over $25"),
    ("Garden Special", "vegetarian"),
    ("I do not eat meat or dairy", "Plant Power"),
    ("deposit for a party", "$20 deposit"),
    ("can I get my money back for a cold pizza", "refund it in full"),
    ("when do you shut on Friday", "until 23:00"),
    ("cheapest way to feed a crowd", "Party Pack"),
]
engines = {"keyword": keyword_search, "meaning": meaning_search, "hybrid": hybrid_search}
wins = {name: 0 for name in engines}
print(f"{'question':<42}" + "".join(f"{name:>10}" for name in engines))
for question, must in TESTS:
    row = ""
    for name, engine in engines.items():
        ranked = engine(question)
        ok = bool(ranked) and must in chunks[ranked[0]]["text"]
        wins[name] += ok
        row += f"{'✅' if ok else '❌':>10}"
    print(f"{question[:40]:<42}" + row)

# 🌶️ Optional: swap in the real embedding function of your chosen AI (practice mode gives a tiny pretend one).
vecs = fde_llm.embed([c["full"] for c in chunks])
q = fde_llm.embed("I do not eat meat or dairy")
best = max(range(len(chunks)), key=lambda i: cosine(q, vecs[i]))
print("Embedding search picks:", chunks[best]["full"][:70])


# ====================================================================
# 🧭 Going further (optional): the real-world tool behind this toy
# ====================================================================

# 🧭 Going further: what you built vs the real tools (this only prints, nothing is installed)
rows = [
    ("step",            "what you built",            "what real systems use"),
    ("keyword search",  "BM25 class",                "BM25 in a search engine"),
    ("meaning search",  "hand-made meaning map",     "learned embeddings + vector database"),
    ("fuse the lists",  "rrf() function",            "RRF built into some search tools"),
    ("rerank",          "rerank_score() rules",      "a cross-encoder reranker model"),
    ("test it",         "10 golden questions",       "hundreds, kept out of the tuning loop"),
]
widths = [max(len(row[i]) for row in rows) for i in range(3)]
for row in rows:
    print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
print()
print("Same pipeline, bigger parts. That is why the small version teaches the real thing.")
