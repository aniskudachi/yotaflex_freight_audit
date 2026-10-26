import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

class TestFreightAuditSmoke(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.test_data = self.root / "test_smoke_data"
        self.test_out = self.root / "test_smoke_out"

    def tearDown(self):
        import shutil
        if self.test_data.exists():
            shutil.rmtree(self.test_data, ignore_errors=True)
        if self.test_out.exists():
            shutil.rmtree(self.test_out, ignore_errors=True)

    def test_starter_generation_and_audit(self):
        # 1. Generate starter dataset
        res_gen = subprocess.run([
            sys.executable, str(self.root / "src/generate_data.py"),
            "--scale", "starter", "--out", str(self.test_data)
        ], capture_output=True, text=True)
        self.assertEqual(res_gen.returncode, 0, f"Generator failed: {res_gen.stderr}")

        # 2. Audit invoices
        res_audit = subprocess.run([
            sys.executable, str(self.root / "src/audit_invoices.py"),
            "--data", str(self.test_data), "--out", str(self.test_out)
        ], capture_output=True, text=True)
        self.assertEqual(res_audit.returncode, 0, f"Audit failed: {res_audit.stderr}")

        # 3. Check audit results file
        results_file = self.test_out / "audit_results.csv"
        self.assertTrue(results_file.exists())
        with open(results_file, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 150)

        # 4. Check decisions
        decisions = {r["decision"] for r in rows}
        self.assertIn("PASS", decisions)
        self.assertIn("REJECT", decisions)
        self.assertIn("REVIEW", decisions)

        # 5. Check metrics
        metrics_file = self.test_out / "metrics.json"
        self.assertTrue(metrics_file.exists())
        metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        self.assertEqual(metrics["ground_truth_evaluation"]["recall"], 1.0)
        self.assertEqual(metrics["ground_truth_evaluation"]["precision"], 1.0)

if __name__ == "__main__":
    unittest.main()
