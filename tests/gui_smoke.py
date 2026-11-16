"""Test d'interface (nécessite tkinter et un écran) : lancé par GitHub Actions sur Windows.

Simule un glissement de souris sur une image du chat et vérifie que le bloc [zone : ...]
arrive dans le champ de saisie.
"""

import os
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ryme_ai import images  # noqa: E402
from ryme_ai.gui import ChatApp  # noqa: E402

workdir = tempfile.mkdtemp()
os.makedirs(os.path.join(workdir, "images"))
with open(os.path.join(workdir, "images", "t.png"), "wb") as f:
    f.write(images.make_mask(600, 400, 0.2, 0.2, 0.8, 0.8))  # PNG valide, réduit à 300x200

root = tk.Tk()
app = ChatApp(root, workdir)
app._show_image("images/t.png")
root.update()

canvases = [w for w in app.chat.winfo_children() if isinstance(w, tk.Canvas)]
assert len(canvases) == 1, "le canevas de l'image est absent du chat"
canvas = canvases[0]
assert (int(canvas["width"]), int(canvas["height"])) == (300, 200), "taille d'aperçu inattendue"

canvas.event_generate("<ButtonPress-1>", x=30, y=20)
canvas.event_generate("<B1-Motion>", x=150, y=100)
canvas.event_generate("<ButtonRelease-1>", x=150, y=100)
root.update()

text = app.input.get("1.0", "end").strip()
assert text == "[zone : images/t.png | left=0.100 top=0.100 right=0.500 bottom=0.500 | rectangle]", text

# un simple clic ne doit rien changer
app.input.delete("1.0", "end")
canvas.event_generate("<ButtonPress-1>", x=200, y=150)
canvas.event_generate("<ButtonRelease-1>", x=200, y=150)
root.update()
assert app.input.get("1.0", "end").strip() == "", "un clic simple a créé une zone"

root.destroy()
print("GUI smoke test OK")
