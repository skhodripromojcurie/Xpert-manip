"""
utils.py
========
Utilitaires partagés entre les modules du projet.

Rôle :
- Fournir des fonctions communes réutilisables dans tout le projet.
- Centraliser la configuration du logger.
- Fournir des helpers pour la gestion des chemins et des fichiers.

Fonctions disponibles :
- get_logger()          : Configure et retourne un logger standardisé.
- get_parser()          : Retourne le parseur approprié selon l'extension du fichier.
- save_text()           : Sauvegarde un texte dans un fichier avec gestion du dossier.
- slugify()             : Convertit un nom de thème en slug pour les noms de fichiers.
- format_file_size()    : Formate une taille en octets en chaîne lisible (KB, MB...).
"""

import logging
import re
from pathlib import Path


# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------

def get_logger(name: str, log_file: str | Path | None = None) -> logging.Logger:
    """
    Configure et retourne un logger avec sortie console et optionnellement fichier.

    Args:
        name: Nom du logger (typiquement __name__ du module appelant).
        log_file: Chemin optionnel vers un fichier de log (dans logs/).

    Returns:
        logging.Logger: Logger configuré.
    """
    # TODO:
    # logger = logging.getLogger(name)
    # logger.setLevel(logging.DEBUG)
    # formatter = logging.Formatter(
    #     "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    #     datefmt="%Y-%m-%d %H:%M:%S",
    # )
    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter)
    # logger.addHandler(console_handler)
    # if log_file:
    #     Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    #     file_handler = logging.FileHandler(log_file, encoding="utf-8")
    #     file_handler.setFormatter(formatter)
    #     logger.addHandler(file_handler)
    # return logger
    raise NotImplementedError("get_logger() non encore implémenté.")


# ------------------------------------------------------------------
# Routage des parseurs
# ------------------------------------------------------------------

def get_parser(file_path: str | Path):
    """
    Retourne l'instance du parseur approprié selon l'extension du fichier.

    Args:
        file_path: Chemin vers le fichier source.

    Returns:
        BaseParser: Instance du parseur correspondant.

    Raises:
        ValueError: Si le format du fichier n'est pas supporté.
    """
    # TODO:
    # from src.parsers import PDFParser, DOCXParser, PPTXParser, TXTParser
    # ext = Path(file_path).suffix.lower()
    # parsers = {
    #     ".pdf":  PDFParser,
    #     ".docx": DOCXParser,
    #     ".pptx": PPTXParser,
    #     ".txt":  TXTParser,
    # }
    # if ext not in parsers:
    #     raise ValueError(f"Format non supporté : '{ext}'. Formats acceptés : {list(parsers)}")
    # return parsers[ext](file_path)
    raise NotImplementedError("get_parser() non encore implémenté.")


# ------------------------------------------------------------------
# Gestion des fichiers
# ------------------------------------------------------------------

def save_text(text: str, output_path: str | Path) -> None:
    """
    Sauvegarde un texte dans un fichier, en créant les dossiers parents si besoin.

    Args:
        text: Texte à sauvegarder.
        output_path: Chemin de destination du fichier.
    """
    # TODO:
    # path = Path(output_path)
    # path.parent.mkdir(parents=True, exist_ok=True)
    # path.write_text(text, encoding="utf-8")
    raise NotImplementedError("save_text() non encore implémenté.")


def slugify(name: str) -> str:
    """
    Convertit un nom de thème en slug utilisable comme nom de fichier.

    Ex: "Embolie Pulmonaire" → "embolie_pulmonaire"
        "Scanner cérébral (urgence)" → "scanner_cerebral_urgence"

    Args:
        name: Nom brut du thème.

    Returns:
        str: Slug normalisé en minuscules sans caractères spéciaux.
    """
    # TODO:
    # import unicodedata
    # # Décomposer les caractères accentués
    # normalized = unicodedata.normalize("NFD", name.lower())
    # # Supprimer les diacritiques
    # ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    # # Remplacer les caractères non alphanumériques par des underscores
    # slug = re.sub(r'[^a-z0-9]+', '_', ascii_str)
    # return slug.strip('_')
    raise NotImplementedError("slugify() non encore implémenté.")


def format_file_size(size_bytes: int) -> str:
    """
    Formate une taille en octets en chaîne lisible.

    Args:
        size_bytes: Taille en octets.

    Returns:
        str: Ex: "1.4 MB", "256.0 KB", "512 B"
    """
    # TODO:
    # for unit in ['B', 'KB', 'MB', 'GB']:
    #     if size_bytes < 1024 or unit == 'GB':
    #         return f"{size_bytes:.1f} {unit}" if unit != 'B' else f"{size_bytes} {unit}"
    #     size_bytes /= 1024
    raise NotImplementedError("format_file_size() non encore implémenté.")
