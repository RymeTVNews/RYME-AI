"""Boucle d'agent : le modèle réfléchit, appelle des outils, puis répond."""

from .tools import TOOL_SPECS, Workspace

SYSTEM_PROMPT = (
    "Tu es RYME AI, un assistant de programmation qui tourne 100 % en local. "
    "Tu réponds en français. Tu disposes d'outils pour lister, lire et écrire des fichiers "
    "et exécuter des commandes dans le dossier de travail. Utilise-les pour accomplir la "
    "tâche plutôt que de deviner, puis résume brièvement ce que tu as fait."
)

MAX_STEPS = 12


class Agent:
    def __init__(self, llm, workspace: Workspace, on_tool=None):
        self.llm = llm
        self.workspace = workspace
        self.on_tool = on_tool or (lambda name, args, result: None)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def ask(self, text: str) -> str:
        self.messages.append({"role": "user", "content": text})
        for _ in range(MAX_STEPS):
            msg = self.llm.chat(self.messages, tools=TOOL_SPECS)
            self.messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content", "")
            for call in calls:
                fn = call.get("function", {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                result = self.workspace.call(name, args)
                self.on_tool(name, args, result)
                self.messages.append({"role": "tool", "content": result, "tool_name": name})
        return "Limite d'étapes atteinte sans réponse finale."
