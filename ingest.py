"""Document ingestion + chunking for the r/SJSU thread corpus (Milestone 3).

Implements stages 1-2 of the planning.md architecture per ADR-002:

- parse_document(): strips the ===== banner, routes header fields (TITLE, URL,
  post_id, DATE, SCORE, ...) into a metadata dict that is never embedded,
  splits POST BODY from COMMENTS, and builds the nested comment tree from
  `[COMMENT|REPLY | u/<author> | score N]` delimiters (4 spaces per nesting
  level).

- chunk_document(): one chunk per substantive comment; replies under
  MERGE_THRESHOLD_WP word-pieces merge into their nearest emitted ancestor so
  high-value one-liners ("DONT TAKE 187 WITH GAO") keep their course/professor
  anchor; oversized post bodies split on existing markdown headers with a
  section-label echo; every chunk's embedded text is prefixed with the thread
  title (plus a parent snippet for reply chunks). BUDGET_WP is a hard ceiling
  counted with the real all-MiniLM-L6-v2 tokenizer (the model silently
  truncates at 256 word-pieces).

Run `python ingest.py` for a corpus-wide chunking stats report.
"""

from __future__ import annotations

import html
import pathlib
import re
import sys
from dataclasses import dataclass, field

BUDGET_WP = 200          # hard ceiling per chunk, prefix included (ADR-002)
MERGE_THRESHOLD_WP = 15  # replies under this merge into their parent chunk
TITLE_PREFIX_MAX_WP = 40  # long titles trimmed in the prefix (ADR-002 open item)
PARENT_SNIPPET_MAX_WP = 32
PACK_SLACK_WP = 8        # safety margin for joiners when packing units

DOCUMENTS_DIR = pathlib.Path(__file__).parent / "documents"

COMMENT_HEADER_RE = re.compile(
    r"^(\s*)\[(COMMENT|REPLY) \| u/(\S+) \| score (-?\d+)\]\s*$"
)
MD_HEADER_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
BOLD_LABEL_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
BULLET_RE = re.compile(r"^[*+-]\s+")
NOISE_RE = re.compile(r"^(?:\s|&#x200B;|​)+$")  # zero-width-space junk lines

_tokenizer = None


def wp_len(text: str) -> int:
    """Word-piece count under the all-MiniLM-L6-v2 tokenizer."""
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        # raw word-piece counting only — never fed to the model from here, so
        # the 512 "longer than maximum length" warning is noise
        _tokenizer.model_max_length = 1_000_000_000
    return len(_tokenizer.encode(text, add_special_tokens=False))


@dataclass
class Comment:
    author: str
    score: int
    depth: int
    text: str = ""
    replies: list["Comment"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1 — parsing
# ---------------------------------------------------------------------------

_HEADER_KEYS = {
    "TITLE": "title",
    "URL": "url",
    "SUBREDDIT": "subreddit",
    "DATE": "date",
    "SCORE": "score",
    "FETCHED COMMENTS (non-bot)": "fetched_comments",
    "SUBSTANTIVE COMMENTS": "substantive_comments",
}
_INT_FIELDS = {"score", "fetched_comments", "substantive_comments"}


def parse_document(path) -> tuple[dict, str, list[Comment]]:
    """Parse one documents/<post_id>.txt into (metadata, post body, comment tree)."""
    path = pathlib.Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    banners = [i for i, ln in enumerate(lines) if re.fullmatch(r"={10,}", ln)]
    if len(banners) < 2:
        raise ValueError(f"{path.name}: missing ===== banner pair")

    meta = {"post_id": path.stem}
    for ln in lines[banners[0] + 1 : banners[1]]:
        key, sep, value = ln.partition(":")
        field_name = _HEADER_KEYS.get(key.strip())
        if sep and field_name:
            value = value.strip()
            meta[field_name] = int(value) if field_name in _INT_FIELDS else value

    body_i = lines.index("--- POST BODY ---")
    comments_i = lines.index("--- COMMENTS ---")
    body = html.unescape("\n".join(lines[body_i + 1 : comments_i]).strip("\n"))
    comments = _parse_comments(lines[comments_i + 1 :])
    return meta, body, comments


def _parse_comments(lines: list[str]) -> list[Comment]:
    roots: list[Comment] = []
    stack: list[Comment] = []  # stack[d] = most recent comment at depth d
    cur: Comment | None = None
    cur_indent = 0
    buf: list[str] = []

    def close():
        if cur is not None:
            cur.text = html.unescape("\n".join(buf).strip("\n")).strip()
        buf.clear()

    for raw in lines:
        m = COMMENT_HEADER_RE.match(raw)
        if m:
            close()
            indent, _kind, author, score = m.groups()
            depth = len(indent) // 4
            cur = Comment(author=author, score=int(score), depth=depth)
            cur_indent = len(indent)
            del stack[depth:]
            if depth == 0 or not stack:
                roots.append(cur)
            else:
                stack[-1].replies.append(cur)
            stack.append(cur)
        elif cur is not None:
            line = raw
            if line[:cur_indent].strip() == "":
                line = line[cur_indent:]
            buf.append(line.rstrip())
    close()
    return roots


# ---------------------------------------------------------------------------
# Stage 2 — chunking
# ---------------------------------------------------------------------------


def _trim_to_wp(text: str, max_wp: int) -> str:
    text = " ".join(text.split())
    if wp_len(text) <= max_wp:
        return text
    words = text.split()
    while len(words) > 1 and wp_len(" ".join(words) + " …") > max_wp:
        words.pop()
    return " ".join(words) + " …"


def _is_noise(text: str) -> bool:
    return not text.strip() or bool(NOISE_RE.fullmatch(text))


def _split_oversized(text: str, avail_wp: int) -> list[str]:
    """Sentence-level fallback for a single unit that exceeds the budget."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, cur, cur_wp = [], [], 0
    for s in sentences:
        s_wp = wp_len(s)
        while s_wp > avail_wp:  # pathological single sentence: hard word split
            words = s.split()
            head = words[: max(1, len(words) // 2)]
            pieces.append(" ".join(head))
            s = " ".join(words[len(head):])
            s_wp = wp_len(s)
        if cur and cur_wp + s_wp > avail_wp:
            pieces.append(" ".join(cur))
            cur, cur_wp = [], 0
        cur.append(s)
        cur_wp += s_wp
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def _pack_units(units: list[str], avail_wp: int) -> list[str]:
    """Greedy-pack paragraph/bullet units into groups fitting avail_wp."""
    expanded: list[str] = []
    for u in units:
        if wp_len(u) <= avail_wp:
            expanded.append(u)
        else:
            expanded.extend(_split_oversized(u, avail_wp))
    groups, cur, cur_wp = [], [], 0
    for u in expanded:
        u_wp = wp_len(u)
        if cur and cur_wp + u_wp > avail_wp:
            groups.append("\n\n".join(cur))
            cur, cur_wp = [], 0
        cur.append(u)
        cur_wp += u_wp
    if cur:
        groups.append("\n\n".join(cur))
    return groups


def _body_sections(body: str) -> list[tuple[str | None, list[str]]]:
    """Split a post body into (section label, [paragraph/bullet units])."""
    sections: list[tuple[str | None, list[str]]] = []
    cur_label: str | None = None
    h_label: str | None = None
    cur_units: list[str] = []
    para: list[str] = []

    def flush_para():
        text = "\n".join(para).strip()
        para.clear()
        if text and not _is_noise(text):
            cur_units.append(text)

    def flush_section():
        nonlocal cur_units
        flush_para()
        if cur_units:
            sections.append((cur_label, cur_units))
        cur_units = []

    for line in body.splitlines():
        stripped = line.strip()
        mh = MD_HEADER_RE.match(line)
        mb = BOLD_LABEL_RE.match(stripped)
        if mh:
            flush_section()
            h_label = mh.group(1).strip()
            cur_label = h_label
        elif mb and len(mb.group(1).split()) <= 5:
            flush_section()
            sub = mb.group(1).strip().rstrip(":")
            cur_label = f"{h_label} — {sub}" if h_label else sub
        elif not stripped:
            flush_para()
        elif BULLET_RE.match(stripped):
            flush_para()
            if not _is_noise(stripped):
                cur_units.append(stripped)
        else:
            para.append(line)
    flush_section()
    return sections


def _chunk_body(title_prefix: str, body: str, budget: int) -> list[tuple[str | None, str]]:
    """Return [(section label or None, packed body text)] respecting the budget."""
    sections = _body_sections(body)
    if not sections:
        return []
    flat = "\n\n".join(u for _, units in sections for u in units)
    if wp_len(title_prefix) + wp_len(flat) + PACK_SLACK_WP <= budget:
        return [(None, flat)]
    out: list[tuple[str | None, str]] = []
    for label, units in sections:
        label_line = f"Section: {label}" if label else ""
        avail = budget - wp_len(title_prefix) - wp_len(label_line) - PACK_SLACK_WP
        for group in _pack_units(units, avail):
            out.append((label, group))
    return out


def _collect_comment_groups(comments: list[Comment], merge_threshold: int) -> list[dict]:
    """Pre-order grouping: substantive comments emit chunks; short ones merge up."""
    groups: list[dict] = []

    def walk(node: Comment, parent: Comment | None, target: dict | None):
        substantive = not _is_noise(node.text) and wp_len(node.text) >= merge_threshold
        if substantive:
            target = {"node": node, "parent": parent, "merged": [], "orphan": False}
            groups.append(target)
        elif target is not None:
            if node.text and not _is_noise(node.text):
                target["merged"].append((node.author, node.text))
        else:
            # short comment with no emitted ancestor: orphan group, pruned
            # later unless its merged descendants make it substantive
            target = {"node": node, "parent": parent, "merged": [], "orphan": True}
            groups.append(target)
        for reply in node.replies:
            walk(reply, node, target)

    for top in comments:
        walk(top, None, None)
    return groups


def chunk_document(
    meta: dict,
    body: str,
    comments: list[Comment],
    budget: int = BUDGET_WP,
    merge_threshold: int = MERGE_THRESHOLD_WP,
) -> list[dict]:
    """Chunk one parsed document into {id, text, metadata} dicts for indexing."""
    title_prefix = f"Thread: {_trim_to_wp(meta['title'], TITLE_PREFIX_MAX_WP)}"
    base_meta = {
        k: meta[k] for k in ("post_id", "title", "url", "date") if k in meta
    }
    chunks: list[dict] = []

    def emit(text: str, **extra):
        chunk_meta = dict(base_meta)
        chunk_meta.update({k: v for k, v in extra.items() if v is not None})
        chunks.append(
            {
                "id": f"{meta['post_id']}-{len(chunks):03d}",
                "text": text,
                "metadata": chunk_meta,
            }
        )

    body_pieces = _chunk_body(title_prefix, body, budget)
    for label, group in body_pieces:
        parts = [title_prefix]
        if label and len(body_pieces) > 1:
            parts.append(f"Section: {label}")
        parts.append(group)
        emit(
            "\n".join(parts),
            kind="post",
            author="OP",
            score=meta.get("score"),
            section=label,
        )

    for g in _collect_comment_groups(comments, merge_threshold):
        node, parent = g["node"], g["parent"]
        units = [p for p in re.split(r"\n\s*\n", node.text) if not _is_noise(p)]
        units += [f"Reply: {' '.join(t.split())}" for _, t in g["merged"]]
        if g["orphan"] and wp_len("\n".join(units)) < merge_threshold:
            continue  # pure noise ("🐐🐐🐐🐐thanks!!") — drop, don't index
        prefix_lines = [title_prefix]
        if parent is not None:
            snippet = _trim_to_wp(parent.text, PARENT_SNIPPET_MAX_WP)
            prefix_lines.append(f'In reply to: "{snippet}"')
        prefix = "\n".join(prefix_lines)
        avail = budget - wp_len(prefix) - PACK_SLACK_WP
        packed = _pack_units(units, avail)
        merged_authors = ",".join(a for a, _ in g["merged"]) or None
        for i, group_text in enumerate(packed):
            emit(
                f"{prefix}\n{group_text}",
                kind="comment" if node.depth == 0 else "reply",
                author=node.author,
                score=node.score,
                depth=node.depth,
                merged_replies=len(g["merged"]) or None,
                merged_authors=merged_authors,
                part=(i + 1) if len(packed) > 1 else None,
            )

    return chunks


def chunk_file(path) -> list[dict]:
    meta, body, comments = parse_document(path)
    return chunk_document(meta, body, comments)


def chunk_corpus(documents_dir=DOCUMENTS_DIR) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(pathlib.Path(documents_dir).glob("*.txt")):
        chunks.extend(chunk_file(path))
    return chunks


def main() -> int:
    paths = sorted(DOCUMENTS_DIR.glob("*.txt"))
    if not paths:
        print(f"no documents found in {DOCUMENTS_DIR}", file=sys.stderr)
        return 1
    total, violations, kinds = 0, [], {}
    print(f"{'file':<14} {'chunks':>6} {'max wp':>7}")
    for path in paths:
        chunks = chunk_file(path)
        sizes = [wp_len(c["text"]) for c in chunks]
        for c, s in zip(chunks, sizes):
            kinds[c["metadata"]["kind"]] = kinds.get(c["metadata"]["kind"], 0) + 1
            if s > BUDGET_WP:
                violations.append((c["id"], s))
        total += len(chunks)
        print(f"{path.name:<14} {len(chunks):>6} {max(sizes):>7}")
    print(f"\ntotal chunks: {total}")
    print("by kind: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    if violations:
        print(f"BUDGET VIOLATIONS (> {BUDGET_WP} wp): {violations}")
        return 1
    print(f"budget violations (> {BUDGET_WP} wp): 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
