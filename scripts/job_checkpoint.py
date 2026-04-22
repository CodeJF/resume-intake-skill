#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_STAGES = {
    "planned",
    "created",
    "uploaded",
    "attachment_updated",
    "completed",
    "failed",
}


def load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Write or read per-job checkpoint state for resumable batch intake")
    ap.add_argument("action", choices=["write", "show"])
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--stage")
    ap.add_argument("--job-id")
    ap.add_argument("--source-name")
    ap.add_argument("--record-id")
    ap.add_argument("--file-token")
    ap.add_argument("--reason")
    ap.add_argument("--message")
    args = ap.parse_args()

    job_dir = Path(args.job_dir)
    checkpoint_path = job_dir / "checkpoint.json"

    if args.action == "show":
        payload = load_existing(checkpoint_path)
        if not payload:
            raise SystemExit(f"checkpoint 不存在: {checkpoint_path}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not args.stage:
        raise SystemExit("write 模式必须提供 --stage")
    if args.stage not in ALLOWED_STAGES:
        raise SystemExit(f"不支持的 stage: {args.stage}")

    job_dir.mkdir(parents=True, exist_ok=True)
    payload = load_existing(checkpoint_path)
    payload.update({
        "job_id": args.job_id or payload.get("job_id") or job_dir.name,
        "source_name": args.source_name if args.source_name is not None else payload.get("source_name", ""),
        "stage": args.stage,
        "record_id": args.record_id if args.record_id is not None else payload.get("record_id", ""),
        "file_token": args.file_token if args.file_token is not None else payload.get("file_token", ""),
        "reason": args.reason if args.reason is not None else payload.get("reason", ""),
        "message": args.message if args.message is not None else payload.get("message", ""),
        "work_dir": str(job_dir),
    })
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
