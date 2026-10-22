"""Semantic retrieval over the Chroma policy collection."""
from dataclasses import asdict, dataclass

from app.rag.embeddings import get_embedder

_collection = None


@dataclass
class RetrievedChunk:
    id: str
    text: str
    doc_id: str
    doc_title: str
    section: str
    score: float

    def citation(self) -> dict:
        d = asdict(self)
        d.pop("text")
        return d


def reset_cache() -> None:
    global _collection
    _collection = None


def _col():
    global _collection
    if _collection is None:
        from app.rag.ingest import get_collection, ingest

        col = get_collection()
        if col.count() == 0:
            ingest()
            col = get_collection()
        _collection = col
    return _collection


def retrieve(query: str, k: int = 5) -> list[RetrievedChunk]:
    col = _col()
    res = col.query(query_embeddings=get_embedder().embed([query]), n_results=k)
    out = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append(RetrievedChunk(id=cid, text=doc, doc_id=meta["doc_id"], doc_title=meta["doc_title"],
                                  section=meta["section"], score=round(1 - float(dist), 4)))
    return out
