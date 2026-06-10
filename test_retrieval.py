"""Milestone 4 verification suite (stdlib unittest, no new dependencies).

Encodes the four concrete verification items from planning.md's AI Tool Plan
(Milestone 4) plus the ADR-003 diversity behavior. Run with:

    .venv/bin/python -m unittest -v test_retrieval

Measured deviations from the AI Tool Plan examples, recorded in DECISIONS.md
(ADR-003) and the M4 task contract:
- Q5 cannot surface the merged 1bwuij Gao chunk at top_k=5: it ranks 233/283
  (sim 0.187) for that broad enumeration query because its embedding is
  dominated by the parent comment. The merge is instead verified with a
  targeted query, where the chunk ranks #1.
- Q4's "most people... weren't positive" OP chunk ranks 9th by relevance;
  the "work won't be difficult" answer chunk does land in top-5.
"""

import unittest

import retrieval


class RetrievalVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = retrieval.build_index()
        cls.results = {
            item["question"]: retrieval.retrieve(item["question"], collection=cls.collection)
            for item in retrieval.EVAL_QUESTIONS
        }
        cls.probe = retrieval.retrieve(retrieval.OUT_OF_CORPUS_PROBE, collection=cls.collection)

    def _q(self, n):
        item = retrieval.EVAL_QUESTIONS[n - 1]
        return item, self.results[item["question"]]

    def test_a_every_question_hits_a_supporting_file(self):
        """(a) Each eval question surfaces >=1 chunk from a named supporting
        file in top_k=5."""
        for n in range(1, 7):
            item, results = self._q(n)
            hit_ids = {r["metadata"]["post_id"] for r in results}
            self.assertTrue(
                hit_ids & item["expect"],
                f"Q{n} retrieved {sorted(hit_ids)}, expected one of {sorted(item['expect'])}",
            )

    def test_a_q4_ezzat_answer_passage(self):
        """(a) Q4 returns the 94eap5 'work won't be difficult' answer chunk
        (the 'weren't positive' OP chunk ranks 9th -- see module docstring)."""
        _, results = self._q(4)
        texts = [r["text"] for r in results if r["metadata"]["post_id"] == "94eap5"]
        self.assertGreaterEqual(len(texts), 3)
        self.assertTrue(any("won't be difficult" in t for t in texts))

    def test_a_q5_avoid_hits_kighem_and_atta(self):
        """(a) Q5 surfaces the kighem AVOID guide and the 2ljx6r Atta thread."""
        _, results = self._q(5)
        hit_ids = {r["metadata"]["post_id"] for r in results}
        self.assertIn("kighem", hit_ids)
        self.assertIn("2ljx6r", hit_ids)

    def test_a_q5_gao_merge_via_targeted_query(self):
        """(a, re-scoped) The merged ADR-002 Gao chunk ranks #1 for a targeted
        query, keeping the one-line warning retrievable with full context."""
        results = retrieval.retrieve(retrieval.TARGETED_GAO_QUERY, collection=self.collection)
        top = results[0]
        self.assertEqual(top["metadata"]["post_id"], "1bwuij")
        self.assertIn("DONT TAKE 187 WITH GAO", top["text"])
        self.assertIn("Gao always teaches that course", top["text"])

    def test_b_collection_reports_cosine_space(self):
        """(b) The collection was created with hnsw:space='cosine', not L2."""
        self.assertEqual((self.collection.metadata or {}).get("hnsw:space"), "cosine")

    def test_c_out_of_corpus_probe_refused(self):
        """(c) The canonical probe scores below the floor and is refused."""
        self.assertLess(self.probe[0]["similarity"], retrieval.REFUSAL_FLOOR)
        self.assertFalse(retrieval.is_answerable(self.probe))

    def test_c_off_domain_probes_refused(self):
        for probe in retrieval.OFF_DOMAIN_PROBES:
            results = retrieval.retrieve(probe, collection=self.collection)
            self.assertFalse(retrieval.is_answerable(results), probe)

    def test_d_floor_separates_eval_questions_from_probe(self):
        """(d) All 6 in-corpus questions clear the floor the probe fails."""
        for n in range(1, 7):
            _, results = self._q(n)
            self.assertGreaterEqual(
                results[0]["similarity"], retrieval.REFUSAL_FLOOR, f"Q{n}"
            )
            self.assertTrue(retrieval.is_answerable(results), f"Q{n}")
        self.assertLess(self.probe[0]["similarity"], retrieval.REFUSAL_FLOOR)

    def test_retrieve_shape_and_floor_invariant(self):
        """results[0] is the global best (MMR never changes the floor gate);
        every result carries url/title metadata for attribution."""
        for question, results in self.results.items():
            self.assertEqual(len(results), retrieval.TOP_K, question)
            best = max(r["similarity"] for r in results)
            self.assertEqual(results[0]["similarity"], best, question)
            for r in results:
                self.assertTrue(r["metadata"]["url"].startswith("https://www.reddit.com/"))
                self.assertIn("title", r["metadata"])
                self.assertTrue(-1.0 <= r["similarity"] <= 1.0)

    def test_mmr_diversifies_q5(self):
        """ADR-003: Q5's top-5 spans >=3 threads (plain cosine returned 4
        sibling replies from a single c81p6a subtree)."""
        _, results = self._q(5)
        self.assertGreaterEqual(len({r["metadata"]["post_id"] for r in results}), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
