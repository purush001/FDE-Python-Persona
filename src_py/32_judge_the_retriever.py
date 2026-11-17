"""Class 32 · Judge the Retriever   (World 7 · RAG Pro 📖 (advanced))

Opening mystery: The feeling
Python in this lab:  zip, enumerate(items, 1), dict comprehensions, round(), a class that wraps a pipeline
FDE ideas in this lab: RAG evaluation, golden questions and trap questions, hit@k and MRR, grounding checks, release gates for retrieval

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (32_Judge_the_Retriever.ipynb) and the slides (32_Judge_the_Retriever.html).
Run it:   python 32_judge_the_retriever.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 32_judge_the_retriever.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The pieces
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
    return word[:5]                  # a crude "stem": fridays -> frida, delivery -> deliv

def tokens(text):
    return [stem(w) for w in re.findall(r"[a-z0-9$]+", text.lower()) if w not in STOP and len(w) > 1]

def chunk_sentences(text, per=2):
    # cut each section into groups of `per` sentences; every chunk remembers its section (metadata)
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

class BM25:
    # keyword scoring: rare words count more (idf), and long chunks do not win just for being long
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [tokens(t) for t in texts]
        self.k1, self.b = k1, b
        self.avg = sum(len(d) for d in self.docs) / len(self.docs)
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in set(d))
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def score(self, question, i):
        doc, tf, total = self.docs[i], Counter(self.docs[i]), 0.0
        for w in tokens(question):
            if w in tf:
                total += self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(doc) / self.avg))
        return total

# A hand-made "meaning map": words that mean the same kind of thing share a concept.
# Real embeddings learn this from billions of sentences. Ours is tiny, so you can read it.
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

def rrf(rankings, k=60):
    # Reciprocal Rank Fusion: every list gives 1/(k+rank) points to each item; sum the points
    scores = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + position)
    return sorted(scores, key=lambda item: (-scores[item], item))

class Searcher:
    def __init__(self, chunks):
        self.chunks = chunks
        self.bm25 = BM25([c["full"] for c in chunks])
        self.vectors = [meaning_vector(c["full"]) for c in chunks]

    def keyword(self, question):
        scored = [(self.bm25.score(question, i), i) for i in range(len(self.chunks))]
        return [i for s, i in sorted(scored, key=lambda p: -p[0]) if s > 0]

    def meaning(self, question):
        q = meaning_vector(question)
        scored = [(cosine(q, v), i) for i, v in enumerate(self.vectors)]
        return [i for s, i in sorted(scored, key=lambda p: -p[0]) if s > 0]

    def hybrid(self, question):
        return rrf([self.keyword(question), self.meaning(question)])

chunks = chunk_sentences(HANDBOOK, 2)
search = Searcher(chunks)

def rerank_score(question, chunk):
    # A careful scorer. For each question word: full credit if the chunk has the word itself,
    # partial credit if it only has a word with the same MEANING. Plus a bit for words sitting close together
    # and for a matching section title. (A real reranker is a small model that reads question + chunk together.)
    q = list(dict.fromkeys(tokens(question)))
    if not q:
        return 0.0
    body = tokens(chunk["full"])
    exact = [w for w in q if w in body]
    concept_hits = Counter(CONCEPT_OF[w] for w in body if w in CONCEPT_OF)
    soft = [w for w in q if w not in exact and w in CONCEPT_OF and CONCEPT_OF[w] in concept_hits]
    soft_credit = sum(0.6 + 0.1 * min(concept_hits[CONCEPT_OF[w]], 3) for w in soft)
    positions = [i for i, w in enumerate(body) if w in exact]
    closeness = 1 / (1 + (max(positions) - min(positions))) if positions else 0
    section_bonus = 0.1 if any(w in tokens(chunk["section"]) for w in q) else 0
    return round((len(exact) + soft_credit) / len(q) + 0.2 * closeness + section_bonus, 3)

def rerank(question, ids, keep=3):
    return sorted(ids, key=lambda i: -rerank_score(question, chunks[i]))[:keep]
print(len(chunks), "chunks ready")


# ====================================================================
# Part 3 · The golden questions
# ====================================================================

# (question, phrase the right chunk must contain).  None = the handbook has NO answer: the right move is to abstain.
GOLDEN = [
    ("celiac", "celiac disease"),
    ("What is the $25 rule?", "over $25"),
    ("Garden Special", "vegetarian"),
    ("I do not eat meat or dairy", "Plant Power"),
    ("deposit for a party", "$20 deposit"),
    ("can I get my money back for a cold pizza", "refund it in full"),
    ("when do you shut on Friday", "until 23:00"),
    ("cheapest way to feed a crowd", "Party Pack"),
    ("How much does a gift card cost?", None),
    ("What time do you open on Christmas?", None),
]
print(len(GOLDEN), "golden questions,", sum(1 for _, m in GOLDEN if m is None), "of them traps")


# ====================================================================
# Part 4 · The numbers
# ====================================================================

def first_good_rank(ranked_ids, must):
    # position (1 = best) of the first chunk that holds the phrase; None if it never shows up
    for position, i in enumerate(ranked_ids, 1):
        if must in chunks[i]["text"]:
            return position
    return None

def evaluate(engine, k=3, abstain_below=0.0):
    hits, reciprocal, traps_ok, traps = 0, 0.0, 0, 0
    for question, must in GOLDEN:
        ranked = engine(question)[:k]
        if abstain_below and (not ranked or rerank_score(question, chunks[ranked[0]]) < abstain_below):
            ranked = []                                   # the system says "I don't know"
        if must is None:
            traps += 1
            traps_ok += (not ranked)                      # a trap is passed only by abstaining
            continue
        rank = first_good_rank(ranked, must)
        hits += rank is not None
        reciprocal += 1 / rank if rank else 0
    n = len(GOLDEN) - traps
    return {"hit@k": round(hits / n, 2), "MRR": round(reciprocal / n, 2), "traps passed": f"{traps_ok}/{traps}"}

print(evaluate(search.keyword))


# ====================================================================
# Part 5 · One change at a time
# ====================================================================

def hybrid_rerank(question):
    return rerank(question, search.hybrid(question)[:6], keep=6)

configs = {
    "keyword only":            (search.keyword, 0.0),
    "meaning only":            (search.meaning, 0.0),
    "hybrid":                  (search.hybrid, 0.0),
    "hybrid + rerank":         (hybrid_rerank, 0.0),
    "hybrid + rerank + abstain": (hybrid_rerank, 0.4),
}
table = {}
print(f"{'configuration':<28}{'hit@3':>7}{'MRR':>7}{'  traps passed':>16}")
for name, (engine, abstain) in configs.items():
    r = evaluate(engine, 3, abstain)
    table[name] = r["hit@k"] * 100
    print(f"{name:<28}{r['hit@k']:>7}{r['MRR']:>7}{r['traps passed']:>16}")


# ====================================================================
# Part 6 · Is the answer grounded?
# ====================================================================

def grounded(answer, context_chunks):
    # every number and every longer word in the answer must appear in the context it was given
    context = " ".join(c["text"] for c in context_chunks).lower()
    claims = re.findall(r"\$?\d[\d:.,]*|[a-z]{6,}", answer.lower())
    unsupported = [c for c in claims if c not in context]
    return len(unsupported) == 0, unsupported

good = "Refunds over $50 need manager approval."
bad = "Refunds over $500 need director approval."
ctx = [chunks[i] for i in search.keyword("refunds approval")[:1]]
print("good answer:", grounded(good, ctx))
print("bad answer :", grounded(bad, ctx))


# ====================================================================
# Part 7 · The whole pipeline in one class
# ====================================================================

class PicoRAG:
    # chunk -> hybrid search -> rerank -> abstain -> answer with sources
    def __init__(self, text, abstain_below=0.4):
        self.chunks = chunk_sentences(text, 2)
        self.search = Searcher(self.chunks)
        self.abstain_below = abstain_below

    def ask(self, question):
        ids = rerank(question, self.search.hybrid(question)[:6], keep=2)
        if not ids or rerank_score(question, self.chunks[ids[0]]) < self.abstain_below:
            return {"answer": "I don't know. That is not in my notes.", "sources": []}
        facts = "\n".join(f"- {self.chunks[i]['text']}" for i in ids)
        system = "You are Pico. Answer ONLY from FACTS, briefly. If it is not in FACTS, say: I don't know.\nFACTS:\n" + facts
        return {"answer": fde_llm.ask(question, system=system), "sources": [self.chunks[i]["section"].title() for i in ids]}

pico_rag = PicoRAG(HANDBOOK)
for q in ("What time are you open on Fridays?", "How much does a gift card cost?"):
    print(q, "->", pico_rag.ask(q))

# A release gate for retrieval (Class 24): ship only if the new version is not worse and the traps pass.
baseline = evaluate(search.keyword, 3)
candidate = evaluate(hybrid_rerank, 3, 0.4)
gate = candidate["hit@k"] >= baseline["hit@k"] and candidate["traps passed"].split("/")[0] == candidate["traps passed"].split("/")[1]
print("baseline :", baseline)
print("candidate:", candidate)
print("SHIP IT 🚀" if gate else "HOLD ON ✋: fix it first")
