#!/usr/bin/env python3
"""Read-only inventory tracker for created Kwork profile kworks."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from kwork_studio_common import rel, write_json, write_text


INVENTORY_DIR = DATA / "kwork_inventory"
CURRENT_INVENTORY = INVENTORY_DIR / "current_inventory.json"
PREVIOUS_INVENTORY = INVENTORY_DIR / "previous_inventory.json"
HISTORY_JSONL = INVENTORY_DIR / "history.jsonl"
REPORT_PATH = REPORTS / "kwork_inventory_report.md"
LIVE_SNAPSHOT = DATA / "kwork_profile_audit" / "live_kworks_snapshot.json"
LIVE_REPORT = REPORTS / "kwork_profile_audit_live_report.md"
MAX_SNAPSHOT_AGE_MINUTES = 30


TRACKED_FIELDS = [
    "title",
    "status",
    "price",
    "category",
    "subcategory",
    "cover_present",
    "score",
    "url",
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return {} if fallback is None else fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_history(payload: dict[str, Any]) -> None:
    ensure_dir(HISTORY_JSONL.parent)
    with HISTORY_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def snapshot_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age <= timedelta(minutes=MAX_SNAPSHOT_AGE_MINUTES)


def run_live_collector_if_needed() -> tuple[bool, str]:
    if snapshot_is_fresh(LIVE_SNAPSHOT):
        return False, "fresh snapshot exists"
    result = subprocess.run(
        ["npm", "run", "money:kwork-profile-audit-live"],
        cwd=ROOT.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        return True, f"live collector failed: {(result.stderr or result.stdout).strip()[:500]}"
    return True, "live collector refreshed snapshot"


def extract_id_from_url(url: str) -> str:
    match = re.search(r"/(?:software|development|kwork|services)/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&](?:id|kwork_id)=(\d+)", url)
    return match.group(1) if match else ""


def stable_identity(item: dict[str, Any]) -> tuple[str, str]:
    url = norm(item.get("url"))
    item_id = extract_id_from_url(url)
    if item_id:
        return f"kwork_id:{item_id}", "high"
    if url and url != "unknown":
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        return f"url:{digest}", "medium"
    base = "|".join([norm(item.get("title")).lower(), norm(item.get("price")).lower(), norm(item.get("status")).lower()])
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"weak:{digest}", "low"


def verdict_for(item: dict[str, Any]) -> tuple[str, str]:
    title = norm(item.get("title"))
    score = int(item.get("score") or item.get("marketing_score") or 0)
    price = norm(item.get("price"))
    cover = bool(item.get("cover_present"))
    status = norm(item.get("status")).lower()
    if "модерац" in status:
        return "WATCH_MODERATION", "Watch moderation status manually; do not automate moderation actions."
    if not cover:
        return "NEEDS_COVER", "Add or improve cover manually before sending more traffic."
    if len(title) < 20:
        return "NEEDS_TITLE_FIX", "Rewrite title to a concrete buyer outcome."
    if not price:
        return "NEEDS_PRICE_FIX", "Check package price manually."
    if score and score < 65:
        return "NEEDS_DESCRIPTION_FIX", "Improve description, FAQ, buyer questions, and trust blocks."
    if "minecraft" in title.lower() and 70 <= score <= 84:
        return "IMPROVE_BEFORE_TRAFFIC", "Improve title to 'Установлю и настрою Minecraft сервер', then check description/extras/questions manually."
    if score >= 85:
        return "READY_FOR_TRAFFIC", "Monitor views and replies; manual edits only."
    return "IMPROVE_BEFORE_TRAFFIC", "Review audit report and improve weak fields manually."


def normalize_item(item: dict[str, Any], previous: dict[str, Any] | None, timestamp: str) -> dict[str, Any]:
    stable_key, confidence = stable_identity(item)
    first_seen = previous.get("first_seen_at") if previous else timestamp
    verdict, action = verdict_for(item)
    return {
        "stable_key": stable_key,
        "identity_confidence": confidence,
        "title": norm(item.get("title")),
        "status": norm(item.get("status")) or "unknown",
        "price": norm(item.get("price")) or "unknown",
        "category": norm(item.get("category")) or "unknown",
        "subcategory": norm(item.get("subcategory")) or "unknown",
        "cover_present": bool(item.get("cover_present")),
        "url": norm(item.get("url")) or "unknown",
        "score": int(item.get("score") or item.get("marketing_score") or 0),
        "recommendation": verdict,
        "next_manual_action": action,
        "last_seen_at": timestamp,
        "first_seen_at": first_seen or timestamp,
    }


def load_current_from_live() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(LIVE_SNAPSHOT, {})
    items = payload.get("kworks") if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)], payload if isinstance(payload, dict) else {}


def index_items(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["stable_key"]: item for item in items}


def changed_fields(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field in TRACKED_FIELDS:
        if previous.get(field) != current.get(field):
            changes[field] = {"before": previous.get(field), "after": current.get(field)}
    return changes


def compare_inventory(previous_items: list[dict[str, Any]], current_items: list[dict[str, Any]]) -> dict[str, Any]:
    previous = index_items(previous_items)
    current = index_items(current_items)
    added = [current[key] for key in current.keys() - previous.keys()]
    missing = [previous[key] for key in previous.keys() - current.keys()]
    changed = []
    unchanged = []
    for key in current.keys() & previous.keys():
        changes = changed_fields(previous[key], current[key])
        if changes:
            item = dict(current[key])
            item["changes"] = changes
            changed.append(item)
        else:
            unchanged.append(current[key])
    return {
        "added": sorted(added, key=lambda item: item["title"]),
        "missing_now": sorted(missing, key=lambda item: item["title"]),
        "changed": sorted(changed, key=lambda item: item["title"]),
        "unchanged": sorted(unchanged, key=lambda item: item["title"]),
    }


def weakest_kwork(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return sorted(items, key=lambda item: (item.get("score", 0), item.get("title", "")))[0]


def build_report(inventory: dict[str, Any]) -> str:
    current = inventory["current"]
    diff = inventory["diff"]
    weak = weakest_kwork(current)
    lines = [
        "# Kwork Inventory Report",
        "",
        "## Summary",
        f"- total_current: `{len(current)}`",
        f"- added: `{len(diff['added'])}`",
        f"- missing_now: `{len(diff['missing_now'])}`",
        f"- changed: `{len(diff['changed'])}`",
        f"- unchanged: `{len(diff['unchanged'])}`",
        f"- last_scan_time: `{inventory['generated_at']}`",
        f"- data_collection_status: `{inventory['data_collection_status']}`",
        f"- live_snapshot: `{rel(LIVE_SNAPSHOT)}`",
        f"- current_inventory: `{rel(CURRENT_INVENTORY)}`",
        f"- previous_inventory: `{rel(PREVIOUS_INVENTORY)}`",
        f"- history: `{rel(HISTORY_JSONL)}`",
        f"- weakest_kwork: `{weak['title'] if weak else 'none'}`",
        f"- next_manual_action: `{weak['next_manual_action'] if weak else 'add or audit kworks manually'}`",
        "",
    ]
    if len(current) == 1:
        lines.extend(
            [
                "Сейчас найден 1 кворк. Это нормально для старта. Inventory tracker готов отслеживать новые кворки после добавления.",
                "",
            ]
        )

    def item_line(item: dict[str, Any]) -> str:
        return (
            f"- `{item['title']}` | status: `{item['status']}` | price: `{item['price']}` | "
            f"score: `{item['score']}` | verdict: `{item['recommendation']}` | key: `{item['stable_key']}` | "
            f"identity: `{item['identity_confidence']}`"
        )

    lines.extend(["## Current Kworks", ""])
    lines.extend(item_line(item) for item in current)
    if not current:
        lines.append("- none")

    lines.extend(["", "## Added Since Last Scan", ""])
    lines.extend(item_line(item) for item in diff["added"])
    if not diff["added"]:
        lines.append("- none")

    lines.extend(["", "## Missing Since Last Scan", ""])
    if diff["missing_now"]:
        lines.extend(item_line(item) for item in diff["missing_now"])
        lines.append("")
        lines.append("Do not assume these kworks were deleted. Treat them as `missing_now` and check manually.")
    else:
        lines.append("- none")

    lines.extend(["", "## Changed Since Last Scan", ""])
    for item in diff["changed"]:
        lines.append(item_line(item))
        for field, change in item.get("changes", {}).items():
            lines.append(f"  - {field}: `{change['before']}` -> `{change['after']}`")
    if not diff["changed"]:
        lines.append("- none")

    lines.extend(["", "## Unchanged Since Last Scan", ""])
    lines.extend(item_line(item) for item in diff["unchanged"])
    if not diff["unchanged"]:
        lines.append("- none")

    lines.extend(["", "## Recommendations", ""])
    for item in current:
        lines.extend(
            [
                f"### {item['title']}",
                f"- verdict: `{item['recommendation']}`",
                f"- first_action: `{item['next_manual_action']}`",
            ]
        )
        if "minecraft" in item["title"].lower():
            lines.extend(
                [
                    "- minecraft_action_pack: `reports/minecraft_kwork_action_pack.md`",
                    "- suggested_title: `Установлю и настрою Minecraft сервер`",
                    "- next_action: вручную проверить описание/допы/вопросы из Minecraft action pack.",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "## Safety",
            "- Inventory tracker is local/report-only.",
            "- It does not click save, moderation, publish, send, proposal, order, delete, phone, SMS, or withdrawal controls.",
            "- Missing kworks are marked `missing_now`, not deleted.",
            "- Any Kwork-changing action remains manual-only.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run() -> dict[str, Any]:
    ensure_dir(INVENTORY_DIR)
    refreshed, refresh_note = run_live_collector_if_needed()
    timestamp = now()
    live_items, live_payload = load_current_from_live()
    previous_payload = read_json(CURRENT_INVENTORY, {"current": []})
    previous_items = previous_payload.get("current", []) if isinstance(previous_payload, dict) else []
    previous_by_key = index_items([item for item in previous_items if isinstance(item, dict)])
    current_items = []
    for raw in live_items:
        key, _confidence = stable_identity(raw)
        current_items.append(normalize_item(raw, previous_by_key.get(key), timestamp))
    diff = compare_inventory([item for item in previous_items if isinstance(item, dict)], current_items)
    if CURRENT_INVENTORY.exists():
        PREVIOUS_INVENTORY.write_text(CURRENT_INVENTORY.read_text(encoding="utf-8"), encoding="utf-8")
    inventory = {
        "generated_at": timestamp,
        "source_snapshot": rel(LIVE_SNAPSHOT),
        "source_report": rel(LIVE_REPORT),
        "snapshot_refreshed": refreshed,
        "refresh_note": refresh_note,
        "data_collection_status": live_payload.get("data_collection_status", "unknown"),
        "kwork_state_changed": False,
        "final_buttons_clicked": False,
        "messages_sent": False,
        "proposals_sent": False,
        "current": current_items,
        "diff": diff,
    }
    write_json(CURRENT_INVENTORY, inventory)
    write_history(
        {
            "generated_at": timestamp,
            "total_current": len(current_items),
            "added": len(diff["added"]),
            "missing_now": len(diff["missing_now"]),
            "changed": len(diff["changed"]),
            "unchanged": len(diff["unchanged"]),
            "data_collection_status": inventory["data_collection_status"],
        }
    )
    write_text(REPORT_PATH, build_report(inventory))
    return inventory


def main() -> None:
    inventory = run()
    diff = inventory["diff"]
    print(REPORT_PATH)
    print(f"total_current={len(inventory['current'])}")
    print(f"added={len(diff['added'])}")
    print(f"missing_now={len(diff['missing_now'])}")
    print(f"changed={len(diff['changed'])}")
    print(f"unchanged={len(diff['unchanged'])}")
    print(f"data_collection_status={inventory['data_collection_status']}")
    print("final_buttons_clicked=false")
    print("kwork_state_changed=false")


if __name__ == "__main__":
    main()
