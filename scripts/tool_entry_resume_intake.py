#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTRACT = ROOT / "extract_resume_text.py"
BUILD = ROOT / "build_candidate_fields.py"
GUARDED = ROOT / "guarded_bitable_write.py"
ATTACH = ROOT / "guarded_attachment_update.py"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{proc.stderr or proc.stdout}")
    return proc


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the end-to-end resume-intake tool plan")
    ap.add_argument("--target-key", default="resume_intake_v1")
    ap.add_argument("--pdf-path", required=True)
    ap.add_argument("--work-dir", required=True)
    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        raise SystemExit(f"PDF 不存在: {pdf_path}")

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    resume_txt = work_dir / "resume.txt"
    fields_json = work_dir / "fields.json"
    create_payload_json = work_dir / "create_payload.json"
    plan_json = work_dir / "tool_plan.json"

    extract_result = run([sys.executable, str(EXTRACT), str(pdf_path)])
    resume_txt.write_text(extract_result.stdout, encoding="utf-8")

    run([sys.executable, str(BUILD), str(resume_txt), str(fields_json), "--pdf-path", str(pdf_path)])
    create_result = run([sys.executable, str(GUARDED), args.target_key, "create", str(fields_json)])
    create_payload_json.write_text(create_result.stdout, encoding="utf-8")
    create_payload = json.loads(create_result.stdout)

    plan = {
        "mode": "feishu_user_toolchain",
        "strict_execution": True,
        "target_key": args.target_key,
        "artifacts": {
            "pdf_path": str(pdf_path),
            "resume_text_path": str(resume_txt),
            "fields_json_path": str(fields_json),
            "create_payload_json_path": str(create_payload_json),
        },
        "fields_preview": create_payload["fields"],
        "must_follow": [
            "Do not create a record when 应聘者姓名 is missing.",
            "Use create_payload.fields exactly as generated for the create step. Do not rename 联系方式 to 手机 or 邮箱, and do not drop payload fields based on guesswork.",
            "Only adjust a field after the Feishu tool explicitly reports a schema/type error and you have verified the real table schema.",
            "Upload the PDF as a Bitable attachment using parent_type=bitable_file and parent_node=<app_token>. Do not use a generic cloud-drive upload for this step.",
            "After feishu_drive_file.upload succeeds, use the returned file_token directly. Do not pause to grep logs or debug unless the upload tool itself returned an error.",
            "After record create + file upload succeed, immediately run guarded_attachment_update.py and then feishu_bitable_app_table_record.update.",
            "Do not send step-by-step progress messages. Send one final result only, unless blocked.",
            "If attachment update fails, report partial success and stop. Do not spend long inline debugging in the user conversation.",
        ],
        "steps": [
            {
                "step": 1,
                "tool": "feishu_bitable_app_table_record",
                "action": "create",
                "params": {
                    "app_token": create_payload["app_token"],
                    "table_id": create_payload["table_id"],
                    "fields": create_payload["fields"],
                },
                "expect": "record_id",
            },
            {
                "step": 2,
                "tool": "feishu_drive_file",
                "action": "upload",
                "params": {
                    "file_path": str(pdf_path),
                    "parent_type": "bitable_file",
                    "parent_node": create_payload["app_token"],
                },
                "expect": "file_token",
            },
            {
                "step": 3,
                "tool": "guarded_attachment_update.py",
                "command_template": f"python3 {ATTACH} --target-key {args.target_key} --record-id <record_id> --file-token <file_token>",
                "expect": "update payload json",
            },
            {
                "step": 4,
                "tool": "feishu_bitable_app_table_record",
                "action": "update",
                "params_from_step3": True,
                "success_rule": "Only after attachment update succeeds can the workflow be reported as complete success.",
            },
        ],
    }

    plan_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
