# Task Contract — Phase 1 / Milestone 1 (Document Collection)

## Objective
Collect a curated corpus of r/SJSU Reddit threads about CS/SWE professors and
courses, write each kept thread as one committed `documents/*.txt`, and fill ONLY
the M1 sections of `planning.md` (Domain, Documents, Evaluation Plan).

## In scope
- `collect_documents.py`: cache-first PullPush collector (already drafted).
- `documents/*.txt`: one file per curated thread (12-15 target, >=10 floor).
- Curation: each kept thread >=5 substantive fetched comments; topic coverage.
- Skim notes (report-only).
- >=5 verified eval questions (>=2 supporting passages each).
- `planning.md`: Domain, Documents table, Evaluation Plan (marked DRAFT).
- `requirements.txt`: add `requests` (used directly).

## Out of scope
- Chunking, Retrieval, Architecture, AI Tool Plan, Anticipated Challenges.
- Any git commit/push. Any edit to `.env`.
- Phase 2/3 pipeline code.

## Constraints
- Use `.venv/bin/python`.
- Politeness: 15s timeout, 1 retry, ~1s sleep between live calls.
- Cache-first: never re-hit API for cached requests; `raw_data/` stays gitignored.
- Count FETCHED comments, never `num_comments`; exclude AutoModerator/bots.
- No recency filter (archive ends ~May 2025). Dedupe threads by post id.
- Committed corpus < ~1 MB total.

## Assumptions
- Existing `collect_documents.py` and `raw_data/` cache are the frozen design;
  the prior run stopped before completing terms / writing docs.
- `requests` present transitively; pin it explicitly.

## Acceptance criteria
- `documents/` contains exactly the curated set (>=10, target 12-15) `.txt` files,
  each with the metadata header + post body + nested comments, each >=5 substantive.
- Coverage spans multiple courses/professors/difficulty/workload/GE.
- `planning.md` M1 sections complete; Evaluation Plan has >=5 verified questions.
- `requirements.txt` lists `requests`.

## Verification targets
- `py_compile collect_documents.py`.
- Re-run shows cache hits (idempotent) on second invocation.
- grep each eval question -> >=2 supporting passages across documents.
- `du` of documents/ < ~1 MB.

## Required artifacts
- `documents/*.txt`, updated `planning.md`, updated `requirements.txt`.

## Open questions
- None blocking; fallbacks (r/SanJoseState, WebSearch) defined if floor missed.

## Next handoff
- Phase 2: Chunking / Retrieval / Architecture sections of planning.md.
