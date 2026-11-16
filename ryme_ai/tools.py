"""Outils que l'agent peut utiliser (lecture/écriture de fichiers, commandes)."""

import subprocess
from pathlib import Path

from . import web

MAX_OUTPUT = 8000


class Workspace:
    """Dossier de travail : l'agent ne peut pas écrire en dehors."""

    def __init__(self, root: str | Path, confirm=None):
        self.root = Path(root).resolve()
        # confirm(description) -> bool ; par défaut tout est refusé pour les actions risquées
        self.confirm = confirm or (lambda _desc: False)

    def _resolve(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"Chemin en dehors du dossier de travail : {path}")
        return p

    def list_dir(self, path: str = ".") -> str:
        p = self._resolve(path)
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        return "\n".join(f"{e.name}{'/' if e.is_dir() else ''}" for e in entries) or "(vide)"

    def read_file(self, path: str) -> str:
        text = self._resolve(path).read_text(encoding="utf-8", errors="replace")
        return text[:MAX_OUTPUT] + ("\n...[tronqué]" if len(text) > MAX_OUTPUT else "")

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        if not self.confirm(f"Écrire le fichier {p} ({len(content)} caractères)"):
            return "Refusé par l'utilisateur."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Fichier écrit : {path}"

    def run_command(self, command: str) -> str:
        if not self.confirm(f"Exécuter la commande : {command}"):
            return "Refusé par l'utilisateur."
        try:
            res = subprocess.run(
                command, shell=True, cwd=self.root, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired:
            return "Commande interrompue (délai de 120 s dépassé)."
        out = (res.stdout + res.stderr)[:MAX_OUTPUT]
        return f"[code {res.returncode}]\n{out}"

    def call(self, name: str, args: dict) -> str:
        fn = {
            "list_dir": self.list_dir,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "run_command": self.run_command,
            "web_search": web.web_search,
            "fetch_url": web.fetch_url,
        }.get(name)
        if fn is None:
            return f"Outil inconnu : {name}"
        try:
            return fn(**args)
        except Exception as exc:  # l'erreur est renvoyée au modèle pour qu'il corrige
            return f"Erreur : {exc}"


def _tool(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOL_SPECS = [
    _tool("list_dir", "Liste le contenu d'un dossier.",
          {"path": {"type": "string", "description": "Chemin relatif"}}, []),
    _tool("read_file", "Lit un fichier texte.",
          {"path": {"type": "string"}}, ["path"]),
    _tool("write_file", "Crée ou remplace un fichier texte.",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("run_command", "Exécute une commande shell dans le dossier de travail.",
          {"command": {"type": "string"}}, ["command"]),
    _tool("web_search", "Cherche sur le web (informations récentes, documentation).",
          {"query": {"type": "string"}}, ["query"]),
    _tool("fetch_url", "Télécharge une page web et retourne son texte.",
          {"url": {"type": "string"}}, ["url"]),
]
