"""Answerability check used before the knowledge agent answers.

Signal: IDF-weighted coverage of the (synonym-expanded) question by the best
retrieved chunk. Question terms that never occur in the policy corpus get the
maximum IDF weight, so questions about topics the policies never mention
("student discount", "referral bonus") score low and the agent abstains.
"""
import math
import re
from functools import lru_cache

from app.rag.embeddings import tokenize

# Small domain thesaurus: maps customer vocabulary onto policy vocabulary.
SYNONYMS = {
    r"\b(canada|mexico|uk|europe|abroad|overseas|international|other countries|outside the us)\b": "internationally",
    r"\bmoney back\b": "refund",
    r"\bsend (it |this |something )?back\b": "return",
    r"\b(parcel|shipment)\b": "package",
    r"\b(broken|smashed|cracked)\b": "damaged",
    r"\b(repair|fix)\b": "warranty",
    r"\b(deliver|delivery)\b": "shipping",
    r"\b(phone|call|reach|talk to)\b": "contact support",
    r"\b(price drop|cheaper)\b": "price drops",
}
# Generic question words that carry no topical signal.
GENERIC = {"order", "polic", "vsr", "store", "item", "offer", "available", "work", "possible", "able", "much",
           "long", "many", "day", "time", "kind", "sort", "thing", "someth", "anyth", "exist", "allow"}


def expand(query: str) -> str:
    """Replace customer vocabulary with the policy documents' vocabulary."""
    q = query.lower()
    for pat, rep in SYNONYMS.items():
        q = re.sub(pat, rep, q)
    return q


@lru_cache
def _idf() -> tuple[dict, float]:
    from app.rag.ingest import load_chunks

    chunks, _ = load_chunks()
    df: dict[str, int] = {}
    for c in chunks:
        for t in set(tokenize(c.text)):
            df[t] = df.get(t, 0) + 1
    n = len(chunks)
    idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}
    # Terms never seen in the policies weigh twice the rarest real term.
    return idf, 2 * math.log((n + 1) / 0.5)


def query_terms(query: str) -> set[str]:
    # Remove conversational wording that does not affect policy answerability.
    cleaned = re.sub(
        r"\b(hi|hello|hey|recently|confused|confuse|explain|"
        r"process|purchased|purchase|headphones|headphone|am)\b",
        " ",
        expand(query),
        flags=re.IGNORECASE,
    )
    return set(tokenize(cleaned)) - GENERIC


def coverage(query: str, chunk_text: str) -> float:
    idf, max_idf = _idf()
    terms = query_terms(query)
    if not terms:
        return 0.0
    chunk = set(tokenize(chunk_text))
    total = sum(idf.get(t, max_idf) for t in terms)
    hit = sum(idf.get(t, max_idf) for t in terms if t in chunk)
    return hit / total


def best_coverage(query: str, chunk_texts: list[str]) -> float:
    return max((coverage(query, t) for t in chunk_texts), default=0.0)
