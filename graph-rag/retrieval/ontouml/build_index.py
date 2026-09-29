#!/usr/bin/env python3
"""
Build a structural OntoUML FAISS index.

Structural units:
- RST headings/subheadings
- **C1:**, **C2:** ... constraints -> one chunk each
- **Q1:** + **A1:** FAQ pairs -> one chunk each
- field-list style anti-pattern sections (Description, Justification, Contraints,
  Examples, Refactoring Plans, References)
- numbered refactoring plans -> one chunk each
- fallback: coherent section, split by paragraphs only if still too large

The original source text is preserved in `text`.
`embedding_text` adds contextual labels used only for retrieval.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus" / "ontouml-language"
INDEX_DIR = HERE / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.jsonl"
FAISS_PATH = INDEX_DIR / "faiss.index"
MANIFEST_PATH = HERE / "manifest.json"

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_MAX_CHARS = 2200
DEFAULT_OVERLAP = 250

HEADING_CHARS = set("=-~^\"`:+*#")
STRUCTURAL_FIELDS = {
    "full name", "type", "feature", "description", "justification",
    "constraints", "contraints", "examples", "refactoring plans",
    "references", "definition"
}


def clean_inline_rst(text: str) -> str:
    text = re.sub(r":[-A-Za-z0-9_]+:`([^`<>]+)\s*<[^`>]+>`", r"\1", text)
    text = re.sub(r":[-A-Za-z0-9_]+:`([^`]+)`", r"\1", text)
    text = re.sub(r"`([^`<>]+)\s*<[^`>]+>`_?", r"\1", text)
    text = text.replace("``", '"')
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text


def remove_rst_noise(text: str) -> str:
    """Remove anchors, images and visual directives, but keep semantic prose."""
    out = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Anchors.
        if re.match(r"^\s*\.\.\s+_[^:]+:\s*$", line):
            i += 1
            continue

        # image substitution definitions.
        if re.match(r"^\s*\.\.\s+\|.*\|\s+image::", line):
            i += 1
            continue

        # Visual directives; skip directive and indented body.
        if re.match(r"^\s*\.\.\s+(container|figure|image)::", line):
            base_indent = len(line) - len(line.lstrip())
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    i += 1
                    continue
                indent = len(nxt) - len(nxt.lstrip())
                if indent > base_indent or re.match(r"^\s*\|[^|]+\|\s*$", nxt):
                    i += 1
                    continue
                break
            continue

        # include directives are navigation, not useful text in the index.
        if re.match(r"^\s*\.\.\s+include::", line):
            i += 1
            continue

        # Standalone image aliases.
        if re.match(r"^\s*\|[^|]+\|\s*$", line):
            i += 1
            continue

        out.append(line)
        i += 1

    text = "\n".join(out)
    text = clean_inline_rst(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_rst_headings(text: str) -> list[tuple[str, str]]:
    """Return (heading, body), using underline-style RST headings."""
    lines = text.splitlines()
    sections = []
    title = "Document"
    buf = []
    i = 0

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((title, body))

    while i < len(lines):
        if (
            i + 1 < len(lines)
            and lines[i].strip()
            and len(lines[i + 1].strip()) >= 3
            and len(set(lines[i + 1].strip())) == 1
            and lines[i + 1].strip()[0] in HEADING_CHARS
        ):
            flush()
            title = clean_inline_rst(lines[i].strip())
            buf = []
            i += 2
        else:
            buf.append(lines[i])
            i += 1

    flush()
    return sections or [("Document", text.strip())]


def split_constraints(body: str):
    """Split **C1:** / C1: blocks."""
    pat = re.compile(r"(?m)^\s*(?:\*\*)?(C\d+)(?:\*\*)?:\s*")
    matches = list(pat.finditer(body))
    if not matches:
        return None

    units = []
    prefix = body[:matches[0].start()].strip()
    if prefix:
        units.append(("context", None, prefix))

    for n, m in enumerate(matches):
        end = matches[n + 1].start() if n + 1 < len(matches) else len(body)
        text = body[m.end():end].strip()
        units.append(("constraint", m.group(1), text))
    return units


def split_faq(body: str):
    """Pair Qn with An, keeping the complete answer with its question."""
    token = re.compile(r"(?m)^\s*(?:\*\*)?([QA])(\d+)(?:\*\*)?:\s*")
    matches = list(token.finditer(body))
    if not matches:
        return None

    pieces = []
    for n, m in enumerate(matches):
        end = matches[n + 1].start() if n + 1 < len(matches) else len(body)
        pieces.append((m.group(1), m.group(2), body[m.end():end].strip()))

    units = []
    i = 0
    while i < len(pieces):
        kind, num, txt = pieces[i]
        if kind == "Q":
            q = txt
            a = None
            if i + 1 < len(pieces) and pieces[i + 1][0] == "A" and pieces[i + 1][1] == num:
                a = pieces[i + 1][2]
                i += 1
            combined = f"Question: {q}"
            if a is not None:
                combined += f"\n\nAnswer: {a}"
            units.append(("faq", f"Q{num}", combined))
        else:
            units.append(("answer", f"A{num}", txt))
        i += 1
    return units


def split_field_sections(body: str):
    """
    Split anti-pattern style field sections:
      Description
          ...
      Justification
          ...
      Refactoring Plans
          1. ...
    """
    lines = body.splitlines()
    starts = []
    for i, line in enumerate(lines):
        stripped = clean_inline_rst(line.strip()).rstrip(":")
        if stripped.lower() in STRUCTURAL_FIELDS and line == line.lstrip():
            starts.append((i, stripped))

    if len(starts) < 2:
        return None

    units = []
    prefix = "\n".join(lines[:starts[0][0]]).strip()
    if prefix:
        units.append(("context", None, prefix))

    for n, (start, label) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        content = "\n".join(lines[start + 1:end]).strip()
        normalized = label.lower().replace(" ", "_")

        if normalized == "refactoring_plans":
            plans = split_numbered_items(content)
            if plans:
                for pid, ptext in plans:
                    units.append(("refactoring_plan", pid, ptext))
                continue

        units.append((normalized, None, content))
    return units


def split_numbered_items(text: str):
    """Split indented '1.' / '2.' / '3.' lists while preserving item bodies."""
    pat = re.compile(r"(?m)^[ \t]*(\d+)\.\s*$")
    matches = list(pat.finditer(text))
    if not matches:
        # Also support "1. text" on one line.
        pat = re.compile(r"(?m)^[ \t]*(\d+)\.\s+")
        matches = list(pat.finditer(text))
    if not matches:
        return None

    items = []
    for n, m in enumerate(matches):
        end = matches[n + 1].start() if n + 1 < len(matches) else len(text)
        content = text[m.end():end].strip()
        items.append((m.group(1), content))
    return items


def fallback_windows(text: str, max_chars: int, overlap: int):
    """Only used when a semantic structural unit is unusually large."""
    if len(text) <= max_chars:
        return [text]

    pars = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], ""
    for p in pars:
        candidate = f"{cur}\n\n{p}".strip() if cur else p
        if len(candidate) <= max_chars:
            cur = candidate
            continue
        if cur:
            out.append(cur)
        if len(p) > max_chars:
            step = max(1, max_chars - overlap)
            out.extend(p[i:i + max_chars].strip() for i in range(0, len(p), step))
            cur = ""
        else:
            prefix = out[-1][-overlap:] if out and overlap else ""
            cur = f"{prefix}\n\n{p}".strip()
    if cur:
        out.append(cur)
    return [x for x in out if x]


def infer_metadata(path: Path):
    rel = path.relative_to(CORPUS)
    parts = rel.parts
    domain = parts[0] if parts else "unknown"

    # Most useful semantic element is the directory directly containing the file.
    # For role: classes/sortals/role/constraints.rst -> role.
    element = path.parent.name if path.parent != CORPUS else path.stem
    document_type = path.stem

    return {
        "repository": "ontouml-language",
        "domain": domain,
        "element": element,
        "document_type": document_type,
        "source": rel.as_posix(),
        "provenance": "official-ontouml-language",
    }


def structural_units(path: Path, raw: str):
    cleaned = remove_rst_noise(raw)
    result = []

    for heading, body in split_rst_headings(cleaned):
        # Most specific structures first.
        units = split_faq(body)
        if units is None:
            units = split_constraints(body)
        if units is None:
            units = split_field_sections(body)
        if units is None:
            units = [("section", None, body)]

        for unit_type, unit_id, text in units:
            if text.strip():
                result.append({
                    "section": heading,
                    "unit_type": unit_type,
                    "unit_id": unit_id,
                    "text": text.strip(),
                })

    return result


def stable_id(source, section, unit_type, unit_id, ordinal, text):
    raw = f"{source}|{section}|{unit_type}|{unit_id}|{ordinal}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    args = ap.parse_args()

    if not CORPUS.exists():
        raise SystemExit("Corpus missing. Run build_corpus.py first.")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks = []
    structural_counts = {}
    domain_counts = {}

    for path in sorted(CORPUS.rglob("*.rst")):
        meta = infer_metadata(path)
        raw = path.read_text(encoding="utf-8", errors="replace")

        for unit in structural_units(path, raw):
            windows = fallback_windows(unit["text"], args.max_chars, args.overlap)

            for ordinal, source_text in enumerate(windows, start=1):
                unit_label = unit["unit_type"]
                if unit["unit_id"]:
                    unit_label += f" {unit['unit_id']}"

                # Retrieval context is explicit but source text remains untouched.
                embedding_text = (
                    f"OntoUML element: {meta['element']}\n"
                    f"Document: {meta['document_type']}\n"
                    f"Section: {unit['section']}\n"
                    f"Unit: {unit_label}\n\n"
                    f"{source_text}"
                )

                item = {
                    "id": stable_id(
                        meta["source"], unit["section"], unit["unit_type"],
                        unit["unit_id"], ordinal, source_text
                    ),
                    **meta,
                    "section": unit["section"],
                    "unit_type": unit["unit_type"],
                    "unit_id": unit["unit_id"],
                    "chunk": ordinal,
                    "text": source_text,
                    "embedding_text": embedding_text,
                }
                chunks.append(item)

                structural_counts[unit["unit_type"]] = structural_counts.get(unit["unit_type"], 0) + 1
                domain_counts[meta["domain"]] = domain_counts.get(meta["domain"], 0) + 1

    if not chunks:
        raise SystemExit("No chunks generated.")

    CHUNKS_PATH.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in chunks),
        encoding="utf-8",
    )

    print(f"Structural chunks: {len(chunks)}")
    print("By unit type:")
    for k, v in sorted(structural_counts.items()):
        print(f"  {k:20} {v}")
    print("By domain:")
    for k, v in sorted(domain_counts.items()):
        print(f"  {k:20} {v}")

    print(f"\nEmbedding {len(chunks)} structural chunks with {args.model}")
    model = SentenceTransformer(args.model)
    embeddings = model.encode(
        [x["embedding_text"] for x in chunks],
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.asarray(embeddings, dtype="float32"))
    faiss.write_index(index, str(FAISS_PATH))

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["index"] = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "faiss",
        "index_type": "IndexFlatIP",
        "similarity": "cosine",
        "chunking_strategy": "structural-v2",
        "embedding_model": args.model,
        "embedding_dimension": int(embeddings.shape[1]),
        "chunk_count": len(chunks),
        "chunks_by_domain": domain_counts,
        "chunks_by_unit_type": structural_counts,
        "fallback_max_chars": args.max_chars,
        "fallback_overlap_chars": args.overlap,
        "files": {
            "chunks": "index/chunks.jsonl",
            "faiss": "index/faiss.index",
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nDimension: {embeddings.shape[1]}")
    print(f"Chunks:    {CHUNKS_PATH}")
    print(f"FAISS:     {FAISS_PATH}")


if __name__ == "__main__":
    main()
