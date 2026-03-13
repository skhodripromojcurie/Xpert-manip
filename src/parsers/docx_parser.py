"""
docx_parser.py
==============
Parseur pour les fichiers Microsoft Word (.docx).

Rôle :
- Extraire le texte brut des paragraphes d'un fichier .docx.
- Conserver l'ordre naturel de lecture.
- Ignorer les éléments non textuels (images, tableaux si inaccessibles).

Bibliothèque utilisée : python-docx

Étape concernée : Étape 2 — Parsing
"""

from pathlib import Path
from .base_parser import BaseParser


class DOCXParser(BaseParser):
    """
    Extrait le texte brut d'un fichier Word (.docx) paragraphe par paragraphe.
    """

    def extract_text(self) -> str:
        """
        Lit tous les paragraphes du document Word et les concatène.

        Returns:
            str: Texte complet du document, un paragraphe par ligne.

        Raises:
            ImportError: Si python-docx n'est pas installé.
            RuntimeError: Si le document est vide.
        """
        # TODO: Implémenter avec python-docx
        # from docx import Document
        # doc = Document(self.file_path)
        # paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # if not paragraphs:
        #     raise RuntimeError(f"Aucun texte dans : {self.file_path.name}")
        # return "\n".join(paragraphs)
        raise NotImplementedError("DOCXParser.extract_text() non encore implémenté.")
