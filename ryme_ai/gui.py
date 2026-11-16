"""Fenêtre de chat de RYME AI (tkinter, aucune dépendance externe)."""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from . import __version__
from .agent import Agent
from .history import History
from .memory import Memory
from .llm import DEFAULT_HOST, DEFAULT_MODEL, OllamaClient, OllamaError
from .tools import Workspace

BG, PANEL, FG, MUTED, ACCENT = "#14161a", "#1d2026", "#e6e6e6", "#8a8f98", "#6c8cff"


class ChatApp:
    def __init__(self, root: tk.Tk, directory: str | None = None):
        self.root = root
        self.directory = directory or os.getcwd()
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.agent: Agent | None = None
        self.agent_key = None
        self.pending_restore: dict | None = None  # discussion à reprendre au prochain message
        self._imgs: list = []  # références pour que tkinter ne libère pas les images

        root.title(f"RYME AI {__version__}")
        root.geometry("900x680")
        root.configure(bg=BG)
        self._build()
        self._append("RYME AI", f"Bonjour ! Dossier de travail : {self.directory}\n"
                     "Demande-moi de lire, créer ou modifier des fichiers, ou de lancer des commandes.",
                     "ai")
        self.root.after(100, self._pump)

    # ---------- interface ----------
    def _build(self):
        top = tk.Frame(self.root, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text="Modèle", bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 4), pady=8)
        self.model_var = tk.StringVar(value=os.environ.get("RYME_MODEL", DEFAULT_MODEL))
        tk.Entry(top, textvariable=self.model_var, width=24, bg=BG, fg=FG,
                 insertbackground=FG, relief="flat").pack(side="left")
        self.dir_label = tk.Label(top, text=self.directory, bg=PANEL, fg=MUTED, anchor="w")
        self.dir_label.pack(side="left", padx=12, fill="x", expand=True)
        tk.Button(top, text="Dossier…", command=self._choose_dir, bg=BG, fg=FG,
                  relief="flat", activebackground=PANEL).pack(side="right", padx=4)
        tk.Button(top, text="Discussions…", command=self._show_discussions, bg=BG, fg=FG,
                  relief="flat", activebackground=PANEL).pack(side="right", padx=4)
        tk.Button(top, text="Nouvelle discussion", command=self._reset, bg=BG, fg=FG,
                  relief="flat", activebackground=PANEL).pack(side="right", padx=4)

        self.chat = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled", bg=BG, fg=FG, relief="flat",
            font=("Segoe UI", 11), padx=14, pady=10, borderwidth=0)
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("user", foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("ai", foreground=FG)
        self.chat.tag_config("who", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        self.chat.tag_config("tool", foreground=MUTED, font=("Consolas", 9))
        self.chat.tag_config("err", foreground="#ff7b7b")

        bottom = tk.Frame(self.root, bg=PANEL)
        bottom.pack(fill="x")
        self.input = tk.Text(bottom, height=3, wrap="word", bg=BG, fg=FG, relief="flat",
                             insertbackground=FG, font=("Segoe UI", 11), padx=8, pady=6)
        self.input.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.input.bind("<Return>", self._on_enter)
        self.send_btn = tk.Button(bottom, text="Envoyer", command=self._send, bg=ACCENT, fg="white",
                                  relief="flat", padx=16, pady=8)
        self.send_btn.pack(side="right", padx=(0, 10))
        self.input.focus_set()

    def _append(self, who: str, text: str, tag: str):
        self.chat.configure(state="normal")
        if who:
            self.chat.insert("end", f"{who}\n", "who")
        self.chat.insert("end", text.rstrip() + "\n\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _show_image(self, rel_path: str):
        try:
            img = tk.PhotoImage(file=os.path.join(self.directory, rel_path))
            factor = max(1, -(-img.width() // 512))  # réduction entière pour tenir dans le chat
            img = img.subsample(factor, factor)
            self._imgs.append(img)
            self.chat.configure(state="normal")
            self.chat.image_create("end", image=img)
            self.chat.insert("end", "\n\n")
            self.chat.configure(state="disabled")
            self.chat.see("end")
        except Exception as exc:
            self._append("", f"(aperçu impossible : {exc})", "tool")

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.directory, title="Dossier de travail")
        if d:
            self.directory = d
            self.dir_label.config(text=d)
            self.agent = None  # nouvelle session dans le nouveau dossier

    def _reset(self):
        if self.busy:
            return
        self.agent = None
        self.pending_restore = None
        self._clear_chat()
        self._append("RYME AI", "Nouvelle discussion.", "ai")

    def _clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _open_saved(self, saved: dict):
        if saved["directory"] and os.path.isdir(saved["directory"]):
            self.directory = saved["directory"]
            self.dir_label.config(text=self.directory)
        self.agent = None
        self.pending_restore = saved
        self._clear_chat()
        self._append("RYME AI", f"Discussion reprise. Dossier de travail : {self.directory}", "ai")
        for m in saved["messages"]:
            if m.get("role") == "user":
                self._append("Vous", m.get("content", ""), "user")
            elif m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
                self._append("RYME AI", m["content"], "ai")

    def _current_session_id(self):
        if self.pending_restore:
            return self.pending_restore["id"]
        return self.agent.session_id if self.agent else None

    def _show_discussions(self):
        if self.busy:
            return
        history = History()
        win = tk.Toplevel(self.root)
        win.title("Discussions")
        win.geometry("640x360")
        win.configure(bg=BG)
        listbox = tk.Listbox(win, bg=PANEL, fg=FG, selectbackground=ACCENT, relief="flat",
                             activestyle="none", font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, padx=10, pady=10)
        items: list[dict] = []

        def refresh():
            items[:] = history.list()
            listbox.delete(0, "end")
            for d in items:
                when = time.strftime("%d/%m/%Y %H:%M", time.localtime(d["updated"]))
                listbox.insert("end", f"{when}   {d['title']}   ({d['count']} échange(s))")
            if not items:
                listbox.insert("end", "Aucune discussion sauvegardée.")

        def selected():
            sel = listbox.curselection()
            return items[sel[0]] if sel and items else None

        def open_it(_event=None):
            d = selected()
            if d:
                win.destroy()
                self._open_saved(d)

        def delete_it():
            d = selected()
            if not d:
                return
            if d["id"] == self._current_session_id():
                messagebox.showinfo("RYME AI", "Cette discussion est en cours : impossible de la supprimer.",
                                    parent=win)
            elif messagebox.askyesno("Supprimer", f"Supprimer « {d['title']} » ?", parent=win):
                history.delete(d["id"])
                refresh()

        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(buttons, text="Ouvrir", command=open_it, bg=ACCENT, fg="white",
                  relief="flat", padx=14, pady=4).pack(side="left")
        tk.Button(buttons, text="Supprimer", command=delete_it, bg=PANEL, fg=FG,
                  relief="flat", padx=14, pady=4).pack(side="left", padx=8)
        tk.Button(buttons, text="Fermer", command=win.destroy, bg=PANEL, fg=FG,
                  relief="flat", padx=14, pady=4).pack(side="right")
        listbox.bind("<Double-Button-1>", open_it)
        refresh()

    def _show_image(self, rel_path: str):
        try:
            img = tk.PhotoImage(file=os.path.join(self.directory, rel_path))
            factor = max(1, -(-img.width() // 512))  # réduction entière pour tenir dans le chat
            img = img.subsample(factor, factor)
            self._imgs.append(img)
            self.chat.configure(state="normal")
            self.chat.image_create("end", image=img)
            self.chat.insert("end", "\n\n")
            self.chat.configure(state="disabled")
            self.chat.see("end")
        except Exception as exc:
            self._append("", f"(aperçu impossible : {exc})", "tool")

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.directory, title="Dossier de travail")
        if d:
            self.directory = d
            self.dir_label.config(text=d)
            self.agent = None  # nouvelle session dans le nouveau dossier

    def _reset(self):
        if self.busy:
            return
        self.agent = None
        self.pending_restore = None
        self._clear_chat()
        self._append("RYME AI", "Nouvelle discussion.", "ai")

    def _clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def _resume(self):
        if self.busy:
            return
        saved = History().latest()
        if not saved:
            messagebox.showinfo("RYME AI", "Aucune discussion sauvegardée.")
            return
        if saved["directory"] and os.path.isdir(saved["directory"]):
            self.directory = saved["directory"]
            self.dir_label.config(text=self.directory)
        self.agent = None
        self.pending_restore = saved
        self._clear_chat()
        self._append("RYME AI", f"Discussion reprise. Dossier de travail : {self.directory}", "ai")
        for m in saved["messages"]:
            if m.get("role") == "user":
                self._append("Vous", m.get("content", ""), "user")
            elif m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
                self._append("RYME AI", m["content"], "ai")

    # ---------- envoi ----------
    def _on_enter(self, event):
        if event.state & 0x1:  # Maj+Entrée : saut de ligne
            return None
        self._send()
        return "break"

    def _send(self):
        text = self.input.get("1.0", "end").strip()
        if not text or self.busy:
            return
        self.input.delete("1.0", "end")
        self._append("Vous", text, "user")
        self._set_busy(True)
        threading.Thread(target=self._work, args=(text,), daemon=True).start()

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.send_btn.config(state="disabled" if busy else "normal",
                             text="Réflexion…" if busy else "Envoyer")

    # ---------- thread de travail ----------
    def _get_agent(self) -> Agent:
        model = self.model_var.get().strip() or DEFAULT_MODEL
        key = (model, self.directory)
        if self.agent is None or self.agent_key != key:
            previous = self.agent  # même dossier, autre modèle : on garde la discussion
            llm = OllamaClient(host=os.environ.get("OLLAMA_HOST", DEFAULT_HOST), model=model)
            if not llm.is_up():
                raise OllamaError("Ollama ne répond pas. Installe-le depuis https://ollama.com, "
                                  f"lance-le, puis exécute : ollama pull {model}")
            ws = Workspace(self.directory, confirm=self._confirm_from_thread, memory=Memory())
            self.agent = Agent(llm, ws, on_tool=lambda n, a, r: self.events.put(("tool", n, a, r)),
                               history=History())
            if self.pending_restore:
                self.agent.restore(self.pending_restore["id"], self.pending_restore["messages"])
                self.pending_restore = None
            elif previous is not None and self.agent_key and self.agent_key[1] == self.directory:
                self.agent.restore(previous.session_id, previous.messages[1:])
            self.agent_key = key
        return self.agent

    def _confirm_from_thread(self, description: str) -> bool:
        done, result = threading.Event(), []
        self.events.put(("confirm", description, done, result))
        done.wait()
        return bool(result and result[0])

    def _work(self, text: str):
        try:
            self.events.put(("answer", self._get_agent().ask(text)))
        except OllamaError as exc:
            self.events.put(("error", str(exc)))
        except Exception as exc:
            self.events.put(("error", f"Erreur inattendue : {exc}"))

    # ---------- événements vers l'interface ----------
    def _pump(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "answer":
                    self._append("RYME AI", ev[1] or "(réponse vide)", "ai")
                    self._set_busy(False)
                elif kind == "error":
                    self._append("", ev[1], "err")
                    self._set_busy(False)
                elif kind == "tool":
                    _, name, args, result = ev
                    first = (result.splitlines() or [""])[0][:100]
                    self._append("", f"🔧 {name}({', '.join(args)}) → {first}", "tool")
                    if name in ("generate_image", "edit_image", "edit_image_zone") and result.startswith("Image créée : "):
                        self._show_image(result.split(" : ", 1)[1].strip())
                elif kind == "confirm":
                    _, desc, done, result = ev
                    result.append(messagebox.askyesno("Autoriser cette action ?", desc))
                    done.set()
        except queue.Empty:
            pass
        self.root.after(100, self._pump)


def main(directory: str | None = None):
    root = tk.Tk()
    ChatApp(root, directory)
    root.mainloop()


if __name__ == "__main__":
    main()
