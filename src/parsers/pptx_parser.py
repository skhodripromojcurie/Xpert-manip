"""
pptx_parser.py
==============
Parseur pour les fichiers Microsoft PowerPoint (.pptx).

Rôle :
- Extraire le texte des formes (shapes) de chaque diapositive.
- Extraire également les notes du présentateur si elles existent.
- Indiquer le numéro de diapositive pour faciliter la relecture.

Bibliothèque utilisée : python-pptx

Étape concernée : Étape 2 — Parsing
"""

from pathlib import Path
from .base_parser import BaseParser


class PPTXParser(BaseParser):
    """
    Extrait le texte des diapositives et notes d'un fichier PowerPoint (.pptx).
    """

    # Marqueur de séparation entre diapositives
    SLIDE_SEPARATOR = "\n\n--- Diapositive {slide_num} ---\n"
    NOTES_SEPARATOR = "\n[Notes] "

    def extract_text(self) -> str:
        """
        Parcourt toutes les diapositives et extrait le texte + notes.

        Returns:
            str: Texte complet de la présentation, slide par slide.

        Raises:
            ImportError: Si python-pptx n'est pas installé.
            RuntimeError: Si la présentation est vide.
        """
        # TODO: Implémenter avec python-pptx
        # from pptx import Presentation
        # prs = Presentation(self.file_path)
        # slides_text = []
        # for i, slide in enumerate(prs.slides, start=1):
        #     slide_content = self.SLIDE_SEPARATOR.format(slide_num=i)
        #     # Texte des formes
        #     for shape in slide.shapes:
        #         if shape.has_text_frame:
        #             for para in shape.text_frame.paragraphs:
        #                 text = para.text.strip()
        #                 if text:
        #                     slide_content += text + "\n"
        #     # Notes du présentateur
        #     if slide.has_notes_slide:
        #         notes = slide.notes_slide.notes_text_frame.text.strip()
        #         if notes:
        #             slide_content += self.NOTES_SEPARATOR + notes
        #     slides_text.append(slide_content)
        # if not slides_text:
        #     raise RuntimeError(f"Aucun texte dans : {self.file_path.name}")
        # return "\n".join(slides_text)
        raise NotImplementedError("PPTXParser.extract_text() non encore implémenté.")
