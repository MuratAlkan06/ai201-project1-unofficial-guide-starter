"""Milestone 3 verification suite (stdlib unittest, no new dependencies).

Encodes the five concrete verification items from planning.md's AI Tool Plan
(Milestone 3) plus the parser/noise rules from ADR-002. Run with:

    .venv/bin/python -m unittest -v test_ingest
"""

import pathlib
import unittest

import ingest

DOCS = pathlib.Path(__file__).parent / "documents"


class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body, cls.comments = ingest.parse_document(DOCS / "94eap5.txt")

    def test_header_routed_to_metadata(self):
        self.assertEqual(self.meta["post_id"], "94eap5")
        self.assertTrue(self.meta["title"].startswith("I am taking CS 157A"))
        self.assertTrue(
            self.meta["url"].startswith("https://www.reddit.com/r/SJSU/comments/94eap5/")
        )
        self.assertEqual(self.meta["date"], "2018-08-03")
        self.assertEqual(self.meta["score"], 2)
        self.assertEqual(self.meta["substantive_comments"], 6)

    def test_body_clean_of_banner_and_markers(self):
        self.assertTrue(self.body.startswith("Hi everyone"))
        self.assertNotIn("=====", self.body)
        self.assertNotIn("TITLE:", self.body)
        self.assertNotIn("--- COMMENTS ---", self.body)

    def test_comment_tree_nesting(self):
        self.assertEqual(len(self.comments), 2)
        first, second = self.comments
        self.assertEqual(first.author, "SomeTechNoob")
        self.assertEqual(first.score, 6)
        self.assertEqual(first.depth, 0)
        # 4-level chain: SomeTechNoob > fantasticsky_hng > SomeTechNoob > fantasticsky_hng
        self.assertEqual(len(first.replies), 1)
        self.assertEqual(first.replies[0].author, "fantasticsky_hng")
        self.assertEqual(first.replies[0].depth, 1)
        self.assertEqual(first.replies[0].replies[0].replies[0].depth, 3)
        self.assertEqual(second.author, "sjsuthrowaway")
        self.assertIn("The work won't be difficult", second.text)


class ChunkingVerification(unittest.TestCase):
    """Items (a)-(e) from planning.md AI Tool Plan, Milestone 3."""

    @classmethod
    def setUpClass(cls):
        cls.by_doc = {}
        for path in sorted(DOCS.glob("*.txt")):
            cls.by_doc[path.stem] = ingest.chunk_file(path)
        cls.all_chunks = [c for cs in cls.by_doc.values() for c in cs]

    def test_a_gao_warning_merged_into_parent(self):
        """(a) 1bwuij.txt: 'DONT TAKE 187 WITH GAO' merges into the CmpE187/Gao
        parent chunk and is never emitted alone."""
        hits = [c for c in self.by_doc["1bwuij"] if "DONT TAKE 187 WITH GAO" in c["text"]]
        self.assertEqual(len(hits), 1)
        chunk = hits[0]
        self.assertIn("Gao always teaches that course", chunk["text"])
        self.assertEqual(chunk["metadata"]["author"], "Riotblade")
        self.assertIn("estidee", chunk["metadata"]["merged_authors"])

    def test_b_oversized_body_split_with_section_labels(self):
        """(b) kighem.txt: ~1,300-word body -> multiple chunks, each within
        budget, each split piece retaining its section label."""
        body_chunks = [
            c for c in self.by_doc["kighem"] if c["metadata"]["kind"] == "post"
        ]
        self.assertGreaterEqual(len(body_chunks), 3)
        for c in body_chunks:
            self.assertLessEqual(ingest.wp_len(c["text"]), ingest.BUDGET_WP)
        unlabeled = [c for c in body_chunks if "Section: " not in c["text"]]
        self.assertLessEqual(len(unlabeled), 1)  # only the pre-header intro
        kim = next(c for c in body_chunks if "Suneuy Kim" in c["text"])
        self.assertIn("AVOID", kim["text"].split("\n")[1])
        take = next(c for c in body_chunks if "William Andreopoulos" in c["text"])
        self.assertIn("Take!", take["text"].split("\n")[1])

    def test_c_title_prefix_and_metadata_routing(self):
        """(c) Title prefix present in embedded text; TITLE/URL in metadata;
        banner markup and the source URL never embedded."""
        for c in self.all_chunks:
            self.assertTrue(c["text"].startswith("Thread: "), c["id"])
            self.assertIn("title", c["metadata"])
            self.assertIn("url", c["metadata"])
            self.assertTrue(c["metadata"]["url"].startswith("https://www.reddit.com/"))
            self.assertNotIn(c["metadata"]["url"], c["text"], c["id"])
            for marker in ("=====", "TITLE:", "URL:", "[COMMENT", "[REPLY"):
                self.assertNotIn(marker, c["text"], c["id"])

    def test_d_budget_holds_across_corpus(self):
        """(d) No chunk in the whole corpus exceeds the word-piece budget."""
        self.assertGreater(len(self.all_chunks), 0)
        oversize = [
            (c["id"], ingest.wp_len(c["text"]))
            for c in self.all_chunks
            if ingest.wp_len(c["text"]) > ingest.BUDGET_WP
        ]
        self.assertEqual(oversize, [])

    def test_e_reply_chunk_keeps_parent_context(self):
        """(e) kighem lines 143-147: the 'easier than most' reply chunk carries
        Fabio / CS 174 context from its parent comment."""
        hits = [
            c
            for c in self.by_doc["kighem"]
            if "easier than most bc he is a good professor" in c["text"]
        ]
        self.assertEqual(len(hits), 1)
        chunk = hits[0]
        self.assertEqual(chunk["metadata"]["kind"], "reply")
        self.assertIn("Fabio", chunk["text"])
        self.assertIn("174", chunk["text"])

    def test_noise_comments_dropped(self):
        """Pure-noise short top-level comments are not indexed."""
        self.assertFalse(any("🐐" in c["text"] for c in self.by_doc["kighem"]))

    def test_chroma_compatible_metadata(self):
        """Metadata values must be str/int/float/bool (Chroma constraint)."""
        for c in self.all_chunks:
            for key, value in c["metadata"].items():
                self.assertIsInstance(value, (str, int, float, bool), f"{c['id']}:{key}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
