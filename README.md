# Xpermanip Content Engine

Outil local de production de fiches pédagogiques pour le projet **Xpermanip**.

Destiné aux formateurs et étudiants **MERM** (Manipulateurs En Électroradiologie Médicale).

---

## Objectif

Transformer des supports de cours bruts (PDF, DOCX, PPTX, TXT) en fiches pédagogiques
homogènes au format Markdown, prêtes pour relecture et publication dans Notion.

Le système **ne copie pas** les sources : il synthétise, réécrit et structure.
**La validation humaine est obligatoire** avant toute diffusion.

---

## Architecture du projet

```
xpermanip-content-engine/
├── input/                        # Sources brutes (organisées par spécialité/thème)
│   └── scanner/
│       └── embolie_pulmonaire/
│           ├── cours_A.pdf
│           └── cours_B.docx
├── parsed/                       # Texte brut extrait (généré automatiquement)
├── cleaned/                      # Texte nettoyé (généré automatiquement)
├── outputs/
│   └── markdown/                 # Fiches Markdown générées
├── templates/
│   └── fiche_template.md         # Template obligatoire de fiche pédagogique
├── logs/                         # Fichiers de log
├── src/
│   ├── parsers/
│   │   ├── base_parser.py        # Classe abstraite commune
│   │   ├── pdf_parser.py         # Parseur PDF (pdfplumber)
│   │   ├── docx_parser.py        # Parseur Word (python-docx)
│   │   ├── pptx_parser.py        # Parseur PowerPoint (python-pptx)
│   │   └── txt_parser.py         # Parseur texte brut
│   ├── cleaner.py                # Nettoyage et normalisation du texte
│   ├── theme_manager.py          # Regroupement des sources par thème
│   ├── sheet_generator.py        # Génération de la fiche Markdown
│   └── utils.py                  # Utilitaires partagés (logger, router, helpers)
├── main.py                       # Point d'entrée CLI
├── config.yaml                   # Configuration du projet
└── requirements.txt
```

---

## Fichiers Python — Rôle de chacun

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée CLI, orchestre le pipeline complet |
| `src/parsers/base_parser.py` | Classe abstraite dont héritent tous les parseurs |
| `src/parsers/pdf_parser.py` | Extrait le texte d'un PDF page par page |
| `src/parsers/docx_parser.py` | Extrait les paragraphes d'un fichier Word |
| `src/parsers/pptx_parser.py` | Extrait les diapositives et notes d'un PowerPoint |
| `src/parsers/txt_parser.py` | Lit un fichier texte brut avec gestion d'encodage |
| `src/cleaner.py` | Nettoie et normalise les textes extraits |
| `src/theme_manager.py` | Gère les thèmes, liste les sources, fusionne les textes |
| `src/sheet_generator.py` | Génère la fiche pédagogique Markdown finale |
| `src/utils.py` | Logger, routeur de parseurs, helpers fichiers |

---

## Pipeline de traitement

```
input/scanner/embolie_pulmonaire/
        |
[Etape 1 - Parsing]     : PDFParser / DOCXParser / PPTXParser / TXTParser
        |
parsed/scanner/embolie_pulmonaire/*.txt
        |
[Etape 2 - Nettoyage]   : cleaner.py
        |
cleaned/scanner/embolie_pulmonaire/*.txt
        |
[Etape 3 - Fusion]      : theme_manager.py -> merge_sources()
        |
[Etape 4 - Generation]  : sheet_generator.py -> fiche Markdown
        |
outputs/markdown/scanner/embolie_pulmonaire.md
        |
[Validation humaine]    : relecture + corrections avant publication Notion
```

---

## Plan de développement MVP

### Phase 1 - Parseurs [Etape suivante]
- [ ] Implémenter `TXTParser.extract_text()`
- [ ] Implémenter `PDFParser.extract_text()` avec pdfplumber
- [ ] Implémenter `DOCXParser.extract_text()` avec python-docx
- [ ] Implémenter `PPTXParser.extract_text()` avec python-pptx
- [ ] Tester sur des fichiers réels du thème "scanner"

### Phase 2 - Nettoyage
- [ ] Implémenter toutes les fonctions de `cleaner.py`
- [ ] Tester et calibrer sur des textes extraits réels
- [ ] Valider que le nettoyage ne supprime pas de contenu utile

### Phase 3 - Gestion des thèmes
- [ ] Implémenter `ThemeManager` (list, get_sources, merge)
- [ ] Tester avec plusieurs fichiers d'un même thème

### Phase 4 - Génération de fiches
- [ ] Implémenter `SheetGenerator.generate()`
- [ ] Valider le respect du template obligatoire
- [ ] Tester la qualité éditoriale sur "embolie_pulmonaire"

### Phase 5 - CLI et polissage
- [ ] Implémenter `main.py` (argparse + orchestration)
- [ ] Tester le pipeline end-to-end
- [ ] Documenter les commandes d'usage

---

## Installation

```bash
# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# Installer les dépendances
pip install -r requirements.txt
```

---

## Usage (une fois implémenté)

```bash
# Lister les thèmes disponibles
python main.py --list

# Traiter un thème précis
python main.py --specialty scanner --theme embolie_pulmonaire

# Traiter tous les thèmes d'une spécialité
python main.py --specialty scanner

# N'exécuter que le parsing
python main.py --specialty scanner --theme dissection_aortique --step parse
```

---

## Structure des sources (input/)

Placer les fichiers sources dans le dossier correspondant :

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

## Template de fiche pédagogique

Chaque fiche générée contient **8 sections obligatoires** :

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
> Il accélère la fabrication, mais la qualité pédagogique finale reste sous responsabilité humaine.

---

*Projet Xpermanip — Formation MERM*
