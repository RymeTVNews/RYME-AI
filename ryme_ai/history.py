"""Historique des conversations : une discussion = un fichier JSON local."""

import json
import os
import re
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

    @staticmethod
    def valid_id(session_id: str) -> bool:
        """Évite qu'un identifiant sorte du dossier d'historique."""
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", session_id or ""))

    def _read(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # fichier abîmé : ignoré
        msgs = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(msgs, list) or not msgs:
            return None
        users = [m for m in msgs if isinstance(m, dict) and m.get("role") == "user"]
        title = " ".join(str(users[0].get("content", "")).split())[:60] if users else "(sans titre)"
        return {"id": path.stem, "directory": data.get("directory", ""), "messages": msgs,
                "title": title, "count": len(users), "updated": path.stat().st_mtime}

    def list(self) -> list[dict]:
        """Toutes les discussions, la plus récente d'abord."""
        if not self.base.exists():
            return []
        files = sorted(self.base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [d for d in (self._read(p) for p in files) if d]

    def load(self, session_id: str) -> dict | None:
        if not self.valid_id(session_id):
            return None
        path = self.base / f"{session_id}.json"
        return self._read(path) if path.exists() else None

    def delete(self, session_id: str) -> bool:
        if not self.valid_id(session_id):
            return False
        path = self.base / f"{session_id}.json"
        try:
            path.unlink()
            return True
        except OSError:
            return False

    def latest(self) -> dict | None:
        """Dernière discussion ou None."""
        found = self.list()
        return found[0] if found else None
