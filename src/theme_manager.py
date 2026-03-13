"""
theme_manager.py
================
Gestionnaire de thèmes et de regroupement de sources.

Rôle :
- Découvrir les thèmes disponibles dans le dossier input/.
- Lister les fichiers sources associés à un thème donné.
- Regrouper les textes nettoyés d'un thème pour la génération de fiche.
- Valider la structure des dossiers (spécialité/thème).

Structure attendue du dossier input/ :
    input/
    └── <spécialité>/          # Ex: scanner, radiologie, IRM
        └── <thème>/           # Ex: embolie_pulmonaire, dissection_aortique
            ├── cours_A.pdf
            ├── cours_B.docx
            └── ...

Exemples d'utilisation :
    manager = ThemeManager(input_dir="input/", cleaned_dir="cleaned/")
    themes = manager.list_themes(specialty="scanner")
    sources = manager.get_cleaned_sources(specialty="scanner", theme="embolie_pulmonaire")
    merged_text = manager.merge_sources(sources)

Étape concernée : Étape 4 — Regroupement par thème
"""

from pathlib import Path

# Extensions de fichiers sources acceptées
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}


class ThemeManager:
    """
    Gère la découverte et le regroupement des sources par thème.
    """

    def __init__(self, input_dir: str | Path, cleaned_dir: str | Path):
        """
        Initialise le gestionnaire de thèmes.

        Args:
            input_dir: Chemin vers le dossier input/ contenant les sources brutes.
            cleaned_dir: Chemin vers le dossier cleaned/ contenant les textes nettoyés.
        """
        self.input_dir = Path(input_dir)
        self.cleaned_dir = Path(cleaned_dir)

    def list_specialties(self) -> list[str]:
        """
        Liste les spécialités disponibles dans input/.

        Returns:
            list[str]: Noms des dossiers de spécialité (ex: ["scanner", "IRM"]).
        """
        # TODO:
        # return [d.name for d in self.input_dir.iterdir() if d.is_dir()]
        raise NotImplementedError("list_specialties() non encore implémenté.")

    def list_themes(self, specialty: str) -> list[str]:
        """
        Liste les thèmes disponibles pour une spécialité donnée.

        Args:
            specialty: Nom de la spécialité (ex: "scanner").

        Returns:
            list[str]: Noms des thèmes (ex: ["embolie_pulmonaire", "dissection_aortique"]).
        """
        # TODO:
        # specialty_path = self.input_dir / specialty
        # return [d.name for d in specialty_path.iterdir() if d.is_dir()]
        raise NotImplementedError("list_themes() non encore implémenté.")

    def get_source_files(self, specialty: str, theme: str) -> list[Path]:
        """
        Retourne la liste des fichiers sources d'un thème donné.

        Args:
            specialty: Nom de la spécialité.
            theme: Nom du thème.

        Returns:
            list[Path]: Chemins vers les fichiers sources supportés.
        """
        # TODO:
        # theme_path = self.input_dir / specialty / theme
        # return [
        #     f for f in theme_path.iterdir()
        #     if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        # ]
        raise NotImplementedError("get_source_files() non encore implémenté.")

    def get_cleaned_sources(self, specialty: str, theme: str) -> list[Path]:
        """
        Retourne la liste des fichiers texte nettoyés pour un thème.

        Args:
            specialty: Nom de la spécialité.
            theme: Nom du thème.

        Returns:
            list[Path]: Chemins vers les fichiers .txt nettoyés dans cleaned/.
        """
        # TODO:
        # cleaned_theme_path = self.cleaned_dir / specialty / theme
        # return list(cleaned_theme_path.glob("*.txt"))
        raise NotImplementedError("get_cleaned_sources() non encore implémenté.")

    def merge_sources(self, source_paths: list[Path]) -> str:
        """
        Fusionne plusieurs fichiers texte nettoyés en un seul bloc de texte.

        Insère un séparateur clair entre chaque source pour que le générateur
        puisse distinguer les origines si nécessaire.

        Args:
            source_paths: Liste des chemins vers les fichiers texte nettoyés.

        Returns:
            str: Texte fusionné de toutes les sources.
        """
        # TODO:
        # merged_parts = []
        # for path in source_paths:
        #     content = path.read_text(encoding="utf-8")
        #     separator = f"\n\n{'='*60}\nSOURCE : {path.name}\n{'='*60}\n\n"
        #     merged_parts.append(separator + content)
        # return "\n".join(merged_parts)
        raise NotImplementedError("merge_sources() non encore implémenté.")
