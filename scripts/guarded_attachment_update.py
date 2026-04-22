#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "references" / "targets.json"


def load_cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8"))


def get_target(cfg: dict, target_key: str) -> dict:
    targets = dict(cfg.get("targets") or {})
    if target_key not in targets:
        raise SystemExit(f"DENY: unknown target_key: {target_key}")
    return dict(targets[target_key])


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate guarded attachment update payload")
    ap.add_argument("--target-key", default="resume_intake_v1")
    ap.add_argument("--record-id", required=True)
    ap.add_argument("--file-token", required=True)
    args = ap.parse_args()

    cfg = load_cfg()
    target = get_target(cfg, args.target_key)

    payload = {
        "target_key": args.target_key,
        "tool": "feishu_bitable_app_table_record",
        "action": "update",
        "app_token": str(target["app_token"]),
        "table_id": str(target["table_id"]),
        "record_id": args.record_id,
        "fields": {
            "附件": [
                {"file_token": args.file_token}
            ]
        }
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
