#!/usr/bin/env python3

from pathlib import Path
import argparse
import json

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder


HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "manifest.json"

RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    # ---------------------------------------------------------
    # 1. Load index configuration
    # ---------------------------------------------------------

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    config = manifest["index"]

    embedding_model_name = config["embedding_model"]
    faiss_path = HERE / config["files"]["faiss"]
    chunks_path = HERE / config["files"]["chunks"]

    chunks = load_jsonl(chunks_path)
    index = faiss.read_index(str(faiss_path))

    # ---------------------------------------------------------
    # 2. First stage: dense retrieval with FAISS
    # ---------------------------------------------------------

    print(f"Embedding model : {embedding_model_name}")
    print(f"Reranker model  : {RERANKER_MODEL}")
    print(f"Query           : {args.query}")
    print()

    embedding_model = SentenceTransformer(embedding_model_name)

    query_vector = embedding_model.encode(
        [args.query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    candidate_count = min(args.candidates, index.ntotal)

    dense_scores, dense_indices = index.search(
        query_vector,
        candidate_count
    )

    candidates = []

    for dense_rank, (score, idx) in enumerate(
        zip(dense_scores[0], dense_indices[0]),
        start=1
    ):
        if idx < 0:
            continue

        chunk = chunks[int(idx)]

        candidates.append({
            "index": int(idx),
            "dense_rank": dense_rank,
            "dense_score": float(score),
            "chunk": chunk,
        })

    # ---------------------------------------------------------
    # 3. Second stage: CrossEncoder reranking
    #
    # IMPORTANT:
    # The CrossEncoder receives query AND document together.
    # ---------------------------------------------------------

    print(f"Loading reranker...")
    reranker = CrossEncoder(RERANKER_MODEL)

    pairs = [
        (
            args.query,
            candidate["chunk"]["embedding_text"]
        )
        for candidate in candidates
    ]

    rerank_scores = reranker.predict(pairs)

    for candidate, score in zip(candidates, rerank_scores):
        candidate["rerank_score"] = float(score)

    # ---------------------------------------------------------
    # 4. Sort by CrossEncoder score
    # ---------------------------------------------------------

    candidates.sort(
        key=lambda x: x["rerank_score"],
        reverse=True
    )

    # ---------------------------------------------------------
    # 5. Display comparison
    # ---------------------------------------------------------

    top_k = min(args.top_k, len(candidates))

    print()
    print(f"Top {top_k} after reranking")
    print("=" * 90)

    for rerank_rank, candidate in enumerate(
        candidates[:top_k],
        start=1
    ):
        chunk = candidate["chunk"]

        print()
        print(
            f"#{rerank_rank} "
            f"rerank={candidate['rerank_score']:.4f} "
            f"| FAISS rank={candidate['dense_rank']} "
            f"| cosine={candidate['dense_score']:.4f}"
        )

        print(f"source     : {chunk.get('source')}")
        print(f"element    : {chunk.get('element')}")
        print(f"section    : {chunk.get('section')}")
        print(f"unit_type  : {chunk.get('unit_type')}")
        print(f"unit_id    : {chunk.get('unit_id')}")
        print(f"provenance : {chunk.get('provenance')}")
        print("-" * 90)

        print(chunk["text"])
        print()


if __name__ == "__main__":
    main()