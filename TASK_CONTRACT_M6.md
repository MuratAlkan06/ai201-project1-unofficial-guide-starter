# Task Contract — Phase 6 / Milestone 6 (Final Submission Docs)

## Objective
Produce the final-submission documentation: a **live evaluation report** of the
already-frozen RAG pipeline and a **complete `README.md`** covering every item on
the course submission checklist. This is a **docs-only** milestone — no change to
any `.py` file, `requirements.txt`, or pipeline behavior. The pipeline (ingestion,
chunking, embedding, retrieval, generation, UI) is frozen exactly as ratified in
ADR-001 through ADR-005.

## Frozen design inputs
- `planning.md` **Evaluation Plan** (the 5 finalized test questions + expected
  answers; the contradiction earmark) and all other sections (Domain, Documents,
  Chunking Strategy, Retrieval Approach, Architecture, AI Tool Plan).
- **ADR-001 → ADR-005** (`DECISIONS.md`): embedding/store/top-k + refusal floor
  0.52; comment-aware chunking; MMR diversity re-rank (λ=0.7); Groq grounded
  generation + `NOT_IN_CORPUS` sentinel + programmatic `[n]→URL` mapping + Gradio
  UI; the **M5 (b) waiver** reclassifying the CS 146 contradiction as the M6
  failure case.
- `TASK_CONTRACT_M5.md` including its **Amendment (2026-06-10)** (the (b) waiver
  and verified root cause).
- The course submission checklist (the `README.md` template's required sections).

## In scope
- This contract (`TASK_CONTRACT_M6.md`).
- **One** live evaluation run: `.venv/bin/python generation.py` with a real
  `GROQ_API_KEY`, captured to a log, covering the 5 eval questions, the
  contradiction question, the floor-gate refusal probes, and the leak probe.
- `README.md` **fully completed** — every template guiding-comment replaced with
  substantive content drawn from real runs/corpus, with all 13 checklist items
  (Domain → AI Usage, plus the Evaluation Report and Failure Case Analysis).

## Out of scope (explicit non-goals)
- **Demo video** — explicitly excluded by user decision (2026-06-10). Recording
  the walkthrough remains a manual user step after this milestone.
- Any code change: no edit to `collect_documents.py`, `ingest.py`, `retrieval.py`,
  `generation.py`, `app.py`, the test files, or `requirements.txt`.
- Any change to floor / `top_k` / MMR λ / chunking (would re-open ADR-005's waiver
  and is barred here).
- Stretch features, deployment, re-chunking, re-calibration.

## Constraints
- **Docs-only diff**: `git diff --stat` against `main` shows only `.md` files (this
  contract added, `README.md` completed) — zero `.py`/`.txt` changes.
- A **single** live `generation.py` run, plus **at most 2–3** ad-hoc retrieval-only
  queries (`retrieval.py` / a small `-c` invocation, no API cost) if needed to
  capture top-5 chunks + similarities for the retrieval-results section. No second
  paid run unless the first fails.
- **Honest accuracy judgments.** The CS 146 contradiction must be reported as a
  *failure* (one-sided answer), not smoothed over. If the live run surfaces a
  second failure, it is documented too.
- **All numbers are real**: every similarity, count, chunk total, rank, and quoted
  response line is copied from an actual run or the corpus — nothing fabricated.
- Sole-author commits — **no `Co-Authored-By` trailer** anywhere (commits or PR).
- `.env` is never committed and `GROQ_API_KEY` is never printed or pasted into any
  artifact, log excerpt, README, or PR comment.

## Acceptance criteria
- Every README item on the course submission checklist is present and substantive
  (no one-liners, no leftover template guiding comments):
  1. Domain summary + document sources with specific thread names/URLs (≥10).
  2. Ingestion pipeline description (collect → clean → structure).
  3. Chunking strategy + reasoning (comment-aware; size/overlap; why it fits Reddit).
  4. ≥5 labeled sample chunks, each with its source document name.
  5. Embedding model (all-MiniLM-L6-v2) + production tradeoff reflection.
  6. Retrieval test results: ≥3 queries with top chunks + similarities; ≥2 with a
     written relevance explanation.
  7. How grounded generation is enforced (system-prompt rules, `NOT_IN_CORPUS`
     sentinel, refusal floor 0.52 *before* any API call, programmatic `[n]→URL`).
  8. ≥2 example responses with visible source attribution, plus one out-of-scope
     query showing the refusal response.
  9. Query interface description (fields) + one complete sample interaction transcript.
  10. Evaluation report: all 5 planning.md questions — question, expected answer,
      actual response (live run), chunks retrieved, honest judgment.
  11. ≥1 honest failure case with pipeline-specific explanation (the CS 146
      contradiction; chunks `co57ff2`/`co4alo2` in `2u15xl` never co-retrieve;
      reference ADR-005). Any second failure surfaced live is documented too.
  12. Spec reflection: one specific way `planning.md` helped + one specific
      divergence and why.
  13. AI usage: ≥2 specific, true instances mined from `DECISIONS.md`/git history.
- The embedding model is named in the README (spec requirement).

## Verification targets
- `git diff --stat` (vs `main`) → only `.md` files changed.
- `env -u GROQ_API_KEY .venv/bin/python -m unittest discover` → **31 OK** (the docs
  slice broke nothing; the suite is unchanged).
- README checklist sweep: every item above present and substantive.
- Traceability spot-check: every sample chunk and every quoted response line in the
  README appears in the corpus (`documents/*.txt`) or the live run log.

## Required artifacts
- `TASK_CONTRACT_M6.md` (this file).
- `/tmp/m6_eval_run.txt` — full captured output of the single live `generation.py`
  run (working evidence; not committed).
- `README.md` — fully completed per the checklist above.
- Draft PR `feat/phase-6-evaluation-readme → main` with scope/out-of-scope body;
  evidence excerpt added as a PR comment after tests pass.

## Open questions
None. The (b) waiver is settled (ADR-005); the demo video is settled out of scope.

## Next handoff
- **User** records the demo video (manual step, deliberately out of this contract).
- **User** submits to the course portal (this branch's PR + README + demo video).
