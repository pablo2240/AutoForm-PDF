"""
SQLite persistence (stdlib) for the reference library.

documents    one row per reference PDF (sha256 drives re-processing)
labels       unique normalised label text + its vector (dedupes across documents, so the
             vector matrix grows with *distinct vocabulary*, not with the number of forms)
occurrences  every appearance of a label: document, page, rect, section, context, concept

The database is a derived cache: it can be deleted and rebuilt from `referencias/pdf`.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY, filename TEXT, sha256 TEXT, family TEXT, builtin INTEGER DEFAULT 0,
    n_pages INTEGER, n_widgets INTEGER, is_acroform INTEGER, structure TEXT, instructions TEXT,
    extractor_version INTEGER, processed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS labels (
    label_id INTEGER PRIMARY KEY AUTOINCREMENT, text_norm TEXT UNIQUE NOT NULL, text TEXT NOT NULL,
    embedder TEXT, vector BLOB
);
CREATE TABLE IF NOT EXISTS occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES labels(label_id),
    label_raw TEXT, section TEXT, page INTEGER, rect TEXT, field_type TEXT, field_name TEXT,
    concept TEXT, concept_source TEXT, concept_score REAL, example_value TEXT, context TEXT
);
CREATE INDEX IF NOT EXISTS idx_occ_doc ON occurrences(doc_id);
CREATE INDEX IF NOT EXISTS idx_occ_label ON occurrences(label_id);
"""


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
        self._matrix: Optional[Tuple[Any, np.ndarray, np.ndarray]] = None  # (cache key, label_ids, matrix)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- documents -------------------------------------------------------------------
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(self, include_builtin: bool = False) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT d.*, (SELECT COUNT(*) FROM occurrences o WHERE o.doc_id = d.doc_id) AS n_fields "
                "FROM documents d WHERE (? OR d.builtin = 0) ORDER BY d.doc_id", (int(include_builtin),)
            ).fetchall()
        return [dict(r) for r in rows]

    def replace_document(self, doc: Dict[str, Any], occurrences: List[Dict[str, Any]]) -> None:
        """Atomically (re)write a document and its occurrences; labels are get-or-created."""
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE doc_id = ?", (doc["doc_id"],))
            c.execute(
                "INSERT INTO documents (doc_id, filename, sha256, family, builtin, n_pages, n_widgets, is_acroform,"
                " structure, instructions, extractor_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (doc["doc_id"], doc.get("filename"), doc.get("sha256"), doc.get("family"), int(doc.get("builtin", 0)),
                 doc.get("n_pages", 0), doc.get("n_widgets", 0), int(doc.get("is_acroform", 0)),
                 json.dumps(doc.get("structure", []), ensure_ascii=False),
                 json.dumps(doc.get("instructions", []), ensure_ascii=False), doc.get("extractor_version", 0)),
            )
            for o in occurrences:
                c.execute("INSERT OR IGNORE INTO labels (text_norm, text) VALUES (?, ?)", (o["text_norm"], o["label_raw"]))
                label_id = c.execute("SELECT label_id FROM labels WHERE text_norm = ?", (o["text_norm"],)).fetchone()[0]
                c.execute(
                    "INSERT INTO occurrences (doc_id, label_id, label_raw, section, page, rect, field_type, field_name,"
                    " concept, concept_source, concept_score, example_value, context) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (doc["doc_id"], label_id, o["label_raw"], o.get("section", ""), o.get("page", 0),
                     json.dumps(o.get("rect", [])), o.get("field_type", ""), o.get("field_name", ""), o.get("concept"),
                     o.get("concept_source", ""), o.get("concept_score", 0.0), o.get("example_value", ""),
                     json.dumps(o.get("context", {}), ensure_ascii=False)),
                )
            self._gc_labels(c)

    def set_family(self, doc_id: str, family: Optional[str]) -> None:
        with self._conn() as c:
            c.execute("UPDATE documents SET family = ? WHERE doc_id = ?", (family, doc_id))

    def delete_document(self, doc_id: str) -> bool:
        with self._conn() as c:
            n = c.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,)).rowcount
            self._gc_labels(c)
        return bool(n)

    @staticmethod
    def _gc_labels(c: sqlite3.Connection) -> None:
        c.execute("DELETE FROM labels WHERE label_id NOT IN (SELECT DISTINCT label_id FROM occurrences)")

    # ---- vectors ---------------------------------------------------------------------
    def labels_missing_vectors(self, embedder_name: str) -> List[Tuple[int, str]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT label_id, text FROM labels WHERE embedder IS NOT ? OR vector IS NULL", (embedder_name,)
            ).fetchall()
        return [(r["label_id"], r["text"]) for r in rows]

    def save_vectors(self, embedder_name: str, ids: Iterable[int], vectors: np.ndarray) -> None:
        with self._conn() as c:
            c.executemany(
                "UPDATE labels SET embedder = ?, vector = ? WHERE label_id = ?",
                [(embedder_name, np.asarray(v, dtype=np.float32).tobytes(), i) for i, v in zip(ids, vectors)],
            )

    def label_matrix(self, embedder_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """(label_ids, matrix) of every embedded label; cached until the database changes."""
        with self._conn() as c:
            fingerprint = c.execute("SELECT COUNT(*), COALESCE(MAX(label_id),0), COUNT(vector) FROM labels").fetchone()
            key = (embedder_name, tuple(fingerprint))
            if self._matrix and self._matrix[0] == key:
                return self._matrix[1], self._matrix[2]
            rows = c.execute("SELECT label_id, vector FROM labels WHERE embedder = ? AND vector IS NOT NULL", (embedder_name,)).fetchall()
        if not rows:
            result = (np.zeros(0, dtype=np.int64), np.zeros((0, 1), dtype=np.float32))
        else:
            result = (np.array([r["label_id"] for r in rows], dtype=np.int64),
                      np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows]))
        self._matrix = (key, result[0], result[1])
        return result

    # ---- queries ---------------------------------------------------------------------
    def occurrences_for(self, label_ids: List[int], exclude_docs: Iterable[str] = ()) -> List[Dict[str, Any]]:
        if not label_ids:
            return []
        marks = ",".join("?" * len(label_ids))
        sql = (f"SELECT o.*, d.family, d.filename, d.builtin FROM occurrences o JOIN documents d USING (doc_id) "
               f"WHERE o.label_id IN ({marks})")
        params: List[Any] = list(label_ids)
        excl = list(exclude_docs)
        if excl:
            sql += f" AND o.doc_id NOT IN ({','.join('?' * len(excl))})"
            params += excl
        with self._conn() as c:
            return [self._decode(dict(r)) for r in c.execute(sql, params).fetchall()]

    def document_occurrences(self, exclude_docs: Iterable[str] = (), include_builtin: bool = False) -> List[Dict[str, Any]]:
        """Light projection (doc, label, concept) used by the classifier."""
        sql = ("SELECT o.doc_id, o.label_id, o.concept, d.family, d.n_widgets, d.is_acroform, d.n_pages "
               "FROM occurrences o JOIN documents d USING (doc_id) WHERE (? OR d.builtin = 0)")
        params: List[Any] = [int(include_builtin)]
        excl = list(exclude_docs)
        if excl:
            sql += f" AND o.doc_id NOT IN ({','.join('?' * len(excl))})"
            params += excl
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def update_concepts(self, updates: List[Tuple[str, str, float, int]]) -> None:
        """updates: (concept, source, score, occurrence_id)."""
        with self._conn() as c:
            c.executemany("UPDATE occurrences SET concept = ?, concept_source = ?, concept_score = ? WHERE id = ?", updates)

    def clear_propagated(self) -> None:
        with self._conn() as c:
            c.execute("UPDATE occurrences SET concept = NULL, concept_source = '', concept_score = 0 WHERE concept_source = 'propagated'")

    def unlabeled_occurrences(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT id, label_id FROM occurrences WHERE concept IS NULL AND field_type NOT IN ('CheckBox','RadioButton')"
            ).fetchall()]

    def concept_labels(self) -> List[Dict[str, Any]]:
        """Distinct (label, concept) pairs with a trusted source (synonyms or builtin)."""
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT label_id, concept, MAX(concept_score) AS score FROM occurrences "
                "WHERE concept IS NOT NULL AND concept_source != 'propagated' GROUP BY label_id, concept"
            ).fetchall()]

    @staticmethod
    def _decode(row: Dict[str, Any]) -> Dict[str, Any]:
        row["rect"] = json.loads(row.get("rect") or "[]")
        row["context"] = json.loads(row.get("context") or "{}")
        return row
