"""
Embedders for form-field labels.

`Embedder` is the only contract the rest of the library depends on, so the vector
provider can change without touching the store, the classifier or the few-shot builder.

- `HashingEmbedder` (default): local, deterministic, zero cost, no extra dependency.
  Lexical (word + char n-gram) with a small Spanish business-term canonicalisation.
- `OpenAIEmbedder`: real semantic embeddings through Azure OpenAI / OpenAI, reusing the
  credentials the agent already reads from `.env`. Enabled with `EMBEDDING_PROVIDER`.
"""

import os
import re
import unicodedata
import zlib
from typing import List, Optional, Protocol

import numpy as np

_STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "e", "u", "a", "en", "para", "por",
    "con", "al", "que", "su", "sus", "un", "una", "se", "es", "ser", "si",
}

# token -> canonical tokens. Keeps equivalent business vocabulary close in the local space.
_TERM_MAP = {
    "nit": ["identificacion", "tributaria"], "rut": ["identificacion", "tributaria"],
    "tax": ["identificacion", "tributaria"], "tributario": ["tributaria"],
    "fiscal": ["tributaria"], "tributaria": ["tributaria"],
    "no": ["numero"], "nro": ["numero"], "num": ["numero"], "n": ["numero"],
    "compania": ["empresa"], "sociedad": ["empresa"], "organizacion": ["empresa"],
    "entidad": ["empresa"], "empresarial": ["empresa"], "juridica": ["empresa"],
    "apoderado": ["representante"], "gerente": ["representante"],
    "correo": ["email"], "mail": ["email"], "electronico": ["email"],
    "celular": ["movil"], "telefono": ["telefono"], "tel": ["telefono"],
    "direccion": ["direccion"], "domicilio": ["direccion"], "residencia": ["direccion"],
    "cedula": ["cedula"], "cc": ["cedula"],
    "denominacion": ["razon", "social"], "legal": ["legal"],
}

_DIM = 512


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def _stem(tok: str) -> str:
    """Cheap Spanish stemming: plural, adverb -mente and a 7-char prefix (represent-e/-a/-ante)."""
    if len(tok) > 4 and tok.endswith("s"):
        tok = tok[:-1]
    if len(tok) > 7 and tok.endswith("mente"):
        tok = tok[:-5]
    return tok[:7]


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for tok in normalize_text(text).split():
        if tok in _STOPWORDS:
            continue
        if len(tok) > 4 and tok.endswith("s"):
            tok = tok[:-1]
        tokens.extend(_stem(t) for t in _TERM_MAP.get(tok, [tok]))
    return tokens


class Embedder(Protocol):
    name: str

    def embed(self, texts: List[str]) -> np.ndarray:
        """Return an (n, d) float32 array of L2-normalised vectors."""


def _normalise_rows(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(norms == 0, 1.0, norms)).astype(np.float32)


class HashingEmbedder:
    name = f"local-hash-{_DIM}-v2"

    def __init__(self, dim: int = _DIM):
        self.dim = dim

    def _add(self, vec: np.ndarray, feature: str, weight: float) -> None:
        h = zlib.crc32(feature.encode("utf-8"))
        vec[h % self.dim] += weight if (h >> 31) & 1 else -weight

    def embed(self, texts: List[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            toks = tokenize(text)
            for j, tok in enumerate(toks):
                self._add(out[i], "w:" + tok, 1.0)
                padded = f"#{tok}#"
                for n in (3, 4):
                    for k in range(max(1, len(padded) - n + 1)):
                        self._add(out[i], "c:" + padded[k:k + n], 0.3)
                if j:
                    self._add(out[i], f"b:{toks[j - 1]}_{tok}", 0.7)
        return _normalise_rows(out)


class OpenAIEmbedder:
    """Azure OpenAI / OpenAI embeddings. Created only when explicitly configured."""

    def __init__(self, provider: str):
        from openai import AzureOpenAI, OpenAI

        if provider == "azure":
            self.model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
            self.client = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT", ""),
                api_key=os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY", ""),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            )
        else:
            self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            self.client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
        self.name = f"{provider}:{self.model}"

    def embed(self, texts: List[str]) -> np.ndarray:
        rows: List[List[float]] = []
        for i in range(0, len(texts), 96):
            batch = [t or " " for t in texts[i:i + 96]]
            res = self.client.embeddings.create(model=self.model, input=batch)
            rows.extend(d.embedding for d in res.data)
        return _normalise_rows(np.asarray(rows, dtype=np.float32))


def get_default_embedder(provider: Optional[str] = None) -> Embedder:
    """EMBEDDING_PROVIDER: local (default) | azure | openai. Falls back to local on any setup error."""
    provider = (provider or os.getenv("EMBEDDING_PROVIDER", "local")).strip().lower()
    if provider in ("azure", "openai"):
        try:
            return OpenAIEmbedder(provider)
        except Exception as ex:
            print(f"[WARN] Embedding provider '{provider}' unavailable ({ex}); using local embedder.")
    return HashingEmbedder()
