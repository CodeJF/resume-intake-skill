#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_STATUS = {"success", "partial", "failed"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a normalized per-job result.json for batch resume intake")
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--job-id")
    ap.add_argument("--source-name", default="")
    ap.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUS))
    ap.add_argument("--record-id", default="")
    ap.add_argument("--file-token", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--message", default="")
    args = ap.parse_args()

    job_dir = Path(args.job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": args.job_id or job_dir.name,
        "source_name": args.source_name,
        "status": args.status,
        "record_id": args.record_id,
        "file_token": args.file_token,
        "reason": args.reason,
        "message": args.message,
        "work_dir": str(job_dir),
    }
    out_path = job_dir / "result.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_payload = {
        "job_id": payload["job_id"],
        "source_name": payload["source_name"],
        "stage": "completed" if args.status in {"success", "partial"} else "failed",
        "record_id": payload["record_id"],
        "file_token": payload["file_token"],
        "reason": payload["reason"],
        "message": payload["message"],
        "work_dir": str(job_dir),
    }
    checkpoint_path = job_dir / "checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
