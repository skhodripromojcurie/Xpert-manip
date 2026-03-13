"""
document_parser.py
==================
Parseur unifié pour tous les formats de documents sources.

Formats supportés : PDF, DOCX, PPTX, TXT

Usage :
    from parsers.document_parser import parse, clean

    text = parse("cours_embolie.pdf")        # Extraction brute
    cleaned = clean(text)                    # Nettoyage
"""

import re
from pathlib import Path

# Extensions acceptées
SUPPORTED = {".pdf", ".docx", ".pptx", ".txt"}


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def parse(file_path: str | Path) -> str:
    """
    Extrait le texte brut d'un fichier selon son extension.

    Args:
        file_path: Chemin vers le fichier source.

    Returns:
        str: Texte brut extrait.

    Raises:
        FileNotFoundError: Fichier introuvable.
        ValueError: Format non supporté.
        RuntimeError: Document vide ou illisible.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(
            f"Format '{ext}' non supporté. Acceptés : {sorted(SUPPORTED)}"
        )

    parsers = {
        ".pdf":  _parse_pdf,
        ".docx": _parse_docx,
        ".pptx": _parse_pptx,
        ".txt":  _parse_txt,
    }
    return parsers[ext](path)


# ---------------------------------------------------------------------------
# Parseurs par format
# ---------------------------------------------------------------------------

def _parse_pdf(path: Path) -> str:
    """Extraction page par page via pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber requis : pip install pdfplumber")

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"\n--- Page {i} ---\n{text}")

    if not pages:
        raise RuntimeError(
            f"Aucun texte extractible dans '{path.name}'. "
            "Le PDF est peut-être scanné (image uniquement)."
        )
    return "\n".join(pages)


def _parse_docx(path: Path) -> str:
    """Extraction des paragraphes via python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx requis : pip install python-docx")

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise RuntimeError(f"Document vide : '{path.name}'")
    return "\n".join(paragraphs)


def _parse_pptx(path: Path) -> str:
    """Extraction des diapositives + notes via python-pptx."""
    try:
        from pptx import Presentation
    except ImportError:
        raise ImportError("python-pptx requis : pip install python-pptx")

    prs = Presentation(path)
    slides_text = []

    for i, slide in enumerate(prs.slides, start=1):
        parts = [f"\n--- Diapositive {i} ---"]

        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        parts.append(t)

        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"[Notes] {notes}")

        if len(parts) > 1:  # au moins du contenu en dehors du titre de slide
            slides_text.append("\n".join(parts))

    if not slides_text:
        raise RuntimeError(f"Présentation vide : '{path.name}'")
    return "\n".join(slides_text)


def _parse_txt(path: Path) -> str:
    """Lecture avec détection d'encodage (UTF-8 → Latin-1 → CP1252)."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            text = path.read_text(encoding=enc)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    raise RuntimeError(
        f"Impossible de lire '{path.name}' "
        "(essayé : utf-8, latin-1, cp1252)"
    )


# ---------------------------------------------------------------------------
# Nettoyage du texte extrait
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    """
    Nettoie et normalise un texte extrait par parse().

    Transformations appliquées :
    1. Réunit les mots coupés par césure PDF (mot-\\n → mot)
    2. Supprime les numéros de page isolés
    3. Réduit les sauts de ligne multiples (> 2 → 2)
    4. Supprime les espaces multiples en milieu de ligne
    5. Supprime les lignes vides en début/fin
    6. Déduplique les lignes identiques consécutives

    Args:
        text: Texte brut issu de parse().

    Returns:
        str: Texte nettoyé.
    """
    # 1. Césure PDF : "anti-\ncorps" → "anticorps"
    text = re.sub(r"-\n(\w)", r"\1", text)

    # 2. Numéros de page (ligne contenant uniquement un entier)
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # 3. Plus de 2 sauts de ligne consécutifs → 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Espaces multiples dans une ligne
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    # 5. Déduplication des lignes consécutives identiques
    deduped: list[str] = []
    prev = None
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped).strip()


# ---------------------------------------------------------------------------
# Utilitaire : traiter un dossier entier
# ---------------------------------------------------------------------------

def parse_folder(folder: str | Path) -> dict[str, str]:
    """
    Parse tous les fichiers supportés d'un dossier.

    Args:
        folder: Chemin vers le dossier source (ex: input/scanner/embolie/).

    Returns:
        dict: {nom_fichier: texte_nettoyé}
    """
    folder = Path(folder)
    results: dict[str, str] = {}

    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            try:
                raw = parse(path)
                results[path.name] = clean(raw)
            except (RuntimeError, ValueError) as exc:
                print(f"  [WARN] {path.name} ignoré : {exc}")

    return results
