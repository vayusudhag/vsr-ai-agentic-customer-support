"""Embedding providers.

`HashingEmbedder` is a deterministic, offline embedding (feature hashing of
stemmed unigrams + bigrams with sublinear TF and L2 normalisation). It needs no
model download or API key, so the project runs and its evaluation is
reproducible anywhere. Set EMBEDDING_PROVIDER=openai to use OpenAI embeddings.
"""
import hashlib
import math
import re
from functools import lru_cache

from app.config import get_settings

STOPWORDS = set(
    """a an the and or but if of to in on for with at by from as is are was were be been being it its this that
    these those i you your we our they their he she my me do does did can could would should will may might
    what when where which who how why there here about into than then so not no yes any all some have has had
    get got also just please tell know want need like""".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _stem(tok: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(tok) > 4 and tok.endswith(suf):
            return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class HashingEmbedder:
    name = "hashing-1024"

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _bucket(self, feature: str) -> tuple[int, float]:
        h = int(hashlib.md5(feature.encode()).hexdigest(), 16)
        return h % self.dim, (1.0 if (h >> 64) & 1 else -1.0)

    def embed_one(self, text: str) -> list[float]:
        toks = tokenize(text)
        feats: dict[str, float] = {}
        for t in toks:
            feats[t] = feats.get(t, 0) + 1.0
        for a, b in zip(toks, toks[1:]):
            k = f"{a}_{b}"
            feats[k] = feats.get(k, 0) + 0.5
        vec = [0.0] * self.dim
        for f, tf in feats.items():
            i, sign = self._bucket(f)
            vec[i] += sign * (1.0 + math.log(tf))
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]


class OpenAIEmbedder:
    def __init__(self):
        from langchain_openai import OpenAIEmbeddings

        s = get_settings()
        self._impl = OpenAIEmbeddings(model=s.openai_embedding_model, api_key=s.openai_api_key)
        self.name = f"openai-{s.openai_embedding_model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._impl.embed_documents(texts)


@lru_cache
def get_embedder():
    s = get_settings()
    if s.embedding_provider == "openai" and s.openai_api_key:
        return OpenAIEmbedder()
    return HashingEmbedder()
