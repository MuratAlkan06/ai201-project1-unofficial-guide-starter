# Decision Log

## ADR-001: Embedding model, vector store, and top-k
**Status:** Accepted (2026-06-10)
**Context:** Course RAG over 15 r/SJSU threads (< 1 MB, a few hundred chunks), CPU laptop, Python 3.13, free/local tooling, graded on clarity and reproducibility.
**Options considered:** Embedding — all-MiniLM-L6-v2 vs all-mpnet-base-v2 vs bge-small-en-v1.5. Store — numpy/sklearn cosine vs FAISS vs ChromaDB. Top-k — 3 vs 5 vs 8-10.
**Decision:** all-MiniLM-L6-v2 embeddings; ChromaDB persistent local collection; top_k=5 exposed as a tunable parameter. No new dependencies (sentence-transformers==3.4.1, chromadb>=0.6.0 already pinned).
**Addendum (risk critique, same date):** the collection MUST be created with hnsw:space="cosine" (Chroma defaults to L2; the space cannot be changed after creation), and a minimum-similarity refusal floor gates retrieval — below it the system answers "the corpus doesn't cover this" instead of summarizing irrelevant chunks. Floor value is calibrated empirically at M4 (not a design-time constant).
**Consequences:** fastest/smallest local setup; embeddings cached for reproducible grading; free source-attribution metadata via Chroma; multi-perspective k suited to threaded discussion. ChromaDB is the complexity ceiling — no FAISS/ANN at this scale.
**Revisit triggers:** corpus > ~10k chunks (ANN); model-attributable retrieval misses on slang/nicknames (trial bge-small-en-v1.5); chunks approaching 256 word-pieces (longer-context model or lower k); non-English content (multilingual model).

## ADR-002: Comment-aware chunking with vertical context anchoring
**Status:** Accepted (2026-06-10, ratified at M1 freeze)
**Context:** Corpus is comment-structured r/SJSU threads with a bimodal comment-length distribution (40-120-word substantive opinions vs sub-25-word one-liners) and occasional oversized structured post bodies (kighem.txt ~1,300 words). High-value answers are short and lose their professor/course anchor when separated from thread title or parent comment.
**Options considered:** (1) fixed-size sliding window (~200 wp / 40 overlap) — slices mid-opinion, rejected; (2) pure per-comment chunking — emits noise one-liners, leaves oversized bodies unsplit; (3) hybrid.
**Decision:** Hybrid: one chunk per comment; replies under ~15 word-pieces merge into their parent chunk; oversized post bodies split on existing markdown headers with section-label echo; every chunk prefixed with thread title (+ parent snippet for replies); ~200 word-piece ceiling (MiniLM truncates at 256); header fields routed to Chroma metadata, never embedded.
**Consequences:** self-contained attributable chunks; high-value one-liners survive with course/professor context; uneven chunk sizes by design; comment score metadata captured but unused (deferred re-rank signal).
**Open at M3:** title-prefix compaction for very long titles (truncate vs compact — measure budget pressure first).
**Resolved at M3 (2026-06-10):** title prefix is trimmed to 40 word-pieces with a trailing ellipsis (`ingest.py: TITLE_PREFIX_MAX_WP`); measured across the corpus, only `kighem.txt`'s 43-wp title exceeds the cap — all 14 other titles embed in full. Word-pieces are counted with the actual `all-MiniLM-L6-v2` tokenizer, not an approximation. Corpus-wide result: 283 chunks, max 192 wp, 0 violations of the 200-wp ceiling.
