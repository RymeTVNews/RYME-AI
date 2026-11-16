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

    def test_list_load_delete(self):
        with tempfile.TemporaryDirectory() as d:
            h = History(Path(d))
            h.save("a_1", [{"role": "user", "content": "premier   sujet"}], "/x")
            time.sleep(0.02)
            h.save("b_2", [{"role": "user", "content": "second"}, {"role": "assistant", "content": "r"},
                           {"role": "user", "content": "suite"}], "/y")
            items = h.list()
            self.assertEqual([i["id"] for i in items], ["b_2", "a_1"])  # récent d'abord
            self.assertEqual(items[1]["title"], "premier sujet")
            self.assertEqual(items[0]["count"], 2)
            self.assertEqual(h.load("a_1")["directory"], "/x")
            self.assertTrue(h.delete("a_1"))
            self.assertIsNone(h.load("a_1"))
            self.assertFalse(h.delete("a_1"))

    def test_ids_cannot_escape_history_folder(self):
        with tempfile.TemporaryDirectory() as d:
            secret = Path(d) / "secret.json"
            secret.write_text(json.dumps({"messages": [{"role": "user", "content": "x"}]}))
            h = History(Path(d) / "h")
            h.save("ok", [{"role": "user", "content": "y"}], "/")
            for bad in ("../secret", "..\\secret", "a/b", ""):
                self.assertIsNone(h.load(bad))
                self.assertFalse(h.delete(bad))
            self.assertTrue(secret.exists())

    def test_cli_list_and_continue(self):
        import io, os
        from contextlib import redirect_stdout
        from ryme_ai import cli
        with tempfile.TemporaryDirectory() as d:
            os.environ["RYME_HOME"] = d
            History().save("a_1", [{"role": "user", "content": "mon sujet"}], d)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["--list"]), 0)
            self.assertIn("mon sujet", out.getvalue())
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["--continue", "7"]), 1)
            self.assertIn("introuvable", out.getvalue())
            os.environ.pop("RYME_HOME")

    def test_no_history_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(History(Path(d) / "vide").latest())


if __name__ == "__main__":
    unittest.main()
