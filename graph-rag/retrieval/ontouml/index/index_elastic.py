import json
from pathlib import Path

from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ES_URL = "http://localhost:9200"
INDEX_NAME = "ontouml-language-v1"

CHUNKS_FILE = Path(__file__).parent / "chunks.jsonl"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMS = 384


# ---------------------------------------------------------------------------
# Elasticsearch
# ---------------------------------------------------------------------------

es = Elasticsearch(ES_URL)

if not es.ping():
    raise RuntimeError(f"Cannot connect to Elasticsearch at {ES_URL}")

print(f"Connected to Elasticsearch {es.info()['version']['number']}")


# ---------------------------------------------------------------------------
# Create index
# ---------------------------------------------------------------------------

MAPPINGS = {
    "properties": {
        "id": {
            "type": "keyword"
        },
        "source": {
            "type": "keyword"
        },
        "domain": {
            "type": "keyword"
        },
        "element": {
            "type": "keyword"
        },
        "section": {
            "type": "keyword"
        },
        "unit_type": {
            "type": "keyword"
        },
        "unit_id": {
            "type": "keyword"
        },
        "provenance": {
            "type": "keyword"
        },
        "repository": {
            "type": "keyword"
        },
        "document_type": {
            "type": "keyword"
        },
        # Used by BM25
        "text": {
            "type": "text"
        },

        # Text actually sent to the embedding model
        "embedding_text": {
            "type": "text"
        },

        # Used by kNN / semantic retrieval
        "embedding": {
            "type": "dense_vector",
            "dims": EMBEDDING_DIMS,
            "index": True,
            "similarity": "cosine"
        }
    }
}


if not es.indices.exists(index=INDEX_NAME):
    es.indices.create(
        index=INDEX_NAME,
        mappings=MAPPINGS
    )
    print(f"Created index: {INDEX_NAME}")
else:
    print(f"Index already exists: {INDEX_NAME}")


# ---------------------------------------------------------------------------
# Load chunks
# ---------------------------------------------------------------------------

if not CHUNKS_FILE.exists():
    raise FileNotFoundError(f"Cannot find {CHUNKS_FILE}")


chunks = []

with CHUNKS_FILE.open("r", encoding="utf-8") as f:
    for line_number, line in enumerate(f, start=1):
        line = line.strip()

        if not line:
            continue

        try:
            chunk = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid JSON at line {line_number}"
            ) from exc

        chunks.append(chunk)


print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}")


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

print(f"Loading embedding model: {EMBEDDING_MODEL}")

model = SentenceTransformer(EMBEDDING_MODEL)


texts = [
    chunk.get("embedding_text")
    or chunk.get("text")
    or ""
    for chunk in chunks
]


print(f"Generating embeddings for {len(texts)} chunks...")


embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True
)


if embeddings.shape[1] != EMBEDDING_DIMS:
    raise RuntimeError(
        f"Unexpected embedding dimension: "
        f"{embeddings.shape[1]} != {EMBEDDING_DIMS}"
    )


# ---------------------------------------------------------------------------
# Bulk indexing
# ---------------------------------------------------------------------------

def actions():
    for chunk, embedding in zip(chunks, embeddings):

        chunk_id = chunk.get("id")

        if not chunk_id:
            raise RuntimeError(
                "A chunk does not contain id"
            )

        document = dict(chunk)

        document["embedding"] = embedding.tolist()

        yield {
            "_index": INDEX_NAME,
            "_id": chunk_id,
            "_source": document
        }


print("Indexing documents into Elasticsearch...")


success, errors = helpers.bulk(
    es,
    actions(),
    raise_on_error=False,
    refresh=True
)


print()
print("--------------------------------------------------")
print("Indexing completed")
print("--------------------------------------------------")
print(f"Indexed : {success}")
print(f"Errors  : {len(errors)}")
print(f"Index   : {INDEX_NAME}")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

count = es.count(index=INDEX_NAME)["count"]

print(f"Documents currently in Elasticsearch: {count}")

if count != len(chunks):
    print(
        f"WARNING: Elasticsearch contains {count} documents "
        f"but {len(chunks)} chunks were loaded."
    )
else:
    print("OK: all chunks are present in Elasticsearch.")