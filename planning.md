# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->

**What SJSU students actually say about CS / Software Engineering professors and courses.** The corpus captures crowd-sourced, candid student experience from r/SJSU: which professors to take or avoid, how hard specific courses are (CS 46A/46B, 146, 147/149, 151, 157A), realistic workload and grading, course sequencing, and which classes best fill GE areas. This knowledge is valuable precisely because it is *absent from official channels*: the catalog and registrar list prerequisites and units but never say a course is "hard but curved" or that a named professor "writes his own RMP reviews"; advisors are cautious and won't name-and-shame instructors; and Rate My Professor entries are sparse, gamed, or deleted (one whole thread documents negative reviews being removed). Reddit is where the unfiltered, attributable signal lives.

In this project a **"document" = one Reddit thread** — the original post plus the comments we actually fetched for it — written to a single `documents/<post_id>.txt` file with a metadata header (title, full URL, date, score, fetched/substantive comment counts), the post body, and the comments delimited and indented to preserve parent→reply nesting.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

All sources are real r/SJSU threads collected via the PullPush.io Reddit archive (one thread = one `documents/<post_id>.txt`). 15 curated threads, each with ≥5 substantive (non-bot, non-deleted, non-noise) fetched comments, spanning courses, professors, difficulty, workload, and GE selection.

| # | Source (file) | Description | URL |
|---|---------------|-------------|-----|
| 1 | `kighem.txt` | "Spartan's Ultimate Guide, Part 2" — CS classes & professors to take vs avoid (Suneuy Kim, Patra, Kong Li, Olga Kovaleva), plus a math-minor path | https://www.reddit.com/r/SJSU/comments/kighem/the_spartans_ultimate_guide_to_sjsu_part_2/ |
| 2 | `2ljx6r.txt` | Adel Atta — collection of negative Rate My Professor reviews that were removed; professor-reputation case study | https://www.reddit.com/r/SJSU/comments/2ljx6r/adel_atta_negative_reviews_removed_from_rate_my/ |
| 3 | `2u15xl.txt` | CS majors rank the upper-division courses by difficulty (146/147/149/151; mentions Atta, Dr. Fai Yeung) | https://www.reddit.com/r/SJSU/comments/2u15xl/cs_majors_how_would_you_rank_the_upper_division/ |
| 4 | `3wjyr5.txt` | "CS 47 or CS 151?" — course-selection + workload advice (Patra, Kim, Yazdankhah) | https://www.reddit.com/r/SJSU/comments/3wjyr5/cs_47_or_cs_151/ |
| 5 | `123uh6b.txt` | Computer Science vs Software Engineering B.S. — program comparison and tradeoffs | https://www.reddit.com/r/SJSU/comments/123uh6b/computer_science_vs_software_engineering_bs/ |
| 6 | `3xmqve.txt` | Difference between CS 46B and CS 146 — content depth, projects, professors (Shaverdian, Mortezaie) | https://www.reddit.com/r/SJSU/comments/3xmqve/computer_science_difference_between_cs_46b_and_cs/ |
| 7 | `37amxl.txt` | Taking 4 CS major courses in one semester — workload reality (147/149 "hard but curved"; Mak for 149) | https://www.reddit.com/r/SJSU/comments/37amxl/comp_sci_majors_4_major_courses_in_one_semester/ |
| 8 | `btavob.txt` | CS 146 for a transfer student with C++/Python (Java prereq, CS 49J, prereq enforcement) | https://www.reddit.com/r/SJSU/comments/btavob/cs_transfer_from_c_school_about_cs_146/ |
| 9 | `94eap5.txt` | CS 157A (databases) with Ahmed Ezzat — survival tips, grading, comparison to Suneuy Kim | https://www.reddit.com/r/SJSU/comments/94eap5/i_am_taking_cs_157a_with_professor_ahmed_ezzat/ |
| 10 | `5rm577.txt` | Best CS electives / deep courses (CS 108 Game Design, CS 155 Algorithms, CS 185c) | https://www.reddit.com/r/SJSU/comments/5rm577/best_cs_electivesdeep_course/ |
| 11 | `1bwuij.txt` | Which CS/CmpE course to take — includes a blunt "DON'T TAKE 187 WITH GAO" warning | https://www.reddit.com/r/SJSU/comments/1bwuij/could_use_some_advice_on_which_course_to_take/ |
| 12 | `he58kf.txt` | Frosh fall-semester CS schedule advice (Math 42 workload, GE area sequencing) | https://www.reddit.com/r/SJSU/comments/he58kf/frosh_courses_for_this_fall_semestercs_major/ |
| 13 | `c81p6a.txt` | "Things I Wish Someone Told Me Freshman Year (Engineering)" — broad CS/eng advice (36 comments) | https://www.reddit.com/r/SJSU/comments/c81p6a/things_i_wish_someone_told_me_freshman_year/ |
| 14 | `2e4b40.txt` | New-student tips — courses, professors, study habits, workload | https://www.reddit.com/r/SJSU/comments/2e4b40/with_school_less_than_a_week_away_here_are_some/ |
| 15 | `nzwxu4.txt` | Best classes to fill GE areas (Professor Do for AAS33A/B, Chem 30A vs Chem 1A) — GE subtopic | https://www.reddit.com/r/SJSU/comments/nzwxu4/best_class_to_fulfill_d2_or_d3us123_and_best/ |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**

**Overlap:**

**Reasoning:**

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**

**Top-k:**

**Production tradeoff reflection:**

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

**DRAFT — to be finalized in Milestone 2.** All 6 candidates below passed a corpus coverage check: for each question, grep across `documents/*.txt` confirmed ≥2 distinct supporting passages (supporting files noted per row).

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | What do students say about Professor Adel Atta? | Strongly negative: students warn to "really think twice" before registering for his classes and document negative Rate My Professor reviews being removed; a CS 147 student adds "was pretty easy but I took it with Atta (disclaimer)". (`2ljx6r.txt`, `2u15xl.txt`) |
| 2 | According to students, how does CS 146 differ from CS 46B? | CS 146 is "more on the science side": more math/theory, more data structures, and a much harder textbook (CLRS); content overlaps 46B but goes deeper. (`3xmqve.txt`, `btavob.txt`) |
| 3 | Which upper-division CS courses do students rank as the hardest? | Students rank the upper-division set (146/147/149/151) with CS 146 and CS 147/149 discussed among the hardest — "hard but curved" — with instructor context (Yeung, Atta, Mak). (`2u15xl.txt`, `37amxl.txt`) |
| 4 | What do students say about taking CS 157A with Professor Ezzat? | Mixed-to-negative: the OP reports "most people I got to ask weren't positive about him"; commenters give survival tips on his homework, tests, and grading, and compare him to Suneuy Kim. (`94eap5.txt`, `2u15xl.txt`) |
| 5 | Which professors or courses do students explicitly say to avoid? | "DONT TAKE 187 WITH GAO" (CmpE 187); warnings about Adel Atta; the Spartan's Guide lists CS professors to take vs avoid. (`1bwuij.txt`, `2ljx6r.txt`, `kighem.txt`) |
| 6 | What GE classes do students recommend as easy or worthwhile? | AAS 33A/B with Professor Do ("it was easy... do not read his RMP reviews"), AMS-1A/1B (knocks out many areas at once), and Chem 30A over Chem 1A ("real easy, half is high-school review"). (`nzwxu4.txt`) |

**Hard-question earmark (for M2):** the corpus contains nested-reply context-loss cases — e.g. in `kighem.txt` a reply says "his class is easier than most bc he is a good professor" while the professor is named only in the parent comment. One of the five final questions will be designated around this failure mode in Milestone 2.

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1.

2.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

**Milestone 4 — Embedding and retrieval:**

**Milestone 5 — Generation and interface:**
