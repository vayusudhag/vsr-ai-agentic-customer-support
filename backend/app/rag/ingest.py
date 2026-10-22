"""Document ingestion: load -> clean -> chunk -> embed -> store in Chroma."""
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.rag.embeddings import get_embedder

# Lines in source documents that look like instructions aimed at an AI model are
# removed during ingestion (defence-in-depth against indirect prompt injection).
INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ignore (all|any|the)? ?(previous|prior|above) (instructions|rules)",
        r"disregard (the )?(system|previous|above)",
        r"you are now",
        r"system prompt",
        r"(approve|issue) (all|every|any) refunds?",
        r"reveal (your|the) (instructions|prompt|api key)",
    ]
]
MAX_WORDS = 120
OVERLAP_WORDS = 25


@dataclass
class Chunk:
    id: str
    text: str
    doc_id: str
    doc_title: str
    section: str


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clean_text(text: str) -> tuple[str, int]:
    kept, removed = [], 0
    for line in text.splitlines():
        if any(p.search(line) for p in INJECTION_PATTERNS):
            removed += 1
            continue
        kept.append(re.sub(r"[ \t]+", " ", line).rstrip())
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return cleaned, removed


def chunk_document(doc_id: str, text: str) -> list[Chunk]:
    title_m = re.search(r"^# (.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else doc_id
    chunks: list[Chunk] = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = sec.partition("\n")
        heading, body = heading.strip(), " ".join(body.split())
        words = body.split()
        start, part = 0, 0
        while start < len(words):
            piece = " ".join(words[start : start + MAX_WORDS])
            chunks.append(
                Chunk(
                    id=f"{doc_id}::{slug(heading)}::{part}",
                    text=f"{title} - {heading}: {piece}",
                    doc_id=doc_id,
                    doc_title=title,
                    section=heading,
                )
            )
            part += 1
            if start + MAX_WORDS >= len(words):
                break
            start += MAX_WORDS - OVERLAP_WORDS
    return chunks


def load_chunks(policies_dir: str | None = None) -> tuple[list[Chunk], int]:
    d = Path(policies_dir or get_settings().policies_dir)
    all_chunks, removed_total = [], 0
    for path in sorted(d.glob("*.md")):
        cleaned, removed = clean_text(path.read_text(encoding="utf-8"))
        removed_total += removed
        all_chunks.extend(chunk_document(path.stem, cleaned))
    return all_chunks, removed_total


def get_collection(reset: bool = False):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    s = get_settings()
    client = chromadb.PersistentClient(path=s.chroma_path, settings=ChromaSettings(anonymized_telemetry=False))
    if reset:
        try:
            client.delete_collection(s.chroma_collection)
        except Exception:
            pass
    return client.get_or_create_collection(
        s.chroma_collection, embedding_function=None, metadata={"hnsw:space": "cosine"}
    )


def ingest(policies_dir: str | None = None) -> dict:
    chunks, removed = load_chunks(policies_dir)
    embedder = get_embedder()
    col = get_collection(reset=True)
    col.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embedder.embed([c.text for c in chunks]),
        metadatas=[{"doc_id": c.doc_id, "doc_title": c.doc_title, "section": c.section} for c in chunks],
    )
    from app.rag import retriever

    retriever.reset_cache()
    return {"documents": len({c.doc_id for c in chunks}), "chunks": len(chunks),
            "embedder": embedder.name, "suspicious_lines_removed": removed}


if __name__ == "__main__":
    print("Ingested:", ingest())
