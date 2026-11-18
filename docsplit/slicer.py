"""
DocSplit Core Legal Slicer Engine
Analyzes court records, appellate dockets, and exhibit packets.
Extracts internal PDF bookmarks or scans legal text headers to split massive court PDFs into individual document files.
"""

import os
import re
import json
import shutil
import tempfile
import subprocess
import fitz  # PyMuPDF

WEIRD_OCR_CHARS = set("~^|\\`<>[]{}=+")
PLEADING_LINE_RE = re.compile(r"^\d{1,2}$")


def _page_ink_ratio(page: fitz.Page) -> float:
    """Estimate fraction of non-white pixels on a page at 72 DPI grayscale."""
    pix = page.get_pixmap(dpi=72, colorspace=fitz.csGRAY, alpha=False)
    samples = pix.samples
    if not samples:
        return 0.0
    dark = sum(1 for b in samples if b < 200)
    return dark / len(samples)


def audit_page_ocr(page: fitz.Page) -> list[str]:
    """Return OCR quality flags for a single PyMuPDF page."""
    stripped = page.get_text("text").strip()
    nchars = len(stripped)
    imgs = len(page.get_images())
    if imgs == 0:
        return []

    flags = []
    if nchars == 0:
        return ["ZERO_TEXT"]
    if nchars < 80:
        flags.append("LOW_TEXT")

    ctrl = sum(1 for c in stripped if (ord(c) < 32 and c not in "\n\r\t") or c == "\ufffd")
    if ctrl >= 5 or (ctrl / max(nchars, 1) > 0.05):
        flags.append("BROKEN_ENCODING")

    bad_lines = 0
    bare_nums = 0
    consec_bare = 0
    max_consec_bare = 0
    for raw in stripped.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if PLEADING_LINE_RE.match(ln) and 1 <= int(ln) <= 28:
            bare_nums += 1
            consec_bare += 1
            max_consec_bare = max(max_consec_bare, consec_bare)
            continue
        consec_bare = 0
        if len(ln) < 5 or set(ln) <= set("_-. "):
            continue
        ln_norm = ln.replace("\u2009", " ").replace("\u2011", "-")
        bad = sum(1 for c in ln_norm if not (c.isalnum() or c in " .,;:'\"-()/?!&$%#[]@\x01"))
        wc = sum(1 for c in ln_norm if c in WEIRD_OCR_CHARS)
        tokens = ln_norm.split()
        frag = sum(1 for t in tokens if len(t) <= 2 and not t.isalnum())
        if (bad / len(ln_norm) > 0.15) or (wc >= 3 and wc / len(ln_norm) > 0.08) or (len(tokens) >= 4 and frag / len(tokens) > 0.45):
            bad_lines += 1

    if bad_lines >= 2:
        flags.append("GARBLED_OCR")
    if bare_nums >= 6 and max_consec_bare >= 4 and _page_ink_ratio(page) > 0.018:
        flags.append("PLEADING_LINE_GAP")
    return flags


def audit_pdf_ocr(pdf_path: str) -> dict:
    """Audit all pages of a PDF for missing, garbled, or encoding-broken OCR layers."""
    doc = fitz.open(pdf_path)
    issues = []
    for idx, page in enumerate(doc):
        flags = audit_page_ocr(page)
        if flags and flags != ["PLEADING_LINE_GAP"]:
            issues.append({"page": idx + 1, "flags": flags, "chars": len(page.get_text("text").strip())})
    total = len(doc)
    doc.close()
    return {
        "filename": os.path.basename(pdf_path),
        "total_pages": total,
        "flagged_pages": len(issues),
        "issues": issues,
    }


def apply_text_overlay(pdf_path: str, page_entries: list[dict], out_path: str | None = None) -> int:
    """
    Replace broken or missing text layers on specified 1-based pages with clean
    invisible searchable text (render_mode=3) without altering visual pixels.
    """
    target_path = out_path or pdf_path
    doc = fitz.open(pdf_path)
    updated = 0

    for entry in page_entries:
        pno = int(entry["page"])
        if pno < 1 or pno > len(doc):
            continue
        page = doc[pno - 1]

        # Wipe existing text across unrotated mediabox & rect BEFORE applying rotation.
        page.add_redact_annot(page.rect, fill=False)
        page.add_redact_annot(page.mediabox, fill=False)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)

        rot = entry.get("rotate_deg")
        if rot and page.rotation == 0:
            page.set_rotation(int(rot))

        rect = page.rect
        fontsize = 6.5
        max_w = max(80.0, rect.width - 36.0)
        lines = []
        for raw_ln in str(entry.get("text", "")).splitlines():
            raw_ln = raw_ln.strip()
            if not raw_ln:
                continue
            cur = ""
            for w in raw_ln.split(" "):
                cand = f"{cur} {w}".strip() if cur else w
                if fitz.get_text_length(cand, fontname="helv", fontsize=fontsize) <= max_w:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)

        x0 = rect.x0 + 18.0
        y = rect.y0 + 20.0
        max_y = rect.y1 - 14.0
        step = min(9.5, max(5.0, (max_y - y) / max(len(lines), 1)))
        for ln in lines:
            if y > max_y:
                y = rect.y0 + 20.0
            page.insert_text((x0, y), ln, fontsize=fontsize, fontname="helv", render_mode=3)
            y += step
        updated += 1

    if updated > 0:
        tmp_path = f"{target_path}.tmp_overlay.pdf"
        doc.save(tmp_path, deflate=True)
        doc.close()
        os.replace(tmp_path, target_path)
    else:
        doc.close()
    return updated


def _run_ocrmypdf_chunk(sub_in: str, sub_out: str, rotate: bool = True, deskew: bool = True) -> bool:
    """Run ocrmypdf on a sub-PDF, falling back to 220 DPI PyMuPDF+Tesseract if needed."""
    if shutil.which("ocrmypdf"):
        cmd = ["ocrmypdf", "--force-ocr", "--jobs", "4", "--output-type", "pdf", "--optimize", "0"]
        if rotate:
            cmd.append("--rotate-pages")
        if deskew:
            cmd.append("--deskew")
        cmd.extend([sub_in, sub_out])
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if res.returncode == 0 and os.path.exists(sub_out):
            return True

    if not shutil.which("tesseract"):
        return False

    doc = fitz.open(sub_in)
    tmp_dir = tempfile.mkdtemp(prefix="docsplit_fb_")
    try:
        merged = fitz.open()
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=220)
            img_p = os.path.join(tmp_dir, f"p_{i:04d}.png")
            pix.save(img_p)
            base_out = os.path.join(tmp_dir, f"p_{i:04d}_ocr")
            r = subprocess.run(["tesseract", img_p, base_out, "pdf"], capture_output=True, text=True)
            pdf_p = f"{base_out}.pdf"
            if r.returncode == 0 and os.path.exists(pdf_p):
                pdoc = fitz.open(pdf_p)
                merged.insert_pdf(pdoc)
                pdoc.close()
            else:
                merged.insert_pdf(doc, from_page=i, to_page=i)
        merged.save(sub_out, deflate=True)
        merged.close()
        doc.close()
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def repair_pdf_ocr(
    pdf_path: str,
    out_path: str | None = None,
    rotate: bool = True,
    deskew: bool = True,
    overlay_entries: list[dict] | None = None,
    chunk_size: int = 80,
) -> dict:
    """
    Repair missing, broken-encoding, or garbled OCR pages in a PDF using Track 1
    (selective ocrmypdf/tesseract splicing) and optional Track 2 curated overlays.
    """
    target_path = out_path or pdf_path
    if target_path != pdf_path:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        shutil.copy2(pdf_path, target_path)

    overlay_pages = {int(e["page"]) for e in (overlay_entries or [])}
    audit = audit_pdf_ocr(target_path)
    t1_pages = sorted(
        iss["page"]
        for iss in audit["issues"]
        if iss["page"] not in overlay_pages
    )

    t1_count = 0
    if t1_pages:
        doc = fitz.open(target_path)
        total = len(doc)
        doc.close()
        for start in range(0, len(t1_pages), chunk_size):
            chunk = t1_pages[start:start + chunk_size]
            tmp_dir = tempfile.mkdtemp(prefix="docsplit_t1_")
            try:
                sub_in = os.path.join(tmp_dir, "sub_in.pdf")
                sub_out = os.path.join(tmp_dir, "sub_out.pdf")
                orig_doc = fitz.open(target_path)
                sub_doc = fitz.open()
                for p in chunk:
                    sub_doc.insert_pdf(orig_doc, from_page=p - 1, to_page=p - 1)
                sub_doc.save(sub_in)
                sub_doc.close()
                orig_doc.close()

                if _run_ocrmypdf_chunk(sub_in, sub_out, rotate=rotate, deskew=deskew) and os.path.exists(sub_out):
                    orig_doc = fitz.open(target_path)
                    rep_doc = fitz.open(sub_out)
                    if len(rep_doc) == len(chunk):
                        rep_map = {p: idx for idx, p in enumerate(chunk)}
                        new_doc = fitz.open()
                        for p in range(1, total + 1):
                            if p in rep_map:
                                new_doc.insert_pdf(rep_doc, from_page=rep_map[p], to_page=rep_map[p])
                            else:
                                new_doc.insert_pdf(orig_doc, from_page=p - 1, to_page=p - 1)
                        tmp_out = f"{target_path}.tmp_t1.pdf"
                        new_doc.save(tmp_out, deflate=True)
                        new_doc.close()
                        os.replace(tmp_out, target_path)
                        t1_count += len(chunk)
                    orig_doc.close()
                    rep_doc.close()
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    t2_count = 0
    if overlay_entries:
        t2_count = apply_text_overlay(target_path, overlay_entries, out_path=target_path)

    post = audit_pdf_ocr(target_path)
    return {
        "filename": os.path.basename(target_path),
        "total_pages": post["total_pages"],
        "track1_repaired_pages": t1_count,
        "track2_overlaid_pages": t2_count,
        "remaining_flagged_pages": post["flagged_pages"],
    }

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

def split_pdf_by_bookmarks(pdf_path, output_dir=None, repair_ocr=False):
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
    print(f"📂 Output Directory: {output_dir}")

    ocr_warnings = []
    for fp in created_files:
        rep = audit_pdf_ocr(fp)
        if rep["flagged_pages"] > 0:
            ocr_warnings.append((rep["filename"], rep["flagged_pages"], rep["total_pages"]))
    if ocr_warnings:
        if repair_ocr:
            print(f"🔧 Repairing OCR on {len(ocr_warnings)} sliced PDF(s)...")
            for fn, _, _ in ocr_warnings:
                rep_res = repair_pdf_ocr(os.path.join(output_dir, fn))
                print(f"   ✓ {fn}: Track1={rep_res['track1_repaired_pages']}p, remaining={rep_res['remaining_flagged_pages']}p")
        else:
            print(f"⚠️  OCR HEALTH WARNING: {len(ocr_warnings)} sliced PDF(s) contain un-OCR'd, garbled, or handwritten-gap pages:")
            for fn, f_cnt, t_cnt in ocr_warnings[:15]:
                print(f"   - {fn}: {f_cnt}/{t_cnt} flagged pages")
            if len(ocr_warnings) > 15:
                print(f"   ... and {len(ocr_warnings) - 15} more (run 'docsplit audit <dir>' or 'docsplit repair <dir>')")
    print()
    return output_dir, created_files
