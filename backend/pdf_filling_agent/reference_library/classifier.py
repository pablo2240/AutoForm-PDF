"""
Form-family classification.

A new form is compared against every reference document on *content*, never on file name:
  - label similarity (soft precision/recall over embedded labels)
  - master-model concept overlap (Jaccard)
  - structure (field count, pages, AcroForm vs flat)
Documents are grouped by family (sub-folder / manifest entry), so adding a family is just
adding documents under a new name. Below the confidence gate the form is "unknown" and the
caller falls back to general analysis + semantic search.
"""

import math
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .embeddings import normalize_text
from .extractor import ExtractedForm

LABEL_FLOOR = 0.4          # cosine below this counts as no match
W_LABELS, W_CONCEPTS, W_STRUCTURE = 0.5, 0.35, 0.15
SOFTMAX_TEMPERATURE = 0.07  # turns family scores into the "86% / 9% / 5%" shares


def _min_score() -> float:
    return float(os.getenv("REFERENCE_CLASSIFY_MIN_SCORE", "0.30"))


def _min_share() -> float:
    return float(os.getenv("REFERENCE_CLASSIFY_MIN_SHARE", "0.60"))


@dataclass
class Classification:
    family: Optional[str]
    confidence: float
    is_known: bool
    strategy: str  # "family" | "unknown"
    shares: List[Dict[str, Any]] = field(default_factory=list)
    nearest_documents: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ratio(a: float, b: float) -> float:
    return min(a, b) / max(a, b) if a and b else 0.0


def classify_form(library, form: ExtractedForm, exclude_docs: Iterable[str] = ()) -> Classification:
    from .library import UNCLASSIFIED

    rows = library.store.document_occurrences(exclude_docs=exclude_docs)
    ids, matrix = library.store.label_matrix(library.embedder.name)
    labels = list(dict.fromkeys(normalize_text(f.label) for f in form.fields if normalize_text(f.label)))
    if not rows or not labels or not len(ids):
        return Classification(None, 0.0, False, "unknown")

    row_of = {int(i): r for r, i in enumerate(ids)}
    sims = library._embed_queries(labels) @ matrix.T
    new_concepts = {f.concept for f in form.fields if f.concept}

    docs: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = docs.setdefault(r["doc_id"], {"cols": set(), "concepts": set(), "family": r["family"] or UNCLASSIFIED,
                                          "n_widgets": r["n_widgets"], "acro": r["is_acroform"], "pages": r["n_pages"]})
        if r["label_id"] in row_of:
            d["cols"].add(row_of[r["label_id"]])
        if r["concept"]:
            d["concepts"].add(r["concept"])

    scored: List[Dict[str, Any]] = []
    for doc_id, d in docs.items():
        if not d["cols"]:
            continue
        block = np.clip((sims[:, sorted(d["cols"])] - LABEL_FLOOR) / (1 - LABEL_FLOOR), 0, 1)
        p, r = float(block.max(axis=1).mean()), float(block.max(axis=0).mean())
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        union = new_concepts | d["concepts"]
        jac = len(new_concepts & d["concepts"]) / len(union) if union else 0.0
        structure = (0.5 * _ratio(form.n_widgets or len(form.fields), d["n_widgets"] or 1)
                     + 0.3 * _ratio(form.n_pages, d["pages"] or 1) + 0.2 * (bool(form.is_acroform) == bool(d["acro"])))
        scored.append({"doc_id": doc_id, "family": d["family"],
                       "score": round(W_LABELS * f1 + W_CONCEPTS * jac + W_STRUCTURE * structure, 4)})

    by_family: Dict[str, List[float]] = {}
    for s in sorted(scored, key=lambda s: -s["score"]):
        by_family.setdefault(s["family"], []).append(s["score"])
    fam_scores = {f: (0.7 * v[0] + 0.3 * v[1]) if len(v) > 1 else v[0] for f, v in by_family.items()}
    if not fam_scores:
        return Classification(None, 0.0, False, "unknown")

    exp = {f: math.exp(s / SOFTMAX_TEMPERATURE) for f, s in fam_scores.items()}
    total = sum(exp.values())
    shares = sorted(({"family": f, "share": round(exp[f] / total, 4), "score": round(fam_scores[f], 4)} for f in fam_scores),
                    key=lambda x: -x["share"])
    best = shares[0]
    known = best["score"] >= _min_score() and best["share"] >= _min_share() and best["family"] != UNCLASSIFIED
    return Classification(
        family=best["family"] if known else None,
        confidence=best["score"], is_known=known, strategy="family" if known else "unknown",
        shares=shares[:5], nearest_documents=sorted(scored, key=lambda s: -s["score"])[:3],
    )
