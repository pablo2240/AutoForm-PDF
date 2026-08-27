"""
Command line interface for the PDF Filling Agent.
"""

import os
import sys
import argparse
from .agent import PDFAgent
from .knowledge_base import KnowledgeBase


def main():
    """Main entry point for the PDF filling agent."""
    parser = argparse.ArgumentParser(description="AI-powered PDF filling agent")
    parser.add_argument("pdf_path", help="Path to the input PDF file")
    parser.add_argument("instructions", help="Instructions for filling the PDF")
    parser.add_argument("--output-dir", "-o", default="output",
                       help="Output directory for filled PDF")
    parser.add_argument("--knowledge-file", "-k",
                       help="Path to knowledge base file")
    parser.add_argument("--api-key", help="OpenRouter API key")
    parser.add_argument("--model", default="qwen/qwen3-max",
                       help="Model to use for code generation")
    parser.add_argument("--mode", default="auto", choices=["auto", "widget", "visual"],
                       help="Form filling mode: auto, widget (AcroForm), or visual (flat PDF)")

    args = parser.parse_args()

    try:
        # Initialize knowledge base
        knowledge_base = KnowledgeBase(args.knowledge_file)

        # Initialize agent
        agent = PDFAgent(
            api_key=args.api_key,
            model=args.model,
            knowledge_base=knowledge_base
        )

        # Ensure output directory exists
        os.makedirs(args.output_dir, exist_ok=True)

        # Fill the PDF
        print(f"Processing PDF: {args.pdf_path}")
        print(f"Instructions: {args.instructions}")
        print(f"Mode: {args.mode}")

        output_path = agent.fill_pdf(
            args.pdf_path,
            args.instructions,
            args.output_dir,
            mode=args.mode
        )

        print(f"[SUCCESS] Successfully filled PDF: {output_path}")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
