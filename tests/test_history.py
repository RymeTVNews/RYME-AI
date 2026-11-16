import json
import tempfile
import time
import unittest
from pathlib import Path

from ryme_ai.agent import Agent
from ryme_ai.history import History, MAX_MESSAGES, trim
from ryme_ai.tools import Workspace


class EchoLLM:
    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "ok: " + messages[-1]["content"]}


class HistoryTest(unittest.TestCase):
    def test_agent_saves_and_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            h = History(Path(d) / "h")
            a = Agent(EchoLLM(), Workspace(d), history=h)
            a.ask("bonjour")
            saved = h.latest()
            self.assertEqual([m["role"] for m in saved["messages"]], ["user", "assistant"])
            self.assertFalse(any(m["role"] == "system" for m in saved["messages"]))
            b = Agent(EchoLLM(), Workspace(d), history=h)
            b.restore(saved["id"], saved["messages"])
            b.ask("encore")
            again = h.latest()
            self.assertEqual(again["id"], saved["id"])  # même fichier, pas de doublon
            self.assertEqual(len(again["messages"]), 4)
            self.assertEqual(b.messages[0]["role"], "system")

    def test_trim_starts_on_user_message(self):
        msgs = []
        for i in range(MAX_MESSAGES):
            msgs += [{"role": "user", "content": str(i)}, {"role": "assistant", "content": "r"},
                     {"role": "tool", "content": "t"}]
        out = trim(msgs)
        self.assertLessEqual(len(out), MAX_MESSAGES)
        self.assertEqual(out[0]["role"], "user")

    def test_latest_skips_corrupted_files_and_picks_newest(self):
        with tempfile.TemporaryDirectory() as d:
            h = History(Path(d))
            h.save("old", [{"role": "user", "content": "a"}], "/x")
            time.sleep(0.02)
            h.save("new", [{"role": "user", "content": "b"}], "/x")
            time.sleep(0.02)
            (Path(d) / "broken.json").write_text("{pas du json", encoding="utf-8")
            self.assertEqual(h.latest()["id"], "new")

    def test_no_history_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(History(Path(d) / "vide").latest())


if __name__ == "__main__":
    unittest.main()
