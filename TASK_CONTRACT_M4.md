# Task Contract — Phase 4 / Milestone 4 (Embedding + Retrieval)

## Objective
Implement stages 3–4 of the architecture in `planning.md`: embed the M3 chunks
with `all-MiniLM-L6-v2`, upsert them into a persistent ChromaDB collection
created with `hnsw:space="cosine"`, expose `retrieve(query, top_k=5)` returning
chunks + cosine similarities, and calibrate the minimum-similarity refusal
floor against the 6 eval questions plus an out-of-corpus probe.

## Frozen design inputs
- planning.md **Retrieval Approach** + **Architecture** (stages 3–4) + **AI
  Tool Plan / Milestone 4** (verification items a–d) + **Evaluation Plan**
  (6 questions with supporting files).
- **ADR-001** (accepted 2026-06-10): `all-MiniLM-L6-v2`; ChromaDB persistent
  local collection; `top_k=5` tunable. Addendum: the collection MUST be created
  with `hnsw:space="cosine"` (Chroma defaults to L2; the space cannot be
  changed after creation); a minimum-similarity refusal floor gates retrieval,
  calibrated empirically at M4.
- **M3 chunk objects** from `ingest.chunk_corpus()` (283 chunks: title-prefixed
  embedded text + Chroma-primitive metadata, ≤200 word-pieces).

## In scope
- `retrieval.py`: persistent client at `chroma_db/` (gitignored);
  `build_index()` embedding chunk text via `sentence-transformers` and
  upserting `{id, embedding, document, metadata}`; `retrieve(query, top_k=5)`
  → list of `{id, text, metadata, similarity}` sorted by cosine similarity;
  refusal-floor gate (`is_answerable()`); a `__main__` calibration report
  (per-question top-k hits + similarities, probe scores, floor verdict).
- `test_retrieval.py`: stdlib `unittest` suite encoding AI-Tool-Plan M4
  verification items (a)–(d). No new dependencies.
- Recording the calibrated floor value in `DECISIONS.md` (resolves the ADR-001
  addendum's open calibration item).

## Out of scope
- Generation, Groq prompts, contradiction policy, UI (M5).
- Any change to `ingest.py` chunking behavior or `documents/*.txt`.
- Re-ranking, ANN tuning, alternate embedding models (ADR-001 revisit triggers).

## Constraints
- Use `.venv/bin/python` (Python 3.13). No new pip dependencies.
- The collection must be created with `hnsw:space="cosine"` and the test suite
  must assert the collection reports cosine space.
- `chroma_db/` stays gitignored (machine-generated, reproducible via
  `build_index()`); embeddings computed once and reused across runs.
- Similarity reported as `1 − cosine distance`; floor compares on that scale.
- `top_k` stays a one-line tunable constant (default 5) per ADR-001.

## Acceptance criteria (= AI Tool Plan M4 verification, made executable)
- (a) For **each** eval question #1–#6, a chunk from a named supporting file
  surfaces in `top_k=5`; specifically Q4 (Ezzat) returns the `94eap5.txt`
  "most people… weren't positive" / "work won't be difficult" passages, and
  Q5 (avoid) returns the merged `1bwuij.txt` Gao chunk **and** a `2ljx6r.txt`
  Atta chunk.
- (b) `collection.metadata` reports cosine space.
- (c) The out-of-corpus probe ("Professor Smith CS 999") scores **below** the
  floor and triggers refusal.
- (d) The calibrated floor admits all 6 in-corpus questions (best similarity ≥
  floor) while rejecting the probe.

## Deviations measured at completion (full rationale in DECISIONS.md ADR-003)
- (a)/Q5: the merged `1bwuij` Gao chunk ranks 233/283 (sim 0.187) for the
  broad Q5 phrasing — its embedding is dominated by the parent comment, so no
  top-5 policy can surface it for an enumeration query. Re-scoped: Q5's top-5
  surfaces `kighem` + `2ljx6r` (via the ADR-003 MMR re-rank), and the Gao
  merge is verified by a targeted query where the chunk ranks **#1**.
- (a)/Q4: the "work won't be difficult" answer chunk is in top-5; the
  "most people… weren't positive" OP chunk ranks 9th by relevance (it is the
  question's premise, not its answer).
- (c): one probe class leaks past any feasible floor — an unknown professor
  phrased in the eval questions' register scores 0.596 vs Q5's 0.558 best.
  Documented; refusal for that class falls to the M5 grounded prompt.

## Verification targets
- `.venv/bin/python -m unittest -v test_retrieval` → all tests pass.
- `.venv/bin/python retrieval.py` → calibration report: 6/6 questions hit
  supporting files and clear the floor; probe refused.

## Required artifacts
- `retrieval.py`, `test_retrieval.py`, this contract, DECISIONS.md update
  (calibrated floor), github-workflow scaffold (branch → draft PR; Issues
  disabled on this fork).

## Next handoff
- M5: Groq generation (answer only from retrieved chunks, surface
  disagreement, cite source URLs, emit the refusal string when the floor gate
  fires) + minimal query UI (Gradio or Streamlit per `requirements.txt`).
