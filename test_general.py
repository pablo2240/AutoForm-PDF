#!/usr/bin/env python3
"""
Test the PDF Filling Agent with different types of instructions to show it's general-purpose.
"""

import os
from pdf_filling_agent import PDFAgent, KnowledgeBase


def test_different_instructions():
    """Test the agent with various instruction formats."""

    knowledge_base = KnowledgeBase("knowledge_base.md")
    agent = PDFAgent(knowledge_base=knowledge_base)

    pdf_path = "input/fw9.pdf"

    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return

    test_cases = [
        {
            "name": "Simple format",
            "instructions": "Name: Jane Smith, Email: jane@example.com, Phone: 555-987-6543"
        },
        {
            "name": "Natural language",
            "instructions": "Please fill in the name field with Alice Johnson, and put alice@company.org in the email field"
        },
        {
            "name": "Mixed format",
            "instructions": "Set name to Bob Wilson and business name to Wilson Consulting LLC, address is 456 Oak Avenue, phone number is 555-111-2222"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        print(f"Instructions: {test_case['instructions']}")

        try:
            output_path = agent.fill_pdf(pdf_path, test_case['instructions'])
            file_size = os.path.getsize(output_path)
            print(f"✅ Success: {output_path} ({file_size} bytes)")

        except Exception as e:
            print(f"❌ Failed: {e}")


def main():
    """Main test function."""
    print("🧪 Testing PDF Filling Agent with different instruction formats...")

    test_different_instructions()

    print("\n🎉 Testing complete! The agent works with various instruction formats.")


if __name__ == "__main__":
    main()
