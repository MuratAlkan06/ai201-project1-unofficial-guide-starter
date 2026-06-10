"""Milestone 5: grounded generation (architecture stage 5).

Passes the M4 retrieved chunks to a Groq chat completion with a prompt that
(i) answers ONLY from the retrieved excerpts, (ii) surfaces disagreement
between students instead of resolving it, (iii) cites excerpts as [n] which
are mapped deterministically back to thread URLs (the model never types a
URL, so it can never invent one), and (iv) emits a NOT_IN_CORPUS sentinel
when the excerpts don't discuss the asked professor/course -- the documented
backstop (ADR-001 resolution) for the leak class no similarity floor can
reject. The refusal-floor gate runs BEFORE any API call, so out-of-corpus
queries are refused for free.

Run the verification report (AI Tool Plan M5 verification (a)-(c)):

    .venv/bin/python generation.py --offline  # floor-gate probes only, no API
    .venv/bin/python generation.py            # full live report (needs GROQ_API_KEY)
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

import retrieval

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"  # current Groq production model (ADR-004)
TEMPERATURE = 0.2  # low: synthesis must stay close to the excerpts
MAX_TOKENS = 1024

# Sentinel the model must emit when the excerpts don't actually discuss the
# asked professor/course (rule 2 of the system prompt). Mapped to
# REFUSAL_MESSAGE before anything reaches the user.
NOT_IN_CORPUS = "NOT_IN_CORPUS"

# Refusal string per planning.md: must contain "the corpus doesn't cover this".
REFUSAL_MESSAGE = (
    "Sorry — the corpus doesn't cover this. None of the collected r/SJSU "
    "threads discuss it, and answering anyway would mean making something up. "
    "Try a question about the CS/SE courses, professors, or GE picks students "
    "actually posted about."
)

SYSTEM_PROMPT = f"""\
You are "The Unofficial Guide": you answer questions about SJSU CS/Software
Engineering courses and professors using ONLY the numbered student-discussion
excerpts provided with each question. The excerpts are candid Reddit comments
from r/SJSU -- opinions and experiences, not official facts.

Rules, in priority order:
1. Answer ONLY from the excerpts. Use only facts, opinions, and experiences
   stated in them. No outside knowledge, no guessing, and never invent a
   professor, course, grade policy, or event.
2. If the excerpts do not actually discuss the specific professor, course, or
   topic the user asked about -- even if they discuss similar ones -- reply
   with exactly {NOT_IN_CORPUS} and nothing else. Never substitute a
   similar-sounding professor or course for the one asked about.
3. Students contradict each other. When excerpts disagree, report both sides
   and attribute them ("one student calls it tough, another says it got
   easier..."); do not pick a winner or average the disagreement away.
4. Cite the excerpt number(s) supporting each claim, like [1] or [2][4]. Use
   only numbers that appear in the provided excerpts.
5. Keep the student framing ("students say", "one commenter warns") -- these
   are opinions, not verified facts.
6. Be concise: a few sentences or short bullets that synthesize the excerpts,
   not an essay.
"""


def format_context(results: list[dict]) -> str:
    """Number the retrieved chunks as [n] excerpts for the user message.

    The chunk text already opens with its 'Thread: <title>' anchoring prefix
    (ADR-002), so the header adds only what the text lacks: the excerpt
    number the model must cite, plus kind/author/score for attribution tone.
    """
    blocks = []
    for n, r in enumerate(results, 1):
        m = r["metadata"]
        blocks.append(
            f"[{n}] ({m['kind']} by {m['author']}, score {m['score']}, {m['date']})\n"
            f"{r['text']}"
        )
    return "\n\n".join(blocks)


def build_messages(query: str, results: list[dict]) -> list[dict]:
    user = (
        f"Student-discussion excerpts:\n\n{format_context(results)}\n\n"
        f"Question: {query}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def collect_sources(results: list[dict]) -> list[dict]:
    """Unique source threads in first-retrieved order, with their excerpt numbers.

    Citations map [n] -> thread URL deterministically here, so a cited URL is
    always one the retriever actually returned -- the model never writes URLs.
    """
    sources: dict[str, dict] = {}
    for n, r in enumerate(results, 1):
        m = r["metadata"]
        src = sources.setdefault(
            m["post_id"],
            {"post_id": m["post_id"], "title": m["title"], "url": m["url"], "excerpts": []},
        )
        src["excerpts"].append(n)
    return list(sources.values())


_groq_client = None


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _groq_client


def _complete(messages: list[dict]) -> str:
    """Single Groq chat completion; isolated so tests can stub it out."""
    response = get_groq_client().chat.completions.create(
        messages=messages,
        model=GROQ_MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content or ""


def generate_answer(query: str, top_k: int = retrieval.TOP_K, collection=None) -> dict:
    """Full stage-4 -> stage-5 pass for one query.

    Returns {query, refused, api_called, answer, sources, results,
    best_similarity}. The refusal floor is checked BEFORE any API call;
    the NOT_IN_CORPUS sentinel is checked after.
    """
    results = retrieval.retrieve(query, top_k=top_k, collection=collection)
    best = results[0]["similarity"] if results else 0.0

    if not retrieval.is_answerable(results):
        return {
            "query": query,
            "refused": True,
            "api_called": False,
            "answer": REFUSAL_MESSAGE,
            "sources": [],
            "results": results,
            "best_similarity": best,
        }

    answer = _complete(build_messages(query, results)).strip()
    refused = NOT_IN_CORPUS in answer
    return {
        "query": query,
        "refused": refused,
        "api_called": True,
        "answer": REFUSAL_MESSAGE if refused else answer,
        "sources": [] if refused else collect_sources(results),
        "results": results,
        "best_similarity": best,
    }


def format_sources_md(sources: list[dict]) -> str:
    return "\n".join(
        f"- [{s['title']}]({s['url']}) — excerpts {', '.join(f'[{n}]' for n in s['excerpts'])}"
        for s in sources
    )


# Contradiction question for AI Tool Plan M5 verification (b): 2u15xl.txt
# calls CS 146 "tough" while another student reports "146 got easier...
# Taylor didn't teach it". The answer must report both sides.
CONTRADICTION_QUESTION = "How hard is CS 146 really?"


def _print_answer(out: dict) -> None:
    print(f"   best={out['best_similarity']:.3f}  refused={out['refused']}")
    for line in out["answer"].splitlines():
        print(f"   | {line}")
    for s in out["sources"]:
        print(f"   src {s['post_id']:<8} excerpts {s['excerpts']}  {s['url']}")


def main() -> int:
    offline = "--offline" in sys.argv[1:]
    collection = retrieval.build_index()
    failures = []

    print(f"model={GROQ_MODEL!r}  floor={retrieval.REFUSAL_FLOOR}  top_k={retrieval.TOP_K}")

    print("\n=== Floor-gate probes (refused before any API call) ===")
    for probe in [retrieval.OUT_OF_CORPUS_PROBE, *retrieval.OFF_DOMAIN_PROBES]:
        out = generate_answer(probe, collection=collection)
        ok = out["refused"] and not out["api_called"]
        status = "ok" if ok else "FAIL"
        if not ok:
            failures.append(f"floor gate did not refuse: {probe!r}")
        print(f"[{status}] best={out['best_similarity']:.3f}  api_called={out['api_called']}  {probe!r}")

    if offline:
        print("\n--offline: skipping live Groq verification (a)-(c).")
        if failures:
            print("FAILURES:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("offline verdict: all floor-gate probes refused with zero API calls")
        return 0

    key = os.environ.get("GROQ_API_KEY", "")
    if not key.startswith("gsk_"):
        print(
            "\nGROQ_API_KEY in .env looks like a placeholder. Paste a real key"
            " (console.groq.com) and re-run: .venv/bin/python generation.py",
            file=sys.stderr,
        )
        return 2

    print("\n=== (a) Eval questions through the full pipeline (spot-check the citations) ===")
    for i, item in enumerate(retrieval.EVAL_QUESTIONS, 1):
        out = generate_answer(item["question"], collection=collection)
        if out["refused"]:
            failures.append(f"Q{i} refused: {item['question']!r}")
        print(f"\nQ{i} [{'FAIL' if out['refused'] else 'ok'}] {item['question']}")
        _print_answer(out)

    print(f"\n=== (b) Contradiction question (must report BOTH sides) ===")
    print(f"\n{CONTRADICTION_QUESTION}")
    out = generate_answer(CONTRADICTION_QUESTION, collection=collection)
    _print_answer(out)
    print("   ^ spot-check: 'tough' side AND the '146 got easier / Taylor' side both present")

    print(f"\n=== (c) Leak probe (above floor; grounded prompt must refuse) ===")
    out = generate_answer(retrieval.LEAK_PROBE, collection=collection)
    ok = out["refused"]
    status = "ok" if ok else "FAIL"
    if not ok:
        failures.append(f"leak probe not refused by the grounded prompt: {retrieval.LEAK_PROBE!r}")
    print(f"[{status}] best={out['best_similarity']:.3f}  {retrieval.LEAK_PROBE!r}")
    _print_answer(out)

    if failures:
        print("\nVERIFICATION FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nlive verdict: eval questions answered with citations; probes and leak refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
