#!/usr/bin/env python3
"""
BM25 v2 baseline for the structural OntoUML corpus.

Improvements over v1:
- English stopword removal
- Porter stemming for ordinary English words
- preserves OntoUML technical terms instead of stemming them
- field-aware repetition/boosting for element, unit_id and section
- keeps retrieval purely lexical: no embeddings, translation, LLM or reranker

Requires:
    pip install rank-bm25 nltk
"""

from pathlib import Path
import argparse
import json
import re
import unicodedata

from rank_bm25 import BM25Okapi
from nltk.stem import PorterStemmer


HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "manifest.json"

STEMMER = PorterStemmer()

# Small local stopword list: deterministic, no nltk.download() required.
ENGLISH_STOPWORDS = {
    "a","an","and","are","as","at","be","been","being","but","by","can","could",
    "did","do","does","doing","for","from","had","has","have","having","he","her",
    "here","hers","him","his","how","i","if","in","into","is","it","its","may",
    "might","must","no","not","of","on","or","our","ours","she","should","so",
    "some","such","than","that","the","their","theirs","them","then","there",
    "these","they","this","those","to","too","under","up","us","was","we","were",
    "what","when","where","which","while","who","why","will","with","would","you",
    "your","yours"
}

# OntoUML terms should remain recognizable and exact.
ONTOUML_TERMS = {
    "kind","subkind","collective","quantity","relator","mode","category",
    "mixin","rolemixin","role","phase","phasemixin","historicalrole",
    "historicalrolemixin","event","situation","type","datatype",
    "mediation","material","derivation","characterization",
    "componentof","memberof","subcollectionof","subquantityof",
    "instantiation","generalization","generalizationset",
    "identity","rigidity","antirigid","semirigid",
    "dependency","dependent","dependence","relational",
    "sortal","nonsortal","abstract","disjoint","complete",
    "stereotype","stereotyped"
}


def raw_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("_", " ")
    # Keep technical compounds such as roleMixin after lowercase -> rolemixin.
    return re.findall(r"\b[^\W_]+\b", text, flags=re.UNICODE)


def normalize_token(token: str) -> str | None:
    if token in ENGLISH_STOPWORDS:
        return None

    if token in ONTOUML_TERMS:
        return token

    # Do not stem identifiers/numbers such as C2.
    if any(ch.isdigit() for ch in token):
        return token

    # Porter stemming is intentionally applied only to ordinary ASCII English.
    if token.isascii() and token.isalpha() and len(token) > 2:
        return STEMMER.stem(token)

    # Non-English tokens are preserved; v2 does NOT pretend to translate them.
    return token


def tokenize(text: str) -> list[str]:
    out = []
    for tok in raw_tokens(text):
        normalized = normalize_token(tok)
        if normalized:
            out.append(normalized)
    return out


def document_tokens(chunk: dict) -> list[str]:
    """
    Field-aware lexical representation.

    Text remains the main signal. Metadata is repeated to give exact structural
    matches more influence without changing the source document itself.
    """
    tokens = tokenize(chunk.get("text", ""))

    element = tokenize(str(chunk.get("element") or ""))
    section = tokenize(str(chunk.get("section") or ""))
    unit_id = tokenize(str(chunk.get("unit_id") or ""))

    # Simple, transparent field boosts:
    # element x3, unit_id x3, section x2.
    tokens.extend(element * 3)
    tokens.extend(unit_id * 3)
    tokens.extend(section * 2)

    return tokens


def main():
    ap = argparse.ArgumentParser(description="BM25 v2 lexical OntoUML search")
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    chunks_path = HERE / manifest["index"]["files"]["chunks"]

    with chunks_path.open("r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]

    corpus_tokens = [document_tokens(c) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)

    q_tokens = tokenize(args.query)
    scores = bm25.get_scores(q_tokens)

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    top_k = min(args.top_k, len(ranked))

    print("Engine       : BM25Okapi v2")
    print("Mode         : lexical + stopwords + stemming + OntoUML preservation + metadata boosts")
    print(f"Query        : {args.query}")
    print(f"Query tokens : {q_tokens}")
    print(f"Documents    : {len(chunks)}")

    if args.debug:
        print("\nTechnical terms preserved:")
        print(sorted(set(q_tokens) & ONTOUML_TERMS))

    print()
    print(f"Top {top_k} results")
    print("=" * 90)

    for rank, idx in enumerate(ranked[:top_k], start=1):
        c = chunks[idx]
        print()
        print(f"#{rank}  BM25={float(scores[idx]):.4f}")
        print(f"source     : {c.get('source')}")
        print(f"domain     : {c.get('domain')}")
        print(f"element    : {c.get('element')}")
        print(f"section    : {c.get('section')}")
        print(f"unit_type  : {c.get('unit_type')}")
        print(f"unit_id    : {c.get('unit_id')}")
        print(f"provenance : {c.get('provenance')}")
        print("-" * 90)
        print(c["text"])
        print()


if __name__ == "__main__":
    main()
