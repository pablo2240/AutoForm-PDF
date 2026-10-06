"""
ReferenceLibrary: the single entry point of the knowledge layer.

    referencias/pdf/<familia>/*.pdf  ->  extract  ->  labels + vectors (SQLite)  ->  search / classify / few-shot

`referencias/pdf` is the source of truth; `sync()` mirrors it into the database (new, changed
and removed files are detected by SHA-256), so growing from 5 to thousands of forms means
dropping files in the folder, with no code changes.
"""

import hashlib
import json
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from ..field_dictionary import FIELD_SYNONYMS
from .embeddings import Embedder, get_default_embedder, normalize_text
from .extractor import EXTRACTOR_VERSION, ExtractedForm, extract_reference, form_from_rich_widgets
from .store import Store

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_REFERENCES_DIR = os.path.join(PROJECT_ROOT, "referencias", "pdf")
DEFAULT_MANIFEST = os.path.join(PROJECT_ROOT, "referencias", "manifest.json")
DEFAULT_DB = os.path.join(PROJECT_ROOT, "backend", "data", "reference_library", "library.db")

MASTER_MODEL_ID = "__modelo_maestro__"
UNCLASSIFIED = "sin_clasificar"
PROPAGATE_MIN_SIMILARITY = 0.8  # an unlabeled label inherits the concept of a near-identical trusted one


class ReferenceLibrary:
    def __init__(
        self,
        db_path: Optional[str] = None,
        references_dir: Optional[str] = None,
        manifest_path: Optional[str] = None,
        embedder: Optional[Embedder] = None,
    ):
        self.references_dir = os.path.abspath(references_dir or os.getenv("REFERENCE_LIBRARY_DIR") or DEFAULT_REFERENCES_DIR)
        self.manifest_path = manifest_path or DEFAULT_MANIFEST
        self.embedder = embedder or get_default_embedder()
        self.store = Store(db_path or os.getenv("REFERENCE_LIBRARY_DB") or DEFAULT_DB)
        self._query_cache: Dict[str, np.ndarray] = {}
        self._lock = threading.RLock()

    # ---- ingestion ------------------------------------------------------------------
    def _manifest(self) -> Dict[str, str]:
        """{relative path or filename: family}. Optional; sub-folder name is the fallback family."""
        try:
            with open(self.manifest_path, "r", encoding="utf-8-sig") as f:
                return {k: v for k, v in json.load(f).get("families", {}).items()}
        except Exception:
            return {}

    def _family_for(self, doc_id: str, manifest: Dict[str, str]) -> str:
        if doc_id in manifest:
            return manifest[doc_id]
        if os.path.basename(doc_id) in manifest:
            return manifest[os.path.basename(doc_id)]
        parts = doc_id.split("/")
        return parts[0] if len(parts) > 1 else UNCLASSIFIED

    @staticmethod
    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _ingest(self, path: str, doc_id: str, family: str, sha: str) -> Dict[str, Any]:
        form: ExtractedForm = extract_reference(path)
        occurrences = [
            {
                "text_norm": normalize_text(f.label), "label_raw": f.label, "section": f.section, "page": f.page,
                "rect": f.rect, "field_type": f.field_type, "field_name": f.field_name, "concept": f.concept,
                "concept_source": f.concept_source, "concept_score": f.concept_score,
                "example_value": f.example_value,
                "context": dict(f.context, in_table=f.in_table),
            }
            for f in form.fields if normalize_text(f.label)
        ]
        self.store.replace_document(
            {"doc_id": doc_id, "filename": os.path.basename(path), "sha256": sha, "family": family,
             "n_pages": form.n_pages, "n_widgets": form.n_widgets, "is_acroform": form.is_acroform,
             "structure": {"pages": form.structure, "sections": form.sections},
             "instructions": form.instructions, "extractor_version": EXTRACTOR_VERSION},
            occurrences,
        )
        return {"doc_id": doc_id, "family": family, "fields": len(occurrences), "pages": form.n_pages}

    def _sync_master_model(self) -> None:
        """The existing FIELD_SYNONYMS dictionary becomes a searchable pseudo-document (label -> master key)."""
        sha = hashlib.sha256(json.dumps(FIELD_SYNONYMS, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        current = self.store.get_document(MASTER_MODEL_ID)
        if current and current["sha256"] == sha:
            return
        occurrences = [
            {"text_norm": normalize_text(s), "label_raw": s, "section": "Modelo maestro", "page": 0, "rect": [],
             "field_type": "Text", "concept": concept, "concept_source": "builtin", "concept_score": 1.0}
            for concept, syns in FIELD_SYNONYMS.items() for s in dict.fromkeys(syns) if normalize_text(s)
        ]
        # a label shared by two concepts (e.g. "País") keeps one row per concept; normalised duplicates collapse
        unique = {(o["text_norm"], o["concept"]): o for o in occurrences}
        self.store.replace_document(
            {"doc_id": MASTER_MODEL_ID, "filename": "field_dictionary.py", "sha256": sha, "family": None, "builtin": 1,
             "extractor_version": EXTRACTOR_VERSION},
            list(unique.values()),
        )

    def _finalize(self) -> None:
        """Embed any label without a vector for the active embedder, then propagate concepts."""
        missing = self.store.labels_missing_vectors(self.embedder.name)
        if missing:
            ids, texts = zip(*missing)
            self.store.save_vectors(self.embedder.name, ids, self.embedder.embed(list(texts)))
        self._propagate_concepts()
        self._query_cache.clear()

    def _propagate_concepts(self) -> None:
        self.store.clear_propagated()
        trusted = self.store.concept_labels()
        unlabeled = self.store.unlabeled_occurrences()
        ids, matrix = self.store.label_matrix(self.embedder.name)
        if not trusted or not unlabeled or not len(ids):
            return
        row_of = {int(i): r for r, i in enumerate(ids)}
        t_rows = [(row_of[t["label_id"]], t) for t in trusted if t["label_id"] in row_of]
        if not t_rows:
            return
        t_matrix = matrix[[r for r, _ in t_rows]]
        updates = []
        by_label: Dict[int, List[int]] = {}
        for o in unlabeled:
            by_label.setdefault(o["label_id"], []).append(o["id"])
        for label_id, occ_ids in by_label.items():
            if label_id not in row_of:
                continue
            sims = t_matrix @ matrix[row_of[label_id]]
            best = int(np.argmax(sims))
            if sims[best] >= PROPAGATE_MIN_SIMILARITY:
                concept = t_rows[best][1]["concept"]
                updates += [(concept, "propagated", float(sims[best]), oid) for oid in occ_ids]
        self.store.update_concepts(updates)

    def sync(self, force: bool = False) -> Dict[str, Any]:
        """Mirror `referencias/pdf` into the database. Idempotent and cheap when nothing changed."""
        with self._lock:
            os.makedirs(self.references_dir, exist_ok=True)
            manifest = self._manifest()
            report: Dict[str, List] = {"added": [], "updated": [], "removed": [], "unchanged": [], "errors": []}
            on_disk: Dict[str, str] = {}
            for root, _, files in os.walk(self.references_dir):
                for name in files:
                    if name.lower().endswith(".pdf"):
                        full = os.path.join(root, name)
                        on_disk[os.path.relpath(full, self.references_dir).replace(os.sep, "/")] = full

            known = {d["doc_id"]: d for d in self.store.list_documents()}
            for doc_id, full in sorted(on_disk.items()):
                family = self._family_for(doc_id, manifest)
                try:
                    sha = self._sha256(full)
                    cur = known.get(doc_id)
                    if cur and not force and cur["sha256"] == sha and cur["extractor_version"] == EXTRACTOR_VERSION:
                        if cur["family"] != family:
                            self.store.set_family(doc_id, family)
                            report["updated"].append(doc_id)
                        else:
                            report["unchanged"].append(doc_id)
                        continue
                    self._ingest(full, doc_id, family, sha)
                    report["updated" if cur else "added"].append(doc_id)
                except Exception as ex:
                    report["errors"].append({"doc_id": doc_id, "error": str(ex)})
            for doc_id in known.keys() - on_disk.keys():
                self.store.delete_document(doc_id)
                report["removed"].append(doc_id)

            self._sync_master_model()
            self._finalize()
            return report

    def add_document(self, filename: str, data: bytes, family: Optional[str] = None) -> Dict[str, Any]:
        """Store a reference PDF (under `<familia>/` when given) and process it."""
        safe = os.path.basename(filename)
        if not safe.lower().endswith(".pdf"):
            raise ValueError("Solo se admiten referencias PDF")
        sub = normalize_text(family).replace(" ", "_") if family else ""
        target_dir = os.path.join(self.references_dir, sub) if sub else self.references_dir
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, safe), "wb") as f:
            f.write(data)
        report = self.sync()
        return {"doc_id": f"{sub}/{safe}" if sub else safe, "sync": report}

    def remove_document(self, doc_id: str) -> bool:
        with self._lock:
            path = os.path.abspath(os.path.join(self.references_dir, doc_id))
            if not path.startswith(self.references_dir + os.sep):
                raise ValueError("doc_id inválido")
            if os.path.exists(path):
                os.remove(path)
            removed = self.store.delete_document(doc_id)
            self._finalize()
            return removed

    def reprocess(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Force re-extraction of one document (or all of them)."""
        if doc_id is None:
            return self.sync(force=True)
        with self._lock:
            full = os.path.join(self.references_dir, doc_id)
            if not os.path.exists(full):
                raise FileNotFoundError(doc_id)
            info = self._ingest(full, doc_id, self._family_for(doc_id, self._manifest()), self._sha256(full))
            self._finalize()
            return info

    # ---- queries --------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        docs = self.store.list_documents()
        ids, _ = self.store.label_matrix(self.embedder.name)
        families: Dict[str, int] = {}
        for d in docs:
            families[d["family"] or UNCLASSIFIED] = families.get(d["family"] or UNCLASSIFIED, 0) + 1
        return {"embedder": self.embedder.name, "documents": len(docs), "families": families,
                "unique_labels": int(len(ids)), "references_dir": self.references_dir,
                "items": [{k: d[k] for k in ("doc_id", "family", "n_pages", "n_widgets", "n_fields", "processed_at")} for d in docs]}

    def _embed_queries(self, texts: List[str]) -> np.ndarray:
        todo = [t for t in dict.fromkeys(texts) if t not in self._query_cache]
        if todo:
            for t, v in zip(todo, self.embedder.embed(todo)):
                self._query_cache[t] = v
        return np.vstack([self._query_cache[t] for t in texts])

    def search_many(
        self,
        queries: List[str],
        top_k: int = 5,
        family: Optional[str] = None,
        prefer_family: Optional[str] = None,
        min_similarity: float = 0.0,
        concept_only: bool = False,
        include_builtin: bool = True,
        exclude_docs: Iterable[str] = (),
    ) -> List[List[Dict[str, Any]]]:
        """Semantic search: one ranked list of distinct labels per query, each with full provenance."""
        ids, matrix = self.store.label_matrix(self.embedder.name)
        if not len(ids) or not queries:
            return [[] for _ in queries]
        qv = self._embed_queries(queries)
        sims = qv @ matrix.T
        n_cand = min(len(ids), max(top_k * 6, 30))
        excl = list(exclude_docs)
        results: List[List[Dict[str, Any]]] = []
        occ_cache: Dict[int, List[Dict[str, Any]]] = {}
        wanted = {int(ids[j]) for row in sims for j in np.argpartition(-row, n_cand - 1)[:n_cand] if row[j] >= min_similarity}
        for occ in self.store.occurrences_for(sorted(wanted), exclude_docs=excl):
            occ_cache.setdefault(occ["label_id"], []).append(occ)

        for qi, row in enumerate(sims):
            cand = np.argpartition(-row, n_cand - 1)[:n_cand]
            hits = []
            for j in cand[np.argsort(-row[cand])]:
                sim = float(row[j])
                if sim < min_similarity:
                    break
                occs = [o for o in occ_cache.get(int(ids[j]), [])
                        if (include_builtin or not o["builtin"]) and (not family or o["family"] == family)
                        and (not concept_only or o["concept"])]
                if not occs:
                    continue
                counts: Dict[str, float] = {}
                for o in occs:
                    if o["concept"]:
                        counts[o["concept"]] = counts.get(o["concept"], 0) + 1 + o["concept_score"]
                concept = max(counts, key=counts.get) if counts else None
                if concept_only and not concept:
                    continue
                occs.sort(key=lambda o: (o["concept"] != concept, o["builtin"], -o["concept_score"]))
                hits.append({
                    "label": occs[0]["label_raw"], "similarity": round(sim, 4), "concept": concept,
                    "_rank": sim + (0.05 if prefer_family and any(o["family"] == prefer_family for o in occs) else 0.0),
                    "occurrences": [
                        {"document": o["filename"], "doc_id": o["doc_id"], "family": o["family"], "page": o["page"],
                         "rect": o["rect"], "section": o["section"], "field_type": o["field_type"],
                         "concept": o["concept"], "concept_source": o["concept_source"],
                         "context": o["context"], "example_value": o["example_value"]}
                        for o in occs[:5]
                    ],
                })
            hits.sort(key=lambda h: -h["_rank"])
            for h in hits:
                del h["_rank"]
            results.append(hits[:top_k])
        return results

    def search(self, query: str, top_k: int = 5, **kw) -> List[Dict[str, Any]]:
        return self.search_many([query], top_k=top_k, **kw)[0]

    def classify_pdf(self, pdf_path: str, exclude_docs: Iterable[str] = ()):
        from .classifier import classify_form
        return classify_form(self, extract_reference(pdf_path), exclude_docs=exclude_docs)

    def classify_widgets(self, rich_widgets: List[Dict[str, Any]], n_pages: int, exclude_docs: Iterable[str] = ()):
        """Classify from widgets already extracted by the caller (no second pass over the PDF)."""
        from .classifier import classify_form
        return classify_form(self, form_from_rich_widgets(rich_widgets, n_pages), exclude_docs=exclude_docs)


_default: Optional[ReferenceLibrary] = None
_default_failed = False
_default_lock = threading.Lock()


def get_default_library() -> Optional[ReferenceLibrary]:
    """Process-wide library synced once. None when disabled (REFERENCE_LIBRARY_ENABLED=0) or on failure."""
    global _default, _default_failed
    if os.getenv("REFERENCE_LIBRARY_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return None
    with _default_lock:
        if _default is None and not _default_failed:
            try:
                lib = ReferenceLibrary()
                lib.sync()
                _default = lib
            except Exception as ex:
                _default_failed = True
                print(f"[WARN] Reference library unavailable, continuing without it: {ex}")
    return _default
