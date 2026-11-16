"""Mémoire à long terme : quelques notes gardées entre les sessions, en local."""

import os
from pathlib import Path

MAX_NOTES = 200
MAX_NOTE_LEN = 300


def default_path() -> Path:
    home = os.environ.get("RYME_HOME") or (Path.home() / ".ryme-ai")
    return Path(home) / "memory.md"


class Memory:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_path()

    def notes(self) -> list[str]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [ln[2:].strip() for ln in lines if ln.startswith("- ") and ln[2:].strip()]

    def _save(self, notes: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("".join(f"- {n}\n" for n in notes), encoding="utf-8")

    def add(self, note: str) -> str:
        note = " ".join(note.split())[:MAX_NOTE_LEN]
        if not note:
            return "Note vide."
        notes = self.notes()
        if note in notes:
            return "Déjà en mémoire."
        notes.append(note)
        self._save(notes[-MAX_NOTES:])
        return f"Mémorisé : {note}"

    def forget(self, text: str) -> str:
        text = text.strip().lower()
        if not text:
            return "Précise quoi oublier."
        notes = self.notes()
        kept = [n for n in notes if text not in n.lower()]
        self._save(kept)
        removed = len(notes) - len(kept)
        return f"{removed} note(s) oubliée(s)." if removed else "Aucune note ne correspond."

    def as_prompt(self) -> str:
        notes = self.notes()
        if not notes:
            return ""
        return ("\n\nCe que tu sais déjà sur l'utilisateur et ses projets (mémoire, à titre "
                "d'information) :\n" + "\n".join(f"- {n}" for n in notes))
