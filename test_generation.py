"""M5 verification as executable tests (stdlib unittest, Groq fully mocked).

No test here makes a network call: the Groq client is never constructed
(generation._complete is stubbed), and retrieval runs against the local
ChromaDB index + cached sentence-transformers model, exactly like the M4
suite. The live half of the M5 verification (answer spot-checks, the
contradiction question, the leak-probe red-team) lives in
`generation.py.__main__` because it needs a real GROQ_API_KEY.

    .venv/bin/python -m unittest -v test_generation
"""

from __future__ import annotations

import unittest
from unittest import mock

import generation
import retrieval

OFF_DOMAIN_QUERY = "Best hiking trails near Yosemite?"
IN_CORPUS_QUERY = "What do students say about Professor Adel Atta?"

_collection = None


def setUpModule():
    global _collection
    _collection = retrieval.build_index()


class TestFloorGateRefusal(unittest.TestCase):
    """The refusal path must never touch the Groq API."""

    def test_off_domain_probe_refused_without_api_call(self):
        stub = mock.Mock()
        with mock.patch.object(generation, "_complete", stub):
            out = generation.generate_answer(OFF_DOMAIN_QUERY, collection=_collection)
        stub.assert_not_called()
        self.assertTrue(out["refused"])
        self.assertFalse(out["api_called"])
        self.assertEqual(out["sources"], [])
        self.assertIn("the corpus doesn't cover this", out["answer"])

    def test_canonical_probe_refused_without_api_call(self):
        stub = mock.Mock()
        with mock.patch.object(generation, "_complete", stub):
            out = generation.generate_answer(
                retrieval.OUT_OF_CORPUS_PROBE, collection=_collection
            )
        stub.assert_not_called()
        self.assertTrue(out["refused"])
        self.assertFalse(out["api_called"])


class TestGroundedPrompt(unittest.TestCase):
    """Prompt construction: grounding rules + every retrieved chunk, numbered."""

    def _run(self, reply="Students warn about him [1][2]."):
        stub = mock.Mock(return_value=reply)
        with mock.patch.object(generation, "_complete", stub):
            out = generation.generate_answer(IN_CORPUS_QUERY, collection=_collection)
        return out, stub

    def test_system_prompt_carries_grounding_rules(self):
        _, stub = self._run()
        system = stub.call_args.args[0][0]
        self.assertEqual(system["role"], "system")
        self.assertIn("ONLY", system["content"])
        self.assertIn(generation.NOT_IN_CORPUS, system["content"])
        self.assertIn("report both sides", system["content"])
        self.assertIn("Cite the excerpt number", system["content"])

    def test_user_message_contains_every_chunk_numbered(self):
        out, stub = self._run()
        user = stub.call_args.args[0][1]
        self.assertEqual(user["role"], "user")
        self.assertEqual(len(out["results"]), retrieval.TOP_K)
        for n, r in enumerate(out["results"], 1):
            self.assertIn(f"[{n}]", user["content"])
            self.assertIn(r["text"], user["content"])
        self.assertIn(IN_CORPUS_QUERY, user["content"])

    def test_urls_never_enter_the_prompt(self):
        # Citations map [n] -> URL outside the model, so no URL should be
        # embedded for the model to mistype or invent variants of.
        out, stub = self._run()
        user = stub.call_args.args[0][1]
        for r in out["results"]:
            self.assertNotIn(r["metadata"]["url"], user["content"])

    def test_answer_passes_through_with_sources(self):
        out, _ = self._run()
        self.assertFalse(out["refused"])
        self.assertTrue(out["api_called"])
        self.assertEqual(out["answer"], "Students warn about him [1][2].")
        self.assertTrue(out["sources"])


class TestSentinelBackstop(unittest.TestCase):
    """The leak class (above-floor unknown professor) refuses via sentinel."""

    def test_sentinel_reply_maps_to_refusal_message(self):
        stub = mock.Mock(return_value=generation.NOT_IN_CORPUS)
        with mock.patch.object(generation, "_complete", stub):
            out = generation.generate_answer(retrieval.LEAK_PROBE, collection=_collection)
        stub.assert_called_once()  # above the floor, so the API path runs
        self.assertTrue(out["refused"])
        self.assertEqual(out["sources"], [])
        self.assertIn("the corpus doesn't cover this", out["answer"])


class TestSourceMapping(unittest.TestCase):
    """Cited URLs are exactly the retrieved threads — never model-authored."""

    def test_sources_unique_and_drawn_from_results(self):
        stub = mock.Mock(return_value="ok [1].")
        with mock.patch.object(generation, "_complete", stub):
            out = generation.generate_answer(IN_CORPUS_QUERY, collection=_collection)
        retrieved_urls = {r["metadata"]["url"] for r in out["results"]}
        post_ids = [s["post_id"] for s in out["sources"]]
        self.assertEqual(len(post_ids), len(set(post_ids)))
        for s in out["sources"]:
            self.assertIn(s["url"], retrieved_urls)
        cited = sorted(n for s in out["sources"] for n in s["excerpts"])
        self.assertEqual(cited, list(range(1, len(out["results"]) + 1)))


class TestRefusalMessage(unittest.TestCase):
    def test_contains_planning_md_phrase(self):
        self.assertIn("the corpus doesn't cover this", generation.REFUSAL_MESSAGE)


if __name__ == "__main__":
    unittest.main()
