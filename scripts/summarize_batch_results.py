#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


STATUS_BUCKETS = ("success", "partial", "failed", "planned", "checkpointed")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_result(job_dir: Path) -> dict:
    result_path = job_dir / "result.json"
    error_path = job_dir / "error.json"
    tool_plan_path = job_dir / "tool_plan.json"
    checkpoint_path = job_dir / "checkpoint.json"

    if result_path.exists():
        result = load_json(result_path)
        result.setdefault("job_id", job_dir.name)
        result.setdefault("work_dir", str(job_dir))
        return result

    if error_path.exists():
        error = load_json(error_path)
        error.setdefault("job_id", job_dir.name)
        error.setdefault("work_dir", str(job_dir))
        error.setdefault("status", "failed")
        return error

    checkpoint = None
    if checkpoint_path.exists():
        checkpoint = load_json(checkpoint_path)
        checkpoint.setdefault("job_id", job_dir.name)
        checkpoint.setdefault("work_dir", str(job_dir))
        checkpoint["status"] = "checkpointed"
        checkpoint.setdefault("reason", f"执行中断，可从 stage={checkpoint.get('stage', 'unknown')} 续跑")
        return checkpoint

    source_name = ""
    if tool_plan_path.exists():
        try:
            tool_plan = load_json(tool_plan_path)
            source_name = Path(tool_plan.get("artifacts", {}).get("pdf_path", "")).name
        except Exception:
            source_name = ""

    return {
        "job_id": job_dir.name,
        "work_dir": str(job_dir),
        "status": "planned",
        "source_name": source_name,
        "reason": "尚未写入结果文件",
    }


def summarize(items: list[dict]) -> dict:
    summary = {key: 0 for key in STATUS_BUCKETS}
    for item in items:
        status = item.get("status", "planned")
        if status not in summary:
            status = "planned"
        summary[status] += 1
    summary["total"] = len(items)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize per-job batch resume intake results")
    ap.add_argument("--work-dir", required=True)
    args = ap.parse_args()

    work_dir = Path(args.work_dir)
    jobs_dir = work_dir / "jobs"
    if not jobs_dir.exists():
        raise SystemExit(f"jobs 目录不存在: {jobs_dir}")

    items = [normalize_result(job_dir) for job_dir in sorted(p for p in jobs_dir.iterdir() if p.is_dir())]
    payload = {
        "mode": "batch_resume_intake_results",
        "work_dir": str(work_dir),
        "summary": summarize(items),
        "items": items,
    }
    out_path = work_dir / "batch_result.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
