# Task Contract — Phase 2 / Milestone 2 (Pipeline Design)

## Objective
Complete the design half of `planning.md` — Chunking Strategy, Retrieval Approach,
Architecture, AI Tool Plan, Anticipated Challenges — so M3-M5 implementation can
proceed against a frozen spec.

## Session ownership (parallel-work guard)
- Another session owns ALL M1 files until it reports M1 done: `planning.md`,
  `collect_documents.py`, `documents/`, `requirements.txt`, logs, `raw_data/`.
- Until M1 freeze is confirmed, this session creates NEW files only and holds
  drafts in-conversation. No edits to M1-owned files. No git operations.

## Frozen design inputs
- **ADR-001** (accepted 2026-06-10): embedding `all-MiniLM-L6-v2` via
  sentence-transformers; vector store ChromaDB persistent local collection with
  source metadata (thread id, title, URL); `top_k = 5` exposed as a tunable
  parameter. No new dependencies (`sentence-transformers==3.4.1`,
  `chromadb>=0.6.0` already pinned).

## In scope
- `planning.md` Retrieval Approach section (paste ADR-001 draft) — AFTER M1 freeze.
- `planning.md` Chunking Strategy — chunk size/overlap **TBD pending corpus
  freeze**; must be justified against the final committed documents (thread
  structure: metadata header + post body + nested comments).
- `planning.md` Architecture diagram (Mermaid, 5 labeled stages).
- `planning.md` AI Tool Plan (M3/M4/M5 entries with input -> output -> verification).
- `planning.md` Anticipated Challenges (>=2 specific risks; seeded from the
  risk-qa-architect critique).

## Out of scope
- Any pipeline code (chunking, embedding, retrieval, generation) — that is M3+.
- Edits to `collect_documents.py`, `documents/`, or M1 planning sections.
- Any commit/push/branch without a github-workflow APPROVE.

## Acceptance criteria
- `planning.md` has no empty template sections; chunk size/overlap carry
  corpus-specific reasoning (not generic defaults).
- Retrieval Approach matches ADR-001 exactly; no dependency drift vs
  `requirements.txt`.
- Risk critique findings are addressed in the design or explicitly accepted.

## Verification targets
- grep `planning.md` for unfilled template markers (`**Chunk size:**` followed by
  blank, empty table cells) -> none.
- Cross-check ADR-001 model/store/k values against `planning.md` and
  `requirements.txt` -> consistent.

## Open questions / blockers
- **BLOCKER:** M1 freeze (other session in progress) gates all planning.md edits.
- Chunk size/overlap values await the final corpus.

## Next handoff
- M3 slice: ingestion + chunking implementation (github-workflow scaffold first:
  issue -> branch -> draft PR).
