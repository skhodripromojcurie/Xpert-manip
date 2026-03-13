"""
base_parser.py
==============
Classe de base abstraite pour tous les parseurs de documents.

Rôle :
- Définir l'interface commune à tous les parseurs.
- Garantir que chaque parseur implémente la méthode `extract_text()`.
- Fournir les attributs communs (chemin du fichier, nom du fichier).

Tous les parseurs du projet héritent de cette classe.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    """
    Classe abstraite dont héritent tous les parseurs de documents.
    """

    def __init__(self, file_path: str | Path):
        """
        Initialise le parseur avec le chemin vers le fichier source.

        Args:
            file_path: Chemin absolu ou relatif vers le fichier à parser.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {self.file_path}")
        self.file_name = self.file_path.stem  # Nom sans extension

    @abstractmethod
    def extract_text(self) -> str:
        """
        Extrait le texte brut du document.

        Returns:
            str: Texte extrait, prêt à être sauvegardé dans parsed/.

        À implémenter dans chaque sous-classe selon le format du fichier.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(file='{self.file_path.name}')"
