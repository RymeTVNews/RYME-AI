import tempfile
import unittest

from ryme_ai.agent import Agent
from ryme_ai.tools import Workspace


class FakeLLM:
    """Simule un modèle : écrit un fichier, puis répond."""

    def __init__(self):
        self.step = 0

    def chat(self, messages, tools=None):
        self.step += 1
        if self.step == 1:
            return {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "write_file",
                              "arguments": {"path": "a.txt", "content": "salut"}}}]}
        return {"role": "assistant", "content": "Fait."}


class AgentTest(unittest.TestCase):
    def test_agent_writes_file_when_confirmed(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(d, confirm=lambda _: True)
            self.assertEqual(Agent(FakeLLM(), ws).ask("écris a.txt"), "Fait.")
            self.assertEqual(ws.read_file("a.txt"), "salut")

    def test_write_refused_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(d)
            self.assertIn("Refusé", ws.write_file("a.txt", "x"))

    def test_path_escape_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("Erreur", Workspace(d).call("read_file", {"path": "../../etc/passwd"}))


if __name__ == "__main__":
    unittest.main()
