#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "references" / "targets.json"
ALLOWED_ACTIONS = {"create", "update"}
REQUIRED_CREATE_FIELDS = {"应聘者姓名"}


def load_cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8"))


def get_target(cfg: dict, target_key: str) -> dict:
    targets = dict(cfg.get("targets") or {})
    if target_key not in targets:
        raise SystemExit(f"DENY: unknown target_key: {target_key}")
    return dict(targets[target_key])


def ensure_allowed(target_key: str, action: str, target: dict) -> None:
    if action not in ALLOWED_ACTIONS:
        raise SystemExit(f"DENY: unsupported action: {action}")
    if action == "create" and not target.get("allow_create", True):
        raise SystemExit(f"DENY: create not allowed for target_key={target_key}")
    if action == "update" and not target.get("allow_update", True):
        raise SystemExit(f"DENY: update not allowed for target_key={target_key}")


def normalize_fields(fields: dict, action: str) -> dict:
    normalized = dict(fields)
    age = normalized.get("年龄")
    if isinstance(age, str) and age.strip().isdigit():
        normalized["年龄"] = int(age.strip())
    if action == "create":
        missing = [key for key in REQUIRED_CREATE_FIELDS if not normalized.get(key)]
        if missing:
            raise SystemExit(f"DENY: missing required create fields: {', '.join(missing)}")
    return normalized


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate guarded Bitable payload for an approved target")
    ap.add_argument("target_key")
    ap.add_argument("action", choices=["create", "update"])
    ap.add_argument("fields_json")
    ap.add_argument("--record-id")
    args = ap.parse_args()

    cfg = load_cfg()
    target = get_target(cfg, args.target_key)
    ensure_allowed(args.target_key, args.action, target)

    fields = json.loads(Path(args.fields_json).read_text(encoding="utf-8"))
    fields = normalize_fields(fields, args.action)
    payload = {
        "target_key": args.target_key,
        "tool": "feishu_bitable_app_table_record",
        "action": args.action,
        "app_token": str(target["app_token"]),
        "table_id": str(target["table_id"]),
        "fields": fields,
    }
    if args.action == "update":
        if not args.record_id:
            raise SystemExit("DENY: --record-id is required for update")
        payload["record_id"] = args.record_id

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
