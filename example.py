#!/usr/bin/env python3
"""
Example script demonstrating how to use the PDF Filling Agent with any PDF.
"""

import os
from pdf_filling_agent import PDFAgent, KnowledgeBase


def main():
    """Example usage of the PDF Filling Agent."""

    # Initialize the agent with custom knowledge base
    knowledge_base = KnowledgeBase("knowledge_base.md")
    agent = PDFAgent(knowledge_base=knowledge_base)

    # Use the fw9.pdf file that exists in input directory
    pdf_path = "input/fw9.pdf"

    # Check if PDF exists
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return

    # Example instructions for filling a tax form
    instructions = """
    Fill out the W-9 form with the following information:
    - Name: John Doe
    - Business name: Doe Enterprises LLC
    - Address: 123 Business St, Anytown, CA 12345
    - Tax ID: 12-3456789
    - Phone: 555-123-4567
    - Email: john.doe@business.com
    """

    try:
        # Fill the PDF
        output_path = agent.fill_pdf(pdf_path, instructions)

        print(f"✅ Successfully filled PDF: {output_path}")
        print(f"📁 Output saved to: {os.path.abspath(output_path)}")

        # Show file size
        file_size = os.path.getsize(output_path)
        print(f"📄 Output file size: {file_size} bytes")

    except Exception as e:
        print(f"❌ Error filling PDF: {e}")


if __name__ == "__main__":
    main()
