"""
main.py — Orchestrateur du pipeline Xpermanip Content Engine
=============================================================
Exécute les 6 étapes de production d'une fiche pédagogique :

    Étape 1 — Input       : Scan des fichiers dans input/<specialty>/<theme>/
    Étape 2 — Parsing     : Extraction du texte brut de chaque document
    Étape 3 — Nettoyage   : Normalisation et suppression des artefacts
    Étape 4 — Fusion      : Regroupement des textes nettoyés par thème
    Étape 5 — Génération  : Production de la fiche via Claude (IA)
    Étape 6 — Export      : Sauvegarde Markdown + optionnel Canva / Notion

Usage :
    # Un thème précis
    python -m pipeline.main --specialty scanner --theme embolie_pulmonaire

    # Toute une spécialité
    python -m pipeline.main --specialty scanner

    # Lister les thèmes disponibles
    python -m pipeline.main --list

    # Activer l'export Canva et/ou Notion
    python -m pipeline.main --specialty scanner --theme dissection_aortique \\
        --export-canva --export-notion
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins racine du projet (relatifs à l'endroit où on lance le script)
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).resolve().parent.parent
INPUT_DIR   = ROOT / "input"
PARSED_DIR  = ROOT / "parsed"
CLEANED_DIR = ROOT / "cleaned"
OUTPUT_DIR  = ROOT / "outputs" / "markdown"
LOG_DIR     = ROOT / "logs"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="xpermanip",
        description="Xpermanip Content Engine — Générateur de fiches pédagogiques MERM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--specialty", "-s",
        type=str,
        help="Spécialité à traiter (ex: scanner). Correspond à un sous-dossier de input/.",
    )
    parser.add_argument(
        "--theme", "-t",
        type=str,
        default=None,
        help="Thème précis (ex: embolie_pulmonaire). Sans cet argument, tous les thèmes sont traités.",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Affiche les spécialités et thèmes disponibles dans input/.",
    )
    parser.add_argument(
        "--export-canva",
        action="store_true",
        help="Génère aussi un export HTML/JSON Canva dans outputs/canva/.",
    )
    parser.add_argument(
        "--export-notion",
        action="store_true",
        help="Publie la fiche dans Notion (nécessite NOTION_TOKEN et NOTION_DATABASE_ID).",
    )
    parser.add_argument(
        "--skip-parse",
        action="store_true",
        help="Sauter les étapes 1-3 (utilise les fichiers déjà présents dans cleaned/).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Étapes du pipeline
# ---------------------------------------------------------------------------

def step_scan(specialty: str, theme: str) -> list[Path]:
    """Étape 1 — Scan : liste les fichiers sources du thème."""
    theme_path = INPUT_DIR / specialty / theme
    if not theme_path.exists():
        print(f"  [ERREUR] Dossier introuvable : {theme_path}")
        return []

    files = [
        f for f in sorted(theme_path.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print(f"  [WARN] Aucun fichier supporté dans {theme_path}")
    else:
        print(f"  [1/6] {len(files)} fichier(s) trouvé(s) : {[f.name for f in files]}")

    return files


def step_parse(files: list[Path], specialty: str, theme: str) -> dict[str, str]:
    """Étape 2 — Parsing : extrait le texte brut de chaque fichier."""
    from parsers.document_parser import parse

    parsed: dict[str, str] = {}
    out_dir = PARSED_DIR / specialty / theme
    out_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        try:
            text = parse(f)
            dest = out_dir / f"{f.stem}.txt"
            dest.write_text(text, encoding="utf-8")
            parsed[f.name] = text
            print(f"  [2/6] Parsé : {f.name} → {dest.relative_to(ROOT)}")
        except Exception as exc:
            print(f"  [WARN] Échec parsing {f.name} : {exc}")

    return parsed


def step_clean(parsed: dict[str, str], specialty: str, theme: str) -> dict[str, str]:
    """Étape 3 — Nettoyage : normalise chaque texte brut."""
    from parsers.document_parser import clean

    cleaned: dict[str, str] = {}
    out_dir = CLEANED_DIR / specialty / theme
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, text in parsed.items():
        c = clean(text)
        dest = out_dir / Path(name).with_suffix(".txt").name
        dest.write_text(c, encoding="utf-8")
        cleaned[name] = c
        print(f"  [3/6] Nettoyé : {name} ({len(c)} caractères)")

    return cleaned


def step_load_cleaned(specialty: str, theme: str) -> dict[str, str]:
    """Variante étape 3 : charge les fichiers nettoyés existants (--skip-parse)."""
    cleaned_path = CLEANED_DIR / specialty / theme
    if not cleaned_path.exists():
        raise FileNotFoundError(
            f"Dossier cleaned/ introuvable : {cleaned_path}\n"
            "Lancez d'abord sans --skip-parse."
        )
    result = {}
    for f in sorted(cleaned_path.glob("*.txt")):
        result[f.name] = f.read_text(encoding="utf-8")
        print(f"  [3/6] Chargé (cache) : {f.name}")
    return result


def step_merge(cleaned: dict[str, str]) -> str:
    """Étape 4 — Fusion : concatène les textes nettoyés en un seul bloc."""
    sep = "\n\n" + "=" * 60 + "\n"
    parts = [
        f"{sep}SOURCE : {name}\n{'=' * 60}\n\n{text}"
        for name, text in cleaned.items()
    ]
    merged = "\n".join(parts)
    print(f"  [4/6] Fusion de {len(cleaned)} source(s) — {len(merged)} caractères au total")
    return merged


def step_generate(
    merged: str,
    theme: str,
    specialty: str,
    source_names: list[str],
) -> str:
    """Étape 5 — Génération : appelle Claude pour produire la fiche Markdown."""
    from pipeline.fiche_generator import generate_fiche

    print(f"  [5/6] Génération IA de la fiche '{theme}'...")
    fiche = generate_fiche(
        merged_text=merged,
        theme=theme,
        specialty=specialty,
        source_files=source_names,
        verbose=True,
    )
    print(f"  [5/6] Fiche générée ({len(fiche)} caractères)")
    return fiche


def step_export(
    fiche_md: str,
    theme: str,
    specialty: str,
    source_names: list[str],
    *,
    export_canva: bool,
    export_notion: bool,
) -> Path:
    """Étape 6 — Export : sauvegarde Markdown + exports optionnels."""
    # Markdown
    md_dir = OUTPUT_DIR / specialty
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{theme}.md"
    md_path.write_text(fiche_md, encoding="utf-8")
    print(f"  [6/6] Markdown sauvegardé : {md_path.relative_to(ROOT)}")

    # Export Canva (optionnel)
    if export_canva:
        from pipeline.canva_exporter import export_to_canva
        canva_path = export_to_canva(fiche_md, theme, specialty)
        print(f"  [6/6] Canva export : {canva_path.relative_to(ROOT)}")

    # Export Notion (optionnel)
    if export_notion:
        from pipeline.notion_exporter import export_to_notion
        notion_url = export_to_notion(fiche_md, theme, specialty)
        if notion_url:
            print(f"  [6/6] Notion page créée : {notion_url}")
        else:
            print("  [6/6] Export Notion ignoré (NOTION_TOKEN manquant).")

    return md_path


# ---------------------------------------------------------------------------
# Orchestrateur principal
# ---------------------------------------------------------------------------

def run_pipeline(
    specialty: str,
    theme: str,
    *,
    skip_parse: bool = False,
    export_canva: bool = False,
    export_notion: bool = False,
) -> Path | None:
    """
    Exécute le pipeline complet pour une spécialité + thème donnés.

    Returns:
        Path vers la fiche Markdown générée, ou None en cas d'échec.
    """
    start = time.time()
    print(f"\n{'─' * 55}")
    print(f"  Thème : {specialty} / {theme}")
    print(f"{'─' * 55}")

    try:
        if skip_parse:
            # Étapes 1-3 sautées : charge directement depuis cleaned/
            cleaned = step_load_cleaned(specialty, theme)
            source_names = list(cleaned.keys())
        else:
            files = step_scan(specialty, theme)
            if not files:
                return None

            parsed  = step_parse(files, specialty, theme)
            cleaned = step_clean(parsed, specialty, theme)
            source_names = [f.name for f in files]

        if not cleaned:
            print("  [ERREUR] Aucun texte nettoyé disponible.")
            return None

        merged   = step_merge(cleaned)
        fiche_md = step_generate(merged, theme, specialty, source_names)
        md_path  = step_export(
            fiche_md, theme, specialty, source_names,
            export_canva=export_canva,
            export_notion=export_notion,
        )

        elapsed = time.time() - start
        print(f"\n  ✓ Fiche prête pour validation ({elapsed:.1f}s)")
        print(f"  → {md_path}")
        _write_log(specialty, theme, source_names, md_path, elapsed)
        return md_path

    except KeyboardInterrupt:
        print("\n  [INTERROMPU] Pipeline arrêté par l'utilisateur.")
        return None
    except Exception as exc:
        print(f"\n  [ERREUR] Pipeline échoué pour {specialty}/{theme} : {exc}")
        return None


def list_themes() -> None:
    """Affiche les spécialités et thèmes disponibles dans input/."""
    if not INPUT_DIR.exists() or not any(INPUT_DIR.iterdir()):
        print("Aucune spécialité trouvée dans input/")
        print("Structure attendue : input/<specialite>/<theme>/fichiers...")
        return

    for specialty_path in sorted(INPUT_DIR.iterdir()):
        if not specialty_path.is_dir():
            continue
        print(f"\n{specialty_path.name}/")
        for theme_path in sorted(specialty_path.iterdir()):
            if not theme_path.is_dir():
                continue
            files = [
                f for f in theme_path.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            print(f"  └── {theme_path.name}/  ({len(files)} fichier(s))")


def _write_log(
    specialty: str,
    theme: str,
    sources: list[str],
    output: Path,
    elapsed: float,
) -> None:
    """Écrit une entrée dans le fichier de log du pipeline."""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "pipeline.log"
    entry = (
        f"{datetime.now().isoformat()} | {specialty}/{theme} | "
        f"{len(sources)} source(s) | {output.name} | {elapsed:.1f}s\n"
    )
    with log_file.open("a", encoding="utf-8") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.list:
        list_themes()
        return

    if not args.specialty:
        print("Erreur : --specialty requis. Voir --list pour les options disponibles.")
        print("Exemple : python -m pipeline.main --specialty scanner --theme embolie_pulmonaire")
        sys.exit(1)

    # Détecter les thèmes à traiter
    if args.theme:
        themes = [args.theme]
    else:
        specialty_path = INPUT_DIR / args.specialty
        if not specialty_path.exists():
            print(f"Erreur : spécialité '{args.specialty}' introuvable dans input/")
            sys.exit(1)
        themes = [
            d.name for d in sorted(specialty_path.iterdir()) if d.is_dir()
        ]
        if not themes:
            print(f"Aucun thème trouvé dans input/{args.specialty}/")
            sys.exit(1)

    print(f"\nXpermanip Content Engine")
    print(f"Spécialité : {args.specialty} | {len(themes)} thème(s) à traiter")

    results: list[Path] = []
    for theme in themes:
        path = run_pipeline(
            args.specialty,
            theme,
            skip_parse=args.skip_parse,
            export_canva=args.export_canva,
            export_notion=args.export_notion,
        )
        if path:
            results.append(path)

    print(f"\n{'=' * 55}")
    print(f"  {len(results)}/{len(themes)} fiche(s) générée(s) avec succès.")
    if results:
        print("  Fiches dans outputs/markdown/ — à valider avant publication.")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
