#!/usr/bin/env python3
"""Local dev server for ctbus health frontend.

Serves static files and mirrors the S3 diet/ prefix locally so the same
URLs work in development as in production (where the browser fetches from S3
directly).

Usage:
    cd pipeline/frontend
    python serve.py [port]          # default 8080, tries S3 then local files
    python serve.py [port] --local  # skip S3, use output/diet/ only
"""
import json
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent
OUTPUT_DIET_DIR = FRONTEND_DIR.parent.parent / "output" / "diet"
S3_BUCKET = "ctbus-health-data"

LOCAL_ONLY = "--local" in sys.argv

_s3 = None
if not LOCAL_ONLY:
    try:
        import boto3
        _s3 = boto3.client("s3")
        _s3.head_bucket(Bucket=S3_BUCKET)
        print(f"  S3 connected  → s3://{S3_BUCKET}/diet/")
    except Exception as e:
        print(f"  S3 unavailable ({e.__class__.__name__}), using local files")
        _s3 = None


def _list_dates():
    dates = set()
    if _s3:
        try:
            paginator = _s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="diet/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    stem = key[5:]  # strip "diet/"
                    if stem.endswith(".json") and stem != "index.json" and "/" not in stem:
                        dates.add(stem[:-5])
        except Exception as e:
            print(f"  S3 list failed: {e}")
    if OUTPUT_DIET_DIR.exists():
        for f in OUTPUT_DIET_DIR.glob("*.json"):
            if f.stem != "index":
                dates.add(f.stem)
    return sorted(dates, reverse=True)


def _fetch_day(date):
    if _s3:
        try:
            obj = _s3.get_object(Bucket=S3_BUCKET, Key=f"diet/{date}.json")
            return json.loads(obj["Body"].read())
        except Exception:
            pass
    local = OUTPUT_DIET_DIR / f"{date}.json"
    if local.exists():
        return json.loads(local.read_text())
    return None


def _all_components():
    for date in _list_dates():
        data = _fetch_day(date)
        if not data:
            continue
        for entry in data.get("entries", []):
            for comp in entry.get("components", []):
                yield date, entry, comp


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, fmt, *args):
        if self.path.startswith("/diet/") or self.path.startswith("/api/"):
            print(f"  {self.command:6} {self.path}")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/diet/index.json":
            self._json(_list_dates())
        elif path.startswith("/diet/") and path.endswith(".json"):
            date = path[6:-5]  # strip /diet/ and .json
            if len(date) == 10:
                data = _fetch_day(date)
                if data:
                    self._json(data)
                else:
                    self._json({"error": f"No data for {date}"}, 404)
            else:
                super().do_GET()
        elif path == "/api/history":
            self._handle_history(parsed.query)
        else:
            super().do_GET()

    def _handle_history(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        q = params.get("q", [""])[0].lower().strip()
        results = []
        for date, entry, comp in _all_components():
            name = comp.get("name", "")
            if not q or q in name.lower():
                results.append({
                    "date": date,
                    "timestamp": entry.get("timestamp"),
                    "name": name,
                    "quantity_g": comp.get("quantity_g"),
                    "source": comp.get("source"),
                    "barcode": comp.get("barcode"),
                    "nutrition_per_100g": comp.get("nutrition_per_100g"),
                })
            if len(results) >= 50:
                break
        self._json(results)

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = next((int(a) for a in sys.argv[1:] if a.isdigit()), 8080)
    print(f"ctbus health  →  http://localhost:{port}")
    print(f"  local diet:  {OUTPUT_DIET_DIR}")
    HTTPServer(("", port), Handler).serve_forever()
