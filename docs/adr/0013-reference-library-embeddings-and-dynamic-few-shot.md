# 0013: Reference Library, Embeddings, Form Classification & Dynamic Few-Shot

Add a reusable knowledge layer so the filling engine learns from previously seen forms and adapts to unknown ones, without sending reference documents to the LLM.

## Context & Problem
The engine (ADR-0001/0003/0005) resolves labels through a hand-curated dictionary (`field_dictionary.py`), deterministic regex rules and a per-chunk LLM pass. Every new form either hit those rules or fell to the LLM with no memory of how similar labels were resolved before. Knowledge was not reusable, not attributable to a source document, and did not scale with the number of forms seen.

## Decision
1. **Reuse, don't duplicate.** Widget analysis moved verbatim from `PDFAgent` to `form_analysis.py` (the agent delegates). Concepts come from `FillingValidator.score_field` over `FIELD_SYNONYMS` (the master model). The LLM call, provider selection, `FillingValidator` and the filling engine are unchanged.
2. **Reference library** (`backend/pdf_filling_agent/reference_library/`): `docs/referencias/[<familia>/]*.pdf` is the source of truth. `sync()` mirrors it into SQLite using SHA-256 change detection (add / update / remove / re-process). Each extracted field keeps label, section, page, rect, field type, neighbours, example value and the originating document. Instructions, sections and page structure are stored per document. Family = sub-folder, overridable by `docs/referencias/manifest.json`.
3. **Embeddings behind an interface** (`Embedder`). Default `HashingEmbedder`: local, deterministic, zero cost (word + char n-grams, Spanish stemming and a small business-term map). `EMBEDDING_PROVIDER=azure|openai` switches to real embeddings through the credentials already in `.env`. Vectors are tagged with the embedder name; changing embedder re-embeds from stored text without re-parsing any PDF.
4. **Vector store: numpy over SQLite, not FAISS/Chroma/Qdrant/pgvector.** Evaluated against cost, development ease, deployment ease and scale:

   | Option | Verdict |
   |---|---|
   | numpy + SQLite (chosen) | No new dependency or service, one file, trivial on Render. Labels are *deduplicated across documents*, so the matrix grows with distinct vocabulary (tens of thousands of rows for thousands of forms, tens of MB), where brute-force search takes milliseconds. |
   | FAISS | Native wheel to ship, no persistence/filtering of its own; pointless below ~10^5-10^6 vectors. |
   | Chroma / Qdrant | An extra process or service to run, secure and pay for. |
   | pgvector | Best long-term fit if the library moves into the existing Supabase/Neon PostgreSQL; requires the extension and a migration. Deferred. |

   `Store.label_matrix()` is the single seam; replacing it with FAISS or pgvector does not touch the classifier or few-shot builder.
5. **Embeddings are a signal, not the truth.** They only rank reference examples. Output still passes `FillingValidator` (negative zones, single-row, type guard) and collision arbitration. Concept labels are assigned conservatively (score >= 0.75, stricter than the 0.60 ADR-0003 floor; never to checkboxes/radios) because they become LLM examples.
6. **Classification** (`classifier.py`): per reference document, label soft-F1 (embedding) + master-concept Jaccard + structure similarity; aggregated per family; softmax gives the "86 % / 9 % / 5 %" shares. A form is *known* only if score >= `REFERENCE_CLASSIFY_MIN_SCORE` (0.30) and share >= `REFERENCE_CLASSIFY_MIN_SHARE` (0.60); otherwise it is *unknown* and uses general analysis + semantic search. File names are never used. New families need no code: add documents under a new folder.
7. **Dynamic few-shot** (`fewshot.py`): in `_fill_acroform`, only the fields the deterministic matcher did not resolve are searched; per field the best `REFERENCE_FEWSHOT_TOP_K` (5) distinct concepts above `REFERENCE_FEWSHOT_MIN_SIM` (0.55) are kept, capped at `REFERENCE_FEWSHOT_MAX` (20) per LLM chunk. Master-dictionary hits are excluded (already in the system prompt). The prompt receives one line per example, never a document.
8. **Operations**: `scripts/reference_library.py` (sync / add / remove / list / search / classify) and admin-only `/api/reference-library/*` endpoints (`require_admin`). `REFERENCE_LIBRARY_ENABLED=0` disables the layer; any failure degrades to the previous behaviour.

## Consequences
- Adding references is a file drop (or upload) and a `sync`; re-sync with no changes costs ~40 ms.
- The audit report gains `reference_library` (strategy, family, confidence, shares, few-shot count).
- Measured on the 5 seed forms (leave-one-out, other forms only): the same concept is recovered for 107 of 127 high-confidence fields (84 %). This measures consistency with the existing dictionary, not correctness against a human-labelled set.
- The local embedder is lexical: it connects "Identificación fiscal" to NIT but only partly "persona que representa legalmente" to "Representante legal". Real semantic quality needs `EMBEDDING_PROVIDER`.
- The database is a derived cache. On Render's ephemeral disk, references must live in the repository or a persistent disk; uploads through the API are lost on redeploy otherwise.
- Not covered yet: few-shot for flat (`_fill_visual`) and scanned (`_fill_vision`) modes, and Excel references. The project has no Excel analyzer today; a new extractor only has to return `ExtractedForm`.
- `*_mapping.json` files were evaluated as ground truth and rejected: the one inspected (Isagen) is an experimental overlay whose boxes do not correspond to the widgets' labels.
