"""
pdf_parser.py
=============
Parseur pour les fichiers PDF.

Rôle :
- Extraire le texte brut d'un fichier PDF, page par page.
- Concaténer les pages avec un marqueur de séparation clair.
- Gérer les PDFs scannés (avertissement si aucun texte détecté).

Bibliothèque utilisée : pdfplumber (meilleure extraction de texte que pypdf,
gère mieux les tableaux et les mises en page complexes).

Étape concernée : Étape 2 — Parsing
"""

from pathlib import Path
from .base_parser import BaseParser


class PDFParser(BaseParser):
    """
    Extrait le texte brut d'un fichier PDF page par page.
    """

    # Marqueur inséré entre chaque page dans le texte extrait
    PAGE_SEPARATOR = "\n\n--- Page {page_num} ---\n\n"

    def extract_text(self) -> str:
        """
        Parcourt toutes les pages du PDF et extrait le texte.

        Returns:
            str: Texte complet du PDF, avec marqueurs de pages.

        Raises:
            ImportError: Si pdfplumber n'est pas installé.
            RuntimeError: Si le PDF est illisible ou vide.
        """
        # TODO: Implémenter avec pdfplumber
        # import pdfplumber
        # with pdfplumber.open(self.file_path) as pdf:
        #     pages_text = []
        #     for i, page in enumerate(pdf.pages, start=1):
        #         text = page.extract_text() or ""
        #         if text.strip():
        #             pages_text.append(self.PAGE_SEPARATOR.format(page_num=i) + text)
        #     if not pages_text:
        #         raise RuntimeError(f"Aucun texte extractible dans : {self.file_path.name}")
        #     return "\n".join(pages_text)
        raise NotImplementedError("PDFParser.extract_text() non encore implémenté.")
