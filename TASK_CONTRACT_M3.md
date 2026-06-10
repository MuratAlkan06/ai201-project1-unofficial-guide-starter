# Task Contract — Phase 3 / Milestone 3 (Ingestion + Chunking)

## Objective
Implement stages 1–2 of the architecture in `planning.md`: a structured parser
for the `documents/*.txt` thread format and the comment-aware chunker specified
by the Chunking Strategy section and ADR-002. Output is chunk objects ready for
M4 embedding (text with anchoring prefix + Chroma-ready metadata).

## Frozen design inputs
- planning.md **Chunking Strategy** + **Architecture** (stages 1–2) + **AI Tool
  Plan / Milestone 3** (verification items a–e).
- **ADR-002** (accepted 2026-06-10): one chunk per comment; replies under ~15
  word-pieces merge into their parent chunk; oversized post bodies split on
  existing markdown headers with section-label echo; every chunk prefixed with
  thread title (+ parent snippet for replies); ~200 word-piece ceiling
  (MiniLM truncates at 256); header fields routed to metadata, never embedded.
- **ADR-001**: word-pieces are counted with the actual `all-MiniLM-L6-v2`
  tokenizer (via `transformers`, already a sentence-transformers dependency).

## In scope
- `ingest.py`: `parse_document()` → (metadata dict, post body, nested comment
  tree); `chunk_document()` → list of chunks, each
  `{id, text (title-prefixed), metadata{title, url, post_id, date, kind,
  author, score, …}}`; `chunk_corpus()` over `documents/`; a `__main__` stats
  report (chunk counts, max word-pieces, budget violations).
- `test_ingest.py`: stdlib `unittest` suite encoding AI-Tool-Plan verification
  items (a)–(e). No new dependencies.
- Resolving ADR-002's open item (long-title prefix compaction) and recording
  the outcome in `DECISIONS.md`.

## Out of scope
- Embedding, ChromaDB indexing, retrieval, refusal floor (M4).
- Generation, prompts, UI (M5).
- Any edit to `documents/*.txt`, `collect_documents.py`, or M1/M2 contracts.

## Constraints
- Use `.venv/bin/python` (Python 3.13). No new pip dependencies.
- Budget is a hard ceiling: no emitted chunk may exceed 200 word-pieces of
  embedded text (title prefix and parent snippet counted inside the budget).
- Metadata values must be Chroma-compatible primitives (str/int/float/bool).
- The source banner (`=====`, `TITLE:`, `URL:` lines) and comment delimiters
  (`[COMMENT | …]`) must never appear in embedded text.

## Acceptance criteria (= AI Tool Plan M3 verification, made executable)
- (a) On `1bwuij.txt`, the `"DONT TAKE 187 WITH GAO"` reply is merged into the
  CmpE187/Gao parent chunk — never emitted alone.
- (b) On `kighem.txt`, the ~1,300-word post body produces multiple chunks, each
  ≤200 word-pieces, each split-continuation carrying its section label.
- (c) Sample chunks carry the thread-title prefix in embedded text; `TITLE`/
  `URL` live in metadata; the URL and banner markup never appear in embedded
  text.
- (d) Stats report prints total chunk count; zero chunks exceed the word-piece
  budget across all 15 files.
- (e) The `kighem.txt` lines 143–147 reply chunk ("his class is easier than
  most…") carries Fabio / CS 174 parent context in its embedded text.
- Noise rule: pure-noise short top-level comments (e.g. "🐐🐐🐐🐐thanks!!") are
  dropped, not indexed.

## Verification targets
- `.venv/bin/python -m unittest -v test_ingest` → all tests pass.
- `.venv/bin/python ingest.py` → stats report, 0 budget violations.

## Required artifacts
- `ingest.py`, `test_ingest.py`, this contract, DECISIONS.md update,
  github-workflow scaffold (issue → branch → draft PR).

## Next handoff
- M4: embed chunks with `all-MiniLM-L6-v2`, upsert to persistent ChromaDB
  collection created with `hnsw:space="cosine"`, `retrieve(query, top_k=5)`,
  refusal-floor calibration against the 6 eval questions + out-of-corpus probe.
