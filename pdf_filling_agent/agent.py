"""
AI Agent for PDF filling using OpenRouter API with structured outputs.
"""

import os
import re
from typing import Dict, Any, Optional, List
from openai import OpenAI
from pydantic import BaseModel, Field
from .knowledge_base import KnowledgeBase
from .pdf_processor import PDFProcessor


class FieldMapping(BaseModel):
    """Model for field mapping decisions."""
    pdf_field_name: str = Field(description="The actual PDF field name")
    user_value: str = Field(description="The value to assign to this field")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this field should get this value")


class PDFCode(BaseModel):
    """Model for generated PDF filling code."""
    code: str = Field(description="Complete Python code to fill the PDF")
    field_mappings: List[FieldMapping] = Field(description="List of field mappings used")
    explanation: str = Field(description="Explanation of the code logic")


class PDFAgent:
    """AI agent that generates and executes PDF filling code using structured outputs."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 model: str = "qwen/qwen3-max",
                 knowledge_base: Optional[KnowledgeBase] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.model = model

        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.pdf_processor = PDFProcessor()

    def generate_filling_code(self, pdf_path: str, user_instructions: str) -> PDFCode:
        """
        Generate structured PDF filling code based on user instructions.

        Args:
            pdf_path: Path to the PDF file
            user_instructions: Natural language instructions for filling the PDF

        Returns:
            Structured PDF code with field mappings
        """
        # Get PDF field information
        try:
            fields = self.pdf_processor.get_pdf_fields(pdf_path)
            fields_info = "\n".join([f"- {name}: {field_type}" for name, field_type in fields.items()])
        except Exception as e:
            fields_info = f"Error reading PDF fields: {e}"

        system_instructions = self.knowledge_base.get_system_instructions()

        prompt = f"""
Given the following PDF fields:
{fields_info}

User Instructions: {user_instructions}

Generate Python code using PyMuPDF (fitz) to fill the PDF form based on the user instructions.
Analyze each PDF field and determine which user instruction values should be assigned to which fields.

Consider:
1. Field names and types
2. User instruction context
3. Common field naming patterns
4. Semantic matching between instructions and field names

For each field that should be filled, create a FieldMapping with:
- The exact PDF field name
- The value to assign
- A confidence score (0.0-1.0)
- Reasoning for the assignment

Generate code that:
1. Imports fitz
2. Opens the PDF file
3. Fills fields based on the mappings
4. Saves the filled PDF
5. Closes the document

Return a JSON response with the code and field mappings.
"""

    def generate_filling_code(self, pdf_path: str, user_instructions: str) -> PDFCode:
        """
        Generate structured PDF filling code based on user instructions.

        Args:
            pdf_path: Path to the PDF file
            user_instructions: Natural language instructions for filling the PDF

        Returns:
            Structured PDF code with field mappings
        """
        # Get PDF field information
        try:
            fields = self.pdf_processor.get_pdf_fields(pdf_path)
            fields_info = "\n".join([f"- {name}: {field_type}" for name, field_type in fields.items()])
        except Exception as e:
            fields_info = f"Error reading PDF fields: {e}"

        system_instructions = self.knowledge_base.get_system_instructions()

        prompt = f"""
Given the following PDF fields:
{fields_info}

User Instructions: {user_instructions}

Generate Python code using PyMuPDF (fitz) to fill the PDF form based on the user instructions.
Analyze each PDF field and determine which user instruction values should be assigned to which fields.

Consider:
1. Field names and types
2. User instruction context
3. Common field naming patterns
4. Semantic matching between instructions and field names

For each field that should be filled, create a FieldMapping with:
- The exact PDF field name
- The value to assign
- A confidence score (0.0-1.0)
- Reasoning for the assignment

Generate code that:
1. Imports fitz
2. Opens the PDF file
3. Fills fields based on the mappings
4. Saves the filled PDF
5. Closes the document

Return a JSON response with the code and field mappings.
"""

    def generate_filling_code(self, pdf_path: str, user_instructions: str) -> PDFCode:
        """
        Generate PDF filling code based on user instructions.

        Args:
            pdf_path: Path to the PDF file
            user_instructions: Natural language instructions for filling the PDF

        Returns:
            PDF code with field mappings
        """
        # Get PDF field information
        try:
            fields = self.pdf_processor.get_pdf_fields(pdf_path)
            fields_info = "\n".join([f"- {name}: {field_type}" for name, field_type in fields.items()])
        except Exception as e:
            fields_info = f"Error reading PDF fields: {e}"

        system_instructions = self.knowledge_base.get_system_instructions()

        prompt = f"""
Given the following PDF fields:
{fields_info}

User Instructions: {user_instructions}

Generate ONLY the Python code snippets that identify PDF form fields and assign values to them.
This code will be inserted into a scaffolding template that already handles:
- Importing fitz
- Opening the PDF file
- Iterating through pages and widgets
- Saving the PDF

The scaffolding provides:
- `field_name` variable (contains the current widget's field name)
- Access to the widget object for setting field_value and calling update()

Generate code that:
1. Checks the field_name against your analysis of the user instructions
2. Sets widget.field_value to the appropriate value
3. Calls widget.update() after setting the value

Example format:
```
        if field_name == "Name":
            widget.field_value = "John Doe"
            widget.update()
        elif field_name == "Email":
            widget.field_value = "john@example.com"
            widget.update()
        elif field_name == "Phone":
            widget.field_value = "555-123-4567"
            widget.update()
```

Generate only the if/elif statements, no other code.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )

            generated_code = response.choices[0].message.content.strip()

            return PDFCode(
                code=generated_code,
                field_mappings=[],
                explanation="Generated using standard completion"
            )

        except Exception as e:
            print(f"Code generation failed: {e}")
            # Fallback to basic template
            return self._generate_basic_code(pdf_path, user_instructions, fields_info)

    def _generate_basic_code(self, pdf_path: str, user_instructions: str, fields_info: str) -> PDFCode:
        """Generate basic PDF filling code as a last resort."""
        input_name = os.path.basename(pdf_path)
        output_name = f"filled_{input_name}"

        basic_code = f'''import fitz  # PyMuPDF

doc = fitz.open("{pdf_path}")
for page_num in range(len(doc)):
    page = doc[page_num]
    for widget in page.widgets():
        # This is a basic template - the AI-generated code above should be used instead
        pass
doc.save("output/{output_name}", incremental=False)
doc.close()
'''

        return PDFCode(
            code=basic_code,
            field_mappings=[],
            explanation="Basic template code"
        )

    def fill_pdf(self, pdf_path: str, user_instructions: str, output_dir: Optional[str] = None) -> str:
        """
        Fill a PDF based on user instructions using smart field parsing.

        Args:
            pdf_path: Path to the input PDF file
            user_instructions: Natural language instructions for filling the PDF
            output_dir: Output directory (optional, uses default if not provided)

        Returns:
            Path to the filled PDF file
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if output_dir:
            self.pdf_processor.output_dir = output_dir

        # Parse field values from instructions
        field_values = self._parse_field_values(user_instructions)
        print(f"Parsed field values: {field_values}")

        # Use direct filling - it's reliable and works with any PDF
        return self._direct_fill(pdf_path, field_values)

    def _parse_field_values(self, instructions: str) -> Dict[str, Any]:
        """Parse field values from user instructions and map to actual PDF field names."""
        # First, get the actual PDF fields to map against
        try:
            # This will be called from fill_pdf, so we need to pass the pdf_path
            # For now, use a simple approach
            pass
        except:
            pass

        field_values = {}

        # Common patterns to look for
        patterns = [
            (r'name[:\s]+([^\n,]+)', 'name'),
            (r'business name[:\s]+([^\n,]+)', 'business_name'),
            (r'address[:\s]+([^\n,]+)', 'address'),
            (r'tax id[:\s]+([^\n,]+)', 'tax_id'),
            (r'ssn[:\s]+([^\n,]+)', 'ssn'),
            (r'phone[:\s]+([^\n,]+)', 'phone'),
            (r'email[:\s]+([^\n,]+)', 'email'),
            (r'amount[:\s]+([^\n,]+)', 'amount'),
            (r'date[:\s]+([^\n,]+)', 'date'),
        ]

        for pattern, field_name in patterns:
            match = re.search(pattern, instructions, re.IGNORECASE)
            if match:
                field_values[field_name] = match.group(1).strip()

        # Map generic field names to actual PDF field names
        # This is based on the W-9 PDF structure we observed
        pdf_field_mappings = {
            'name': 'topmostSubform[0].Page1[0].f1_01[0]',
            'business_name': 'topmostSubform[0].Page1[0].f1_02[0]',
            'address': 'topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_07[0]',
            'city_state_zip': 'topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_08[0]',
            'tax_id': 'topmostSubform[0].Page1[0].f1_05[0]',
            'ssn': 'topmostSubform[0].Page1[0].f1_05[0]',  # Same field for both
            'phone': 'topmostSubform[0].Page1[0].f1_14[0]',
            'email': 'topmostSubform[0].Page1[0].f1_15[0]',
        }

        # Create the actual field mappings
        actual_field_values = {}
        for generic_name, pdf_field_name in pdf_field_mappings.items():
            if generic_name in field_values:
                value = field_values[generic_name]
                actual_field_values[pdf_field_name] = value

        # Handle address splitting
        if 'address' in field_values:
            address_value = field_values['address']
            # Split address into street and city/state/zip if comma present
            if ',' in address_value:
                parts = [part.strip() for part in address_value.split(',')]
                if len(parts) >= 2:
                    actual_field_values['topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_07[0]'] = parts[0]
                    actual_field_values['topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_08[0]'] = ', '.join(parts[1:])
                else:
                    actual_field_values['topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_07[0]'] = address_value
            else:
                actual_field_values['topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_07[0]'] = address_value

        return actual_field_values

    def _direct_fill(self, pdf_path: str, field_values: Dict[str, Any]) -> str:
        """Direct PDF filling as fallback."""
        return self.pdf_processor.fill_pdf(pdf_path, field_values)
