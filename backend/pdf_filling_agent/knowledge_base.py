"""
Knowledge Base system for PDF filling instructions.
"""

import os
from typing import Dict, Any, Optional


class KnowledgeBase:
    """Manages system instructions for PDF filling."""

    def __init__(self, knowledge_file: Optional[str] = None):
        if knowledge_file is None:
            # Default knowledge base content
            self.knowledge_content = self._get_default_knowledge()
        else:
            self.knowledge_content = self._load_knowledge_file(knowledge_file)

    def _get_default_knowledge(self) -> str:
        """Get default knowledge base content."""
        return """
# PDF Filling System Instructions

## General Guidelines
- Always use PyMuPDF (fitz) for PDF manipulation
- Field names are case-sensitive
- Call widget.update() after setting field values
- Save the PDF with incremental=False
- Handle errors gracefully and provide meaningful feedback

## Code Generation Rules
1. Import fitz at the beginning of generated code
2. Open the PDF document with fitz.open()
3. Iterate through all pages and widgets
4. Set field_value for matching field names
5. Update widgets after setting values
6. Save to output directory
7. Close the document properly

## Field Value Types
- Text fields: Use string values
- Checkboxes: Use boolean values (True/False)
- Radio buttons: Use string values matching the option
- Dropdowns: Use string values matching the option

## Error Handling
- Validate that PDF files exist before processing
- Handle cases where field names don't exist in the PDF
- Provide informative error messages for debugging
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
You are an AI assistant specialized in generating Python code to fill PDF forms using PyMuPDF.

KNOWLEDGE BASE:
{self.knowledge_content}

Your task is to generate Python code that:
1. Opens the specified PDF file
2. Fills in the form fields based on the user's instructions
3. Saves the filled PDF to the output directory

Generate code that follows this pattern:
```python
import fitz  # PyMuPDF

doc = fitz.open("input.pdf")
for page_num in range(len(doc)):
    page = doc[page_num]
    for widget in page.widgets():
        if widget.field_name == "FieldName":
            widget.field_value = "Value"
            widget.update()
doc.save("output.pdf", incremental=False)
doc.close()
```

The generated code should be executable and handle the specific field names and values from the user's instructions.
"""

    def update_knowledge(self, new_content: str):
        """Update the knowledge base content."""
        self.knowledge_content = new_content

    def get_knowledge_content(self) -> str:
        """Get the raw knowledge base content."""
        return self.knowledge_content
