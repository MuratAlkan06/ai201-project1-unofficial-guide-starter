"""Milestone 4: embedding + retrieval (architecture stages 3-4).

Embeds the M3 chunks (`ingest.chunk_corpus()`) with all-MiniLM-L6-v2 and
upserts them into a persistent ChromaDB collection created with
hnsw:space="cosine" (ADR-001 addendum -- Chroma defaults to L2 and the space
cannot be changed after creation). `retrieve()` returns chunks with cosine
similarities (1 - distance), diversified across threads with an MMR re-rank
(ADR-003); `is_answerable()` applies the minimum-similarity refusal floor so
out-of-corpus queries get refused instead of summarized.

Run the calibration report (AI Tool Plan M4 verification (a)-(d)):

    .venv/bin/python retrieval.py            # builds index if needed
    .venv/bin/python retrieval.py --rebuild  # drop + re-embed from scratch
"""

from __future__ import annotations

import pathlib
import sys

import chromadb
import numpy as np

import ingest

DB_DIR = pathlib.Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "unofficial_guide"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # ADR-001, same as wp_len tokenizer
TOP_K = 5  # ADR-001: tunable, default 5

# ADR-003: plain cosine top-5 returns single-thread monocultures (4 sibling
# replies from one c81p6a subtree for eval Q5), defeating the documented k=5
# intent of a cross-thread spread. retrieve() therefore over-fetches FETCH_K
# candidates and applies an MMR diversity re-rank. Lambda weights relevance;
# 1.0 would reduce to plain top-k (0.5 measurably drags in unrelated chunks).
FETCH_K = 50
MMR_LAMBDA = 0.7

# Minimum cosine similarity of the BEST hit for a query to be answerable.
# Calibrated at M4: canonical probe scores 0.479, min eval-question best is
# 0.558 (Q5), so 0.52 splits the gap with ~0.04 margin on each side
# (see DECISIONS.md ADR-001 resolution and the __main__ report below).
REFUSAL_FLOOR = 0.52

# Evaluation Plan questions (planning.md) with the supporting files each
# answer must draw from -- verification item (a) checks that at least one
# chunk from a named supporting file surfaces in top_k.
EVAL_QUESTIONS = [
    {
        "question": "What do students say about Professor Adel Atta?",
        "expect": {"2ljx6r", "2u15xl"},
    },
    {
        "question": "According to students, how does CS 146 differ from CS 46B?",
        "expect": {"3xmqve", "btavob"},
    },
    {
        "question": "Which upper-division CS courses do students rank as the hardest?",
        "expect": {"2u15xl", "37amxl"},
    },
    {
        "question": "What do students say about taking CS 157A with Professor Ezzat?",
        "expect": {"94eap5", "2u15xl"},
    },
    {
        "question": "Which professors or courses do students explicitly say to avoid?",
        "expect": {"1bwuij", "2ljx6r", "kighem"},
    },
    {
        "question": "What GE classes do students recommend as easy or worthwhile?",
        "expect": {"nzwxu4"},
    },
]

# Canonical out-of-corpus probe from the AI Tool Plan (verification item (c)).
OUT_OF_CORPUS_PROBE = "Professor Smith CS 999"

# Clearly off-domain probes: the floor must also refuse these.
OFF_DOMAIN_PROBES = [
    "How do I file taxes as an international student?",
    "Best hiking trails near Yosemite?",
]

# Known-leak probe, report-only: an unknown professor asked in the exact
# register of the eval questions scores 0.596 -- above any floor that still
# admits Q5 (0.558). No similarity floor can reject it; M5's grounded prompt
# ("answer only from retrieved chunks") is the documented backstop.
LEAK_PROBE = "What do students say about Professor Smith's CS 999 class?"

# ADR-002 sanity demo: the merged "DONT TAKE 187 WITH GAO" chunk is not
# enumerable via the broad Q5 (rank 233/283, sim 0.187 -- the chunk embedding
# is dominated by its parent comment) but ranks #1 for a targeted query.
TARGETED_GAO_QUERY = "Should I take CmpE 187 with Professor Gao?"

_model = None
_client = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(DB_DIR))
    return _client


def get_collection():
    return get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # ADR-001: NOT the L2 default
    )


def build_index(rebuild: bool = False):
    """Embed all corpus chunks and upsert them; idempotent across runs.

    The chunk count is the staleness signal: if the collection already holds
    exactly one entry per current chunk, the cached embeddings are reused
    (ADR-001: computed once, reproducible grading). `rebuild=True` drops the
    collection first so stale ids can never linger after a chunking change.
    """
    chunks = ingest.chunk_corpus()
    if rebuild:
        try:
            get_client().delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # nothing to drop on first build
    collection = get_collection()
    if collection.count() == len(chunks):
        return collection

    texts = [c["text"] for c in chunks]
    embeddings = get_model().encode(
        texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
    )
    collection.upsert(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[c["metadata"] for c in chunks],
    )
    return collection


def _mmr_order(embeddings: np.ndarray, relevance: np.ndarray, k: int, lam: float) -> list[int]:
    """Greedy maximal-marginal-relevance selection over the candidate pool.

    Candidates arrive sorted by relevance, so the first pick (index 0) is
    always the globally most-similar chunk -- which keeps the refusal-floor
    gate (best similarity) identical to plain top-k retrieval.
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    unit = embeddings / np.where(norms == 0, 1.0, norms)
    k = min(k, len(relevance))
    selected = [0]
    while len(selected) < k:
        best_i, best_score = -1, -np.inf
        for i in range(len(relevance)):
            if i in selected:
                continue
            redundancy = max(float(unit[i] @ unit[j]) for j in selected)
            score = lam * relevance[i] - (1.0 - lam) * redundancy
            if score > best_score:
                best_i, best_score = i, score
        selected.append(best_i)
    return selected


def retrieve(
    query: str,
    top_k: int = TOP_K,
    collection=None,
    fetch_k: int = FETCH_K,
    mmr_lambda: float = MMR_LAMBDA,
) -> list[dict]:
    """Return top_k chunks for `query`, MMR-diversified (ADR-003).

    Each result is {id, text, metadata, similarity} with similarity =
    1 - cosine distance (1.0 identical, ~0 unrelated). Results are in MMR
    selection order; results[0] is always the single most-similar chunk, so
    `is_answerable()` sees the same best score plain top-k would produce.
    """
    if collection is None:
        collection = build_index()
    qvec = get_model().encode([query], show_progress_bar=False, convert_to_numpy=True)[0]
    pool = max(top_k, min(fetch_k, collection.count()))
    res = collection.query(
        query_embeddings=[qvec.tolist()],
        n_results=pool,
        include=["documents", "metadatas", "distances", "embeddings"],
    )
    relevance = 1.0 - np.asarray(res["distances"][0])
    order = _mmr_order(np.asarray(res["embeddings"][0]), relevance, top_k, mmr_lambda)
    return [
        {
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "similarity": float(relevance[i]),
        }
        for i in order
    ]


def is_answerable(results: list[dict], floor: float = REFUSAL_FLOOR) -> bool:
    """Refusal gate: True iff the best retrieved similarity clears the floor."""
    return bool(results) and results[0]["similarity"] >= floor


def main() -> int:
    rebuild = "--rebuild" in sys.argv[1:]
    collection = build_index(rebuild=rebuild)
    print(f"collection={COLLECTION_NAME!r}  space={collection.metadata.get('hnsw:space')!r}  count={collection.count()}")

    failures = []
    eval_best = {}
    print(f"\n=== Eval questions (top_k={TOP_K}, floor={REFUSAL_FLOOR}) ===")
    for i, item in enumerate(EVAL_QUESTIONS, 1):
        results = retrieve(item["question"], collection=collection)
        hits = [(r["metadata"]["post_id"], round(r["similarity"], 3)) for r in results]
        hit_ids = {pid for pid, _ in hits}
        best = results[0]["similarity"]
        eval_best[i] = best
        supported = bool(hit_ids & item["expect"])
        answerable = is_answerable(results)
        status = "ok" if supported and answerable else "FAIL"
        if status == "FAIL":
            failures.append(f"Q{i}: supported={supported} answerable={answerable}")
        print(f"Q{i} [{status}] best={best:.3f}  expect={sorted(item['expect'])}")
        print(f"   {item['question']}")
        for pid, sim in hits:
            mark = "*" if pid in item["expect"] else " "
            print(f"   {mark} {pid:<8} {sim:.3f}")

    print("\n=== Out-of-corpus probes (must fall below the floor) ===")
    probe_best = {}
    for probe in [OUT_OF_CORPUS_PROBE, *OFF_DOMAIN_PROBES]:
        results = retrieve(probe, collection=collection)
        best = results[0]["similarity"]
        probe_best[probe] = best
        refused = not is_answerable(results)
        status = "ok" if refused else "FAIL"
        if not refused:
            failures.append(f"probe not refused: {probe!r} (best={best:.3f})")
        print(f"[{status}] best={best:.3f}  top={results[0]['metadata']['post_id']}  {probe!r}")

    leak = retrieve(LEAK_PROBE, collection=collection)
    print(
        f"[known leak, report-only] best={leak[0]['similarity']:.3f}  {LEAK_PROBE!r}"
        f"  -> gated by the M5 grounded prompt, not the floor"
    )

    gao = retrieve(TARGETED_GAO_QUERY, collection=collection)
    gao_rank = next(
        (i for i, r in enumerate(gao, 1) if "DONT TAKE 187 WITH GAO" in r["text"]), None
    )
    status = "ok" if gao_rank == 1 else "FAIL"
    if gao_rank != 1:
        failures.append(f"targeted Gao query rank={gao_rank}, expected 1")
    print(f"[{status}] ADR-002 merge demo: {TARGETED_GAO_QUERY!r} -> merged Gao chunk rank {gao_rank}")

    lo = max(probe_best.values())
    hi = min(eval_best.values())
    print(f"\nseparation: max probe best = {lo:.3f}  <  floor = {REFUSAL_FLOOR}  <=  min eval best = {hi:.3f}")
    if failures:
        print("CALIBRATION FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("floor verdict: all 6 eval questions answerable, all probes refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
