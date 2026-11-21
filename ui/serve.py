#!/usr/bin/env python3
"""Serve the Fathom analyst UI and refresh the data bundle when output appears.

    python3 /workspace/track2_ui/serve.py
    # then open http://127.0.0.1:8765/

Does not modify files inside /workspace/track2/.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TRACK2 = Path(__file__).resolve().parent.parent  # repo root (ui/ lives inside it)


def prepare(track2: Path, predictions_only: bool = False) -> None:
    sys.path.insert(0, str(HERE))
    from prepare import build
    build(track2, HERE / "data", predictions_only=predictions_only)


def watch(track2: Path, interval: float) -> None:
    output = track2 / "output" / "dev.jsonl"
    last = None
    while True:
        time.sleep(interval)
        try:
            mtime = output.stat().st_mtime if output.exists() and output.stat().st_size else None
        except FileNotFoundError:
            mtime = None
        if mtime and mtime != last:
            print(f"[watch] {output} changed — rebuilding bundle", flush=True)
            try:
                # Full rebuild so newly cited evidence is included.
                prepare(track2, predictions_only=False)
                last = mtime
            except Exception as e:
                print(f"[watch] rebuild failed: {e}", flush=True)
        elif last is None:
            last = mtime


class Handler(SimpleHTTPRequestHandler):
    track2: Path = DEFAULT_TRACK2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        if self.path.startswith("/data/") or self.path.startswith("/track2/"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/track2/"):
            rel = self.path[len("/track2/"):].split("?", 1)[0]
            # prevent path escape
            target = (self.track2 / rel).resolve()
            if self.track2.resolve() not in target.parents and target != self.track2.resolve():
                self.send_error(403, "Forbidden")
                return
            if not target.is_file():
                self.send_error(404, "Not found")
                return
            try:
                data = target.read_bytes()
            except OSError:
                self.send_error(404, "Not found")
                return
            self.send_response(200)
            if target.suffix == ".jsonl":
                self.send_header("Content-Type", "application/jsonl; charset=utf-8")
            elif target.suffix == ".json":
                self.send_header("Content-Type", "application/json; charset=utf-8")
            else:
                self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--track2", type=Path, default=DEFAULT_TRACK2)
    ap.add_argument("--no-prepare", action="store_true")
    ap.add_argument("--watch-interval", type=float, default=10.0)
    args = ap.parse_args()

    Handler.track2 = args.track2
    if not args.no_prepare:
        print("Building review bundle…", flush=True)
        prepare(args.track2)

    t = threading.Thread(target=watch, args=(args.track2, args.watch_interval), daemon=True)
    t.start()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Fathom is at http://{args.host}:{args.port}/", flush=True)
    print("Drop a new output/dev.jsonl into the track2 folder and the desk will refresh.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
