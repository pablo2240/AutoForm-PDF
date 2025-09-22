# PDF Filling Agent

An AI-powered PDF filling agent that uses OpenRouter's qwen/qwen3-max LLM to dynamically create and execute code for filling PDF forms based on natural language instructions.

## Features

- 🤖 AI-powered code generation using OpenRouter API
- 📄 Dynamic PDF form filling with PyMuPDF
- 🧠 Knowledge base integration for consistent instructions
- 🔧 Safe code execution environment
- 🖥️ Command-line interface and Python API
- 📚 Extensible knowledge base system

## Installation

### Prerequisites

1. **Python 3.8+**
2. **UV package manager** (recommended)
3. **OpenRouter API key** - Get one at [openrouter.ai](https://openrouter.ai)

### Setup

1. Clone or download this project
2. Install dependencies:
   ```bash
   uv sync
   ```

3. Create environment file:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_actual_api_key_here
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```

## Usage

### Command Line Interface

```bash
# Basic usage
uv run pdf-agent input_form.pdf "Fill name as John Doe and SSN as 123-45-6789"

# With custom output directory
uv run pdf-agent input_form.pdf "Fill all fields with test data" --output-dir ./results

# With custom knowledge base
uv run pdf-agent input_form.pdf "Process form" --knowledge-file custom_knowledge.md
```

### Python API

```python
from pdf_filling_agent import PDFAgent, KnowledgeBase

# Initialize with custom knowledge base
knowledge_base = KnowledgeBase("knowledge_base.md")
agent = PDFAgent(knowledge_base=knowledge_base)

# Fill a PDF
output_path = agent.fill_pdf(
    "input_form.pdf",
    "Fill name as Jane Smith and email as jane@example.com"
)

print(f"Filled PDF saved to: {output_path}")
```

### Creating Input PDFs

Place your PDF forms in an `input/` directory, or specify the full path when running the agent.

## Quick Start Testing

Test the PDF filling agent immediately with the included example:

```bash
# Run the example script with the provided W-9 PDF
uv run python example.py

# This will:
# 1. Parse instructions to fill a W-9 form
# 2. Use the included fw9.pdf as input
# 3. Generate a filled PDF in the output/ directory
# 4. Display field mapping and results
```

The included `input/fw9.pdf` is a sample W-9 tax form that demonstrates the system's capabilities with real-world PDF forms.

### Testing Different Instruction Formats

Use the comprehensive test suite to verify functionality:

```bash
# Run all tests
uv run pytest

# Test different instruction parsing scenarios
uv run python test_general.py

# Test the core agent functionality
uv run python test_agent.py
```

## Project Structure

```
pdf-filling-agent/
├── pdf_filling_agent/          # Main package
│   ├── __init__.py            # Package initialization
│   ├── agent.py               # AI agent implementation
│   ├── knowledge_base.py      # Knowledge base management
│   ├── pdf_processor.py       # PDF manipulation utilities
│   └── main.py                # CLI interface
├── input/                     # PDF forms for testing
│   └── fw9.pdf               # Sample W-9 tax form
├── output/                    # Generated filled PDFs
├── tests/                     # Test files
│   ├── test_general.py       # Instruction format testing
│   └── test_agent.py         # Core functionality testing
├── knowledge_base.md          # Default knowledge base
├── example.py                 # Usage example with fw9.pdf
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── README.md                 # This file
└── pyproject.toml            # Project configuration
```

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `OPENROUTER_BASE_URL`: OpenRouter API base URL (default: https://openrouter.ai/api/v1)

### Knowledge Base

The knowledge base (`knowledge_base.md`) contains system instructions for the AI agent. You can customize it to:

- Define field naming conventions
- Specify data formats
- Add business rules
- Include error handling guidelines

## How It Works

1. **Input Processing**: The agent receives a PDF file and natural language instructions
2. **Field Analysis**: Extracts available form fields from the PDF
3. **Code Generation**: Uses OpenRouter's LLM to generate Python code based on knowledge base
4. **Code Execution**: Safely executes the generated code to fill the PDF
5. **Output**: Saves the filled PDF to the output directory

## Example Generated Code

The agent generates code following this pattern:

```python
import fitz  # PyMuPDF

doc = fitz.open("input.pdf")
page = doc[0]
for w in page.widgets():
    if w.field_name == "Name":
        w.field_value = "Jane Doe"
        w.update()  # regenerates the widget appearance
    if w.field_name == "SSN":
        w.field_value = "123-45-6789"
        w.update()
doc.save("output/filled_input.pdf", incremental=False)
doc.close()
```

## Error Handling

The system includes robust error handling:

- Validates PDF file existence
- Handles API errors gracefully
- Provides fallback direct filling if code generation fails
- Logs detailed error messages for debugging

## Extending the System

### Custom Knowledge Base

Create a new markdown file with your specific instructions:

```markdown
# Custom Instructions

## Field Mappings
- customer_name: Maps to "Full Name" field
- tax_id: Maps to "SSN/TIN" field

## Business Rules
- Always format phone numbers as (XXX) XXX-XXXX
- Validate email addresses before setting
```

### Adding New Field Types

Extend the `PDFProcessor` class to handle additional field types:

```python
def handle_checkbox_field(self, widget, value):
    """Handle checkbox fields."""
    if isinstance(value, bool):
        widget.field_value = value
        widget.update()
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test files
uv run pytest tests/

# Test different instruction parsing scenarios
uv run python tests/test_general.py

# Test the core agent functionality
uv run python tests/test_agent.py

# Run example with provided sample PDF
uv run python example.py
```

### Code Formatting

```bash
uv run black pdf_filling_agent/
uv run isort pdf_filling_agent/
```

## Requirements

- **PyMuPDF**: PDF manipulation and form filling
- **openai**: OpenRouter API client
- **python-dotenv**: Environment variable management
- **requests**: HTTP client for API calls

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues or questions:
1. Check the [OpenRouter documentation](https://openrouter.ai/docs)
2. Review the knowledge base guidelines
3. Create an issue in the repository
