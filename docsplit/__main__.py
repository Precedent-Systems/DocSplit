#!/usr/bin/env python3
"""
DocSplit CLI Interface
Usage:
  docsplit split <court_record.pdf> [output_dir] [--repair-ocr]
  docsplit inspect <court_record.pdf>
  docsplit audit <pdf_or_dir>
  docsplit repair <pdf_or_dir> [--out-dir DIR] [--overlay-json FILE] [--no-rotate] [--no-deskew]
"""

import sys
import os
import json
import argparse

DOCSPLIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOCSPLIT_ROOT)

from docsplit.slicer import (
    split_pdf_by_bookmarks,
    inspect_pdf_docket,
    audit_pdf_ocr,
    repair_pdf_ocr,
)


def _collect_pdfs(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target]
    return sorted(
        os.path.join(target, f)
        for f in os.listdir(target)
        if f.lower().endswith(".pdf")
    )


def _load_overlay_map(overlay_json: str | None) -> dict[str, list[dict]]:
    if not overlay_json:
        return {}
    with open(overlay_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    mapping: dict[str, list[dict]] = {}
    for item in data:
        fn = item.get("file", "")
        if fn:
            mapping.setdefault(fn, []).extend(item.get("pages", []))
    return mapping


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print("\n✂️ DocSplit — Open-Source Legal Document Slicer & OCR Auditor")
        print("--------------------------------------------------")
        print("  docsplit split <court_record.pdf> [out_dir] [--repair-ocr]  Slice PDF & check/repair OCR")
        print("  docsplit inspect <court_record.pdf>                         View internal document TOC & page ranges")
        print("  docsplit audit <pdf_or_dir>                                 Audit PDF(s) for missing/garbled OCR")
        print("  docsplit repair <pdf_or_dir> [--out-dir DIR] [--overlay-json FILE] [--no-rotate] [--no-deskew]")
        print("--------------------------------------------------\n")
        return

    cmd = sys.argv[1].lower()

    if cmd == "split":
        parser = argparse.ArgumentParser(prog="docsplit split", add_help=False)
        parser.add_argument("pdf_path")
        parser.add_argument("out_dir", nargs="?", default=None)
        parser.add_argument("--repair-ocr", action="store_true")
        args = parser.parse_args(sys.argv[2:])
        if not os.path.exists(args.pdf_path):
            print("❌ Please provide a valid court PDF path. Usage: docsplit split <court_record.pdf> [out_dir] [--repair-ocr]")
            return
        split_pdf_by_bookmarks(args.pdf_path, args.out_dir, repair_ocr=args.repair_ocr)

    elif cmd == "inspect":
        pdf_path = sys.argv[2] if len(sys.argv) > 2 else ""
        if not pdf_path or not os.path.exists(pdf_path):
            print("❌ Please provide a valid court PDF path. Usage: docsplit inspect <court_record.pdf>")
            return
        info = inspect_pdf_docket(pdf_path)
        print(json.dumps(info, indent=2))

    elif cmd == "audit":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if not target or not os.path.exists(target):
            print("❌ Please provide a valid PDF or directory path. Usage: docsplit audit <pdf_or_dir>")
            return
        pdfs = _collect_pdfs(target)
        reports = [r for r in (audit_pdf_ocr(p) for p in pdfs) if r["flagged_pages"] > 0]
        print(json.dumps({"total_pdfs": len(pdfs), "flagged_pdfs": len(reports), "details": reports}, indent=2))

    elif cmd == "repair":
        parser = argparse.ArgumentParser(prog="docsplit repair", add_help=False)
        parser.add_argument("target")
        parser.add_argument("--out-dir", default=None)
        parser.add_argument("--overlay-json", default=None)
        parser.add_argument("--no-rotate", action="store_true")
        parser.add_argument("--no-deskew", action="store_true")
        args = parser.parse_args(sys.argv[2:])
        if not os.path.exists(args.target):
            print("❌ Please provide a valid PDF or directory path. Usage: docsplit repair <pdf_or_dir>")
            return
        overlay_map = _load_overlay_map(args.overlay_json)
        pdfs = _collect_pdfs(args.target)
        results = []
        for p in pdfs:
            out_p = os.path.join(args.out_dir, os.path.basename(p)) if args.out_dir else None
            entries = overlay_map.get(os.path.basename(p))
            rep = repair_pdf_ocr(
                p,
                out_path=out_p,
                rotate=not args.no_rotate,
                deskew=not args.no_deskew,
                overlay_entries=entries,
            )
            if rep["track1_repaired_pages"] or rep["track2_overlaid_pages"] or rep["remaining_flagged_pages"]:
                results.append(rep)
        print(json.dumps({"total_pdfs": len(pdfs), "processed": len(results), "results": results}, indent=2))

    else:
        print(f"Unknown command '{cmd}'. Run 'docsplit --help' for options.")


if __name__ == "__main__":
    main()
