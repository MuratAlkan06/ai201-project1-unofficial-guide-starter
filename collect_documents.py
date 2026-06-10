"""
collect_documents.py — Phase 1 / Milestone 1 document collector.

Domain: "What SJSU students actually say about CS/Software Engineering
professors and courses" (recommendations, course difficulty, exam style,
workload).

Source: real r/SJSU posts via the PullPush.io Reddit archive API.

A "document" = one Reddit thread = one post + the comment set we actually
fetched for it. Each kept thread is written to documents/<id>.txt.

Design notes (frozen M1 slice):
  * Query submissions per search term (course codes/topics first, then a few
    professor names discovered in the first pass).
  * For each candidate post, fetch its comments by link_id.
  * Politeness: 15s timeout, 1 retry on failure, ~1s sleep between API calls.
  * Cache-first: every raw JSON response is written to raw_data/ (gitignored)
    with a deterministic filename. On re-run, cached requests are served from
    disk and never re-hit the network.
  * Known PullPush facts handled here:
      - size caps at 100.
      - Archive for r/SJSU ends ~May 19, 2025 -> we do NOT filter by recency.
      - Count comments we actually FETCHED, never the post's num_comments.
      - AutoModerator / bot comments are excluded from substantive counts.
      - Threads are deduped by post id across search terms.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

BASE = "https://api.pullpush.io/reddit/search"
RAW_DIR = "raw_data"
DOCS_DIR = "documents"

REQUEST_TIMEOUT = 15          # seconds
SLEEP_BETWEEN_CALLS = 1.0     # seconds, politeness
MAX_RETRIES = 1               # 1 retry on failure (= up to 2 attempts total)
SIZE = 100                    # PullPush hard cap

# Course codes / topics FIRST, then professor names discovered in first pass.
COURSE_AND_TOPIC_TERMS = [
    "CS 46A",
    "CS 46B",
    "CS 146",
    "CS 151",
    "CS 157A",
    "CMPE 102",
    "best CS professor",
    "avoid professor",
    "CS workload",
    "easy A CS",
    "GE recommendation",
]

# Professor names are discovered dynamically from first-pass results (see
# discover_professor_terms). A small seed list of names that recur in SJSU CS
# discussion is used as a fallback if discovery finds too few.
PROFESSOR_SEED_TERMS = [
    "professor Mak",
    "professor Taylor",
    "professor Kim",
    "professor Potika",
]

# Subreddits to search. r/SJSU is primary; r/SanJoseState is the documented
# fallback if we fall short of the floor.
PRIMARY_SUBREDDIT = "SJSU"
FALLBACK_SUBREDDIT = "SanJoseState"

# Bot / automated authors whose comments never count as substantive.
BOT_AUTHORS = {
    "automoderator",
    "sjsu-modteam",
    "[deleted]",
    "[removed]",
}

# Curation thresholds.
TARGET_MIN = 12
TARGET_MAX = 15
HARD_FLOOR = 10
MIN_SUBSTANTIVE_COMMENTS = 5

# Final curated corpus (post ids), in coverage order. The automatic heuristic
# (_domain_score / _is_on_domain) is a keyword brush that lets a few off-domain
# posts through (e.g. a Korea research-recruitment post that merely contains
# "Dr."/"course"). After a manual read of the cached candidates we pin the kept
# set here so the committed corpus is explicit, on-domain, and reproducible.
# Each id was confirmed to: (a) have >= MIN_SUBSTANTIVE_COMMENTS substantive
# fetched comments, and (b) genuinely discuss CS/SWE courses, professors,
# difficulty, workload, or GE selection. Leave empty to fall back to the
# automatic heuristic selection.
CURATED_POST_IDS = [
    "kighem",   # Ultimate Guide: CS classes/professors to take & avoid (Mak, Potika, Taylor)
    "2ljx6r",   # Adel Atta negative RMP reviews removed — professor reputation
    "2u15xl",   # Rank upper-division CS courses by difficulty (146/149, Yeung, Atta)
    "3wjyr5",   # CS 47 vs CS 151 — course selection + workload
    "123uh6b",  # Computer Science vs Software Engineering B.S. — program comparison
    "3xmqve",   # CS 46B vs CS 146 difference (Shaverdian, Mortezaie, projects)
    "37amxl",   # 4 CS major courses in one semester — workload (147/149 curve)
    "btavob",   # CS 146 prereqs / Java background / 49J — transfer advice
    "94eap5",   # CS 157A with Ezzat vs Kim — professor-specific tips
    "5rm577",   # Best CS electives/deep courses (CS 108, 155, 185c)
    "1bwuij",   # Which CS course to take ("DONT TAKE 187 WITH GAO")
    "he58kf",   # Frosh CS course schedule advice (Math 42 workload)
    "c81p6a",   # Things I wish I knew freshman year (Engineering) — broad advice
    "2e4b40",   # Tips for new students — courses/professors/workload
    "nzwxu4",   # Best GE-area classes (Professor Do AAS33, Chem 30A) — GE subtopic
]

# --------------------------------------------------------------------------- #
# Pre-filter / cost controls
# --------------------------------------------------------------------------- #
# The prior run stalled because it fetched comments for EVERY search hit
# (75 posts/term x ~1s politeness x 15 terms). To stay cheap we:
#   1. Pre-filter on the submission JSON alone BEFORE any comment fetch.
#   2. Cap the number of *live* comment fetches per whole run.
# num_comments is only a PREFILTER signal -- final curation still counts the
# comments we actually fetched (is_substantive on real bodies).
PREFILTER_MIN_NUM_COMMENTS = 5     # post-claimed comment count to be a candidate
MAX_COMMENT_FETCHES = 45           # hard cap on LIVE comment fetches this run

# Keywords that mark a candidate post as on-domain (professors, course
# difficulty, exam style, workload, GE). Used to rank candidates so the limited
# fetch budget is spent on the most relevant posts first. Cached threads are
# always re-read for free regardless of this list.
DOMAIN_KEYWORDS = (
    "professor", "prof ", "dr.", "teacher", "instructor", "lecturer",
    "exam", "midterm", "final", "test", "quiz", "grading", "curve",
    "hard", "difficult", "easy", "tough", "workload", "homework", "hw",
    "project", "recommend", "avoid", "take", "class", "course", "section",
    "best", "worst", "ge ", "general ed", "elective",
    "cs ", "cmpe", "se ", "software", "comp sci", "computer science",
)

# Pure-noise comment bodies (after strip/lower) that are not substantive.
NOISE_BODIES = {
    "[deleted]",
    "[removed]",
    "+1",
    "this",
    "same",
    "lol",
    "lmao",
    "^this",
    "yes",
    "no",
    "agreed",
}

# --------------------------------------------------------------------------- #
# Stats (for the end-of-run report)
# --------------------------------------------------------------------------- #

STATS = {
    "api_calls": 0,
    "cache_hits": 0,
    "retries": 0,
    "failures": 0,
    "live_comment_fetches": 0,   # GLOBAL count, enforces MAX_COMMENT_FETCHES
}

# Progress log so a background run can be polled with Read instead of blocking
# on a long foreground call.
LOG_PATH = "collect.log"


def log(msg: str) -> None:
    """Print to stdout AND append to LOG_PATH (line-buffered, flushed)."""
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


# --------------------------------------------------------------------------- #
# Cache-first HTTP
# --------------------------------------------------------------------------- #

def _cache_path(kind: str, key: str) -> str:
    """Deterministic cache filename for a request.

    kind: "submission" or "comment".
    key:  a stable identifier (e.g. "SJSU__CS_46A" or post id).
    """
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return os.path.join(RAW_DIR, f"{kind}__{safe}__{digest}.json")


def _get(url: str, cache_path: str) -> dict | None:
    """Cache-first GET. Returns parsed JSON dict, or None on hard failure.

    On a cache hit, no network request is made.
    """
    if os.path.exists(cache_path):
        STATS["cache_hits"] += 1
        with open(cache_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    attempt = 0
    while attempt <= MAX_RETRIES:
        attempt += 1
        try:
            STATS["api_calls"] += 1
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            with open(cache_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            time.sleep(SLEEP_BETWEEN_CALLS)  # politeness, only after a live call
            return data
        except (requests.RequestException, ValueError) as exc:
            if attempt <= MAX_RETRIES:
                STATS["retries"] += 1
                print(f"  ! request failed ({exc!s:.80}); retrying once...")
                time.sleep(SLEEP_BETWEEN_CALLS)
                continue
            STATS["failures"] += 1
            print(f"  ! request failed after retry, giving up: {url}")
            return None
    return None


def search_submissions(subreddit: str, term: str) -> list[dict]:
    key = f"{subreddit}__{term}"
    url = f"{BASE}/submission/?subreddit={subreddit}&q={requests.utils.quote(term)}&size={SIZE}"
    data = _get(url, _cache_path("submission", key))
    return (data or {}).get("data", []) or []


def comments_are_cached(post_id: str) -> bool:
    """True if this post's comments are already on disk (a free re-read)."""
    return os.path.exists(_cache_path("comment", post_id))


def fetch_comments(post_id: str) -> list[dict]:
    url = f"{BASE}/comment/?link_id={post_id}&size={SIZE}"
    data = _get(url, _cache_path("comment", post_id))
    return (data or {}).get("data", []) or []


# --------------------------------------------------------------------------- #
# Comment classification
# --------------------------------------------------------------------------- #

def is_substantive(comment: dict) -> bool:
    """A comment counts as substantive if it is not from a bot, not deleted,
    and not pure noise. Used for curation thresholds."""
    author = (comment.get("author") or "").strip().lower()
    if author in BOT_AUTHORS:
        return False
    if author.endswith("bot"):
        return False
    body = (comment.get("body") or "").strip()
    if not body:
        return False
    low = body.lower()
    if low in NOISE_BODIES:
        return False
    # Very short, link-only, or single-emoji bodies are not substantive.
    if len(body) < 10:
        return False
    return True


def is_bot(comment: dict) -> bool:
    author = (comment.get("author") or "").strip().lower()
    return author in BOT_AUTHORS or author.endswith("bot")


# --------------------------------------------------------------------------- #
# Document rendering
# --------------------------------------------------------------------------- #

def _fmt_date(created_utc) -> str:
    try:
        return datetime.fromtimestamp(int(created_utc), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "unknown"


def _reddit_url(post: dict) -> str:
    permalink = post.get("permalink")
    if permalink:
        return "https://www.reddit.com" + permalink
    return f"https://www.reddit.com/r/{post.get('subreddit','SJSU')}/comments/{post.get('id')}/"


def _comment_id(parent_id) -> str | None:
    """Strip the t1_/t3_ prefix from a parent_id.

    Older PullPush comment records sometimes store parent_id as a bare int
    (legacy threads, pre-2016) instead of the "t1_<id>"/"t3_<id>" string form,
    so coerce to str before splitting.
    """
    if not parent_id:
        return None
    return str(parent_id).split("_", 1)[-1]


def render_document(post: dict, comments: list[dict]) -> str:
    """Render a thread (post + fetched comments) to the committed .txt format.

    Comments are ordered so replies follow their parents, preserving
    parent->reply nesting context where the JSON provides it. Bot comments are
    kept out of the body to keep the corpus clean and on-topic.
    """
    post_id = post.get("id")
    title = (post.get("title") or "").strip()
    url = _reddit_url(post)
    date = _fmt_date(post.get("created_utc"))
    score = post.get("score", "n/a")

    # Keep only non-bot comments in the body; index them for nesting.
    kept = [c for c in comments if not is_bot(c)]
    by_id = {c.get("id"): c for c in kept}

    # Build a children map for nesting.
    children: dict[str, list[dict]] = {}
    roots: list[dict] = []
    for c in kept:
        parent = _comment_id(c.get("parent_id"))
        if parent and parent in by_id:
            children.setdefault(parent, []).append(c)
        else:
            # parent is the post (t3_) or a parent we did not fetch -> treat as root
            roots.append(c)

    # Stable ordering: by created_utc ascending.
    def _key(c):
        try:
            return int(c.get("created_utc") or 0)
        except (TypeError, ValueError):
            return 0

    roots.sort(key=_key)
    for k in children:
        children[k].sort(key=_key)

    substantive_count = sum(1 for c in kept if is_substantive(c))

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"TITLE: {title}")
    lines.append(f"URL: {url}")
    lines.append(f"SUBREDDIT: r/{post.get('subreddit', 'SJSU')}")
    lines.append(f"DATE: {date}")
    lines.append(f"SCORE: {score}")
    lines.append(f"FETCHED COMMENTS (non-bot): {len(kept)}")
    lines.append(f"SUBSTANTIVE COMMENTS: {substantive_count}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("--- POST BODY ---")
    body = (post.get("selftext") or "").strip()
    lines.append(body if body else "(no post body / link post)")
    lines.append("")
    lines.append("--- COMMENTS ---")

    def emit(comment: dict, depth: int) -> None:
        indent = "    " * depth
        author = comment.get("author") or "[unknown]"
        cscore = comment.get("score", "n/a")
        cbody = (comment.get("body") or "").strip()
        marker = "REPLY" if depth > 0 else "COMMENT"
        lines.append("")
        lines.append(f"{indent}[{marker} | u/{author} | score {cscore}]")
        for ln in cbody.splitlines():
            lines.append(f"{indent}{ln}")
        for child in children.get(comment.get("id"), []):
            emit(child, depth + 1)

    if not kept:
        lines.append("(no non-bot comments fetched)")
    else:
        for root in roots:
            emit(root, 0)

    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Professor-name discovery (course/topic pass informs professor pass)
# --------------------------------------------------------------------------- #

# Match a capitalized token after "prof/professor/dr" -- but only when it is
# Capitalized in the ORIGINAL text (case-sensitive), so we skip sentence
# fragments like "professor was..." / "professor but...".
PROF_PATTERN = re.compile(r"\b(?:Prof(?:essor)?|Dr)\.?\s+([A-Z][a-zA-Z]{2,})")

# Common English words that follow "professor" in a sentence but are NOT names.
# Filters the false positives the prior run produced (Was, But, Recommendations,
# Teaching, ...), which polluted the discovered-terms list non-deterministically.
PROF_STOPWORDS = {
    "the", "who", "for", "and", "you", "that", "this", "from", "was", "but",
    "are", "with", "they", "she", "her", "his", "him", "not", "had", "has",
    "would", "could", "should", "will", "did", "does", "doesn", "isn", "wasn",
    "teaching", "recommendation", "recommendations", "recommend", "reviews",
    "review", "rating", "ratings", "office", "hours", "name", "names", "said",
    "says", "told", "gave", "give", "made", "make", "took", "take", "taking",
    "class", "classes", "course", "courses", "left", "right", "here", "there",
    "what", "when", "where", "which", "really", "very", "also", "just", "got",
}


def discover_professor_terms(threads: dict[str, dict], limit: int = 4) -> list[str]:
    """Scan first-pass post+comment text for recurring professor surnames.

    Deterministic: results depend only on the threads dict, and ties break by
    name so the discovered list is stable across runs.
    """
    counts: dict[str, int] = {}
    for entry in threads.values():
        text = (entry["post"].get("title", "") + " " +
                entry["post"].get("selftext", "") + " " +
                " ".join((c.get("body") or "") for c in entry["comments"]))
        for m in PROF_PATTERN.finditer(text):
            name = m.group(1).strip()
            if name.lower() in PROF_STOPWORDS:
                continue
            key = name.capitalize()
            counts[key] = counts.get(key, 0) + 1
    # Sort by frequency desc, then name asc for a stable tie-break.
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    discovered = [f"professor {name}" for name, n in ranked if n >= 2][:limit]
    return discovered


# --------------------------------------------------------------------------- #
# Collection driver
# --------------------------------------------------------------------------- #

def _passes_prefilter(post: dict) -> bool:
    """Cheap submission-only gate applied BEFORE any comment fetch.

    Keep posts that claim enough discussion (num_comments) AND have a non-empty
    selftext or a title that reads as on-topic. num_comments is a PREFILTER ONLY;
    final curation counts the comments actually fetched.
    """
    if post.get("num_comments", 0) < PREFILTER_MIN_NUM_COMMENTS:
        return False
    selftext = (post.get("selftext") or "").strip()
    if selftext and selftext not in ("[removed]", "[deleted]"):
        return True
    # No usable body -> require an on-domain title to keep it as a candidate.
    return _domain_score(post) > 0


def _domain_score(post: dict) -> int:
    """Relevance signal: count of domain keyword hits in title+selftext."""
    text = ((post.get("title") or "") + " " + (post.get("selftext") or "")).lower()
    return sum(1 for kw in DOMAIN_KEYWORDS if kw in text)


def _candidate_rank(post: dict) -> tuple:
    """Sort key (descending) for spending the limited fetch budget well:
    on-domain relevance first, then claimed discussion size, then post score."""
    return (
        _domain_score(post),
        post.get("num_comments", 0),
        post.get("score", 0),
    )


def collect_for_terms(subreddit: str, terms: list[str],
                      threads: dict[str, dict]) -> None:
    """Search each term, PRE-FILTER on submission JSON, then fetch comments for
    the best new candidates -- subject to a hard cap on LIVE comment fetches.

    Threads are deduped by post id across terms. Comment fetches that hit the
    on-disk cache are free and do NOT count against the live-fetch budget.
    """
    # Gather + dedup candidate posts across all terms (cheap submission calls).
    candidates: dict[str, dict] = {}
    for i, term in enumerate(terms, 1):
        posts = search_submissions(subreddit, term)
        kept = 0
        for post in posts:
            pid = post.get("id")
            if not pid or pid in threads or pid in candidates:
                continue
            if not _passes_prefilter(post):
                continue
            candidates[pid] = post
            kept += 1
        log(f"term {i}/{len(terms)}: {term} — r/{subreddit} "
            f"{len(posts)} posts, {kept} new candidates "
            f"({len(candidates)} total pending)")

    # Rank candidates so the fetch budget is spent on the most relevant first.
    ranked = sorted(candidates.values(), key=_candidate_rank, reverse=True)

    for post in ranked:
        pid = post["id"]
        cached = comments_are_cached(pid)
        # MAX_COMMENT_FETCHES is a GLOBAL cap across the whole run (all terms,
        # both passes). Cache reads are free and never count against it.
        if not cached and STATS["live_comment_fetches"] >= MAX_COMMENT_FETCHES:
            continue
        comments = fetch_comments(pid)
        if not cached:
            STATS["live_comment_fetches"] += 1
        threads[pid] = {"post": post, "comments": comments}
        n = sum(1 for c in comments if is_substantive(c))
        label = ("cache" if cached
                 else f"live {STATS['live_comment_fetches']}/{MAX_COMMENT_FETCHES}")
        log(f"  fetched {pid} ({label}) — {n} substantive / {len(comments)} fetched")
        if not cached and STATS["live_comment_fetches"] >= MAX_COMMENT_FETCHES:
            log(f"  ! live comment-fetch cap reached ({MAX_COMMENT_FETCHES}); "
                "remaining candidates served from cache only")


def evaluate(threads: dict[str, dict]) -> list[tuple[str, dict, int]]:
    """Return (post_id, entry, substantive_count) for threads meeting the
    per-thread floor, sorted by substantive count desc."""
    qualifying = []
    for pid, entry in threads.items():
        n = sum(1 for c in entry["comments"] if is_substantive(c))
        if n >= MIN_SUBSTANTIVE_COMMENTS:
            qualifying.append((pid, entry, n))
    qualifying.sort(key=lambda t: t[2], reverse=True)
    return qualifying


# A thread is on-domain only if its post+comments actually discuss a CS/SE
# course or a professor's teaching -- not just a generic keyword brush. This
# gate keeps out off-topic posts (e.g. research-assistant recruitment, club
# ads) that happen to contain words like "course" or "professor".
COURSE_CODE_RE = re.compile(r"\b(?:cs|cmpe|se|math|engr|isda)\s?\d{2,3}[ab]?\b",
                            re.IGNORECASE)
TEACHING_TERMS = (
    "professor", "instructor", "lecturer", "teacher", "ta ", "grader",
    "exam", "midterm", "final exam", "quiz", "homework", "workload",
    "grading", "curve", "easy a", "hard class", "difficult class",
    "recommend", "avoid", "rate my professor", "rmp", "syllabus", "lecture",
)


def _thread_text(entry: dict) -> str:
    post = entry["post"]
    return (post.get("title", "") + " " + (post.get("selftext") or "") + " " +
            " ".join((c.get("body") or "") for c in entry["comments"])).lower()


def _is_on_domain(entry: dict) -> bool:
    """True if the thread genuinely discusses a CS/SE course or teaching."""
    text = _thread_text(entry)
    if COURSE_CODE_RE.search(text):
        return True
    return sum(1 for t in TEACHING_TERMS if t in text) >= 2


def _select(qualifying: list[tuple[str, dict, int]]) -> list[tuple[str, dict, int]]:
    """Pick the kept set, biased toward on-domain coverage (professors /
    difficulty / workload / exams / GE) rather than raw substantive count,
    which over-weights generic enrollment-logistics threads.

    On-domain gate filters off-topic posts first; ranking is then deterministic
    (domain hits, substantive count, score, then post id as a stable tie-break)
    so the selected set is reproducible across runs.

    If CURATED_POST_IDS is populated, it takes precedence: we emit exactly that
    pinned, manually verified on-domain set (in coverage order), which is what
    the committed corpus should be. The heuristic below is the fallback.
    """
    if CURATED_POST_IDS:
        by_id = {pid: (pid, entry, n) for pid, entry, n in qualifying}
        curated = [by_id[pid] for pid in CURATED_POST_IDS if pid in by_id]
        missing = [pid for pid in CURATED_POST_IDS if pid not in by_id]
        if missing:
            log(f"  ! curated ids missing from qualifying set: {missing}")
        return curated

    on_domain = [t for t in qualifying if _is_on_domain(t[1])]
    pool = on_domain if len(on_domain) >= HARD_FLOOR else qualifying

    def key(t):
        pid, entry, n = t
        post = entry["post"]
        # All-descending via negation, then pid ascending for a stable tie-break.
        return (-_domain_score(post), -n, -(post.get("score") or 0), pid)

    ranked = sorted(pool, key=key)
    return ranked[:TARGET_MAX]


def write_documents(selected: list[tuple[str, dict, int]]) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    for pid, entry, n in selected:
        text = render_document(entry["post"], entry["comments"])
        out = os.path.join(DOCS_DIR, f"{pid}.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        title = (entry["post"].get("title") or "")[:60]
        log(f"  wrote {out}  ({n} substantive)  {title!r}")


def main() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    # Reset the progress log for this run.
    open(LOG_PATH, "w", encoding="utf-8").close()
    start = time.time()
    threads: dict[str, dict] = {}

    # Pass 1: course codes and topics.
    log("=== PASS 1: course codes & topics ===")
    collect_for_terms(PRIMARY_SUBREDDIT, COURSE_AND_TOPIC_TERMS, threads)

    # Pass 2: professor names discovered from pass 1 (+ seeds).
    log("=== PASS 2: professor names ===")
    discovered = discover_professor_terms(threads)
    log(f"discovered professor terms: {discovered}")
    prof_terms = discovered + [t for t in PROFESSOR_SEED_TERMS if t not in discovered]
    prof_terms = prof_terms[:6]
    collect_for_terms(PRIMARY_SUBREDDIT, prof_terms, threads)

    qualifying = evaluate(threads)
    log(f"threads fetched: {len(threads)} | "
        f"qualifying (>= {MIN_SUBSTANTIVE_COMMENTS} substantive): {len(qualifying)}")

    # Fallback: widen to r/SanJoseState if below the hard floor.
    if len(qualifying) < HARD_FLOOR:
        log(f"=== FALLBACK: r/{FALLBACK_SUBREDDIT} (below floor {HARD_FLOOR}) ===")
        collect_for_terms(FALLBACK_SUBREDDIT, COURSE_AND_TOPIC_TERMS, threads)
        qualifying = evaluate(threads)
        log(f"after fallback -> qualifying: {len(qualifying)}")

    selected = _select(qualifying)
    log(f"writing top {len(selected)} threads "
        f"(target {TARGET_MIN}-{TARGET_MAX}, floor {HARD_FLOOR})")
    write_documents(selected)

    # Report.
    elapsed = time.time() - start
    log("=" * 60)
    log("API BEHAVIOR")
    log("=" * 60)
    log(f"  live api calls       : {STATS['api_calls']}")
    log(f"  live comment fetches : {STATS['live_comment_fetches']} (cap {MAX_COMMENT_FETCHES})")
    log(f"  cache hits           : {STATS['cache_hits']}")
    log(f"  retries              : {STATS['retries']}")
    log(f"  failures             : {STATS['failures']}")
    log(f"  wall time            : {elapsed:.1f}s")

    log("=" * 60)
    log(f"SELECTED {len(selected)} DOCUMENTS")
    log("=" * 60)
    for pid, entry, n in selected:
        log(f"  {pid}.txt | {n:>2} substantive | dom={_domain_score(entry['post'])} | "
            f"{_reddit_url(entry['post'])} | {(entry['post'].get('title') or '')[:55]!r}")

    if len(selected) < HARD_FLOOR:
        log(f"!!! WARNING: only {len(selected)} threads qualify "
            f"(< hard floor {HARD_FLOOR}). Consider WebSearch/WebFetch fallback.")
        sys.exit(2)
    log("DONE")


if __name__ == "__main__":
    main()
