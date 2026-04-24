#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

TRANSPORT_SUFFIX_RE = re.compile(
    r"---[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def derive_source_name(pdf_path: Path, source_name: str | None = None) -> str:
    raw_name = (source_name or pdf_path.name).strip()
    candidate = Path(raw_name).name
    stem = TRANSPORT_SUFFIX_RE.sub("", Path(candidate).stem)
    suffix = Path(candidate).suffix or pdf_path.suffix
    cleaned = f"{stem}{suffix}".strip()
    return cleaned or pdf_path.name


def prepare_upload_copy(pdf_path: Path, work_dir: Path, source_name: str | None = None) -> tuple[Path, str]:
    resolved_source_name = derive_source_name(pdf_path, source_name)
    if pdf_path.name == resolved_source_name:
        return pdf_path, resolved_source_name

    upload_dir = work_dir / "upload_source"
    upload_dir.mkdir(parents=True, exist_ok=True)
    staged_path = upload_dir / resolved_source_name
    if pdf_path.resolve() != staged_path.resolve():
        shutil.copy2(pdf_path, staged_path)
    return staged_path, resolved_source_name
