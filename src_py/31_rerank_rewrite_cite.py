"""Class 31 · Rerank, Rewrite, Cite   (World 7 · RAG Pro 📖 (advanced))

Opening mystery: The page at number four
Python in this lab:  sorted(key=lambda ...), set operations (intersection and union), max(..., default=...), list(dict.fromkeys(...)), f-strings for citations
FDE ideas in this lab: query rewriting and multi-query, two-stage retrieval: search then rerank, MMR (diversity), grounded answers with citations, an "I don't know" threshold

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (31_Rerank_Rewrite_Cite.ipynb) and the slides (31_Rerank_Rewrite_Cite.html).
Run it:   python 31_rerank_rewrite_cite.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 31_rerank_rewrite_cite.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The search from Class 30
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
print(len(chunks), "chunks ready. Try: search.hybrid('when do you shut on Friday') ->", search.hybrid("when do you shut on Friday")[:3])


# ====================================================================
# Part 3 · Rewrite the question
# ====================================================================

SAYS_THE_SAME = {"shut": "close", "meatless": "vegetarian", "stuff": "pizza", "food": "pizza", "shows": "arrives", "up": "", "crowd": "party", "nosh": "pizza"}

def rewrite(question):
    # tiny rule-based rewriter: lower-case, swap casual words for handbook words, drop filler
    words = re.findall(r"[a-z0-9$']+", question.lower())
    return " ".join(w for w in (SAYS_THE_SAME.get(w, w) for w in words) if w)

def multi_query(question):
    # ask the same thing in 2 ways, search each way, fuse the lists
    return list(dict.fromkeys([question, rewrite(question)]))                 # same order, no repeats

def found_in_top3(ids, must):
    return any(must in chunks[i]["text"] for i in ids[:3])

q, must = "do you do meatless stuff", "vegetarian"
print("versions:", multi_query(q))
print("single question finds it in the top 3?  ", found_in_top3(search.hybrid(q), must))
print("multi-query (fused) finds it in the top 3?", found_in_top3(rrf([search.hybrid(v) for v in multi_query(q)]), must))

reply = fde_llm.ask("Rewrite this customer message as ONE short search query for a pizza shop handbook. Message: how long until my food shows up?")
print(reply)


# ====================================================================
# Part 4 · Rerank the top few
# ====================================================================

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

question = "deposit for a party"
stage1 = search.hybrid(question)[:5]
stage2 = rerank(question, stage1)
print("stage 1 (fast, rough):  ", stage1, "->", chunks[stage1[0]]["text"][:45])
print("stage 2 (slow, careful):", stage2, "->", chunks[stage2[0]]["text"][:45])


# ====================================================================
# Part 5 · No copies please
# ====================================================================

def overlap(a, b):
    x, y = set(tokens(a)), set(tokens(b))
    return len(x & y) / len(x | y) if x | y else 0.0                # Jaccard: 1.0 = same words

def pick_diverse(question, candidate_ids, keep=3, lam=0.7):
    # MMR: pick the most relevant, then prefer chunks that are relevant AND different from the ones already picked
    chosen, pool = [], list(candidate_ids)
    while pool and len(chosen) < keep:
        def value(i):
            relevance = rerank_score(question, chunks[i])
            copy_penalty = max((overlap(chunks[i]["full"], chunks[j]["full"]) for j in chosen), default=0)
            return lam * relevance - (1 - lam) * copy_penalty
        best = max(pool, key=value)
        chosen.append(best)
        pool.remove(best)
    return chosen

print(pick_diverse("what does a vegan pizza cost", search.hybrid("what does a vegan pizza cost")[:5]))


# ====================================================================
# Part 6 · Answer with sources, or say I don't know
# ====================================================================

MIN_SCORE = 0.4          # below this, the best chunk is not good enough to answer from

def answer(question, keep=2):
    candidates = search.hybrid(question)[:6]
    best = rerank(question, candidates, keep=6)
    if not best or rerank_score(question, chunks[best[0]]) < MIN_SCORE:
        return "I don't know. That is not in my notes.", []
    picked = pick_diverse(question, best, keep=keep)
    facts = "\n".join(f"- [{n}] {chunks[i]['text']}" for n, i in enumerate(picked, 1))
    system = ("You are Pico. Answer ONLY from FACTS and keep it short. If the answer is not in FACTS, say: I don't know.\n"
              "FACTS:\n" + facts)
    reply = fde_llm.ask(question, system=system)
    sources = [f"[{n}] {chunks[i]['section'].title()}" for n, i in enumerate(picked, 1)]
    return reply, sources

for q in ("Who must approve a big refund?", "How much does a gift card cost?", "What time are you open on Fridays?"):
    reply, sources = answer(q)
    print("Q:", q, "\nA:", reply, "\nSources:", sources or "none (honest!)", "\n")
