"""
DocSplit Core Legal Slicer Engine
Analyzes court records, appellate dockets, and exhibit packets.
Extracts internal PDF bookmarks or scans legal text headers to split massive court PDFs into individual document files.
"""

import os
import re
import json
import fitz  # PyMuPDF

LEGAL_HEADER_PATTERNS = [
    r'IN THE CIRCUIT COURT OF THE STATE OF OREGON',
    r'IN THE DISTRICT COURT OF THE UNITED STATES',
    r'IN THE COURT OF APPEALS OF THE STATE OF OREGON',
    r'COMPLAINT',
    r'MOTION TO',
    r'DECLARATION OF',
    r'AFFIDAVIT OF',
    r'ORDER',
    r'GENERAL JUDGMENT',
    r'LIMITED JUDGMENT',
    r'NOTICE OF',
    r'RESPONSE TO',
    r'REPLY TO'
]

def clean_filename(title):
    clean = re.sub(r'[^a-zA-Z0-9_\-\. ]', '_', title).strip()
    clean = re.sub(r'\s+', '_', clean)
    return clean[:80]

def inspect_pdf_docket(pdf_path):
    """
    Returns metadata and list of document bookmarks in PDF.
    """
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    
    info = {
        "filename": os.path.basename(pdf_path),
        "total_pages": len(doc),
        "total_documents": len(toc),
        "documents": []
    }

    total_pages = len(doc)
    for idx, item in enumerate(toc):
        title = item[1]
        start_page = item[2] - 1
        end_page = toc[idx + 1][2] - 1 if idx + 1 < len(toc) else total_pages
        if start_page >= end_page or start_page >= total_pages:
            end_page = min(start_page + 1, total_pages)
        
        info["documents"].append({
            "index": idx + 1,
            "title": title,
            "start_page": start_page + 1,
            "end_page": end_page,
            "page_count": end_page - start_page
        })

    return info

def split_pdf_by_bookmarks(pdf_path, output_dir=None):
    """
    Slices a PDF into individual document files using internal Table of Contents / Bookmarks.
    """
    if not output_dir:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = os.path.join(os.path.dirname(pdf_path), f"{base_name}_Split_Documents")

    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    total_pages = len(doc)

    print(f"==================================================")
    print(f" ✂️ DOCSPLIT: Slicing {os.path.basename(pdf_path)}")
    print(f"   Total Pages: {total_pages} | Documents Found: {len(toc)}")
    print(f"==================================================")

    created_files = []

    if toc:
        for idx, item in enumerate(toc):
            title = item[1]
            start_page = item[2] - 1
            end_page = toc[idx + 1][2] - 1 if idx + 1 < len(toc) else total_pages
            if start_page >= end_page or start_page >= total_pages:
                end_page = min(start_page + 1, total_pages)

            c_title = clean_filename(title)
            out_fn = f"{idx+1:03d}_{c_title}_p{start_page+1}-{end_page}.pdf"
            out_fp = os.path.join(output_dir, out_fn)

            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page-1)
            new_doc.save(out_fp)
            new_doc.close()

            created_files.append(out_fp)
            print(f"  [{idx+1:03d}] {title[:45]:<45} (p. {start_page+1}-{end_page}) -> {out_fn}")
    else:
        print("⚠️ No bookmark TOC found. Falling back to 50-page chunk splitting.")
        chunk_size = 50
        for idx in range(0, total_pages, chunk_size):
            end = min(idx + chunk_size, total_pages)
            out_fn = f"Chunk_{(idx//chunk_size)+1:02d}_p{idx+1}-{end}.pdf"
            out_fp = os.path.join(output_dir, out_fn)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=idx, to_page=end-1)
            new_doc.save(out_fp)
            new_doc.close()
            created_files.append(out_fp)

    print(f"\n✅ Successfully created {len(created_files)} individual document PDFs!")
    print(f"📂 Output Directory: {output_dir}\n")
    return output_dir, created_files
