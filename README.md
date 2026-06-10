# The Unofficial Guide — Project 1

A retrieval-augmented (RAG) question-answering system over real r/SJSU threads:
**what SJSU students actually say about CS / Software Engineering courses and
professors.** Ask a question, get an answer synthesized *only* from collected
Reddit comments, with the source threads cited. If the corpus doesn't cover the
question, the system says so instead of guessing.

**Pipeline:** `collect_documents.py` → `ingest.py` (parse + comment-aware
chunking) → `retrieval.py` (all-MiniLM-L6-v2 embeddings, ChromaDB, MMR re-rank,
refusal floor) → `generation.py` (Groq `llama-3.3-70b-versatile`, grounded
prompt, `[n]`→URL citation mapping) → `app.py` (Gradio UI).

**Run it:**

```bash
.venv/bin/python retrieval.py            # build/inspect the index (no API key)
.venv/bin/python generation.py           # live evaluation report (needs GROQ_API_KEY)
.venv/bin/python app.py                  # launch the Gradio query UI
env -u GROQ_API_KEY .venv/bin/python -m unittest discover   # 31 tests, no network
```

---

## Domain

**What SJSU students actually say about CS / Software Engineering professors and
courses.** The corpus captures crowd-sourced, candid student experience from
r/SJSU: which professors to take or avoid, how hard specific courses are (CS
46A/46B, 146, 147/149, 151, 157A, CmpE 187), realistic workload and grading,
course sequencing, and which classes best fill GE areas.

This knowledge is valuable precisely because it is **absent from official
channels**. The catalog and registrar list prerequisites and units but never say
a course is "hard but curved," and advisors won't name-and-shame instructors.
Rate My Professor entries are sparse or gamed — one whole thread in this corpus
(`2ljx6r`) documents a professor's negative reviews being removed within 24
hours. Reddit is where the unfiltered, attributable signal lives.

A **"document" = one Reddit thread** — the original post plus the comments we
fetched — stored as `documents/<post_id>.txt` with a metadata header (title,
URL, date, score, comment counts), the post body, and indented comments
preserving parent→reply nesting.

---

## Document Sources

All sources are real r/SJSU threads collected via the PullPush.io Reddit archive
(`collect_documents.py`), one thread per `documents/<post_id>.txt`. **15 curated
threads**, each with multiple substantive (non-bot, non-deleted) comments,
spanning courses, professors, difficulty, workload, and GE selection.

| # | Source (file) | Subtopic / description | URL |
|---|---------------|------------------------|-----|
| 1 | `kighem.txt` | "Spartan's Ultimate Guide, Part 2" — CS classes & professors to take vs avoid (Suneuy Kim, Patra, Kong Li, Olga Kovaleva), math-minor path | https://www.reddit.com/r/SJSU/comments/kighem/the_spartans_ultimate_guide_to_sjsu_part_2/ |
| 2 | `2ljx6r.txt` | Adel Atta — negative RMP reviews removed; professor-reputation case study | https://www.reddit.com/r/SJSU/comments/2ljx6r/adel_atta_negative_reviews_removed_from_rate_my/ |
| 3 | `2u15xl.txt` | CS majors rank upper-division courses by difficulty (146/147/149/151; Atta, Dr. Fai Yeung) | https://www.reddit.com/r/SJSU/comments/2u15xl/cs_majors_how_would_you_rank_the_upper_division/ |
| 4 | `3wjyr5.txt` | "CS 47 or CS 151?" — course selection + workload (Patra, Kim, Yazdankhah) | https://www.reddit.com/r/SJSU/comments/3wjyr5/cs_47_or_cs_151/ |
| 5 | `123uh6b.txt` | Computer Science vs Software Engineering B.S. — program comparison | https://www.reddit.com/r/SJSU/comments/123uh6b/computer_science_vs_software_engineering_bs/ |
| 6 | `3xmqve.txt` | Difference between CS 46B and CS 146 — content depth, projects (Shaverdian, Mortezaie) | https://www.reddit.com/r/SJSU/comments/3xmqve/computer_science_difference_between_cs_46b_and_cs/ |
| 7 | `37amxl.txt` | 4 CS major courses in one semester — workload reality (147/149 "hard but curved"; Mak for 149) | https://www.reddit.com/r/SJSU/comments/37amxl/comp_sci_majors_4_major_courses_in_one_semester/ |
| 8 | `btavob.txt` | CS 146 for a transfer student with C++/Python (Java prereq, CS 49J, prereq enforcement) | https://www.reddit.com/r/SJSU/comments/btavob/cs_transfer_from_c_school_about_cs_146/ |
| 9 | `94eap5.txt` | CS 157A (databases) with Ahmed Ezzat — survival tips, grading, vs Suneuy Kim | https://www.reddit.com/r/SJSU/comments/94eap5/i_am_taking_cs_157a_with_professor_ahmed_ezzat/ |
| 10 | `5rm577.txt` | Best CS electives / deep courses (CS 108 Game Design, CS 155 Algorithms, CS 185c) | https://www.reddit.com/r/SJSU/comments/5rm577/best_cs_electivesdeep_course/ |
| 11 | `1bwuij.txt` | Which CS/CmpE course to take — includes the blunt "DONT TAKE 187 WITH GAO" warning | https://www.reddit.com/r/SJSU/comments/1bwuij/could_use_some_advice_on_which_course_to_take/ |
| 12 | `he58kf.txt` | Frosh fall CS schedule advice (Math 42 workload, GE area sequencing) | https://www.reddit.com/r/SJSU/comments/he58kf/frosh_courses_for_this_fall_semestercs_major/ |
| 13 | `c81p6a.txt` | "Things I Wish Someone Told Me Freshman Year (Engineering)" — broad CS/eng advice | https://www.reddit.com/r/SJSU/comments/c81p6a/things_i_wish_someone_told_me_freshman_year/ |
| 14 | `2e4b40.txt` | New-student tips — courses, professors, study habits, workload | https://www.reddit.com/r/SJSU/comments/2e4b40/with_school_less_than_a_week_away_here_are_some/ |
| 15 | `nzwxu4.txt` | Best classes to fill GE areas (Professor Do for AAS33A/B, Chem 30A vs Chem 1A) | https://www.reddit.com/r/SJSU/comments/nzwxu4/best_class_to_fulfill_d2_or_d3us123_and_best/ |

---

## Ingestion Pipeline

Three stages, `collect → clean → structure` (`collect_documents.py` for
collection, `ingest.parse_document()` for clean/structure):

**Collect.** `collect_documents.py` pulls each thread (post + comments) from the
PullPush.io Reddit archive and writes one `documents/<post_id>.txt` per thread.
Each file opens with a `=====` banner, a `TITLE / URL / SUBREDDIT / DATE / SCORE
/ comment-count` header, a `--- POST BODY ---` section, and a `--- COMMENTS ---`
section whose units are marked `[COMMENT | u/user | score N]` (top level) and
`[REPLY | u/user | score N]` (indented 4 spaces per nesting level).

**Clean.** Removed before indexing: the `=====` banner; the `[COMMENT|REPLY |
u/user | score N]` delimiter lines themselves; zero-width-space junk lines
(`&#x200B;`); and bot/deleted/empty comments (filtered at collection). HTML
entities are unescaped (`&gt;` → `>`, `&amp;` → `&`). **Kept:** the post body and
every substantive comment/reply body. Header fields (`TITLE`, `URL`, `post_id`,
`DATE`, `SCORE`) are **routed to ChromaDB metadata, never embedded** — so a URL
or score can never be retrieved as if it were content.

**Structure.** `parse_document()` returns `(metadata dict, post body, nested
comment tree)`. The comment tree is rebuilt from the 4-space indentation so each
reply knows its parent — which the chunker needs for context anchoring.

---

## Chunking Strategy

The corpus is **comment-structured threads, not prose**, with a *bimodal* comment
length: substantive 40–120-word opinions vs sub-15-word one-liners ("Thanks for
this!" but also high-value "DONT TAKE 187 WITH GAO"). So chunk boundaries follow
the document's own delimiters, not a fixed character window (ADR-002).

**Chunk size:** ~200 word-pieces maximum per chunk (`ingest.BUDGET_WP = 200`), a
hard ceiling below MiniLM's 256 word-piece silent-truncation limit, with the
thread-title prefix counted inside that budget. Word-pieces are counted with the
**actual all-MiniLM-L6-v2 tokenizer**, not an approximation. Most chunks land
well under the ceiling (one comment ≈ 60–170 word-pieces).

**Overlap:** **None** between sibling comments — each comment is a
self-contained opinion, so a sliding window would only duplicate unrelated
takes and slice mid-opinion. The only deliberate redundancy is *vertical*: every
chunk is prefixed with `Thread: <title>` and, for a reply, an `In reply to:
"<parent snippet>"` line, so a free-floating answer ("The work won't be
difficult") still embeds *with* the professor/course it refers to.

**The rules (`ingest.chunk_document()`):**

1. **One chunk per substantive comment** (and per substantive standalone reply).
2. **Short-comment merge** — a reply under `MERGE_THRESHOLD_WP = 15` word-pieces
   is folded into its nearest emitted ancestor's chunk. This drops pure noise
   *and* rescues high-value one-liners: `"DONT TAKE 187 WITH GAO"` merges up into
   `u/Riotblade`'s parent comment (which carries "CmpE187… J. Gao always teaches
   that course"), so the warning keeps its course + professor anchor.
3. **Title + parent-snippet prefix** on every chunk (long titles trimmed to
   `TITLE_PREFIX_MAX_WP = 40` with an ellipsis — only `kighem`'s 43-wp title hits
   the cap; all 14 others embed in full).
4. **Oversized post bodies split on existing markdown headers**, echoing the
   `Section: <label>` into each piece so a "Take!"/"Avoid" list never loses its
   label. The only thread that needs this is `kighem`'s ~1,300-word "Spartan's
   Ultimate Guide" body → 32 chunks, each ≤200 wp and section-labeled.

**Why this fits Reddit threads.** A fixed window would cut "147 — Was pretty easy
but I took it with Atta (disclaimer)" away from the course it rates; per-comment
chunking keeps each opinion intact, and the merge rule keeps short warnings
attached to their professor/course. These numbers are corpus-driven (the 256-wp
ceiling from MiniLM, the boundaries from the comment/reply/header structure, the
merge threshold from the measured one-liner mode), not generic defaults.

**Final chunk count:** **283 chunks** across 15 documents — 89 top-level
comments, 63 post-body chunks, 131 replies. Max chunk size **192 word-pieces;
0 violations** of the 200-wp ceiling (measured by `python ingest.py`).

---

## Sample Chunks

Five real chunks, each labeled with its source document. Every chunk begins with
its `Thread:` anchoring prefix; reply chunks add an `In reply to:` line.

**Chunk `94eap5-007`** — source: `94eap5.txt` (CS 157A / Ezzat), comment by
`u/sjsuthrowaway`. *This is the answer chunk for eval Q4 — it self-describes via
the title prefix even though "The work won't be difficult" never names Ezzat.*

```
Thread: I am taking CS 157A with professor Ahmed Ezzat. Any tips to survive?
The work won't be difficult so you shouldn't have any trouble passing.

The hard part will be having to stomach him constantly bragging about his past,
and snapping at students for the smallest of questions.

The guy is a cartoon character.
```

**Chunk `1bwuij-008`** — source: `1bwuij.txt`, comment by `u/Riotblade` with a
merged reply. *The short-comment merge rule in action: the 5-word warning
`DONT TAKE 187 WITH GAO` (from `u/estidee`) is folded in and keeps the parent's
CmpE 187 / Gao anchor.*

```
Thread: Could use some advice on which course to take from Computer Science / Computer Engineering
I can only speak for CmpE187.  J. Gao always teaches that course and there's a lot
of information involved.  However, a lot of it is straight forward.  The only work
you'll be doing is for the final project, which is done in groups...

Reply: DONT TAKE 187 WITH GAO
```

**Chunk `3xmqve-005`** — source: `3xmqve.txt` (CS 46B vs 146), comment by
`u/h2opologod94` (top hit for eval Q2 at similarity **0.903**).

```
Thread: [Computer Science] Difference between CS 46B and CS 146?
I haven't taken 46B, but I just took 146 this past term. Here are my instructor's
materials if you're interested in looking them over to see what's covered:
http://www.cs.sjsu.edu/~shaverdian/

Reply: Thanks!
```

**Chunk `kighem-001`** — source: `kighem.txt`, **post-body section chunk** (the
oversized-body split). Note the trimmed title prefix and the `Section:` echo.

```
Thread: The Spartan's Ultimate Guide to SJSU, Part 2: General Advice Picking
Classes + Majoring In Computer Science (Classes and Professors To Take, Avoid …
Section: Picking Your Classes
My first piece of advice is to **figure out it from Year 0**. It will take a lot
of time to plan it out but at least you won't make the same mistake as me...
```

**Chunk `nzwxu4-007`** — source: `nzwxu4.txt` (GE areas), reply by `u/Swang1217`
(supports eval Q6). *A reply chunk: it carries an `In reply to:` parent snippet.*

```
Thread: Best class to fulfill D2 or D3/US123 and Best class for B1+B3 GE Area?...
In reply to: "Now, take my word with a grain of salt, and I don't know if you've
already registered for classes, but this is all I …"
Rising senior here too -- I took AAS33A/B and it was easy. Take it with Professor
Do. I think he's still teaching. Do not read his RMP reviews, his reviews actually
are not accurate. Just stay on his good side if you ever happen to take him!
```

---

## Embedding Model

**Model used:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional
vectors). Chosen because at this scale — a few hundred short, informal English
chunks where the relevant passage usually contains the professor's name or course
code outright — a larger model (`all-mpnet-base-v2`, `bge-small-en-v1.5`) would
retrieve the same passages while costing more latency and disk for no measurable
gain. MiniLM runs fast on a CPU laptop (~5× faster than mpnet), is ~90 MB, and is
the canonical sentence-transformers baseline, which keeps the pipeline
reproducible. Embeddings are stored in a persistent ChromaDB collection created
with `hnsw:space="cosine"` (Chroma defaults to L2 and the space cannot be changed
after creation), computed once and reused across runs.

A trial of `bge-small-en-v1.5` *was* run (per ADR-001's slang-miss revisit
trigger) and **rejected**: it improved passage ranking but compressed the
similarity scale until the refusal-floor separation between in-corpus and
out-of-corpus queries vanished (min eval best 0.707 vs max probe best 0.702).
MiniLM's wider score spread is what makes the refusal floor work (see below).

**Production tradeoff reflection.** With real users and no cost constraint, I'd
weigh factors that don't matter at a few-hundred-chunk scale:

- **Accuracy on domain-specific text** — I'd test a retrieval-tuned or larger
  model (`bge-large`, `all-mpnet-base-v2`) or a hosted API (OpenAI
  `text-embedding-3-large`, Cohere `embed-v3`) for professor nicknames, course
  codes ("CS 157A"), and sentiment slang ("hard but curved", "RUN") that
  general-purpose embeddings under-weight.
- **Context length** — MiniLM truncates at 256 word-pieces; if chunks grew I'd
  move to mpnet (384) or bge-small (512), which would also relax the chunker's
  200-wp ceiling.
- **Multilingual support** — MiniLM is English-only, and our corpus already
  includes non-native-speaker threads; a diverse student body would justify
  `bge-m3` or `paraphrase-multilingual-MiniLM`.
- **Local vs API-hosted** — hosted APIs buy accuracy and zero local compute but
  add per-call cost, network latency, and sending data off-machine; local models
  are free, private, and offline but bounded by laptop CPU.
- At production scale I'd also swap brute-force search for an ANN index
  (FAISS / a managed vector DB) and likely add a reranker — all unjustified here,
  where exact search over a few hundred vectors is instant.

---

## Retrieval Test Results

`retrieve(query, top_k=5)` (`retrieval.py`) embeds the query, over-fetches 50
candidates, and selects 5 by **greedy MMR re-rank (λ=0.7)** so the top-5 isn't a
single-thread monoculture (ADR-003). `results[0]` is always the globally
most-similar chunk, so the refusal floor sees the same best score plain top-k
would. Similarity = `1 − cosine distance`. Captured live, no API cost
(`python retrieval.py`):

**Query A — "What do students say about Professor Adel Atta?"** (top-5):

| rank | similarity | source | kind / author |
|------|-----------|--------|---------------|
| 1 | 0.696 | `2ljx6r` | reply / juangoat |
| 2 | 0.638 | `2ljx6r` | post / OP |
| 3 | 0.695 | `2ljx6r` | comment / person594 |
| 4 | 0.667 | `2ljx6r` | reply / person594 |
| 5 | 0.654 | `2ljx6r` | post / OP |

*Why these are relevant:* `2ljx6r` is the dedicated "Adel Atta Negative Reviews
Removed from RMP" thread, so every top hit is on-target — the OP body ("you
should really think twice"), the quoted removed reviews ("the difference between
Attas teaching and a train wreck…"), and the "negligent, incompetent professor"
review. The query names a professor who has a whole thread, so retrieval is tight
and high-similarity; the only cost is single-thread monoculture, which is correct
here because that one thread *is* the corpus's coverage of Atta.

**Query B — "According to students, how does CS 146 differ from CS 46B?"** (top-5):

| rank | similarity | source | kind / author |
|------|-----------|--------|---------------|
| 1 | 0.903 | `3xmqve` | comment / h2opologod94 |
| 2 | 0.842 | `3xmqve` | post / OP |
| 3 | 0.817 | `3xmqve` | reply / pythonhalp |
| 4 | 0.838 | `3xmqve` | reply / pythonhalp |
| 5 | 0.840 | `3xmqve` | comment / bhargavat |

*Why these are relevant:* the query nearly quotes the `3xmqve` thread title
("Difference between CS 46B and CS 146?"), so similarities are the highest in the
whole evaluation (0.903 at rank 1). The retrieved chunks contain the exact
comparison the question asks for — "146 goes more in depth into the data
structures learned in 46B," "more on the science side… more math," and the
observation that the two courses' content "appears strikingly similar." High
lexical *and* semantic overlap with a single authoritative thread.

**Query C — "Should I take CmpE 187 with Professor Gao?"** (top-5):

| rank | similarity | source | kind / author |
|------|-----------|--------|---------------|
| 1 | 0.559 | `1bwuij` | comment / Riotblade |
| 2 | 0.494 | `94eap5` | reply / fantasticsky_hng |
| 3 | 0.419 | `3wjyr5` | reply / Digital_Skyline |
| 4 | 0.446 | `1bwuij` | reply / Frokostblanding |
| 5 | 0.354 | `nzwxu4` | reply / Swang1217 |

*This query is included to demonstrate the merge rule + MMR.* The merged Gao
chunk (`1bwuij-008`, containing both "J. Gao always teaches that course" and the
merged "DONT TAKE 187 WITH GAO") ranks **#1** at 0.559 when asked directly — even
though it ranks 233/283 (sim 0.187) for the *broad* "professors to avoid" query,
because its embedding is dominated by the long parent CmpE 187 comment (ADR-002 /
ADR-003 documented deviation). The lower similarities here (0.35–0.56 vs Query
B's 0.90) show the floor is calibrated for exactly this: a real-but-niche query
still clears 0.52 at rank 1, while genuinely off-corpus queries do not.

**Refusal floor:** `REFUSAL_FLOOR = 0.52`. Calibrated at M4: the out-of-corpus
probe "Professor Smith CS 999" peaks at **0.479** (off-domain probes lower:
taxes 0.353, hiking 0.269), while the weakest in-corpus eval question (Q5) peaks
at **0.558** — 0.52 splits the gap with ~0.04 margin each side.

---

## Grounded Generation

Grounding is enforced at **three points**, two of which run before the model ever
sees the query (`generation.py`):

**1. Refusal floor — before any API call.** `is_answerable()` checks that the
best retrieved similarity clears 0.52. If not, `generate_answer()` returns the
refusal string immediately, with **zero Groq API calls** (free, deterministic,
test-asserted). Out-of-corpus probes never cost a token.

**2. System-prompt rules.** The retrieved chunks are numbered `[1]…[5]` in the
user message; the system prompt (verbatim in `generation.py: SYSTEM_PROMPT`)
orders the model, in priority order, to:

> 1. Answer **ONLY** from the excerpts… never invent a professor, course, grade
>    policy, or event.
> 2. If the excerpts do not actually discuss the specific professor, course, or
>    topic the user asked about — even if they discuss similar ones — reply with
>    exactly `NOT_IN_CORPUS` and nothing else.
> 3. When excerpts disagree, **report both sides** and attribute them; do not
>    pick a winner.
> 4. Cite the excerpt number(s) supporting each claim, like `[1]` or `[2][4]`.

Rule 2's `NOT_IN_CORPUS` sentinel is the **backstop for the one leak class no
floor can reject**: an unknown professor asked in the eval questions' register
("What do students say about Professor Smith's CS 999 class?") scores 0.596 —
above any floor that still admits the in-corpus questions. `generate_answer()`
maps any sentinel-bearing reply back to the refusal string.

**3. Programmatic `[n]` → URL citation mapping.** The model cites excerpt
*numbers*, never URLs. `collect_sources()` maps each cited number back to the
retrieved chunk's source URL **outside the model**, so a cited URL is always one
the retriever actually returned and can never be invented or mistyped. This is
test-asserted: `test_urls_never_enter_the_prompt` confirms no source URL ever
appears in the prompt text.

**How attribution surfaces:** the answer carries inline `[n]` citations; the UI
appends a **Sources** list (`title` → `url`, with the excerpt numbers that cite
it) and a collapsible **Retrieved excerpts** accordion showing each numbered
chunk with its `post_id` and similarity. On refusal the accordion shows a
"No excerpts cleared the relevance floor" note rather than the below-floor
chunks, so a refusal is never dressed up as grounded.

---

## Example Responses

From the live run (`generation.py`, `llama-3.3-70b-versatile`):

**Example 1 — in-corpus, with attribution.**
> *Q: What do students say about Professor Adel Atta?*
>
> Students say that Professor Adel Atta is a poor teacher who doesn't seem to
> know the material he's teaching [1][3]. He is described as unprepared, reading
> from slides with no elaboration, and evading student questions [2][3]… Overall,
> students warn others to avoid his classes if they want to learn [3].
>
> **Sources:** [Adel Atta Negative Reviews Removed from Rate My Professor](https://www.reddit.com/r/SJSU/comments/2ljx6r/adel_atta_negative_reviews_removed_from_rate_my/) — excerpts [1]–[5]

**Example 2 — in-corpus, with attribution.**
> *Q: What do students say about taking CS 157A with Professor Ezzat?*
>
> Students say that the work in CS 157A with Professor Ezzat won't be difficult,
> so passing shouldn't be a problem [2][5]. However, one commenter warns that the
> hard part will be tolerating Professor Ezzat's constant bragging about his past
> and his behavior of snapping at students for small questions [5]…
>
> **Sources:** [I am taking CS 157A with professor Ahmed Ezzat. Any tips to survive?](https://www.reddit.com/r/SJSU/comments/94eap5/i_am_taking_cs_157a_with_professor_ahmed_ezzat/) — excerpts [1]–[5]

**Example 3 — out-of-scope query, refused (no API call).**
> *Q: Best hiking trails near Yosemite?* (best similarity 0.269, below the 0.52 floor)
>
> Sorry — the corpus doesn't cover this. None of the collected r/SJSU threads
> discuss it, and answering anyway would mean making something up. Try a question
> about the CS/SE courses, professors, or GE picks students actually posted about.

The leak-class probe "What do students say about Professor Smith's CS 999 class?"
clears the floor (0.596) but is refused by the **grounded prompt** (sentinel) —
returning the same message — confirming both guards work.

---

## Query Interface

A minimal Gradio Blocks app (`app.py`, launched with `python app.py`):

**Input field**
- **Question** — a textbox (placeholder: *"e.g. Should I take CS 157A with
  Professor Ezzat?"*); submit via the **Ask** button or Enter.

**Output fields**
- **Answer** — markdown rendering of the grounded answer with inline `[n]`
  citations, followed by a **Sources** list (clickable thread titles → URLs).
- **Retrieved excerpts** — a collapsible accordion ("what the answer is grounded
  in") showing each numbered chunk with its `post_id` and similarity; on refusal
  it shows the no-excerpts note instead.
- **Example questions** — the 5 evaluation questions are wired as one-click
  `gr.Examples`.

**Sample interaction transcript** (a faithful transcript of the Gradio
interaction, reconstructed from the live `generate_answer` output as `app.py`
renders it):

```
[Question]  What do students say about taking CS 157A with Professor Ezzat?
[Ask ▸]

[Answer]
Students say that the work in CS 157A with Professor Ezzat won't be difficult,
so passing shouldn't be a problem [2][5]. However, one commenter warns that the
hard part will be tolerating Professor Ezzat's constant bragging about his past
and his behavior of snapping at students for small questions [5]. Another student
mentions that they didn't hate him, but he's not their lecturer of choice [4].

Sources
- I am taking CS 157A with professor Ahmed Ezzat. Any tips to survive? — excerpts [1], [2], [3], [4], [5]

[▾ Retrieved excerpts (what the answer is grounded in)]
[1] 94eap5 — similarity 0.804
    > Thread: I am taking CS 157A with professor Ahmed Ezzat. Any tips to survive?
    > ... (OP: "most people I got to ask weren't positive about him")
[5] 94eap5 — similarity 0.755
    > Thread: I am taking CS 157A with professor Ahmed Ezzat. Any tips to survive?
    > The work won't be difficult so you shouldn't have any trouble passing.
    > The hard part will be ... constantly bragging about his past ...
```

---

## Evaluation Report

All 5 finalized test questions from `planning.md` run through the **live**
pipeline (`generation.py`, real `GROQ_API_KEY`). Judgments are honest — see the
Failure Case Analysis for Q5 and the contradiction question.

| # | Question | Expected answer | System response (live) | Chunks retrieved | Judgment |
|---|----------|-----------------|------------------------|------------------|----------|
| 1 | What do students say about Professor Adel Atta? | Strongly negative; warns to "think twice," documents removed RMP reviews | "poor teacher who doesn't seem to know the material… unprepared… warn others to avoid" [1][3] | 5× `2ljx6r` (best 0.696) | **Accurate** |
| 2 | How does CS 146 differ from CS 46B? | 146 is "more on the science side": more math/theory, deeper data structures, harder textbook | "goes more in depth into the data structures… more on the science side… involving more math" [3][5] | 5× `3xmqve` (best 0.903) | **Accurate** |
| 3 | Which upper-division CS courses do students rank as hardest? | 146/147/149/151 among hardest; "hard but curved"; Yeung/Atta/Mak context | Centers on CS 146 ("gatekeeper class"; "got easier… Taylor"); notes the ranking question lists 146/147/149/151/152/154/160 but does not rank them | `2u15xl` ×4 + `he58kf` (best 0.776) | **Partially accurate** — describes 146 well but doesn't deliver the requested hardest-ranking across courses |
| 4 | What do students say about taking CS 157A with Professor Ezzat? | Mixed-to-negative; "weren't positive"; survival tips; vs Suneuy Kim | "work won't be difficult… hard part will be tolerating Ezzat's constant bragging… snapping at students" [2][5] | 5× `94eap5` (best 0.804) | **Accurate** |
| 5 | Which professors or courses do students explicitly say to avoid? | "DONT TAKE 187 WITH GAO" (CmpE 187); avoid Adel Atta; the Spartan's Guide take/avoid lists | "avoid Adel Atta's class [4]… 'train wreck'… No other professors or courses are explicitly mentioned" | `c81p6a`×2, `kighem`, `2ljx6r`, `37amxl` (best 0.558) | **Partially accurate** — surfaces Atta correctly but **misses** the Gao/CmpE 187 warning (see Failure Case) |

**Retrieval quality:** Q1, Q2, Q4 — *Relevant*; Q3 — *Partially relevant*; Q5 —
*Partially relevant* (correct Atta evidence, but the Gao warning was diversified
out of the top-5).
**Response accuracy:** Q1, Q2, Q4 — *Accurate*; Q3, Q5 — *Partially accurate*.

(Eval question #6 from planning.md — "What GE classes do students recommend?" —
is exercised in the live run and also answers correctly from `nzwxu4`/`he58kf`;
the five graded questions above are the finalized set.)

---

## Failure Case Analysis

### Primary failure — the CS 146 contradiction (designated case, ADR-005)

**Question that failed:** *"How hard is CS 146 really?"* — the planning.md
hard-question earmark. Thread `2u15xl` contains a genuine contradiction: one
student says 146 was **"pretty tough"** (comment `co57ff2`) while another reports
**"146 got easier last semester… Mostly because Taylor didn't teach it"** (comment
`co4alo2`). A correct answer must surface *both* sides (the system prompt's rule
3 explicitly orders this).

**What the system returned (live):**
> Students have differing opinions on the difficulty of CS 146. One student says
> it's "not too difficult" if you take the time to understand the material [2]…

— which reports **neither** side of the actual contradiction. It answered from
`3xmqve` and `3wjyr5` chunks instead.

**Root cause (retrieval × chunking, not generation).** The two halves of the
contradiction live in **different chunks of `2u15xl` that never co-occur in the
top-5**. For this query the top-5 is entirely `3xmqve`/`3wjyr5`; the
"146 got easier / Taylor" chunk ranks **20/283 (sim 0.569)** and the "pretty
tough" chunk ranks even lower — both far outside the retrieved 5. So neither side
ever reaches the model's context, and the model correctly answers only from what
it was given without fabricating the missing side. This is a textbook instance of
the "chunks that split key information across boundaries" risk named in
planning.md's Anticipated Challenges: comment-per-chunk granularity plus MMR
diversification scatter the contradiction across non-co-retrieved chunks. Per
ADR-005, this was **waived for M5** and carried here as the documented failure
case rather than altering frozen retrieval.

**What I would change to fix it.** Options, all of which touch frozen pipeline
behavior and were deliberately deferred: (a) raise MMR λ toward 1.0 or `top_k`
so more of `2u15xl` co-retrieves; (b) re-chunk `2u15xl` to keep the difficulty
assessments in one chunk; or (c) add a per-thread "gather siblings of a strong
hit" expansion step before generation. Each risks regressing the Q1–Q6/probe
calibration that ADR-001/003/004 verified, so the honest call was to document the
limitation, not paper over it.

### Secondary failure surfaced by the live run — Q5 misses the Gao warning

**Question:** *"Which professors or courses do students explicitly say to avoid?"*
**What the system returned:** a correct, well-cited warning about **Adel Atta**,
but ending "**No other professors or courses are explicitly mentioned as ones to
avoid in the provided excerpts**" — i.e. it **omits** the corpus's bluntest
avoid-warning, "DONT TAKE 187 WITH GAO."

**Root cause (retrieval, the merged-chunk embedding).** The Gao warning was
merged into `u/Riotblade`'s long CmpE 187 comment (chunk `1bwuij-008`), so that
chunk's embedding is dominated by the *neutral, detailed* parent text about Gao's
course — not by the 5-word warning. For the broad "avoid" query it ranks
**233/283 (sim 0.187)** and never enters the top-5, so the model can't cite it.
The same chunk ranks **#1 (0.559)** for the targeted "Should I take CmpE 187 with
Gao?" query — proving the information is indexed and retrievable, just not
enumerable by the broad phrasing. This is the documented ADR-003 deviation, now
confirmed end-to-end in generation. The fix would be the same class of
retrieval/chunking change as above (e.g. weight short merged warnings, or
query-expand on "avoid"), again out of the frozen scope.

The model's behavior is correct in *both* failures — it grounded faithfully and
did not fabricate. The failures are upstream, in the retrieval/chunking interplay.

---

## Spec Reflection

**One way the spec helped.** `planning.md`'s Evaluation Plan was written *before*
any pipeline code, and writing those 5 testable questions plus the "hard-question
earmark" (the nested-reply context-loss case) is what exposed the contradiction
gap early. Because the CS 146 contradiction was named as a candidate failure at
planning time, M5 verification went looking for it specifically, found that the
`co57ff2`/`co4alo2` chunks never co-retrieve, and could make a *deliberate*
scope decision (ADR-005: waive and document) instead of discovering a silent bug
at submission. The spec also fixed the architecture's data-flow contract — header
fields to metadata, never embedded — which the chunker and the
`test_urls_never_enter_the_prompt` test both enforce.

**One way the implementation diverged, and why.** planning.md's original
Architecture had the **model cite source URLs directly** ("cite the excerpts'
source URLs"). During M5 I changed this to **programmatic `[n]` → URL mapping**
(ADR-004): the model cites only excerpt *numbers*, and `collect_sources()` maps
them to URLs *outside* the model. The reason is correctness-by-construction — a
model that writes URLs can invent or mistype one, whereas a number that indexes
into the retrieved set can only ever resolve to a thread the retriever actually
returned (asserted by `test_urls_never_enter_the_prompt`). A second divergence,
ADR-003, added an **MMR diversity re-rank** that wasn't in the original retrieval
plan, because plain cosine top-5 returned single-thread monocultures that
defeated the documented k=5 "spread of perspectives" rationale. (Ironically, that
same diversification is part of why the Q5 Gao warning gets pushed out of top-5 —
a real, documented tradeoff.)

---

## AI Usage

**Instance 1 — citation scheme: AI's URL-citation design overridden to
programmatic `[n]`→URL mapping.**
- *What I gave the AI:* planning.md's Architecture stage 5 ("cite the excerpts'
  source URLs") plus the anti-hallucination requirement, and asked it to
  implement grounded generation.
- *What it produced:* a first design where the model writes source URLs inline in
  its answer, taking the planning text literally.
- *What I changed/overrode:* I rejected model-authored URLs because the model can
  invent or mistype them. I redesigned it (ADR-004) so the model cites excerpt
  *numbers* and `collect_sources()` maps `[n]` → URL deterministically outside the
  model. I then directed the AI to write `test_urls_never_enter_the_prompt`,
  which asserts no retrieved URL ever appears in the prompt — turning the design
  intent into an enforced invariant.

**Instance 2 — design review caught the refusal accordion presenting below-floor
chunks as grounding.**
- *What I gave the AI:* the M5 UI (`app.py`) for a grounding review — specifically
  the "Retrieved excerpts (what the answer is grounded in)" accordion.
- *What it produced:* an accordion that, on a *refusal*, still rendered the
  below-floor retrieved chunks — visually implying the refusal was "grounded in"
  chunks that had in fact failed the relevance floor.
- *What I changed/overrode:* I directed a fix (commit `916d08e`) introducing
  `format_chunks_md` / `NO_EXCERPTS_NOTE` so the refusal path shows
  "No excerpts cleared the relevance floor" instead of the chunks, with an
  offline unit test asserting the refusal path emits no chunk content. The
  `generate_answer` return contract was deliberately left intact (it still returns
  `results`) — the fix lives only in presentation.

**Instance 3 — corrected a wrong AI-drafted test assertion (M5 amendment).**
- *What I gave the AI:* a request to assert that the excerpts accordion renders
  each retrieved chunk's text.
- *What it produced:* `test_answer_path_still_renders_numbered_chunks` asserting
  the *full multi-line* chunk string appeared verbatim in the accordion markdown.
- *What I changed/overrode:* that assertion was wrong — the UI renders chunk text
  as a **blockquote**, prefixing every line with `"> "`, so the raw multi-line
  string is never a substring. I corrected it to match the chunk's **first line**
  (`r["text"].splitlines()[0]`) instead, with a code comment explaining the
  blockquote transform. Recorded during the M5 amendment.
