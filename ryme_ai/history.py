"""Historique des conversations : une discussion = un fichier JSON local."""

import json
import os
import time
from pathlib import Path

MAX_MESSAGES = 80  # au-delà, les plus anciens messages sont oubliés


def default_dir() -> Path:
    home = os.environ.get("RYME_HOME") or (Path.home() / ".ryme-ai")
    return Path(home) / "history"


def trim(messages: list[dict]) -> list[dict]:
    """Garde les derniers messages, en commençant par un message de l'utilisateur
    (un résultat d'outil sans son appel d'origine embrouillerait le modèle)."""
    kept = messages[-MAX_MESSAGES:]
    while kept and kept[0].get("role") != "user":
        kept = kept[1:]
    return kept


class History:
    def __init__(self, base: str | Path | None = None):
        self.base = Path(base) if base else default_dir()

    @staticmethod
    def new_id() -> str:
        return time.strftime("%Y%m%d_%H%M%S") + f"_{os.getpid()}"

    def save(self, session_id: str, messages: list[dict], directory: str) -> None:
        """Sauvegarde sans le message système (il est reconstruit à la reprise)."""
        convo = trim([m for m in messages if m.get("role") != "system"])
        if not convo:
            return
        self.base.mkdir(parents=True, exist_ok=True)
        path = self.base / f"{session_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"directory": directory, "messages": convo},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def latest(self) -> dict | None:
        """Dernière discussion : {'id', 'directory', 'messages'} ou None."""
        files = sorted(self.base.glob("*.json"), key=lambda p: p.stat().st_mtime) if self.base.exists() else []
        for path in reversed(files):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data.get("messages"), list) and data["messages"]:
                    return {"id": path.stem, "directory": data.get("directory", ""),
                            "messages": data["messages"]}
            except (OSError, ValueError):
                continue  # fichier abîmé : on regarde le précédent
        return None
