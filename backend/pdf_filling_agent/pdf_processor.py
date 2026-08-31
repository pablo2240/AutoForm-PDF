"""
PDF Processing utilities for filling PDF forms.
"""

import fitz  # PyMuPDF
import os
from typing import Dict, Any


class PDFProcessor:
    """Handles PDF form filling operations."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def fill_pdf(self, input_pdf_path: str, field_values: Dict[str, Any]) -> str:
        """
        Fill a PDF with the given field values.

        Args:
            input_pdf_path: Path to the input PDF file
            field_values: Dictionary mapping field names to values

        Returns:
            Path to the filled PDF file
        """
        doc = fitz.open(input_pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            for widget in page.widgets():
                field_name = widget.field_name
                if field_name in field_values:
                    val = field_values[field_name]
                    if val is None:
                        continue
                    try:
                        if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                            if str(val).lower() in ["true", "1", "yes", "si", "x", "on"]:
                                widget.field_value = "1"
                            else:
                                widget.field_value = "Off"
                        elif widget.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
                            if str(val).lower() in ["true", "1", "yes", "si", "x", "on"]:
                                widget.field_value = "1"
                            else:
                                widget.field_value = "Off"
                        else:
                            widget.field_value = str(val)
                        widget.update()  # Regenerates the widget appearance
                    except Exception as wex:
                        print(f"[WARN] Failed to update widget '{field_name}': {wex}")

        # Generate output filename
        input_filename = os.path.basename(input_pdf_path)
        output_filename = f"filled_{input_filename}"
        output_path = os.path.join(self.output_dir, output_filename)

        doc.save(output_path, incremental=False)
        doc.close()

        return output_path

    def get_pdf_fields(self, pdf_path: str) -> Dict[str, str]:
        """
        Extract field names and types from a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary mapping field names to field types
        """
        doc = fitz.open(pdf_path)
        fields = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            for widget in page.widgets():
                field_name = widget.field_name
                field_type = widget.field_type_string
                fields[field_name] = field_type

        doc.close()
        return fields

    def execute_generated_code(self, code: str, pdf_path: str, field_values: Dict[str, Any]) -> str:
        """
        Execute dynamically generated code to fill PDF using scaffolding approach.

        Args:
            code: Generated Python code snippets for field filling
            pdf_path: Path to the input PDF file
            field_values: Dictionary of field values

        Returns:
            Path to the filled PDF file
        """
        # Clean the AI-generated field filling code
        field_code = self._clean_field_code(code)

        # Create the complete code using scaffolding
        complete_code = self._create_scaffolding_code(pdf_path, field_code)

        print(f"Executing complete code:\n{complete_code}\n")

        # Create a namespace with the required imports and variables
        namespace = {
            'fitz': fitz,
            'os': os,
            '__file__': pdf_path,
            'field_values': field_values,
            'output_dir': self.output_dir,
            'pdf_path': pdf_path
        }

        try:
            # Execute the complete code
            exec(complete_code, namespace)

            # Check if the code set output_path
            output_path = namespace.get('output_path')
            if output_path and os.path.exists(output_path):
                return output_path
            else:
                # Look for the expected output file
                input_name = os.path.basename(pdf_path)
                expected_output = os.path.join(self.output_dir, f"filled_{input_name}")
                if os.path.exists(expected_output):
                    return expected_output
                else:
                    return expected_output

        except Exception as e:
            print(f"Error executing generated code: {e}")
            raise RuntimeError(f"Error executing generated code: {e}")

    def _clean_field_code(self, code: str) -> str:
        """Clean the AI-generated field filling code snippets."""
        # Remove markdown formatting if present
        code = code.strip()
        if code.startswith('```python'):
            code = code[9:]
        if code.endswith('```'):
            code = code[:-3]
        code = code.strip()

        # Remove any import statements (handled by scaffolding)
        lines = code.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('import ') and not line.startswith('from '):
                clean_lines.append(line)

        code = '\n'.join(clean_lines)

        # If no if statements found, add a default pass
        if not any('if ' in line for line in clean_lines):
            return '        # No specific field mappings generated\n        pass'

        # Fix the code structure - ensure proper if/elif chain
        lines = code.split('\n')
        fixed_lines = []
        in_if_chain = False

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            if 'field_name ==' in line:
                if not in_if_chain:
                    # First if statement
                    fixed_lines.append('        ' + line)
                    in_if_chain = True
                else:
                    # Subsequent elif statements
                    fixed_lines.append('        elif ' + line)
            elif 'widget.field_value' in line or 'widget.update' in line:
                # Indent these lines
                fixed_lines.append('            ' + line)
            else:
                # Other lines - try to handle them
                if 'field_name ==' in line:
                    fixed_lines.append('        elif ' + line)
                else:
                    fixed_lines.append('            ' + line)

        # If we have field assignments but no if statements, wrap them
        if fixed_lines and not any('if ' in line for line in fixed_lines):
            # Find widget assignments and wrap them in if statements
            new_lines = []
            current_field = None
            current_value = None

            for line in fixed_lines:
                if 'field_name ==' in line:
                    if current_field and current_value:
                        new_lines.append(f'        if field_name == "{current_field}":')
                        new_lines.append(f'            widget.field_value = "{current_value}"')
                        new_lines.append('            widget.update()')
                    current_field = line.split('field_name == "')[1].split('"')[0]
                    current_value = None
                elif 'widget.field_value' in line:
                    current_value = line.split('widget.field_value = "')[1].split('"')[0]

            # Add the last one
            if current_field and current_value:
                new_lines.append(f'        if field_name == "{current_field}":')
                new_lines.append(f'            widget.field_value = "{current_value}"')
                new_lines.append('            widget.update()')

            fixed_lines = new_lines

        return '\n'.join(fixed_lines)

    def _create_scaffolding_code(self, pdf_path: str, field_code: str) -> str:
        """Create complete code using scaffolding with AI-generated field code."""
        input_name = os.path.basename(pdf_path)
        output_name = f"filled_{input_name}"
        output_path = os.path.join(self.output_dir, output_name)

        scaffolding = f'''
import fitz  # PyMuPDF

# Open the PDF
doc = fitz.open("{pdf_path}")

# Fill the fields
for page_num in range(len(doc)):
    page = doc[page_num]
    for widget in page.widgets():
        field_name = widget.field_name

        # AI-generated field filling logic
        {field_code}

# Save the filled PDF
doc.save("{output_path}", incremental=False)
doc.close()

# Set output path for return value
output_path = "{output_path}"
'''

        return scaffolding

    def _generate_default_output_path(self, pdf_path: str, field_values: Dict[str, Any]) -> str:
        """Generate a default output path for the filled PDF."""
        input_name = os.path.basename(pdf_path)
        output_name = f"filled_{input_name}"
        output_path = os.path.join(self.output_dir, output_name)

        # Do a basic fill with any available field values
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            for widget in page.widgets():
                if widget.field_name in field_values:
                    widget.field_value = field_values[widget.field_name]
                    widget.update()
        doc.save(output_path, incremental=False)
        doc.close()

        return output_path
