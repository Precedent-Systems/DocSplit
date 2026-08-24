#!/usr/bin/env python3
"""
DocSplit CLI Interface
Usage:
  docsplit split <court_record.pdf> [output_dir]
  docsplit inspect <court_record.pdf>
"""

import sys
import os
import json

DOCSPLIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOCSPLIT_ROOT)

from docsplit.slicer import split_pdf_by_bookmarks, inspect_pdf_docket

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print("\n✂️ DocSplit — Open-Source Legal Document Slicer")
        print("--------------------------------------------------")
        print("  docsplit split <court_record.pdf> [out_dir]   Slice PDF into individual document files")
        print("  docsplit inspect <court_record.pdf>           View internal document TOC & page ranges")
        print("--------------------------------------------------\n")
        return

    cmd = sys.argv[1].lower()

    if cmd == "split":
        pdf_path = sys.argv[2] if len(sys.argv) > 2 else ""
        if not pdf_path or not os.path.exists(pdf_path):
            print("❌ Please provide a valid court PDF path. Usage: docsplit split <court_record.pdf>")
            return
        out_dir = sys.argv[3] if len(sys.argv) > 3 else None
        split_pdf_by_bookmarks(pdf_path, out_dir)

    elif cmd == "inspect":
        pdf_path = sys.argv[2] if len(sys.argv) > 2 else ""
        if not pdf_path or not os.path.exists(pdf_path):
            print("❌ Please provide a valid court PDF path. Usage: docsplit inspect <court_record.pdf>")
            return
        info = inspect_pdf_docket(pdf_path)
        print(json.dumps(info, indent=2))

    else:
        print(f"Unknown command '{cmd}'. Run 'docsplit --help' for options.")

if __name__ == "__main__":
    main()
