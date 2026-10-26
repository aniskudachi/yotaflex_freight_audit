#!/usr/bin/env python3
"""Interactive Freight Invoice Audit & Settlement Web Application Server.

Zero third-party dependencies — built strictly with Python's standard library.
Serves a modern, reactive web interface for Operations Managers, Logistics Analysts,
Planners, and Carriers.
"""
import argparse
import csv
import json
import mimetypes
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUT_DIR = ROOT_DIR / "outputs"
WEB_DIR = ROOT_DIR / "web"

def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def append_csv(path, row, fieldnames):
    path = Path(path)
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerow(row)

class FreightAuditHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath):
        path = Path(filepath)
        if not path.exists() or path.is_dir():
            self.send_error(404, "File Not Found")
            return
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "application/octet-stream"
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "json" in mime_type or "javascript" in mime_type else mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Static assets
        if path == "/" or path == "/index.html":
            return self._serve_file(WEB_DIR / "index.html")
        elif path.startswith("/css/") or path.startswith("/js/"):
            return self._serve_file(WEB_DIR / path.lstrip("/"))

        # API Endpoints
        if path == "/api/summary":
            metrics_file = OUT_DIR / "metrics.json"
            if metrics_file.exists():
                metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
            else:
                metrics = {"error": "Metrics not generated yet. Run audit first."}
            return self._send_json(metrics)

        elif path == "/api/invoices":
            results = read_csv(OUT_DIR / "audit_results.csv")
            # Apply filters
            decision_filter = query.get("decision", [""])[0]
            carrier_filter = query.get("carrier", [""])[0]
            issue_filter = query.get("issue", [""])[0]
            search_query = query.get("q", [""])[0].lower()

            filtered = []
            for r in results:
                if decision_filter and r["decision"] != decision_filter:
                    continue
                if carrier_filter and r["carrier_id"] != carrier_filter:
                    continue
                if issue_filter and issue_filter not in r.get("issue_types", "").split("|"):
                    continue
                if search_query:
                    match_str = f"{r['invoice_id']} {r['shipment_id']} {r['carrier_id']} {r.get('issue_types','')}".lower()
                    if search_query not in match_str:
                        continue
                filtered.append(r)

            return self._send_json({
                "total": len(results),
                "filtered_count": len(filtered),
                "invoices": filtered[:300]  # Return top 300 for snappy UI rendering
            })

        elif path == "/api/invoice-detail":
            inv_id = query.get("id", [""])[0]
            if not inv_id:
                return self._send_json({"error": "Missing invoice id"}, status=400)

            invoices = {r["invoice_id"]: r for r in read_csv(DATA_DIR / "freight_invoice.csv")}
            audit_results = {r["invoice_id"]: r for r in read_csv(OUT_DIR / "audit_results.csv")}
            lines = [l for l in read_csv(DATA_DIR / "invoice_line.csv") if l["invoice_id"] == inv_id]
            exceptions = [e for e in read_csv(OUT_DIR / "exceptions.csv") if e["invoice_id"] == inv_id]
            credits = [c for c in read_csv(OUT_DIR / "credit_note_validation.csv") if c["invoice_id"] == inv_id]
            events = [ev for ev in read_csv(OUT_DIR / "audit_events.csv") if ev["entity_id"] in (inv_id, *[c['credit_note_id'] for c in credits])]

            inv = invoices.get(inv_id) or audit_results.get(inv_id)
            if not inv:
                return self._send_json({"error": "Invoice not found"}, status=404)

            sid = inv.get("shipment_id", "")
            shipment = next((s for s in read_csv(DATA_DIR / "shipment.csv") if s["shipment_id"] == sid), None)
            rate_id = inv.get("source_rate_id") or (shipment.get("rate_id") if shipment else "")
            rate = next((r for r in read_csv(DATA_DIR / "rate_card.csv") if r["rate_id"] == rate_id), None)
            legs = [leg for leg in read_csv(DATA_DIR / "shipment_leg.csv") if leg["shipment_id"] == sid]
            weights = [w for w in read_csv(DATA_DIR / "weight_measurement.csv") if w["shipment_id"] == sid]
            accessorials = [a for a in read_csv(DATA_DIR / "accessorial.csv") if a["shipment_id"] == sid]
            gt = next((g for g in read_csv(DATA_DIR / "ground_truth.csv") if g["invoice_id"] == inv_id), None)

            # Calculate expected line breakdown if rate exists
            expected_breakdown = []
            if rate and shipment:
                base_val = float(rate["base_rate"])
                fuel_val = round(base_val * float(rate["fuel_pct"]), 2)
                expected_breakdown.append({"line_type": "BASE", "amount": base_val, "description": "Contracted base freight"})
                expected_breakdown.append({"line_type": "FUEL", "amount": fuel_val, "description": f"Contracted fuel surcharge ({float(rate['fuel_pct'])*100:.0f}%)"})
                for acc in accessorials:
                    if acc.get("eligible") == "true" and acc.get("approved") == "true":
                        expected_breakdown.append({
                            "line_type": acc["code"],
                            "amount": float(acc["amount"]),
                            "description": f"Approved {acc['code']}"
                        })

            return self._send_json({
                "invoice": inv,
                "audit_result": audit_results.get(inv_id, {}),
                "shipment": shipment,
                "rate_card": rate,
                "lines": lines,
                "expected_lines": expected_breakdown,
                "legs": legs,
                "weight_measurements": weights,
                "accessorials": accessorials,
                "exceptions": exceptions,
                "credit_notes": credits,
                "audit_events": events,
                "ground_truth": gt
            })

        elif path == "/api/exceptions":
            exceptions = read_csv(OUT_DIR / "exceptions.csv")
            return self._send_json({"total": len(exceptions), "exceptions": exceptions})

        elif path == "/api/credit-notes":
            credits = read_csv(OUT_DIR / "credit_note_validation.csv")
            return self._send_json({"total": len(credits), "credit_notes": credits})

        elif path == "/api/validation":
            val_file = OUT_DIR / "validation_summary.json"
            if val_file.exists():
                val_data = json.loads(val_file.read_text(encoding="utf-8"))
            else:
                val_data = {"error": "Validation summary not available"}
            return self._send_json(val_data)

        elif path == "/api/carriers":
            carriers = read_csv(DATA_DIR / "carrier.csv")
            return self._send_json({"carriers": carriers})

        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        data = json.loads(body) if body else {}

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if path == "/api/run-audit":
            # Execute audit_invoices.py
            cmd = [sys.executable, str(ROOT_DIR / "src/audit_invoices.py"), "--data", str(DATA_DIR), "--out", str(OUT_DIR)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            metrics_file = OUT_DIR / "metrics.json"
            metrics = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.exists() else {}
            return self._send_json({
                "status": "SUCCESS" if res.returncode == 0 else "ERROR",
                "output": res.stdout,
                "metrics": metrics
            })

        elif path == "/api/regenerate":
            scale = data.get("scale", "starter")
            seed = int(data.get("seed", 20261022))
            cmd_gen = [sys.executable, str(ROOT_DIR / "src/generate_data.py"), "--scale", scale, "--seed", str(seed), "--out", str(DATA_DIR)]
            res_gen = subprocess.run(cmd_gen, capture_output=True, text=True)
            cmd_aud = [sys.executable, str(ROOT_DIR / "src/audit_invoices.py"), "--data", str(DATA_DIR), "--out", str(OUT_DIR)]
            res_aud = subprocess.run(cmd_aud, capture_output=True, text=True)
            cmd_sql = [sys.executable, str(ROOT_DIR / "src/load_sqlite.py"), "--data", str(DATA_DIR), "--db", str(OUT_DIR / "freight_audit.db"), "--outputs", str(OUT_DIR)]
            subprocess.run(cmd_sql, capture_output=True)
            cmd_val = [sys.executable, str(ROOT_DIR / "src/validate_data.py"), "--data", str(DATA_DIR), "--out", str(OUT_DIR / "validation_summary.json")]
            subprocess.run(cmd_val, capture_output=True)

            return self._send_json({
                "status": "SUCCESS" if res_gen.returncode == 0 and res_aud.returncode == 0 else "ERROR",
                "scale": scale,
                "seed": seed
            })

        elif path == "/api/action":
            # Simulated workflow action: dispute, approve, issue credit
            action_type = data.get("action")  # DISPUTE, APPROVE, CREDIT_MEMO, RESOLVE
            inv_id = data.get("invoice_id")
            actor = data.get("actor", "Logistics Analyst")
            notes = data.get("notes", "")

            event_row = {
                "event_id": f"EVT-2026-{int(datetime.now().timestamp()) % 1000000:06d}",
                "entity_type": "INVOICE",
                "entity_id": inv_id,
                "previous_state": "AUDITED",
                "new_state": action_type,
                "actor": actor,
                "notes": notes or f"Action {action_type} recorded by {actor}.",
                "timestamp": now_iso
            }

            fieldnames = ["event_id", "entity_type", "entity_id", "previous_state", "new_state", "actor", "notes", "timestamp"]
            append_csv(OUT_DIR / "audit_events.csv", event_row, fieldnames)

            return self._send_json({
                "status": "SUCCESS",
                "event": event_row,
                "message": f"Action '{action_type}' recorded successfully."
            })

        else:
            self.send_error(404, "Action Not Found")

def start_server(port=8080):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, FreightAuditHandler)
    print(f"============================================================")
    print(f" Freight Audit & Settlement System running at:")
    print(f" http://127.0.0.1:{port}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Freight Audit Web Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    start_server(args.port)
