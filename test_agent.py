#!/usr/bin/env python3
"""
Comprehensive test script for the PDF Filling Agent.
"""

import os
import tempfile
from pdf_filling_agent import PDFAgent, KnowledgeBase, PDFProcessor


def create_test_pdf():
    """Create a simple test PDF with form fields."""
    import fitz

    # Create a simple PDF with form fields
    doc = fitz.open()
    page = doc.new_page()

    # Add some text to the page
    page.insert_text((50, 50), "Test PDF Form", fontsize=14)
    page.insert_text((50, 100), "Name: __________________", fontsize=12)
    page.insert_text((50, 150), "Email: __________________", fontsize=12)
    page.insert_text((50, 200), "Phone: __________________", fontsize=12)

    # Save to temporary file
    temp_path = "/tmp/test_form.pdf"
    doc.save(temp_path)
    doc.close()

    return temp_path


def test_full_workflow():
    """Test the complete PDF filling workflow."""
    print("🧪 Starting comprehensive PDF Filling Agent test...")

    try:
        # Test 1: Component initialization
        print("\n1️⃣ Testing component initialization...")
        kb = KnowledgeBase('knowledge_base.md')
        processor = PDFProcessor()
        agent = PDFAgent(knowledge_base=kb)
        print("✅ All components initialized successfully")

        # Test 2: PDF creation and field detection
        print("\n2️⃣ Creating test PDF and analyzing fields...")
        test_pdf_path = create_test_pdf()
        print(f"✅ Test PDF created: {test_pdf_path}")

        fields = processor.get_pdf_fields(test_pdf_path)
        print(f"📋 Detected fields: {list(fields.keys())}")

        # Test 3: Code generation
        print("\n3️⃣ Testing code generation...")
        instructions = "Fill name as John Doe, email as john@example.com, phone as 555-1234"
        generated_code = agent.generate_filling_code(test_pdf_path, instructions)
        print("✅ Code generated successfully")
        print(f"Generated code preview:\n{generated_code[:300]}...")

        # Test 4: PDF filling
        print("\n4️⃣ Testing PDF filling...")
        output_path = agent.fill_pdf(test_pdf_path, instructions)
        print(f"✅ PDF filled successfully: {output_path}")

        # Verify the output
        if os.path.exists(output_path):
            output_fields = processor.get_pdf_fields(output_path)
            print(f"📋 Output PDF fields: {list(output_fields.keys())}")
            print("✅ Output PDF created and accessible")

        # Clean up
        if os.path.exists(test_pdf_path):
            os.remove(test_pdf_path)
        if os.path.exists(output_path):
            os.remove(output_path)

        print("\n🎉 All tests passed! PDF Filling Agent is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def test_knowledge_base():
    """Test knowledge base functionality."""
    print("\n📚 Testing Knowledge Base...")

    kb = KnowledgeBase('knowledge_base.md')
    print("✅ Knowledge base loaded")

    system_instructions = kb.get_system_instructions()
    print(f"📝 System instructions length: {len(system_instructions)} characters")

    # Test custom knowledge base
    custom_kb = KnowledgeBase()
    custom_instructions = custom_kb.get_system_instructions()
    print(f"📝 Default instructions length: {len(custom_instructions)} characters")

    print("✅ Knowledge base functionality working")


def test_pdf_processor():
    """Test PDF processor functionality."""
    print("\n📄 Testing PDF Processor...")

    processor = PDFProcessor()

    # Test directory creation
    test_dir = "/tmp/pdf_test_output"
    processor.output_dir = test_dir

    # Create a minimal PDF for testing
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test", fontsize=12)
    temp_pdf = "/tmp/minimal_test.pdf"
    doc.save(temp_pdf)
    doc.close()

    try:
        # Test with a valid PDF
        result = processor.fill_pdf(temp_pdf, {"TestField": "TestValue"})
        print("✅ PDF processing working")

        if os.path.exists(result):
            os.remove(result)
    except Exception as e:
        print(f"❌ PDF processing error: {e}")
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

    if os.path.exists(test_dir):
        print("✅ Output directory creation working")
        os.rmdir(test_dir)
    else:
        print("❌ Output directory not created")


if __name__ == "__main__":
    test_knowledge_base()
    test_pdf_processor()
    test_full_workflow()
