# DocSplit: Open-Source Legal Document Slicer & OCR Auditor

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)]()
[![Court Grade](https://img.shields.io/badge/Court_Grade-Docket_Slicer-emerald.svg)]()

**DocSplit** (by Precedent Systems Org) is an open-source Python CLI and browser-local docket auditor designed to slice massive court records, appellate dockets, and exhibit packets into cleanly titled individual document PDFs—while auditing and repairing un-OCR'd scans, broken font encodings, and garbled handwriting text layers.

---

## 🎯 Key Differentiators

| Feature | Standard PDF Splitters | DocSplit |
|---|---|---|
| **Splitting Logic** | Fixed page intervals or manual page numbers | **Smart Bookmark TOC & Legal Header Boundaries** |
| **File Size Limits** | Restricted / Paid tiers (&lt; 50 pages) | **Unlimited (Local CLI & Browser-Local Auditor)** |
| **Document Naming** | `part_1.pdf`, `part_2.pdf` | **`001_2023-06-12_Complaint_p1-79.pdf`** |
| **OCR Health Guard** | None (silently preserves broken/missing OCR) | **Detects `ZERO_TEXT`, `BROKEN_ENCODING`, `GARBLED_OCR`, & `PLEADING_LINE_GAP`** |
| **Two-Track OCR Repair** | None | **`ocrmypdf` selective re-OCR + Vision-verified `render_mode=3` text overlay** |

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/Precedent-Systems/DocSplit.git
cd DocSplit
pip install -e .
```

Optional system tools for `docsplit repair`: `ocrmypdf` and `tesseract-ocr`.

### 2. Slice a Court Record PDF (with Automatic OCR Health Check)

```bash
docsplit split "/path/to/23CV23393 Volume 1.pdf"
# Or slice and automatically repair flagged OCR pages in one pass:
docsplit split "/path/to/23CV23393 Volume 1.pdf" --repair-ocr
```

### 3. Inspect Docket TOC & Page Ranges

```bash
docsplit inspect "/path/to/23CV23393 Volume 1.pdf"
```

### 4. Audit PDF(s) for Missing, Encoding-Broken, or Garbled Handwriting OCR

```bash
docsplit audit "/path/to/sliced_folder_or_file.pdf"
```

### 5. Repair Flagged Pages (Track 1 `ocrmypdf` + Track 2 Curated Handwriting Overlays)

```bash
docsplit repair "/path/to/sliced_folder_or_file.pdf"
# With verified handwriting / rotation JSON overlay manifest:
docsplit repair "/path/to/sliced_folder" --overlay-json overlays.json
```

---

## ⚖️ License

Distributed under the **GNU Affero General Public License v3.0 (AGPLv3)**. Free forever for pro se litigants, legal aid organizations, and public defenders.
