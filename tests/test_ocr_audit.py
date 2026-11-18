import sys
import unittest
import tempfile
from pathlib import Path
import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docsplit.slicer import audit_pdf_ocr, apply_text_overlay, repair_pdf_ocr


class TestDocSplitOcrAudit(unittest.TestCase):
    def test_audit_flags_zero_text_and_broken_encoding_and_garbled(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "test.pdf"
            doc = fitz.open()

            # Page 1: clean text (no images)
            p1 = doc.new_page()
            p1.insert_text((36, 50), "Clean legal text page with normal sentences and citations.")

            # Page 2: image with zero text
            p2 = doc.new_page()
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), 0)
            pix.clear_with(128)
            p2.insert_image(fitz.Rect(10, 10, 100, 100), stream=pix.tobytes("png"))

            # Page 3: image with garbled handwriting OCR
            p3 = doc.new_page()
            p3.insert_image(fitz.Rect(10, 10, 100, 100), stream=pix.tobytes("png"))
            p3.insert_text(
                (36, 50),
                "3. Duties include:\n"
                "E? ~/\\1 , ; 4~~ Opmt~-xo11.{ G.-rtJl...f ;\n"
                ":±1lti7~=• \\vruk'-'<-k; s+•ta~r,k~~,\n",
            )

            doc.save(str(pdf_path))
            doc.close()

            rep = audit_pdf_ocr(str(pdf_path))
            self.assertEqual(rep["total_pages"], 3)
            self.assertEqual(rep["flagged_pages"], 2)
            self.assertEqual(rep["issues"][0]["flags"], ["ZERO_TEXT"])
            self.assertIn("GARBLED_OCR", rep["issues"][1]["flags"])

    def test_overlay_wipes_broken_text_and_wraps_narrow_rotated_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "narrow_rot.pdf"
            doc = fitz.open()
            p = doc.new_page(width=288, height=432)
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60), 0)
            pix.clear_with(200)
            p.insert_image(fitz.Rect(10, 10, 270, 410), stream=pix.tobytes("png"))
            p.insert_text((20, 40), "\x01" * 80)
            doc.save(str(pdf_path))
            doc.close()

            res = repair_pdf_ocr(
                str(pdf_path),
                overlay_entries=[{
                    "page": 1,
                    "rotate_deg": 270,
                    "text": "Served 08/08/2025 to John Kosogot Senior VP Legal at Millennia Mortgage Corporation.",
                }],
            )
            self.assertEqual(res["track2_overlaid_pages"], 1)
            self.assertEqual(res["remaining_flagged_pages"], 0)

            reopened = fitz.open(str(pdf_path))
            extracted = " ".join(reopened[0].get_text("text").split())
            self.assertEqual(reopened[0].rotation, 270)
            self.assertNotIn("\x01", extracted)
            self.assertIn("John Kosogot Senior VP Legal", extracted)
            self.assertIn("Millennia Mortgage Corporation", extracted)
            reopened.close()


if __name__ == "__main__":
    unittest.main()
