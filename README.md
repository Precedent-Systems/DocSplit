# DocSplit: Open-Source Legal Document & Court Record Slicer

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)]()
[![Court Grade](https://img.shields.io/badge/Court_Grade-Docket_Slicer-emerald.svg)]()

**DocSplit** (by Precedent Systems Org) is an open-source Python tool designed to slice massive court records, appellate dockets, and exhibit packets into cleanly titled individual document PDFs based on internal PDF bookmark Table of Contents and legal header boundaries.

Unlike standard PDF splitters that rely on arbitrary fixed page intervals (e.g., "split every 10 pages"), DocSplit understands **court docket structure** and extracts individual filings (Complaints, Motions, Declarations, Orders) with exact start/end page precision.

---

## 🎯 Key Differentiators

| Feature | Standard PDF Splitters (SmallPDF, Acrobat) | DocSplit |
|---|---|---|
| **Splitting Logic** | Fixed page intervals or manual page numbers | **Smart Bookmark TOC & Legal Header Boundaries** |
| **File Size Limits** | Restricted / Paid tiers (&lt; 50 pages) | **Unlimited (Local CLI)** |
| **Document Naming** | `part_1.pdf`, `part_2.pdf` | **`001_2023-06-12_Complaint_p1-79.pdf`** |
| **Speed** | Slow web uploads (200MB = minutes) | **Local processing (1,000 pages in &lt; 5 sec)** |

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/Precedent-Systems/DocSplit.git
cd DocSplit
pip install -e .
```

### 2. Slice a Court Record PDF

```bash
docsplit split "/path/to/23CV23393 Volume 1.pdf"
```

### 3. Inspect Docket TOC & Page Ranges

```bash
docsplit inspect "/path/to/23CV23393 Volume 1.pdf"
```

---

## ⚖️ License

Distributed under the **GNU Affero General Public License v3.0 (AGPLv3)**. Free forever for pro se litigants, legal aid organizations, and public defenders.
