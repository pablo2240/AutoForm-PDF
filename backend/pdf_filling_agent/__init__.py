"""
PDF Filling Agent

An AI-powered agent that uses OpenRouter's LLM to dynamically generate and execute
code for filling PDF forms based on user instructions and a knowledge base.
"""

from .agent import PDFAgent
from .knowledge_base import KnowledgeBase
from .pdf_processor import PDFProcessor
from .visual_processor import VisualPDFProcessor, VisualPlacement

__version__ = "0.1.0"
__all__ = ["PDFAgent", "KnowledgeBase", "PDFProcessor", "VisualPDFProcessor", "VisualPlacement"]
