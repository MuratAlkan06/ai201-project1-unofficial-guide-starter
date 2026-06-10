# Task Contract — Phase 5 / Milestone 5 (Generation + Interface)

## Objective
Implement stage 5 of the architecture in `planning.md`: grounded Groq
generation over the M4 retrieved chunks (answer only from chunks, surface
disagreement, cite source URLs, emit the refusal string when the floor gate
fires) plus a minimal Gradio query UI.

## Frozen design inputs
- planning.md **Architecture** (stage 5) + **AI Tool Plan / Milestone 5**
  (verification items a–c) + **Anticipated Challenges** contradiction policy
  (surface disagreement, don't resolve).
- **ADR-001** resolution (M4): refusal floor 0.52; the documented leak class
  (unknown professor asked in the eval questions' register, sim 0.596) cannot
  be rejected by any floor — the grounded prompt is the designated backstop.
- **ADR-003**: `retrieve()` returns MMR-diversified top-5; `results[0]` always
  carries the best similarity, so the floor gate is unchanged.
- M4 chunk results: `{id, text, metadata{title, url, post_id, ...}, similarity}`.

## In scope
- `generation.py`: Groq chat completion (`llama-3.3-70b-versatile`, current
  production model per Groq docs) behind `generate_answer(query, top_k=5)`;
  refusal-floor gate **before** any API call; numbered-excerpt context format
  with per-chunk source metadata; system prompt enforcing (i) answer only
  from excerpts, (ii) surface disagreement, (iii) cite sources as [n] mapped
  to thread URLs, (iv) a `NOT_IN_CORPUS` sentinel the model must emit when
  the excerpts don't discuss the asked professor/course (leak-class
  backstop), mapped back to the refusal string; a `__main__` verification
  report mirroring `retrieval.py` (eval questions through the full pipeline,
  contradiction question, probes, leak probe).
- `app.py`: minimal Gradio Blocks UI — query box, answer markdown, sources,
  retrieved-chunk accordion, eval questions as examples.
- `test_generation.py`: stdlib `unittest`; Groq client mocked (no key, no
  network): floor-gate refusal makes **zero** API calls; prompt construction
  contains chunk texts + grounding instructions; sentinel maps to refusal;
  cited source URLs come only from retrieved chunks.
- `requirements.txt`: uncomment `gradio>=6.9.0` (planned M5 dependency).
- `DECISIONS.md`: ADR-004 (Groq model, Gradio over Streamlit, sentinel
  backstop, context format).

## Out of scope
- README.md submission sections + Evaluation Report (final submission phase).
- Any change to `ingest.py` / `retrieval.py` behavior, floor, or chunking.
- Streaming responses, chat history, deployment.

## Constraints
- Use `.venv/bin/python` (Python 3.13). New dependency limited to `gradio`
  (pre-approved in requirements.txt for M5); `groq==0.15.0` already pinned.
- The refusal path must never call the Groq API (cost + determinism).
- Refusal string contains the planning.md phrase "the corpus doesn't cover this".
- Model id, temperature, and `top_k` stay one-line tunable constants.
- `.env` is never committed; `GROQ_API_KEY` read via python-dotenv.

## Acceptance criteria (= AI Tool Plan M5 verification, made executable)
- (a) Spot-check ≥3 answers — each cited URL's file actually contains the
  claim (e.g. Q1 Atta answer cites `2ljx6r.txt`'s URL).
- (b) The CS 146 contradiction question reports both sides ("tough" vs "146
  got easier... Taylor didn't teach it") rather than picking one.
- (c) The out-of-corpus probe returns the refusal string, not a fabricated
  summary; the M4 leak probe is refused by the grounded prompt (sentinel).
- Unit suite green with zero network/API calls.

## Known blocker at authoring time
`.env` holds a placeholder `GROQ_API_KEY`, so (a), (b), and the leak-probe
half of (c) cannot be executed live in this phase session. They are encoded
in the `generation.py __main__` report: paste a real key, run
`.venv/bin/python generation.py`, attach output to the PR, then merge.
The floor-gate half of (c) and the unit suite are verified now (no API).

## Verification targets
- `.venv/bin/python -m unittest -v test_generation` → all tests pass, no network.
- `.venv/bin/python -m unittest discover -v` → M3 + M4 suites still green.
- `.venv/bin/python generation.py --offline` → floor-gate probes refused
  without any API call.
- `.venv/bin/python generation.py` (real key required) → full live report:
  items (a)–(c).

## Required artifacts
- `generation.py`, `app.py`, `test_generation.py`, this contract,
  requirements.txt update, DECISIONS.md ADR-004, github-workflow scaffold
  (branch → draft PR; Issues disabled on this fork).

## Next handoff
- Final submission phase: README.md (Domain → AI Usage), Evaluation Report
  table from the live `generation.py` run, failure-case analysis (candidates
  already documented: ADR-003 deviations, the M4 leak class).
