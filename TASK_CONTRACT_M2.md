# Task Contract — Phase 2 / Milestone 2 (Pipeline Design) — v2 (post risk critique)

## Objective
Complete the design half of `planning.md` — Chunking Strategy, Retrieval Approach,
Architecture, AI Tool Plan, Anticipated Challenges — so M3-M5 implementation can
proceed against a frozen spec.

## Session ownership (parallel-work guard)
- Another session owns ALL M1 files until it reports M1 done: `planning.md`,
  `collect_documents.py`, `documents/`, `requirements.txt`, logs, `raw_data/`.
- Until M1 completion is confirmed, this session creates/edits NEW files only
  (this contract) and holds planning.md drafts in-conversation. No git operations.

## Frozen design inputs
- **ADR-001** (accepted 2026-06-10): `all-MiniLM-L6-v2` embeddings via
  sentence-transformers; ChromaDB persistent local collection; `top_k = 5`
  tunable. No new dependencies (`sentence-transformers==3.4.1`,
  `chromadb>=0.6.0`, `groq==0.15.0` already pinned).
- **ADR-001 addendum (required by risk critique, to be ratified at freeze):**
  - Collection MUST be created with `hnsw:space="cosine"` (Chroma defaults to
    L2; the space cannot be changed after creation).
  - A minimum-similarity floor MUST gate retrieval: below it, the system
    answers "the corpus doesn't cover this" instead of summarizing the k
    least-irrelevant chunks (refusal > hallucination for out-of-corpus
    professors/courses).

## Design requirements (from risk critique — Blockers/High)
1. **Question-context anchoring:** every chunk's embedded text is prefixed with
   the thread title (+ post-question context), so an answer chunk ("the work
   won't be difficult") never loses which professor/course it refers to.
2. **Structured parsing, not naive splitting:** strip the `=====` banner;
   route `TITLE/URL/post_id` header fields into Chroma METADATA (never into
   embedded text); chunk only post body + comment bodies.
3. **Short-comment rule:** minimum-content threshold at chunk time; merge very
   short replies into their parent comment so high-value one-liners
   ("DONT TAKE 187 WITH GAO") keep course/professor context.
4. **Contradiction policy:** generation prompt must surface disagreement among
   retrieved chunks rather than resolve it.
5. **Word-piece budget:** chunk size expressed in tokens, target ~200 word-pieces
   (MiniLM silently truncates at 256).

## Corpus status (corrected)
- The corpus is pinned (`CURATED_POST_IDS` in collect_documents.py; 15 files in
  documents/). Chunking strategy SHOULD be drafted now against the real files;
  it is FINALIZED when the other session declares M1 done (confirming no
  curation changes).

## In scope
- planning.md sections (pasted AFTER M1 done): Chunking Strategy, Retrieval
  Approach (ADR-001 draft), Architecture (Mermaid, 5 labeled stages),
  AI Tool Plan (M3/M4/M5: input -> output -> verification), Anticipated
  Challenges (3 entries drafted by risk critique, ready to paste).

## Out of scope
- Any pipeline code (M3+). Edits to M1-owned files before M1 done.
- Any commit/push/branch without a github-workflow APPROVE.

## Acceptance criteria (strengthened per critique)
- planning.md has no empty template sections; Chunking Strategy names the
  thread structure and cites a concrete corpus example (not generic defaults);
  reviewer sign-off is the gate, not grep alone.
- Every chunk carries thread-title/question context in its embedded text (spec
  stated in planning.md; verified at M3).
- Generation cites source URL(s); spot-check of >=3 answers confirms each cited
  URL contains the claim (verified at M5).
- For each of the 5 eval questions: >=1 supporting passage survives chunking in
  a single retrievable chunk and surfaces at top_k=5 (verified at M4).
- Retrieval Approach matches ADR-001 + addendum exactly; no dependency drift.

## Open questions / blockers
- **BLOCKER:** planning.md file contention — other session mid-M1 (Domain,
  Documents filled; Evaluation Plan pending). Gates the paste, not the drafting.
- Final chunk size/overlap numbers: draft now, ratify at M1-done confirmation.

## Next handoff
- M3 slice: ingestion + chunking implementation (github-workflow scaffold first:
  issue -> branch -> draft PR).
