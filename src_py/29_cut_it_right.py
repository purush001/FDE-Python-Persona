"""Class 29 · Cut It Right   (World 7 · RAG Pro 📖 (advanced))

Opening mystery: The sentence cut in half
Python in this lab:  string slicing, range(start, stop, step), re.split, list comprehensions, dicts as chunk records
FDE ideas in this lab: RAG pipeline, chunking: fixed, sentence, section, overlap, metadata and citations, chunk size trade-off (quality vs cost)

This file is the lab's lesson code as one runnable script, in the same order as the
notebook (29_Cut_It_Right.ipynb) and the slides (29_Cut_It_Right.html).
Run it:   python 29_cut_it_right.py
It runs offline with the built-in pretend AI (mock). To use a real model:
    PICO_PROVIDER=gemini GEMINI_API_KEY=...  python 29_cut_it_right.py
"""
import os
import fde_llm

fde_llm.use(os.environ.get("PICO_PROVIDER", "mock"), quiet=True)


# ====================================================================
# Part 2 · The handbook
# ====================================================================

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
print(len(HANDBOOK), "characters,", HANDBOOK.count("# "), "sections")
print(HANDBOOK[:150], "...")


# ====================================================================
# Part 3 · Three ways to cut
# ====================================================================

import re

def chunk_fixed(text, size=60, overlap=0):
    # cut every `size` letters; move forward by (size - overlap) so neighbours share some text
    step = size - overlap
    return [{"id": f"f{i}", "section": "", "text": text[s:s + size]}
            for i, s in enumerate(range(0, len(text), step)) if text[s:s + size].strip()]

def chunk_sentences(text, per=2):
    # a few sentences per chunk; every chunk remembers which section it came from (metadata)
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
            chunks.append({"id": f"s{len(chunks)}", "section": section, "text": " ".join(sentences[i:i + per])})
    return chunks

def chunk_sections(text):
    # one chunk per "# HEADING" section
    chunks = []
    for part in re.split(r"(?m)^# ", text.strip()):
        if part.strip():
            head, _, body = part.partition("\n")
            chunks.append({"id": f"h{len(chunks)}", "section": head.strip(), "text": body.strip()})
    return chunks

for name, made in (("fixed 60", chunk_fixed(HANDBOOK, 60)), ("sentences", chunk_sentences(HANDBOOK)), ("sections", chunk_sections(HANDBOOK))):
    print(f"{name:<10} -> {len(made):>2} chunks, e.g. {made[3]['text'][:60]!r}")

# Where did the fixed cut land? Find the chunk that holds the delivery fee.
fixed = chunk_fixed(HANDBOOK, 60)
for c in fixed:
    if "fee" in c["text"] or "$3" in c["text"] or "delivery" in c["text"].lower():
        print(c["id"], "|", repr(c["text"]))


# ====================================================================
# Part 4 · Which cut finds the answers?
# ====================================================================

STOP = {"the", "and", "for", "are", "you", "how", "does", "what", "much", "can", "have", "with", "from", "that", "this", "your", "who", "which", "when", "many", "there", "pizza", "pizzas"}

def words(text):
    return {w[:5] for w in re.findall(r"[a-z0-9$]+", text.lower()) if len(w) >= 3 and w not in STOP}

def retrieve(question, chunks, k=1):
    # the k chunks that share the most words with the question (chunks with no shared word are dropped)
    q = words(question)
    scored = sorted(((len(q & words(c["text"] + " " + c["section"])), c) for c in chunks), key=lambda pair: -pair[0])
    return [c for score, c in scored[:k] if score > 0]

# question -> the exact phrase the right chunk MUST contain
QA = [
    ("How much is delivery for a small order?", "$3 delivery fee"),
    ("Is the gluten free crust baked in a separate oven?", "separate oven"),
    ("Which pizza is fully vegan?", "Plant Power"),
    ("When do refunds need manager approval?", "over $50"),
    ("What time do you close on Friday?", "until 23:00"),
    ("How many people does the Party Pack serve?", "serves 10 people"),
]

def report(chunks):
    hits, chars = 0, 0
    for question, must in QA:
        top = retrieve(question, chunks, 1)
        if top and must in top[0]["text"]:
            hits += 1
        chars += len(top[0]["text"]) if top else 0
    return hits, round(chars / len(QA))

candidates = {
    "fixed 60": chunk_fixed(HANDBOOK, 60),
    "fixed 120": chunk_fixed(HANDBOOK, 120),
    "fixed 120 + overlap 40": chunk_fixed(HANDBOOK, 120, 40),
    "2 sentences": chunk_sentences(HANDBOOK, 2),
    "whole sections": chunk_sections(HANDBOOK),
}
results = {}
print(f"{'way to cut':<24}{'chunks':>7}{'answers found':>15}{'avg letters sent':>18}")
for name, made in candidates.items():
    hits, avg = report(made)
    results[name] = hits
    print(f"{name:<24}{len(made):>7}{str(hits) + ' / 6':>15}{avg:>18}")


# ====================================================================
# Part 5 · Overlap and labels
# ====================================================================

text = "Refunds over $50 need manager approval."
no_overlap = chunk_fixed(text, 20, 0)
with_overlap = chunk_fixed(text, 20, 8)
print("no overlap  :", [c["text"] for c in no_overlap])
print("with overlap:", [c["text"] for c in with_overlap])
rule = "$50 need manager"                                     # the facts that belong together
print(f"Does any chunk keep '{rule}' whole?  no overlap:", any(rule in c["text"] for c in no_overlap), "| overlap:", any(rule in c["text"] for c in with_overlap))

# Metadata = labels that travel with every chunk: which section, which document, which page.
for c in chunk_sentences(HANDBOOK, 2)[:3]:
    print(c["id"], "|", c["section"], "|", c["text"][:50] + "...")

# A labelled chunk can be CITED later: "(source: REFUNDS)". Unlabelled chunks cannot.
best = retrieve("Who must approve a big refund?", chunk_sentences(HANDBOOK, 2), 1)[0]
print("\nAnswer comes from:", best["text"], " (source:", best["section"] + ")")


# ====================================================================
# Part 6 · Let the AI answer from the chunk
# ====================================================================

question = "How much is delivery for a small order?"
top = retrieve(question, chunk_sentences(HANDBOOK, 2), 1)
system = ("You are Pico, the pizza shop assistant. Answer ONLY from FACTS. If the answer is not in FACTS, say: I don't know.\n"
          "FACTS:\n" + "\n".join("- " + c["text"] for c in top))
print(fde_llm.ask(question, system=system))
print("(source:", top[0]["section"] + ")")
