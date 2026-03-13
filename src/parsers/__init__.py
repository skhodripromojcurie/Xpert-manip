"""
Package parsers
===============
Regroupe tous les parseurs de documents sources.
Chaque parseur extrait le texte brut d'un format de fichier spécifique.

Parseurs disponibles :
- PDFParser    : extraction page par page depuis les fichiers .pdf
- DOCXParser   : extraction des paragraphes depuis les fichiers .docx
- PPTXParser   : extraction des diapositives et notes depuis les fichiers .pptx
- TXTParser    : lecture directe du contenu brut des fichiers .txt
"""

from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .pptx_parser import PPTXParser
from .txt_parser import TXTParser

__all__ = ["PDFParser", "DOCXParser", "PPTXParser", "TXTParser"]
