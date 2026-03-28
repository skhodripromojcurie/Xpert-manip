# Xpermanip Content Engine

Outil local de production de fiches pédagogiques pour le projet **Xpermanip**.

Destiné aux formateurs et étudiants **MERM** (Manipulateurs En Électroradiologie Médicale).

---

## Objectif

Transformer des supports de cours bruts (PDF, DOCX, PPTX, TXT) en fiches pédagogiques
homogènes au format Markdown, via l'IA (Claude), prêtes pour relecture et publication.

Le système **ne copie pas** les sources : il synthétise, réécrit et structure.
**La validation humaine est obligatoire** avant toute diffusion.

---

## Architecture

```
xpermanip/
├── pipeline/
│   ├── main.py              Orchestrateur des 6 étapes (CLI)
│   ├── fiche_generator.py   Génération IA via Claude (claude-opus-4-6)
│   ├── canva_exporter.py    Mise en forme visuelle HTML + JSON Canva
│   └── notion_exporter.py   Export vers base Notion
├── parsers/
│   └── document_parser.py   Lit PDF / DOCX / PPTX / TXT + nettoyage
├── input/                   Sources brutes (organisées par spécialité/thème)
│   └── scanner/
│       ├── embolie_pulmonaire/
│       └── dissection_aortique/
├── parsed/                  Texte brut extrait (auto-généré)
├── cleaned/                 Texte nettoyé (auto-généré)
├── outputs/
│   ├── markdown/            Fiches Markdown générées
│   └── canva/               Exports HTML + JSON Canva
├── templates/
│   └── fiche_template.md    Template de référence (8 sections)
├── logs/
├── requirements.txt
└── README.md
```

---

## Fichiers Python

| Fichier | Rôle |
|---|---|
| `pipeline/main.py` | CLI + orchestration des 6 étapes |
| `pipeline/fiche_generator.py` | Appel Claude API, génération Markdown structurée |
| `pipeline/canva_exporter.py` | Export HTML visuel + JSON Bulk Create Canva |
| `pipeline/notion_exporter.py` | Création de pages Notion via API |
| `parsers/document_parser.py` | Extraction texte (PDF/DOCX/PPTX/TXT) + nettoyage |

---

## Pipeline (6 étapes)

```
input/scanner/embolie_pulmonaire/
        |
Etape 1 - Scan       : liste les fichiers sources du theme
        |
Etape 2 - Parsing    : document_parser.parse() -> parsed/
        |
Etape 3 - Nettoyage  : document_parser.clean() -> cleaned/
        |
Etape 4 - Fusion     : merge des textes nettoyes du theme
        |
Etape 5 - Generation : Claude claude-opus-4-6 -> fiche Markdown
        |
Etape 6 - Export     : outputs/markdown/ + Canva (opt.) + Notion (opt.)
        |
[Validation humaine] : relecture avant publication
```

---

## Installation

```bash
# Cloner le projet
git clone <url>
cd xpermanip-content-engine

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
.venv\Scripts\activate        # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer la clé API Claude (obligatoire)
export ANTHROPIC_API_KEY="sk-ant-..."   # Linux/Mac
set ANTHROPIC_API_KEY=sk-ant-...        # Windows

# Optionnel : export Notion
export NOTION_TOKEN="secret_..."
export NOTION_DATABASE_ID="xxxxxxxx..."
```

---

## Usage

```bash
# Lister les spécialités et thèmes disponibles
python -m pipeline.main --list

# Générer une fiche pour un thème précis
python -m pipeline.main --specialty scanner --theme embolie_pulmonaire

# Générer toutes les fiches d'une spécialité
python -m pipeline.main --specialty scanner

# Avec export Canva (HTML + JSON)
python -m pipeline.main --specialty scanner --theme embolie_pulmonaire --export-canva

# Avec export Notion
python -m pipeline.main --specialty scanner --theme embolie_pulmonaire --export-notion

# Sauter le parsing (utiliser les textes déjà nettoyés dans cleaned/)
python -m pipeline.main --specialty scanner --theme embolie_pulmonaire --skip-parse
```

---

## Structure des sources (input/)

```
input/
└── scanner/
    ├── embolie_pulmonaire/
    │   ├── cours_ifmem.pdf
    │   └── slides_DES.pptx
    └── dissection_aortique/
        └── fiche_chu.docx
```

---

## Template de fiche (8 sections)

1. **Titre**
2. **Objectif pédagogique**
3. **Notions clés**
4. **Explication structurée**
5. **Point terrain manipulateur**
6. **Erreurs fréquentes**
7. **Mini quiz**
8. **Résumé final**

---

## Philosophie

> Cet outil est un **assistant de production**, pas un auteur autonome.
> Il accélère la fabrication, mais la qualité pédagogique finale
> reste sous responsabilité humaine.

---

*Projet Xpermanip — Formation MERM*
