"""
MAS Exchange Rate - 30-Day Average Calculator (local web app)
----------------------------------------------------------------
Run this, then open the link it prints in your browser.

This runs a tiny local web server on your own computer. The page in
your browser talks to this local server, and THIS SERVER (not your
browser) talks to the MAS API. That sidesteps the browser CORS block
you hit when the HTML file called MAS directly.

Needs only the Python standard library - no pip install required.

HOW TO RUN
----------
    python app.py

Then open the printed link (usually http://localhost:8765) in your
browser. Paste your MAS keyid into the page itself, same as before.
"""

import json
import os
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PORT = int(os.environ.get("PORT", 8765))

MAS_BASE_URL = (
    "https://eservices.mas.gov.sg/apimg-gw/server/"
    "monthly_statistical_bulletin_non610ora/"
    "exchange_rates_end_of_period_daily/views/"
    "exchange_rates_end_of_period_daily"
)


def extract_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("result", "results", "data", "records", "elements", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


def fetch_from_mas(date_str, field_name, keyid):
    """Call MAS server-side. Returns dict describing what happened."""
    url = f"{MAS_BASE_URL}?end_of_day={quote(date_str)}"
    req = Request(url, headers={"keyid": keyid})
    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": e.code, "raw": raw, "value": None}
    except URLError as e:
        return {"ok": False, "status": 0, "raw": f"Could not reach MAS: {e}", "value": None}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "status": status, "raw": raw, "value": None}

    rows = extract_rows(parsed)
    value = None
    if rows:
        row = rows[0]
        v = row.get(field_name) if isinstance(row, dict) else None
        if v not in (None, ""):
            try:
                value = float(v)
            except (TypeError, ValueError):
                value = None

    return {"ok": True, "status": status, "raw": raw, "value": value}


INDEX_HTML = None  # filled in at startup by reading index.html


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console quiet

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/rate":
            qs = parse_qs(parsed.query)
            date_str = qs.get("date", [""])[0]
            field = qs.get("field", [""])[0]
            keyid = qs.get("keyid", [""])[0]

            # basic validation of date format
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                self._send_json({"ok": False, "status": 0, "raw": "Bad date", "value": None}, 400)
                return

            if not keyid or not field:
                self._send_json({"ok": False, "status": 0, "raw": "Missing keyid or field", "value": None}, 400)
                return

            result = fetch_from_mas(date_str, field, keyid)
            self._send_json(result, 200)
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, obj, status):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with open("index.html", "r", encoding="utf-8") as f:
        INDEX_HTML = f.read()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Running on port {PORT}  (press Ctrl+C to stop)")
    if os.environ.get("PORT") is None:
        # only auto-open a browser tab when running on your own machine
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
