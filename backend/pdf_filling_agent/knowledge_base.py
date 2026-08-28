"""
Knowledge Base system for PDF filling instructions.
"""

import os
from typing import Dict, Any, Optional
from .field_dictionary import get_dictionary_context, FIELD_SYNONYMS, IGNORE_RULES


class KnowledgeBase:
    """Manages system instructions and domain context for PDF filling."""

    def __init__(self, knowledge_file: Optional[str] = None):
        if knowledge_file is None:
            self.knowledge_content = self._get_default_knowledge()
        else:
            self.knowledge_content = self._load_knowledge_file(knowledge_file)

    def _get_default_knowledge(self) -> str:
        """Get default knowledge base content including dictionary and exclusion rules."""
        return f"""
# PDF Filling System Instructions

## General Guidelines
- Always use PyMuPDF (fitz) for PDF manipulation
- Match form field labels against the synonyms dictionary
- Adhere strictly to the negative exclusion rules (never fill foreign or counterparty sections)
- Call widget.update() after setting field values
- Save the PDF with incremental=False

{get_dictionary_context()}
"""

    def _load_knowledge_file(self, file_path: str) -> str:
        """Load knowledge base from a file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Knowledge base file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def get_system_instructions(self) -> str:
        """Get formatted system instructions for the AI agent."""
        return f"""
You are an expert AI assistant specialized in analyzing, mapping, and filling PDF forms (both AcroForms and Flat visual PDFs).

KNOWLEDGE BASE & DOMAIN RULES:
{self.knowledge_content}

Your objective is to identify matching fields based on the synonyms dictionary, assign company profile values, and strictly respect exclusion rules.
"""

    def update_knowledge(self, new_content: str):
        """Update the knowledge base content."""
        self.knowledge_content = new_content

    def get_knowledge_content(self) -> str:
        """Get the raw knowledge base content."""
        return self.knowledge_content
