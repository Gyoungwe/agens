#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
from datetime import datetime


TASK_RE = re.compile(r"\[([a-zA-Z0-9_\-]+)\] 收到任务")
EMIT_RE = re.compile(r"\[([a-zA-Z0-9_\-]+)\] _emit type=([a-z_]+)")
RESULT_RE = re.compile(r"收到 \[([a-zA-Z0-9_\-]+)\] 的结果")


def today_log_path(base_dir: str) -> str:
    return os.path.join(base_dir, "logs", f"agens_{datetime.now():%Y%m%d}.log")


def render(states: dict) -> str:
    rows = []
    for agent_id in sorted(states.keys()):
        s = states[agent_id]
        rows.append(
            {
                "agent": agent_id,
                "status": s.get("status", "idle"),
                "event": s.get("last_event", "-"),
                "time": s.get("updated_at", "-"),
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def update_from_line(line: str, states: dict):
    now = datetime.now().strftime("%H:%M:%S")

    m = TASK_RE.search(line)
    if m:
        agent = m.group(1)
        states[agent] = {
            "status": "running",
            "last_event": "task_received",
            "updated_at": now,
        }
        return True

    m = EMIT_RE.search(line)
    if m:
        agent, event_type = m.group(1), m.group(2)
        status = "running"
        if event_type == "agent_done":
            status = "done"
        states[agent] = {
            "status": status,
            "last_event": event_type,
            "updated_at": now,
        }
        return True

    m = RESULT_RE.search(line)
    if m:
        agent = m.group(1)
        states[agent] = {
            "status": "done",
            "last_event": "result_received",
            "updated_at": now,
        }
        return True

    return False


def main():
    parser = argparse.ArgumentParser(
        description="Monitor agent status from backend logs"
    )
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--snapshot", default="logs/agent_status_snapshot.json")
    args = parser.parse_args()

    log_path = today_log_path(args.base_dir)
    if not os.path.exists(log_path):
        print(f"log file not found: {log_path}")
        return 1

    states = {}
    print(f"monitoring: {log_path}")

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(args.interval)
                continue

            if update_from_line(line, states):
                output = render(states)
                print(output, flush=True)
                with open(args.snapshot, "w", encoding="utf-8") as sf:
                    sf.write(output)


if __name__ == "__main__":
    raise SystemExit(main())
