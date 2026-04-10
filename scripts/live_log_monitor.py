#!/usr/bin/env python3
import os
import time
from datetime import datetime
from pathlib import Path


BASE = Path("/Users/gaoyangwei/Downloads/Dev1/logs")
KEYWORDS = [
    "ISSUE_DISPATCH",
    "ERROR",
    "WARNING",
    "chat_stream_start",
    "chat_stream_event",
    "chat_done",
    "chat_error",
    "login_failed",
    "connection_error",
    "create_session",
    "delete_session",
]


def current_paths():
    today = datetime.now().strftime("%Y%m%d")
    return [
        BASE / f"agens_{today}.log",
        BASE / "features" / f"chat_{today}.log",
        BASE / "features" / f"auth_{today}.log",
        BASE / "features" / f"ws_{today}.log",
        BASE / "features" / f"sessions_{today}.log",
        BASE / "features" / f"system_{today}.log",
    ]


def main():
    open_files = {}
    print("LIVE_MONITOR_STARTED", flush=True)

    while True:
        paths = current_paths()

        for p in paths:
            if p not in open_files:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch(exist_ok=True)
                f = p.open("r", encoding="utf-8", errors="ignore")
                f.seek(0, os.SEEK_END)
                open_files[p] = f
                print(f"WATCH {p}", flush=True)

        for p in list(open_files.keys()):
            if p not in paths:
                try:
                    open_files[p].close()
                except Exception:
                    pass
                del open_files[p]
                continue

            f = open_files[p]
            while True:
                line = f.readline()
                if not line:
                    break
                if any(k in line for k in KEYWORDS):
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"[{ts}] [{p.name}] {line.strip()}", flush=True)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
