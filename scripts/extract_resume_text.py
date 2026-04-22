#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def extract_with_pypdf(pdf_path: Path) -> str:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n\n".join(pages).strip()
    if not text:
        raise RuntimeError("empty text extracted from pdf")
    return text


def extract_with_pdftotext(pdf_path: Path) -> str:
    proc = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pdftotext failed")
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError("empty text extracted from pdf")
    return text


def extract_text(pdf_path: Path) -> str:
    errors: list[str] = []
    try:
        return extract_with_pypdf(pdf_path)
    except Exception as e:
        errors.append(f"pypdf: {e}")
    try:
        return extract_with_pdftotext(pdf_path)
    except Exception as e:
        errors.append(f"pdftotext: {e}")
    raise RuntimeError("; ".join(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract plain text from a resume PDF")
    ap.add_argument("pdf_path")
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    text = extract_text(pdf_path)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
