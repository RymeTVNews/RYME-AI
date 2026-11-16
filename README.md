# RYME AI

Agent IA **100 % local** pour Windows : il discute, lit et écrit des fichiers et lance des commandes dans un dossier de travail, avec ta confirmation avant toute action risquée. Aucune donnée ne quitte ton PC.

## Installation (Windows, RTX 3080 Ti)

1. Installe [Ollama](https://ollama.com) et lance-le.
2. Télécharge un modèle (14B quantifié, tient dans 12 Go de VRAM) :
   `ollama pull qwen2.5-coder:14b`
3. Télécharge le build : onglet **Actions** du dépôt → dernier build → artefact `ryme-ai-windows` (ou page **Releases** pour une version taguée).
4. Double-clique `RYME-AI.exe` : la fenêtre de chat s'ouvre. Choisis ton dossier de travail avec le bouton « Dossier… ».
   (`ryme-ai-cli.exe` est la version terminal.)

**Recherche web** : l'agent peut chercher sur le web (DuckDuckGo, sans clé d'API) et lire des pages. Seules ses requêtes de recherche et les pages demandées sortent de ton PC ; le modèle reste local. Les adresses locales et privées sont bloquées.

**Images locales** : l'agent crée des images avec ta carte graphique (outil `generate_image`, fichiers PNG dans `images/` du dossier de travail, aperçu dans la fenêtre). Il faut un serveur d'images local :
1. Installe [Stable Diffusion WebUI Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) et un modèle (par exemple SDXL ou FLUX, adaptés à 12 Go de VRAM).
2. Lance-le avec l'option `--api` (ajoute `--api` à `COMMANDLINE_ARGS` dans `webui-user.bat`).
3. Demande par exemple : « Génère un logo de chat robot ». Adresse par défaut : `http://127.0.0.1:7860` (variable `RYME_IMAGE_HOST` pour la changer).

**Modifier une image** : outil `edit_image` (img2img) — par exemple « prends images/logo.png et passe-le en bleu ». L'image d'origine n'est jamais modifiée, le résultat est une nouvelle image dans `images/`. C'est une retransformation guidée par la description (pas une retouche ciblée comme Nano Banana) : l'agent règle la force du changement, de la retouche légère à la refonte.

**Mémoire entre sessions** : l'agent peut garder des notes durables (préférences, projets) dans `%USERPROFILE%\.ryme-ai\memory.md` et les relit à chaque démarrage. Chaque ajout (`remember`) ou suppression (`forget`) te demande confirmation, pour qu'une page web piégée ne puisse pas écrire dans ta mémoire. Tu peux aussi éditer le fichier à la main (une note par ligne, commençant par `- `). Variable `RYME_HOME` pour changer le dossier.

Options : `--model`, `--host`, `--dir`. Variables : `RYME_MODEL`, `OLLAMA_HOST`.

## Développement

```
python -m unittest discover -s tests
python run_gui.py   # fenêtre de chat
python run_cli.py   # terminal
```

Pour publier une version : `git tag v0.1.0 && git push --tags`.

## Feuille de route

- Retouche ciblée d'images (inpainting par zone)
- Historique des conversations sauvegardé entre sessions
- Installeur `.msi`
