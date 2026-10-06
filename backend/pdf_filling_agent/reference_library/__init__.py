"""Reference form library: reusable knowledge, embeddings, classification and dynamic few-shot."""

from .classifier import Classification, classify_form
from .fewshot import build_fewshot, format_fewshot_block
from .library import ReferenceLibrary, get_default_library

__all__ = [
    "ReferenceLibrary", "get_default_library", "Classification", "classify_form",
    "build_fewshot", "format_fewshot_block",
]
