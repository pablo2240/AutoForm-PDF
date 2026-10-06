#!/usr/bin/env python
"""
Reference library CLI: manage the reusable knowledge extracted from reference forms.

    python scripts/reference_library.py sync [--force]
    python scripts/reference_library.py add path/to/form.pdf [--family proveedor]
    python scripts/reference_library.py remove proveedor/form.pdf
    python scripts/reference_library.py list
    python scripts/reference_library.py search "Identificación fiscal" [-k 5] [--family proveedor]
    python scripts/reference_library.py classify path/to/new_form.pdf
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(dotenv_path=ROOT_DIR / ".env", override=True)

from backend.pdf_filling_agent.reference_library import ReferenceLibrary  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="mirror docs/referencias into the database")
    s.add_argument("--force", action="store_true", help="re-process every document")
    a = sub.add_parser("add", help="copy a PDF into the library and process it")
    a.add_argument("pdf")
    a.add_argument("--family", default=None)
    r = sub.add_parser("remove", help="delete a reference (doc_id as shown by `list`)")
    r.add_argument("doc_id")
    sub.add_parser("list", help="show documents, families and vocabulary size")
    q = sub.add_parser("search", help="semantic search over reference fields")
    q.add_argument("query")
    q.add_argument("-k", type=int, default=5)
    q.add_argument("--family", default=None)
    c = sub.add_parser("classify", help="classify a PDF against the known families")
    c.add_argument("pdf")
    args = ap.parse_args()

    lib = ReferenceLibrary()
    if args.cmd == "sync":
        out = lib.sync(force=args.force)
    elif args.cmd == "add":
        with open(args.pdf, "rb") as f:
            out = lib.add_document(os.path.basename(args.pdf), f.read(), args.family)
    elif args.cmd == "remove":
        out = {"removed": lib.remove_document(args.doc_id)}
    elif args.cmd == "list":
        lib.sync()
        out = lib.status()
    elif args.cmd == "search":
        lib.sync()
        out = lib.search(args.query, top_k=args.k, family=args.family)
    else:
        lib.sync()
        out = lib.classify_pdf(args.pdf).to_dict()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
