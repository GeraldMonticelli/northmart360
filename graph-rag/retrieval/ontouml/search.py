#!/usr/bin/env python3

from pathlib import Path
import argparse
import json

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "manifest.json"


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Semantic search in the local OntoUML documentation."
    )
    parser.add_argument(
        "query",
        help="Natural-language query, in English or French."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return."
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # 1. Read index configuration
    # ---------------------------------------------------------

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    index_config = manifest["index"]

    model_name = index_config["embedding_model"]
    faiss_path = HERE / index_config["files"]["faiss"]
    chunks_path = HERE / index_config["files"]["chunks"]

    print(f"Model : {model_name}")
    print(f"Query : {args.query}")
    print()

    # ---------------------------------------------------------
    # 2. Load the same embedding model used at indexing time
    # ---------------------------------------------------------

    model = SentenceTransformer(model_name)

    # ---------------------------------------------------------
    # 3. Transform the query into a 384-dimensional vector
    # ---------------------------------------------------------

    query_vector = model.encode(
        [args.query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_vector = np.asarray(
        query_vector,
        dtype="float32"
    )

    # ---------------------------------------------------------
    # 4. Load FAISS and our chunk metadata
    # ---------------------------------------------------------

    index = faiss.read_index(str(faiss_path))
    chunks = load_jsonl(chunks_path)

    if index.ntotal != len(chunks):
        raise RuntimeError(
            f"FAISS contains {index.ntotal} vectors "
            f"but chunks.jsonl contains {len(chunks)} chunks."
        )

    # ---------------------------------------------------------
    # 5. Vector similarity search
    #
    # distances[0] = similarity scores
    # indices[0]   = positions in chunks.jsonl
    # ---------------------------------------------------------

    k = min(args.top_k, index.ntotal)

    distances, indices = index.search(
        query_vector,
        k
    )

    # ---------------------------------------------------------
    # 6. Display retrieved documents
    # ---------------------------------------------------------

    print(f"Top {k} results")
    print("=" * 80)

    for rank, (score, idx) in enumerate(
        zip(distances[0], indices[0]),
        start=1
    ):
        if idx < 0:
            continue

        chunk = chunks[int(idx)]

        print()
        print(f"#{rank}  score={float(score):.4f}")
        print(f"source     : {chunk['source']}")
        print(f"domain     : {chunk['domain']}")
        print(f"element    : {chunk['element']}")
        print(f"section    : {chunk['section']}")
        print(f"chunk      : {chunk['chunk']}")
        print(f"provenance : {chunk['provenance']}")
        print("-" * 80)
        print(chunk["text"])
        print()


if __name__ == "__main__":
    main()