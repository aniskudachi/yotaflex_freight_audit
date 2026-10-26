import json
import os
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.app import FreightAuditHandler, ServerClass, ensure_data_and_db

class TestFreightAuditWebApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_data_and_db()
        # Bind to a random port or high port on 127.0.0.1 for testing
        cls.port = 18080
        cls.host = "127.0.0.1"
        cls.httpd = ServerClass((cls.host, cls.port), FreightAuditHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path):
        url = f"http://{self.host}:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.headers, response.read()

    def test_health_endpoints(self):
        status, headers, body = self._get("/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "healthy")

        status_z, _, body_z = self._get("/healthz")
        self.assertEqual(status_z, 200)
        data_z = json.loads(body_z.decode("utf-8"))
        self.assertEqual(data_z.get("service"), "freight-audit")

    def test_static_assets_serving(self):
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"YotaFlex Freight Audit", body)
        self.assertIn("text/html", headers.get("Content-Type", ""))

        status_css, headers_css, body_css = self._get("/css/styles.css")
        self.assertEqual(status_css, 200)
        self.assertIn("text/css", headers_css.get("Content-Type", ""))

        status_js, headers_js, body_js = self._get("/js/app.js")
        self.assertEqual(status_js, 200)
        self.assertIn("javascript", headers_js.get("Content-Type", ""))

    def test_api_summary(self):
        status, headers, body = self._get("/api/summary")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["total_invoices_audited"], 150)
        self.assertIn("ground_truth_evaluation", data)
        self.assertEqual(data["ground_truth_evaluation"]["recall"], 1.0)

    def test_api_invoices(self):
        status, _, body = self._get("/api/invoices?decision=PASS")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("invoices", data)
        self.assertEqual(data["total"], 150)
        self.assertEqual(data["filtered_count"], 136)

    def test_api_carriers(self):
        status, _, body = self._get("/api/carriers")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("carriers", data)
        self.assertEqual(len(data["carriers"]), 10)

if __name__ == "__main__":
    unittest.main()
