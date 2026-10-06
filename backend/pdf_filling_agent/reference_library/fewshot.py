"""
Dynamic few-shot: for the fields of the form being filled, retrieve only the most similar
fields from the reference library and render them as a compact hint block for the LLM.

Never sends reference documents. Examples are hints: the LLM output still goes through
FillingValidator, and the master-model dictionary already in the system prompt is not repeated.
"""

import os
from typing import Any, Dict, List, Optional

from .extractor import clean_label


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def build_fewshot(
    library,
    widgets: List[Dict[str, Any]],
    top_k: Optional[int] = None,
    family: Optional[str] = None,
    exclude_docs=(),
    min_similarity: Optional[float] = None,
    max_examples: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return examples [{field_name, label, ref_label, concept, similarity, document, section}].

    top_k           best distinct concepts kept per field (REFERENCE_FEWSHOT_TOP_K, default 5)
    max_examples    hard cap for the whole call (REFERENCE_FEWSHOT_MAX, default 20)
    min_similarity  relevance floor (REFERENCE_FEWSHOT_MIN_SIM, default 0.55)
    """
    top_k = top_k or _env_int("REFERENCE_FEWSHOT_TOP_K", 5)
    max_examples = max_examples or _env_int("REFERENCE_FEWSHOT_MAX", 20)
    min_similarity = _env_float("REFERENCE_FEWSHOT_MIN_SIM", 0.55) if min_similarity is None else min_similarity

    queries = [clean_label(w.get("label", ""), w.get("field_name", "")) for w in widgets]
    usable = [(w, q) for w, q in zip(widgets, queries) if q]
    if not usable:
        return []

    results = library.search_many(
        [q for _, q in usable], top_k=top_k * 2, prefer_family=family, min_similarity=min_similarity,
        concept_only=True, include_builtin=False, exclude_docs=exclude_docs,
    )
    examples: List[Dict[str, Any]] = []
    for (w, q), hits in zip(usable, results):
        seen = set()
        for h in hits:
            if h["concept"] in seen:
                continue
            seen.add(h["concept"])
            occ = next((o for o in h["occurrences"] if o["concept"] == h["concept"]), h["occurrences"][0])
            examples.append({
                "field_name": w.get("field_name", ""), "label": q, "ref_label": h["label"], "concept": h["concept"],
                "similarity": h["similarity"], "document": occ["document"], "section": occ["section"],
            })
            if len(seen) >= top_k:
                break
    examples.sort(key=lambda e: -e["similarity"])
    return examples[:max_examples]


def format_fewshot_block(examples: List[Dict[str, Any]], family: Optional[str] = None, confidence: float = 0.0) -> str:
    if not examples:
        return ""
    lines = ["", "REFERENCE KNOWLEDGE (hints from previously seen forms; the field's own label/section and the rules above prevail):"]
    if family:
        lines.append(f"- This form most resembles the known family '{family}' (confidence {confidence:.0%}).")
    for e in examples:
        sec = f" [{e['section'][:40]}]" if e.get("section") else ""
        lines.append(
            f"- Field ID '{e['field_name']}' (label '{e['label'][:70]}') resembles reference \"{e['ref_label'][:70]}\"{sec} "
            f"from '{e['document'][:40]}', which maps to profile key '{e['concept']}' (similarity {e['similarity']:.2f})."
        )
    return "\n".join(lines) + "\n"
