"""
txt_parser.py
=============
Parseur pour les fichiers texte brut (.txt).

Rôle :
- Lire le contenu d'un fichier .txt en gérant les encodages courants.
- Retourner le texte brut tel quel (le nettoyage est fait par cleaner.py).

Encodages tentés dans l'ordre : UTF-8, Latin-1 (ISO-8859-1), CP1252.

Étape concernée : Étape 2 — Parsing
"""

from pathlib import Path
from .base_parser import BaseParser

# Encodages à tester dans l'ordre (couvrent la majorité des fichiers français)
ENCODINGS_TO_TRY = ["utf-8", "latin-1", "cp1252"]


class TXTParser(BaseParser):
    """
    Lit le contenu brut d'un fichier texte (.txt).
    """

    def extract_text(self) -> str:
        """
        Lit le fichier texte en essayant plusieurs encodages.

        Returns:
            str: Contenu brut du fichier texte.

        Raises:
            RuntimeError: Si aucun encodage ne fonctionne ou si le fichier est vide.
        """
        # TODO: Implémenter la lecture avec gestion d'encodage
        # for encoding in ENCODINGS_TO_TRY:
        #     try:
        #         text = self.file_path.read_text(encoding=encoding)
        #         if not text.strip():
        #             raise RuntimeError(f"Fichier vide : {self.file_path.name}")
        #         return text
        #     except UnicodeDecodeError:
        #         continue
        # raise RuntimeError(
        #     f"Impossible de décoder {self.file_path.name} "
        #     f"avec les encodages : {ENCODINGS_TO_TRY}"
        # )
        raise NotImplementedError("TXTParser.extract_text() non encore implémenté.")
