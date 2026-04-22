#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
SINGLE_PLAN = ROOT / "resume_intake_tool_plan.py"
DEFAULT_ALLOWED_EXTS = {".pdf"}
SKIP_DIR_NAMES = {"__MACOSX"}
SKIP_FILE_PREFIXES = {".", "~"}


@dataclass
class IntakeInput:
    source_name: str
    pdf_path: Path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"命令失败: {' '.join(cmd)}")
    return proc


def safe_slug(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "resume"


def should_skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts) or path.name.startswith(tuple(SKIP_FILE_PREFIXES))


def copy_single_pdf(input_path: Path, staging_dir: Path) -> list[IntakeInput]:
    target = staging_dir / input_path.name
    shutil.copy2(input_path, target)
    return [IntakeInput(source_name=input_path.name, pdf_path=target)]


def decode_zip_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("utf-8")
    except Exception:
        pass
    try:
        return name.encode("cp437").decode("gbk")
    except Exception:
        return name


def extract_zip_inputs(zip_path: Path, staging_dir: Path) -> list[IntakeInput]:
    extracted_dir = staging_dir / "unzipped"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    inputs: list[IntakeInput] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            decoded_name = decode_zip_member_name(info)
            member_path = Path(decoded_name)
            if info.is_dir():
                continue
            if should_skip_path(member_path):
                continue
            if member_path.suffix.lower() not in DEFAULT_ALLOWED_EXTS:
                continue
            target_path = extracted_dir / member_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            inputs.append(IntakeInput(source_name=str(member_path), pdf_path=target_path))
    return sorted(inputs, key=lambda item: item.source_name)


def discover_inputs(input_path: Path, staging_dir: Path) -> list[IntakeInput]:
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return copy_single_pdf(input_path, staging_dir)
    if suffix == ".zip":
        return extract_zip_inputs(input_path, staging_dir)
    raise SystemExit(f"仅支持 PDF 或 ZIP 输入: {input_path}")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_job_plan(target_key: str, intake_input: IntakeInput, jobs_dir: Path, index: int) -> dict:
    job_id = f"job-{index:03d}-{safe_slug(Path(intake_input.source_name).stem)}"
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    normalized_pdf_path = job_dir / Path(intake_input.source_name).name
    if intake_input.pdf_path.resolve() != normalized_pdf_path.resolve():
        shutil.copy2(intake_input.pdf_path, normalized_pdf_path)
    else:
        normalized_pdf_path = intake_input.pdf_path

    plan_path = job_dir / "tool_plan.json"
    if plan_path.exists():
        plan = load_json(plan_path)
    else:
        proc = run([
            sys.executable,
            str(SINGLE_PLAN),
            "--target-key",
            target_key,
            "--pdf-path",
            str(normalized_pdf_path),
            "--work-dir",
            str(job_dir),
        ])
        plan = json.loads(proc.stdout)

    result_path = job_dir / "result.json"
    checkpoint_path = job_dir / "checkpoint.json"
    status = "planned"
    checkpoint = None
    if result_path.exists():
        result = load_json(result_path)
        status = result.get("status") or "planned"
    elif checkpoint_path.exists():
        checkpoint = load_json(checkpoint_path)

    payload = {
        "job_id": job_id,
        "source_name": intake_input.source_name,
        "pdf_path": str(normalized_pdf_path),
        "work_dir": str(job_dir),
        "plan": plan,
        "status": status,
    }
    if checkpoint:
        payload["checkpoint"] = checkpoint
    return payload


def clamp_workers(requested: int, item_count: int) -> int:
    return max(1, min(requested, item_count))


def summarize_items(items: Iterable[dict]) -> dict:
    results = list(items)
    summary = {
        "total": len(results),
        "planned": 0,
        "success": 0,
        "partial": 0,
        "failed": 0,
        "checkpointed": 0,
    }
    for item in results:
        status = item.get("status") or "planned"
        checkpoint = item.get("checkpoint") or {}
        if status in {"success", "partial", "failed"}:
            summary[status] += 1
            continue
        if checkpoint.get("stage") in {"created", "uploaded", "attachment_updated"}:
            summary["checkpointed"] += 1
        else:
            summary["planned"] += 1
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate batch resume-intake plans from a PDF or ZIP bundle")
    ap.add_argument("--target-key", default="resume_intake_v1")
    ap.add_argument("--input-path", required=True, help="Path to a PDF resume or a ZIP containing multiple PDFs")
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--max-workers", type=int, default=3)
    args = ap.parse_args()

    input_path = Path(args.input_path)
    if not input_path.exists():
        raise SystemExit(f"输入文件不存在: {input_path}")

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = work_dir / "staging"
    jobs_dir = work_dir / "jobs"
    staging_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    intake_inputs = discover_inputs(input_path, staging_dir)
    if not intake_inputs:
        raise SystemExit("未发现可处理的 PDF 文件")

    max_workers = clamp_workers(args.max_workers, len(intake_inputs))
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(build_job_plan, args.target_key, intake_input, jobs_dir, idx): (idx, intake_input)
            for idx, intake_input in enumerate(intake_inputs, start=1)
        }
        for future in as_completed(future_map):
            idx, intake_input = future_map[future]
            try:
                results.append(future.result())
            except Exception as err:
                job_id = f"job-{idx:03d}-{safe_slug(Path(intake_input.source_name).stem)}"
                job_dir = jobs_dir / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                error_payload = {
                    "job_id": job_id,
                    "source_name": intake_input.source_name,
                    "pdf_path": str(intake_input.pdf_path),
                    "work_dir": str(job_dir),
                    "status": "failed",
                    "error": str(err),
                }
                (job_dir / "error.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
                results.append(error_payload)

    results.sort(key=lambda item: item["job_id"])
    batch_plan = {
        "mode": "batch_resume_intake",
        "target_key": args.target_key,
        "input_path": str(input_path),
        "work_dir": str(work_dir),
        "source_type": input_path.suffix.lower().lstrip("."),
        "max_workers": max_workers,
        "summary": summarize_items(results),
        "execution": {
            "recommended_parallelism": max_workers,
            "result_file_contract": {
                "path_pattern": "jobs/<job_id>/result.json",
                "allowed_status": ["success", "partial", "failed"],
                "recommended_fields": [
                    "job_id",
                    "source_name",
                    "status",
                    "record_id",
                    "file_token",
                    "reason"
                ]
            },
            "checkpoint_file_contract": {
                "path_pattern": "jobs/<job_id>/checkpoint.json",
                "allowed_stage": ["planned", "created", "uploaded", "attachment_updated", "completed", "failed"],
                "recommended_fields": [
                    "job_id",
                    "source_name",
                    "stage",
                    "record_id",
                    "file_token",
                    "reason"
                ]
            },
            "final_summary_script": f"python3 {ROOT / 'summarize_batch_results.py'} --work-dir {work_dir}",
        },
        "must_follow": [
            "Keep user-visible replies consolidated. Prefer one final summary, with at most one short processing notice if the run is long.",
            "Treat each planned item independently. Do not reuse one resume's artifacts for another.",
            "Only execute a job's create/upload/update steps using that job's own generated plan and artifacts.",
            "Do not execute feishu_bitable_app_table_record.create, feishu_drive_file.upload, or feishu_bitable_app_table_record.update inside a subagent or isolated session. Those writes must run in the original Feishu main session so user auth context is preserved.",
            "If you split work for speed, child tasks may only produce local artifacts such as resume.txt, fields.json, create_payload.json, or validation outputs. The Feishu write steps stay in the main session.",
            "Immediately after create succeeds, write jobs/<job_id>/checkpoint.json with stage=created and the record_id. Immediately after upload succeeds, update the checkpoint to stage=uploaded with the file_token.",
            "After each job finishes, write jobs/<job_id>/result.json before moving on to the final summary step.",
            "If a run is interrupted, rerun this script with the same work_dir and resume from jobs that have checkpoint.json but no final result.json. Do not create a duplicate record when checkpoint.record_id already exists.",
            "If some jobs fail during planning, continue with the successful ones and report partial success.",
            "For ZIP inputs, ignore non-PDF files silently unless the user explicitly asks for validation details.",
        ],
        "items": results,
    }

    (work_dir / "batch_plan.json").write_text(json.dumps(batch_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(batch_plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
